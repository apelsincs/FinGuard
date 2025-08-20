"""
Сервис расширенной аналитики
Обеспечивает прогнозирование и детальный анализ финансовых данных
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import statistics
from app.database.models import Transaction, TransactionType, Category
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    """Сервис для расширенной аналитики и прогнозирования"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_expense_forecast(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Прогнозирует расходы на основе исторических данных
        
        Args:
            user_id: ID пользователя
            days: Количество дней для прогноза
            
        Returns:
            dict: Прогноз расходов
        """
        try:
            # Получаем исторические данные за последние 90 дней
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            
            expenses = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date
                )
            ).all()
            
            if not expenses:
                return {
                    'success': False,
                    'error': 'Недостаточно данных для прогноза'
                }
            
            # Группируем по дням
            daily_expenses = {}
            for expense in expenses:
                date_key = expense.transaction_date.date()
                if date_key not in daily_expenses:
                    daily_expenses[date_key] = []
                daily_expenses[date_key].append(expense.amount)
            
            # Вычисляем средние дневные расходы
            daily_totals = [sum(amounts) for amounts in daily_expenses.values()]
            
            if not daily_totals:
                return {
                    'success': False,
                    'error': 'Недостаточно данных для прогноза'
                }
            
            # Статистика
            avg_daily = statistics.mean(daily_totals)
            median_daily = statistics.median(daily_totals)
            std_daily = statistics.stdev(daily_totals) if len(daily_totals) > 1 else 0
            
            # Прогноз
            forecast_total = avg_daily * days
            forecast_min = (avg_daily - std_daily) * days
            forecast_max = (avg_daily + std_daily) * days
            
            return {
                'success': True,
                'forecast_days': days,
                'average_daily': avg_daily,
                'median_daily': median_daily,
                'forecast_total': forecast_total,
                'forecast_min': forecast_min,
                'forecast_max': forecast_max,
                'confidence_interval': f"{forecast_min:,.0f} - {forecast_max:,.0f} ₽"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при прогнозировании расходов: {e}")
            return {
                'success': False,
                'error': f'Ошибка при прогнозировании: {str(e)}'
            }
    
    def get_spending_trends(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Анализирует тренды расходов
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            dict: Анализ трендов
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Получаем данные по неделям
            weekly_data = {}
            for i in range(days // 7 + 1):
                week_start = start_date + timedelta(days=i * 7)
                week_end = min(week_start + timedelta(days=7), end_date)
                
                expenses = self.db.query(func.sum(Transaction.amount)).filter(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.type == TransactionType.EXPENSE,
                        Transaction.transaction_date >= week_start,
                        Transaction.transaction_date < week_end
                    )
                ).scalar() or 0
                
                weekly_data[f"Неделя {i+1}"] = expenses
            
            # Анализируем тренд
            values = list(weekly_data.values())
            if len(values) < 2:
                return {
                    'success': False,
                    'error': 'Недостаточно данных для анализа тренда'
                }
            
            # Простой анализ тренда
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            
            avg_first = statistics.mean(first_half) if first_half else 0
            avg_second = statistics.mean(second_half) if second_half else 0
            
            trend_direction = "📈 Растут" if avg_second > avg_first else "📉 Снижаются" if avg_second < avg_first else "➡️ Стабильны"
            trend_percentage = ((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0
            
            return {
                'success': True,
                'weekly_data': weekly_data,
                'trend_direction': trend_direction,
                'trend_percentage': trend_percentage,
                'average_weekly': statistics.mean(values),
                'total_period': sum(values)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при анализе трендов: {e}")
            return {
                'success': False,
                'error': f'Ошибка при анализе трендов: {str(e)}'
            }
    
    def get_savings_recommendations(self, user_id: int) -> Dict[str, Any]:
        """
        Генерирует рекомендации по экономии
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Рекомендации по экономии
        """
        try:
            # Получаем данные за последние 30 дней
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            expenses = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date
                )
            ).all()
            
            if not expenses:
                return {
                    'success': False,
                    'error': 'Недостаточно данных для рекомендаций'
                }
            
            # Анализируем по категориям
            category_expenses = {}
            for expense in expenses:
                category_name = expense.category.name if expense.category else 'Без категории'
                if category_name not in category_expenses:
                    category_expenses[category_name] = []
                category_expenses[category_name].append(expense.amount)
            
            # Находим самые дорогие категории
            category_totals = {cat: sum(amounts) for cat, amounts in category_expenses.items()}
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            
            total_expenses = sum(category_totals.values())
            recommendations = []
            
            # Генерируем рекомендации
            for category, amount in sorted_categories[:3]:  # Топ-3 категории
                percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
                
                if percentage > 30:
                    recommendations.append({
                        'category': category,
                        'amount': amount,
                        'percentage': percentage,
                        'suggestion': f"Сократите расходы на {category} - это {percentage:.1f}% ваших трат"
                    })
                elif percentage > 15:
                    recommendations.append({
                        'category': category,
                        'amount': amount,
                        'percentage': percentage,
                        'suggestion': f"Рассмотрите оптимизацию расходов на {category}"
                    })
            
            # Общие рекомендации
            avg_daily = total_expenses / 30
            if avg_daily > 5000:
                recommendations.append({
                    'category': 'Общие расходы',
                    'amount': total_expenses,
                    'percentage': 100,
                    'suggestion': f"Ваши средние дневные расходы {avg_daily:,.0f} ₽ довольно высокие. Рассмотрите создание бюджета."
                })
            
            return {
                'success': True,
                'total_expenses': total_expenses,
                'average_daily': avg_daily,
                'recommendations': recommendations,
                'top_categories': sorted_categories[:5]
            }
            
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            return {
                'success': False,
                'error': f'Ошибка при генерации рекомендаций: {str(e)}'
            }
    
    def get_financial_health_score(self, user_id: int) -> Dict[str, Any]:
        """
        Вычисляет оценку финансового здоровья
        
        Args:
            user_id: ID пользователя
            
        Returns:
            dict: Оценка финансового здоровья
        """
        try:
            # Получаем данные за последние 30 дней
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            transactions = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date
                )
            ).all()
            
            if not transactions:
                return {
                    'success': False,
                    'error': 'Недостаточно данных для оценки'
                }
            
            total_income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
            total_expenses = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
            
            # Вычисляем показатели
            savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
            expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else 100
            
            # Оценка по шкале 0-100
            score = 0
            
            # Оценка по сбережениям (40 баллов)
            if savings_rate >= 20:
                score += 40
            elif savings_rate >= 10:
                score += 30
            elif savings_rate >= 0:
                score += 20
            else:
                score += 0
            
            # Оценка по соотношению доходов и расходов (30 баллов)
            if expense_ratio <= 80:
                score += 30
            elif expense_ratio <= 90:
                score += 20
            elif expense_ratio <= 100:
                score += 10
            else:
                score += 0
            
            # Оценка по разнообразию доходов (20 баллов)
            income_categories = set(t.category.name for t in transactions if t.type == TransactionType.INCOME and t.category)
            if len(income_categories) >= 3:
                score += 20
            elif len(income_categories) >= 2:
                score += 15
            elif len(income_categories) >= 1:
                score += 10
            
            # Оценка по стабильности (10 баллов)
            # Простая оценка - если есть регулярные доходы
            if total_income > 0:
                score += 10
            
            # Определяем уровень
            if score >= 80:
                level = "Отлично"
                emoji = "🟢"
            elif score >= 60:
                level = "Хорошо"
                emoji = "🟡"
            elif score >= 40:
                level = "Удовлетворительно"
                emoji = "🟠"
            else:
                level = "Требует внимания"
                emoji = "🔴"
            
            return {
                'success': True,
                'score': score,
                'level': level,
                'emoji': emoji,
                'total_income': total_income,
                'total_expenses': total_expenses,
                'savings_rate': savings_rate,
                'expense_ratio': expense_ratio,
                'income_categories': len(income_categories)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при вычислении финансового здоровья: {e}")
            return {
                'success': False,
                'error': f'Ошибка при вычислении оценки: {str(e)}'
            }
    
    def get_comparison_with_previous_period(self, user_id: int, current_days: int = 30) -> Dict[str, Any]:
        """
        Сравнивает текущий период с предыдущим
        
        Args:
            user_id: ID пользователя
            current_days: Количество дней текущего периода
            
        Returns:
            dict: Сравнение периодов
        """
        try:
            end_date = datetime.now()
            current_start = end_date - timedelta(days=current_days)
            previous_start = current_start - timedelta(days=current_days)
            
            # Текущий период
            current_transactions = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= current_start,
                    Transaction.transaction_date <= end_date
                )
            ).all()
            
            # Предыдущий период
            previous_transactions = self.db.query(Transaction).filter(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= previous_start,
                    Transaction.transaction_date < current_start
                )
            ).all()
            
            # Вычисляем показатели
            current_income = sum(t.amount for t in current_transactions if t.type == TransactionType.INCOME)
            current_expenses = sum(t.amount for t in current_transactions if t.type == TransactionType.EXPENSE)
            
            previous_income = sum(t.amount for t in previous_transactions if t.type == TransactionType.INCOME)
            previous_expenses = sum(t.amount for t in previous_transactions if t.type == TransactionType.EXPENSE)
            
            # Изменения в процентах
            income_change = ((current_income - previous_income) / previous_income * 100) if previous_income > 0 else 0
            expense_change = ((current_expenses - previous_expenses) / previous_expenses * 100) if previous_expenses > 0 else 0
            
            return {
                'success': True,
                'current_period': {
                    'income': current_income,
                    'expenses': current_expenses,
                    'balance': current_income - current_expenses
                },
                'previous_period': {
                    'income': previous_income,
                    'expenses': previous_expenses,
                    'balance': previous_income - previous_expenses
                },
                'changes': {
                    'income_change': income_change,
                    'expense_change': expense_change,
                    'income_trend': "📈" if income_change > 0 else "📉" if income_change < 0 else "➡️",
                    'expense_trend': "📈" if expense_change > 0 else "📉" if expense_change < 0 else "➡️"
                }
            }
            
        except Exception as e:
            logger.error(f"Ошибка при сравнении периодов: {e}")
            return {
                'success': False,
                'error': f'Ошибка при сравнении периодов: {str(e)}'
            }
