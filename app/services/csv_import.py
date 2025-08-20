"""
Сервис импорта данных из CSV-файлов банков
Поддерживает форматы Т-Банка и Альфа-Банка
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.database.models import Transaction, TransactionType, TransactionStatus, User, Category
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CSVImportService:
    """Сервис для импорта данных из CSV-файлов банков"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_bank_format(self, csv_content: str) -> str:
        """
        Автоматически определяет формат банка по содержимому CSV
        
        Args:
            csv_content: Содержимое CSV файла
            
        Returns:
            str: 'alfabank', 'tbank', или 'unknown'
        """
        try:
            # Читаем первые несколько строк для анализа
            lines = csv_content.strip().split('\n')[:5]
            
            if not lines:
                return 'unknown'
            
            # Анализируем заголовки
            headers = [line.strip().lower() for line in lines if line.strip()]
            
            # Проверяем характерные признаки Альфа-Банка
            alfabank_keywords = ['дата', 'операции', 'сумма', 'валюта', 'описание', 'операции', 'mcc']
            alfabank_score = sum(1 for keyword in alfabank_keywords if any(keyword in header for header in headers))
            
            # Проверяем характерные признаки Т-Банка
            tbank_keywords = ['дата', 'время', 'сумма', 'описание', 'тип', 'операции', 'баланс']
            tbank_score = sum(1 for keyword in tbank_keywords if any(keyword in header for header in headers))
            
            if alfabank_score >= 4:
                return 'alfabank'
            elif tbank_score >= 4:
                return 'tbank'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Ошибка при определении формата банка: {e}")
            return 'unknown'
    
    def parse_alfabank_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """
        Парсит CSV файл Альфа-Банка
        
        Args:
            csv_content: Содержимое CSV файла
            
        Returns:
            list: Список транзакций
        """
        transactions = []
        
        try:
            # Создаем StringIO объект для чтения CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file, delimiter=';')
            
            for row in reader:
                try:
                    # Парсим дату (формат может быть разным)
                    date_str = row.get('Дата операции', '').strip()
                    if not date_str:
                        continue
                    
                    # Пробуем разные форматы даты
                    transaction_date = None
                    date_formats = [
                        '%d.%m.%Y %H:%M:%S',
                        '%d.%m.%Y %H:%M',
                        '%d.%m.%Y',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            transaction_date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not transaction_date:
                        logger.warning(f"Не удалось распарсить дату: {date_str}")
                        continue
                    
                    # Парсим сумму
                    amount_str = row.get('Сумма', '0').strip()
                    try:
                        amount = float(amount_str.replace(',', '.'))
                    except ValueError:
                        logger.warning(f"Не удалось распарсить сумму: {amount_str}")
                        continue
                    
                    # Определяем тип транзакции
                    if amount > 0:
                        transaction_type = TransactionType.INCOME
                    else:
                        transaction_type = TransactionType.EXPENSE
                        amount = abs(amount)
                    
                    # Получаем описание
                    description = row.get('Описание операции', '').strip()
                    if not description:
                        description = 'Импорт из Альфа-Банка'
                    
                    # Получаем валюту
                    currency = row.get('Валюта', 'RUB').strip()
                    
                    # Получаем номер карты/счета
                    card_number = row.get('Номер карты/счета', '').strip()
                    
                    # Получаем MCC код для категоризации
                    mcc_code = row.get('MCC код', '').strip()
                    
                    transaction_data = {
                        'date': transaction_date,
                        'amount': amount,
                        'type': transaction_type,
                        'description': description,
                        'currency': currency,
                        'card_number': card_number,
                        'mcc_code': mcc_code,
                        'bank': 'alfabank'
                    }
                    
                    transactions.append(transaction_data)
                    
                except Exception as e:
                    logger.error(f"Ошибка при парсинге строки Альфа-Банка: {e}, строка: {row}")
                    continue
            
            logger.info(f"Успешно распарсено {len(transactions)} транзакций из Альфа-Банка")
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге CSV Альфа-Банка: {e}")
        
        return transactions
    
    def parse_tbank_csv(self, csv_content: str) -> List[Dict[str, Any]]:
        """
        Парсит CSV файл Т-Банка
        
        Args:
            csv_content: Содержимое CSV файла
            
        Returns:
            list: Список транзакций
        """
        transactions = []
        
        try:
            # Создаем StringIO объект для чтения CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file, delimiter=';')
            
            for row in reader:
                try:
                    # Парсим дату и время
                    date_str = row.get('Дата', '').strip()
                    time_str = row.get('Время', '').strip()
                    
                    if not date_str:
                        continue
                    
                    # Объединяем дату и время
                    datetime_str = f"{date_str} {time_str}" if time_str else date_str
                    
                    # Пробуем разные форматы даты
                    transaction_date = None
                    date_formats = [
                        '%d.%m.%Y %H:%M:%S',
                        '%d.%m.%Y %H:%M',
                        '%d.%m.%Y',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            transaction_date = datetime.strptime(datetime_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not transaction_date:
                        logger.warning(f"Не удалось распарсить дату: {datetime_str}")
                        continue
                    
                    # Парсим сумму
                    amount_str = row.get('Сумма', '0').strip()
                    try:
                        amount = float(amount_str.replace(',', '.'))
                    except ValueError:
                        logger.warning(f"Не удалось распарсить сумму: {amount_str}")
                        continue
                    
                    # Определяем тип транзакции
                    transaction_type_str = row.get('Тип операции', '').strip().lower()
                    if 'приход' in transaction_type_str or 'доход' in transaction_type_str:
                        transaction_type = TransactionType.INCOME
                    elif 'расход' in transaction_type_str or 'списание' in transaction_type_str:
                        transaction_type = TransactionType.EXPENSE
                        amount = abs(amount)
                    else:
                        # Определяем по знаку суммы
                        if amount > 0:
                            transaction_type = TransactionType.INCOME
                        else:
                            transaction_type = TransactionType.EXPENSE
                            amount = abs(amount)
                    
                    # Получаем описание
                    description = row.get('Описание', '').strip()
                    if not description:
                        description = 'Импорт из Т-Банка'
                    
                    # Получаем валюту (обычно RUB)
                    currency = row.get('Валюта', 'RUB').strip()
                    
                    # Получаем баланс после операции
                    balance_str = row.get('Баланс', '').strip()
                    balance = None
                    if balance_str:
                        try:
                            balance = float(balance_str.replace(',', '.'))
                        except ValueError:
                            pass
                    
                    # Получаем номер карты
                    card_number = row.get('Номер карты', '').strip()
                    
                    transaction_data = {
                        'date': transaction_date,
                        'amount': amount,
                        'type': transaction_type,
                        'description': description,
                        'currency': currency,
                        'balance': balance,
                        'card_number': card_number,
                        'bank': 'tbank'
                    }
                    
                    transactions.append(transaction_data)
                    
                except Exception as e:
                    logger.error(f"Ошибка при парсинге строки Т-Банка: {e}, строка: {row}")
                    continue
            
            logger.info(f"Успешно распарсено {len(transactions)} транзакций из Т-Банка")
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге CSV Т-Банка: {e}")
        
        return transactions
    
    def categorize_transaction(self, description: str, mcc_code: str = None, bank: str = None) -> Optional[int]:
        """
        Автоматически категоризирует транзакцию на основе описания и MCC кода
        
        Args:
            description: Описание транзакции
            mcc_code: MCC код (для Альфа-Банка)
            bank: Название банка
            
        Returns:
            int: ID категории или None
        """
        try:
            description_lower = description.lower()
            
            # Словарь ключевых слов для категорий
            category_keywords = {
                'продукты': ['продукты', 'еда', 'магнит', 'пятерочка', 'лента', 'ашан', 'спар', 'перекресток'],
                'транспорт': ['такси', 'метро', 'автобус', 'троллейбус', 'трамвай', 'uber', 'яндекс.такси', 'ситимобил'],
                'кафе': ['кафе', 'ресторан', 'столовая', 'макдональдс', 'kfc', 'бургер кинг', 'суши', 'пицца'],
                'развлечения': ['кино', 'театр', 'концерт', 'музей', 'выставка', 'игры', 'развлечения'],
                'здоровье': ['аптека', 'врач', 'больница', 'клиника', 'медицина', 'лекарства'],
                'одежда': ['одежда', 'обувь', 'магазин', 'h&m', 'zara', 'uniqlo', 'масс'],
                'связь': ['телефон', 'интернет', 'связь', 'мтс', 'билайн', 'мегафон', 'tele2'],
                'топливо': ['азс', 'лк', 'топливо', 'бензин', 'дизель', 'газ'],
                'банковские услуги': ['комиссия', 'обслуживание', 'банк', 'карта', 'счет'],
                'доходы': ['зарплата', 'доход', 'поступление', 'перевод', 'возврат']
            }
            
            # Проверяем по ключевым словам
            for category_name, keywords in category_keywords.items():
                if any(keyword in description_lower for keyword in keywords):
                    # Ищем категорию в базе
                    category = self.db.query(Category).filter(
                        Category.name.ilike(f"%{category_name}%")
                    ).first()
                    
                    if category:
                        return category.id
            
            # Если есть MCC код, используем его для категоризации
            if mcc_code and bank == 'alfabank':
                mcc_category = self._get_category_by_mcc(mcc_code)
                if mcc_category:
                    return mcc_category
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при категоризации транзакции: {e}")
            return None
    
    def _get_category_by_mcc(self, mcc_code: str) -> Optional[int]:
        """
        Получает категорию по MCC коду
        
        Args:
            mcc_code: MCC код
            
        Returns:
            int: ID категории или None
        """
        try:
            # Словарь MCC кодов для основных категорий
            mcc_categories = {
                '5411': 'продукты',      # Продуктовые магазины
                '5812': 'кафе',          # Рестораны
                '5813': 'кафе',          # Бары
                '5814': 'кафе',          # Фаст-фуд
                '5541': 'топливо',       # АЗС
                '5542': 'топливо',       # АЗС
                '4121': 'транспорт',     # Такси
                '4111': 'транспорт',     # Транспорт
                '4131': 'транспорт',     # Автобусы
                '5912': 'аптека',        # Аптеки
                '5311': 'одежда',        # Универмаги
                '5691': 'одежда',        # Одежда
                '5999': 'развлечения',   # Различные магазины
                '4899': 'связь',         # Кабельное ТВ
                '4814': 'связь',         # Телекоммуникации
            }
            
            if mcc_code in mcc_categories:
                category_name = mcc_categories[mcc_code]
                category = self.db.query(Category).filter(
                    Category.name.ilike(f"%{category_name}%")
                ).first()
                
                if category:
                    return category.id
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении категории по MCC: {e}")
            return None
    
    def import_transactions(self, user_id: int, csv_content: str, bank_name: str = None) -> Dict[str, Any]:
        """
        Импортирует транзакции из CSV файла
        
        Args:
            user_id: ID пользователя
            csv_content: Содержимое CSV файла
            bank_name: Название банка (если известно)
            
        Returns:
            dict: Результат импорта
        """
        try:
            # Определяем формат банка
            if not bank_name:
                bank_name = self.detect_bank_format(csv_content)
            
            if bank_name == 'unknown':
                return {
                    'success': False,
                    'error': 'Не удалось определить формат банка. Проверьте структуру CSV файла.'
                }
            
            # Парсим CSV в зависимости от банка
            if bank_name == 'alfabank':
                transactions_data = self.parse_alfabank_csv(csv_content)
            elif bank_name == 'tbank':
                transactions_data = self.parse_tbank_csv(csv_content)
            else:
                return {
                    'success': False,
                    'error': f'Неподдерживаемый формат банка: {bank_name}'
                }
            
            if not transactions_data:
                return {
                    'success': False,
                    'error': 'Не удалось извлечь транзакции из CSV файла'
                }
            
            # Импортируем транзакции в базу данных
            imported_count = 0
            skipped_count = 0
            errors_count = 0
            
            for transaction_data in transactions_data:
                try:
                    # Проверяем, не дублируется ли транзакция
                    existing = self.db.query(Transaction).filter(
                        Transaction.user_id == user_id,
                        Transaction.amount == transaction_data['amount'],
                        Transaction.description == transaction_data['description'],
                        Transaction.transaction_date == transaction_data['date']
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Категоризируем транзакцию
                    category_id = self.categorize_transaction(
                        transaction_data['description'],
                        transaction_data.get('mcc_code'),
                        transaction_data.get('bank')
                    )
                    
                    # Создаем транзакцию
                    transaction = Transaction(
                        user_id=user_id,
                        category_id=category_id,
                        amount=transaction_data['amount'],
                        currency=transaction_data['currency'],
                        description=transaction_data['description'],
                        type=transaction_data['type'],
                        status=TransactionStatus.CONFIRMED,
                        transaction_date=transaction_data['date']
                    )
                    
                    self.db.add(transaction)
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка при импорте транзакции: {e}")
                    errors_count += 1
                    continue
            
            # Сохраняем изменения
            self.db.commit()
            
            logger.info(f"Импортировано {imported_count} транзакций для пользователя {user_id}")
            
            return {
                'success': True,
                'imported': imported_count,
                'skipped': skipped_count,
                'errors': errors_count,
                'total': len(transactions_data),
                'bank': bank_name
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка при импорте транзакций: {e}")
            return {
                'success': False,
                'error': f'Ошибка при импорте: {str(e)}'
            }
    
    def get_import_template(self, bank_name: str) -> str:
        """
        Возвращает шаблон CSV файла для указанного банка
        
        Args:
            bank_name: Название банка
            
        Returns:
            str: Шаблон CSV
        """
        if bank_name == 'alfabank':
            return """Дата операции;Сумма;Валюта;Описание операции;MCC код;Номер карты/счета
01.01.2025 10:30:00;-1500;RUB;Покупка в магазине Продукты;5411;1234****5678
01.01.2025 15:45:00;50000;RUB;Зарплата;0000;1234****5678"""
        
        elif bank_name == 'tbank':
            return """Дата;Время;Сумма;Тип операции;Описание;Баланс;Номер карты
01.01.2025;10:30:00;-1500;Расход;Покупка в магазине;48500;1234****5678
01.01.2025;15:45:00;50000;Приход;Зарплата;98500;1234****5678"""
        
        else:
            return "Неизвестный формат банка"
