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
        examples=['acordao', 'resolucao', 'notificacao']
    )
    sessao: Optional[str] = Field(
        default="",
        description="Data da publicação representada no diário oficial",
        examples=['3 de Março de 2025']
    )
    numero: Optional[str] = Field(
        default="",
        description="Número do documento"
    )
    publicacao: Optional[DataDiario] = Field(
        default=DataDiario(),
        description="Data da publicação do diário oficial em DD/MM/YYYY",
        examples=['03/03/2025']
    )
    texto_original: Optional[str] = Field(
        default="",
        description="Texto limpo (processado) do documento"
    )
    diario: Optional[DiarioOficial] = Field(
        default=DiarioOficial(),
        description="Diário oficial de onde o documento foi extraído"
    )
   
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

class ListaDocumentos(DocumentoDiarioOficial):
    documentos: List[DocumentoDiarioOficial] = Field(
        default=[],
        description="Lista de documentos extraídos do diário oficial"
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
        return re.sub(r'\d{3}\.\d{3}\.\d{3}-?\d{2}', '[REDIGIDO]', text)

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

    def _get_keys(self, text: Optional[str] = None) -> List[str]:
        """
        Extrai possíveis chaves (nomes de campos) do texto.
        """
        if text is None:
            text = self.texto_original
        #pattern = r'((?!PA:)[\(A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+[ \(A-Za-záéíóúàâêôçüãõ\)]*)(?=:)'
        pattern = r'((?!PA:)[\(A-ZÁÉÍÓÚÀÂÊÔÇÜÃÕ]+[ \(A-Za-záéíóúàâêôçüãõ\)]*(?=:))(?=.*[A-Za-záéíóúàâêôçüãõ].*[A-Za-záéíóúàâêôçüãõ])'
        logger.info("Extraindo chaves do texto")
        matches = re.findall(pattern, text)
        logger.debug(f"Chaves encontradas: {matches}")
        filtered_keys = []
        for match in matches:
            match = match.strip()
            if match.lower() not in ('cpf', 'endereço') and match not in filtered_keys:
                filtered_keys.append(match)
        return filtered_keys

    def _extract_key_content(self, text: Optional[str] = None, keys: Optional[List[str]] = None) -> Dict[str, str]:
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
                pattern = rf'{re.escape(key)}:\s*(.*?)\s*(?={re.escape(next_key)}:)'
            else:
                pattern = rf'{re.escape(key)}:\s*(.*)$'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                logger.info(f"Match found for {key}")
                value = match.group(1).strip()
                values[re.sub(r'\s+', '_', key.lower())] = self.clean_text(value)
            else:
                logger.warning(f"No match found for {key}")
                values[key.lower()] = ""
        return values

    def _extract_field(self, pattern: str, flags: int = 0) -> Optional[str]:
        """
        Extrai um úni