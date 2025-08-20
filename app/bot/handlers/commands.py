"""
Обработчики команд Telegram бота
Базовые функции для управления финансами
"""

from aiogram import types
from aiogram.filters import Command
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import re
import os

from app.database.database import SessionLocal
from app.database.models import User, Transaction, Category, TransactionType, TransactionStatus, Budget, FraudAlert
from app.services.fraud_detection import FraudDetectionService
from app.services.notifications import NotificationService
from app.services.backup import BackupService
from app.services.visualization import VisualizationService
from app.services.reports import ReportService
from app.services.payment_methods import PaymentMethodService
from app.services.transfers import TransferService
from app.services.two_factor import TwoFactorService
from app.services.transaction_status import TransactionStatusService
from app.services.analytics import AnalyticsService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    """Получить или создать пользователя"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Создан новый пользователь: {telegram_id}")
        return user
    finally:
        db.close()


async def start_command(message: types.Message) -> None:
    """Обработчик команды /start"""
    user = message.from_user
    
    # Получаем или создаем пользователя в БД
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    welcome_text = f"""
🤖 Добро пожаловать в FinGuard!

Привет, {user.first_name}! Я помогу тебе управлять личными финансами.

📋 Основные команды:
/add - Добавить транзакцию
/transactions - Посмотреть транзакции
/budget - Управление бюджетом
/set_budget - Установить бюджет
/stats - Статистика
/alerts - Уведомления о безопасности
/settings - Настройки
/help - Справка

💡 Просто напиши сумму и описание, например:
"500 еда" или "-1000 такси"
    """
    
    await message.answer(welcome_text)


async def help_command(message: types.Message) -> None:
    """Обработчик команды /help"""
    help_text = """
📚 Справка по командам FinGuard:

💰 Добавление транзакций:
• /add - Добавить транзакцию через диалог
• Или просто напиши: "500 еда" или "-1000 такси"

📊 Просмотр данных:
• /transactions - Посмотреть последние транзакции
• /budget - Просмотр бюджета
• /set_budget - Установить бюджет
• /stats - Статистика за 30 дней

💳 Платежные методы:
• /payment_methods - Управление способами оплаты
• /add_payment_method - Добавить способ оплаты
• /delete_payment_method - Удалить способ оплаты
• /set_default_payment - Установить по умолчанию

💸 Переводы:
• /transfer - Перевод между счетами
• /transfers - История переводов

🔐 Двухфакторная аутентификация:
• /enable_2fa - Включить 2FA
• /disable_2fa - Отключить 2FA
• /verify_2fa - Проверить код
• /backup_codes - Резервные коды
• /2fa_status - Статус 2FA

📊 Управление транзакциями:
• /confirm_transaction - Подтвердить транзакцию
• /reject_transaction - Отклонить транзакцию
• /pending_transactions - Ожидающие транзакции
• /transaction_status_summary - Сводка по статусам

📈 Графики и визуализация:
• /chart_expenses - График расходов
• /chart_income - График доходов
• /chart_categories - Диаграмма по категориям
• /chart_balance - График баланса
• /chart_budget - График бюджета

📄 Экспорт отчетов:
• /export_excel - Экспорт в Excel
• /export_csv - Экспорт в CSV
• /export_pdf - Экспорт в PDF
• /monthly_report - Месячный отчет

🔮 Аналитика и прогнозы:
• /forecast - Прогноз расходов
• /trends - Анализ трендов
• /recommendations - Рекомендации по экономии
• /financial_health - Оценка финансового здоровья
• /compare_periods - Сравнение периодов

🔒 Безопасность:
• /alerts - Уведомления о подозрительных операциях

⚙️ Настройки:
• /settings - Настройки бота

