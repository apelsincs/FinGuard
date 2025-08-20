"""
Обработчики команд Telegram бота
Базовые функции для управления финансами
"""

from aiogram import types
from aiogram.filters import Command
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import re

from app.database.database import SessionLocal
from app.database.models import User, Transaction, Category, TransactionType, TransactionStatus, Budget, FraudAlert
from app.services.fraud_detection import FraudDetectionService
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
    """
    
    await message.answer(help_text)


async def add_transaction(message: types.Message) -> None:
    """Обработчик добавления транзакции"""
    user = message.from_user
    text = message.text
    
    # Пропускаем команды
    if text.startswith('/'):
        return
    
    # Парсим сообщение
    try:
        # Простой парсер: "сумма описание" или "-сумма описание"
        match = re.match(r'^(-?\d+(?:\.\d+)?)\s+(.+)$', text.strip())
        if not match:
            await message.answer(
                "❌ Неверный формат. Используйте: сумма описание\n"
                "Примеры: '500 еда' или '-1000 такси'"
            )
            return
        
        amount = float(match.group(1))
        description = match.group(2).strip()
        
        # Определяем тип транзакции
        transaction_type = TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME
        amount = abs(amount)  # Сохраняем положительное значение
        
        # Получаем пользователя
        db_user = get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Создаем транзакцию
        db = SessionLocal()
        try:
            transaction = Transaction(
                user_id=db_user.id,
                amount=amount,
                description=description,
                type=transaction_type,
                status=TransactionStatus.CONFIRMED,
                transaction_date=datetime.now()
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            
            # Анализируем транзакцию на мошенничество
            fraud_service = FraudDetectionService(db)
            analysis = fraud_service.analyze_transaction(transaction)
            
            # Обновляем транзакцию с результатами анализа
            transaction.is_suspicious = analysis['is_suspicious']
            transaction.fraud_score = analysis['fraud_score']
            transaction.fraud_reasons = ', '.join(analysis['reasons']) if analysis['reasons'] else None
            db.commit()
            
            # Создаем уведомление если транзакция подозрительная
            if analysis['is_suspicious']:
                fraud_service.create_fraud_alert(transaction, analysis)
            
            # Формируем ответ
            emoji = "💸" if transaction_type == TransactionType.EXPENSE else "💰"
            status_text = "расход" if transaction_type == TransactionType.EXPENSE else "доход"
            
            response = f"""
{emoji} Транзакция добавлена!

💰 Сумма: {amount} ₽
📝 Описание: {description}
📊 Тип: {status_text}
✅ Статус: Подтверждена
            """
            
            # Добавляем предупреждение если транзакция подозрительная
            if analysis['is_suspicious']:
                response += f"\n⚠️ Подозрительная транзакция!\n"
                response += f"Оценка риска: {analysis['fraud_score']:.1%}\n"
                response += f"Причины: {', '.join(analysis['reasons'])}"
            
            await message.answer(response)
            logger.info(f"Добавлена транзакция: {amount} ₽ - {description}")
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении транзакции: {e}")
            await message.answer("❌ Ошибка при сохранении транзакции")
        finally:
            db.close()
            
    except ValueError:
        await message.answer("❌ Неверный формат суммы")


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
