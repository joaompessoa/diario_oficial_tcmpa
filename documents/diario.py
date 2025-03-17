from datetime import datetime
from typing import Union, Optional, List, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import os
import re
import logging
import pymupdf
from pathlib import Path
from documents.acordao import Acordao

# Configuração do sistema de logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DiarioOficial")

class DiarioOficial:
    """
    Classe para buscar, baixar e processar PDFs do Diário Oficial do TCM-PA.

    Esta classe gerencia a busca e o processamento de documentos oficiais do
    Tribunal de Contas dos Municípios do Estado do Pará. Ela fornece um
    pipeline completo para buscar a URL do documento, baixar o PDF e extrair texto e metadados.

    Attributes:
        BASE_URL (str): URL base para a página de busca do Diário Oficial
        pdf_url (str, opcional): URL do PDF definida após o método fetch
        save_path (Path, opcional): Caminho onde o PDF baixado é salvo após download

    Examples:
        >>> # Busca e download do Diário Oficial para uma data específica
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

        >>> # Pipeline completo com tratamento de erros
        >>> try:
        ...     diario = DiarioOficial(dia=15, mes=5, ano=2024)
        ...     diario.download_pdf()
        ...     texto = diario.extract_text()
        ... except ValueError as e:
        ...     print(f"Erro de data: {e}")
        ... except Exception as e:
        ...     print(f"Erro inesperado: {e}")
    """
    
    # URL base para pesquisa
    BASE_URL = "https://tcm.ioepa.com.br/busca/default.aspx"

    def __init__(
        self,
        dia: Optional[Union[int, str]] = None,
        mes: Optional[Union[int, str]] = None,
        ano: Optional[Union[int, str]] = None,
        save_pdf: bool = True,
        download_dir: Optional[str] = None,
        auto_fetch: bool = True,
        raw_text: Optional[str] = None
    ):
        """
        Inicializa o objeto DiarioOficial com a data especificada e verifica disponibilidade.

        Args:
            dia: Dia do mês (padrão: dia atual)
            mes: Mês (padrão: mês atual)
            ano: Ano (padrão: ano atual)
            download_dir: Diretório para salvar arquivos (padrão: diretório atual)
            auto_fetch: Verifica automaticamente a disponibilidade (padrão: True)

        Raises:
            ValueError: Se a data especificada estiver no futuro
            RuntimeError: Se o diário não estiver disponível com auto_fetch ativado
        """
        
        # Data de hoje
        hoje = datetime.today()

        # Parsing e validação da data
        self.dia = self._parse_date_part(dia, hoje.day)
        self.mes = self._parse_date_part(mes, hoje.month)
        self.ano = self._parse_date_part(ano, hoje.year)

        # Validação se o usuario nao esta pedindo uma data futura
        data_solicitada = datetime(self.ano, self.mes, self.dia)
        if data_solicitada > hoje:
            raise ValueError(
                f"Data solicitada {self.dia:02d}/{self.mes:02d}/{self.ano} é futura"
            )

        # Configuração do diretório de download, se não for instanciado, fica o diretorio atual
        self.download_dir = Path(download_dir) if download_dir else Path.cwd()  / f'diarios/{str(self.ano)}' / f"{self.mes:02d}"
        if not self.download_dir.exists():
            self.download_dir.mkdir(parents=True)

        # Construção da URL de pesquisa
        self.ioepa_url = f"{self.BASE_URL}?dts={self.dia:02d}/{self.mes:02d}/{self.ano}"

        # Inicialização de atributos
        self.pdf_url: Optional[str] = None
        self.save_path: Optional[Path] = None
        self.session = requests.Session()
        self.is_valid = False
        self.raw_text = ""

        logger.info(
            f"Inicializando DiarioOficial para a data: {self.dia:02d}/{self.mes:02d}/{self.ano}"
        )

        # Busca automática se configurado
        if auto_fetch:
            self.is_valid = self._fetch()
            if not self.is_valid:
                raise RuntimeError(
                    f"Diário não disponível para {self.dia:02d}/{self.mes:02d}/{self.ano}"
                )

    def _parse_date_part(self, value: Optional[Union[int, str]], default: int) -> int:
        """
        Analisa e valida componentes de data (dia, mês, ano).

        Args:
            value: Valor a ser analisado (int, str ou None)
            default: Valor padrão caso value seja None

        Returns:
            Componente de data validado como inteiro

        Raises:
            ValueError: Para valores inválidos ou não numéricos
            TypeError: Para tipos não suportados
        """
        if value is None:
            return default

        if isinstance(value, int):
            return value

        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                raise ValueError(f"Valor de data inválido '{value}'. Deve ser numérico.")

        raise TypeError(
            f"Tipo inválido {type(value)} para parâmetro de data. Esperado int, str ou None."
        )

    def _fetch(self) -> bool:
        """
        Busca a página do Diário Oficial e extrai a URL do PDF.

        Returns:
            True se encontrou o PDF com sucesso, False caso contrário
        """
        try:
            logger.info(f"Buscando URL: {self.ioepa_url}")
            response = self.session.get(self.ioepa_url, timeout=30)
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

        self.pdf_url = urljoin(self.ioepa_url, link["href"])

        # Verificação do tipo de arquivo
        if not self.pdf_url.lower().endswith(".pdf"):
            pdf_link = mid_div.find(
                "a", href=lambda href: href and href.lower().endswith(".pdf")
            )
            if pdf_link and "href" in pdf_link.attrs:
                self.pdf_url = urljoin(self.ioepa_url, pdf_link["href"])
            else:
                logger.warning(f"URL encontrada não parece ser PDF: {self.pdf_url}")

        logger.info(f"URL do PDF encontrada: {self.pdf_url}")
        return True

    def refresh(self) -> bool:
        """
        Atualiza as informações buscando novamente a página.

        Returns:
            True se encontrou o PDF com sucesso
        """
        self.is_valid = self._fetch()
        return self.is_valid

    def download_pdf(self, save_path: Optional[str] = None) -> bool:
        """
        Baixa o PDF da URL armazenada.

        Args:
            save_path: Caminho personalizado para salvar o arquivo

        Returns:
            True se o download foi bem sucedido

        Raises:
            RuntimeError: Se não houver URL válida
        """
        if not self.is_valid or not self.pdf_url:
            logger.error("URL do PDF não disponível. Diário pode não existir.")
            return False

        try:
            logger.info(f"Iniciando download do PDF: {self.pdf_url}")
            response = self.session.get(self.pdf_url, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Falha no download do PDF: {e}")
            return False

        # Determinação do caminho de salvamento
        if save_path:
            self.save_path = self.download_dir
        else:
            parsed_url = urlparse(self.pdf_url)
            path = unquote(parsed_url.path)
            filename = (
                path.split("/")[-1]
                or f"diario_{self.dia:02d}_{self.mes:02d}_{self.ano}.pdf"
            )
            self.save_path = self.download_dir / filename

        try:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.save_path, "wb") as f:
                f.write(response.content)

            logger.info(f"PDF salvo com sucesso em: {self.save_path}")
            return True
        except IOError as e:
            logger.error(f"Falha ao salvar PDF: {e}")
            return False

    def extract_text(
        self, pdf_path: Optional[Union[str, Path]] = None
    ) -> str:
        """
        Extrai texto do PDF com opção de limpeza.

        Args:
            clean: Habilita limpeza do texto extraído
            pdf_path: Caminho alternativo para o arquivo PDF

        Returns:
            Texto extraído (limpo se habilitado)
        """
        if hasattr(self, 'raw_text') and self.raw_text:
            logger.info("Texto já extraído anteriormente, reutilizando raw_text.")
            return self.raw_text

        pdf_path = pdf_path or self.save_path
        if not pdf_path:
            logger.error("Nenhum PDF disponível. Faça o download primeiro.")
            return ""

        try:
            logger.info(f"Iniciando extração de texto de: {pdf_path}")
            with pymupdf.open(pdf_path) as pdf:
                texto = []
                total_paginas = len(pdf)

                for i, pagina in enumerate(pdf):
                    logger.info(f"Processando página {i+1}/{total_paginas}")
                    texto_pagina = pagina.get_text()
                    if texto_pagina:
                        texto.append(texto_pagina)

                texto_bruto = "\n".join(texto)

            if not texto_bruto:
                logger.warning("Nenhum texto extraído do PDF")

            self.raw_text = texto_bruto  # Armazena o texto para reutilização
            return texto_bruto
        except Exception as e:
            logger.error(f"Erro na extração de texto: {e}")
            return ""


    def is_available(self) -> bool:
        """
        Verifica disponibilidade do diário.

        Returns:
            True se o diário está disponível
        """
        return self.is_valid
    
    def get_acordao(self) -> List[Acordao]:
        if self.raw_text:
            texto = self.raw_text
        else:
            texto = self.extract_text()
        
        if not texto:
            logger.warning("Nenhum texto disponível para extração de dados")
            return []
        
        acordao = Acordao(raw_text=texto, date_str=f"{self.dia:02d}/{self.mes:02d}/{self.ano}")
        acordao_structured = acordao.from_sections(texto)
        
        return acordao_structured
        

    def get_structured_data(self) -> List[Dict[str, Any]]:
        """
        Extrai dados estruturados de editais e documentos.

        Returns:
            Lista de dicionários com dados estruturados
        """
        if self.raw_text:
            texto = self.raw_text
        else:
            texto = self.extract_text()
        if not texto:
            logger.warning("Nenhum texto disponível para extração de dados")
            return []

        documentos = []
        
        acordao = Acordao(raw_text=texto)
        acordao_structured = acordao.from_sections(texto)
        
        return acordao_structured

        
    def __str__(self) -> str:
        """Representação textual do objeto DiarioOficial."""
        status = "Disponível" if self.is_valid else "Indisponível"
        caminho_pdf = str(self.save_path) if self.save_path else "Não baixado"

        return (
            f"DiarioOficial({self.dia:02d}/{self.mes:02d}/{self.ano}) - "
            f"Status: {status}, PDF: {caminho_pdf}"
        )