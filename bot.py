import os
import sys
import httpx
import logging
import asyncio
import io 
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# --- ИМПОРТ ИЗ НАСТРОЕК ---
# Используем общие настройки приложения для доступа к токену и ID администратора
from app.core.config import settings 

# --- Настройка Логирования ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Константы ---
# Теперь берем из settings
BOT_TOKEN = settings.BOT_TOKEN
ADMIN_ID = settings.ADMIN_ID
# Внимание: API_URL здесь не используется, так как бот будет общаться с FastAPI 
# через Webhook, а FastAPI, в свою очередь, будет обращаться к базе данных.
API_URL = settings.API_URL # Оставим на всякий случай, если понадобится боту 

# --- Инициализация объектов Aiogram (глобальные, т.к. используются в main.py) ---
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher()
router = Router()

# --- Состояния для FSM ---
class ItemCreation(StatesGroup):
    """Состояния для добавления нового товара через бота."""
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_category_id = State()
    waiting_for_is_active = State()
    waiting_for_main_image_url = State()
    waiting_for_additional_images = State()
    waiting_for_memory_options = State()
    waiting_for_color_options = State()


# ----------------------------------------------------------------------
# --- Роуты Бота ---
# ----------------------------------------------------------------------

@router.message(Command("start"))
async def command_start_handler(message: types.Message) -> None:
    """
    Обрабатывает команду /start. 
    Показывает приветственное сообщение и кнопку для открытия Mini App.
    """
    # Создаем кнопку, которая открывает наше Mini App
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛍 Открыть Магазин", 
                # !!! ВАЖНО !!! URL здесь должен быть URL Mini App, 
                # который вы установили через @BotFather. 
                # Для теста используем API_URL, но его нужно заменить на реальный домен.
                web_app=types.WebAppInfo(url=f"{settings.WEBAPP_URL}")
            )
        ]
    ])

    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.full_name}!\n\n"
        "Это Telegram-магазин. Нажмите кнопку ниже, чтобы открыть каталог.",
        reply_markup=keyboard
    )
    
@router.message(Command("admin"))
async def command_admin_handler(message: types.Message) -> None:
    """
    Обрабатывает команду /admin. Показывает меню администратора (если это администратор).
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора.")
        return

    admin_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/add_item")],
            [KeyboardButton(text="/stats")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
    
    await message.answer(
        "🛠 *Меню Администратора* 🛠\nВыберите действие:",
        reply_markup=admin_keyboard,
        parse_mode="Markdown"
    )