💡 Примеры использования:
• "1500 зарплата" - добавить доход
• "-500 продукты" - добавить расход
• "-2000 аренда квартиры" - крупный расход
• /set_budget 50000 месяц - установить месячный бюджет
• /settings notifications off - отключить уведомления
• /add_payment_method карта Сбербанк card 1234567890123456 123
• /transfer 1 2 5000 перевод на карту
• /enable_2fa - включить двухфакторную аутентификацию
    """
    
    await message.answer(help_text)


async def add_transaction(message: types.Message) -> None:
    """Обработчик добавления транзакций"""
    user = message.from_user
    text = message.text.strip()
    
    # Пропускаем команды
    if text.startswith('/'):
        return
    
    # Валидация формата
    if not text or len(text) < 2:
        await message.answer("❌ Пожалуйста, укажите сумму и описание.\nПример: '500 еда' или '-1000 такси'")
        return
    
    # Парсим сумму, описание и категорию
    try:
        # Формат: "сумма описание #категория" или "сумма описание"
        if '#' in text:
            # Есть категория
            parts = text.split('#', 1)
            main_part = parts[0].strip()
            category_name = parts[1].strip()
            
            # Парсим основную часть
            match = re.match(r'^(-?\d+(?:\.\d+)?)\s+(.+)$', main_part)
            if not match:
                await message.answer(
                    "❌ Неверный формат. Используйте: 'сумма описание #категория'\n"
                    "Примеры:\n"
                    "• 500 еда #продукты\n"
                    "• -1000 такси #транспорт\n"
                    "• 1500.50 зарплата #доходы"
                )
                return
            
            amount = float(match.group(1))
            description = match.group(2).strip()
        else:
            # Нет категории
            match = re.match(r'^(-?\d+(?:\.\d+)?)\s+(.+)$', text)
            if not match:
                await message.answer(
                    "❌ Неверный формат. Используйте: 'сумма описание' или 'сумма описание #категория'\n"
                    "Примеры:\n"
                    "• 500 еда\n"
                    "• -1000 такси #транспорт\n"
                    "• 1500.50 зарплата #доходы"
                )
                return
            
            amount = float(match.group(1))
            description = match.group(2).strip()
            category_name = None
        
        # Валидация суммы
        if amount == 0:
            await message.answer("❌ Сумма не может быть равна нулю")
            return
        
        if abs(amount) > 1000000000:  # 1 миллиард
            await message.answer("❌ Сумма слишком большая")
            return
        
        # Валидация описания
        if len(description) > 200:
            await message.answer("❌ Описание слишком длинное (максимум 200 символов)")
            return
        
        if not description:
            await message.answer("❌ Укажите описание транзакции")
            return
            
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Используйте числа, например: 500 или -1000")
        return
    
    # Определяем тип транзакции
    transaction_type = TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE
    abs_amount = abs(amount)
    
    # Получаем или создаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Ищем категорию, если указана
        category_id = None
        if category_name:
            category = db.query(Category).filter(
                Category.user_id == db_user.id,
                Category.name == category_name,
                Category.transaction_type == transaction_type,
                Category.is_active == True
            ).first()
            
            if category:
                category_id = category.id
            else:
                # Категория не найдена, но продолжаем без неё
                await message.answer(f"⚠️ Категория '{category_name}' не найдена. Транзакция будет добавлена без категории.")
        
        # Создаем транзакцию
        transaction = Transaction(
            user_id=db_user.id,
            category_id=category_id,
            amount=abs_amount,
            currency="RUB",
            description=description,
            type=transaction_type,
            status=TransactionStatus.CONFIRMED,
            transaction_date=datetime.now()
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Анализируем на подозрительность
        fraud_service = FraudDetectionService(db)
        analysis = fraud_service.analyze_transaction(transaction)
        
        # Обновляем транзакцию с результатами анализа
        transaction.is_suspicious = analysis['is_suspicious']
        transaction.fraud_score = analysis['fraud_score']
        transaction.fraud_reasons = ', '.join(analysis['reasons']) if analysis['reasons'] else None
        
        db.commit()
        
        # Формируем ответ
        emoji = "💰" if transaction_type == TransactionType.INCOME else "💸"
        type_text = "доход" if transaction_type == TransactionType.INCOME else "расход"
        
        response = f"{emoji} Транзакция добавлена!\n"
        response += f"💰 Сумма: {abs_amount} ₽\n"
        response += f"📝 Описание: {description}\n"
        response += f"📊 Тип: {type_text}\n"
        
        # Добавляем информацию о категории
        if category_id:
            category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                response += f"📂 Категория: {category.icon or '📊'} {category.name}\n"
        
        response += f"✅ Статус: Подтверждена"
        
        # Добавляем предупреждение о подозрительности
        if analysis['is_suspicious']:
            response += f"\n\n⚠️ Подозрительная транзакция!\n"
            response += f"Оценка риска: {int(analysis['fraud_score'] * 100)}%\n"
            response += f"Причины: {', '.join(analysis['reasons'])}"
            
            # Создаем уведомление о мошенничестве
            if db_user.fraud_alerts_enabled:
                fraud_service.create_fraud_alert(transaction, analysis)
        
        await message.answer(response)
        logger.info(f"Добавлена транзакция: {abs_amount} ₽ - {description}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении транзакции: {e}")
        await message.answer("❌ Произошла ошибка при добавлении транзакции. Попробуйте еще раз.")
        db.rollback()
    finally:
        db.close()


async def view_transactions(message: types.Message) -> None:
    """Обработчик просмотра транзакций"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Получаем последние 10 транзакций
        transactions = db.query(Transaction).filter(
            Transaction.user_id == db_user.id
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        if not transactions:
            await message.answer("📭 У вас пока нет транзакций.\nИспользуйте /add для добавления!")
            return
        
        # Формируем список транзакций
        response = "📊 Последние транзакции:\n\n"
        total_income = 0
        total_expense = 0
        
        for i, transaction in enumerate(transactions, 1):
            emoji = "💸" if transaction.type == TransactionType.EXPENSE else "💰"
            sign = "-" if transaction.type == TransactionType.EXPENSE else "+"
            
            if transaction.type == TransactionType.EXPENSE:
                total_expense += transaction.amount
            else:
                total_income += transaction.amount
            
            response += f"{i}. {emoji} {sign}{transaction.amount} ₽ - {transaction.description}\n"
            
            # Добавляем информацию о категории
            if transaction.category_id:
                category = db.query(Category).filter(Category.id == transaction.category_id).first()
                if category:
                    response += f"   📂 {category.icon or '📊'} {category.name}\n"
            
            response += f"   📅 {transaction.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        # Добавляем итоги
        balance = total_income - total_expense
        response += f"📈 Итого:\n"
        response += f"💰 Доходы: +{total_income} ₽\n"
        response += f"💸 Расходы: -{total_expense} ₽\n"
        response += f"💳 Баланс: {balance:+.0f} ₽"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении транзакций: {e}")
        await message.answer("❌ Ошибка при получении транзакций")
    finally:
        db.close()


async def set_budget(message: types.Message) -> None:
    """Обработчик установки бюджета"""
    user = message.from_user
    text = message.text
    
    # Парсим команду: /set_budget сумма период
    # Примеры: /set_budget 50000 месяц, /set_budget 10000 неделя
    parts = text.split()
    
    if len(parts) < 3:
        await message.answer(
            "📊 Установка бюджета\n\n"
            "Используйте: /set_budget сумма период\n"
            "Примеры:\n"
            "• /set_budget 50000 месяц\n"
            "• /set_budget 10000 неделя\n"
            "• /set_budget 2000 день"
        )
        return
    
    try:
        amount = float(parts[1])
        period = parts[2].lower()
        
        # Определяем период
        if period in ['день', 'day']:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            period_name = "день"
        elif period in ['неделя', 'week']:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(weeks=1)
            period_name = "неделя"
        elif period in ['месяц', 'month']:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=30)
            period_name = "месяц"
        else:
            await message.answer("❌ Неподдерживаемый период. Используйте: день, неделя, месяц")
            return
        
        # Получаем пользователя
        db_user = get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Создаем бюджет
        db = SessionLocal()
        try:
            budget = Budget(
                user_id=db_user.id,
                name=f"Бюджет на {period_name}",
                amount=amount,
                currency="RUB",
                start_date=start_date,
                end_date=end_date,
                alert_threshold=0.8  # Предупреждение при 80% использования
            )
            db.add(budget)
            db.commit()
            
            response = f"""
📊 Бюджет установлен!

💰 Сумма: {amount} ₽
📅 Период: {period_name}
📅 С: {start_date.strftime('%d.%m.%Y')}
📅 По: {end_date.strftime('%d.%m.%Y')}
⚠️ Предупреждение: при {int(budget.alert_threshold * 100)}% использования
            """
            
            await message.answer(response)
            logger.info(f"Установлен бюджет: {amount} ₽ на {period_name}")
            
        except Exception as e:
            logger.error(f"Ошибка при установке бюджета: {e}")
            await message.answer("❌ Ошибка при установке бюджета")
        finally:
            db.close()
            
    except ValueError:
        await message.answer("❌ Неверный формат суммы")


async def view_budget(message: types.Message) -> None:
    """Обработчик просмотра бюджета"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Получаем активные бюджеты
        current_date = datetime.now()
        budgets = db.query(Budget).filter(
            Budget.user_id == db_user.id,
            Budget.is_active == True,
            Budget.start_date <= current_date,
            Budget.end_date >= current_date
        ).all()
        
        if not budgets:
            await message.answer(
                "📊 У вас нет активных бюджетов.\n\n"
                "Установите бюджет командой:\n"
                "/set_budget сумма период\n"
                "Пример: /set_budget 50000 месяц"
            )
            return
        
        response = "📊 Ваши бюджеты:\n\n"
        
        for i, budget in enumerate(budgets, 1):
            # Вычисляем потраченную сумму за период бюджета
            spent = db.query(Transaction).filter(
                Transaction.user_id == db_user.id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.transaction_date >= budget.start_date,
                Transaction.transaction_date <= budget.end_date
            ).with_entities(db.func.sum(Transaction.amount)).scalar() or 0
            
            # Вычисляем процент использования
            usage_percent = (spent / budget.amount) * 100 if budget.amount > 0 else 0
            
            # Определяем статус
            if usage_percent >= 100:
                status = "🔴 Превышен"
                emoji = "🔴"
            elif usage_percent >= budget.alert_threshold * 100:
                status = "🟡 Внимание"
                emoji = "🟡"
            else:
                status = "🟢 В норме"
                emoji = "🟢"
            
            response += f"{i}. {emoji} {budget.name}\n"
            response += f"   💰 Бюджет: {budget.amount} ₽\n"
            response += f"   💸 Потрачено: {spent:.0f} ₽ ({usage_percent:.1f}%)\n"
            response += f"   💳 Осталось: {budget.amount - spent:.0f} ₽\n"
            response += f"   📅 {budget.start_date.strftime('%d.%m')} - {budget.end_date.strftime('%d.%m')}\n"
            response += f"   📊 Статус: {status}\n\n"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении бюджета: {e}")
        await message.answer("❌ Ошибка при получении бюджета")
    finally:
        db.close()


async def fraud_alerts(message: types.Message) -> None:
    """Обработчик уведомлений о мошенничестве"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        fraud_service = FraudDetectionService(db)
        alerts = fraud_service.get_user_alerts(db_user.id, unread_only=True)
        
        if not alerts:
            await message.answer(
                "🔒 У вас нет непрочитанных уведомлений о безопасности.\n\n"
                "Система автоматически анализирует все ваши транзакции и "
                "предупреждает о подозрительной активности."
            )
            return
        
        response = "🔒 Уведомления о безопасности:\n\n"
        
        for i, alert in enumerate(alerts, 1):
            # Определяем эмодзи по уровню серьезности
            if alert.severity == "HIGH":
                emoji = "🔴"
            elif alert.severity == "MEDIUM":
                emoji = "🟡"
            else:
                emoji = "🟢"
            
            response += f"{i}. {emoji} {alert.message}\n"
            response += f"   📅 {alert.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            response += f"   ⚠️ Уровень: {alert.severity}\n\n"
        
        response += f"📊 Всего непрочитанных уведомлений: {len(alerts)}"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении уведомлений: {e}")
        await message.answer("❌ Ошибка при получении уведомлений")
    finally:
        db.close()


