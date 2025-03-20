from datetime import datetime
from typing import Union, Optional, List, Dict, Any, Type, TypeVar
from h11 import Data
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import os
import sys
import re
from loguru import logger
import pymupdf
from pathlib import Path
from pydantic import BaseModel, model_validator, field_validator, Field, ValidationError
from documents.diario_exceptions import DiarioNaoExiste


logger.add(sink=sys.stdout,level="DEBUG", format="{time} {level} {message}",)


class DataDiario(BaseModel):
    """
    Modelo para validação e armazenamento da data do diário oficial.

    Attributes:
        dia (int): Dia do mês
        mes (int): Mês do ano
        ano (int): Ano
        hoje (datetime): Data de hoje para validação
    """

    dia: int = Field(default_factory=lambda: datetime.today().day)
    mes: int = Field(default_factory=lambda: datetime.today().month)
    ano: int = Field(default_factory=lambda: datetime.today().year)

    @field_validator("dia", "mes", "ano", mode="before")
    @classmethod
    def validar_numeros(cls, v):
        """Converte strings para inteiros, se necessário."""
        if isinstance(v, str):
            if not v.isdigit():
                raise ValueError(f"O valor '{v}' não é um número válido.")
            return int(v)
        return v

    @model_validator(mode="after")
    def validar_data_futura(self):
        """Valida se a data não é maior que hoje."""
        try:
            data = datetime(self.ano, self.mes, self.dia)
        except ValueError:
            raise DiarioNaoExiste(f"Data inválida: {self.dia}/{self.mes}/{self.ano}")

        if data > datetime.today():
            raise DiarioNaoExiste(
                f"A data {self.dia}/{self.mes}/{self.ano} não pode ser maior que hoje ({datetime.today().strftime(format="%S/%M/%Y")})."
            )

        return self


