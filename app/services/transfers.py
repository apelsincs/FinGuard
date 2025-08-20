"""
Сервис управления переводами между счетами
Обеспечивает функциональность переводов между разными способами оплаты
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database.models import Transaction, TransactionType, TransactionStatus, PaymentMethod, User
from app.services.payment_methods import PaymentMethodService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TransferService:
    """Сервис для управления переводами между счетами"""
    
    def __init__(self, db: Session):
        self.db = db
        self.payment_method_service = PaymentMethodService(db)
    
    def create_transfer(
        self,
        user_id: int,
        from_method_id: int,
        to_method_id: int,
        amount: float,
        description: str = None,
        fee: float = 0.0
    ) -> Dict[str, Any]:
        """
        Создает перевод между счетами
        
        Args:
            user_id: ID пользователя
            from_method_id: ID способа оплаты откуда
            to_method_id: ID способа оплаты куда
            amount: Сумма перевода
            description: Описание перевода
            fee: Комиссия за перевод
            
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
            
            # Проверяем способы оплаты
            from_method = self.payment_method_service.get_payment_method(from_method_id, user_id)
            to_method = self.payment_method_service.get_payment_method(to_method_id, user_id)
            
            if not from_method:
                return {
                    'success': False,
                    'error': 'Способ оплаты "откуда" не найден'
                }
            
            if not to_method:
                return {
                    'success': False,
                    'error': 'Способ оплаты "куда" не найден'
                }
            
            if from_method_id == to_method_id:
                return {
                    'success': False,
                    'error': 'Нельзя переводить на тот же счет'
                }
            
            if amount <= 0:
                return {
                    'success': False,
                    'error': 'Сумма перевода должна быть больше нуля'
                }
            
            # Создаем транзакцию списания
            from_transaction = Transaction(
                user_id=user_id,
                payment_method_id=from_method_id,
                amount=amount + fee,
                currency="RUB",
                description=f"Перевод: {description or 'между счетами'}",
                type=TransactionType.EXPENSE,
                status=TransactionStatus.CONFIRMED,
                transaction_date=datetime.now()
            )
            
            # Создаем транзакцию зачисления
            to_transaction = Transaction(
                user_id=user_id,
                payment_method_id=to_method_id,
                amount=amount,
                currency="RUB",
                description=f"Перевод: {description or 'между счетами'}",
                type=TransactionType.INCOME,
                status=TransactionStatus.CONFIRMED,
                transaction_date=datetime.now()
            )
            
            self.db.add(from_transaction)
            self.db.add(to_transaction)
            self.db.commit()
            
            # Обновляем объекты
            self.db.refresh(from_transaction)
            self.db.refresh(to_transaction)
            
            logger.info(f"Создан перевод: {amount} ₽ от {from_method.name} к {to_method.name} для пользователя {user_id}")
            
            return {
                'success': True,
                'from_transaction': from_transaction,
                'to_transaction': to_transaction,
                'amount': amount,
                'fee': fee,
                'message': f'Перевод {amount:,.0f} ₽ успешно выполнен'
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при создании перевода: {e}")
            return {
                'success': False,
                'error': f'Ошибка при создании перевода: {str(e)}'
            }
    
    def get_user_transfers(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Получает переводы пользователя
        
        Args:
            user_id: ID пользователя
            days: Количество дней для поиска
            
        Returns:
            list: Список переводов
        """
        try:
            from datetime import timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Получаем все транзакции типа TRANSFER или связанные с переводами
            transfers = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.description.like('Перевод:%')
                )
            ).order_by(Transaction.transaction_date.desc()).all()
            
            # Группируем переводы по парам транзакций
            transfer_pairs = []
            processed_ids = set()
            
            for transaction in transfers:
                if transaction.id in processed_ids:
                    continue
                
                # Ищем парную транзакцию
                pair_transaction = None
                for other_transaction in transfers:
                    if (other_transaction.id != transaction.id and 
                        other_transaction.id not in processed_ids and
                        other_transaction.description == transaction.description and
                        other_transaction.transaction_date == transaction.transaction_date):
                        pair_transaction = other_transaction
                        break
                
                if pair_transaction:
                    # Определяем какая транзакция списание, какая зачисление
                    if transaction.type == TransactionType.EXPENSE:
                        from_transaction = transaction
                        to_transaction = pair_transaction
                    else:
                        from_transaction = pair_transaction
                        to_transaction = transaction
                    
                    transfer_pairs.append({
                        'from_transaction': from_transaction,
                        'to_transaction': to_transaction,
                        'amount': to_transaction.amount,  # Сумма зачисления
                        'fee': from_transaction.amount - to_transaction.amount,  # Комиссия
                        'description': transaction.description.replace('Перевод: ', ''),
                        'date': transaction.transaction_date
                    })
                    
                    processed_ids.add(transaction.id)
                    processed_ids.add(pair_transaction.id)
            
            return transfer_pairs
            
        except Exception as e:
            logger.error(f"Ошибка при получении переводов: {e}")
            return []
    
    def get_transfer_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Получает статистику переводов
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            dict: Статистика переводов
        """
        try:
            transfers = self.get_user_transfers(user_id, days)
            
            total_transfers = len(transfers)
            total_amount = sum(transfer['amount'] for transfer in transfers)
            total_fees = sum(transfer['fee'] for transfer in transfers)
            
            # Статистика по способам оплаты
            method_stats = {}
            for transfer in transfers:
                from_method = transfer['from_transaction'].payment_method
                to_method = transfer['to_transaction'].payment_method
                
                if from_method:
                    method_name = from_method.name
                    if method_name not in method_stats:
                        method_stats[method_name] = {'out': 0, 'in': 0}
                    method_stats[method_name]['out'] += transfer['amount']
                
                if to_method:
                    method_name = to_method.name
                    if method_name not in method_stats:
                        method_stats[method_name] = {'out': 0, 'in': 0}
                    method_stats[method_name]['in'] += transfer['amount']
            
            return {
                'total_transfers': total_transfers,
                'total_amount': total_amount,
                'total_fees': total_fees,
                'average_amount': total_amount / total_transfers if total_transfers > 0 else 0,
                'method_statistics': method_stats
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики переводов: {e}")
            return {
                'total_transfers': 0,
                'total_amount': 0,
                'total_fees': 0,
                'average_amount': 0,
                'method_statistics': {}
            }
    
    def format_transfer_display(self, transfer: Dict[str, Any]) -> str:
        """
        Форматирует перевод для отображения
        
        Args:
            transfer: Данные перевода
            
        Returns:
            str: Отформатированная строка
        """
        from_method = transfer['from_transaction'].payment_method
        to_method = transfer['to_transaction'].payment_method
        
        display = f"💸 Перевод: {transfer['amount']:,.0f} ₽\n"
        display += f"📤 От: {from_method.name if from_method else 'Неизвестно'}\n"
        display += f"📥 К: {to_method.name if to_method else 'Неизвестно'}\n"
        
        if transfer['fee'] > 0:
            display += f"💸 Комиссия: {transfer['fee']:,.0f} ₽\n"
        
        if transfer['description']:
            display += f"📝 {transfer['description']}\n"
        
        display += f"📅 {transfer['date'].strftime('%d.%m.%Y %H:%M')}"
        
        return display
