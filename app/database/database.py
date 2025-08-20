"""
Настройка подключения к базе данных
Использует SQLAlchemy для работы с PostgreSQL
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Получаем настройки
settings = get_settings()

# Создаем движок базы данных
engine = create_engine(
    settings.database_url,
    echo=settings.debug,  # Выводим SQL запросы в режиме отладки
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


def get_db():
    """
    Генератор для получения сессии базы данных
    Автоматически закрывает сессию после использования
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Ошибка в сессии базы данных: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Инициализация базы данных
    Создает все таблицы на основе моделей
    """
    try:
        # Импортируем модели для создания таблиц
        from app.database.models import User, Transaction, Category, Budget, PaymentMethod
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        logger.info("✅ База данных успешно инициализирована")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации базы данных: {e}")
        raise


def check_db_connection():
    """
    Проверка подключения к базе данных
    Возвращает True если подключение успешно
    """
    try:
        from sqlalchemy import text
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Подключение к базе данных успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        return False


def create_sample_data():
    """
    Создание демо-данных для тестирования
    Добавляет базовые категории и настройки
    """
    from app.database.models import User, Category, TransactionType
    from sqlalchemy.orm import Session
    
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже данные
        if db.query(User).first():
            logger.info("Демо-данные уже существуют")
            return
        
        # Создаем демо-пользователя
        demo_user = User(
            telegram_id=123456789,
            username="demo_user",
            first_name="Демо",
            last_name="Пользователь"
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
        
        # Создаем базовые категории расходов
        expense_categories = [
            ("🍔 Еда", "Продукты питания и рестораны", "#FF6B6B"),
            ("🚗 Транспорт", "Такси, метро, бензин", "#4ECDC4"),
            ("🏠 Жилье", "Аренда, коммунальные услуги", "#45B7D1"),
            ("🛍️ Покупки", "Одежда, электроника", "#96CEB4"),
            ("🎮 Развлечения", "Кино, игры, хобби", "#FFEAA7"),
            ("💊 Здоровье", "Медицина, спорт", "#DDA0DD"),
            ("📚 Образование", "Курсы, книги", "#98D8C8"),
            ("💼 Работа", "Офис, командировки", "#F7DC6F")
        ]
        
        for name, description, color in expense_categories:
            category = Category(
                user_id=demo_user.id,
                name=name,
                description=description,
                color=color,
                transaction_type=TransactionType.EXPENSE
            )
            db.add(category)
        
        # Создаем базовые категории доходов
        income_categories = [
            ("💰 Зарплата", "Основной доход", "#2ECC71"),
            ("💼 Фриланс", "Дополнительный доход", "#3498DB"),
            ("📈 Инвестиции", "Доходы от инвестиций", "#9B59B6"),
            ("🎁 Подарки", "Подарки и бонусы", "#E67E22")
        ]
        
        for name, description, color in income_categories:
            category = Category(
                user_id=demo_user.id,
                name=name,
                description=description,
                color=color,
                transaction_type=TransactionType.INCOME
            )
            db.add(category)
        
        db.commit()
        logger.info("✅ Демо-данные успешно созданы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании демо-данных: {e}")
        db.rollback()
    finally:
        db.close()
