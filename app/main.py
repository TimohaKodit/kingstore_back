from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base 
from app.db.session import engine 
from app.models import item, category # Убедитесь, что все модели здесь
from app.api.v1.endpoints import items, categories, orders, uploads # Добавлен uploads
from app.core.config import settings

# 💡 НОВЫЕ ИМПОРТЫ ДЛЯ ТЕЛЕГРАМ WEBHOOK
from bot import bot, dp # Импортируем инициализированные объекты из bot.py
import logging
from aiogram.types import Update

# Инициализация логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем таблицы в БД.
# Если вы используете модели из item, category, order, они должны быть импортированы выше!
Base.metadata.create_all(bind=engine) 

app = FastAPI(
    title="Telegram Mini App Shop Backend",
    version="1.0.0",
)

# Настройки CORS
origins = [
    "http://127.0.0.1:5500", 
    "http://localhost:5500",
    "http://127.0.0.1:8888",
    "http://127.0.0.1:8000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# РЕГИСТРАЦИЯ СТАТИЧЕСКОЙ ПАПКИ (для загруженных изображений)
app.mount("/static/images", StaticFiles(directory="uploaded_images"), name="static_images")


# Подключаем роуты для API
app.include_router(items.router, prefix="/api/v1/items", tags=["Items (Products)"])
app.include_router(categories.router, prefix="/api/v1", tags=["Categories"])
app.include_router(orders.router, prefix="/api/v1", tags=["orders"])
app.include_router(uploads.router, prefix="/api/v1", tags=["File Uploads"]) # Роут для загрузки файлов

# --------------------------------------------------------------------------------------
# --- ОБРАБОТКА ТЕЛЕГРАМ WEBHOOK ---
# --------------------------------------------------------------------------------------

# Константа, определяющая путь к вебхуку
WEBHOOK_PATH = "/webhook"
# Полный URL, который мы отправим Telegram (получается из WEBHOOK_URL в config.py)
# settings.WEBHOOK_URL будет вашим публичным доменом Railway.
FULL_WEBHOOK_URL = settings.WEBHOOK_URL.rstrip('/') + WEBHOOK_PATH

@app.on_event("startup")
async def on_startup():
    """Устанавливает вебхук при запуске сервера."""
    if not settings.WEBHOOK_URL:
        logger.warning("WEBHOOK_URL не установлен. Webhook не будет настроен. Бот будет работать только локально.")
        return

    try:
        current_webhook = await bot.get_webhook_info()
        
        if current_webhook.url != FULL_WEBHOOK_URL:
            logger.info(f"Установка нового вебхука: {FULL_WEBHOOK_URL}")
            await bot.set_webhook(
                url=FULL_WEBHOOK_URL,
                drop_pending_updates=True, # Удаляем старые обновления
                max_connections=40 
            )
            logger.info("Вебхук успешно установлен.")
        else:
            logger.info("Вебхук уже установлен и актуален.")

    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    """Удаляет вебхук при завершении работы сервера (необязательно, но полезно)."""
    logger.info("Закрытие сессии бота...")
    await bot.session.close()


@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """Роут для приема обновлений от Telegram."""
    try:
        # Получаем тело запроса
        telegram_update = await request.json()
        
        # Конвертируем JSON в объект Update aiogram
        update = Update(**telegram_update)
        
        # Передаем обновление диспетчеру для обработки
        await dp.feed_update(bot, update)
        
        # Telegram ожидает, что мы ответим 200 OK быстро.
        return {"ok": True}
    except Exception as e:
        logger.error(f"Ошибка обработки WebHook: {e}")
        return {"ok": False, "error": str(e)}

# --------------------------------------------------------------------------------------

@app.get("/")
def read_root():
    return {"message": "Welcome to the Telegram Mini App Shop Backend! API and Webhook are running."}
