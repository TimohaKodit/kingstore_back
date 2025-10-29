import os
import httpx
import logging
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# --- Настройка Логирования ---
logging.basicConfig(level=logging.INFO)

# --- Настройка Констант из config.py ---
# Используем try/except для импорта, чтобы этот файл можно было тестировать отдельно,
# но основной сценарий работы - импорт из main.py, где доступен app.core.config.
try:
    from app.core.config import settings
    BOT_TOKEN = settings.BOT_TOKEN
    ADMIN_ID = settings.ADMIN_ID
    API_URL = settings.API_URL
except ImportError:
    # Запасной вариант для локальной отладки bot.py напрямую. 
    # В этом случае нужно убедиться, что .env находится в корне проекта.
    load_dotenv() 
    logging.warning("Используются прямые os.getenv() для bot.py (нет доступа к app.core.config)")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID_RAW = os.getenv("ADMIN_ID")
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW and ADMIN_ID_RAW.isdigit() else 0
    API_URL = os.getenv("API_URL", "http://127.0.0.1:8888/api/v1")


# --------------------------------------------------------------------------------------
# --- 1. Инициализация Бота и Диспетчера ---
# --------------------------------------------------------------------------------------

if not BOT_TOKEN:
    # При деплое это критично, останавливаемся
    raise ValueError("BOT_TOKEN не найден. Проверьте переменную окружения.")
    
# Создаем объекты, которые будут импортированы в main.py
# DefaultBotProperties можно использовать для настройки режима парсинга по умолчанию
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()

# Добавьте ваш роутер в диспетчер
dp.include_router(router) 

# --------------------------------------------------------------------------------------
# --- 2. State Group (FSM) ---
# --------------------------------------------------------------------------------------

class ItemCreation(StatesGroup):
    """FSM для создания нового товара."""
    name = State()
    description = State()
    price = State()
    category_id = State()
    image_urls = State()
    
# --------------------------------------------------------------------------------------
# --- 3. Хэндлеры ---
# --------------------------------------------------------------------------------------

# Хэндлер на команду /start
@router.message(Command("start"))
async def command_start_handler(message: types.Message) -> None:
    """Обрабатывает команду /start."""
    await message.answer(
        f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
        f"Это бот-интерфейс для управления магазином Mini App.\n"
        f"Ваш ID: <code>{message.from_user.id}</code>. (Для получения прав админа, пропишите этот ID в `.env`)\n\n"
        f"Доступные команды:\n"
        f"/start - Начать взаимодействие\n"
        f"/add_item - Добавить новый товар (только для админа)"
    )

# Хэндлер на команду /add_item
@router.message(Command("add_item"))
async def command_add_item_handler(message: types.Message, state: FSMContext) -> None:
    """Запускает процесс добавления товара."""
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 У вас нет прав администратора для этой команды.")
        return

    await state.set_state(ItemCreation.name)
    await message.answer("➡️ Введите название нового товара:")


# Хэндлер для получения названия товара
@router.message(ItemCreation.name, F.text)
async def process_name(message: types.Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await state.set_state(ItemCreation.description)
    await message.answer("➡️ Введите краткое описание товара:")

# Хэндлер для получения описания товара
@router.message(ItemCreation.description, F.text)
async def process_description(message: types.Message, state: FSMContext) -> None:
    await state.update_data(description=message.text)
    await state.set_state(ItemCreation.price)
    await message.answer("➡️ Введите цену товара (целое число, в рублях):")

# Хэндлер для получения цены товара
@router.message(ItemCreation.price, F.text)
async def process_price(message: types.Message, state: FSMContext) -> None:
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Цена должна быть положительным целым числом. Попробуйте снова:")
        return

    await state.update_data(price=price)
    await state.set_state(ItemCreation.category_id)
    
    # 💡 Здесь в идеале нужно обращаться к API, чтобы получить актуальные категории.
    await message.answer(
        "➡️ Введите ID категории (например, 1, 2, 3). Если сомневаетесь, введите 1:"
    )

# Хэндлер для получения ID категории
@router.message(ItemCreation.category_id, F.text)
async def process_category_id(message: types.Message, state: FSMContext) -> None:
    try:
        category_id = int(message.text)
    except ValueError:
        await message.answer("❌ ID категории должен быть целым числом. Попробуйте снова:")
        return

    await state.update_data(category_id=category_id)
    await state.set_state(ItemCreation.image_urls)
    await message.answer(
        "➡️ Введите URL-ы изображений, разделенные запятой.\n"
        "Эти URL должны указывать на изображения, загруженные через API `/upload/images/`.\n"
        "Если изображений нет, введите <b>-</b> (прочерк)."
    )

# Хэндлер для получения URL изображений и отправки на API
@router.message(ItemCreation.image_urls, F.text)
async def process_image_urls(message: types.Message, state: FSMContext) -> None:
    raw_urls = message.text
    
    # Загружаем все данные FSM
    data = await state.get_data()
    
    # Обрабатываем URLs: если '-', то пустой JSON-массив, иначе - строка из URL
    image_urls_for_db = raw_urls if raw_urls.strip() != '-' else '[]'
    
    # Создаем минимальный SKU и variants_json, чтобы соответствовать схеме ItemCreate
    sku = f"SKU-{data['name'][:3].upper()}-{data['price']}"
    variants_json = '[{"memory": "256GB", "color": "Space Gray", "price_change": 0}]'
    
    item_data = {
        "name": data["name"],
        "description": data["description"],
        "price": data["price"],
        "category_id": data["category_id"],
        "image_urls_json": image_urls_for_db,
        "is_active": True,
        "sku": sku,
        "variants_json": variants_json
    }

    await message.answer("⏳ Отправляю данные товара на бэкенд...")

    # Отправка данных на FastAPI
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/items/",
                json=item_data
            )
            response.raise_for_status()
            
            # Парсим ответ для получения ID нового товара
            new_item = response.json()
            await message.answer(
                f"✅ Товар <b>{new_item['name']}</b> успешно добавлен!\n"
                f"ID: <code>{new_item['id']}</code>"
            )
        except httpx.HTTPStatusError as e:
             logging.error(f"Item creation failed: {e.response.text}")
             await message.answer(
                 f"❌ <b>Ошибка добавления товара</b>. Проверьте логи.\n"
                 f"Статус: {e.response.status_code}\n"
                 f"Ответ API: <code>{e.response.text}</code>"
             )
        except Exception as e:
            logging.error(f"API connection error: {e}")
            await message.answer(f"❌ Произошла ошибка: <code>{e}</code>")

    await state.clear()
