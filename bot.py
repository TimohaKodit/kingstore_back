import os
import sys
import httpx
import logging
import asyncio
import io 
import re
from typing import List, Dict, Any
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, Message
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# --- Настройка Логирования ---
logging.basicConfig(level=logging.INFO)

# --- Настройка Констант из .env ---
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")

# Читаем ADMIN_ID. Используем 0 как безопасное, гарантированно невалидное ID по умолчанию, 
# если значение не найдено или не является числом.
ADMIN_ID_RAW = os.getenv("ADMIN_ID")
if ADMIN_ID_RAW:
    try:
        ADMIN_ID = int(ADMIN_ID_RAW)
    except ValueError:
        logging.error(f"Ошибка: Значение ADMIN_ID в .env ('{ADMIN_ID_RAW}') должно быть целым числом.")
        ADMIN_ID = 0
else:
    ADMIN_ID = 0

API_URL = os.getenv("API_URL", "http://127.0.0.1:8888/api/v1") 

# --- FSM States ---
class AddCategoryStates(StatesGroup):
    """Состояния для добавления категории."""
    waiting_for_name = State()

class AddAccessoryStates(StatesGroup):
    """Состояния для добавления простого товара (имя, цена, фото)."""
    waiting_for_price = State()
    waiting_for_photo = State() 
    
class AddItemStates(StatesGroup):
    """
    Состояния для добавления базового товара и его вариантов (СЛОЖНЫЙ ПОТОК).
    """
    waiting_for_name = State() # Ожидание базового названия
    waiting_for_category_id = State() # Ожидание ID категории
    waiting_for_flow_choice = State() # Выбор типа потока (сложный/простой)
    
    # Состояния для циклического ввода вариантов:
    waiting_for_variant_start = State() # Запуск или завершение цикла
    waiting_for_variant_memory = State()
    waiting_for_variant_colors_list = State() # Ожидание списка цветов
    
    # Состояния для циклического ввода Цены/Фото для каждого цвета
    waiting_for_color_price = State() 
    waiting_for_color_photo = State() 
    waiting_for_description = State()
    

class DeleteItemStates(StatesGroup):
    """Состояния для удаления товара."""
    waiting_for_item_id = State()
    
class UpdateItemPriceStates(StatesGroup):
    """Состояния для изменения цены товара."""
    waiting_for_item_id = State()
    waiting_for_new_price = State()

class PriceUpdateStates(StatesGroup):
    waiting_for_file = State()

# --- Вспомогательные Функции и Роутер ---
router = Router()

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором."""
    return user_id == ADMIN_ID

async def get_categories(client: httpx.AsyncClient) -> list:
    """Получить список категорий с бэкенда."""
    try:
        response = await client.get(f"{API_URL}/categories/")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logging.error(f"Error fetching categories: {e}")
        return []

async def get_items(client: httpx.AsyncClient) -> list:
    """Получить список товаров с бэкенда."""
    try:
        response = await client.get(f"{API_URL}/items/")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logging.error(f"Error fetching items: {e}")
        return []


def flatten_categories_for_bot(categories: List[Dict[str, Any]], prefix: str = "") -> Dict[str, str]:
    """
    Рекурсивно "расплющивает" дерево категорий в плоский словарь {id: "Name"}.
    Добавляет префикс "— " для вложенных элементов для красивого отображения.
    """
    category_map = {}
    for cat in categories:
        # Формируем отображаемое имя с отступом
        display_name = f"{prefix}{cat['name']}"
        
        # Добавляем родителя
        category_map[str(cat['id'])] = display_name
        
        # Рекурсивно обрабатываем детей
        if cat.get('subcategories'): # Используем .get() для безопасности
            child_prefix = f"{prefix}— " # Увеличиваем отступ
            flat_children = flatten_categories_for_bot(cat['subcategories'], child_prefix)
            category_map.update(flat_children)
            
    return category_map


ADMIN_START_TEXT = (
    "👋 Привет, Администратор!\n\n"
    "Доступные команды:\n"
    "[/add](/add) - 🚀 Добавить новый товар\n"
    "[/price](/price) - 💰 Изменить цену (поштучно)\n"
    "[/get_prices](/get_prices) - 📊 **Скачать Excel-прайс**\n"
    "[/update_prices](/update_prices) - 📈 **Загрузить Excel-прайс**\n"
    "[/delete](/delete) `ID` - ❌ Удалить товар по ID\n"
    "[/list_items](/list_items) - 📋 Показать список всех товаров\n"
    "[/cancel](/cancel) - ↩️ Отменить текущую операцию"
)

ADMIN_COMMANDS_TEXT = (
    "✅ **Операция завершена.**\n\n"
    "Что делаем дальше? Доступные команды:\n"
    "[/add](/add) - 🚀 Добавить новый товар\n"
    "[/price](/price) - 💰 Изменить цену (поштучно)\n"
    "[/get_prices](/get_prices) - 📊 **Скачать Excel-прайс**\n"
    "[/update_prices](/update_prices) - 📈 **Загрузить Excel-прайс**\n"
    "[/delete](/delete) `ID` - ❌ Удалить товар по ID\n"
    "[/list_items](/list_items) - 📋 Показать список всех товаров\n"
    "[/cancel](/cancel) - ↩️ Отменить текущую операцию"
)

async def send_admin_commands_list(message: types.Message):
    """
    Отправляет отформатированный список админ-команд 
    после успешной операции.
    """
    # Мы используем parse_mode="Markdown", так как он установлен по умолчанию для бота
    await message.answer(ADMIN_COMMANDS_TEXT)

# Клавиатура для начала/завершения добавления вариантов (СЛОЖНЫЙ ПОТОК)
KEYBOARD_VARIANT_CHOICE = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="➕ Добавить новый объем памяти", callback_data="add_variant"),
    ],
    [
        InlineKeyboardButton(text="✅ Завершить и сохранить товар", callback_data="finish_item"),
    ]
])

# Клавиатура для выбора потока
KEYBOARD_FLOW_CHOICE = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📱 Сложный товар (Память/Цвет)", callback_data="flow_complex")],
    [InlineKeyboardButton(text="🛠️ Простой товар (Аксессуар)", callback_data="flow_simple")],
])


# Кнопка для пропуска фото
KEYBOARD_SKIP_PHOTO = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏩ Пропустить фото")]],
    resize_keyboard=True, one_time_keyboard=True
)

# ----------------------------------------------------------------------
# --- 1. Обработка общих команд ---
# ----------------------------------------------------------------------
@router.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start и /help."""
    if 'ADMIN_START_TEXT' not in globals():
        logging.error("ADMIN_START_TEXT не определена!")
        await message.answer("Произошла ошибка конфигурации.")
        return

    if is_admin(message.from_user.id):
        # ❗ Используем нашу новую константу
        await message.answer(ADMIN_START_TEXT) 
    else:
        await message.answer("Здравствуйте! Это бот магазина.")

