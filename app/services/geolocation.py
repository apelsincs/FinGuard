"""
Сервис геолокации транзакций
Обеспечивает анализ транзакций по географическим регионам
"""

import requests
import json
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import Transaction, User
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GeolocationService:
    """Сервис для работы с геолокацией транзакций"""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
    
    def get_location_by_ip(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о местоположении по IP адресу
        
        Args:
            ip_address: IP адрес
            
        Returns:
            dict: Информация о местоположении
        """
        try:
            # Используем бесплатный сервис ipapi.co
            response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'timezone': data.get('timezone'),
                        'isp': data.get('isp')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения геолокации по IP: {e}")
            return None
    
    def detect_merchant_location(self, description: str) -> Optional[Dict[str, Any]]:
        """
        Определяет местоположение мерчанта по описанию транзакции
        
        Args:
            description: Описание транзакции
            
        Returns:
            dict: Информация о местоположении
        """
        try:
            description_lower = description.lower()
            
            # Словарь известных мерчантов и их локаций
            known_merchants = {
                'магнит': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'пятерочка': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'лента': {'city': 'Санкт-Петербург', 'country': 'Россия', 'lat': 59.9311, 'lon': 30.3609},
                'ашан': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'спар': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'перекресток': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'мкдональдс': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'kfc': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'бургер кинг': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'яндекс.такси': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'uber': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176},
                'ситимобил': {'city': 'Москва', 'country': 'Россия', 'lat': 55.7558, 'lon': 37.6176}
            }
            
            # Ищем известного мерчанта
            for merchant, location in known_merchants.items():
                if merchant in description_lower:
                    return location
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения местоположения мерчанта: {e}")
            return None
    
    def analyze_transactions_by_region(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Анализирует транзакции пользователя по регионам
        
        Args:
            user_id: ID пользователя
            days: Количество дней для анализа
            
        Returns:
            dict: Анализ по регионам
        """
        try:
            from datetime import datetime, timedelta
            
            # Вычисляем дату начала периода
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем транзакции с геолокацией
            transactions = self.db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= start_date,
                Transaction.location.isnot(None)
            ).all()
            
            if not transactions:
                return {
                    'success': False,
                    'error': 'Нет транзакций с геолокацией за указанный период'
                }
            
            # Группируем транзакции по регионам
            regions = {}
            total_amount = 0
            
            for transaction in transactions:
                location = transaction.location
                
                if location not in regions:
                    regions[location] = {
                        'count': 0,
                        'total_amount': 0,
                        'transactions': []
                    }
                
                regions[location]['count'] += 1
                regions[location]['total_amount'] += transaction.amount
                regions[location]['transactions'].append({
                    'id': transaction.id,
                    'amount': transaction.amount,
                    'description': transaction.description,
                    'date': transaction.created_at
                })
                
                total_amount += transaction.amount
            
            # Сортируем регионы по количеству транзакций
            sorted_regions = sorted(
                regions.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            # Формируем результат
            result = {
                'success': True,
                'period_days': days,
                'total_transactions': len(transactions),
                'total_amount': total_amount,
                'regions': []
            }
            
            for region, data in sorted_regions:
                result['regions'].append({
                    'name': region,
                    'transaction_count': data['count'],
                    'total_amount': data['total_amount'],
                    'percentage': (data['count'] / len(transactions)) * 100,
                    'avg_amount': data['total_amount'] / data['count']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка анализа транзакций по регионам: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def detect_suspicious_locations(
        self,
        user_id: int,
        transaction_location: str
    ) -> Dict[str, Any]:
        """
        Определяет подозрительные местоположения
        
        Args:
            user_id: ID пользователя
            transaction_location: Местоположение транзакции
            
        Returns:
            dict: Результат анализа подозрительности
        """
        try:
            # Получаем обычные местоположения пользователя
            usual_locations = self.db.query(
                Transaction.location,
                func.count(Transaction.id).label('count')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.location.isnot(None),
                Transaction.location != transaction_location
            ).group_by(Transaction.location).order_by(
                func.count(Transaction.id).desc()
            ).limit(5).all()
            
            if not usual_locations:
                return {
                    'is_suspicious': False,
                    'reason': 'Недостаточно данных для анализа',
                    'score': 0.0
                }
            
            # Проверяем, является ли местоположение необычным
            usual_location_names = [loc.location for loc in usual_locations]
            
            if transaction_location not in usual_location_names:
                # Вычисляем оценку подозрительности
                score = min(7.0, len(usual_location_names) * 1.5)
                
                return {
                    'is_suspicious': True,
                    'reason': f'Необычное местоположение: {transaction_location}',
                    'score': score,
                    'usual_locations': usual_location_names
                }
            else:
                return {
                    'is_suspicious': False,
                    'reason': 'Обычное местоположение',
                    'score': 0.0
                }
                
        except Exception as e:
            logger.error(f"Ошибка определения подозрительных местоположений: {e}")
            return {
                'is_suspicious': False,
                'reason': f'Ошибка анализа: {str(e)}',
                'score': 0.0
            }
    
    def get_location_statistics(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Получает статистику по местоположениям
        
        Args:
            user_id: ID пользователя
            days: Количество дней
            
        Returns:
            dict: Статистика по местоположениям
        """
        try:
            from datetime import datetime, timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            # Получаем статистику по городам
            city_stats = self.db.query(
                Transaction.location,
                func.count(Transaction.id).label('count'),
                func.sum(Transaction.amount).label('total_amount'),
                func.avg(Transaction.amount).label('avg_amount')
            ).filter(
                Transaction.user_id == user_id,
                Transaction.created_at >= start_date,
                Transaction.location.isnot(None)
            ).group_by(Transaction.location).order_by(
                func.count(Transaction.id).desc()
            ).all()
            
            # Получаем статистику по странам (если есть)
            country_stats = {}
            for stat in city_stats:
                # Простая логика определения страны по городу
                country = self._get_country_by_city(stat.location)
                if country not in country_stats:
                    country_stats[country] = {
                        'count': 0,
                        'total_amount': 0,
                        'cities': []
                    }
                
                country_stats[country]['count'] += stat.count
                country_stats[country]['total_amount'] += stat.total_amount
                country_stats[country]['cities'].append({
                    'name': stat.location,
                    'count': stat.count,
                    'total_amount': stat.total_amount,
                    'avg_amount': stat.avg_amount
                })
            
            return {
                'success': True,
                'period_days': days,
                'city_statistics': [
                    {
                        'city': stat.location,
                        'transaction_count': stat.count,
                        'total_amount': stat.total_amount,
                        'average_amount': stat.avg_amount
                    }
                    for stat in city_stats
                ],
                'country_statistics': [
                    {
                        'country': country,
                        'transaction_count': data['count'],
                        'total_amount': data['total_amount'],
                        'cities': data['cities']
                    }
                    for country, data in country_stats.items()
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики по местоположениям: {e}")
            return {
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }
    
    def _get_country_by_city(self, city: str) -> str:
        """
        Определяет страну по городу
        
        Args:
            city: Название города
            
        Returns:
            str: Название страны
        """
        # Простая логика для российских городов
        russian_cities = [
            'москва', 'санкт-петербург', 'новосибирск', 'екатеринбург',
            'казань', 'нижний новгород', 'челябинск', 'самара',
            'ростов-на-дону', 'уфа', 'омск', 'красноярск'
        ]
        
        if city.lower() in russian_cities:
            return 'Россия'
        
        # Можно расширить для других стран
        return 'Неизвестно'
