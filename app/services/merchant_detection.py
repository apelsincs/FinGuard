"""
Сервис автоматического определения мерчантов
Обеспечивает распознавание магазинов и мерчантов по описанию транзакций
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Transaction, User
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MerchantDetectionService:
    """Сервис для автоматического определения мерчантов"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Словарь известных мерчантов с категориями
        self.known_merchants = {
            # Продуктовые магазины
            'продукты': {
                'name': 'Продуктовый магазин',
                'category': 'продукты',
                'confidence': 0.9,
                'keywords': ['продукты', 'еда', 'магазин']
            },
            'магнит': {
                'name': 'Магнит',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['магнит', 'магнит-косметик']
            },
            'пятерочка': {
                'name': 'Пятёрочка',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['пятерочка', '5ка', '5-ка']
            },
            'лента': {
                'name': 'Лента',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['лента', 'лента-гипермаркет']
            },
            'ашан': {
                'name': 'Ашан',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['ашан', 'auchan', 'ашан-гипермаркет']
            },
            'спар': {
                'name': 'Спар',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['спар', 'spar']
            },
            'перекресток': {
                'name': 'Перекрёсток',
                'category': 'продукты',
                'confidence': 0.95,
                'keywords': ['перекресток', 'перекрёсток']
            },
            
            # Рестораны и кафе
            'ресторан': {
                'name': 'Ресторан',
                'category': 'кафе',
                'confidence': 0.8,
                'keywords': ['ресторан', 'ресторанчик']
            },
            'кафе': {
                'name': 'Кафе',
                'category': 'кафе',
                'confidence': 0.8,
                'keywords': ['кафе', 'кафетерий']
            },
            'столовая': {
                'name': 'Столовая',
                'category': 'кафе',
                'confidence': 0.9,
                'keywords': ['столовая', 'столовая-']
            },
            'мкдональдс': {
                'name': 'Макдональдс',
                'category': 'кафе',
                'confidence': 0.95,
                'keywords': ['мкдональдс', 'макдональдс', 'mcdonalds', 'мак']
            },
            'kfc': {
                'name': 'KFC',
                'category': 'кафе',
                'confidence': 0.95,
                'keywords': ['kfc', 'кфс']
            },
            'бургер кинг': {
                'name': 'Бургер Кинг',
                'category': 'кафе',
                'confidence': 0.95,
                'keywords': ['бургер кинг', 'burger king', 'бк']
            },
            'суши': {
                'name': 'Суши-бар',
                'category': 'кафе',
                'confidence': 0.8,
                'keywords': ['суши', 'суши-бар', 'sushi']
            },
            'пицца': {
                'name': 'Пиццерия',
                'category': 'кафе',
                'confidence': 0.8,
                'keywords': ['пицца', 'пиццерия', 'pizza']
            },
            
            # Транспорт
            'такси': {
                'name': 'Такси',
                'category': 'транспорт',
                'confidence': 0.9,
                'keywords': ['такси', 'taxi']
            },
            'метро': {
                'name': 'Метро',
                'category': 'транспорт',
                'confidence': 0.95,
                'keywords': ['метро', 'подземка']
            },
            'автобус': {
                'name': 'Автобус',
                'category': 'транспорт',
                'confidence': 0.9,
                'keywords': ['автобус', 'автобус-']
            },
            'троллейбус': {
                'name': 'Троллейбус',
                'category': 'транспорт',
                'confidence': 0.9,
                'keywords': ['троллейбус', 'троллейбус-']
            },
            'трамвай': {
                'name': 'Трамвай',
                'category': 'транспорт',
                'confidence': 0.9,
                'keywords': ['трамвай', 'трамвай-']
            },
            'яндекс.такси': {
                'name': 'Яндекс.Такси',
                'category': 'транспорт',
                'confidence': 0.95,
                'keywords': ['яндекс.такси', 'яндекс такси', 'yandex.taxi']
            },
            'uber': {
                'name': 'Uber',
                'category': 'транспорт',
                'confidence': 0.95,
                'keywords': ['uber', 'убер']
            },
            'ситимобил': {
                'name': 'Ситимобил',
                'category': 'транспорт',
                'confidence': 0.95,
                'keywords': ['ситимобил', 'citymobil', 'сити']
            },
            
            # Аптеки и здоровье
            'аптека': {
                'name': 'Аптека',
                'category': 'здоровье',
                'confidence': 0.9,
                'keywords': ['аптека', 'аптечный', 'pharmacy']
            },
            'врач': {
                'name': 'Медицинские услуги',
                'category': 'здоровье',
                'confidence': 0.8,
                'keywords': ['врач', 'доктор', 'медицинский', 'клиника']
            },
            'больница': {
                'name': 'Больница',
                'category': 'здоровье',
                'confidence': 0.9,
                'keywords': ['больница', 'госпиталь', 'hospital']
            },
            
            # Одежда и обувь
            'одежда': {
                'name': 'Магазин одежды',
                'category': 'одежда',
                'confidence': 0.8,
                'keywords': ['одежда', 'одежный', 'clothing']
            },
            'обувь': {
                'name': 'Магазин обуви',
                'category': 'одежда',
                'confidence': 0.8,
                'keywords': ['обувь', 'обувной', 'shoes']
            },
            'h&m': {
                'name': 'H&M',
                'category': 'одежда',
                'confidence': 0.95,
                'keywords': ['h&m', 'h&m-', 'hm']
            },
            'zara': {
                'name': 'Zara',
                'category': 'одежда',
                'confidence': 0.95,
                'keywords': ['zara', 'зара']
            },
            'uniqlo': {
                'name': 'Uniqlo',
                'category': 'одежда',
                'confidence': 0.95,
                'keywords': ['uniqlo', 'уникло']
            },
            'масс': {
                'name': 'Масс-маркет',
                'category': 'одежда',
                'confidence': 0.8,
                'keywords': ['масс', 'масс-маркет']
            },
            
            # Связь и интернет
            'телефон': {
                'name': 'Телефонные услуги',
                'category': 'связь',
                'confidence': 0.8,
                'keywords': ['телефон', 'телефонный', 'phone']
            },
            'интернет': {
                'name': 'Интернет-услуги',
                'category': 'связь',
                'confidence': 0.8,
                'keywords': ['интернет', 'internet', 'online']
            },
            'мтс': {
                'name': 'МТС',
                'category': 'связь',
                'confidence': 0.95,
                'keywords': ['мтс', 'mts']
            },
            'билайн': {
                'name': 'Билайн',
                'category': 'билайн',
                'confidence': 0.95,
                'keywords': ['билайн', 'beeline']
            },
            'мегафон': {
                'name': 'МегаФон',
                'category': 'связь',
                'confidence': 0.95,
                'keywords': ['мегафон', 'megafon']
            },
            'tele2': {
                'name': 'Tele2',
                'category': 'связь',
                'confidence': 0.95,
                'keywords': ['tele2', 'теле2']
            },
            
            # Топливо
            'азс': {
                'name': 'АЗС',
                'category': 'топливо',
                'confidence': 0.9,
                'keywords': ['азс', 'заправка', 'gas station']
            },
            'лк': {
                'name': 'Лукойл',
                'category': 'топливо',
                'confidence': 0.95,
                'keywords': ['лк', 'лукойл', 'lukoil']
            },
            'топливо': {
                'name': 'Топливо',
                'category': 'топливо',
                'confidence': 0.8,
                'keywords': ['топливо', 'бензин', 'дизель', 'газ']
            },
            
            # Банковские услуги
            'комиссия': {
                'name': 'Банковская комиссия',
                'category': 'банковские услуги',
                'confidence': 0.9,
                'keywords': ['комиссия', 'commission', 'fee']
            },
            'обслуживание': {
                'name': 'Банковское обслуживание',
                'category': 'банковские услуги',
                'confidence': 0.8,
                'keywords': ['обслуживание', 'service', 'maintenance']
            },
            'банк': {
                'name': 'Банк',
                'category': 'банковские услуги',
                'confidence': 0.7,
                'keywords': ['банк', 'bank', 'банковский']
            },
            
            # Доходы
            'зарплата': {
                'name': 'Зарплата',
                'category': 'доходы',
                'confidence': 0.9,
                'keywords': ['зарплата', 'salary', 'payroll']
            },
            'доход': {
                'name': 'Доход',
                'category': 'доходы',
                'confidence': 0.8,
                'keywords': ['доход', 'income', 'revenue']
            },
            'поступление': {
                'name': 'Поступление средств',
                'category': 'доходы',
                'confidence': 0.8,
                'keywords': ['поступление', 'receipt', 'incoming']
            }
        }
    
    def detect_merchant(self, description: str) -> Optional[Dict[str, Any]]:
        """
        Автоматически определяет мерчанта по описанию транзакции
        
        Args:
            description: Описание транзакции
            
        Returns:
            dict: Информация о мерчанте или None
        """
        try:
            description_lower = description.lower()
            best_match = None
            best_score = 0
            
            # Ищем лучшее совпадение
            for merchant_id, merchant_info in self.known_merchants.items():
                score = 0
                
                # Проверяем точное совпадение
                if merchant_id in description_lower:
                    score += merchant_info['confidence'] * 2
                
                # Проверяем ключевые слова
                for keyword in merchant_info['keywords']:
                    if keyword in description_lower:
                        score += merchant_info['confidence'] * 0.5
                
                # Проверяем частичные совпадения
                if any(word in description_lower for word in merchant_id.split()):
                    score += merchant_info['confidence'] * 0.3
                
                # Обновляем лучшее совпадение
                if score > best_score:
                    best_score = score
                    best_match = {
                        'id': merchant_id,
                        'name': merchant_info['name'],
                        'category': merchant_info['category'],
                        'confidence': score,
                        'original_description': description
                    }
            
            # Возвращаем мерчанта только если уверенность достаточно высокая
            if best_match and best_match['confidence'] >= 0.5:
                logger.info(f"Определен мерчант: {best_match['name']} (уверенность: {best_match['confidence']:.2f})")
                return best_match
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения мерчанта: {e}")
            return None
    
    def get_merchant_statistics(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает статистику по мерчантам
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            dict: Статистика по мерчантам
        """
        try:
            from datetime import datetime, timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем транзакции с мерчантами
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= start_date,
                Transaction.merchant.isnot(None)
            ).all()
            
            if not transactions:
                return {
                    'success': False,
                    'error': 'Нет транзакций с мерчантами за указанный период'
                }
            
            # Группируем по мерчантам
            merchants = {}
            total_amount = 0
            
            for transaction in transactions:
                merchant = transaction.merchant
                
                if merchant not in merchants:
                    merchants[merchant] = {
                        'count': 0,
                        'total_amount': 0,
                        'categories': set(),
                        'transactions': []
                    }
                
                merchants[merchant]['count'] += 1
                merchants[merchant]['total_amount'] += transaction.amount
                
                if transaction.category_id:
                    # Получаем название категории
                    category = self.db.query(Category).filter(Category.id == transaction.category_id).first()
                    if category:
                        merchants[merchant]['categories'].add(category.name)
                
                merchants[merchant]['transactions'].append({
                    'id': transaction.id,
                    'amount': transaction.amount,
                    'description': transaction.description,
                    'date': transaction.created_at
                })
                
                total_amount += transaction.amount
            
            # Сортируем мерчантов по количеству транзакций
            sorted_merchants = sorted(
                merchants.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            # Формируем результат
            result = {
                'success': True,
                'period_days': days,
                'total_transactions': len(transactions),
                'total_amount': total_amount,
                'unique_merchants': len(merchants),
                'merchants': []
            }
            
            for merchant_name, data in sorted_merchants:
                result['merchants'].append({
                    'name': merchant_name,
                    'transaction_count': data['count'],
                    'total_amount': data['total_amount'],
                    'average_amount': data['total_amount'] / data['count'],
                    'percentage': (data['count'] / len(transactions)) * 100,
                    'categories': list(data['categories'])
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики по мерчантам: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def suggest_merchant_name(self, description: str) -> List[str]:
        """
        Предлагает возможные названия мерчантов
        
        Args:
            description: Описание транзакции
            
        Returns:
            list: Список предложений
        """
        try:
            suggestions = []
            description_lower = description.lower()
            
            # Ищем похожие мерчанты
            for merchant_id, merchant_info in self.known_merchants.items():
                # Проверяем частичные совпадения
                if any(word in description_lower for word in merchant_id.split()):
                    suggestions.append(merchant_info['name'])
                
                # Проверяем ключевые слова
                for keyword in merchant_info['keywords']:
                    if keyword in description_lower:
                        suggestions.append(merchant_info['name'])
                        break
            
            # Убираем дубликаты и сортируем
            unique_suggestions = list(set(suggestions))
            unique_suggestions.sort()
            
            return unique_suggestions[:5]  # Возвращаем максимум 5 предложений
            
        except Exception as e:
            logger.error(f"Ошибка предложения названий мерчантов: {e}")
            return []
    
    def update_merchant_info(
        self,
        transaction_id: int,
        merchant_name: str,
        category: str = None
    ) -> Dict[str, Any]:
        """
        Обновляет информацию о мерчанте в транзакции
        
        Args:
            transaction_id: ID транзакции
            merchant_name: Название мерчанта
            category: Категория мерчанта
            
        Returns:
            dict: Результат обновления
        """
        try:
            # Получаем транзакцию
            transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
            
            if not transaction:
                return {
                    'success': False,
                    'error': 'Транзакция не найдена'
                }
            
            # Обновляем мерчанта
            transaction.merchant = merchant_name
            
            # Если указана категория, ищем её в базе
            if category:
                category_obj = self.db.query(Category).filter(
                    Category.name.ilike(f"%{category}%"),
                    Category.user_id == transaction.user_id
                ).first()
                
                if category_obj:
                    transaction.category_id = category_obj.id
            
            self.db.commit()
            
            logger.info(f"Обновлен мерчант для транзакции {transaction_id}: {merchant_name}")
            
            return {
                'success': True,
                'merchant': merchant_name,
                'category': category
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка обновления мерчанта: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
