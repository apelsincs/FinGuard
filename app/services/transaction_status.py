"""
Сервис управления статусами транзакций
Обеспечивает контроль над статусами финансовых операций
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database.models import Transaction, TransactionStatus, User
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TransactionStatusService:
    """Сервис для управления статусами транзакций"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def confirm_transaction(self, transaction_id: int, user_id: int) -> Dict[str, Any]:
        """
        Подтверждает транзакцию
        
        Args:
            transaction_id: ID транзакции
            user_id: ID пользователя
            
        Returns:
            dict: Результат операции
        """
        try:
            transaction = self.db.query(Transaction).filter(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                )
            ).first()
            
            if not transaction:
                return {
                    'success': False,
                    'error': 'Транзакция не найдена'
                }
            
            if transaction.status == TransactionStatus.CONFIRMED:
                return {
                    'success': False,
                    'error': 'Транзакция уже подтверждена'
                }
            
            if transaction.status == TransactionStatus.REJECTED:
                return {
                    'success': False,
                    'error': 'Нельзя подтвердить отклоненную транзакцию'
                }
            
            transaction.status = TransactionStatus.CONFIRMED
            transaction.updated_at = datetime.now()
            self.db.commit()
            
            logger.info(f"Подтверждена транзакция {transaction_id} пользователем {user_id}")
            
            return {
                'success': True,
                'transaction': transaction,
                'message': f'Транзакция {transaction_id} подтверждена'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при подтверждении транзакции: {e}")
            return {
                'success': False,
                'error': f'Ошибка при подтверждении транзакции: {str(e)}'
            }
    
    def reject_transaction(self, transaction_id: int, user_id: int, reason: str = None) -> Dict[str, Any]:
        """
        Отклоняет транзакцию
        
        Args:
            transaction_id: ID транзакции
            user_id: ID пользователя
            reason: Причина отклонения
            
        Returns:
            dict: Результат операции
        """
        try:
            transaction = self.db.query(Transaction).filter(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                )
            ).first()
            
            if not transaction:
                return {
                    'success': False,
                    'error': 'Транзакция не найдена'
                }
            
            if transaction.status == TransactionStatus.REJECTED:
                return {
                    'success': False,
                    'error': 'Транзакция уже отклонена'
                }
            
            if transaction.status == TransactionStatus.CONFIRMED:
                return {
                    'success': False,
                    'error': 'Нельзя отклонить подтвержденную транзакцию'
                }
            
            transaction.status = TransactionStatus.REJECTED
            transaction.updated_at = datetime.now()
            
            # Добавляем причину отклонения в описание
            if reason:
                current_description = transaction.description or ""
                transaction.description = f"{current_description} [ОТКЛОНЕНО: {reason}]"
            
            self.db.commit()
            
            logger.info(f"Отклонена транзакция {transaction_id} пользователем {user_id}")
            
            return {
                'success': True,
                'transaction': transaction,
                'message': f'Транзакция {transaction_id} отклонена'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при отклонении транзакции: {e}")
            return {
                'success': False,
                'error': f'Ошибка при отклонении транзакции: {str(e)}'
            }
    
    def mark_as_suspicious(self, transaction_id: int, user_id: int, reason: str = None) -> Dict[str, Any]:
        """
        Помечает транзакцию как подозрительную
        
        Args:
            transaction_id: ID транзакции
            user_id: ID пользователя
            reason: Причина подозрительности
            
        Returns:
            dict: Результат операции
        """
        try:
            transaction = self.db.query(Transaction).filter(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id
                )
            ).first()
            
            if not transaction:
                return {
                    'success': False,
                    'error': 'Транзакция не найдена'
                }
            
            transaction.status = TransactionStatus.SUSPICIOUS
            transaction.is_suspicious = True
            transaction.fraud_score = 0.8  # Высокий уровень подозрительности
            transaction.fraud_reasons = reason or "Помечено пользователем как подозрительная"
            transaction.updated_at = datetime.now()
            
            self.db.commit()
            
            logger.info(f"Помечена как подозрительная транзакция {transaction_id} пользователем {user_id}")
            
            return {
                'success': True,
                'transaction': transaction,
                'message': f'Транзакция {transaction_id} помечена как подозрительная'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при пометке транзакции как подозрительной: {e}")
            return {
                'success': False,
                'error': f'Ошибка при пометке транзакции: {str(e)}'
            }
    
    def get_pending_transactions(self, user_id: int, limit: int = 10) -> List[Transaction]:
        """
        Получает ожидающие транзакции пользователя
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество транзакций
            
        Returns:
            list: Список ожидающих транзакций
        """
        return self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.status == TransactionStatus.PENDING
            )
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
    
    def get_suspicious_transactions(self, user_id: int, limit: int = 10) -> List[Transaction]:
        """
        Получает подозрительные транзакции пользователя
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество транзакций
            
        Returns:
            list: Список подозрительных транзакций
        """
        return self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_suspicious == True
            )
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
    
    def get_transactions_by_status(self, user_id: int, status: TransactionStatus, limit: int = 10) -> List[Transaction]:
        """
        Получает транзакции по статусу
        
        Args:
            user_id: ID пользователя
            status: Статус транзакций
            limit: Максимальное количество транзакций
            
        Returns:
            list: Список транзакций
        """
        return self.db.query(Transaction).filter(
            and_(
                Transaction.user_id == user_id,
                Transaction.status == status
            )
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
    
    def get_transaction_status_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Получает сводку по статусам транзакций
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Сводка по статусам
        """
        try:
            from sqlalchemy import func
            
            # Подсчитываем транзакции по статусам
            status_counts = self.db.query(
                Transaction.status,
                func.count(Transaction.id).label('count')
            ).filter(
                Transaction.user_id == user_id
            ).group_by(Transaction.status).all()
            
            summary = {
                'pending': 0,
                'confirmed': 0,
                'rejected': 0,
                'suspicious': 0,
                'total': 0
            }
            
            for status, count in status_counts:
                if status == TransactionStatus.PENDING:
                    summary['pending'] = count
                elif status == TransactionStatus.CONFIRMED:
                    summary['confirmed'] = count
                elif status == TransactionStatus.REJECTED:
                    summary['rejected'] = count
                elif status == TransactionStatus.SUSPICIOUS:
                    summary['suspicious'] = count
                
                summary['total'] += count
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводки статусов: {e}")
            return {
                'pending': 0,
                'confirmed': 0,
                'rejected': 0,
                'suspicious': 0,
                'total': 0
            }
    
    def format_transaction_status(self, transaction: Transaction) -> str:
        """
        Форматирует статус транзакции для отображения
        
        Args:
            transaction: Транзакция
            
        Returns:
            str: Отформатированный статус
        """
        status_icons = {
            TransactionStatus.PENDING: "⏳",
            TransactionStatus.CONFIRMED: "✅",
            TransactionStatus.REJECTED: "❌",
            TransactionStatus.SUSPICIOUS: "⚠️"
        }
        
        status_names = {
            TransactionStatus.PENDING: "Ожидает",
            TransactionStatus.CONFIRMED: "Подтверждена",
            TransactionStatus.REJECTED: "Отклонена",
            TransactionStatus.SUSPICIOUS: "Подозрительная"
        }
        
        icon = status_icons.get(transaction.status, "❓")
        name = status_names.get(transaction.status, "Неизвестно")
        
        return f"{icon} {name}"
