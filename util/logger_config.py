from loguru import logger as loguru_logger
from loguru._logger import Logger
import sys
from pathlib import Path


def setup_logger(name: str = __name__) -> Logger:
    # Create a configured logger instance
    logger: Logger = loguru_logger
    # Remove default handlers
    logger.remove()

    base_dir = Path(__file__).parent.parent  # Root do projeto
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)  # Cria o diretorio de logs se não existir

    time_format = "{time:YYYY-MM-DD HH:mm}"
    log_format = (
        f"{time_format} | {{level}} | {{file}}:{{function}}:{{line}} | {{message}}"
    )

    # Main logger
    log_file = log_dir / f"{name}.log"

    logger.add(
        sink=log_file,
        level="DEBUG",
        rotation="00:00",  # Rotaciona a meia noite
        retention="3 days",  # Mantém os logs por 3 dias
        colorize=False,
        enqueue=True,  # Usa fila para evitar bloqueio
        backtrace=True,  # Inclui backtrace em caso de erro
        diagnose=True,  # Inclui diagnóstico de erro
        format=log_format,
    )

    # stdout handler para operações normais
    logger.add(
        sink=sys.stdout,
        level="DEBUG",
        colorize=True,
        enqueue=True,
        format=log_format,
    )

    return logger



