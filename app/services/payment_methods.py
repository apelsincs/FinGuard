"""
Сервис управления платежными методами
Обеспечивает безопасное управление способами оплаты
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database.models import PaymentMethod, PaymentMethodType, User
from app.security.encryption import get_encryption_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PaymentMethodService:
    """Сервис для управления платежными методами"""
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption_service = get_encryption_service()
    
    def add_payment_method(
        self, 
        user_id: int, 
        name: str, 
        method_type: PaymentMethodType,
        card_number: str = None,
        cvv: str = None,
        is_default: bool = False
    ) -> Dict[str, Any]:
        """
        Добавляет новый способ оплаты
        
        Args:
            user_id: ID пользователя
            name: Название способа оплаты
            method_type: Тип способа оплаты
            card_number: Номер карты (для карт)
            cvv: CVV код (для карт)
            is_default: Сделать способом по умолчанию
            
        Returns:
            dict: Результат операции
        """
        try:
            # Проверяем существование пользователя
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            # Если это карта, шифруем данные
            encrypted_data = None
            masked_number = None
            
            if method_type == PaymentMethodType.CARD and card_number:
                # Шифруем данные карты
                encrypted_data = self.encryption_service.encrypt_payment_data(
                    card_number, cvv
                )
                masked_number = encrypted_data['masked_number']
                encrypted_data = str(encrypted_data)  # Сохраняем как строку
            
            # Если устанавливаем как способ по умолчанию, сбрасываем другие
            if is_default:
                self.db.query(PaymentMethod).filter(
                    and_(
                        PaymentMethod.user_id == user_id,
                        PaymentMethod.is_default == True
                    )
                ).update({'is_default': False})
            
            # Создаем новый способ оплаты
            payment_method = PaymentMethod(
                user_id=user_id,
                name=name,
                type=method_type,
                encrypted_data=encrypted_data,
                masked_number=masked_number,
                is_default=is_default,
                is_active=True
            )
            
            self.db.add(payment_method)
            self.db.commit()
            self.db.refresh(payment_method)
            
            logger.info(f"Добавлен способ оплаты: {name} для пользователя {user_id}")
            
            return {
                'success': True,
                'payment_method': payment_method,
                'message': f'Способ оплаты "{name}" успешно добавлен'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при добавлении способа оплаты: {e}")
            return {
                'success': False,
                'error': f'Ошибка при добавлении способа оплаты: {str(e)}'
            }
    
    def get_user_payment_methods(self, user_id: int, active_only: bool = True) -> List[PaymentMethod]:
        """
        Получает способы оплаты пользователя
        
        Args:
            user_id: ID пользователя
            active_only: Только активные способы
            
        Returns:
            list: Список способов оплаты
        """
        query = self.db.query(PaymentMethod).filter(PaymentMethod.user_id == user_id)
        
        if active_only:
            query = query.filter(PaymentMethod.is_active == True)
        
        return query.order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
    
    def get_payment_method(self, payment_method_id: int, user_id: int) -> Optional[PaymentMethod]:
        """
        Получает конкретный способ оплаты
        
        Args:
            payment_method_id: ID способа оплаты
            user_id: ID пользователя
            
        Returns:
            PaymentMethod: Способ оплаты или None
        """
        return self.db.query(PaymentMethod).filter(
            and_(
                PaymentMethod.id == payment_method_id,
                PaymentMethod.user_id == user_id,
                PaymentMethod.is_active == True
            )
        ).first()
    
    def update_payment_method(
        self, 
        payment_method_id: int, 
        user_id: int, 
        name: str = None,
        is_default: bool = None
    ) -> Dict[str, Any]:
        """
        Обновляет способ оплаты
        
        Args:
            payment_method_id: ID способа оплаты
            user_id: ID пользователя
            name: Новое название
            is_default: Сделать способом по умолчанию
            
        Returns:
            dict: Результат операции
        """
        try:
            payment_method = self.get_payment_method(payment_method_id, user_id)
            if not payment_method:
                return {
                    'success': False,
                    'error': 'Способ оплаты не найден'
                }
            
            # Обновляем поля
            if name:
                payment_method.name = name
            
            if is_default is not None:
                if is_default:
                    # Сбрасываем другие способы по умолчанию
                    self.db.query(PaymentMethod).filter(
                        and_(
                            PaymentMethod.user_id == user_id,
                            PaymentMethod.is_default == True,
                            PaymentMethod.id != payment_method_id
                        )
                    ).update({'is_default': False})
                
                payment_method.is_default = is_default
            
            payment_method.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"Обновлен способ оплаты: {payment_method_id} для пользователя {user_id}")
            
            return {
                'success': True,
                'payment_method': payment_method,
                'message': 'Способ оплаты успешно обновлен'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при обновлении способа оплаты: {e}")
            return {
                'success': False,
                'error': f'Ошибка при обновлении способа оплаты: {str(e)}'
            }
    
    def delete_payment_method(self, payment_method_id: int, user_id: int) -> Dict[str, Any]:
        """
        Удаляет способ оплаты (мягкое удаление)
        
        Args:
            payment_method_id: ID способа оплаты
            user_id: ID пользователя
            
        Returns:
            dict: Результат операции
        """
        try:
            payment_method = self.get_payment_method(payment_method_id, user_id)
            if not payment_method:
                return {
                    'success': False,
                    'error': 'Способ оплаты не найден'
                }
            
            # Проверяем, используется ли способ в транзакциях
            from app.database.models import Transaction
            transactions_count = self.db.query(Transaction).filter(
                Transaction.payment_method_id == payment_method_id
            ).count()
            
            if transactions_count > 0:
                return {
                    'success': False,
                    'error': f'Нельзя удалить способ оплаты, который используется в {transactions_count} транзакциях'
                }
            
            # Мягкое удаление
            payment_method.is_active = False
            payment_method.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"Удален способ оплаты: {payment_method_id} для пользователя {user_id}")
            
            return {
                'success': True,
                'message': 'Способ оплаты успешно удален'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при удалении способа оплаты: {e}")
            return {
                'success': False,
                'error': f'Ошибка при удалении способа оплаты: {str(e)}'
            }
    
    def set_default_payment_method(self, payment_method_id: int, user_id: int) -> Dict[str, Any]:
        """
        Устанавливает способ оплаты по умолчанию
        
        Args:
            payment_method_id: ID способа оплаты
            user_id: ID пользователя
            
        Returns:
            dict: Результат операции
        """
        try:
            payment_method = self.get_payment_method(payment_method_id, user_id)
            if not payment_method:
                return {
                    'success': False,
                    'error': 'Способ оплаты не найден'
                }
            
            # Сбрасываем другие способы по умолчанию
            self.db.query(PaymentMethod).filter(
                and_(
                    PaymentMethod.user_id == user_id,
                    PaymentMethod.is_default == True
                )
            ).update({'is_default': False})
            
            # Устанавливаем новый способ по умолчанию
            payment_method.is_default = True
            payment_method.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"Установлен способ оплаты по умолчанию: {payment_method_id} для пользователя {user_id}")
            
            return {
                'success': True,
                'message': f'Способ оплаты "{payment_method.name}" установлен по умолчанию'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при установке способа оплаты по умолчанию: {e}")
            return {
                'success': False,
                'error': f'Ошибка при установке способа оплаты по умолчанию: {str(e)}'
            }
    
    def get_default_payment_method(self, user_id: int) -> Optional[PaymentMethod]:
        """
        Получает способ оплаты по умолчанию
        
        Args:
            user_id: ID пользователя
            
        Returns:
            PaymentMethod: Способ оплаты по умолчанию или None
        """
        return self.db.query(PaymentMethod).filter(
            and_(
                PaymentMethod.user_id == user_id,
                PaymentMethod.is_default == True,
                PaymentMethod.is_active == True
            )
        ).first()
    
    def format_payment_method_display(self, payment_method: PaymentMethod) -> str:
        """
        Форматирует способ оплаты для отображения
        
        Args:
            payment_method: Способ оплаты
            
        Returns:
            str: Отформатированная строка
        """
        display = f"💳 {payment_method.name}"
        
        if payment_method.type == PaymentMethodType.CARD:
            if payment_method.masked_number:
                display += f" ({payment_method.masked_number})"
            else:
                display += " (карта)"
        elif payment_method.type == PaymentMethodType.CASH:
            display += " (наличные)"
        elif payment_method.type == PaymentMethodType.BANK_TRANSFER:
            display += " (банковский перевод)"
        elif payment_method.type == PaymentMethodType.DIGITAL_WALLET:
            display += " (цифровой кошелек)"
        
        if payment_method.is_default:
            display += " ⭐ (по умолчанию)"
        
        return display
