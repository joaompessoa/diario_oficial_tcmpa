import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator, root_validator
from documents.diario import DiarioOficial, DataDiario
import json
import os
from util.logger_config import logger


# -----------------------------
# Data Model for Document Fields
# -----------------------------
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
        description="Data da publicação representada no diário oficial",
        examples=["3 de Março de 2025"],
    )
    numero: Optional[str] = Field(default="", description="Número do documento")
    publicacao: Optional[str] = Field(
        default="",
        description="Data da publicação do diário oficial em DD/MM/YYYY",
        examples=["03/03/2025"],
    )
    texto_original: Optional[str] = Field(
        default="", description="Texto limpo (processado) do documento"
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
        return text.strip()

    # def _get_keys(self, text: Optional[str] = None) -> List[str]:
    #     """
    #     Extrai possíveis chaves (nomes de campos) do texto.
    #     """
    #     if text is None:
    #         text = self.texto_original
    #     pattern = r"(?!PA:)[\(A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+[\(A-Za-záéíóúàâêôçüãõ\)](?=:)"


    #     logger.info("Extraindo chaves do texto")
    #     matches = re.findall(pattern, text)
    #     logger.debug(f"Chaves encontradas: {matches}")
    #     filtered_keys = []
    #     for match in matches:
    #         match = match.strip()
    #         if match.lower() not in ("cpf", "endereço", "(cpf") and match not in filtered_keys:
    #             if len(match) > 2:
    #                 logger.debug(f'Chave {match} passou nos filtros')
    #                 filtered_keys.append(match)
    #     return filtered_keys
    def _get_keys(self, text: Optional[str] = None) -> List[str]:
        """
        Extrai possíveis chaves (nomes de campos) do texto.
        """
        if text is None:
            text = self.texto_original
        
        #pattern = r'\b(?!PA:)([A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ][a-záéíóúàâêôçüãõ]+)(?=\s*:)'
        #pattern = r'(?!PA:)[\(A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+[\s*\(A-Za-záéíóúàâêôçüãõ\)](?=:)'
        pattern = r'(?!PA:)\w*(?=:\s)'
        
        #pattern = r'\b(?!PA:)((?:[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ][a-záéíóúàâêôçüãõ]+|[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+)(?:\s+(?:[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ][a-záéíóúàâêôçüãõ]+|[A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+))*)(?=\s*:)'
        logger.info("Extraindo chaves do texto")
        matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
        logger.debug(f"Chaves encontradas: {matches}")
        filtered_keys = []
        for key in matches:
            key = key.strip()
            if key.lower() not in ("cpf", "endereço", "(cpf", "(cpf)") and key not in filtered_keys:
                if len(key) > 1 and key[0].isupper():
                    filtered_keys.append(key)
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
                if key.lower() == 'município':
                    value = self.validate_municipio(key_value=value)
                if key.lower() == 'instrução':
                    value = self.validate_controladoria(key_value=value)
                values[re.sub(r"\s+", "_", key.lower())] = self.clean_text(value)
            else:
                logger.warning(f"No match found for {key}")
                values[key.lower()] = ""
        return values
    
    def validate_municipio(self, key_value: str):
        municipios = [
            "Abaetetuba", "Abel Figueiredo", "Acará", "Afuá", "Água Azul do Norte", "Alenquer", "Almeirim", "Altamira",
            "Anajás", "Ananindeua", "Anapu", "Augusto Corrêa", "Aurora do Pará", "Aveiro", "Bagre", "Baião", "Bannach",
            "Barcarena", "Belém", "Belterra", "Benevides", "Bom Jesus do Tocantins", "Bonito", "Bragança", "Brasil Novo",
            "Brejo Grande do Araguaia", "Breu Branco", "Breves", "Bujaru", "Cachoeira do Arari", "Cachoeira do Piriá",
            "Cametá", "Canaã dos Carajás", "Capanema", "Capitão Poço", "Castanhal", "Chaves", "Colares", "Conceição do Araguaia",
            "Concórdia do Pará", "Cumaru do Norte", "Curionópolis", "Curralinho", "Curuá", "Curuçá", "Dom Eliseu",
            "Eldorado do Carajás", "Faro", "Floresta do Araguaia", "Garrafão do Norte", "Goianésia do Pará", "Gurupá",
            "Igarapé-Açu", "Igarapé-Miri", "Inhangapi", "Ipixuna do Pará", "Irituia", "Itaituba", "Itupiranga", "Jacareacanga",
            "Jacundá", "Juruti", "Limoeiro do Ajuru", "Mãe do Rio", "Magalhães Barata", "Marabá", "Maracanã", "Marapanim",
            "Marituba", "Medicilândia", "Melgaço", "Mocajuba", "Moju", "Mojuí dos Campos", "Monte Alegre", "Muaná",
            "Nova Esperança do Piriá", "Nova Ipixuna", "Nova Timboteua", "Novo Progresso", "Novo Repartimento", "Óbidos",
            "Oeiras do Pará", "Oriximiná", "Ourém", "Ourilândia do Norte", "Pacajá", "Palestina do Pará", "Paragominas",
            "Parauapebas", "Pau D'Arco", "Peixe-Boi", "Piçarra", "Placas", "Ponta de Pedras", "Portel", "Porto de Moz",
            "Prainha", "Primavera", "Quatipuru", "Redenção", "Rio Maria", "Rondon do Pará", "Rurópolis", "Salinópolis",
            "Salvaterra", "Santa Bárbara do Pará", "Santa Cruz do Arari", "Santa Isabel do Pará", "Santa Luzia do Pará",
            "Santa Maria das Barreiras", "Santa Maria do Pará", "Santana do Araguaia", "Santarém", "Santarém Novo",
            "Santo Antônio do Tauá", "São Caetano de Odivelas", "São Domingos do Araguaia", "São Domingos do Capim",
            "São Félix do Xingu", "São Francisco do Pará", "São Geraldo do Araguaia", "São João da Ponta", "São João de Pirabas",
            "São João do Araguaia", "São Miguel do Guamá", "São Sebastião da Boa Vista", "Sapucaia", "Senador José Porfírio",
            "Soure", "Tailândia", "Terra Alta", "Terra Santa", "Tomé-Açu", "Tracuateua", "Trairão", "Tucumã", "Tucuruí",
            "Ulianópolis", "Uruará", "Vigia", "Viseu", "Vitória do Xingu", "Xinguara"
        ]
        municipio_regex = re.compile(
                r'\b(' + '|'.join(municipios) + r')\b', re.IGNORECASE
            )
        match = municipio_regex.search(key_value)
        if match:
            # This returns only the matched municipality name.
            municipio_name = match.group(1)
            return municipio_name
        else:
            return key_value
        
    def validate_controladoria(self, key_value:str):
        controladoria_regex = re.compile(r'(\d.\sControladoria)')
        match = controladoria_regex.search(key_value)
        if match:
            controladoria = match.group(1)
            return controladoria
        else:
            return key_value

    def _extract_field(self, pattern: str, flags: int = 0) -> Optional[str]:
        """
        Extrai um único campo do texto usando o padrão regex fornecido.
        """
        match = re.search(pattern, self.texto_original, flags)
        return match.group(1).strip() if match else None

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
