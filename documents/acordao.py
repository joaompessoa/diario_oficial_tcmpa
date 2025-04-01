import re
from util.logger_config import setup_logger
from typing import Dict, Any, List, Optional
from documents.document import DocumentoBase, DocumentoDiarioOficial
from documents.diario import DiarioOficial, DataDiario

logger = setup_logger("acordao")

class Acordao(DocumentoBase):
    """
    Classe representando um Acórdão extraído do Diário Oficial.

    Um Acórdão é um documento de decisão emitido pelo tribunal com estrutura
    específica e metadados que precisam ser extraídos para análise posterior.
    """

    def __init__(self, diario: Optional[DiarioOficial] = None) -> None:
        """
        Inicializa a classe.

        Args:
            diario (Optional[DiarioOficial]): Diário oficial de onde extrair os documentos.
            Se não fornecido, cria um novo para a data atual.
        """
        logger.debug(f"Inicializando {self.__class__.__name__}...")

        if not diario:
            logger.warning(f"Nenhum diario disponibilizado, usando o dia de hoje!")
            diario = DiarioOficial()

        super().__init__(diario=diario)

        self.publicacao = diario.publicacao
        self.texto_original = diario.texto_original
        self.categoria = self._document_type()
        self.diario = diario
        self.documentos = self._extract_data(diario=self.diario)

    def _extract_data(self, diario: DiarioOficial) -> List[DocumentoDiarioOficial]:
        """
        Processa o texto do diário, dividindo-o em seções para cada Acórdão, então retorna os dados de cada
        seção em uma lista de objetos DocumentoDiarioOficial (criado em documents/document.py).

        Returns:
            List[DocumentoDiarioOficial]: Documentos extraídos.
        """
        texto_original = diario.texto_original
        extracted_documents: List[DocumentoDiarioOficial] = []
        sections = self.get_sections(text=texto_original)
        if not sections:
            logger.warning("Nenhuma seção encontrada no texto bruto.")
            return extracted_documents

        for section in sections:
            # Limpa o texto da seção
            # clean_raw = self.clean_text(section)
            clean_raw = section
            data_dict: Dict[str, Any] = {"categoria": self.categoria}
            

            # Extrai o número do acórdão
            match = re.search(r"ACÓRDÃO Nº (\d+\.\d+)", clean_raw)
            if match:
                data_dict["numero"] = match.group(1)
            else:
                logger.warning("No acórdão number found in section; skipping section.")
                continue
            processo_pattern = re.compile(
                r'PROCESSO\s+N[º°]\s+([\d\.]+(?:\s*\([\d\.]+\))?)',
                re.IGNORECASE
            )
            processo_match = processo_pattern.search(clean_raw)

            if processo_match:
                data_dict["processo"] = processo_match.group(1)
            else:
                logger.warning(f"Sem processo para {self.categoria}")

            # Extrai pares chave:valor e limpa cada valor
            keys = self._get_keys(clean_raw)
            extracted_data = self._extract_key_content(clean_raw, keys=keys)
            for key, value in extracted_data.items():
                data_dict[key.lower()] = value  # self.clean_text(value)

            # Extrai a data da sessão utilizando um padrão
            date_pattern = (
                r"(\d+(?:\s+a\s+\d+)?\s+de\s+"
                r"(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
                r"\s+de\s+\d{4})"
            )
            date_match = re.search(
                f"Sessão Eletrônica.*?{date_pattern}", clean_raw, re.DOTALL
            )
            if date_match:
                data_dict["sessao"] = date_match.group(1).strip()
            else:
                alt_date_match = re.search(date_pattern, clean_raw)
                if alt_date_match:
                    data_dict["sessao"] = alt_date_match.group(1).strip()

            # Redige dados pessoais conforme LGPD
            for field in [
                "ordenador",
                "responsavel",
                "representante_legal",
                "interessado",
                "recorrente"
            ]:
                if field in data_dict and data_dict[field]:
                    data_dict[field] = self._redact_personal_data(data_dict[field])

            # Armazena um texto de exemplo do original
            data_dict["sample_texto"] = f'{clean_raw[:100]}...'
            # Certifique-se de que "data_diario" esteja presente; use self.data_diario se existir, ou uma string vazia
            data_dict["publicacao"] = getattr(self, "publicacao", "")
            data_dict["numero_diario"] = diario.numero_diario
            data_dict["ioepa"] = diario.internet_path
            data_dict["local"] = {"caminho": diario.local_path, "pdf": diario.pdf_file}

            logger.debug(f"Extracted {self.__class__.__name__}...) {data_dict.get('numero', 'unknown')}")
            try:
                documento = DocumentoDiarioOficial(**data_dict)
                extracted_documents.append(documento)
                logger.success(
                    f"Acordaos extraídos com sucesso: {data_dict.get('numero', 'unknown')}"
                )
                try:
                    self._cache_entry(texto=section, diario=diario, data = documento, format='json')
                    self._tokenize_and_store(texto=section, metadados=data_dict, database=self.categoria)
                    logger.success(f'{self.categoria}:{data_dict.get('numero')} do dia {self.publicacao} tokenizado com sucesso ')
                except Exception as e:
                    logger.error(f'Erro ao tentar tokenizar os documentos {e}')
            except Exception as e:
                logger.error(f"Erro ao criar DocumentoDiarioOficial para seção: {e}")

        return extracted_documents


    def get_sections(self, text: str = None) -> List[str]:
        """
        Extrai os acórdãos do Diário Oficial

        Args:
            text (str): O texto original do diário.

        Returns:
            list: A list of dictionaries, each containing the structured data of an acórdão.
        """
        if not text:
            text = self.texto_original

        acordao_pattern = r"ACÓRDÃO\s+Nº\s+(\d+\.\d+)"
        acordao_matches = list(re.finditer(acordao_pattern, text))

        # Define os delimitadores de seção mais comuns
        section_delimiters = [
            "DO GABINETE DA PRESIDÊNCIA",
            "PAUTA DE JULGAMENTO",
            "DO GABINETE DE CONSELHEIRO",
            "CONTROLADORIAS DE CONTROLE EXTERNO",
            "SERVIÇOS AUXILIARES",
            "Download Anexo"
        ]

        acordaos = []

        for i, match in enumerate(acordao_matches):
            # Get the start position of the current acórdão
            start_pos = match.start()

            # Find the end position (either next acórdão or next section delimiter)
            if i < len(acordao_matches) - 1:
                end_pos = acordao_matches[i + 1].start()
            else:
                end_pos = len(text)
                for delimiter in section_delimiters:
                    delimiter_pos = text.find(delimiter, start_pos)
                    if delimiter_pos != -1 and delimiter_pos < end_pos:
                        end_pos = delimiter_pos

            # Extrai o acórdão
            acordao_text = text[start_pos:end_pos].strip()

            if acordao_text:
                acordaos.append(acordao_text)

        return acordaos
