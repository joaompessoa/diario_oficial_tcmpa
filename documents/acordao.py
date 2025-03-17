# diario_oficial/documents/acordao.py
import re
from typing import Dict, Any, List, Optional
import logging
from .base import Document

logger = logging.getLogger(__name__)

class Acordao(Document):
    """
    Class representing an Acordao document from DiarioOficial.
    
    An Acordao is a decision document issued by the court with specific 
    structure and metadata.
    
    Attributes:
        raw_text (str): The raw text of the acordao
        data (Dict[str, Any]): Structured data extracted from the acordao
    """
    
    # Common header/footer patterns to remove from extracted fields
    HEADER_FOOTER_PATTERNS = [
        r'(Segunda|Terça|Quarta|Quinta|Sexta)-feira,\s+\d+\s+de\s+\w+\s+de\s+\d{4}',
        r'DOE\s+TCMPA\s+Nº\s+\d+\.\d+',
        r'https://www\.tcmpa\.tc\.br/',
        r'Consulta via leitora de QR Code',
        r'\d+\s+DOE\s+TCMPA\s+Nº\s+\d+\.\d+',
        r'Diário Oficial Eletrônico do TCMPA',
        r'Este é GRATUITO e sua autenticidade poderá ser confirmada na página do Tribunal de Contas dos Municípios do Estado do Pará na Internet, no',
    ]
    
    @property
    def document_type(self) -> str:
        """
        Returns the document type.
        
        Returns:
            str: "acordao"
        """
        return "acordao"
    
    def _extract_data(self) -> None:
        """
        Extract structured data from acordao raw text.
        
        Populates self.data with fields such as:
        - numero
        - processo
        - municipio
        - unidade_gestora
        - exercicio
        - ordenador
        - responsavel
        - representante_legal
        - interessado
        - assunto
        - procurador
        - relator
        - ementa
        - decisao
        - data
        """
        # Initialize data dictionary with document type
        self.data = {"tipo": self.document_type}
        
        # Extract ACÓRDÃO number
        acordao_match = re.search(r'ACÓRDÃO Nº (\d+\.\d+)', self.raw_text)
        if acordao_match:
            self.data["numero"] = acordao_match.group(1)
        else:
            logger.warning("No acordao number found in text")
            return  # Skip if no ACÓRDÃO number found
        
        keys = self._get_keys()
        extracted_data = self._extract_key_content(keys=keys)
        for key, value in extracted_data.items():
            self.data[key.lower()] = self.clean_text(value)
        
        # Extract date
        date_pattern = r'(\d+(?:\s+a\s+\d+)?\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4})'
        date_match = re.search(f'Sessão Eletrônica.*?{date_pattern}', self.raw_text, re.DOTALL)
        
        if date_match:
            self.data["data"] = date_match.group(1).strip()
        else:
            # Try an alternative pattern
            alt_date_match = re.search(date_pattern, self.raw_text)
            if alt_date_match:
                self.data["data"] = alt_date_match.group(1).strip()
        
        # Redact personal data
        for key in ["ordenador", "responsavel", "representante_legal", "interessado"]:
            if key in self.data and self.data[key]:
                self.data[key] = self._redact_personal_data(self.data[key])
        self.data['texto_original'] = self.raw_text
        self.data['data_diario'] = self.date_str
        
        logger.debug(f"Extracted Acordao {self.data.get('numero', 'unknown')}")
    
    def _extract_field(self, pattern: str, flags: int = 0) -> Optional[str]:
        """
        Extract a field from raw_text using regex pattern.
        
        Args:
            pattern: Regular expression pattern with one capture group
            flags: Regex flags
            
        Returns:
            Extracted value or None
        """
        match = re.search(pattern, self.raw_text, flags)
        if match:
            return match.group(1).strip()
        return None
    
    def get_decision(self) -> str:
        """
        Get the decision text from the acordao.
        
        Returns:
            The decision text or empty string if not found
        """
        return self.data.get("decisao", "")
    
    def get_votes(self) -> List[str]:
        """
        Extract the voting information.
        
        Returns:
            List of voters and their votes
        """
        votes_text = self._extract_field(
            r'Votação:(.*?)(?=(?:Sala das|Plenário|$))',
            flags=re.DOTALL
        )
        
        if not votes_text:
            return []
            
        return [vote.strip() for vote in votes_text.split(',') if vote.strip()]
    
    @staticmethod
    def get_sections(text: str) -> List[str]:
        """
        Split text into acordao sections.
        
        Args:
            text: Full text containing multiple acordaos
            
        Returns:
            List of individual acordao texts
        """
        # Find all sections starting with ACÓRDÃO
        acordao_pattern = r'ACÓRDÃO Nº \d+\.\d+'
        
        # Split text into sections
        sections = re.split(f"(?={acordao_pattern})", text)
        
        # Filter out sections that don't actually start with ACÓRDÃO
        acordao_sections = [s for s in sections if re.match(acordao_pattern, s.strip())]
        
        return acordao_sections
    
    
    def from_sections(self, text: str) -> List['Acordao']:
        """
        Create Acordao instances from text containing multiple acordaos.
        
        Args:
            text: Full text containing multiple acordaos
            
        Returns:
            List of Acordao instances
        """
        sections = self.get_sections(text)
        acordaos = []
        
        for section in sections:
            try:
                acordao = Acordao(raw_text=section, date_str=self.date_str)
                acordaos.append(acordao)
            except Exception as e:
                logger.error(f"Error creating Acordao from section: {e}")
                
        return acordaos