async def statistics_command(message: types.Message) -> None:
    """Обработчик просмотра статистики"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Получаем статистику за последние 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Общая статистика
        total_transactions = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.created_at >= thirty_days_ago
        ).count()
        
        # Доходы
        total_income = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.type == TransactionType.INCOME,
            Transaction.created_at >= thirty_days_ago
        ).with_entities(db.func.sum(Transaction.amount)).scalar() or 0
        
        # Расходы
        total_expense = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.created_at >= thirty_days_ago
        ).with_entities(db.func.sum(Transaction.amount)).scalar() or 0
        
        # Подозрительные транзакции
        suspicious_count = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.is_suspicious == True,
            Transaction.created_at >= thirty_days_ago
        ).count()
        
        # Средние суммы
        avg_income = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.type == TransactionType.INCOME,
            Transaction.created_at >= thirty_days_ago
        ).with_entities(db.func.avg(Transaction.amount)).scalar() or 0
        
        avg_expense = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.created_at >= thirty_days_ago
        ).with_entities(db.func.avg(Transaction.amount)).scalar() or 0
        
        # Баланс
        balance = total_income - total_expense
        
        response = f"""
📊 Статистика за последние 30 дней

💰 Общая информация:
• Всего транзакций: {total_transactions}
• Доходы: +{total_income:.0f} ₽
• Расходы: -{total_expense:.0f} ₽
• Баланс: {balance:+.0f} ₽

📈 Средние суммы:
• Средний доход: {avg_income:.0f} ₽
• Средний расход: {avg_expense:.0f} ₽

🔒 Безопасность:
• Подозрительных транзакций: {suspicious_count}
        """
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        await message.answer("❌ Ошибка при получении статистики")
    finally:
        db.close()


async def settings_command(message: types.Message) -> None:
    """Обработчик настроек"""
    user = message.from_user
    text = message.text
    
    # Парсим команду: /settings параметр значение
    parts = text.split()
    
    if len(parts) < 2:
        await message.answer(
            "⚙️ Настройки FinGuard\n\n"
            "Доступные команды:\n"
            "• /settings notifications on/off - Уведомления\n"
            "• /settings reports on/off - Ежедневные отчеты\n"
            "• /settings alerts on/off - Уведомления о безопасности\n"
            "• /settings 2fa on/off - Двухфакторная аутентификация\n\n"
            "Примеры:\n"
            "• /settings notifications off\n"
            "• /settings reports on"
        )
        return
    
    setting = parts[1].lower()
    value = parts[2].lower() if len(parts) > 2 else None
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Обновляем настройки
        if setting == "notifications":
            if value == "on":
                db_user.notifications_enabled = True
                response = "✅ Уведомления включены"
            elif value == "off":
                db_user.notifications_enabled = False
                response = "🔇 Уведомления отключены"
            else:
                await message.answer("❌ Используйте: on или off")
                return
                
        elif setting == "reports":
            if value == "on":
                db_user.daily_reports_enabled = True
                response = "✅ Ежедневные отчеты включены"
            elif value == "off":
                db_user.daily_reports_enabled = False
                response = "🔇 Ежедневные отчеты отключены"
            else:
                await message.answer("❌ Используйте: on или off")
                return
                
        elif setting == "alerts":
            if value == "on":
                db_user.fraud_alerts_enabled = True
                response = "✅ Уведомления о безопасности включены"
            elif value == "off":
                db_user.fraud_alerts_enabled = False
                response = "🔇 Уведомления о безопасности отключены"
            else:
                await message.answer("❌ Используйте: on или off")
                return
                
        elif setting == "2fa":
            if value == "on":
                db_user.two_factor_enabled = True
                response = "✅ Двухфакторная аутентификация включена"
            elif value == "off":
                db_user.two_factor_enabled = False
                response = "🔇 Двухфакторная аутентификация отключена"
            else:
                await message.answer("❌ Используйте: on или off")
                return
                
        else:
            await message.answer("❌ Неизвестная настройка")
            return
        
        db.commit()
        await message.answer(response)
        logger.info(f"Пользователь {user.id} изменил настройку {setting}: {value}")
        
    except Exception as e:
        logger.error(f"Ошибка при изменении настроек: {e}")
        await message.answer("❌ Ошибка при изменении настроек")
    finally:
        db.close()


async def delete_transaction_command(message: types.Message) -> None:
    """Обработчик удаления транзакций"""
    user = message.from_user
    text = message.text.strip()
    
    # Парсим команду: /delete ID
    parts = text.split()
    if len(parts) != 2:
        await message.answer(
            "🗑️ Удаление транзакции\n\n"
            "Использование: /delete ID\n"
            "Пример: /delete 123\n\n"
            "Чтобы найти ID транзакции, используйте /transactions"
        )
        return
    
    try:
        transaction_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID транзакции должен быть числом")
        return
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Находим транзакцию
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.user_id == db_user.id
        ).first()
        
        if not transaction:
            await message.answer("❌ Транзакция не найдена или у вас нет прав на её удаление")
            return
        
        # Сохраняем информацию для лога
        amount = transaction.amount
        description = transaction.description
        transaction_type = transaction.type
        
        # Удаляем транзакцию
        db.delete(transaction)
        db.commit()
        
        # Формируем ответ
        emoji = "💰" if transaction_type == TransactionType.INCOME else "💸"
        type_text = "доход" if transaction_type == TransactionType.INCOME else "расход"
        
        response = f"🗑️ Транзакция удалена!\n"
        response += f"💰 Сумма: {amount} ₽\n"
        response += f"📝 Описание: {description}\n"
        response += f"📊 Тип: {type_text}\n"
        response += f"🆔 ID: {transaction_id}"
        
        await message.answer(response)
        logger.info(f"Удалена транзакция {transaction_id}: {amount} ₽ - {description}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении транзакции: {e}")
        await message.answer("❌ Произошла ошибка при удалении транзакции")
        db.rollback()
    finally:
        db.close()


async def balance_command(message: types.Message) -> None:
    """Обработчик команды баланса"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Получаем все транзакции пользователя
        transactions = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.status == TransactionStatus.CONFIRMED
        ).all()
        
        # Подсчитываем баланс
        total_income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
        total_expense = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
        balance = total_income - total_expense
        
        # Получаем статистику за последние 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_transactions = db.query(Transaction).filter(
            Transaction.user_id == db_user.id,
            Transaction.status == TransactionStatus.CONFIRMED,
            Transaction.transaction_date >= thirty_days_ago
        ).all()
        
        recent_income = sum(t.amount for t in recent_transactions if t.type == TransactionType.INCOME)
        recent_expense = sum(t.amount for t in recent_transactions if t.type == TransactionType.EXPENSE)
        recent_balance = recent_income - recent_expense
        
        # Формируем ответ
        response = f"💳 Баланс FinGuard\n\n"
        response += f"📊 Общий баланс:\n"
        response += f"💰 Доходы: +{total_income:,.0f} ₽\n"
        response += f"💸 Расходы: -{total_expense:,.0f} ₽\n"
        response += f"💳 Баланс: {balance:+,.0f} ₽\n\n"
        response += f"📈 За последние 30 дней:\n"
        response += f"💰 Доходы: +{recent_income:,.0f} ₽\n"
        response += f"💸 Расходы: -{recent_expense:,.0f} ₽\n"
        response += f"💳 Баланс: {recent_balance:+,.0f} ₽\n\n"
        response += f"📊 Всего транзакций: {len(transactions)}"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        await message.answer("❌ Ошибка при получении баланса")
    finally:
        db.close()


