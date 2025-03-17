# diario_oficial/documents/resolucao.py
import re
from typing import Dict, Any, List, Optional
import logging
from .base import Document

logger = logging.getLogger(__name__)

class Resolucao(Document):
    """
    Class representing a Resolucao document from DiarioOficial.
    
    A Resolucao is a resolution document issued by the court with specific 
    structure and metadata.
    
    Attributes:
        raw_text (str): The raw text of the resolucao
        data (Dict[str, Any]): Structured data extracted from the resolucao
    """
    
    # Common header/footer patterns to remove from extracted fields
    HEADER_FOOTER_PATTERNS = [
        r'Sexta-feira,\s+\d+\s+de\s+\w+\s+de\s+\d{4}',
        r'DOE\s+TCMPA\s+Nº\s+\d+\.\d+',
        r'https://www\.tcmpa\.tc\.br/',
        r'Consulta via leitora de QR Code',
        r'\d+\s+DOE\s+TCMPA\s+Nº\s+\d+\.\d+',
        r'Diário Oficial Eletrônico do TCMPA',
    ]
    
    @property
    def document_type(self) -> str:
        """
        Returns the document type.
        
        Returns:
            str: "resolucao"
        """
        return "resolucao"
    
    def _extract_data(self) -> None:
        """
        Extract structured data from resolucao raw text.
        
        Populates self.data with fields such as:
        - numero
        - processo
        - municipio
        - orgao
        - assunto
        - exercicio
        - recorrente
        - procurador
        - relator
        - ementa
        - resolucao_texto
        - data
        """
        # Initialize data dictionary with document type
        self.data = {"tipo": self.document_type}
        
        # Extract RESOLUÇÃO number
        resolucao_match = re.search(r'RESOLUÇÃO Nº (\d+\.\d+)', self.raw_text)
        if resolucao_match:
            self.data["numero"] = resolucao_match.group(1)
        else:
            logger.warning("No resolucao number found in text")
            return  # Skip if no RESOLUÇÃO number found
        
        # Extract Processo number
        self.data["processo"] = self._extract_field(
            r'Processo n[ºo°][:.]?\s*([\d\.\/-]+)'
        )
        
        # Extract Município
        municipio = self._extract_field(
            r'Município[:.]?\s*([^–\n]+?)(?:\s*–\s*PA|\s+Órgão|\n)'
        )
        if not municipio:
            municipio = self._extract_field(
                r'Município[:.]?\s*(.*?)(?:\s*-\s*PA|\s+Órgão|\n)'
            )
        self.data["municipio"] = self._clean_field(municipio) if municipio else None
        
        # Extract Órgão
        orgao = self._extract_field(
            r'Órgão[:.]?\s*(.*?)(?=\nAssunto|\s+Assunto)'
        )
        self.data["orgao"] = self._clean_field(orgao) if orgao else None
        
        # Extract Assunto
        self.data["assunto"] = self._extract_field(r'Assunto[:.]?\s*(.*?)(?=\n)')
        
        # Extract Exercício
        self.data["exercicio"] = self._extract_field(r'Exercício[:.]?\s*(\d+)')
        
        # Extract Recorrente
        recorrente = self._extract_field(
            r'Recorrente[:.]?\s*(.*?)(?:\s*[–-]\s*CPF[:.]?|$|\n)', 
            flags=re.DOTALL
        )
        self.data["recorrente"] = self._clean_field(recorrente) if recorrente else None
        
        # Extract Procurador
        self.data["procurador"] = self._extract_field(
            r'Procurador[a]?(?: do MPCM-PA)?[:.]?\s*(.*?)(?=\n)', 
            flags=re.DOTALL
        )
        
        # Extract Relator
        self.data["relator"] = self._extract_field(r'Relator[a]?[:.]?\s*(.*?)(?=\n)')
        
        # Extract EMENTA
        ementa = self._extract_field(
            r'EMENTA[:.]?\s*(.*?)(?=RESOLVEM|RESOLVE|DECISÃO:|Os Membros)', 
            flags=re.DOTALL
        )
        self.data["ementa"] = self._clean_field(' '.join(ementa.split())) if ementa else None
        
        # Extract RESOLUÇÃO text
        resolucao_texto = self._extract_field(
            r'(?:RESOLVEM|RESOLVE)[\s:]+(.*?)(?=Sessão Eletrônica|RESOLUÇÃO Nº|$)', 
            flags=re.DOTALL
        )
        self.data["resolucao_texto"] = self._clean_field(' '.join(resolucao_texto.split())) if resolucao_texto else None
        
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
        for key in ["recorrente"]:
            if key in self.data and self.data[key]:
                self.data[key] = self._redact_personal_data(self.data[key])
        
        logger.debug(f"Extracted Resolucao {self.data.get('numero', 'unknown')}")
    
    def _clean_field(self, text: str) -> str:
        """
        Clean a field by removing header/footer patterns.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        # Remove header/footer patterns
        for pattern in self.HEADER_FOOTER_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
        # Remove multiple whitespaces and normalize
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
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
    
    def get_resolution_text(self) -> str:
        """
        Get the resolution text from the resolucao.
        
        Returns:
            The resolution text or empty string if not found
        """
        return self.data.get("resolucao_texto", "")
    
    def is_unanimity(self) -> bool:
        """
        Check if the resolution was approved by unanimity.
        
        Returns:
            True if approved by unanimity
        """
        voting_text = self._extract_field(
            r'Votação:(.*?)(?=(?:Sala das|Plenário|$))',
            flags=re.DOTALL
        ) or ""
        return "unanimidade" in voting_text.lower()
    
    @staticmethod
    def split_sections(text: str) -> List[str]:
        """
        Split text into resolucao sections.
        
        Args:
            text: Full text containing multiple resolucoes
            
        Returns:
            List of individual resolucao texts
        """
        # Find all sections starting with RESOLUÇÃO
        resolucao_pattern = r'RESOLUÇÃO Nº \d+\.\d+'
        
        # Split text into sections
        sections = re.split(f"(?={resolucao_pattern})", text)
        
        # Filter out sections that don't actually start with RESOLUÇÃO
        resolucao_sections = [s for s in sections if re.match(resolucao_pattern, s.strip())]
        
        return resolucao_sections
    
    @classmethod
    def from_sections(cls, text: str) -> List['Resolucao']:
        """
        Create Resolucao instances from text containing multiple resolucoes.
        
        Args:
            text: Full text containing multiple resolucoes
            
        Returns:
            List of Resolucao instances
        """
        sections = cls.split_sections(text)
        resolucoes = []
        
        for section in sections:
            try:
                resolucao = cls(section)
                resolucoes.append(resolucao)
            except Exception as e:
                logger.error(f"Error creating Resolucao from section: {e}")
                
        return resolucoes