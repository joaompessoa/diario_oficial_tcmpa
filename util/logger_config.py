from loguru import logger as loguru_logger
from loguru._logger import Logger
import sys

time_format = "{time:YYYY-MM-DD HH:mm}"
logger: Logger = loguru_logger
logger.remove()
logger.add(
    sys.stdout, 
    level="DEBUG",
    colorize=True,
)
  