@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущей операции и сброс состояния FSM."""
    if is_admin(message.from_user.id):
        current_state = await state.get_state()
        if current_state is None:
            await message.answer("Нет активных операций для отмены.")
            return

        # Удаляем Reply-клавиатуру, если она была активна
        await message.answer("Операция отменена.", reply_markup=types.ReplyKeyboardRemove()) 
        await state.clear()
    else:
        await message.answer("У вас нет прав для этой команды.")
        
# ----------------------------------------------------------------------
# --- 2. Добавление Категории (/кат_новую) ---
# ----------------------------------------------------------------------
# @router.message(Command("кат_новую"))
# async def cmd_add_category(message: types.Message, state: FSMContext):
#     if not is_admin(message.from_user.id):
#         await message.answer("У вас нет прав администратора.")
#         return
#     await message.answer("Введите название новой категории:")
#     await state.set_state(AddCategoryStates.waiting_for_name)

# @router.message(AddCategoryStates.waiting_for_name, F.text)
# async def process_category_name(message: types.Message, state: FSMContext):
#     category_name = message.text
#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.post(
#                 f"{API_URL}/categories/",
#                 json={"name": category_name}
#             )
#             response.raise_for_status()
#             await message.answer(f"✅ Категория '{category_name}' успешно добавлена (ID: {response.json()['id']}).")
#         except httpx.HTTPStatusError as e:
#             logging.error(f"Category creation failed: {e.response.text}")
#             await message.answer(f"❌ Ошибка добавления. Проверьте логи.")
#         except Exception as e:
#             logging.error(f"API connection error: {e}")
#             await message.answer(f"❌ Произошла ошибка при обращении к API.")
#     await state.clear()

# ----------------------------------------------------------------------
# --- 3. Добавление Товара (/товар_новый) --- 
# ----------------------------------------------------------------------

# ШАГ 1: Запрос базового имени
@router.message(Command("add"))
async def cmd_add_item(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    
    # Инициализируем хранилище вариантов и очищаем состояние
    await state.clear()
    await state.update_data(variants=[]) 
    await message.answer("Введите **базовое название** товара (например, 'iPhone 15 Pro' или 'Защитное стекло'):")
    await state.set_state(AddItemStates.waiting_for_name)

# ШАГ 2: Запрос категории
@router.message(AddItemStates.waiting_for_name, F.text)
async def process_item_name(message: types.Message, state: FSMContext):
    await state.update_data(base_name=message.text)
    async with httpx.AsyncClient() as client:
        categories = await get_categories(client)
        if not categories:
            await message.answer("❌ Нет доступных категорий. Сначала добавьте их.")
            await state.clear()
            return
        await state.update_data(base_name=message.text.strip())
    
    # ❗ ПЕРЕХОД К ЗАПРОСУ ОПИСАНИЯ
    await message.answer(
        "📝 **Введите полное описание товара.**\n"
        "Если описание не нужно, введите `-` (прочерк).",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="-")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    # Устанавливаем следующее состояние
    await state.set_state(AddItemStates.waiting_for_description)

@router.message(AddItemStates.waiting_for_description, F.text)
async def process_description(message: types.Message, state: FSMContext):
    """Шаг 3: Получение описания и запрос категории."""
    
    description_text = message.text.strip()
    
    # Если админ ввел '-', сохраняем None, иначе сохраняем текст
    final_description = description_text if description_text != '-' else None
    
    await state.update_data(description=final_description)
    
    # ❗ ЛОГИКА ЗАПРОСА КАТЕГОРИЙ (ПЕРЕНЕСЕНА СЮДА)
    async with httpx.AsyncClient() as client:
        # Убедитесь, что функция get_categories импортирована и работает
        categories = await get_categories(client) 
        
        if not categories:
            await message.answer("❌ Нет доступных категорий. Сначала добавьте их через API.")
            await state.clear()
            return
            
        # Формируем карту категорий
        category_map = flatten_categories_for_bot(categories)
        await state.update_data(category_map=category_map)
        
        # Формируем сообщение для админа
        # (Эта строка остается без изменений, т.к. category_map уже содержит красивые имена)
        category_names = "\n".join([f"ID: **{id}** -> {name}" for id, name in category_map.items()])
        await message.answer(
            f"Введите **ID категории** для товара:\n\n{category_names}",
            parse_mode='Markdown'
        )
        
    # Устанавливаем следующее состояние
    await state.set_state(AddItemStates.waiting_for_category_id)

# ШАГ 3: Выбор категории и ветвление потока (СЛОЖНЫЙ / ПРОСТОЙ)
@router.message(AddItemStates.waiting_for_category_id, F.text)
async def process_item_category(message: types.Message, state: FSMContext):
    category_id_str = message.text.strip()
    data = await state.get_data()
    category_map = data.get('category_map', {})
    
    if category_id_str not in category_map:
        await message.answer("❌ Неверный ID категории. Попробуйте снова.")
        return
    try:
        category_id = int(category_id_str)
        category_name = category_map[category_id_str]
        await state.update_data(category_id=category_id, category_name=category_name)
        
        await message.answer(
            f"Вы выбрали категорию: **{category_name}** (ID: {category_id}). \n"
            "Это **сложный** товар (с вариантами памяти и цвета) или **простой** (аксессуар)?"
            , reply_markup=KEYBOARD_FLOW_CHOICE
        )
        # Переходим в новое состояние, ожидая выбор потока
        await state.set_state(AddItemStates.waiting_for_flow_choice)
        
    except ValueError:
        await message.answer("❌ ID категории должен быть числом. Попробуйте снова.")

# ----------------------------------------------------------------------
# ПРОСТОЙ ПОТОК ДОБАВЛЕНИЯ ТОВАРА (АКСЕССУАР)
# ----------------------------------------------------------------------

@router.callback_query(AddItemStates.waiting_for_flow_choice, F.data == "flow_simple")
async def start_simple_flow(callback_query: types.CallbackQuery, state: FSMContext):
    """Запуск простого потока (аксессуар)."""
    await callback_query.answer("Запуск простого потока...")
    # Убираем кнопки в исходном сообщении
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.warning(f"Failed to remove markup: {e}")
        
    data = await state.get_data()
    await callback_query.message.answer(
        f"Товар: **{data['base_name']}** ({data['category_name']}). \n"
        "Введите **цену** для этого товара (напр., 50.99):"
    )
    await state.set_state(AddAccessoryStates.waiting_for_price)

@router.message(AddAccessoryStates.waiting_for_price, F.text)
async def process_accessory_price(message: types.Message, state: FSMContext):
    """Получение цены (или текста) и запрос фото."""
    data = await state.get_data()
    item_name = data.get('base_name', '').lower()
    price_input = message.text.replace(',', '.').strip()
    
    price_to_save = None

    # Проверяем, наш ли это особый товар
    is_special_item = item_name.startswith(('samsung', 'sony'))

    try:
        # Сначала пробуем конвертировать в число
        price = float(price_input)
        if price <= 0:
            raise ValueError("Цена должна быть положительной.")
        price_to_save = price
        
    except ValueError:
        # Если не получилось, и это особый товар, сохраняем как -1.0 (для "Под заказ")
        if is_special_item and len(price_input) > 1:
            price_to_save = -1.0 # "Магическое число"
            await state.update_data(custom_price_text=price_input) # Сохраняем сам текст
        else:
            # Если это обычный товар ИЛИ текст невалидный
            await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова.")
            return

    if price_to_save is not None:
        await state.update_data(accessory_price=price_to_save)
        
        await message.answer(
            f"Цена/Статус **'{price_input}'** сохранен. \n"
            f"Отправьте **одну фотографию** для аксессуара или нажмите 'Пропустить фото'.",
            reply_markup=KEYBOARD_SKIP_PHOTO
        )
        await state.set_state(AddAccessoryStates.waiting_for_photo)


@router.message(AddAccessoryStates.waiting_for_photo, F.photo | F.text)
async def process_accessory_photo(message: types.Message, state: FSMContext, bot: Bot):
    """Получение фото или пропускание для аксессуара и сохранение товара."""
    
    data = await state.get_data()
    item_name = data['base_name']
    
    uploaded_urls = []
    is_photo = message.photo and len(message.photo) > 0
    is_skip = message.text and message.text.strip() == "⏩ Пропустить фото"
    
    # УДАЛЯЕМ КЛАВИАТУРУ БЕЗОПАСНЫМ СПОСОБОМ
    await message.answer("...", reply_markup=types.ReplyKeyboardRemove()) 

    if is_photo:
        await message.answer(f"⏳ Загружаю фото для аксессуара '{item_name}'...")
        
        # --- ЛОГИКА ЗАГРУЗКИ ФОТОГРАФИИ НА СЕРВЕР ---
        photo_file = message.photo[-1]
        file_id = photo_file.file_id
        
        file_buffer = None
        try:
            file_info = await bot.get_file(file_id)
            file_buffer = io.BytesIO() 
            await bot.download_file(file_info.file_path, file_buffer)
            file_buffer.seek(0)
            
            # Имя файла для аксессуара
            filename = f"Accessory_{item_name.replace(' ', '_')}.jpg" 
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{API_URL}/upload/images/",
                    files={"files": (filename, file_buffer, 'image/jpeg')} 
                )
                response.raise_for_status()
                uploaded_urls = response.json() 
                
            await message.answer(f"✅ Фото для '{item_name}' успешно загружено!")
            
        except httpx.HTTPStatusError as e:
            logging.error(f"Upload failed: {e.response.text}")
            await message.answer(f"❌ Ошибка загрузки файла на сервер. Повторите фото.")
            await state.set_state(AddAccessoryStates.waiting_for_photo)
            await message.answer(f"Повторите фото для '{item_name}' или нажмите 'Пропустить фото'.", reply_markup=KEYBOARD_SKIP_PHOTO)
            return
        except Exception as e:
            logging.error(f"Bot file download error: {e}")
            await message.answer(f"❌ Произошла ошибка при загрузке файла: {e}")
            await state.set_state(AddAccessoryStates.waiting_for_photo)
            await message.answer(f"Повторите фото для '{item_name}' или нажмите 'Пропустить фото'.", reply_markup=KEYBOARD_SKIP_PHOTO)
            return
        finally:
            if file_buffer:
                file_buffer.close()
    
    elif is_skip:
        await message.answer(f"⏩ Фото для '{item_name}' пропущено.")
    else:
        # Если пришел не фото и не текст "Пропустить"
        await message.answer("❌ Ожидаю **фотографию** или нажатие кнопки 'Пропустить фото'. Пожалуйста, попробуйте снова.", reply_markup=KEYBOARD_SKIP_PHOTO)
        await state.set_state(AddAccessoryStates.waiting_for_photo)
        return
        
    # --- Сохранение простого товара ---
    price = data['accessory_price']
    
    item_data = {
        "name": item_name,
        "description": data.get('description'), # <-- ИСПРАВЛЕНО: Пустая строка
        "price": price,
        "category_id": data['category_id'],
        "memory": None, 
        "color": None,  
        "image_urls": uploaded_urls, # Сохраняем URL-ы, даже если список пуст
        "is_active": True
    }

    await message.answer("⏳ Сохраняю аксессуар...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{API_URL}/items/",
                json=item_data
            )
            response.raise_for_status()

            await message.answer(
                f"✅ Аксессуар '{item_name}' успешно добавлен!\n"
                f"ID: {response.json()['id']}, Цена: {price}"
            )
            await send_admin_commands_list(message)
    except httpx.HTTPStatusError as e:
        logging.error(f"Simple item creation failed: {e.response.text}")
        await message.answer(f"❌ Ошибка добавления аксессуара. Проверьте логи.")
    except Exception as e:
        logging.error(f"API connection error: {e}")
        await message.answer(f"❌ Произошла ошибка при обращении к API.")

    await state.clear()


# ----------------------------------------------------------------------
# СЛОЖНЫЙ ПОТОК ДОБАВЛЕНИЯ ТОВАРА (ТЕЛЕФОН)
# ----------------------------------------------------------------------

@router.callback_query(AddItemStates.waiting_for_flow_choice, F.data == "flow_complex")
async def start_complex_flow(callback_query: types.CallbackQuery, state: FSMContext):
    """Запуск сложного потока (с вариантами)."""
    await callback_query.answer("Запуск сложного потока...")
    # Убираем кнопки в исходном сообщении
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.warning(f"Failed to remove markup: {e}")
        
    # Переходим к циклическому добавлению вариантов (старая логика)
    await ask_for_next_variant_step(callback_query.message, state)


# ЦИКЛИЧЕСКАЯ ЛОГИКА ДОБАВЛЕНИЯ ВАРИАНТОВ (Остается без изменений)
async def ask_for_next_variant_step(message: types.Message, state: FSMContext):
    """Спрашивает, хочет ли админ добавить еще один объем памяти или завершить."""
    data = await state.get_data()
    variants_count = len(data.get('variants', []))
    
    summary = "\n".join([
        f"✅ {v.get('memory', 'БЕЗ ПАМЯТИ')} ({len(v.get('variants_details', []))} шт.)"
        for v in data.get('variants', [])
    ])
    
    if variants_count > 0:
        await message.answer(
            f"Текущие группы вариантов ({variants_count}):\n{summary}\n\n"
            f"Что вы хотите сделать дальше?",
            reply_markup=KEYBOARD_VARIANT_CHOICE
        )
        await state.set_state(AddItemStates.waiting_for_variant_start)
    else:
        # Если вариантов нет, сразу переходим к первому шагу
        await message.answer(
             "✅ Основная информация сохранена. Начните добавлять группы вариантов.\n"
             "**Группа #1**\nВведите **объем памяти** (напр., 256 GB). Если нет, введите `-`:"
        )
        await state.set_state(AddItemStates.waiting_for_variant_memory)


# Обработка колбэков: Добавить/Завершить
@router.callback_query(AddItemStates.waiting_for_variant_start, F.data == "add_variant")
async def start_next_variant(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    variants_count = len(data.get('variants', []))
    
    # Инициализируем данные для нового объема
    await state.update_data(current_variant={})
    
    await callback_query.message.answer(
        f"**Группа #{variants_count + 1}**\nВведите **объем памяти** (напр., 256 GB). Если нет, введите `-`:"
    )
    await state.set_state(AddItemStates.waiting_for_variant_memory)


@router.callback_query(AddItemStates.waiting_for_variant_start, F.data == "finish_item")
async def finish_item_creation(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    # Убираем кнопки в исходном сообщении, чтобы не было повторных нажатий
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None) 
    except Exception as e:
        logging.warning(f"Failed to remove markup: {e}")
    
    data = await state.get_data()
    all_variants = data.get('variants', [])
    
    if not all_variants:
        await callback_query.message.answer("❌ Нельзя сохранить товар без вариантов. Пожалуйста, добавьте хотя бы один объем памяти.")
        # Возвращаем состояние и клавиатуру
        await ask_for_next_variant_step(callback_query.message, state) 
        return
        
    await callback_query.message.answer("⏳ Сохраняю товар и все его варианты...")
    
    # 1. Разворачиваем все варианты в единый список для отправки
    final_items_to_send = []
    for group in all_variants:
        memory = group.get('memory')
        for detail in group.get('variants_details', []):
            final_items_to_send.append({
                "name": data['base_name'],
                "description": data.get('description'), # <-- ИСПРАВЛЕНО: Пустая строка
                "price": detail['price'],
                "category_id": data['category_id'],
                "memory": memory,
                "color": detail['color'],
                "image_urls": detail.get('image_urls', []), 
                "is_active": True
            })
    
    # 2. Отправляем каждый вариант по отдельности
    try:
        async with httpx.AsyncClient(timeout=30.0) as client: # Увеличим таймаут для загрузки
            final_response = None
            total_added = 0
            
            for item_data in final_items_to_send:
                response = await client.post(
                    f"{API_URL}/items/",
                    json=item_data
                )
                response.raise_for_status()
                final_response = response.json() 
                total_added += 1

            if total_added > 0:
                await callback_query.message.answer(
                    f"✅ Товар '{data['base_name']}' успешно добавлен ({total_added} вариантов)!\n"
                    f"Последний добавленный ID: {final_response['id']}"
                )
                await send_admin_commands_list(callback_query.message)
            else:
                await callback_query.message.answer("❌ Произошла ошибка: не удалось добавить ни один вариант.")
                 
    except httpx.HTTPStatusError as e:
        logging.error(f"Item creation failed: {e.response.text}")
        await callback_query.message.answer(f"❌ Ошибка добавления товара: {e.response.text}. Проверьте логи.")
    except Exception as e:
        logging.error(f"API connection error: {e}")
        await callback_query.message.answer(f"❌ Произошла ошибка при обращении к API.")

    await state.clear()


# Шаг 1: Получение объема памяти
@router.message(AddItemStates.waiting_for_variant_memory, F.text)
async def process_variant_memory(message: types.Message, state: FSMContext):
    memory_input = message.text.strip()
    memory = memory_input if memory_input != '-' else None
    
    # Сохраняем память и инициализируем список деталей
    await state.update_data(
        current_variant={
            'memory': memory, 
            'colors_list': [], 
            'variants_details': [], 
            'current_color_index': 0
        }
    )
    
    await message.answer(
        "**Введите все цвета** для этого объема памяти (напр., Space Gray, Black, Red). \n"
        "Разделяйте цвета **запятой**."
    )
    await state.set_state(AddItemStates.waiting_for_variant_colors_list)


# Шаг 2: Получение списка цветов и старт цикла Цена/Фото
@router.message(AddItemStates.waiting_for_variant_colors_list, F.text)
async def process_variant_colors_list(message: types.Message, state: FSMContext):
    colors_input = message.text.strip()
    
    # Разделение и очистка списка цветов
    colors_list = [c.strip() for c in colors_input.split(',') if c.strip()]
    
    if not colors_list:
        await message.answer("❌ Вы не ввели ни одного цвета. Попробуйте снова.")
        return
    
    data = await state.get_data()
    current_variant = data['current_variant']
    current_variant['colors_list'] = colors_list
    current_variant['variants_details'] = [] # Список для сохранения собранных деталей
    current_variant['current_color_index'] = 0 # Сброс индекса на случай перезапуска
    await state.update_data(current_variant=current_variant)
    
    # Начинаем цикл с первого цвета
    await ask_for_color_price(message, state)


# Асинхронная функция для запроса Цены и перехода к Фото
async def ask_for_color_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    current_variant = data['current_variant']
    colors_list = current_variant['colors_list']
    index = current_variant['current_color_index']
    
    if index >= len(colors_list):
        # Цикл завершен! Сохраняем группу и переходим к следующему объему
        variants = data.get('variants', [])
        # Создаем финальный объект группы
        group_to_save = {
            'memory': current_variant['memory'],
            'variants_details': current_variant['variants_details']
        }
        variants.append(group_to_save)
        
        await state.update_data(variants=variants, current_variant={})
        
        await message.answer(
            f"✅ Группа '{current_variant.get('memory', 'БЕЗ ПАМЯТИ')}' ({len(colors_list)} цветов) успешно завершена!"
        )
        # Спрашиваем, что делать дальше (цикл для нового объема)
        await ask_for_next_variant_step(message, state)
        return
    
    # Продолжаем цикл: запрашиваем цену для текущего цвета
    current_color = colors_list[index]
    await message.answer(
        f"**Ввод данных: {current_variant.get('memory', '-')}/{current_color}**\n"
        f"Введите **цену** для этого варианта (напр., 199.99):"
    )
    await state.set_state(AddItemStates.waiting_for_color_price)


@router.message(AddItemStates.waiting_for_color_price, F.text)
async def process_variant_price(message: types.Message, state: FSMContext):
    
    data = await state.get_data()
    item_name = data.get('base_name', '').lower()
    price_input = message.text.replace(',', '.').strip()
    
    price_to_save = None
    custom_text_to_save = None

    # Проверяем, наш ли это особый товар
    is_special_item = item_name.startswith(('samsung', 'sony'))

    try:
        # Сначала пробуем конвертировать в число
        price = float(price_input)
        if price <= 0:
            raise ValueError("Цена должна быть положительной.")
        price_to_save = price
        
    except ValueError:
        # Если не получилось, и это особый товар, сохраняем как -1.0 (для "Под заказ")
        if is_special_item and len(price_input) > 1:
            price_to_save = -1.0 # "Магическое число"
            custom_text_to_save = price_input # Сохраняем сам текст
        else:
            # Если это обычный товар ИЛИ текст невалидный
            await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова.")
            return

    if price_to_save is not None:
        current_variant = data['current_variant']
        index = current_variant['current_color_index']
        current_color = current_variant['colors_list'][index]
        
        # Сохраняем цену временно
        current_variant['temp_price'] = price_to_save
        # Если есть кастомный текст, тоже сохраняем
        if custom_text_to_save:
            current_variant['temp_custom_text'] = custom_text_to_save
            
        await state.update_data(current_variant=current_variant)
        
        # Запрашиваем фото
        await message.answer(
            f"**Фото для: {current_variant.get('memory', '-')}/{current_color}**\n"
            f"Отправьте **одну фотографию** или нажмите 'Пропустить фото'.",
            reply_markup=KEYBOARD_SKIP_PHOTO
        )
        await state.set_state(AddItemStates.waiting_for_color_photo)

# Шаг получения фотографии или пропуска
@router.message(AddItemStates.waiting_for_color_photo, F.photo | F.text)
async def  process_variant_photo(message: types.Message, state: FSMContext, bot: Bot):
    
    data = await state.get_data()
    current_variant = data['current_variant']
    index = current_variant['current_color_index']
    current_color = current_variant['colors_list'][index]

    
    uploaded_urls = []
    
    is_photo = message.photo and len(message.photo) > 0
    is_skip = message.text and message.text.strip() == "⏩ Пропустить фото"
    
    # УДАЛЯЕМ КЛАВИАТУРУ БЕЗОПАСНЫМ СПОСОБОМ
    await message.answer("...", reply_markup=types.ReplyKeyboardRemove()) 

    if is_photo:
        await message.answer(f"⏳ Загружаю фото для {current_color}...")
        
        # --- ЛОГИКА ЗАГРУЗКИ ФОТОГРАФИИ НА СЕРВЕР ---
        photo_file = message.photo[-1]
        file_id = photo_file.file_id
        
        file_buffer = None
        try:
            file_info = await bot.get_file(file_id)
            file_buffer = io.BytesIO() 
            await bot.download_file(file_info.file_path, file_buffer)
            file_buffer.seek(0)
            # Внимание: имя файла может быть любым, но важно, чтобы оно соответствовало формату FastAPI
            filename = f"{current_variant.get('memory', 'NoMem')}_{current_color.replace(' ', '_')}.jpg" 
            
            async with httpx.AsyncClient(timeout=30.0) as client: # Увеличим таймаут для загрузки
                response = await client.post(
                    f"{API_URL}/upload/images/",
                    # 'files' принимает кортеж: (filename, file_object, mime_type)
                    files={"files": (filename, file_buffer, 'image/jpeg')} 
                )
                response.raise_for_status()
                # Предполагаем, что бэкенд возвращает список URL-ов
                uploaded_urls = response.json() 
                
            await message.answer(f"✅ Фото для {current_color} успешно загружено!")
            
        except httpx.HTTPStatusError as e:
            logging.error(f"Upload failed: {e.response.text}")
            await message.answer(f"❌ Ошибка загрузки файла на сервер. Повторите фото.")
            # Возвращаем клавиатуру и состояние для повтора
            await state.set_state(AddItemStates.waiting_for_color_photo)
            await message.answer(f"Повторите фото для {current_color} или нажмите 'Пропустить фото'.", reply_markup=KEYBOARD_SKIP_PHOTO)
            return
        except Exception as e:
            logging.error(f"Bot file download error: {e}")
            await message.answer(f"❌ Произошла ошибка при загрузке файла: {e}")
            # Возвращаем клавиатуру и состояние для повтора
            await state.set_state(AddItemStates.waiting_for_color_photo)
            await message.answer(f"Повторите фото для {current_color} или нажмите 'Пропустить фото'.", reply_markup=KEYBOARD_SKIP_PHOTO)
            return
        finally:
            if file_buffer:
                file_buffer.close()
    
    elif is_skip:
        await message.answer(f"⏩ Фото для {current_color} пропущено.")
        
    else:
        # Если пришел не фото и не текст "Пропустить"
        await message.answer("❌ Ожидаю **фотографию** или нажатие кнопки 'Пропустить фото'. Пожалуйста, попробуйте снова.", reply_markup=KEYBOARD_SKIP_PHOTO)
        await state.set_state(AddItemStates.waiting_for_color_photo)
        return
    
    # --- 4. Сохранение варианта и переход к следующему цвету ---
    
    # Сохраняем собранный вариант
    variant_detail = {
        'color': current_color,
        'price': current_variant.get('temp_price'),
        'image_urls': uploaded_urls
        
    }
    current_variant['variants_details'].append(variant_detail)
    
    # Переход к следующему индексу
    current_variant['current_color_index'] += 1
    await state.update_data(current_variant=current_variant)
    
    # Продолжаем цикл: запрашиваем цену для следующего цвета или завершаем
    await ask_for_color_price(message, state)


# --- 4. Удаление Товара (/товар_удали) ---
@router.message(Command("delete_product"))
async def cmd_delete_item(message: types.Message, state: FSMContext):
    """Начало диалога удаления товара: вывод списка и запрос ID."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    async with httpx.AsyncClient() as client:
        items = await get_items(client)
        if not items:
            await message.answer("❌ В базе данных нет товаров для удаления.")
            await state.clear()
            return
            
        # Форматирование списка товаров
        item_list = "\n".join([f"ID: {item['id']} -> {item['name']} (Цена: {item['price']})" for item in items])
        await message.answer(
            f"Введите ID товара, который вы хотите **удалить безвозвратно**:\n\n{item_list}"
        )
        await state.set_state(DeleteItemStates.waiting_for_item_id)

