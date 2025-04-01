import json
import os
import re
from abc import ABC, abstractmethod
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import chromadb
import ollama
from chromadb.errors import InvalidCollectionException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

from documents.diario import DiarioOficial
from util.logger_config import setup_logger

logger = setup_logger()


class DocumentoDiarioOficial(BaseModel):
    """
    Esquema para dados estruturados extraídos de documentos do diário oficial.
    """

    categoria: Optional[str] = Field(
        default="",
        description="Categoria do documento",
        examples=["acordao", "resolucao", "notificacao"],
    )
    sessao: Optional[str] = Field(
        default="",
        description="Data da sesão representada no diário oficial",
        examples=["3 de Março de 2025"],
    )
    numero: Optional[str] = Field(default="", description="Número do documento")
    publicacao: Optional[str] = Field(
        default="",
        description="Data da publicação do diário oficial em DD/MM/YYYY",
        examples=["03/03/2025"],
    )
    numero_diario: Optional[str] = Field(
        default="",
        description="Número do diário oficial",
        examples=["1.2345"],
    )

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


class ListaDocumentos(DocumentoDiarioOficial):
    documentos: List[DocumentoDiarioOficial] = Field(
        default_factory=list,
        description="Lista de documentos extraídos do diário oficial",
    )


class DocumentoBase(ListaDocumentos, ABC):
    """
    Classe base para todos os tipos de documentos extraídos do Diário Oficial.

    Fornece métodos comuns, como:
      - Limpeza e normalização de texto
      - Extração de chaves e seus conteúdos
      - Redação de dados pessoais
      - Criação de cache de documentos local para evitar multiplos downloads
      - Tokenização do texto em uma base de vetores vetorial
    """

    def _document_type(self) -> str:
        """Retorna o tipo de documento."""
        return self.__class__.__name__.lower()

    @abstractmethod
    def _extract_data(self) -> None:
        """
        Extrai dados estruturados do texto bruto.
        Deve ser implementado por cada subclasse.
        """
        pass

    def _get_doc_id(self, pattern: str, texto: str) -> str:
        # match = re.search(r"ACÓRDÃO Nº (\d+\.\d+)", clean_raw)
        match = re.search(rf"{pattern}", texto)
        doc_id = match.group(1).replace(".", "")
        return doc_id
    
    def _is_there_personal_data(self, texto: str) -> bool:
        """
        Identifica se existem pessoais no texto.
        Inicial buscaremos por CPFs no seguinte padrao:
        CPF: 123.456.789-10
        """
        logger.debug(f"Identificando dados pessoais no texto: {texto}")
        cpf_matches = re.findall(r"CPF:\d{3}\.\d{3}\.\d{3}-\d{2}" , texto, re.MULTILINE)
        if cpf_matches:
            logger.warning(f"CPF encontrado no texto: {cpf_matches}")
            return True
        return False
        

    def _redact_personal_data(self, text: str) -> str:
        """
        Redige dados pessoais, por exemplo, CPF.
        """
        logger.debug(f"Redigindo dados pessoais do texto: {text}")
        return re.sub(r"\d{3}\.\d{3}\.\d{3}-?\d{2}", "[REDIGIDO]", text)

    def clean_text(self, text: str) -> str:
        """
        Realiza limpeza e normalização do texto.
        """
        if not text:
            logger.warning("Texto vazio fornecido para limpeza")
            return ""
        logger.info("Iniciando limpeza do texto")
        padroes = [
            r"(?m)Consulta via leitor de QR Code.*?diario-eletronico\.",
            r"https?://www\.tcmpa\.tc\.br/?",
            r"www\.tcm\.pa\.gov\.br",
            r"BIÊNIO – \w+ de \d{4}/\w+ de \d{4}",
            r"Redes Sociais \d+ Páginas",
            r"^\s*-\s*$",
            r"[\uf0e7\uf038\uf039\uf028\uf02b]",
            r"\\uf[0-9A-Fa-f]{3,}",
            r"\uf03c",
            r"(?m)^\s*(?:Publicado por:.*?$)",
        ]
        for padrao in padroes:
            text = re.sub(padrao, "", text, flags=re.DOTALL)
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n", "", text)
        if self._is_there_personal_data(text):
            text = self._redact_personal_data(text)
        logger.success("Texto limpo com sucesso")
        return text.strip()

    def _get_keys(self, text: Optional[str] = None) -> List[str]:
        """
        Extrai possíveis chaves (nomes de campos) do texto.
        """
        if text is None:
            text = self.texto_original

        pattern = r"(?!PA:)\w*[\(\w*\)]*(?=:\s)"

        logger.info("Extraindo chaves do texto")
        matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
        logger.success(f"Chaves encontradas: {matches}")
        filtered_keys = []
        for key in matches:
            key = key.strip()
            if (
                key.lower() not in ("cpf", "endereço", "(cpf", "(cpf)")
                and key not in filtered_keys
            ):
                if len(key) > 1 and key[0].isupper():
                    filtered_keys.append(key)
        logger.debug(f"Chaves filtradas: {filtered_keys}")
        return filtered_keys

    def _extract_key_content(
        self, text: Optional[str] = None, keys: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        A partir de uma lista de chaves, extrai os respectivos conteúdos do texto.
        """
        if text is None:
            text = self.texto_original
        if keys is None:
            keys = self._get_keys(text)
        values = {}
        for i, key in enumerate(keys):
            if i < len(keys) - 1:
                next_key = keys[i + 1]
                pattern = rf"{re.escape(key)}:\s*(.*?)\s*(?={re.escape(next_key)}:)"
            else:
                pattern = rf"{re.escape(key)}:\s*(.*)$"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                logger.debug(f"Match found for {key}")
                value = match.group(1).strip()
                if key.lower() == "município":
                    value = self.validate_municipio(key_value=value)
                if key.lower() == "instrução":
                    value = self.validate_controladoria(key_value=value)
                values[re.sub(r"\s+", "_", key.lower())] = self.clean_text(value)
            else:
                logger.warning(f"No match found for {key}")
                values[key.lower()] = ""
        return values

    def validate_municipio(self, key_value: str) -> str:
        """
        Valida se uma string contém o nome de um município válido do Pará.

        Args:
            key_value (str): Texto onde será buscado o nome do município.

        Returns:
            str: Nome do município formatado corretamente se encontrado, ou o valor original.

        Exemplo:
            >>> validate_municipio("Processo referente a Belém.")
            'Belém'
            
            >>> validate_municipio("Texto sem município")
            'Texto sem município'

        Exceções:
            AttributeError: Se o input não for uma string.
        """
        municipios = [
            "Abaetetuba",
            "Abel Figueiredo",
            "Acará",
            "Afuá",
            "Água Azul do Norte",
            "Alenquer",
            "Almeirim",
            "Altamira",
            "Anajás",
            "Ananindeua",
            "Anapu",
            "Augusto Corrêa",
            "Aurora do Pará",
            "Aveiro",
            "Bagre",
            "Baião",
            "Bannach",
            "Barcarena",
            "Belém",
            "Belterra",
            "Benevides",
            "Bom Jesus do Tocantins",
            "Bonito",
            "Bragança",
            "Brasil Novo",
            "Brejo Grande do Araguaia",
            "Breu Branco",
            "Breves",
            "Bujaru",
            "Cachoeira do Arari",
            "Cachoeira do Piriá",
            "Cametá",
            "Canaã dos Carajás",
            "Capanema",
            "Capitão Poço",
            "Castanhal",
            "Chaves",
            "Colares",
            "Conceição do Araguaia",
            "Concórdia do Pará",
            "Cumaru do Norte",
            "Curionópolis",
            "Curralinho",
            "Curuá",
            "Curuçá",
            "Dom Eliseu",
            "Eldorado do Carajás",
            "Faro",
            "Floresta do Araguaia",
            "Garrafão do Norte",
            "Goianésia do Pará",
            "Gurupá",
            "Igarapé-Açu",
            "Igarapé-Miri",
            "Inhangapi",
            "Ipixuna do Pará",
            "Irituia",
            "Itaituba",
            "Itupiranga",
            "Jacareacanga",
            "Jacundá",
            "Juruti",
            "Limoeiro do Ajuru",
            "Mãe do Rio",
            "Magalhães Barata",
            "Marabá",
            "Maracanã",
            "Marapanim",
            "Marituba",
            "Medicilândia",
            "Melgaço",
            "Mocajuba",
            "Moju",
            "Mojuí dos Campos",
            "Monte Alegre",
            "Muaná",
            "Nova Esperança do Piriá",
            "Nova Ipixuna",
            "Nova Timboteua",
            "Novo Progresso",
            "Novo Repartimento",
            "Óbidos",
            "Oeiras do Pará",
            "Oriximiná",
            "Ourém",
            "Ourilândia do Norte",
            "Pacajá",
            "Palestina do Pará",
            "Paragominas",
            "Parauapebas",
            "Pau D'Arco",
            "Peixe-Boi",
            "Piçarra",
            "Placas",
            "Ponta de Pedras",
            "Portel",
            "Porto de Moz",
            "Prainha",
            "Primavera",
            "Quatipuru",
            "Redenção",
            "Rio Maria",
            "Rondon do Pará",
            "Rurópolis",
            "Salinópolis",
            "Salvaterra",
            "Santa Bárbara do Pará",
            "Santa Cruz do Arari",
            "Santa Isabel do Pará",
            "Santa Luzia do Pará",
            "Santa Maria das Barreiras",
            "Santa Maria do Pará",
            "Santana do Araguaia",
            "Santarém",
            "Santarém Novo",
            "Santo Antônio do Tauá",
            "São Caetano de Odivelas",
            "São Domingos do Araguaia",
            "São Domingos do Capim",
            "São Félix do Xingu",
            "São Francisco do Pará",
            "São Geraldo do Araguaia",
            "São João da Ponta",
            "São João de Pirabas",
            "São João do Araguaia",
            "São Miguel do Guamá",
            "São Sebastião da Boa Vista",
            "Sapucaia",
            "Senador José Porfírio",
            "Soure",
            "Tailândia",
            "Terra Alta",
            "Terra Santa",
            "Tomé-Açu",
            "Tracuateua",
            "Trairão",
            "Tucumã",
            "Tucuruí",
            "Ulianópolis",
            "Uruará",
            "Vigia",
            "Viseu",
            "Vitória do Xingu",
            "Xinguara",
        ]
        municipio_regex = re.compile(
            r"\b(" + "|".join(municipios) + r")\b", re.IGNORECASE
        )
        match = municipio_regex.search(key_value)
        if match:
            # Retorna o municipio encontrado
            municipio_name = match.group(1)
            return municipio_name
        else:
            # Retorna o valor original
            return key_value

    def validate_controladoria(self, key_value: str) -> str:
        """
        Valida se não existe texto em acesso quando estamos buscando somente o metadado
        referente ao número da controladoria.

        Args:
            key_value (str): Texto onde será buscado o padrão.

        Returns:
            str: Texto correspondente ao padrão encontrado ou valor original.

        Exemplo:
            >>> validate_controladoria("2° Controladoria foi responsável pela...")
            '2° Controladoria'
            # se já estiver dentro do padrão, somente retornamos o valor
            >>> validate_controladoria("2° Controladoria")
            '2° Controladoria'

        Exceções:
            AttributeError: Se o input não for uma string.
        """
        controladoria_regex = re.compile(r"(\d.\sControladoria)")
        match = controladoria_regex.search(key_value)
        if match:
            controladoria = match.group(1)
            return controladoria
        else:
            return key_value

    def _cache_entry(
        self,
        texto: str,
        diario: DiarioOficial,
        data: dict | DocumentoDiarioOficial,
        format="json",
    ):
        """
        Armazena localmente o conteúdo processado em um arquivo JSON ou texto.

        Args:
            texto (str): Texto original completo do documento
            diario (DiarioOficial): Instância do diário oficial
            data (dict | DocumentoDiarioOficial): Dados processados do documento
            format (str): Formato de saída ('json' ou 'txt')

        Returns:
            None

        Exemplo:
            >>> self._cache_entry(
                "Texto completo...",
                diario_instance,
                DocumentoDiarioOficial(categoria="Lei", numero="123.45"),
                "json"
            )

        Exceções:
            FileNotFoundError: Registro em log se o caminho não existir
            OSError: Registrao em log para erros de sistema
            Exception: Captura erros genéricos e registra em log
        """
        try:
            # Cria uma id para a criação do nome do arquivo, normalmente no texto original existe um '.' entres os númeroes
            file_id = data.numero.replace(".", "") if data.numero else None
            diario_id = data.numero_diario.replace(".", "") if data.numero_diario else None
            # diario.download_dir é um método da classe diário que cria uma pasta com o padrão diretorio_base/ano/mes
            path = Path(diario.download_dir) / data.categoria
            file_name = f"{diario_id}_{data.categoria}_{file_id}.{format}"
            file_path = path / file_name
            if file_path.exists():
                logger.warning(f"Arquivo {file_path} ja existe!")
                return
            data = (
                data.model_dump() if isinstance(data, DocumentoDiarioOficial) else data
            )

            # Por motivos de apresentação e redução de bloat, a class original não retorna o texto original completo
            data["texto_original"] = texto
            # Verifica se o diretorio existe, se não o cria
            os.makedirs(name=path, exist_ok=True)

            if format == "json":
                content = json.dumps(
                    (
                        data.model_dump()
                        if isinstance(data, DocumentoDiarioOficial)
                        else data
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            else:
                content = texto  # Assume raw text for other formats
            file_path.write_text(content)

            logger.info(f"Arquivo salvo com sucesso em {file_path}")
        except FileNotFoundError as e:
            logger.error(
                f"Erro ao tentar salvar o arquivo: Diretório não encontrado - {e}"
            )
        except OSError as e:
            logger.error(f"Erro ao criar diretórios ou escrever arquivo: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao tentar salvar o arquivo: {e}")

    def _get_vector_db(
        self, collection: chromadb.Collection | str, path="database/chromadb"
    ) -> chromadb.Collection:
        """
        Obtém ou cria uma coleção no banco de dados vetorial, por padrão usamos a chromadb.

        Args:
            collection (chromadb.Collection | str): Nome ou objeto da coleção
            path (str): Caminho de armazenamento do banco de dados

        Returns:
            chromadb.Collection: Coleção solicitada ou recém-criada

        Examples:
            >>> self._get_vector_db("leis_municipais")

        Exceptions:
            InvalidCollectionException: Tratada internamente para criar nova coleção
        """
        chroma = chromadb.PersistentClient(path=path)
        try:
            collection = chroma.get_collection(name=collection)
            return collection
        except InvalidCollectionException:
            collection = chroma.create_collection(
                name=collection,
                metadata={"hnsw:space": "cosine"}
                )
            return collection

    def _tokenize_and_store(self, texto: str, metadados: dict, database: str):
        """
        Tokeniza texto e armazena embeddings no banco vetorial com metadados.

        Args:
            texto (str): Conteúdo textual a ser tokenizado
            metadados (dict): Metadados do documento com campos obrigatórios:
                - categoria (str): Classificação do documento
                - numero (str): Identificador único do documento em sua categoria
            database (str): Nome da coleção de destino

        Returns:
            None

        Examples:
            >>> self._tokenize_and_store(
                "Texto do documento...",
                {"categoria": "acordao", "numero": "123.45", "local": "Belém"},
                "coleção_leis"
            )

        Exceptions:
            ValueError: Se metadados não contiverem 'categoria' ou 'numero'
            ServerError: Erros de conexão com o servidor de embeddings
            APIError: Erros na API do ChromaDB
        """

        vector_db = self._get_vector_db(database)
        existing_entries = vector_db.get(
            where={
                "$and": [
                    {"categoria": metadados.get("categoria")},
                    {"numero": metadados.get("numero")},
                ]
            }
        )
        if existing_entries["ids"]:
            logger.warning(
                f"Documento com categoria '{metadados['categoria']}' e de '{metadados['numero']}' ja  Tokenizado"
            )
            return
        #tokenizer = ollama.Client(host="http://10.2.10.115:11434")
        #embed = tokenizer.embed(input=texto, model="llama3.1")
        #embed = SentenceTransformer("all-MiniLM-L6-v2")
        #embeddings = embed.encode([texto])
        #logger.debug(f'Embeddings: {embeddings.shape}')
        if metadados.get("local"):
            metadados["pdf"] = metadados.pop("local")
            metadados["pdf"] = metadados["pdf"].get("pdf")
        metadata = {**metadados}
        # Example: Using a hypothetical vector DB client
        vector_db.add(
            #embeddings=embeddings.tolist(),
            documents=[texto],
            metadatas=[metadata],
            ids=metadados.get("numero"),
        )

    def _extract_field(self, pattern: str, flags: int = 0) -> Optional[str]:
        """
        Extrai um único campo do texto usando o padrão regex fornecido.
        """
        match = re.search(pattern, self.texto_original, flags)
        return match.group(1).strip() if match else None

    def _get_documents_month(self, diario: DiarioOficial) -> List[str]:
        lista_diarios = glob(diario.download_dir)
        return lista_diarios

    def __str__(self) -> str:
        """
        Customizes the string representation of the DiarioOficial object.
        Shows a preview of texto_original (first 100 characters) instead of the full text.

        Returns:
            str: The formatted string representation
        """
        # Create a preview of texto_original
        texto_preview = (
            f"{self.texto_original[:100]}..."
            if self.texto_original
            else "No text extracted"
        )

        # Get all object attributes except texto_original
        attributes = self.model_dump()
        if "texto_original" in attributes:
            attributes["texto_original"] = texto_preview

        # Format the representation
        formatted_attrs = ", ".join([f"{k}={repr(v)}" for k, v in attributes.items()])
        return f"DiarioOficial({formatted_attrs})"

    def __repr__(self) -> str:
        """
        Override __repr__ to ensure that nested representations use the truncated version.
        """
        return self.__str__()
