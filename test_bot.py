#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности FinGuard
Проверяет работу базы данных и основных функций
"""

import os
import sys

# Добавляем текущую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import SessionLocal, check_db_connection, create_sample_data
from app.database.models import User, Transaction, Category, TransactionType, TransactionStatus
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)


def test_database():
    """Тестирование базы данных"""
    print("🧪 Тестирование базы данных...")
    
    # Проверяем подключение
    if not check_db_connection():
        print("❌ Ошибка подключения к базе данных")
        return False
    
    print("✅ Подключение к базе данных успешно")
    
    # Создаем демо-данные
    create_sample_data()
    
    # Тестируем запросы
    db = SessionLocal()
    try:
        # Проверяем пользователей
        users = db.query(User).all()
        print(f"👥 Найдено пользователей: {len(users)}")
        
        # Проверяем категории
        categories = db.query(Category).all()
        print(f"📂 Найдено категорий: {len(categories)}")
        
        # Проверяем транзакции
        transactions = db.query(Transaction).all()
        print(f"💰 Найдено транзакций: {len(transactions)}")
        
        # Создаем тестовую транзакцию
        if users:
            test_transaction = Transaction(
                user_id=users[0].id,
                amount=1000.0,
                description="Тестовая транзакция",
                type=TransactionType.INCOME,
                status=TransactionStatus.CONFIRMED,
                transaction_date=datetime.now()
            )
            db.add(test_transaction)
            db.commit()
            print("✅ Тестовая транзакция создана")
            
            # Проверяем обновленное количество
            transactions = db.query(Transaction).all()
            print(f"💰 Обновленное количество транзакций: {len(transactions)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        return False
    finally:
        db.close()


def test_handlers():
    """Тестирование обработчиков (без бота)"""
    print("\n🧪 Тестирование обработчиков...")
    
    try:
        from app.bot.handlers import get_or_create_user
        
        # Тестируем создание пользователя
        user = get_or_create_user(
            telegram_id=999999999,
            username="test_user",
            first_name="Тест",
            last_name="Пользователь"
        )
        print(f"✅ Тестовый пользователь создан: {user.first_name} {user.last_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании обработчиков: {e}")
        return False


def main():
    """Главная функция тестирования"""
    print("🚀 Тестирование FinGuard")
    print("=" * 50)
    
    # Тестируем базу данных
    db_success = test_database()
    
    # Тестируем обработчики
    handlers_success = test_handlers()
    
    print("\n" + "=" * 50)
    if db_success and handlers_success:
        print("🎉 Все тесты прошли успешно!")
        print("\n📋 Что работает:")
        print("✅ Подключение к SQLite базе данных")
        print("✅ Создание таблиц")
        print("✅ Добавление демо-данных")
        print("✅ Создание пользователей")
        print("✅ Добавление транзакций")
        print("✅ Обработчики команд")
        
        print("\n🚀 Для запуска бота:")
        print("1. Получите токен у @BotFather в Telegram")
        print("2. Замените DEMO_TOKEN_PLACEHOLDER в файле .env")
        print("3. Запустите: PYTHONPATH=. python app/main.py")
        
    else:
        print("❌ Некоторые тесты не прошли")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
