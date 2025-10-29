from fastapi import FastAPI
from app.api.v1.endpoints import items
# --- ИМПОРТЫ РОУТЕРОВ ---
from app.api.v1.endpoints import categories 
from app.api.v1.endpoints import orders
# 💡 НОВЫЙ ИМПОРТ ДЛЯ ЗАГРУЗКИ ФАЙЛОВ
from app.api.v1.endpoints import uploads
# 💡 НОВЫЙ ИМПОРТ ДЛЯ РАЗДАЧИ СТАТИЧЕСКИХ ФАЙЛОВ
from fastapi.staticfiles import StaticFiles 
# -------------------------

# --- ИМПОРТЫ МОДЕЛЕЙ ДЛЯ СОЗДАНИЯ ТАБЛИЦ ---
from app.db.base import Base 
from app.db.session import engine 
# 💡 ИМПОРТИРУЕМ ВСЕ ОСНОВНЫЕ МОДЕЛИ, ЧТОБЫ BASE ЗАРЕГИСТРИРОВАЛ ИХ!
from app.models import item, category, order 

from fastapi.middleware.cors import CORSMiddleware

# Создаем таблицы в БД.
# Если база данных не существует (например, файл sql_app.db), она будет создана.
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
    "*" # Опционально, если не уверены в источнике
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 💡 РЕГИСТРАЦИЯ СТАТИЧЕСКОЙ ПАПКИ 
# Путь /static/images/ будет обслуживать содержимое папки 'uploaded_images'
app.mount("/static/images", StaticFiles(directory="uploaded_images"), name="static_images")


# Подключаем роуты для товаров
app.include_router(
    items.router, 
    prefix="/api/v1/items", 
    tags=["Items (Products)"]
)

# 💡 ПОДКЛЮЧАЕМ РОУТЫ ДЛЯ ЗАГРУЗКИ ФАЙЛОВ
app.include_router(
    uploads.router, 
    prefix="/api/v1", 
    tags=["File Uploads"]
)

# Подключаем роуты для категорий (используют фиксированный список)
app.include_router(
    categories.router, 
    prefix="/api/v1", 
    tags=["Categories"]
)

# Подключаем роуты для заказов
app.include_router(
    orders.router, 
    prefix="/api/v1", 
    tags=["orders"]
)
