"""
Модели базы данных для FinGuard
Определяет структуру таблиц для хранения финансовых данных
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database.database import Base


class TransactionType(enum.Enum):
    """Типы транзакций"""
    INCOME = "income"      # Доход
    EXPENSE = "expense"    # Расход
    TRANSFER = "transfer"  # Перевод


class TransactionStatus(enum.Enum):
    """Статусы транзакций"""
    PENDING = "pending"    # Ожидает подтверждения
    CONFIRMED = "confirmed"  # Подтверждена
    REJECTED = "rejected"  # Отклонена
    SUSPICIOUS = "suspicious"  # Подозрительная


class PaymentMethodType(enum.Enum):
    """Типы платежных методов"""
    CARD = "card"         # Банковская карта
    CASH = "cash"         # Наличные
    BANK_TRANSFER = "bank_transfer"  # Банковский перевод
    DIGITAL_WALLET = "digital_wallet"  # Цифровой кошелек


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone_number = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    
    # Настройки безопасности
    two_factor_enabled = Column(Boolean, default=False)
    fraud_alerts_enabled = Column(Boolean, default=True)
    
    # Настройки уведомлений
    notifications_enabled = Column(Boolean, default=True)
    daily_reports_enabled = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    transactions = relationship("Transaction", back_populates="user")
    categories = relationship("Category", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    payment_methods = relationship("PaymentMethod", back_populates="user")


class Category(Base):
    """Модель категорий расходов/доходов"""
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # HEX цвет
    icon = Column(String(50), nullable=True)  # Эмодзи или название иконки
    
    # Тип категории (доход/расход)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")


class PaymentMethod(Base):
    """Модель платежных методов"""
    __tablename__ = "payment_methods"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Основная информация
    name = Column(String(100), nullable=False)  # Название карты/кошелька
    type = Column(Enum(PaymentMethodType), nullable=False)
    
    # Зашифрованные данные (реальные данные шифруются)
    encrypted_data = Column(Text, nullable=True)  # Зашифрованные данные карты
    masked_number = Column(String(20), nullable=True)  # Маскированный номер
    
    # Настройки безопасности
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="payment_methods")
    transactions = relationship("Transaction", back_populates="payment_method")


class Transaction(Base):
    """Модель финансовых транзакций"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=True)
    
    # Основная информация о транзакции
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="RUB")
    description = Column(Text, nullable=True)
    type = Column(Enum(TransactionType), nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING)
    
    # Детали транзакции
    merchant = Column(String(200), nullable=True)  # Название магазина/получателя
    location = Column(String(200), nullable=True)  # Местоположение
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    
    # Данные для анализа мошенничества
    is_suspicious = Column(Boolean, default=False)
    fraud_score = Column(Float, default=0.0)  # Оценка подозрительности (0-1)
    fraud_reasons = Column(Text, nullable=True)  # Причины подозрительности
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    payment_method = relationship("PaymentMethod", back_populates="transactions")


class Budget(Base):
    """Модель бюджетов"""
    __tablename__ = "budgets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Основная информация
    name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="RUB")
    
    # Период бюджета
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Настройки уведомлений
    alert_threshold = Column(Float, default=0.8)  # Порог предупреждения (80%)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    user = relationship("User", back_populates="budgets")


class FraudAlert(Base):
    """Модель уведомлений о мошенничестве"""
    __tablename__ = "fraud_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Информация об уведомлении
    alert_type = Column(String(50), nullable=False)  # Тип уведомления
    severity = Column(String(20), nullable=False)  # Уровень серьезности
    message = Column(Text, nullable=False)
    
    # Статус уведомления
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User")
    transaction = relationship("Transaction")
