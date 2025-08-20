"""
Webhook поддержка для продакшена
Обеспечивает безопасное получение обновлений от Telegram
"""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Создаем FastAPI приложение
app = FastAPI(title="FinGuard Webhook", version="1.0.0")

# Глобальные переменные для бота и диспетчера
bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None


def init_webhook(bot_instance: Bot, dispatcher: Dispatcher) -> None:
    """Инициализирует webhook для бота"""
    global bot, dp
    bot = bot_instance
    dp = dispatcher
    logger.info("Webhook инициализирован")


def verify_telegram_signature(request: Request, body: bytes) -> bool:
    """Проверяет подпись от Telegram"""
    settings = get_settings()
    
    if not settings.telegram_webhook_secret:
        logger.warning("TELEGRAM_WEBHOOK_SECRET не установлен, пропускаем проверку подписи")
        return True
    
    # Получаем заголовки
    x_telegram_bot_api_secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    
    if not x_telegram_bot_api_secret_token:
        logger.warning("Отсутствует X-Telegram-Bot-Api-Secret-Token")
        return False
    
    # Проверяем токен
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("Неверный webhook secret token")
        return False
    
    return True


@app.post("/webhook")
async def webhook_handler(request: Request) -> JSONResponse:
    """Обработчик webhook от Telegram"""
    try:
        # Читаем тело запроса
        body = await request.body()
        
        # Проверяем подпись (если включена)
        if not verify_telegram_signature(request, body):
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Парсим JSON
        update_data = json.loads(body.decode('utf-8'))
        update = Update(**update_data)
        
        # Проверяем, что бот и диспетчер инициализированы
        if not bot or not dp:
            logger.error("Бот или диспетчер не инициализированы")
            raise HTTPException(status_code=500, detail="Bot not initialized")
        
        # Обрабатываем обновление
        await dp.feed_update(bot, update)
        
        logger.info(f"Webhook обработан: {update.update_id}")
        return JSONResponse(content={"status": "ok"})
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check() -> JSONResponse:
    """Проверка здоровья сервиса"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "FinGuard Webhook",
        "bot_initialized": bot is not None,
        "dispatcher_initialized": dp is not None
    })


@app.get("/")
async def root() -> JSONResponse:
    """Корневой endpoint"""
    return JSONResponse(content={
        "service": "FinGuard Webhook",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health"
        }
    })


async def setup_webhook(bot: Bot, webhook_url: str) -> bool:
    """Настраивает webhook для бота"""
    try:
        # Устанавливаем webhook
        await bot.set_webhook(
            url=webhook_url,
            secret_token=get_settings().telegram_webhook_secret,
            drop_pending_updates=True
        )
        
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook установлен: {webhook_info.url}")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
        return False


async def remove_webhook(bot: Bot) -> bool:
    """Удаляет webhook для бота"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удален")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
        return False
