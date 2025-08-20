"""
Сервис уведомлений и напоминаний
Отправляет уведомления пользователям о важных событиях
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import User, Transaction, Budget, TransactionType
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_budget_alerts(self, user_id: int) -> list:
        """
        Проверяет превышение бюджета и возвращает список уведомлений
        
        Args:
            user_id: ID пользователя
            
        Returns:
            list: Список уведомлений о бюджете
        """
        notifications = []
        
        # Получаем активные бюджеты пользователя
        active_budgets = self.db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.start_date <= datetime.now(),
            Budget.end_date >= datetime.now(),
            Budget.is_active == True
        ).all()
        
        for budget in active_budgets:
            # Получаем расходы за период бюджета
            expenses = self.db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == "confirmed",
                Transaction.transaction_date >= budget.start_date,
                Transaction.transaction_date <= budget.end_date
            ).scalar() or 0
            
            # Проверяем превышение лимита
            usage_percentage = expenses / budget.amount if budget.amount > 0 else 0
            
            if usage_percentage >= 1.0:
                notifications.append({
                    'type': 'budget_exceeded',
                    'title': '🚨 Превышен бюджет!',
                    'message': f"Бюджет '{budget.name}' превышен на {((usage_percentage - 1) * 100):.1f}%",
                    'budget': budget,
                    'expenses': expenses,
                    'usage_percentage': usage_percentage
                })
            elif usage_percentage >= budget.alert_threshold:
                notifications.append({
                    'type': 'budget_warning',
                    'title': '⚠️ Приближение к лимиту бюджета',
                    'message': f"Бюджет '{budget.name}' использован на {usage_percentage * 100:.1f}%",
                    'budget': budget,
                    'expenses': expenses,
                    'usage_percentage': usage_percentage
                })
        
        return notifications
    
    def check_daily_report(self, user_id: int) -> dict:
        """
        Генерирует ежедневный отчет
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Данные ежедневного отчета
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        
        # Получаем транзакции за вчера
        transactions = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "confirmed",
            Transaction.transaction_date >= yesterday,
            Transaction.transaction_date < today
        ).all()
        
        total_income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
        total_expense = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
        balance = total_income - total_expense
        
        return {
            'date': yesterday.strftime('%d.%m.%Y'),
            'transactions_count': len(transactions),
            'total_income': total_income,
            'total_expense': total_expense,
            'balance': balance,
            'transactions': transactions
        }
    
    def check_suspicious_activity(self, user_id: int) -> list:
        """
        Проверяет подозрительную активность за последние 24 часа
        
        Args:
            user_id: ID пользователя
            
        Returns:
            list: Список подозрительных транзакций
        """
        yesterday = datetime.now() - timedelta(days=1)
        
        suspicious_transactions = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.is_suspicious == True,
            Transaction.transaction_date >= yesterday
        ).all()
        
        return suspicious_transactions
    
    def get_user_notifications(self, user_id: int) -> dict:
        """
        Получает все уведомления для пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Все уведомления пользователя
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}
        
        notifications = {
            'budget_alerts': [],
            'daily_report': None,
            'suspicious_activity': []
        }
        
        # Проверяем уведомления о бюджете
        if user.notifications_enabled:
            notifications['budget_alerts'] = self.check_budget_alerts(user_id)
        
        # Проверяем ежедневный отчет
        if user.daily_reports_enabled:
            notifications['daily_report'] = self.check_daily_report(user_id)
        
        # Проверяем подозрительную активность
        if user.fraud_alerts_enabled:
            notifications['suspicious_activity'] = self.check_suspicious_activity(user_id)
        
        return notifications
    
    def format_notifications(self, notifications: dict) -> str:
        """
        Форматирует уведомления в текст для отправки
        
        Args:
            notifications: Словарь с уведомлениями
            
        Returns:
            str: Отформатированный текст уведомлений
        """
        if not any(notifications.values()):
            return "📭 У вас нет новых уведомлений"
        
        response = "📢 Ваши уведомления:\n\n"
        
        # Уведомления о бюджете
        if notifications['budget_alerts']:
            response += "💰 Бюджет:\n"
            for alert in notifications['budget_alerts']:
                response += f"• {alert['title']}\n"
                response += f"  {alert['message']}\n\n"
        
        # Ежедневный отчет
        if notifications['daily_report']:
            report = notifications['daily_report']
            if report['transactions_count'] > 0:
                response += f"📊 Отчет за {report['date']}:\n"
                response += f"• Транзакций: {report['transactions_count']}\n"
                response += f"• Доходы: +{report['total_income']:,.0f} ₽\n"
                response += f"• Расходы: -{report['total_expense']:,.0f} ₽\n"
                response += f"• Баланс: {report['balance']:+,.0f} ₽\n\n"
        
        # Подозрительная активность
        if notifications['suspicious_activity']:
            response += "🔒 Безопасность:\n"
            for transaction in notifications['suspicious_activity']:
                response += f"• Подозрительная транзакция: {transaction.amount} ₽ - {transaction.description}\n"
                if transaction.fraud_reasons:
                    response += f"  Причины: {transaction.fraud_reasons}\n"
            response += "\n"
        
        return response.strip()
