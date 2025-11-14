"""
Logger centralizado para la aplicación.
"""

import logging
from src.config import LOG_LEVEL, DEBUG_MODE

# Configurar logger
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def log_info(message: str):
    """Log de información"""
    logger.info(message)


def log_warning(message: str):
    """Log de advertencia"""
    logger.warning(message)


def log_error(message: str):
    """Log de error"""
    logger.error(message)


def log_debug(message: str):
    """Log de debug"""
    if DEBUG_MODE:
        logger.debug(message)
