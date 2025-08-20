"""
Сервис шифрования данных
Обеспечивает безопасное хранение чувствительных данных
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EncryptionService:
    """Сервис для шифрования и расшифровки данных"""
    
    def __init__(self, encryption_key: str):
        """
        Инициализация сервиса шифрования
        
        Args:
            encryption_key: Ключ шифрования (32 байта)
        """
        self.encryption_key = encryption_key.encode()
        self._fernet = None
        self._initialize_fernet()
    
    def _initialize_fernet(self):
        """Инициализация Fernet для шифрования"""
        try:
            # Создаем ключ из пароля
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'finguard_salt_2025',  # Фиксированная соль для демо
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key))
            self._fernet = Fernet(key)
            logger.info("✅ Сервис шифрования инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации шифрования: {e}")
            self._fernet = None
    
    def encrypt(self, data: str) -> str:
        """
        Шифрует данные
        
        Args:
            data: Данные для шифрования
            
        Returns:
            str: Зашифрованные данные в base64
        """
        if not self._fernet:
            logger.error("❌ Сервис шифрования не инициализирован")
            return data
        
        try:
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"❌ Ошибка шифрования: {e}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Расшифровывает данные
        
        Args:
            encrypted_data: Зашифрованные данные в base64
            
        Returns:
            str: Расшифрованные данные
        """
        if not self._fernet:
            logger.error("❌ Сервис шифрования не инициализирован")
            return encrypted_data
        
        try:
            # Проверяем, что данные действительно зашифрованы
            if not encrypted_data or len(encrypted_data) < 10:
                return encrypted_data
            
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"❌ Ошибка расшифровки: {e}")
            return encrypted_data
    
    def encrypt_payment_data(self, card_number: str, cvv: str = None) -> dict:
        """
        Шифрует платежные данные
        
        Args:
            card_number: Номер карты
            cvv: CVV код (опционально)
            
        Returns:
            dict: Зашифрованные данные
        """
        encrypted_data = {
            'card_number': self.encrypt(card_number),
            'masked_number': self._mask_card_number(card_number)
        }
        
        if cvv:
            encrypted_data['cvv'] = self.encrypt(cvv)
        
        return encrypted_data
    
    def decrypt_payment_data(self, encrypted_data: dict) -> dict:
        """
        Расшифровывает платежные данные
        
        Args:
            encrypted_data: Зашифрованные данные
            
        Returns:
            dict: Расшифрованные данные
        """
        decrypted_data = {}
        
        if 'card_number' in encrypted_data:
            decrypted_data['card_number'] = self.decrypt(encrypted_data['card_number'])
        
        if 'cvv' in encrypted_data:
            decrypted_data['cvv'] = self.decrypt(encrypted_data['cvv'])
        
        if 'masked_number' in encrypted_data:
            decrypted_data['masked_number'] = encrypted_data['masked_number']
        
        return decrypted_data
    
    def _mask_card_number(self, card_number: str) -> str:
        """
        Маскирует номер карты
        
        Args:
            card_number: Номер карты
            
        Returns:
            str: Маскированный номер
        """
        if not card_number or len(card_number) < 4:
            return card_number
        
        return f"{'*' * (len(card_number) - 4)}{card_number[-4:]}"
    
    def is_encrypted(self, data: str) -> bool:
        """
        Проверяет, зашифрованы ли данные
        
        Args:
            data: Данные для проверки
            
        Returns:
            bool: True если данные зашифрованы
        """
        try:
            if not data or len(data) < 10:
                return False
            
            # Пытаемся декодировать base64
            base64.urlsafe_b64decode(data.encode())
            return True
        except Exception:
            return False


# Глобальный экземпляр сервиса шифрования
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """
    Получает глобальный экземпляр сервиса шифрования
    
    Returns:
        EncryptionService: Сервис шифрования
    """
    global _encryption_service
    
    if _encryption_service is None:
        from app.config import get_settings
        settings = get_settings()
        _encryption_service = EncryptionService(settings.encryption_key)
    
    return _encryption_service


def encrypt_data(data: str) -> str:
    """
    Шифрует данные
    
    Args:
        data: Данные для шифрования
        
    Returns:
        str: Зашифрованные данные
    """
    service = get_encryption_service()
    return service.encrypt(data)


def decrypt_data(encrypted_data: str) -> str:
    """
    Расшифровывает данные
    
    Args:
        encrypted_data: Зашифрованные данные
        
    Returns:
        str: Расшифрованные данные
    """
    service = get_encryption_service()
    return service.decrypt(encrypted_data)