async def categories_command(message: types.Message) -> None:
    """Обработчик команды категорий"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Получаем все категории пользователя
        categories = db.query(Category).filter(
            Category.user_id == db_user.id,
            Category.is_active == True
        ).order_by(Category.transaction_type, Category.name).all()
        
        if not categories:
            await message.answer(
                "📂 У вас пока нет категорий.\n\n"
                "Создайте категории командой:\n"
                "/add_category название тип\n\n"
                "Примеры:\n"
                "• /add_category Продукты расход\n"
                "• /add_category Зарплата доход"
            )
            return
        
        # Группируем по типу
        income_categories = [c for c in categories if c.transaction_type == TransactionType.INCOME]
        expense_categories = [c for c in categories if c.transaction_type == TransactionType.EXPENSE]
        
        response = "📂 Ваши категории:\n\n"
        
        if income_categories:
            response += "💰 Доходы:\n"
            for i, cat in enumerate(income_categories, 1):
                response += f"{i}. {cat.icon or '📊'} {cat.name}\n"
            response += "\n"
        
        if expense_categories:
            response += "💸 Расходы:\n"
            for i, cat in enumerate(expense_categories, 1):
                response += f"{i}. {cat.icon or '📊'} {cat.name}\n"
        
        response += "\n💡 Команды:\n"
        response += "• /add_category название тип - добавить категорию\n"
        response += "• /edit_category ID название - изменить категорию\n"
        response += "• /delete_category ID - удалить категорию"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении категорий: {e}")
        await message.answer("❌ Ошибка при получении категорий")
    finally:
        db.close()


async def add_category_command(message: types.Message) -> None:
    """Обработчик добавления категории"""
    user = message.from_user
    text = message.text.strip()
    
    # Парсим команду: /add_category название тип
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "📂 Добавление категории\n\n"
            "Использование: /add_category название тип\n\n"
            "Примеры:\n"
            "• /add_category Продукты расход\n"
            "• /add_category Зарплата доход\n"
            "• /add_category Рестораны расход\n\n"
            "Типы: доход, расход"
        )
        return
    
    name = parts[1].strip()
    category_type = parts[2].lower().strip()
    
    # Валидация
    if len(name) > 50:
        await message.answer("❌ Название категории слишком длинное (максимум 50 символов)")
        return
    
    if category_type not in ['доход', 'расход']:
        await message.answer("❌ Тип должен быть 'доход' или 'расход'")
        return
    
    # Определяем тип транзакции
    transaction_type = TransactionType.INCOME if category_type == 'доход' else TransactionType.EXPENSE
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Проверяем, не существует ли уже такая категория
        existing = db.query(Category).filter(
            Category.user_id == db_user.id,
            Category.name == name,
            Category.transaction_type == transaction_type,
            Category.is_active == True
        ).first()
        
        if existing:
            await message.answer(f"❌ Категория '{name}' уже существует")
            return
        
        # Создаем категорию
        category = Category(
            user_id=db_user.id,
            name=name,
            transaction_type=transaction_type,
            icon="📊"  # Базовый значок
        )
        
        db.add(category)
        db.commit()
        db.refresh(category)
        
        # Формируем ответ
        type_emoji = "💰" if transaction_type == TransactionType.INCOME else "💸"
        type_text = "доход" if transaction_type == TransactionType.INCOME else "расход"
        
        response = f"✅ Категория создана!\n\n"
        response += f"📂 Название: {name}\n"
        response += f"📊 Тип: {type_emoji} {type_text}\n"
        response += f"🆔 ID: {category.id}"
        
        await message.answer(response)
        logger.info(f"Создана категория: {name} ({type_text})")
        
    except Exception as e:
        logger.error(f"Ошибка при создании категории: {e}")
        await message.answer("❌ Ошибка при создании категории")
        db.rollback()
    finally:
        db.close()


async def delete_category_command(message: types.Message) -> None:
    """Обработчик удаления категории"""
    user = message.from_user
    text = message.text.strip()
    
    # Парсим команду: /delete_category ID
    parts = text.split()
    if len(parts) != 2:
        await message.answer(
            "🗑️ Удаление категории\n\n"
            "Использование: /delete_category ID\n"
            "Пример: /delete_category 123\n\n"
            "Чтобы найти ID категории, используйте /categories"
        )
        return
    
    try:
        category_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID категории должен быть числом")
        return
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        # Находим категорию
        category = db.query(Category).filter(
            Category.id == category_id,
            Category.user_id == db_user.id,
            Category.is_active == True
        ).first()
        
        if not category:
            await message.answer("❌ Категория не найдена или у вас нет прав на её удаление")
            return
        
        # Проверяем, есть ли транзакции в этой категории
        transactions_count = db.query(Transaction).filter(
            Transaction.category_id == category_id
        ).count()
        
        if transactions_count > 0:
            await message.answer(
                f"❌ Нельзя удалить категорию '{category.name}'\n\n"
                f"В ней есть {transactions_count} транзакций.\n"
                "Сначала переместите или удалите эти транзакции."
            )
            return
        
        # Сохраняем информацию для лога
        name = category.name
        transaction_type = category.transaction_type
        
        # Удаляем категорию (мягкое удаление)
        category.is_active = False
        db.commit()
        
        # Формируем ответ
        type_emoji = "💰" if transaction_type == TransactionType.INCOME else "💸"
        type_text = "доход" if transaction_type == TransactionType.INCOME else "расход"
        
        response = f"🗑️ Категория удалена!\n\n"
        response += f"📂 Название: {name}\n"
        response += f"📊 Тип: {type_emoji} {type_text}\n"
        response += f"🆔 ID: {category_id}"
        
        await message.answer(response)
        logger.info(f"Удалена категория {category_id}: {name}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении категории: {e}")
        await message.answer("❌ Ошибка при удалении категории")
        db.rollback()
    finally:
        db.close()


async def notifications_command(message: types.Message) -> None:
    """Обработчик команды уведомлений"""
    user = message.from_user
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        from app.services.notifications import NotificationService
        
        # Получаем уведомления
        notification_service = NotificationService(db)
        notifications = notification_service.get_user_notifications(db_user.id)
        
        # Форматируем уведомления
        response = notification_service.format_notifications(notifications)
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении уведомлений: {e}")
        await message.answer("❌ Ошибка при получении уведомлений")
    finally:
        db.close()


async def backup_command(message: types.Message) -> None:
    """Обработчик команды резервного копирования"""
    user = message.from_user
    text = message.text.strip()
    
    # Парсим команду: /backup create или /backup list
    parts = text.split()
    if len(parts) < 2:
        await message.answer(
            "💾 Резервное копирование\n\n"
            "Команды:\n"
            "• /backup create - создать резервную копию\n"
            "• /backup list - список резервных копий\n"
            "• /backup restore filename - восстановить из копии\n"
            "• /backup delete filename - удалить копию\n\n"
            "Примеры:\n"
            "• /backup create\n"
            "• /backup restore backup_user_123_20250820_143022.json"
        )
        return
    
    action = parts[1].lower()
    
    # Получаем пользователя
    db_user = get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    db = SessionLocal()
    try:
        from app.services.backup import BackupService
        
        backup_service = BackupService(db)
        
        if action == "create":
            # Создаем резервную копию
            result = backup_service.create_user_backup(db_user.id)
            
            if result['success']:
                response = f"✅ Резервная копия создана!\n\n"
                response += f"📁 Файл: {result['filename']}\n"
                response += f"💰 Транзакций: {result['transactions_count']}\n"
                response += f"📂 Категорий: {result['categories_count']}\n"
                response += f"📊 Бюджетов: {result['budgets_count']}\n"
                response += f"🔒 Уведомлений: {result['alerts_count']}"
            else:
                response = f"❌ Ошибка: {result['error']}"
            
            await message.answer(response)
            
        elif action == "list":
            # Показываем список резервных копий
            backups = backup_service.list_backups(db_user.id)
            
            if not backups:
                await message.answer("📭 У вас нет резервных копий")
                return
            
            response = "📁 Ваши резервные копии:\n\n"
            
            for i, backup in enumerate(backups[:5], 1):  # Показываем только 5 последних
                response += f"{i}. {backup['filename']}\n"
                response += f"   📅 {backup['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
                response += f"   📏 {backup['size'] / 1024:.1f} KB\n\n"
            
            if len(backups) > 5:
                response += f"... и еще {len(backups) - 5} копий\n\n"
            
            response += "💡 Команды:\n"
            response += "• /backup restore filename - восстановить\n"
            response += "• /backup delete filename - удалить"
            
            await message.answer(response)
            
        elif action == "restore":
            if len(parts) < 3:
                await message.answer("❌ Укажите имя файла для восстановления")
                return
            
            filename = parts[2]
            
            # Восстанавливаем из резервной копии
            result = backup_service.restore_user_backup(
                os.path.join("backups", filename), 
                db_user.id
            )
            
            if result['success']:
                response = f"✅ Данные восстановлены!\n\n"
                response += f"📂 Категорий: {result['categories_restored']}\n"
                response += f"📊 Бюджетов: {result['budgets_restored']}\n"
                response += f"💰 Транзакций: {result['transactions_restored']}\n"
                response += f"📈 Всего восстановлено: {result['restored_count']}"
            else:
                response = f"❌ Ошибка: {result['error']}"
            
            await message.answer(response)
            
        elif action == "delete":
            if len(parts) < 3:
                await message.answer("❌ Укажите имя файла для удаления")
                return
            
            filename = parts[2]
            
            # Удаляем резервную копию
            result = backup_service.delete_backup(filename)
            
            if result['success']:
                await message.answer("✅ Резервная копия удалена")
            else:
                await message.answer(f"❌ Ошибка: {result['error']}")
        
        else:
            await message.answer("❌ Неизвестное действие. Используйте: create, list, restore, delete")
        
    except Exception as e:
        logger.error(f"Ошибка при работе с резервными копиями: {e}")
        await message.answer("❌ Ошибка при работе с резервными копиями")
    finally:
        db.close()


async def chart_expenses_command(message: types.Message) -> None:
    """Обработчик команды /chart_expenses - график расходов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        viz_service = VisualizationService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю график расходов...")
        
        chart_path = viz_service.create_expense_chart(db_user.id, days)
        
        if chart_path:
            with open(chart_path, 'rb') as photo:
                await message.answer_photo(
                    photo,
                    caption=f"📈 График расходов за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать график. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании графика расходов: {e}")
        await message.answer("❌ Произошла ошибка при создании графика")
    finally:
        db.close()


