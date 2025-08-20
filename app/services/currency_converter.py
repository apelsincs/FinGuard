"""
Сервис конвертации валют
Обеспечивает многовалютные операции и конвертацию
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.database.models import Transaction, User
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CurrencyConverterService:
    """Сервис для работы с валютами и конвертацией"""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        
        # Поддерживаемые валюты
        self.supported_currencies = {
            'RUB': {'name': 'Российский рубль', 'symbol': '₽'},
            'USD': {'name': 'Доллар США', 'symbol': '$'},
            'EUR': {'name': 'Евро', 'symbol': '€'},
            'GBP': {'name': 'Фунт стерлингов', 'symbol': '£'},
            'CNY': {'name': 'Китайский юань', 'symbol': '¥'},
            'JPY': {'name': 'Японская иена', 'symbol': '¥'},
            'CHF': {'name': 'Швейцарский франк', 'symbol': 'CHF'},
            'CAD': {'name': 'Канадский доллар', 'symbol': 'C$'},
            'AUD': {'name': 'Австралийский доллар', 'symbol': 'A$'},
            'TRY': {'name': 'Турецкая лира', 'symbol': '₺'}
        }
        
        # Кэш курсов валют
        self.rates_cache = {}
        self.cache_expiry = None
    
    def get_exchange_rates(self, base_currency: str = 'RUB') -> Dict[str, Any]:
        """
        Получает актуальные курсы валют
        
        Args:
            base_currency: Базовая валюта
            
        Returns:
            dict: Курсы валют
        """
        try:
            # Проверяем кэш
            if (self.rates_cache and self.cache_expiry and 
                datetime.now() < self.cache_expiry):
                return self.rates_cache
            
            # Используем бесплатный API exchangerate-api.com
            url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                rates = {
                    'base_currency': data['base'],
                    'date': data['date'],
                    'rates': data['rates']
                }
                
                # Кэшируем на 1 час
                self.rates_cache = rates
                self.cache_expiry = datetime.now() + timedelta(hours=1)
                
                logger.info(f"Получены курсы валют для {base_currency}")
                return rates
            else:
                logger.error(f"Ошибка получения курсов валют: {response.status_code}")
                return self._get_fallback_rates(base_currency)
                
        except Exception as e:
            logger.error(f"Ошибка получения курсов валют: {e}")
            return self._get_fallback_rates(base_currency)
    
    def _get_fallback_rates(self, base_currency: str) -> Dict[str, Any]:
        """
        Возвращает резервные курсы валют (если API недоступен)
        
        Args:
            base_currency: Базовая валюта
            
        Returns:
            dict: Резервные курсы
        """
        # Примерные курсы (можно обновлять вручную)
        fallback_rates = {
            'RUB': {
                'USD': 0.011,  # 1 RUB = 0.011 USD
                'EUR': 0.010,  # 1 RUB = 0.010 EUR
                'GBP': 0.008,  # 1 RUB = 0.008 GBP
                'CNY': 0.079,  # 1 RUB = 0.079 CNY
                'JPY': 1.65,   # 1 RUB = 1.65 JPY
                'CHF': 0.009,  # 1 RUB = 0.009 CHF
                'CAD': 0.015,  # 1 RUB = 0.015 CAD
                'AUD': 0.017,  # 1 RUB = 0.017 AUD
                'TRY': 0.35    # 1 RUB = 0.35 TRY
            },
            'USD': {
                'RUB': 90.0,   # 1 USD = 90 RUB
                'EUR': 0.92,   # 1 USD = 0.92 EUR
                'GBP': 0.79,   # 1 USD = 0.79 GBP
                'CNY': 7.2,    # 1 USD = 7.2 CNY
                'JPY': 150.0,  # 1 USD = 150 JPY
                'CHF': 0.85,   # 1 USD = 0.85 CHF
                'CAD': 1.35,   # 1 USD = 1.35 CAD
                'AUD': 1.52,   # 1 USD = 1.52 AUD
                'TRY': 31.5    # 1 USD = 31.5 TRY
            }
        }
        
        if base_currency in fallback_rates:
            return {
                'base_currency': base_currency,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'rates': fallback_rates[base_currency],
                'fallback': True
            }
        
        # Если базовая валюта не поддерживается, возвращаем RUB
        return {
            'base_currency': 'RUB',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'rates': fallback_rates['RUB'],
            'fallback': True
        }
    
    def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str
    ) -> Dict[str, Any]:
        """
        Конвертирует сумму из одной валюты в другую
        
        Args:
            amount: Сумма для конвертации
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            
        Returns:
            dict: Результат конвертации
        """
        try:
            # Проверяем валюты
            if from_currency not in self.supported_currencies:
                return {
                    'success': False,
                    'error': f'Неподдерживаемая исходная валюта: {from_currency}'
                }
            
            if to_currency not in self.supported_currencies:
                return {
                    'success': False,
                    'error': f'Неподдерживаемая целевая валюта: {to_currency}'
                }
            
            # Если валюты одинаковые, возвращаем исходную сумму
            if from_currency == to_currency:
                return {
                    'success': True,
                    'original_amount': amount,
                    'converted_amount': amount,
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'rate': 1.0,
                    'no_conversion': True
                }
            
            # Получаем курсы валют
            rates_data = self.get_exchange_rates(from_currency)
            
            if 'rates' not in rates_data:
                return {
                    'success': False,
                    'error': 'Не удалось получить курсы валют'
                }
            
            rates = rates_data['rates']
            
            if to_currency not in rates:
                return {
                    'success': False,
                    'error': f'Курс для {to_currency} не найден'
                }
            
            # Выполняем конвертацию
            rate = rates[to_currency]
            converted_amount = amount * rate
            
            # Округляем до 2 знаков после запятой
            converted_amount = round(converted_amount, 2)
            
            logger.info(f"Конвертация: {amount} {from_currency} = {converted_amount} {to_currency}")
            
            return {
                'success': True,
                'original_amount': amount,
                'converted_amount': converted_amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'rate': rate,
                'exchange_date': rates_data.get('date'),
                'fallback': rates_data.get('fallback', False)
            }
            
        except Exception as e:
            logger.error(f"Ошибка конвертации валют: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def get_multi_currency_balance(
        self,
        user_id: int,
        target_currency: str = 'RUB'
    ) -> Dict[str, Any]:
        """
        Получает баланс пользователя в нескольких валютах
        
        Args:
            user_id: ID пользователя
            target_currency: Валюта для конвертации
            
        Returns:
            dict: Баланс по валютам
        """
        try:
            # Получаем все транзакции пользователя
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id
            ).all()
            
            if not transactions:
                return {
                    'success': False,
                    'error': 'Нет транзакций для расчета баланса'
                }
            
            # Группируем по валютам
            currency_balances = {}
            
            for transaction in transactions:
                currency = transaction.currency or 'RUB'
                
                if currency not in currency_balances:
                    currency_balances[currency] = {
                        'income': 0.0,
                        'expense': 0.0,
                        'balance': 0.0
                    }
                
                if transaction.type.value == 'INCOME':
                    currency_balances[currency]['income'] += transaction.amount
                else:
                    currency_balances[currency]['expense'] += transaction.amount
                
                currency_balances[currency]['balance'] = (
                    currency_balances[currency]['income'] - 
                    currency_balances[currency]['expense']
                )
            
            # Конвертируем все валюты в целевую
            total_balance = 0.0
            converted_balances = []
            
            for currency, balance_data in currency_balances.items():
                if currency == target_currency:
                    converted_amount = balance_data['balance']
                else:
                    conversion = self.convert_currency(
                        balance_data['balance'],
                        currency,
                        target_currency
                    )
                    
                    if conversion['success']:
                        converted_amount = conversion['converted_amount']
                    else:
                        converted_amount = 0.0
                        logger.warning(f"Не удалось конвертировать {currency} в {target_currency}")
                
                total_balance += converted_amount
                
                converted_balances.append({
                    'currency': currency,
                    'currency_name': self.supported_currencies.get(currency, {}).get('name', currency),
                    'currency_symbol': self.supported_currencies.get(currency, {}).get('symbol', ''),
                    'original_balance': balance_data['balance'],
                    'income': balance_data['income'],
                    'expense': balance_data['expense'],
                    'converted_balance': converted_amount,
                    'conversion_rate': self._get_conversion_rate(currency, target_currency)
                })
            
            return {
                'success': True,
                'user_id': user_id,
                'target_currency': target_currency,
                'total_balance': round(total_balance, 2),
                'currencies': converted_balances,
                'currency_count': len(currency_balances)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения многовалютного баланса: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def _get_conversion_rate(self, from_currency: str, to_currency: str) -> float:
        """
        Получает курс конвертации между валютами
        
        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            
        Returns:
            float: Курс конвертации
        """
        try:
            if from_currency == to_currency:
                return 1.0
            
            rates_data = self.get_exchange_rates(from_currency)
            rates = rates_data.get('rates', {})
            
            return rates.get(to_currency, 0.0)
            
        except Exception as e:
            logger.error(f"Ошибка получения курса конвертации: {e}")
            return 0.0
    
    def get_currency_statistics(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает статистику по валютам
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            dict: Статистика по валютам
        """
        try:
            from datetime import datetime, timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем транзакции за период
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= start_date
            ).all()
            
            if not transactions:
                return {
                    'success': False,
                    'error': 'Нет транзакций за указанный период'
                }
            
            # Группируем по валютам
            currency_stats = {}
            
            for transaction in transactions:
                currency = transaction.currency or 'RUB'
                
                if currency not in currency_stats:
                    currency_stats[currency] = {
                        'count': 0,
                        'total_income': 0.0,
                        'total_expense': 0.0,
                        'avg_amount': 0.0,
                        'transactions': []
                    }
                
                currency_stats[currency]['count'] += 1
                
                if transaction.type.value == 'INCOME':
                    currency_stats[currency]['total_income'] += transaction.amount
                else:
                    currency_stats[currency]['total_expense'] += transaction.amount
                
                currency_stats[currency]['transactions'].append({
                    'id': transaction.id,
                    'amount': transaction.amount,
                    'type': transaction.type.value,
                    'description': transaction.description,
                    'date': transaction.created_at
                })
            
            # Вычисляем средние значения
            for currency, stats in currency_stats.items():
                total_amount = stats['total_income'] + stats['total_expense']
                stats['avg_amount'] = total_amount / stats['count'] if stats['count'] > 0 else 0.0
                stats['balance'] = stats['total_income'] - stats['total_expense']
            
            # Сортируем по количеству транзакций
            sorted_stats = sorted(
                currency_stats.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            return {
                'success': True,
                'period_days': days,
                'total_transactions': len(transactions),
                'currencies': [
                    {
                        'currency': currency,
                        'currency_name': self.supported_currencies.get(currency, {}).get('name', currency),
                        'currency_symbol': self.supported_currencies.get(currency, {}).get('symbol', ''),
                        'transaction_count': stats['count'],
                        'total_income': stats['total_income'],
                        'total_expense': stats['total_expense'],
                        'balance': stats['balance'],
                        'average_amount': stats['avg_amount']
                    }
                    for currency, stats in sorted_stats
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики по валютам: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def get_supported_currencies(self) -> Dict[str, Any]:
        """
        Возвращает список поддерживаемых валют
        
        Returns:
            dict: Список валют
        """
        return {
            'success': True,
            'currencies': self.supported_currencies,
            'count': len(self.supported_currencies)
        }