@router.message(DeleteItemStates.waiting_for_item_id, F.text)
async def process_item_to_delete(message: types.Message, state: FSMContext):
    """Получение ID товара и отправка DELETE запроса на бэкенд."""
    try:
        item_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID товара должен быть числом. Попробуйте снова или введите /cancel.")
        return

    async with httpx.AsyncClient() as client:
        try:
            # Отправляем DELETE запрос
            response = await client.delete(f"{API_URL}/items/{item_id}")
            
            if response.status_code == 204:
                await message.answer(f"✅ Товар с ID: {item_id} успешно удален.")
            elif response.status_code == 404:
                await message.answer(f"❌ Товар с ID: {item_id} не найден.")
            else:
                response.raise_for_status()
            
        except httpx.HTTPStatusError as e:
            logging.error(f"Item deletion failed: {e.response.text}")
            await message.answer(f"❌ Ошибка удаления товара: {e.response.text}. Проверьте логи.")
        except Exception as e:
            logging.error(f"API connection error during deletion: {e}")
            await message.answer(f"❌ Произошла ошибка при обращении к API: {e}")

    await state.clear()


# --- 5. Изменение Цены Товара (/товар_цена) ---
@router.message(Command("price"))
async def cmd_update_price(message: types.Message, state: FSMContext):
    """Начало диалога изменения цены: вывод списка и запрос ID."""
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return

    async with httpx.AsyncClient() as client:
        items = await get_items(client)
        if not items:
            await message.answer("❌ В базе данных нет товаров для изменения цены.")
            await state.clear()
            return
            
        # Форматирование списка товаров с текущей ценой
        item_list = "\n".join([f"ID: {item['id']} -> {item['name']} (Текущая цена: {item['price']})" for item in items])
        
        await message.answer(
            f"Введите ID товара, цену которого вы хотите изменить:\n\n{item_list}"
        )
        await state.set_state(UpdateItemPriceStates.waiting_for_item_id)