async def chart_income_command(message: types.Message) -> None:
    """Обработчик команды /chart_income - график доходов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        viz_service = VisualizationService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю график доходов...")
        
        chart_path = viz_service.create_income_chart(db_user.id, days)
        
        if chart_path:
            with open(chart_path, 'rb') as photo:
                await message.answer_photo(
                    photo,
                    caption=f"📈 График доходов за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать график. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании графика доходов: {e}")
        await message.answer("❌ Произошла ошибка при создании графика")
    finally:
        db.close()


async def chart_categories_command(message: types.Message) -> None:
    """Обработчик команды /chart_categories - диаграмма по категориям"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        viz_service = VisualizationService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю диаграмму по категориям...")
        
        chart_path = viz_service.create_category_pie_chart(db_user.id, days)
        
        if chart_path:
            with open(chart_path, 'rb') as photo:
                await message.answer_photo(
                    photo,
                    caption=f"📊 Диаграмма по категориям за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать диаграмму. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании диаграммы категорий: {e}")
        await message.answer("❌ Произошла ошибка при создании диаграммы")
    finally:
        db.close()


async def chart_balance_command(message: types.Message) -> None:
    """Обработчик команды /chart_balance - график баланса"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        viz_service = VisualizationService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю график баланса...")
        
        chart_path = viz_service.create_balance_chart(db_user.id, days)
        
        if chart_path:
            with open(chart_path, 'rb') as photo:
                await message.answer_photo(
                    photo,
                    caption=f"📈 График баланса за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать график. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании графика баланса: {e}")
        await message.answer("❌ Произошла ошибка при создании графика")
    finally:
        db.close()


async def chart_budget_command(message: types.Message) -> None:
    """Обработчик команды /chart_budget - график бюджета"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        viz_service = VisualizationService(db)
        
        await message.answer("📊 Создаю график бюджета...")
        
        chart_path = viz_service.create_budget_chart(db_user.id)
        
        if chart_path:
            with open(chart_path, 'rb') as photo:
                await message.answer_photo(
                    photo,
                    caption="📊 График использования бюджета"
                )
        else:
            await message.answer("❌ Не удалось создать график. Возможно, у вас нет активных бюджетов.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании графика бюджета: {e}")
        await message.answer("❌ Произошла ошибка при создании графика")
    finally:
        db.close()


async def export_excel_command(message: types.Message) -> None:
    """Обработчик команды /export_excel - экспорт в Excel"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        report_service = ReportService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю Excel отчет...")
        
        report_path = report_service.export_to_excel(db_user.id, days)
        
        if report_path:
            with open(report_path, 'rb') as file:
                await message.answer_document(
                    file,
                    caption=f"📈 Excel отчет за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать отчет. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании Excel отчета: {e}")
        await message.answer("❌ Произошла ошибка при создании отчета")
    finally:
        db.close()


async def export_csv_command(message: types.Message) -> None:
    """Обработчик команды /export_csv - экспорт в CSV"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        report_service = ReportService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю CSV отчет...")
        
        report_path = report_service.export_to_csv(db_user.id, days)
        
        if report_path:
            with open(report_path, 'rb') as file:
                await message.answer_document(
                    file,
                    caption=f"📈 CSV отчет за последние {days} days"
                )
        else:
            await message.answer("❌ Не удалось создать отчет. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании CSV отчета: {e}")
        await message.answer("❌ Произошла ошибка при создании отчета")
    finally:
        db.close()


