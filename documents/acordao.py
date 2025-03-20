import re
import logging
from typing import Dict, Any, List, Optional
from documents.document import DocumentoBase, DocumentoDiarioOficial
from documents.diario import DiarioOficial, DataDiario

logger = logging.getLogger(__name__)

class Acordao(DocumentoBase, DiarioOficial):
    """
    Classe representando um Acórdão extraído do Diário Oficial.

    Um Acórdão é um documento de decisão emitido pelo tribunal com estrutura
    específica e metadados que precisam ser extraídos para análise posterior.
    """
    def __init__(
        self,
        publicacao: DataDiario | str = DataDiario(),
        texto_original: str = "",
    ) -> None:
        """
        Inicializa a classe Acordao.

        Args:
            publicacao (DataDiario | str): Data de publicação do acórdão.
            texto_original (str): Texto bruto do acórdão.
        """
        super().__init__(publicacao=publicacao, texto_original=texto_original)
        self.document_type = self._document_type
        super(DiarioOficial, self).__init__(
            dia=self.publicacao.dia,
            mes=self.publicacao.mes,
            ano=self.publicacao.ano,
        )

    def _extract_data(self) -> List[DocumentoDiarioOficial]:
        """
        Processa o raw_text, dividindo-o em seções, extraindo os dados de cada
        seção e retornando uma lista de objetos DocumentoDiarioOficial.

        Returns:
            List[DocumentoDiarioOficial]: Documentos extraídos.
        """
        extracted_documents: List[DocumentoDiarioOficial] = []
        sections = self.get_sections(text=self.raw_text)
        if not sections:
            logger.warning("Nenhuma seção encontrada no texto bruto.")
            return extracted_documents

        for section in sections:
            # Limpa o texto da seção
            #clean_raw = self.clean_text(section)
            clean_raw = section
            data_dict: Dict[str, Any] = {"categoria": self.document_type}

            # Extrai o número do acórdão
            acordao_match = re.search(r'ACÓRDÃO Nº (\d+\.\d+)', clean_raw)
            if acordao_match:
                data_dict["numero"] = acordao_match.group(1)
            else:
                logger.warning("No acórdão number found in section; skipping section.")
                continue

            # Extrai pares chave:valor e limpa cada valor
            keys = self._get_keys(clean_raw)
            extracted_data = self._extract_key_content(clean_raw, keys=keys)
            for key, value in extracted_data.items():
                data_dict[key.lower()] = value # self.clean_text(value)

            # Extrai a data da sessão utilizando um padrão
            date_pattern = (
                r'(\d+(?:\s+a\s+\d+)?\s+de\s+'
                r'(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)'
                r'\s+de\s+\d{4})'
            )
            date_match = re.search(f'Sessão Eletrônica.*?{date_pattern}', clean_raw, re.DOTALL)
            if date_match:
                data_dict["julgado_em"] = date_match.group(1).strip()
            else:
                alt_date_match = re.search(date_pattern, clean_raw)
                if alt_date_match:
                    data_dict["julgado_em"] = alt_date_match.group(1).strip()

            # # Redige dados pessoais conforme LGPD
            # for field in ["ordenador", "responsavel", "representante_legal", "interessado"]:
            #     if field in data_dict and data_dict[field]:
            #         data_dict[field] = self._redact_personal_data(data_dict[field])

            # Armazena o texto original da seção e a data do diário
            data_dict["texto_original"] = clean_raw
            # Certifique-se de que "data_diario" esteja presente; use self.data_diario se existir, ou uma string vazia
            data_dict["publicado_em"] = getattr(self, "publicado_em", "")

            logger.debug(f"Extracted Acordao {data_dict.get('numero', 'unknown')}")
            try:
                documento = DocumentoDiarioOficial(**data_dict)
                extracted_documents.append(documento)
                logger.debug(f"Acórdão extraído com sucesso: {data_dict.get('numero', 'unknown')}")
            except Exception as e:
                logger.error(f"Erro ao criar DocumentoDiarioOficial para seção: {e}")

        return extracted_documents

    @staticmethod
    def get_sections(text: str):
        """
        Extract and structure acórdãos from a DOE TCMPA document.
        
        Args:
            text (str): The full text of the DOE TCMPA document.
            
        Returns:
            list: A list of dictionaries, each containing the structured data of an acórdão.
        """
        
      
        # Find all acórdão start positions
        acordao_pattern = r'ACÓRDÃO\s+Nº\s+(\d+\.\d+)'
        acordao_matches = list(re.finditer(acordao_pattern, text))
        
        # Define section delimiters for finding the end of an acórdão
        section_delimiters = [
            "DO GABINETE DA PRESIDÊNCIA",
            "PAUTA DE JULGAMENTO",
            "DO GABINETE DE CONSELHEIRO",
            "CONTROLADORIAS DE CONTROLE EXTERNO",
            "SERVIÇOS AUXILIARES"
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
            
            # Extract the acórdão text
            acordao_text = text[start_pos:end_pos].strip()

            
            if acordao_text:
                acordaos.append(acordao_text)
        
        return acordaos