@router.message(UpdateItemPriceStates.waiting_for_item_id, F.text)
async def process_item_id_for_price(message: types.Message, state: FSMContext):
    """Получение ID товара и запрос новой цены."""
    try:
        item_id = int(message.text.strip())
        
        # Проверим, что товар существует, запросив его у API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/items/{item_id}")
            response.raise_for_status() # Вызовет исключение, если товар не найден (404)
            
            current_item = response.json()
            
            await state.update_data(item_id=item_id, old_price=current_item['price'])
            
            await message.answer(
                f"Товар: **{current_item['name']}** (ID: {item_id}). Текущая цена: **{current_item['price']}**.\n"
                f"Введите новую цену (например, 1250.50):"
            )
            await state.set_state(UpdateItemPriceStates.waiting_for_new_price)
            
    except ValueError:
        await message.answer("❌ ID товара должен быть числом. Попробуйте снова или введите /cancel.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer(f"❌ Товар с ID: {item_id} не найден. Попробуйте снова.")
        else:
            logging.error(f"Error fetching item details: {e}")
            await message.answer(f"❌ Произошла ошибка при получении данных о товаре. Проверьте логи.")
        await state.clear() 
    except Exception as e:
        logging.error(f"API connection error: {e}")
        await message.answer(f"❌ Произошла ошибка при обращении к API.")
        await state.clear()


@router.message(UpdateItemPriceStates.waiting_for_new_price, F.text)
async def process_new_price(message: types.Message, state: FSMContext):
    """Получение новой цены и отправка PUT запроса на бэкенд."""
    try:
        new_price = float(message.text.replace(',', '.').strip())
        if new_price <= 0:
            await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова.")
            return
            
        data = await state.get_data()
        item_id = data['item_id']
        old_price = data['old_price']
        
        # Данные для отправки: только то, что меняем
        update_data = {"price": new_price}

        async with httpx.AsyncClient() as client:
            # Отправляем PUT запрос на эндпоинт обновления товара
            response = await client.put(
                f"{API_URL}/items/{item_id}",
                json=update_data
            )
            response.raise_for_status() 
            
            await message.answer(
                f"✅ Цена товара (ID: {item_id}) успешно обновлена.\n"
                f"Старая цена: **{old_price}**\n"
                f"Новая цена: **{new_price}**"
            )
            await send_admin_commands_list(message)
            
    except ValueError:
        await message.answer("❌ Цена должна быть числом. Попробуйте снова.")
    except httpx.HTTPStatusError as e:
        logging.error(f"Item update failed: {e.response.text}")
        await message.answer(f"❌ Ошибка обновления цены: {e.response.text}. Проверьте логи.")
    except Exception as e:
        logging.error(f"API connection error during price update: {e}")
        await message.answer(f"❌ Произошла ошибка при обращении к API: {e}")

    await state.clear()


# --- 6. Запуск Бота ---

async def main() -> None:
    """Инициализация и запуск бота."""
    if not BOT_TOKEN:
        logging.error("Ошибка: BOT_TOKEN не найден. Завершение работы.")
        return
        
    # КРИТИЧЕСКАЯ ПРОВЕРКА ADMIN_ID
    if ADMIN_ID == 0:
        logging.error("Ошибка: ADMIN_ID не найден или установлен неверно в .env. Установите ваш ID для работы административных команд. Завершение работы.")
        return

    # Используем DefaultBotProperties для установки parse_mode
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode="Markdown")
    ) 
    
    dp = Dispatcher()
    dp.include_router(router)
    
    logging.info("🚀 Бот запущен. Ожидание команд в Telegram...")
    await dp.start_polling(bot)


