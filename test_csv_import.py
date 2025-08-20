#!/usr/bin/env python3
"""
Тест импорта CSV файлов банков
"""

import sys
import os
sys.path.append('.')

from app.database.database import SessionLocal, init_db
from app.services.csv_import import CSVImportService
from app.database.models import User, Transaction
from app.utils.logger import get_logger

logger = get_logger(__name__)


def test_csv_import():
    """Тестирует импорт CSV файлов"""
    print("🧪 Тестирование импорта CSV файлов")
    print("=" * 50)
    
    # Инициализируем базу данных
    init_db()
    
    # Создаем сессию
    db = SessionLocal()
    
    try:
        # Получаем первого пользователя
        user = db.query(User).first()
        if not user:
            print("❌ Пользователи не найдены")
            return
        
        print(f"👤 Тестируем для пользователя: {user.first_name}")
        
        # Создаем сервис импорта
        import_service = CSVImportService(db)
        
        # Тестируем определение формата банка
        print("\n🔍 Тестирование определения формата банка...")
        
        # Читаем тестовые файлы
        with open('test_alfabank.csv', 'r', encoding='utf-8') as f:
            alfabank_content = f.read()
        
        with open('test_tbank.csv', 'r', encoding='utf-8') as f:
            tbank_content = f.read()
        
        # Определяем формат
        alfabank_format = import_service.detect_bank_format(alfabank_content)
        tbank_format = import_service.detect_bank_format(tbank_content)
        
        print(f"✅ Альфа-Банк: {alfabank_format}")
        print(f"✅ Т-Банк: {tbank_format}")
        
        # Тестируем парсинг Альфа-Банка
        print("\n📊 Тестирование парсинга Альфа-Банка...")
        alfabank_transactions = import_service.parse_alfabank_csv(alfabank_content)
        print(f"✅ Распарсено транзакций: {len(alfabank_transactions)}")
        
        for i, trans in enumerate(alfabank_transactions[:3], 1):
            print(f"  {i}. {trans['date'].strftime('%d.%m.%Y')} - {trans['amount']} ₽ - {trans['description']}")
        
        # Тестируем парсинг Т-Банка
        print("\n📊 Тестирование парсинга Т-Банка...")
        tbank_transactions = import_service.parse_tbank_csv(tbank_content)
        print(f"✅ Распарсено транзакций: {len(tbank_transactions)}")
        
        for i, trans in enumerate(tbank_transactions[:3], 1):
            print(f"  {i}. {trans['date'].strftime('%d.%m.%Y')} - {trans['amount']} ₽ - {trans['description']}")
        
        # Тестируем категоризацию
        print("\n🏷️ Тестирование категоризации...")
        test_descriptions = [
            "Покупка в магазине Продукты",
            "Такси",
            "Ресторан",
            "Аптека",
            "Зарплата"
        ]
        
        for desc in test_descriptions:
            category_id = import_service.categorize_transaction(desc)
            if category_id:
                print(f"✅ '{desc}' -> категория ID: {category_id}")
            else:
                print(f"❌ '{desc}' -> категория не найдена")
        
        # Тестируем полный импорт (без сохранения в БД)
        print("\n📥 Тестирование полного импорта...")
        
        # Создаем временный сервис для тестирования
        test_result = import_service.import_transactions(user.id, alfabank_content, 'alfabank')
        
        if test_result['success']:
            print(f"✅ Импорт успешен!")
            print(f"   • Импортировано: {test_result['imported']}")
            print(f"   • Пропущено: {test_result['skipped']}")
            print(f"   • Ошибок: {test_result['errors']}")
            print(f"   • Банк: {test_result['bank']}")
        else:
            print(f"❌ Ошибка импорта: {test_result['error']}")
        
        print("\n🎉 Тестирование завершено!")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        logger.error(f"Ошибка при тестировании: {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    test_csv_import()
