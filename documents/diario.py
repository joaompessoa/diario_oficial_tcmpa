from datetime import datetime
from turtle import down
from typing import Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import sys
import re
from util.logger_config import logger
import pymupdf
from pathlib import Path
from pydantic import BaseModel, model_validator, field_validator, Field
from exceptions.diario_exceptions import DiarioNaoExiste


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

    publicacao: str = ""
    numero_diario: str = ""
    ioepa_endpoint: str = ""
    # Campos principais do modelo
    texto_original: str = str()
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
        dia: Optional[int | str | None] = None,
        mes: Optional[int | str | None] = None,
        ano: Optional[int | str | None] = None,
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
        super().__init__()
        self.dia = dia if dia else datetime.today().day
        self.mes = mes if mes else datetime.today().month
        self.ano = ano if ano else datetime.today().year

        data_diario_args = {
            "dia": self.dia,
            "mes": self.mes,
            "ano": self.ano,
        }
        kwargs["data_diario"] = DataDiario(**data_diario_args)


        # Confirma se o diário existe para a data
        self.limpar_texto = limpar_texto
        self.publicacao = f"{self.dia}/{self.mes}/{self.ano}"
        self.ioepa_endpoint = f"{BASE_URL}{self.publicacao}"
        self.diario_valido = self._diario_existe(self.ioepa_endpoint)
        self.pdf_file = os.path.basename(self.internet_path)


        # Se o diário não existir, não é necessário continuar
        if not self.diario_valido:
            raise DiarioNaoExiste(f"Diário não encontrado para {self.publicacao}")
        else:
            logger.success(f"Diário encontrado para {self.publicacao}")

        # 1. Verificar e configurar diretório de download
        # Se o diretorio for especificado pelo usuario, checa se ele e valido, e temos as permissoes para salvar documentos nele
        if download_dir:
            try:
                self.download_dir = Path(download_dir)
                # Verifica se o diretório é válido
                if not self._validar_diretorio(self.download_dir):
                    logger.warning(
                        f"Diretório inválido: {download_dir}. Usando diretório padrão."
                    )
                    # Se for invalido usamos o diretorio padrao que e pasta_atual/diarios/ano/mes/diario.pdf
                    self.download_dir = self._obter_diretorio_padrao()
                # se o diretorio for valido, realizamos o download do pdf
                else:
                    if self.download_pdf(local_path=self.download_dir, internet_path=self.internet_path):
                        self.texto_original = self.extract_text(
                            pdf_path=self.local_path, limpar_texto=self.limpar_texto
                        )
                    
            except Exception as e:
                # Qual outro erro tentamos criar o diretorio padrao comentado acima
                logger.warning(
                    f"Erro ao configurar diretório de download: {e}. Usando diretório padrão."
                )
                self.download_dir = self._obter_diretorio_padrao()
        else:
            # Se o diretorio nao for especificado pelo usuario, seguimos direto para checar o diretorio padrao
            self.download_dir = self._obter_diretorio_padrao()
            # local_path sera o caminho para o pdf
            self.local_path = os.path.join(self.download_dir, Path(self.pdf_file))
            # checa se o pdf ja existe e ja foi baixado anteriormente
            if self._pdf_disponivel(self.local_path):
                logger.success(f"PDF válido encontrado: {self.pdf_file}")
                # se o pdf existir verificamos se temos acesso ao texto dele
                if not self.texto_original:
                    logger.info("Extraindo texto do PDF")
                    # se nao tivermos o texto, usamos extract_text para extrai-lo
                    self.texto_original = self.extract_text(
                        pdf_path=self.local_path, limpar_texto=self.limpar_texto
                    )
            else:
                # se o pdf nao estiver disponivel, assumimos que precisamos fazer o download do mesmo
                if self.download_pdf(local_path=self.local_path, internet_path=self.internet_path):
                    self.texto_original = self.extract_text(
                        pdf_path=self.local_path, limpar_texto=self.limpar_texto
                    )
                else:
                    logger.error(f"Erro ao verificar PDF especificado: {e}")
        

        logger.info(
            f"Inicializando DiarioOficial para a data: {self.dia:02d}/{self.mes:02d}/{self.ano}"
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
            / f"{self.ano}"
            / f"{self.mes:02d}"
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
                logger.warning(
                    f"URL encontrada não parece ser PDF: {self.internet_path}"
                )

        logger.success(f"URL do PDF encontrada: {self.internet_path}")
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
            logger.success(f"Diretório encontrado: {download_dir}")
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
                    logger.success(f"PDF encontrado e não vazio: {pdf_path}")
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


    def download_pdf(self, internet_path: str, local_path: Path = None) -> bool:
        """
        Baixa o PDF da URL armazenada.

        Args:
            save_path: Caminho personalizado para salvar o arquivo

        Returns:
            True se o download foi bem sucedido
        """
        if not self.diario_valido or not internet_path:
            logger.error("URL do PDF não disponível. Diário pode não existir.")
            raise DiarioNaoExiste(f"Diário não encontrado para {self.publicacao}")
        local_path = self.local_path if not local_path else local_path
        
        try:
            logger.info(f"Iniciando download do PDF: {self.pdf_file}")
            response = requests.get(internet_path, timeout=60)
            response.raise_for_status()
            try:
                # Ensure the directory exists before saving the file
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                logger.debug(f'Trying to make a file {self.pdf_file} on {self.download_dir} with the full local_path as {self.local_path}')
                with open(self.local_path, "wb") as f:
                    f.write(response.content)
                logger.success(f"PDF salvo com sucesso em: {self.local_path}")
                return True
            except IOError as e:
                logger.error(f"Falha ao salvar PDF: {e}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Falha no download do PDF: {e}")
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

    def _obter_numero_diario(self, texto: str) -> str:
        pattern = r"\b\d{4}[\s\W]+DOE\s+TCMPA\s+Nº\s+([\d\.]+)"
        match = re.search(pattern, texto, re.DOTALL)
        if match:
            numero = match.group(1)
            return numero
        else:
            return ""

    def extract_text(self, pdf_path: Path = None, limpar_texto: bool = True) -> str:
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

        try:
            logger.info(f"Iniciando extração de texto de: {pdf_path}")
            with pymupdf.open(pdf_path) as pdf:
                texto = []
                total_paginas = len(pdf)

                for i, pagina in enumerate(pdf):
                    if i == 0:  # Pula a primeira página
                        continue
                    logger.info(f"Processando página {i+1}/{total_paginas}")
                    texto_pagina = pagina.get_text()
                    self.numero_diario = self._obter_numero_diario(texto_pagina)
                    texto_pagina = (
                        self.clean_text(texto_pagina) if limpar_texto else texto_pagina
                    )
                    if texto_pagina:
                        texto.append(texto_pagina)

                texto_bruto = "\n".join(texto)

            if not texto_bruto:
                logger.warning("Nenhum texto extraído do PDF")

            self.texto_original = texto_bruto  # Armazena o texto para reutilização
            return self.texto_original
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

    @property
    def texto_preview(self) -> str:
        """Returns a truncated preview of the texto_original"""
        if not hasattr(self, "texto_original") or not self.texto_original:
            return "No text extracted"
        return (
            f"{self.texto_original[:100]}..."
            if len(self.texto_original) > 100
            else self.texto_original
        )

    def __str__(self) -> str:
        """
        Customizes the string representation of the DiarioOficial object.
        Shows a preview of texto_original (first 100 characters) instead of the full text.

        Returns:
            str: The formatted string representation
        """

        # Pegue os atributos do modelo
        attributes = self.model_dump()
        if "texto_original" in attributes and attributes["texto_original"]:
            attributes["texto_original"] = self.texto_preview

        # Formate os atributos em uma string
        formatted_attrs = ", ".join([f"{k}={repr(v)}" for k, v in attributes.items()])
        return f"DiarioOficial({formatted_attrs})"

    def __repr__(self) -> str:
        """
        Override __repr__ to ensure that nested representations use the truncated version.
        """
        return self.__str__()

    def get_full_text(self) -> str:
        """
        Returns the full texto_original content.

        Returns:
            str: The complete extracted text
        """
        return self.texto_original