@router.message(Command(commands=["delete", "del"]))
async def delete_item_command(message: types.Message):
    """Обрабатывает команду /delete <item_id> для удаления товара."""
    
    # 1. Проверка на Админа
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Эта команда доступна только администратору.")
        return

    # 2. Извлечение ID
    try:
        # Ожидаемый формат: /delete 123
        item_id = int(message.text.split()[1].strip())
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат. Используйте: `/delete <ID_товара>`", parse_mode="Markdown")
        return

    # 3. Вызов API на удаление
    logging.info(f"Админ {ADMIN_ID} инициировал удаление товара ID: {item_id}")
    await message.answer(f"⏳ Попытка удаления товара ID: {item_id}...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{API_URL}/items/{item_id}",
            )
            
            if response.status_code == 204:
                await message.answer(f"✅ Товар ID **{item_id}** успешно удален из базы данных и больше не будет отображаться на сайте.", parse_mode="Markdown")
                await send_admin_commands_list(message)
            elif response.status_code == 404:
                await message.answer(f"⚠️ Товар ID **{item_id}** не найден в базе данных.", parse_mode="Markdown")
            else:
                logging.error(f"Ошибка API при удалении товара: {response.text}")
                await message.answer(f"❌ Неизвестная ошибка ({response.status_code}) при удалении товара ID **{item_id}**.", parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Ошибка подключения к API при удалении: {e}")
        await message.answer("❌ Произошла ошибка подключения к API.")

@router.message(Command("list_items"), F.from_user.id == ADMIN_ID)
async def admin_list_items_handler(message: types.Message):
    """
    Обработчик команды /list_items для администратора.
    Получает список всех товаров с ID, названием, ценой, памятью и цветом.
    """
    logging.info(f"Admin {message.from_user.id} requested item list.")
    
    # Используем асинхронный клиент httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Запрос к роуту /items/all
            response = await client.get(f"{API_URL}/items/all") 
            response.raise_for_status() # Вызывает исключение для 4xx/5xx ошибок

            # Ожидаем, что API вернет список объектов с полями: id, name, price, memory, color
            items_list: List[Dict[str, Any]] = response.json()
            
            if not items_list:
                await message.answer("ℹ️ **Список товаров пуст.**", parse_mode='Markdown')
                return

            # Форматирование списка товаров
            item_strings = []
            for item in items_list:
                # Извлекаем только нужные поля: ID, Название, Цена, Память, Цвет.
                # Описания, фото и статуса активности здесь нет.
                item_info = (
                    f"**ID:** `{item.get('id', 'N/A')}`\n"
                    f"**Название:** {item.get('name', 'N/A')}\n"
                    f"**Цена:** {item.get('price', 'N/A')} RUB\n"
                    # Характеристики. Если memory или color None, используем '—'
                    f"**Память:** {item.get('memory') or '—'}\n"
                    f"**Цвет:** {item.get('color') or '—'}"
                )
                item_strings.append(item_info)

            final_message = "📋 **Список всех товаров**:\n\n" + ("—"*20) + "\n\n" + "\n\n".join(item_strings)
            
            # Разбить сообщение, если оно слишком длинное (Telegram limit ~4096 символов)
            if len(final_message) > 4096:
                messages = [final_message[i:i + 4000] for i in range(0, len(final_message), 4000)]
                for msg in messages:
                    await message.answer(msg, parse_mode='Markdown')
            else:
                await message.answer(final_message, parse_mode='Markdown')

        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to fetch item list (HTTP error): {e.response.text}")
            await message.answer(f"❌ **Ошибка API** ({e.response.status_code}): Не удалось получить список товаров. Проверьте лог.", parse_mode='Markdown')
        except httpx.RequestError as e:
            logging.error(f"API connection error: {e}")
            await message.answer(f"❌ **Ошибка подключения к API:** Убедитесь, что бэкенд запущен и доступен по адресу: `{API_URL}/items/all`", parse_mode='Markdown')
        except Exception as e:
            logging.exception(f"An unexpected error occurred: {e}")
            await message.answer("❌ Произошла непредвиденная ошибка при обработке запроса.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем.")
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при запуске бота: {e}")


# --- ЭКСПОРТ EXCEL ---
@router.message(Command("get_prices"), F.from_user.id == ADMIN_ID)
async def cmd_get_prices(message: types.Message):
    await message.answer("⏳ Генерирую Excel-файл... Это может занять несколько секунд.")
    
    headers = {"X-Admin-Token": ADMIN_API_TOKEN}
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{API_URL}/price-list/download", headers=headers) 
            
            response.raise_for_status() # 💡 Улучшенная проверка статуса
            
            file_content = response.content 
            file_buffer = io.BytesIO(file_content)
            
            # 💡 Улучшенный парсинг имени файла из заголовка Content-Disposition
            content_disposition = response.headers.get("content-disposition", "filename=price_list.xlsx")
            filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
            filename = filename_match.group(1) if filename_match else "price_list.xlsx"

            await message.answer_document(
                FSInputFile(file_buffer, filename=filename),
                caption="✅ Ваш прайс-лист готов. \n\n"
                        "**Инструкция:**\n"
                        "1. Измените цены в колонке 'Цена (Редактировать)' (E).\n"
                        "2. Сохраните файл.\n"
                        "3. Вызовите /update_prices и отправьте этот файл."
            )

    except httpx.HTTPStatusError as e:
        # Логика для ошибки API (например, 403 Forbidden из-за неверного токена)
        await message.answer(f"❌ Ошибка API ({e.response.status_code}): {e.response.text}")
    except httpx.RequestError as e:
        logging.error(f"Error downloading price list: {e}")
        await message.answer(f"❌ Ошибка подключения к API: {e}")
    except Exception as e:
        logging.error(f"Error processing price list download: {e}")
        await message.answer(f"❌ Непредвиденная ошибка: {e}")

# --- ИМПОРТ EXCEL (/update_prices) ---
@router.message(Command("update_prices"), F.from_user.id == ADMIN_ID)
async def cmd_start_update_prices(message: types.Message, state: FSMContext):
    await message.answer(
        "**Загрузите измененный .xlsx файл прайс-листа.**\n\n"
        "Я обновлю цены в базе данных на основе колонок 'ID' и 'Цена'.\n"
        "Для отмены нажмите /cancel."
    )
    await state.set_state(PriceUpdateStates.waiting_for_file)

@router.message(PriceUpdateStates.waiting_for_file, F.document, F.from_user.id == ADMIN_ID)
async def process_price_file_upload(message: Message, state: FSMContext, bot: Bot):
    if not message.document.file_name.lower().endswith('.xlsx'): 
        await message.answer("❌ Неверный тип файла. Пожалуйста, загрузите файл `.xlsx`.")
        return

    await message.answer("⏳ Обрабатываю файл... Ожидайте.")
    
    file_buffer = io.BytesIO()
    try:
        # 1. Скачиваем файл из Telegram
        file_info = await bot.get_file(message.document.file_id)
        await bot.download_file(file_info.file_path, file_buffer)
        file_buffer.seek(0)
        
        # 2. Готовим и отправляем файл на API
        headers = {"X-Admin-Token": ADMIN_API_TOKEN}
        files_to_upload = {'file': (message.document.file_name, file_buffer, message.document.mime_type)}

        async with httpx.AsyncClient(timeout=120.0) as client: 
            response = await client.post(
                f"{API_URL}/price-list/upload",
                headers=headers,
                files=files_to_upload
            )
            
            response.raise_for_status() # 💡 Улучшенная проверка статуса
            
            data = response.json()
            await message.answer(
                f"✅ **Обновление завершено!**\n\n"
                f"Успешно обновлено: {data.get('updated', 0)}\n"
                f"Пропущено (ошибки): {data.get('skipped', 0)}\n"
            )
            if data.get('errors'):
                # Логируем ошибки
                logging.warning(f"Price list upload errors: {data['errors']}")
                await message.answer(f"Детали ошибок:\n{data['errors']}")
                
    except httpx.HTTPStatusError as e:
        logging.error(f"API Error processing file: {e.response.text}")
        await message.answer(f"❌ Ошибка API ({e.response.status_code}) при обработке файла: {e.response.text[:100]}...")
    except Exception as e:
        logging.error(f"Error processing price file upload: {e}")
        await message.answer(f"❌ Непредвиденная ошибка при загрузке файла: {e}")
    finally:
        file_buffer.close()
        await state.clear()
        # Предполагаем, что эта функция существует
        # await send_admin_commands_list(message)