async def export_pdf_command(message: types.Message) -> None:
    """Обработчик команды /export_pdf - экспорт в PDF"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        report_service = ReportService(db)
        
        # Парсим количество дней из команды
        args = message.text.split()
        days = 30  # По умолчанию 30 дней
        
        if len(args) > 1:
            try:
                days = int(args[1])
                if days <= 0 or days > 365:
                    await message.answer("❌ Количество дней должно быть от 1 до 365")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректное количество дней")
                return
        
        await message.answer("📊 Создаю PDF отчет...")
        
        report_path = report_service.export_to_pdf(db_user.id, days)
        
        if report_path:
            with open(report_path, 'rb') as file:
                await message.answer_document(
                    file,
                    caption=f"📈 PDF отчет за последние {days} дней"
                )
        else:
            await message.answer("❌ Не удалось создать отчет. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании PDF отчета: {e}")
        await message.answer("❌ Произошла ошибка при создании отчета")
    finally:
        db.close()


async def monthly_report_command(message: types.Message) -> None:
    """Обработчик команды /monthly_report - месячный отчет"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        report_service = ReportService(db)
        
        # Парсим год и месяц из команды
        args = message.text.split()
        year = None
        month = None
        
        if len(args) > 1:
            try:
                # Формат: /monthly_report 2024 12
                if len(args) >= 3:
                    year = int(args[1])
                    month = int(args[2])
                else:
                    # Формат: /monthly_report 12 (текущий год)
                    month = int(args[1])
                    year = datetime.now().year
                
                if year < 2020 or year > 2030:
                    await message.answer("❌ Год должен быть от 2020 до 2030")
                    return
                if month < 1 or month > 12:
                    await message.answer("❌ Месяц должен быть от 1 до 12")
                    return
            except ValueError:
                await message.answer("❌ Укажите корректный год и месяц")
                return
        
        await message.answer("📊 Создаю месячный отчет...")
        
        report_path = report_service.create_monthly_report(db_user.id, year, month)
        
        if report_path:
            with open(report_path, 'rb') as file:
                period = f"{year or datetime.now().year} {month or datetime.now().month:02d}"
                await message.answer_document(
                    file,
                    caption=f"📈 Месячный отчет за {period}"
                )
        else:
            await message.answer("❌ Не удалось создать отчет. Возможно, нет данных за указанный период.")
            
    except Exception as e:
        logger.error(f"Ошибка при создании месячного отчета: {e}")
        await message.answer("❌ Произошла ошибка при создании отчета")
    finally:
        db.close()


async def payment_methods_command(message: types.Message) -> None:
    """Обработчик команды /payment_methods - управление способами оплаты"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        payment_service = PaymentMethodService(db)
        
        payment_methods = payment_service.get_user_payment_methods(db_user.id)
        
        if not payment_methods:
            response = "💳 У вас пока нет способов оплаты\n\n"
            response += "💡 Добавьте способ оплаты:\n"
            response += "• /add_payment_method карта Сбербанк card 1234567890123456 123\n"
            response += "• /add_payment_method наличные cash\n"
            response += "• /add_payment_method кошелек ЮMoney digital_wallet"
        else:
            response = "💳 Ваши способы оплаты:\n\n"
            
            for i, method in enumerate(payment_methods, 1):
                display = payment_service.format_payment_method_display(method)
                response += f"{i}. {display}\n"
            
            response += "\n💡 Команды:\n"
            response += "• /add_payment_method название тип [номер] [cvv]\n"
            response += "• /delete_payment_method ID\n"
            response += "• /set_default_payment ID\n"
            response += "• /edit_payment_method ID новое_название"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении способов оплаты: {e}")
        await message.answer("❌ Произошла ошибка при получении способов оплаты")
    finally:
        db.close()


async def add_payment_method_command(message: types.Message) -> None:
    """Обработчик команды /add_payment_method - добавление способа оплаты"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Укажите название и тип способа оплаты\n\n"
                           "Примеры:\n"
                           "• /add_payment_method карта Сбербанк card 1234567890123456 123\n"
                           "• /add_payment_method наличные cash\n"
                           "• /add_payment_method кошелек ЮMoney digital_wallet")
        return
    
    db = SessionLocal()
    try:
        payment_service = PaymentMethodService(db)
        
        name = args[1]
        method_type_str = args[2].lower()
        
        # Определяем тип способа оплаты
        from app.database.models import PaymentMethodType
        
        if method_type_str == "card":
            method_type = PaymentMethodType.CARD
            card_number = args[3] if len(args) > 3 else None
            cvv = args[4] if len(args) > 4 else None
        elif method_type_str == "cash":
            method_type = PaymentMethodType.CASH
            card_number = None
            cvv = None
        elif method_type_str == "bank_transfer":
            method_type = PaymentMethodType.BANK_TRANSFER
            card_number = None
            cvv = None
        elif method_type_str == "digital_wallet":
            method_type = PaymentMethodType.DIGITAL_WALLET
            card_number = None
            cvv = None
        else:
            await message.answer("❌ Неизвестный тип способа оплаты\n\n"
                               "Доступные типы:\n"
                               "• card - банковская карта\n"
                               "• cash - наличные\n"
                               "• bank_transfer - банковский перевод\n"
                               "• digital_wallet - цифровой кошелек")
            return
        
        result = payment_service.add_payment_method(
            db_user.id, name, method_type, card_number, cvv
        )
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении способа оплаты: {e}")
        await message.answer("❌ Произошла ошибка при добавлении способа оплаты")
    finally:
        db.close()


async def delete_payment_method_command(message: types.Message) -> None:
    """Обработчик команды /delete_payment_method - удаление способа оплаты"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID способа оплаты\n\n"
                           "Пример: /delete_payment_method 123")
        return
    
    try:
        payment_method_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    
    db = SessionLocal()
    try:
        payment_service = PaymentMethodService(db)
        
        result = payment_service.delete_payment_method(payment_method_id, db_user.id)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении способа оплаты: {e}")
        await message.answer("❌ Произошла ошибка при удалении способа оплаты")
    finally:
        db.close()


async def set_default_payment_command(message: types.Message) -> None:
    """Обработчик команды /set_default_payment - установка способа оплаты по умолчанию"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID способа оплаты\n\n"
                           "Пример: /set_default_payment 123")
        return
    
    try:
        payment_method_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    
    db = SessionLocal()
    try:
        payment_service = PaymentMethodService(db)
        
        result = payment_service.set_default_payment_method(payment_method_id, db_user.id)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при установке способа оплаты по умолчанию: {e}")
        await message.answer("❌ Произошла ошибка при установке способа оплаты по умолчанию")
    finally:
        db.close()


