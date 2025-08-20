"""
Сервис резервного копирования
Создает и восстанавливает резервные копии данных пользователей
"""

import os
import json
import shutil
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models import User, Transaction, Category, Budget, FraudAlert
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BackupService:
    """Сервис для резервного копирования данных"""
    
    def __init__(self, db: Session, backup_dir: str = "backups"):
        self.db = db
        self.backup_dir = backup_dir
        
        # Создаем директорию для резервных копий
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
    
    def create_user_backup(self, user_id: int) -> dict:
        """
        Создает резервную копию данных пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Информация о созданной резервной копии
        """
        try:
            # Получаем данные пользователя
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {'success': False, 'error': 'Пользователь не найден'}
            
            # Получаем все данные пользователя
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id
            ).all()
            
            categories = self.db.query(Category).filter(
                Category.user_id == user_id
            ).all()
            
            budgets = self.db.query(Budget).filter(
                Budget.user_id == user_id
            ).all()
            
            fraud_alerts = self.db.query(FraudAlert).filter(
                FraudAlert.user_id == user_id
            ).all()
            
            # Формируем данные для резервной копии
            backup_data = {
                'metadata': {
                    'created_at': datetime.now().isoformat(),
                    'user_id': user_id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'version': '1.0'
                },
                'user': {
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone_number': user.phone_number,
                    'email': user.email,
                    'two_factor_enabled': user.two_factor_enabled,
                    'fraud_alerts_enabled': user.fraud_alerts_enabled,
                    'notifications_enabled': user.notifications_enabled,
                    'daily_reports_enabled': user.daily_reports_enabled,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'updated_at': user.updated_at.isoformat() if user.updated_at else None
                },
                'transactions': [
                    {
                        'amount': t.amount,
                        'currency': t.currency,
                        'description': t.description,
                        'type': t.type.value,
                        'status': t.status.value,
                        'merchant': t.merchant,
                        'location': t.location,
                        'transaction_date': t.transaction_date.isoformat(),
                        'is_suspicious': t.is_suspicious,
                        'fraud_score': t.fraud_score,
                        'fraud_reasons': t.fraud_reasons,
                        'created_at': t.created_at.isoformat() if t.created_at else None
                    }
                    for t in transactions
                ],
                'categories': [
                    {
                        'name': c.name,
                        'description': c.description,
                        'color': c.color,
                        'icon': c.icon,
                        'transaction_type': c.transaction_type.value,
                        'created_at': c.created_at.isoformat() if c.created_at else None
                    }
                    for c in categories
                ],
                'budgets': [
                    {
                        'name': b.name,
                        'amount': b.amount,
                        'currency': b.currency,
                        'start_date': b.start_date.isoformat() if b.start_date else None,
                        'end_date': b.end_date.isoformat() if b.end_date else None,
                        'alert_threshold': b.alert_threshold,
                        'created_at': b.created_at.isoformat() if b.created_at else None
                    }
                    for b in budgets
                ],
                'fraud_alerts': [
                    {
                        'transaction_id': a.transaction_id,
                        'alert_type': a.alert_type,
                        'severity': a.severity,
                        'description': a.description,
                        'is_read': a.is_read,
                        'created_at': a.created_at.isoformat() if a.created_at else None
                    }
                    for a in fraud_alerts
                ]
            }
            
            # Создаем имя файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"backup_user_{user_id}_{timestamp}.json"
            filepath = os.path.join(self.backup_dir, filename)
            
            # Сохраняем резервную копию
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return {
                'success': True,
                'filename': filename,
                'filepath': filepath,
                'transactions_count': len(transactions),
                'categories_count': len(categories),
                'budgets_count': len(budgets),
                'alerts_count': len(fraud_alerts)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при создании резервной копии: {e}")
            return {'success': False, 'error': str(e)}
    
    def restore_user_backup(self, filepath: str, user_id: int) -> dict:
        """
        Восстанавливает данные пользователя из резервной копии
        
        Args:
            filepath: Путь к файлу резервной копии
            user_id: ID пользователя для восстановления
            
        Returns:
            dict: Результат восстановления
        """
        try:
            # Проверяем существование файла
            if not os.path.exists(filepath):
                return {'success': False, 'error': 'Файл резервной копии не найден'}
            
            # Читаем резервную копию
            with open(filepath, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Проверяем версию и метаданные
            if backup_data.get('metadata', {}).get('user_id') != user_id:
                return {'success': False, 'error': 'Резервная копия не соответствует пользователю'}
            
            # Начинаем восстановление
            restored_count = 0
            
            # Восстанавливаем категории
            for cat_data in backup_data.get('categories', []):
                category = Category(
                    user_id=user_id,
                    name=cat_data['name'],
                    description=cat_data.get('description'),
                    color=cat_data.get('color'),
                    icon=cat_data.get('icon'),
                    transaction_type=cat_data['transaction_type']
                )
                self.db.add(category)
                restored_count += 1
            
            # Восстанавливаем бюджеты
            for budget_data in backup_data.get('budgets', []):
                budget = Budget(
                    user_id=user_id,
                    name=budget_data['name'],
                    amount=budget_data['amount'],
                    currency=budget_data['currency'],
                    start_date=datetime.fromisoformat(budget_data['start_date']) if budget_data.get('start_date') else None,
                    end_date=datetime.fromisoformat(budget_data['end_date']) if budget_data.get('end_date') else None,
                    alert_threshold=budget_data.get('alert_threshold', 0.8)
                )
                self.db.add(budget)
                restored_count += 1
            
            # Восстанавливаем транзакции
            for trans_data in backup_data.get('transactions', []):
                transaction = Transaction(
                    user_id=user_id,
                    amount=trans_data['amount'],
                    currency=trans_data['currency'],
                    description=trans_data['description'],
                    type=trans_data['type'],
                    status=trans_data['status'],
                    merchant=trans_data.get('merchant'),
                    location=trans_data.get('location'),
                    transaction_date=datetime.fromisoformat(trans_data['transaction_date']),
                    is_suspicious=trans_data.get('is_suspicious', False),
                    fraud_score=trans_data.get('fraud_score', 0.0),
                    fraud_reasons=trans_data.get('fraud_reasons')
                )
                self.db.add(transaction)
                restored_count += 1
            
            self.db.commit()
            
            return {
                'success': True,
                'restored_count': restored_count,
                'categories_restored': len(backup_data.get('categories', [])),
                'budgets_restored': len(backup_data.get('budgets', [])),
                'transactions_restored': len(backup_data.get('transactions', []))
            }
            
        except Exception as e:
            logger.error(f"Ошибка при восстановлении резервной копии: {e}")
            self.db.rollback()
            return {'success': False, 'error': str(e)}
    
    def list_backups(self, user_id: int = None) -> list:
        """
        Получает список резервных копий
        
        Args:
            user_id: ID пользователя (опционально)
            
        Returns:
            list: Список резервных копий
        """
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.json') and filename.startswith('backup_user_'):
                filepath = os.path.join(self.backup_dir, filename)
                file_stat = os.stat(filepath)
                
                # Парсим информацию из имени файла
                parts = filename.replace('.json', '').split('_')
                if len(parts) >= 4:
                    backup_user_id = int(parts[2])
                    
                    # Фильтруем по пользователю, если указан
                    if user_id is None or backup_user_id == user_id:
                        backups.append({
                            'filename': filename,
                            'filepath': filepath,
                            'user_id': backup_user_id,
                            'created_at': datetime.fromtimestamp(file_stat.st_mtime),
                            'size': file_stat.st_size
                        })
        
        # Сортируем по дате создания (новые сначала)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
    
    def delete_backup(self, filename: str) -> dict:
        """
        Удаляет резервную копию
        
        Args:
            filename: Имя файла резервной копии
            
        Returns:
            dict: Результат удаления
        """
        try:
            filepath = os.path.join(self.backup_dir, filename)
            
            if not os.path.exists(filepath):
                return {'success': False, 'error': 'Файл не найден'}
            
            os.remove(filepath)
            
            return {'success': True, 'message': 'Резервная копия удалена'}
            
        except Exception as e:
            logger.error(f"Ошибка при удалении резервной копии: {e}")
            return {'success': False, 'error': str(e)}