class DiarioOficial(DataDiario):
    """
    Classe para buscar, baixar e processar PDFs do Diário Oficial do TCM-PA.

    Esta classe gerencia a busca e o processamento de documentos oficiais do
    TCM-PA Ela fornece uma pipelina completa para buscar, verificar e baixar
    o diário oficial com base de uma data específica ou a data de hoje, como default.

    Attributes:
        dia (DataDiario.dia): Dia do mês
        mes (DataDiario.mes): Mês do ano
        ano (DataDiario.ano): Ano
        download_dir (Path): Diretório onde os PDFs são salvos
        limpar_texto (bool): Se o texto extraído deve ser limpo
    Examples:
        >>> # Busca  o Diário Oficial para uma data específica
        >>> diario = DiarioOficial(dia=10, mes=5, ano=2024, download_dir="./downloads")
        >>> if diario.is_valid:
        ...     diario.download_pdf()
        ...     print(f"PDF baixado em: {diario.save_path}")

        >>> # Busca padrão do diário mais recente
        >>> diario_hoje = DiarioOficial()
        >>> if diario_hoje.is_valid:
        ...    print("Diário Oficial está disponível para hoje")
        ... else:
        ...    print("Diário Oficial não está disponível para hoje")
    """

    # URL base para pesquisa

    publicacao: str = ""
    ioepa_endpoint: str = ""
    # Campos principais do modelo
    texto_original: str = ""
    diario_valido: bool = False
    download_dir: Path = Field(default_factory=lambda: Path.cwd() / "diarios")
    pdf_file: Optional[str] = ""
    local_path: Path = ""
    internet_path: Path = ""

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True

    def __init__(
        self,
        dia: Optional[int | str] = datetime.today().day,
        mes: Optional[int | str] = datetime.today().month,
        ano: Optional[int | str] = datetime.today().year,
        download_dir: Optional[str | Path] = "",
        limpar_texto: bool = True,
        BASE_URL: str = "https://tcm.ioepa.com.br/busca/default.aspx?dts=",
        **kwargs,
    ) -> None:
        """
        Inicializa o objeto DiarioOficial com a data especificada e verifica disponibilidade.

        Args:
            dia: Dia do mês (padrão: dia atual)
            mes: Mês (padrão: mês atual)
            ano: Ano (padrão: ano atual)
            download_dir: Diretório para salvar arquivos (padrão: diretório atual)
            pdf_path: Caminho para um PDF já existente
            limpar_texto: Se o texto deve ser limpo durante a extração
            texto_bruto: Texto já extraído (opcional)
        """

        data_diario_args = {
            "dia": dia ,
            "mes": mes ,
            "ano": ano ,
        }
        kwargs["data_diario"] = DataDiario(**data_diario_args)

        super().__init__(**kwargs)

        # Confirma se o diário existe para a data
        self.limpar_texto = limpar_texto
        self.publicacao = f"{dia}/{mes}/{ano}"
        self.ioepa_endpoint = f"{BASE_URL}{self.publicacao}"
        self.diario_valido = self._diario_existe(self.ioepa_endpoint)
        

        # Se o diário não existir, não é necessário continuar
        if not self.diario_valido:
            raise DiarioNaoExiste(
                f"Diário não encontrado para {self.publicacao}"
            )
        else:
            logger.info(f"Diário encontrado para {self.publicacao}")

        # 1. Verificar e configurar diretório de download
        if download_dir:
            try:
                self.download_dir = Path(download_dir)
                # Verifica se o diretório é válido
                if not self._validar_diretorio(self.download_dir):
                    logger.warning(f"Diretório inválido: {download_dir}. Usando diretório padrão.")
                    self.download_dir = self._obter_diretorio_padrao()
            except Exception as e:
                logger.warning(f"Erro ao configurar diretório de download: {e}. Usando diretório padrão.")
                self.download_dir = self._obter_diretorio_padrao()
        else:
            self.download_dir = self._obter_diretorio_padrao()
            self.local_path = os.path.join(self.download_dir, Path(self.pdf_file))
            if self._pdf_disponivel(self.local_path):
                logger.info(f"PDF válido encontrado: {self.pdf_file}")
            else:
                self.download_pdf(self.internet_path)

        logger.info(f"Diretório de download configurado: {self.download_dir}")

        if not self.pdf_file:
            try:
                self.local_path = self.download_dir / Path(self.pdf_file)
                if self._pdf_disponivel(self.local_path):
                    logger.info(f"PDF válido encontrado: {self.pdf_file}")
                    # Extrair texto se necessário
                    if not self.texto_original:
                        self.texto_original = self.extract_text(pdf_path=self.full_path, limpar_texto=self.limpar_texto)
                else:
                    logger.warning(f"PDF não encontrado ou inválido: {self.pdf_file}")
                    # Continua o fluxo para tentar baixar o PDF
            except Exception as e:
                logger.error(f"Erro ao verificar PDF especificado: {e}")

        logger.info(
            f"Inicializando DiarioOficial para a data: {self.data_diario.dia:02d}/{self.data_diario.mes:02d}/{self.data_diario.ano}"
        )

    def _obter_diretorio_padrao(self) -> Path:
        """
        Retorna o diretório padrão para download dos diários.
        
        Returns:
            Path: Caminho do diretório padrão
        """
        return (
            Path.cwd()
            / "diarios"
            / f"{self.data_diario.ano}"
            / f"{self.data_diario.mes:02d}"
        )

    def _validar_diretorio(self, path: Path) -> bool:
        """
        Valida se um diretório é utilizável para download.
        
        Args:
            path: Caminho do diretório a ser validado
            
        Returns:
            bool: True se o diretório for válido
        """
        try:
            # Verifica se o diretório existe ou pode ser criado
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
            # Testa permissão de escrita criando um arquivo temporário
            test_file = path / ".test_write_permission"
            test_file.touch()
            test_file.unlink()
            return True
        except (PermissionError, OSError) as e:
            logger.warning(f"Erro ao validar diretório {path}: {e}")
            return False

    def _diario_existe(self, ioepa_endpoint: str) -> bool:
        """
        Busca a página do Diário Oficial e extrai a URL do PDF.

        Returns:
            True se encontrou o PDF com sucesso, False caso contrário
        """
        if not ioepa_endpoint:
            ioepa_endpoint = self.ioepa_endpoint
        try:
            logger.info(f"Buscando URL: {ioepa_endpoint}")
            response = requests.get(ioepa_endpoint, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Falha na requisição: {e}")
            return False

        soup = BeautifulSoup(response.text, "html.parser")
        mid_div = soup.find("div", id="mid")

        if not mid_div:
            logger.warning("Div 'mid' não encontrada no HTML")
            return False

        link = mid_div.find("a")
        if not link or "href" not in link.attrs:
            logger.warning("Nenhum link válido encontrado na div 'mid'")
            return False

        self.internet_path = urljoin(ioepa_endpoint, link["href"])

        # Verificação do tipo de arquivo
        if not self.internet_path.lower().endswith(".pdf"):
            pdf_link = mid_div.find(
                "a", href=lambda href: href and href.lower().endswith(".pdf")
            )
            if pdf_link and "href" in pdf_link.attrs:
                self.internet_path = urljoin(ioepa_endpoint, pdf_link["href"])
            else:
                logger.warning(f"URL encontrada não parece ser PDF: {self.internet_path}")

        logger.info(f"URL do PDF encontrada: {self.internet_path}")
        pdf_file = os.path.basename(self.internet_path)
        self.pdf_file = pdf_file
        return True

    def refresh(self) -> bool:
        """
        Atualiza as informações buscando novamente a página.

        Returns:
            True se encontrou o PDF com sucesso
        """
        self.diario_valido = self._diario_existe(self.ioepa_endpoint)
        return self.diario_valido
    def _diretorio_existe(self, download_dir: str | Path) -> bool:
        """
        Verifica se o diretório de download existe.

        Args:
            download_dir: Caminho do diretório a ser verificado
        Returns:
            True se o diretório existir
        """
        if not os.path.exists(download_dir):
            logger.warning(f"Diretório não encontrado: {download_dir}")
            return False
        else:
            logger.info(f"Diretório encontrado: {download_dir}")
            return True
    def _pdf_disponivel(self, pdf_path: str | Path) -> bool:
        """
        Verifica se o PDF está disponível.

        Returns:
            True se o PDF estiver disponível
        """
        if not os.path.isfile(pdf_path):
            logger.warning(f"PDF não encontrado: {pdf_path}")
            return False
        try:
            with open(pdf_path, "rb") as f:
                content = f.read()
                if not content:
                    logger.warning(f"PDF vazio: {pdf_path}")
                    return False
                else:
                    logger.info(f"PDF encontrado e não vazio: {pdf_path}")
                    return True
        except FileNotFoundError:
            logger.warning(f"Arquivo não encontrado: {pdf_path}")
            return False
        except PermissionError:
            logger.error(f"Permissão negada para acessar o arquivo: {pdf_path}")
            return False
        except IOError as e:
            logger.error(f"Erro ao ler o PDF: {e}")
            return False

    def _obter_diretorio_padrao(self) -> Path:
        """
        Retorna o diretório padrão para download dos diários.
        
        Returns:
            Path: Caminho do diretório padrão
        """
        return (
            Path.cwd()
            / "diarios"
            / f"{self.data_diario.ano}"
            / f"{self.data_diario.mes:02d}"
        )

    def download_pdf(self, internet_path: str) -> bool:
        """
        Baixa o PDF da URL armazenada.

        Args:
            save_path: Caminho personalizado para salvar o arquivo

        Returns:
            True se o download foi bem sucedido
        """
        if not self.diario_valido or not internet_path:
            logger.error("URL do PDF não disponível. Diário pode não existir.")
            raise DiarioNaoExiste(
                f"Diário não encontrado para {self.publicacao}"
            )

        try:
            logger.info(f"Iniciando download do PDF: {self.pdf_file}")
            response = requests.get(internet_path, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Falha no download do PDF: {e}")
            return False

        try:

            with open(self.local_path, "wb") as f:
                f.write(response.content)

            logger.info(f"PDF salvo com sucesso em: {self.local_path}")
            return True
        except IOError as e:
            logger.error(f"Falha ao salvar PDF: {e}")
            return False

    def clean_text(self, text: str) -> str:
        # Check if cleaning is disabled
        if hasattr(self, "limpar_texto") and not self.limpar_texto:
            return text
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

    def extract_text(self, pdf_path: Optional[Union[str, Path]] = None, limpar_texto: bool = True) -> str:
        """
        Extrai o texto de um arquivo PDF.
        
        Args:
            pdf_path: Caminho do arquivo PDF (opcional)
            limpar_texto: Se deve limpar o texto extraído
            
        Returns:
            str: Texto extraído do PDF
        """
        # Se já tivermos o texto, retorna-o diretamente
        if self.texto_original:
            logger.info("Texto já extraído anteriormente, reutilizando raw_text.")
            return self.texto_original

        pdf_file_path = self.local_path

        try:
            logger.info(f"Iniciando extração de texto de: {pdf_file_path}")
            with pymupdf.open(pdf_file_path) as pdf:
                texto = []
                total_paginas = len(pdf)

                for i, pagina in enumerate(pdf):
                    if i == 0:  # Pula a primeira página
                        continue
                    logger.info(f"Processando página {i+1}/{total_paginas}")
                    texto_pagina = pagina.get_text()
                    texto_pagina = self.clean_text(texto_pagina) if limpar_texto else texto_pagina
                    if texto_pagina:
                        texto.append(texto_pagina)

                texto_bruto = "\n".join(texto)

            if not texto_bruto:
                logger.warning("Nenhum texto extraído do PDF")

            self.texto_original = texto_bruto  # Armazena o texto para reutilização
            return texto_bruto
        except Exception as e:
            logger.error(f"Erro na extração de texto: {e}")
            return ""

    @classmethod
    def para_data(
        cls, data_str: str, formato: str = "%d/%m/%Y", **kwargs
    ) -> "DiarioOficial":
        """
        Cria uma instância de DiarioOficial a partir de uma string de data.

        Args:
            data_str (str): String da data no formato especificado.
            formato (str, opcional): Formato da data (padrão: "%d/%m/%Y").
            **kwargs: Argumentos adicionais para o DiarioOficial

        Returns:
            DiarioOficial: Instância de DiarioOficial para a data especificada.

        Examples:
            >>> diario = DiarioOficial.para_data("15/05/2024")
            >>> print(diario)
        """
        try:
            data = datetime.strptime(data_str, formato)
            return cls(dia=data.day, mes=data.month, ano=data.year, **kwargs)
        except ValueError as e:
            raise ValueError(f"Erro na validação da data: {e}")