async def transfer_command(message: types.Message) -> None:
    """Обработчик команды /transfer - перевод между счетами"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 4:
        await message.answer("❌ Укажите параметры перевода\n\n"
                           "Формат: /transfer от_счета к_счету сумма [описание]\n\n"
                           "Примеры:\n"
                           "• /transfer 1 2 5000 перевод на карту\n"
                           "• /transfer 2 3 10000 пополнение кошелька")
        return
    
    try:
        from_method_id = int(args[1])
        to_method_id = int(args[2])
        amount = float(args[3])
        description = " ".join(args[4:]) if len(args) > 4 else "Перевод между счетами"
    except ValueError:
        await message.answer("❌ Неверный формат параметров")
        return
    
    if amount <= 0:
        await message.answer("❌ Сумма перевода должна быть больше нуля")
        return
    
    db = SessionLocal()
    try:
        transfer_service = TransferService(db)
        
        result = transfer_service.create_transfer(
            db_user.id, from_method_id, to_method_id, amount, description
        )
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании перевода: {e}")
        await message.answer("❌ Произошла ошибка при создании перевода")
    finally:
        db.close()


async def transfers_command(message: types.Message) -> None:
    """Обработчик команды /transfers - история переводов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    days = 30  # По умолчанию 30 дней
    
    if len(args) > 1:
        try:
            days = int(args[1])
            if days <= 0 or days > 365:
                await message.answer("❌ Количество дней должно быть от 1 до 365")
                return
        except ValueError:
            await message.answer("❌ Укажите корректное количество дней")
            return
    
    db = SessionLocal()
    try:
        transfer_service = TransferService(db)
        
        transfers = transfer_service.get_user_transfers(db_user.id, days)
        
        if not transfers:
            await message.answer(f"📭 У вас нет переводов за последние {days} дней")
            return
        
        response = f"💸 История переводов за последние {days} дней:\n\n"
        
        for i, transfer in enumerate(transfers[:10], 1):  # Показываем только 10 последних
            display = transfer_service.format_transfer_display(transfer)
            response += f"{i}. {display}\n\n"
        
        if len(transfers) > 10:
            response += f"... и еще {len(transfers) - 10} переводов\n\n"
        
        # Статистика
        stats = transfer_service.get_transfer_statistics(db_user.id, days)
        response += f"📊 Статистика:\n"
        response += f"• Всего переводов: {stats['total_transfers']}\n"
        response += f"• Общая сумма: {stats['total_amount']:,.0f} ₽\n"
        response += f"• Средняя сумма: {stats['average_amount']:,.0f} ₽\n"
        if stats['total_fees'] > 0:
            response += f"• Комиссии: {stats['total_fees']:,.0f} ₽"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории переводов: {e}")
        await message.answer("❌ Произошла ошибка при получении истории переводов")
    finally:
        db.close()


async def enable_2fa_command(message: types.Message) -> None:
    """Обработчик команды /enable_2fa - включение двухфакторной аутентификации"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        two_factor_service = TwoFactorService(db)
        
        result = two_factor_service.enable_2fa(db_user.id)
        
        if result['success']:
            response = f"✅ {result['message']}\n\n"
            response += f"🔐 Код подтверждения: {result['code']}\n\n"
            response += "⚠️ В реальном приложении код отправляется по SMS или email"
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при включении 2FA: {e}")
        await message.answer("❌ Произошла ошибка при включении 2FA")
    finally:
        db.close()


async def disable_2fa_command(message: types.Message) -> None:
    """Обработчик команды /disable_2fa - отключение двухфакторной аутентификации"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код подтверждения\n\n"
                           "Пример: /disable_2fa 123456")
        return
    
    code = args[1]
    
    db = SessionLocal()
    try:
        two_factor_service = TwoFactorService(db)
        
        result = two_factor_service.disable_2fa(db_user.id, code)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при отключении 2FA: {e}")
        await message.answer("❌ Произошла ошибка при отключении 2FA")
    finally:
        db.close()


async def verify_2fa_command(message: types.Message) -> None:
    """Обработчик команды /verify_2fa - проверка кода двухфакторной аутентификации"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите код подтверждения\n\n"
                           "Пример: /verify_2fa 123456")
        return
    
    code = args[1]
    
    db = SessionLocal()
    try:
        two_factor_service = TwoFactorService(db)
        
        result = two_factor_service.verify_2fa_code(db_user.id, code)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке 2FA кода: {e}")
        await message.answer("❌ Произошла ошибка при проверке кода")
    finally:
        db.close()


async def backup_codes_command(message: types.Message) -> None:
    """Обработчик команды /backup_codes - генерация резервных кодов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        two_factor_service = TwoFactorService(db)
        
        result = two_factor_service.generate_backup_codes(db_user.id)
        
        if result['success']:
            response = f"✅ {result['message']}\n\n"
            response += "🔑 Резервные коды:\n"
            for i, code in enumerate(result['backup_codes'], 1):
                response += f"{i}. {code}\n"
            response += "\n⚠️ Сохраните эти коды в безопасном месте!"
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации резервных кодов: {e}")
        await message.answer("❌ Произошла ошибка при генерации резервных кодов")
    finally:
        db.close()


async def two_factor_status_command(message: types.Message) -> None:
    """Обработчик команды /2fa_status - статус двухфакторной аутентификации"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        two_factor_service = TwoFactorService(db)
        
        result = two_factor_service.get_2fa_status(db_user.id)
        
        if result['success']:
            status_emoji = "🟢" if result['enabled'] else "🔴"
            response = f"{status_emoji} {result['message']}\n\n"
            
            if result['enabled']:
                response += "💡 Команды:\n"
                response += "• /disable_2fa код - отключить 2FA\n"
                response += "• /verify_2fa код - проверить код\n"
                response += "• /backup_codes - резервные коды"
            else:
                response += "💡 Команды:\n"
                response += "• /enable_2fa - включить 2FA"
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса 2FA: {e}")
        await message.answer("❌ Произошла ошибка при получении статуса")
    finally:
        db.close()


async def confirm_transaction_command(message: types.Message) -> None:
    """Обработчик команды /confirm_transaction - подтверждение транзакции"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID транзакции\n\n"
                           "Пример: /confirm_transaction 123")
        return
    
    try:
        transaction_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    
    db = SessionLocal()
    try:
        status_service = TransactionStatusService(db)
        
        result = status_service.confirm_transaction(transaction_id, db_user.id)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении транзакции: {e}")
        await message.answer("❌ Произошла ошибка при подтверждении транзакции")
    finally:
        db.close()


async def reject_transaction_command(message: types.Message) -> None:
    """Обработчик команды /reject_transaction - отклонение транзакции"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID транзакции\n\n"
                           "Пример: /reject_transaction 123 [причина]")
        return
    
    try:
        transaction_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return
    
    reason = " ".join(args[2:]) if len(args) > 2 else None
    
    db = SessionLocal()
    try:
        status_service = TransactionStatusService(db)
        
        result = status_service.reject_transaction(transaction_id, db_user.id, reason)
        
        if result['success']:
            await message.answer(f"✅ {result['message']}")
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении транзакции: {e}")
        await message.answer("❌ Произошла ошибка при отклонении транзакции")
    finally:
        db.close()


async def pending_transactions_command(message: types.Message) -> None:
    """Обработчик команды /pending_transactions - ожидающие транзакции"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        status_service = TransactionStatusService(db)
        
        pending_transactions = status_service.get_pending_transactions(db_user.id, limit=10)
        
        if not pending_transactions:
            await message.answer("📭 У вас нет ожидающих транзакций")
            return
        
        response = "⏳ Ожидающие транзакции:\n\n"
        
        for i, transaction in enumerate(pending_transactions, 1):
            status_display = status_service.format_transaction_status(transaction)
            response += f"{i}. {status_display}\n"
            response += f"   💰 {transaction.amount:,.0f} ₽ - {transaction.description}\n"
            response += f"   📅 {transaction.transaction_date.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        response += "💡 Команды:\n"
        response += "• /confirm_transaction ID - подтвердить\n"
        response += "• /reject_transaction ID [причина] - отклонить"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении ожидающих транзакций: {e}")
        await message.answer("❌ Произошла ошибка при получении ожидающих транзакций")
    finally:
        db.close()


