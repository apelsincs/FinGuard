"""
Конфигурация приложения FinGuard
Использует Pydantic Settings для безопасного управления переменными окружения
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Основные настройки приложения"""
    
    # Telegram Bot Configuration
    telegram_bot_token: str
    telegram_webhook_url: Optional[str] = None
    
    # Database Configuration
    database_url: str
    
    # Security Configuration
    secret_key: str
    encryption_key: str
    
    # Payment System Configuration
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    yookassa_secret_key: Optional[str] = None
    yookassa_shop_id: Optional[str] = None
    
    # Application Configuration
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"
    
    # Fraud Detection Configuration
    fraud_detection_enabled: bool = True
    suspicious_amount_threshold: float = 10000.0
    unusual_time_window_hours: int = 2
    
    # Analytics Configuration
    analytics_enabled: bool = True
    report_generation_enabled: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Создаем глобальный экземпляр настроек
settings = Settings()


def get_settings() -> Settings:
    """Получить настройки приложения"""
    return settings


def validate_environment() -> bool:
    """
    Проверка корректности настроек окружения
    Возвращает True если все критически важные настройки присутствуют
    """
    required_settings = [
        'telegram_bot_token',
        'database_url',
        'secret_key',
        'encryption_key'
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not getattr(settings, setting, None):
            missing_settings.append(setting)
    
    if missing_settings:
        print(f"❌ Отсутствуют обязательные настройки: {', '.join(missing_settings)}")
        print("Пожалуйста, создайте файл .env на основе env.example")
        return False
    
    print("✅ Все обязательные настройки присутствуют")
    return True
