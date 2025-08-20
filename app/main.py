"""
Главный файл приложения FinGuard
Инициализирует Telegram бота и запускает приложение
"""

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from app.config import get_settings, validate_environment
from app.database.database import init_db, check_db_connection, create_sample_data
from app.utils.logger import get_logger
from app.bot.handlers import (
    start_command,
    help_command,
    add_transaction,
    view_transactions,
    set_budget,
    view_budget,
    fraud_alerts,
    settings_command,
    statistics_command
)

logger = get_logger(__name__)


async def main() -> None:
    """
    Главная функция приложения
    Инициализирует и запускает Telegram бота
    """
    logger.info("🚀 Запуск FinGuard Telegram Bot...")
    
    # Проверяем настройки окружения
    if not validate_environment():
        logger.error("❌ Ошибка в настройках окружения. Завершение работы.")
        return
    
    # Получаем настройки
    settings = get_settings()
    
    # Проверяем подключение к базе данных
    if not check_db_connection():
        logger.error("❌ Ошибка подключения к базе данных. Завершение работы.")
        return
    
    # Инициализируем базу данных
    try:
        init_db()
        # Создаем демо-данные
        create_sample_data()
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        return
    
    # Создаем бота и диспетчер
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    
    # Регистрируем обработчики
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(settings_command, Command("settings"))
    dp.message.register(add_transaction, Command("add"))
    dp.message.register(view_transactions, Command("transactions"))
    dp.message.register(view_budget, Command("budget"))
    dp.message.register(set_budget, Command("set_budget"))
    dp.message.register(fraud_alerts, Command("alerts"))
    dp.message.register(statistics_command, Command("stats"))
    
    # Обработчик всех текстовых сообщений (для добавления транзакций)
    dp.message.register(add_transaction)
    
    logger.info("✅ FinGuard Bot успешно инициализирован")
    
    # Запускаем бота
    try:
        logger.info("🔄 Запуск в режиме polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 FinGuard Bot остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
