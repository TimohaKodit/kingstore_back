# from fastapi import FastAPI
# from app.api.v1.endpoints import items
# # --- НОВЫЙ ИМПОРТ ---
# from app.api.v1.endpoints import categories 
# # Импортируем все модели, чтобы Base.metadata.create_all их нашел
# from app.db.base import Base 
# from app.db.session import engine 
# from app.models import item, category # <--- НОВЫЙ ИМПОРТ
# from fastapi.middleware.cors import CORSMiddleware
# from app.api.v1.endpoints import orders
# # Создаем таблицы в БД (включая новую таблицу 'categories'). 
# Base.metadata.create_all(bind=engine) 

# app = FastAPI(
#     title="Telegram Mini App Shop Backend",
#     version="1.0.0",
# )
# origins = [
#     "http://127.0.0.1:5500", # Порт вашего Live Server
#     "http://localhost:5500",
#     "http://127.0.0.1:8888",
#     "*" # Если вы не знаете, какой порт использует Telegram Mini App
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Подключаем роуты для товаров
# app.include_router(
#     items.router, 
#     prefix="/api/v1/items", 
#     tags=["Items (Products)"]
# )

# # --- ПОДКЛЮЧАЕМ НОВЫЕ РОУТЫ ДЛЯ КАТЕГОРИЙ ---
# app.include_router(
#     categories.router, 
#     prefix="/api/v1/categories", 
#     tags=["Categories"]
# )
# app.include_router(
#     orders.router, 
#     prefix="/api/v1",  # <-- Вот это нужно добавить!
#     tags=["orders"]
# )

from fastapi import FastAPI
from app.api.v1.endpoints import items
# --- ИМПОРТЫ РОУТЕРОВ ---
from app.api.v1.endpoints import categories 
from app.api.v1.endpoints import orders
# 💡 НОВЫЙ ИМПОРТ ДЛЯ ЗАГРУЗКИ ФАЙЛОВ
from app.api.v1.endpoints import uploads
# 💡 НОВЫЙ ИМПОРТ ДЛЯ РАЗДАЧИ СТАТИЧЕСКИХ ФАЙЛОВ
from fastapi.staticfiles import StaticFiles 
# 💡 НОВЫЙ ИМПОРТ ДЛЯ ПРАЙС-ЛИСТА
from app.api.v1.endpoints import price_list
# -------------------------

# Импортируем только те модели SQLAlchemy, которые мы используем
from app.db.base import Base 
from app.db.session import engine 
from app.models import item, category

from fastapi.middleware.cors import CORSMiddleware

# Создаем таблицы в БД.
Base.metadata.create_all(bind=engine) 

app = FastAPI(
    title="Telegram Mini App Shop Backend",
    version="1.0.0",
)

app.mount("/static/images", StaticFiles(directory="uploaded_images"), name="static_images")
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
app.include_router(
    price_list.router,
    prefix="/api/v1",
    tags=["Price List"]
)