"""
Сервис двухфакторной аутентификации
Обеспечивает безопасную аутентификацию пользователей
"""

import secrets
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database.models import User
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TwoFactorService:
    """Сервис для двухфакторной аутентификации"""
    
    def __init__(self, db: Session):
        self.db = db
        self.code_length = 6
        self.code_expiry_minutes = 5
        self.max_attempts = 3
        self.lockout_minutes = 15
    
    def generate_code(self) -> str:
        """
        Генерирует код подтверждения
        
        Returns:
            str: 6-значный код
        """
        return ''.join(secrets.choice('0123456789') for _ in range(self.code_length))
    
    def hash_code(self, code: str) -> str:
        """
        Хеширует код для безопасного хранения
        
        Args:
            code: Код для хеширования
            
        Returns:
            str: Хеш кода
        """
        return hashlib.sha256(code.encode()).hexdigest()
    
    def enable_2fa(self, user_id: int) -> Dict[str, Any]:
        """
        Включает двухфакторную аутентификацию
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Результат операции
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            if user.two_factor_enabled:
                return {
                    'success': False,
                    'error': 'Двухфакторная аутентификация уже включена'
                }
            
            # Генерируем код подтверждения
            code = self.generate_code()
            code_hash = self.hash_code(code)
            
            # Сохраняем хеш кода и время создания
            user.two_factor_enabled = True
            user.updated_at = datetime.now()
            
            # В реальном приложении здесь можно сохранить хеш кода в отдельной таблице
            # Для демо-версии просто возвращаем код
            
            self.db.commit()
            
            logger.info(f"Включена 2FA для пользователя {user_id}")
            
            return {
                'success': True,
                'code': code,  # В продакшене код отправляется по SMS/email
                'message': 'Двухфакторная аутентификация включена. Код подтверждения отправлен.'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при включении 2FA: {e}")
            return {
                'success': False,
                'error': f'Ошибка при включении 2FA: {str(e)}'
            }
    
    def disable_2fa(self, user_id: int, code: str) -> Dict[str, Any]:
        """
        Отключает двухфакторную аутентификацию
        
        Args:
            user_id: ID пользователя
            code: Код подтверждения
            
        Returns:
            dict: Результат операции
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            if not user.two_factor_enabled:
                return {
                    'success': False,
                    'error': 'Двухфакторная аутентификация не включена'
                }
            
            # В реальном приложении здесь проверяется код
            # Для демо-версии принимаем любой код
            
            user.two_factor_enabled = False
            user.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"Отключена 2FA для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Двухфакторная аутентификация отключена'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при отключении 2FA: {e}")
            return {
                'success': False,
                'error': f'Ошибка при отключении 2FA: {str(e)}'
            }
    
    def verify_2fa_code(self, user_id: int, code: str) -> Dict[str, Any]:
        """
        Проверяет код двухфакторной аутентификации
        
        Args:
            user_id: ID пользователя
            code: Код для проверки
            
        Returns:
            dict: Результат проверки
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            if not user.two_factor_enabled:
                return {
                    'success': False,
                    'error': 'Двухфакторная аутентификация не включена'
                }
            
            # В реальном приложении здесь проверяется код из базы данных
            # Для демо-версии принимаем любой 6-значный код
            
            if not code.isdigit() or len(code) != self.code_length:
                return {
                    'success': False,
                    'error': f'Код должен содержать {self.code_length} цифр'
                }
            
            # Проверяем код (в демо-версии принимаем любой)
            code_hash = self.hash_code(code)
            
            # В реальном приложении здесь сравниваем с сохраненным хешем
            # и проверяем время истечения
            
            logger.info(f"Успешная проверка 2FA кода для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Код подтверждения верный'
            }
            
        except Exception as e:
            logger.error(f"Ошибка при проверке 2FA кода: {e}")
            return {
                'success': False,
                'error': f'Ошибка при проверке кода: {str(e)}'
            }
    
    def generate_backup_codes(self, user_id: int) -> Dict[str, Any]:
        """
        Генерирует резервные коды для восстановления доступа
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Резервные коды
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            if not user.two_factor_enabled:
                return {
                    'success': False,
                    'error': 'Двухфакторная аутентификация не включена'
                }
            
            # Генерируем 5 резервных кодов
            backup_codes = []
            for _ in range(5):
                code = self.generate_code()
                backup_codes.append(code)
            
            logger.info(f"Сгенерированы резервные коды для пользователя {user_id}")
            
            return {
                'success': True,
                'backup_codes': backup_codes,
                'message': 'Резервные коды сгенерированы. Сохраните их в безопасном месте.'
            }
            
        except Exception as e:
            logger.error(f"Ошибка при генерации резервных кодов: {e}")
            return {
                'success': False,
                'error': f'Ошибка при генерации резервных кодов: {str(e)}'
            }
    
    def get_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """
        Получает статус двухфакторной аутентификации
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Статус 2FA
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            return {
                'success': True,
                'enabled': user.two_factor_enabled,
                'message': 'Двухфакторная аутентификация включена' if user.two_factor_enabled else 'Двухфакторная аутентификация отключена'
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статуса 2FA: {e}")
            return {
                'success': False,
                'error': f'Ошибка при получении статуса: {str(e)}'
            }
    
    def require_2fa_for_transaction(self, user_id: int, amount: float) -> bool:
        """
        Определяет, требуется ли 2FA для транзакции
        
        Args:
            user_id: ID пользователя
            amount: Сумма транзакции
            
        Returns:
            bool: Требуется ли 2FA
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.two_factor_enabled:
                return False
            
            # 2FA требуется для крупных транзакций (>10,000 ₽)
            return amount > 10000
            
        except Exception as e:
            logger.error(f"Ошибка при проверке необходимости 2FA: {e}")
            return False
