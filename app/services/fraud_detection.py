"""
Сервис обнаружения мошенничества
Анализирует транзакции на предмет подозрительной активности
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Transaction, TransactionType, FraudAlert
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FraudDetectionService:
    """Сервис для обнаружения мошенничества"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze_transaction(self, transaction: Transaction) -> dict:
        """
        Анализирует транзакцию на предмет подозрительности
        
        Args:
            transaction: Транзакция для анализа
            
        Returns:
            dict: Результат анализа с оценкой подозрительности и причинами
        """
        fraud_score = 0.0
        reasons = []
        
        # Проверяем только расходы
        if transaction.type != TransactionType.EXPENSE:
            return {
                'is_suspicious': False,
                'fraud_score': 0.0,
                'reasons': []
            }
        
        # 1. Проверка на крупные суммы
        if transaction.amount > 10000:
            fraud_score += 0.3
            reasons.append("Крупная сумма (>10,000 ₽)")
        
        if transaction.amount > 50000:
            fraud_score += 0.2
            reasons.append("Очень крупная сумма (>50,000 ₽)")
        
        # 2. Проверка на необычное время
        hour = transaction.transaction_date.hour
        if hour < 6 or hour > 23:
            fraud_score += 0.2
            reasons.append("Необычное время транзакции")
        
        # 3. Проверка на частые транзакции
        recent_transactions = self.db.query(Transaction).filter(
            Transaction.user_id == transaction.user_id,
            Transaction.created_at >= datetime.now() - timedelta(hours=1)
        ).count()
        
        if recent_transactions > 5:
            fraud_score += 0.3
            reasons.append("Много транзакций за последний час")
        
        # 4. Проверка на подозрительные описания
        suspicious_keywords = [
            'крипто', 'биткоин', 'эфир', 'crypto', 'bitcoin', 'ethereum',
            'казино', 'casino', 'ставки', 'bet', 'gambling',
            'лотерея', 'lottery', 'приз', 'prize',
            'инвестиции', 'investment', 'трейдинг', 'trading'
        ]
        
        description_lower = transaction.description.lower()
        for keyword in suspicious_keywords:
            if keyword in description_lower:
                fraud_score += 0.4
                reasons.append(f"Подозрительное описание: {keyword}")
                break
        
        # 5. Проверка на превышение средних расходов пользователя
        avg_expense = self.db.query(func.avg(Transaction.amount)).filter(
            Transaction.user_id == transaction.user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.created_at >= datetime.now() - timedelta(days=30)
        ).scalar() or 0
        
        if avg_expense > 0 and transaction.amount > avg_expense * 3:
            fraud_score += 0.3
            reasons.append("Сумма значительно превышает средние расходы")
        
        # 6. Проверка на повторяющиеся транзакции
        similar_transactions = self.db.query(Transaction).filter(
            Transaction.user_id == transaction.user_id,
            Transaction.amount == transaction.amount,
            Transaction.description == transaction.description,
            Transaction.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if similar_transactions > 2:
            fraud_score += 0.2
            reasons.append("Повторяющиеся транзакции")
        
        # Ограничиваем оценку до 1.0
        fraud_score = min(fraud_score, 1.0)
        
        return {
            'is_suspicious': fraud_score > 0.5,
            'fraud_score': fraud_score,
            'reasons': reasons
        }
    
    def create_fraud_alert(self, transaction: Transaction, analysis: dict) -> FraudAlert:
        """
        Создает уведомление о мошенничестве
        
        Args:
            transaction: Подозрительная транзакция
            analysis: Результат анализа
            
        Returns:
            FraudAlert: Созданное уведомление
        """
        if analysis['fraud_score'] > 0.7:
            severity = "HIGH"
        elif analysis['fraud_score'] > 0.5:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        
        alert = FraudAlert(
            user_id=transaction.user_id,
            transaction_id=transaction.id,
            alert_type="SUSPICIOUS_TRANSACTION",
            severity=severity,
            message=f"Подозрительная транзакция: {transaction.amount} ₽ - {transaction.description}. Причины: {', '.join(analysis['reasons'])}"
        )
        
        self.db.add(alert)
        self.db.commit()
        
        logger.warning(f"Создано уведомление о мошенничестве: {alert.message}")
        return alert
    
    def get_user_alerts(self, user_id: int, unread_only: bool = True) -> list:
        """
        Получает уведомления пользователя
        
        Args:
            user_id: ID пользователя
            unread_only: Только непрочитанные уведомления
            
        Returns:
            list: Список уведомлений
        """
        query = self.db.query(FraudAlert).filter(FraudAlert.user_id == user_id)
        
        if unread_only:
            query = query.filter(FraudAlert.is_read == False)
        
        return query.order_by(FraudAlert.created_at.desc()).all()
    
    def mark_alert_as_read(self, alert_id: int) -> bool:
        """
        Отмечает уведомление как прочитанное
        
        Args:
            alert_id: ID уведомления
            
        Returns:
            bool: Успешность операции
        """
        try:
            alert = self.db.query(FraudAlert).filter(FraudAlert.id == alert_id).first()
            if alert:
                alert.is_read = True
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при отметке уведомления как прочитанного: {e}")
            return False