async def transaction_status_summary_command(message: types.Message) -> None:
    """Обработчик команды /transaction_status_summary - сводка по статусам транзакций"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        status_service = TransactionStatusService(db)
        
        summary = status_service.get_transaction_status_summary(db_user.id)
        
        response = "📊 Сводка по статусам транзакций:\n\n"
        response += f"⏳ Ожидающие: {summary['pending']}\n"
        response += f"✅ Подтвержденные: {summary['confirmed']}\n"
        response += f"❌ Отклоненные: {summary['rejected']}\n"
        response += f"⚠️ Подозрительные: {summary['suspicious']}\n"
        response += f"📈 Всего: {summary['total']}"
        
        await message.answer(response)
        
    except Exception as e:
        logger.error(f"Ошибка при получении сводки статусов: {e}")
        await message.answer("❌ Произошла ошибка при получении сводки")
    finally:
        db.close()


async def forecast_command(message: types.Message) -> None:
    """Обработчик команды /forecast - прогноз расходов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    days = 30  # По умолчанию 30 дней
    
    if len(args) > 1:
        try:
            days = int(args[1])
            if days <= 0 or days > 365:
                await message.answer("❌ Количество дней должно быть от 1 до 365")
                return
        except ValueError:
            await message.answer("❌ Укажите корректное количество дней")
            return
    
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(db)
        
        result = analytics_service.get_expense_forecast(db_user.id, days)
        
        if result['success']:
            response = f"🔮 Прогноз расходов на {days} дней:\n\n"
            response += f"📊 Средние дневные расходы: {result['average_daily']:,.0f} ₽\n"
            response += f"📈 Прогноз общих расходов: {result['forecast_total']:,.0f} ₽\n"
            response += f"📊 Доверительный интервал: {result['confidence_interval']}\n\n"
            response += f"📈 Медиана дневных расходов: {result['median_daily']:,.0f} ₽"
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении прогноза: {e}")
        await message.answer("❌ Произошла ошибка при получении прогноза")
    finally:
        db.close()


async def trends_command(message: types.Message) -> None:
    """Обработчик команды /trends - анализ трендов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    days = 30  # По умолчанию 30 дней
    
    if len(args) > 1:
        try:
            days = int(args[1])
            if days <= 0 or days > 365:
                await message.answer("❌ Количество дней должно быть от 1 до 365")
                return
        except ValueError:
            await message.answer("❌ Укажите корректное количество дней")
            return
    
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(db)
        
        result = analytics_service.get_spending_trends(db_user.id, days)
        
        if result['success']:
            response = f"📈 Анализ трендов за {days} дней:\n\n"
            response += f"📊 Направление тренда: {result['trend_direction']}\n"
            if result['trend_percentage'] != 0:
                response += f"📈 Изменение: {result['trend_percentage']:+.1f}%\n"
            response += f"📊 Средние недельные расходы: {result['average_weekly']:,.0f} ₽\n"
            response += f"📈 Общие расходы за период: {result['total_period']:,.0f} ₽\n\n"
            
            response += "📅 По неделям:\n"
            for week, amount in result['weekly_data'].items():
                response += f"• {week}: {amount:,.0f} ₽\n"
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при анализе трендов: {e}")
        await message.answer("❌ Произошла ошибка при анализе трендов")
    finally:
        db.close()


async def recommendations_command(message: types.Message) -> None:
    """Обработчик команды /recommendations - рекомендации по экономии"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(db)
        
        result = analytics_service.get_savings_recommendations(db_user.id)
        
        if result['success']:
            response = f"💡 Рекомендации по экономии:\n\n"
            response += f"📊 Общие расходы за 30 дней: {result['total_expenses']:,.0f} ₽\n"
            response += f"📈 Средние дневные расходы: {result['average_daily']:,.0f} ₽\n\n"
            
            if result['recommendations']:
                response += "🎯 Рекомендации:\n"
                for i, rec in enumerate(result['recommendations'], 1):
                    response += f"{i}. {rec['suggestion']}\n"
            else:
                response += "✅ Ваши расходы выглядят хорошо!"
            
            response += "\n📊 Топ категорий расходов:\n"
            for category, amount in result['top_categories']:
                response += f"• {category}: {amount:,.0f} ₽\n"
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при получении рекомендаций: {e}")
        await message.answer("❌ Произошла ошибка при получении рекомендаций")
    finally:
        db.close()


async def financial_health_command(message: types.Message) -> None:
    """Обработчик команды /financial_health - оценка финансового здоровья"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(db)
        
        result = analytics_service.get_financial_health_score(db_user.id)
        
        if result['success']:
            response = f"{result['emoji']} Оценка финансового здоровья: {result['level']}\n\n"
            response += f"📊 Общий балл: {result['score']}/100\n"
            response += f"💰 Общие доходы: {result['total_income']:,.0f} ₽\n"
            response += f"💸 Общие расходы: {result['total_expenses']:,.0f} ₽\n"
            response += f"📈 Норма сбережений: {result['savings_rate']:.1f}%\n"
            response += f"📊 Соотношение расходов к доходам: {result['expense_ratio']:.1f}%\n"
            response += f"📂 Источники доходов: {result['income_categories']}\n\n"
            
            if result['score'] >= 80:
                response += "🎉 Отличная работа! Ваши финансы в отличном состоянии."
            elif result['score'] >= 60:
                response += "👍 Хорошо! Есть возможности для улучшения."
            elif result['score'] >= 40:
                response += "⚠️ Требует внимания. Рассмотрите оптимизацию расходов."
            else:
                response += "🚨 Требует немедленного внимания. Рекомендуется консультация."
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при оценке финансового здоровья: {e}")
        await message.answer("❌ Произошла ошибка при оценке финансового здоровья")
    finally:
        db.close()


async def compare_periods_command(message: types.Message) -> None:
    """Обработчик команды /compare_periods - сравнение периодов"""
    user = message.from_user
    db_user = get_or_create_user(user.id, user.username, user.first_name, user.last_name)
    
    args = message.text.split()
    days = 30  # По умолчанию 30 дней
    
    if len(args) > 1:
        try:
            days = int(args[1])
            if days <= 0 or days > 365:
                await message.answer("❌ Количество дней должно быть от 1 до 365")
                return
        except ValueError:
            await message.answer("❌ Укажите корректное количество дней")
            return
    
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(db)
        
        result = analytics_service.get_comparison_with_previous_period(db_user.id, days)
        
        if result['success']:
            response = f"📊 Сравнение периодов ({days} дней):\n\n"
            
            response += f"📈 Текущий период:\n"
            response += f"• Доходы: {result['current_period']['income']:,.0f} ₽\n"
            response += f"• Расходы: {result['current_period']['expenses']:,.0f} ₽\n"
            response += f"• Баланс: {result['current_period']['balance']:+,.0f} ₽\n\n"
            
            response += f"📉 Предыдущий период:\n"
            response += f"• Доходы: {result['previous_period']['income']:,.0f} ₽\n"
            response += f"• Расходы: {result['previous_period']['expenses']:,.0f} ₽\n"
            response += f"• Баланс: {result['previous_period']['balance']:+,.0f} ₽\n\n"
            
            response += f"🔄 Изменения:\n"
            response += f"• Доходы: {result['changes']['income_trend']} {result['changes']['income_change']:+.1f}%\n"
            response += f"• Расходы: {result['changes']['expense_trend']} {result['changes']['expense_change']:+.1f}%"
            
            await message.answer(response)
        else:
            await message.answer(f"❌ {result['error']}")
        
    except Exception as e:
        logger.error(f"Ошибка при сравнении периодов: {e}")
        await message.answer("❌ Произошла ошибка при сравнении периодов")
    finally:
        db.close()
