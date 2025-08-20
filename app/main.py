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
    statistics_command,
    delete_transaction_command,
    balance_command,
    categories_command,
    add_category_command,
    delete_category_command,
    notifications_command,
    backup_command,
    chart_expenses_command,
    chart_income_command,
    chart_categories_command,
    chart_balance_command,
    chart_budget_command,
    export_excel_command,
    export_csv_command,
    export_pdf_command,
    monthly_report_command,
    payment_methods_command,
    add_payment_method_command,
    delete_payment_method_command,
    set_default_payment_command,
    transfer_command,
    transfers_command,
    enable_2fa_command,
    disable_2fa_command,
    verify_2fa_command,
    backup_codes_command,
    two_factor_status_command,
    confirm_transaction_command,
    reject_transaction_command,
    pending_transactions_command,
    transaction_status_summary_command,
    forecast_command,
    trends_command,
    recommendations_command,
    financial_health_command,
    compare_periods_command,
    import_csv_command,
    csv_template_command,
    import_status_command,
    handle_document
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
    
    # Регистрируем обработчики команд
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(settings_command, Command("settings"))
    dp.message.register(add_transaction, Command("add"))
    dp.message.register(view_transactions, Command("transactions"))
    dp.message.register(view_budget, Command("budget"))
    dp.message.register(set_budget, Command("set_budget"))
    dp.message.register(fraud_alerts, Command("alerts"))
    dp.message.register(statistics_command, Command("stats"))
    dp.message.register(delete_transaction_command, Command("delete"))
    dp.message.register(balance_command, Command("balance"))
    dp.message.register(categories_command, Command("categories"))
    dp.message.register(add_category_command, Command("add_category"))
    dp.message.register(delete_category_command, Command("delete_category"))
    dp.message.register(notifications_command, Command("notifications"))
    dp.message.register(backup_command, Command("backup"))
    dp.message.register(chart_expenses_command, Command("chart_expenses"))
    dp.message.register(chart_income_command, Command("chart_income"))
    dp.message.register(chart_categories_command, Command("chart_categories"))
    dp.message.register(chart_balance_command, Command("chart_balance"))
    dp.message.register(chart_budget_command, Command("chart_budget"))
    dp.message.register(export_excel_command, Command("export_excel"))
    dp.message.register(export_csv_command, Command("export_csv"))
    dp.message.register(export_pdf_command, Command("export_pdf"))
    dp.message.register(monthly_report_command, Command("monthly_report"))
    dp.message.register(payment_methods_command, Command("payment_methods"))
    dp.message.register(add_payment_method_command, Command("add_payment_method"))
    dp.message.register(delete_payment_method_command, Command("delete_payment_method"))
    dp.message.register(set_default_payment_command, Command("set_default_payment"))
    dp.message.register(transfer_command, Command("transfer"))
    dp.message.register(transfers_command, Command("transfers"))
    dp.message.register(enable_2fa_command, Command("enable_2fa"))
    dp.message.register(disable_2fa_command, Command("disable_2fa"))
    dp.message.register(verify_2fa_command, Command("verify_2fa"))
    dp.message.register(backup_codes_command, Command("backup_codes"))
    dp.message.register(two_factor_status_command, Command("2fa_status"))
    dp.message.register(confirm_transaction_command, Command("confirm_transaction"))
    dp.message.register(reject_transaction_command, Command("reject_transaction"))
    dp.message.register(pending_transactions_command, Command("pending_transactions"))
    dp.message.register(transaction_status_summary_command, Command("transaction_status_summary"))
    dp.message.register(forecast_command, Command("forecast"))
    dp.message.register(trends_command, Command("trends"))
    dp.message.register(recommendations_command, Command("recommendations"))
    dp.message.register(financial_health_command, Command("financial_health"))
    dp.message.register(compare_periods_command, Command("compare_periods"))
    dp.message.register(import_csv_command, Command("import_csv"))
    dp.message.register(csv_template_command, Command("csv_template"))
    dp.message.register(import_status_command, Command("import_status"))
    
    # Обработчик документов (CSV файлов)
    dp.message.register(handle_document, lambda m: m.document is not None)
    
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
