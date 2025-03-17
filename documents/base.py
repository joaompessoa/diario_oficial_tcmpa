# diario_oficial/documents/base.py
from typing import Dict, Any, Optional, List
import re
from abc import ABC, abstractmethod
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DocumentoDiarioOficial(BaseModel):
    # Optionally, declare some fields
    categoria: Optional[str] = Field(examples=['acordao','resolucao','notificao'],description="Categoria do documento")
    data: Optional[str] = Field(examples=['3 de Março de 2025'], description="Data da publicação representado no diário oficial")
    numero: Optional[str] = Field(description="Número do documento")
    data_diario: Optional[str] = Field(examples='03/03/2025',description="Data da publicação do diário oficial em DD/MM/YYYY")

    # Allow any extra fields
    class Config:
        extra = 'allow'

class Document(BaseModel):
    """
    Base class for all document types that can be extracted from DiarioOficial.
    
    This abstract class defines the common interface and functionality for all 
    document types such as Acordao, Resolucao, Citacao, etc.
    
    Attributes:
        raw_text (str): The raw text of the document
        data (Dict[str, Any]): Structured data extracted from the document
    """
    
    def __init__(self, raw_text: str, date_str: str):
        """
        Initialize a document with raw text.
        
        Args:
            raw_text (str): The raw text of the document
        """
        self.raw_text = raw_text
        self.date_str = date_str
        self.data: Dict[DocumentoDiarioOficial] = {}
        self._extract_data()
        
    @property
    @abstractmethod
    def document_type(self) -> str:
        """
        Returns the document type.
        
        Must be implemented by subclasses.
        
        Returns:
            str: Document type identifier (e.g., "acordao", "resolucao")
        """
        pass
    
    @abstractmethod
    def _extract_data(self) -> None:
        """
        Extract structured data from raw text.
        
        Must be implemented by subclasses to populate self.data.
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert document to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary containing document data and metadata
        """
        return {
            "tipo": self.document_type,
            **self.data
        }
    
    def _extract_field(self, pattern: str, default: Optional[str] = None) -> Optional[str]:
        """
        Extract a field from raw_text using regex pattern.
        
        Args:
            pattern (str): Regular expression pattern with one capture group
            default (Optional[str]): Default value if pattern not found
            
        Returns:
            Optional[str]: Extracted value or default
        """
        match = re.search(pattern, self.raw_text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return default
    
    def _redact_personal_data(self, text: str) -> str:
        """
        Redact personal data like CPF according to LGPD.
        
        Args:
            text (str): Text that may contain personal data
            
        Returns:
            str: Text with personal data redacted
        """
        # Redact CPF
        text = re.sub(r'\d{3}\.\d{3}\.\d{3}-?\d{2}', '[REDIGIDO]', text)
        return text
    
    def clean_text(self, text: str) -> str:
        """
        Realiza limpeza e normalização do texto extraído.

        Args:
            text: Texto bruto para limpeza

        Returns:
            Texto processado e normalizado
        """
        if not text:
            return ""

        logger.info("Iniciando limpeza do texto")

        # Padrões para remoção
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


        # Aplicação dos padrões
        for padrao in padroes:
            # Remove caso encontre algum termo dentro dos padrões listados
            text = re.sub(padrao, "", text, flags=re.DOTALL)

        # Correções de hifenização e espaçamento
        text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n", "", text)

        return text.strip()
    
    def _get_keys(self, text: Optional[str] = None) -> List[str]:
        """
        Extract keys from the text. If no text is provided, use self.raw_text.
        Ignores CPF as a key.

        Args:
            text (Optional[str]): The text to extract keys from. Defaults to self.raw_text.

        Returns:
            List[str]: List of extracted keys.
        """
        if text is None:
            text = self.raw_text
        
        pattern = r'((?!PA:)[\(A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+[ \(A-Za-záéíóúàâêôçüãõ\)]*)(?=:)'
 
        matches = re.findall(pattern, text)
        
        # Filter out CPF and keep only unique keys
        filtered_keys = []
        for match in matches:
            match =  match.strip()
            if match.lower() not in ('cpf','endereço') and match not in filtered_keys:
                filtered_keys.append(match)
        
        return filtered_keys
        
    def _extract_key_content(self, text: Optional[str] = None, keys: Optional[List[str]] = None) -> dict:
        """
        Extract content based on keys from the text. If no text or keys are provided, 
        use self.raw_text and keys extracted from it.

        Args:
            text (Optional[str]): The text to extract content from. Defaults to self.raw_text.
            keys (Optional[List[str]]): The keys to use for extraction. Defaults to keys extracted from self.raw_text.

        Returns:
            dict: Dictionary containing extracted key-value pairs.
        """
        if text is None:
            text = self.raw_text
        if keys is None:
            keys = self._get_keys(text)
        values = {}
        # Loop over the keys provided.
        for i, key in enumerate(keys):
            # Use re.escape to safely insert the key into the regex pattern.
            if i < len(keys) - 1:
                # For non-last keys, capture content up until the next key followed by a colon.
                next_key = keys[i+1]
                pattern = rf'{re.escape(key)}:\s*(.*?)\s*(?={re.escape(next_key)}:)'
            else:
                # For the last key, capture everything until the end of the string.
                pattern = rf'{re.escape(key)}:\s*(.*)$'
            
            # Use DOTALL to allow matching across newlines.
            match = re.search(pattern, text, re.DOTALL)
            if match:
                # Clean-up the value by stripping leading/trailing whitespace.
                value = match.group(1).strip()
                values[re.sub(r'\s+', '_',key.lower())] = value
            else:
                values[key.lower()] = ""
                
        return values
        
    
    def __str__(self) -> str:
        """String representation of the document."""
        return f"{self.document_type.capitalize()} - {self.data.get('numero', 'Sem número')}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the document."""
        return f"{self.__class__.__name__}({self.data})"