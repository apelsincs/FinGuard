"""
Система логирования для FinGuard
Использует Loguru для удобного и структурированного логирования
"""

import sys
from loguru import logger
from app.config import get_settings


def setup_logger():
    """
    Настройка системы логирования
    Конфигурирует Loguru для вывода в консоль и файлы
    """
    settings = get_settings()
    
    # Удаляем стандартный обработчик Loguru
    logger.remove()
    
    # Добавляем обработчик для консоли
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=settings.log_level,
        colorize=True
    )
    
    # Добавляем обработчик для файла логов
    logger.add(
        "logs/finguard.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=settings.log_level,
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    # Добавляем обработчик для ошибок
    logger.add(
        "logs/errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="5 MB",
        retention="90 days",
        compression="zip"
    )
    
    # Добавляем обработчик для финансовых операций
    logger.add(
        "logs/financial.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        filter=lambda record: "financial" in record["name"].lower() or "payment" in record["name"].lower(),
        rotation="20 MB",
        retention="1 year",
        compression="zip"
    )
    
    # Добавляем обработчик для безопасности
    logger.add(
        "logs/security.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        filter=lambda record: "security" in record["name"].lower() or "fraud" in record["name"].lower(),
        rotation="10 MB",
        retention="2 years",
        compression="zip"
    )


def get_logger(name: str):
    """
    Получить логгер для конкретного модуля
    
    Args:
        name: Имя модуля (обычно __name__)
    
    Returns:
        Logger: Настроенный логгер
    """
    return logger.bind(name=name)


# Создаем директорию для логов при импорте модуля
import os
os.makedirs("logs", exist_ok=True)

# Настраиваем логгер при импорте
setup_logger()
