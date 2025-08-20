"""
Сервис интеграции с платежными системами
Поддерживает Stripe и YooKassa
"""

import stripe
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session
from app.database.models import Transaction, TransactionType, TransactionStatus, User
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Инициализируем Stripe
stripe.api_key = get_settings().stripe_secret_key


class PaymentSystemService:
    """Сервис для работы с платежными системами"""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    def create_stripe_payment_intent(
        self,
        user_id: int,
        amount: float,
        currency: str = "RUB",
        description: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Создает платежное намерение в Stripe
        
        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            currency: Валюта
            description: Описание платежа
            metadata: Дополнительные данные
            
        Returns:
            dict: Информация о платежном намерении
        """
        try:
            if not self.settings.stripe_secret_key:
                return {
                    'success': False,
                    'error': 'Stripe не настроен'
                }
            
            # Получаем пользователя
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            # Создаем платежное намерение
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe использует центы
                currency=currency.lower(),
                description=description or f"Платеж пользователя {user.first_name}",
                metadata={
                    'user_id': user_id,
                    'telegram_id': user.telegram_id,
                    **(metadata or {})
                }
            )
            
            logger.info(f"Создано платежное намерение Stripe: {intent.id}")
            
            return {
                'success': True,
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'amount': amount,
                'currency': currency,
                'status': intent.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Ошибка Stripe: {e}")
            return {
                'success': False,
                'error': f'Ошибка Stripe: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def confirm_stripe_payment(
        self,
        payment_intent_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Подтверждает платеж в Stripe
        
        Args:
            payment_intent_id: ID платежного намерения
            user_id: ID пользователя
            
        Returns:
            dict: Результат подтверждения
        """
        try:
            # Получаем платежное намерение
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                # Создаем транзакцию в базе данных
                transaction = Transaction(
                    user_id=user_id,
                    amount=float(intent.amount) / 100,  # Конвертируем из центов
                    currency=intent.currency.upper(),
                    description=f"Платеж Stripe: {intent.description}",
                    type=TransactionType.INCOME,
                    status=TransactionStatus.CONFIRMED,
                    transaction_date=datetime.fromtimestamp(intent.created),
                    merchant="Stripe",
                    location="Online"
                )
                
                self.db.add(transaction)
                self.db.commit()
                
                logger.info(f"Платеж Stripe подтвержден: {payment_intent_id}")
                
                return {
                    'success': True,
                    'transaction_id': transaction.id,
                    'amount': transaction.amount,
                    'status': 'confirmed'
                }
            else:
                return {
                    'success': False,
                    'error': f'Платеж не подтвержден. Статус: {intent.status}'
                }
                
        except stripe.error.StripeError as e:
            logger.error(f"Ошибка Stripe при подтверждении: {e}")
            return {
                'success': False,
                'error': f'Ошибка Stripe: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Ошибка подтверждения платежа: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def create_yookassa_payment(
        self,
        user_id: int,
        amount: float,
        currency: str = "RUB",
        description: str = None,
        return_url: str = None
    ) -> Dict[str, Any]:
        """
        Создает платеж в YooKassa
        
        Args:
            user_id: ID пользователя
            amount: Сумма платежа
            currency: Валюта
            description: Описание платежа
            return_url: URL для возврата после оплаты
            
        Returns:
            dict: Информация о платеже
        """
        try:
            if not self.settings.yookassa_secret_key:
                return {
                    'success': False,
                    'error': 'YooKassa не настроен'
                }
            
            # Получаем пользователя
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    'success': False,
                    'error': 'Пользователь не найден'
                }
            
            # Здесь должна быть интеграция с YooKassa API
            # Для демонстрации возвращаем заглушку
            
            logger.info(f"Создан платеж YooKassa для пользователя {user_id}")
            
            return {
                'success': True,
                'payment_id': f"yk_{user_id}_{int(datetime.now().timestamp())}",
                'amount': amount,
                'currency': currency,
                'status': 'pending',
                'message': 'Платеж создан (демо-режим)'
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа YooKassa: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def get_payment_status(
        self,
        payment_id: str,
        payment_system: str
    ) -> Dict[str, Any]:
        """
        Получает статус платежа
        
        Args:
            payment_id: ID платежа
            payment_system: Система платежа (stripe, yookassa)
            
        Returns:
            dict: Статус платежа
        """
        try:
            if payment_system == 'stripe':
                intent = stripe.PaymentIntent.retrieve(payment_id)
                return {
                    'success': True,
                    'status': intent.status,
                    'amount': float(intent.amount) / 100,
                    'currency': intent.currency.upper(),
                    'created': datetime.fromtimestamp(intent.created)
                }
            elif payment_system == 'yookassa':
                # Здесь должна быть проверка статуса в YooKassa
                return {
                    'success': True,
                    'status': 'pending',
                    'message': 'Демо-режим YooKassa'
                }
            else:
                return {
                    'success': False,
                    'error': 'Неизвестная платежная система'
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статуса платежа: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def refund_payment(
        self,
        payment_id: str,
        payment_system: str,
        amount: float = None
    ) -> Dict[str, Any]:
        """
        Возвращает средства
        
        Args:
            payment_id: ID платежа
            payment_system: Система платежа
            amount: Сумма возврата (если None, возвращается вся сумма)
            
        Returns:
            dict: Результат возврата
        """
        try:
            if payment_system == 'stripe':
                if amount:
                    refund = stripe.Refund.create(
                        payment_intent=payment_id,
                        amount=int(amount * 100)
                    )
                else:
                    refund = stripe.Refund.create(payment_intent=payment_id)
                
                logger.info(f"Возврат Stripe создан: {refund.id}")
                
                return {
                    'success': True,
                    'refund_id': refund.id,
                    'amount': float(refund.amount) / 100,
                    'status': refund.status
                }
                
            elif payment_system == 'yookassa':
                # Здесь должна быть интеграция с YooKassa API
                return {
                    'success': True,
                    'message': 'Возврат создан (демо-режим)'
                }
            else:
                return {
                    'success': False,
                    'error': 'Неизвестная платежная система'
                }
                
        except Exception as e:
            logger.error(f"Ошибка возврата средств: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def get_payment_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Получает историю платежей пользователя
        
        Args:
            user_id: ID пользователя
            limit: Количество платежей
            
        Returns:
            dict: История платежей
        """
        try:
            # Получаем транзакции, связанные с платежными системами
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.merchant.in_(['Stripe', 'YooKassa'])
            ).order_by(Transaction.created_at.desc()).limit(limit).all()
            
            payment_history = []
            for transaction in transactions:
                payment_history.append({
                    'id': transaction.id,
                    'amount': transaction.amount,
                    'currency': transaction.currency,
                    'description': transaction.description,
                    'status': transaction.status.value,
                    'date': transaction.created_at,
                    'merchant': transaction.merchant
                })
            
            return {
                'success': True,
                'payments': payment_history,
                'total': len(payment_history)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения истории платежей: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
