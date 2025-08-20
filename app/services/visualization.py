"""
Сервис визуализации данных
Создает графики и диаграммы для финансовой аналитики
"""

import os
import io
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Transaction, Category, TransactionType
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Настройка стилей для графиков
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")


class VisualizationService:
    """Сервис для создания графиков и диаграмм"""
    
    def __init__(self, db: Session):
        self.db = db
        self.charts_dir = "charts"
        
        # Создаем директорию для графиков
        if not os.path.exists(self.charts_dir):
            os.makedirs(self.charts_dir)
    
    def create_expense_chart(self, user_id: int, days: int = 30) -> str:
        """
        Создает график расходов за период
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            str: Путь к файлу графика
        """
        try:
            # Получаем данные
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).all()
            
            if not transactions:
                return None
            
            # Создаем DataFrame
            data = []
            for t in transactions:
                data.append({
                    'date': t.transaction_date.date(),
                    'amount': t.amount,
                    'description': t.description,
                    'category': t.category.name if t.category else 'Без категории'
                })
            
            df = pd.DataFrame(data)
            
            # Группируем по дате
            daily_expenses = df.groupby('date')['amount'].sum().reset_index()
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            plt.plot(daily_expenses['date'], daily_expenses['amount'], 
                    marker='o', linewidth=2, markersize=6)
            
            plt.title(f'Расходы за последние {days} дней', fontsize=16, fontweight='bold')
            plt.xlabel('Дата', fontsize=12)
            plt.ylabel('Сумма (₽)', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Форматируем оси
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
            plt.xticks(rotation=45)
            
            # Добавляем общую сумму
            total_expenses = daily_expenses['amount'].sum()
            plt.figtext(0.02, 0.02, f'Общая сумма: {total_expenses:,.0f} ₽', 
                       fontsize=10, style='italic')
            
            plt.tight_layout()
            
            # Сохраняем график
            filename = f"expenses_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика расходов: {e}")
            return None
    
    def create_income_chart(self, user_id: int, days: int = 30) -> str:
        """
        Создает график доходов за период
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            str: Путь к файлу графика
        """
        try:
            # Получаем данные
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).all()
            
            if not transactions:
                return None
            
            # Создаем DataFrame
            data = []
            for t in transactions:
                data.append({
                    'date': t.transaction_date.date(),
                    'amount': t.amount,
                    'description': t.description,
                    'category': t.category.name if t.category else 'Без категории'
                })
            
            df = pd.DataFrame(data)
            
            # Группируем по дате
            daily_income = df.groupby('date')['amount'].sum().reset_index()
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            plt.plot(daily_income['date'], daily_income['amount'], 
                    marker='o', linewidth=2, markersize=6, color='green')
            
            plt.title(f'Доходы за последние {days} дней', fontsize=16, fontweight='bold')
            plt.xlabel('Дата', fontsize=12)
            plt.ylabel('Сумма (₽)', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Форматируем оси
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
            plt.xticks(rotation=45)
            
            # Добавляем общую сумму
            total_income = daily_income['amount'].sum()
            plt.figtext(0.02, 0.02, f'Общая сумма: {total_income:,.0f} ₽', 
                       fontsize=10, style='italic')
            
            plt.tight_layout()
            
            # Сохраняем график
            filename = f"income_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика доходов: {e}")
            return None
    
    def create_category_pie_chart(self, user_id: int, days: int = 30) -> str:
        """
        Создает круговую диаграмму по категориям
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            str: Путь к файлу графика
        """
        try:
            # Получаем данные
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).all()
            
            if not transactions:
                return None
            
            # Создаем DataFrame
            data = []
            for t in transactions:
                category_name = t.category.name if t.category else 'Без категории'
                data.append({
                    'category': category_name,
                    'amount': t.amount,
                    'type': t.type.value
                })
            
            df = pd.DataFrame(data)
            
            # Создаем график
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
            
            # Расходы по категориям
            expense_data = df[df['type'] == 'expense'].groupby('category')['amount'].sum()
            if not expense_data.empty:
                ax1.pie(expense_data.values, labels=expense_data.index, autopct='%1.1f%%', startangle=90)
                ax1.set_title('Расходы по категориям', fontsize=14, fontweight='bold')
            
            # Доходы по категориям
            income_data = df[df['type'] == 'income'].groupby('category')['amount'].sum()
            if not income_data.empty:
                ax2.pie(income_data.values, labels=income_data.index, autopct='%1.1f%%', startangle=90)
                ax2.set_title('Доходы по категориям', fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            # Сохраняем график
            filename = f"categories_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании диаграммы категорий: {e}")
            return None
    
    def create_balance_chart(self, user_id: int, days: int = 30) -> str:
        """
        Создает график баланса за период
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            str: Путь к файлу графика
        """
        try:
            # Получаем данные
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date
            ).order_by(Transaction.transaction_date).all()
            
            if not transactions:
                return None
            
            # Создаем DataFrame
            data = []
            balance = 0
            for t in transactions:
                if t.type == TransactionType.INCOME:
                    balance += t.amount
                else:
                    balance -= t.amount
                
                data.append({
                    'date': t.transaction_date.date(),
                    'balance': balance,
                    'amount': t.amount,
                    'type': t.type.value
                })
            
            df = pd.DataFrame(data)
            
            # Создаем график
            plt.figure(figsize=(12, 6))
            
            # График баланса
            plt.plot(df['date'], df['balance'], marker='o', linewidth=2, markersize=4)
            
            # Добавляем линию нуля
            plt.axhline(y=0, color='red', linestyle='--', alpha=0.5, label='Нулевой баланс')
            
            plt.title(f'Баланс за последние {days} дней', fontsize=16, fontweight='bold')
            plt.xlabel('Дата', fontsize=12)
            plt.ylabel('Баланс (₽)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # Форматируем оси
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
            plt.xticks(rotation=45)
            
            # Добавляем текущий баланс
            current_balance = df['balance'].iloc[-1] if not df.empty else 0
            plt.figtext(0.02, 0.02, f'Текущий баланс: {current_balance:+,.0f} ₽', 
                       fontsize=10, style='italic')
            
            plt.tight_layout()
            
            # Сохраняем график
            filename = f"balance_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика баланса: {e}")
            return None
    
    def create_budget_chart(self, user_id: int) -> str:
        """
        Создает график использования бюджета
        
        Args:
            user_id: ID пользователя
            
        Returns:
            str: Путь к файлу графика
        """
        try:
            from app.database.models import Budget
            
            # Получаем активные бюджеты
            budgets = self.db.query(Budget).filter(
                Budget.user_id == user_id,
                Budget.is_active == True,
                Budget.start_date <= datetime.now(),
                Budget.end_date >= datetime.now()
            ).all()
            
            if not budgets:
                return None
            
            # Создаем график
            fig, axes = plt.subplots(len(budgets), 1, figsize=(12, 4 * len(budgets)))
            if len(budgets) == 1:
                axes = [axes]
            
            for i, budget in enumerate(budgets):
                # Получаем расходы за период бюджета
                expenses = self.db.query(func.sum(Transaction.amount)).filter(
                    Transaction.user_id == user_id,
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.transaction_date >= budget.start_date,
                    Transaction.transaction_date <= budget.end_date
                ).scalar() or 0
                
                usage_percentage = (expenses / budget.amount) * 100
                
                # Создаем столбчатую диаграмму
                categories = ['Использовано', 'Осталось']
                values = [expenses, max(0, budget.amount - expenses)]
                colors = ['#ff6b6b' if usage_percentage > 80 else '#4ecdc4', '#95a5a6']
                
                axes[i].bar(categories, values, color=colors)
                axes[i].set_title(f'{budget.name} ({budget.amount:,.0f} ₽)', fontsize=14, fontweight='bold')
                axes[i].set_ylabel('Сумма (₽)', fontsize=12)
                
                # Добавляем подписи значений
                for j, v in enumerate(values):
                    axes[i].text(j, v + max(values) * 0.01, f'{v:,.0f} ₽', 
                               ha='center', va='bottom', fontweight='bold')
                
                # Добавляем процент использования
                axes[i].text(0.5, 0.95, f'Использовано: {usage_percentage:.1f}%', 
                           transform=axes[i].transAxes, ha='center', va='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            plt.tight_layout()
            
            # Сохраняем график
            filename = f"budget_user_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.charts_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Ошибка при создании графика бюджета: {e}")
            return None
    
    def cleanup_old_charts(self, max_age_hours: int = 24):
        """
        Удаляет старые графики
        
        Args:
            max_age_hours: Максимальный возраст файлов в часах
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            for filename in os.listdir(self.charts_dir):
                if filename.endswith('.png'):
                    filepath = os.path.join(self.charts_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    if file_time < cutoff_time:
                        os.remove(filepath)
                        logger.info(f"Удален старый график: {filename}")
                        
        except Exception as e:
            logger.error(f"Ошибка при очистке старых графиков: {e}")
