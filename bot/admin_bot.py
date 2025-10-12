import asyncio
import os
import requests
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

# === Загрузка переменных окружения ===
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
API_URL = os.getenv("API_URL")  # пример: http://127.0.0.1:8000/products/

if not BOT_TOKEN or not API_URL:
    raise ValueError("❌ Проверь .env — должны быть заданы BOT_TOKEN и API_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Временное хранилище состояния ---
product_data = {}

# --- Команда /start ---
@dp.message(Command("start"))
async def start(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ У тебя нет прав для добавления товаров.")

    await message.answer("Привет, админ! 🛍\nХочешь добавить товар? Напиши /add")

# --- Команда /add ---
@dp.message(Command("add"))
async def add_product(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Только администратор может добавлять товары.")

    product_data[message.from_user.id] = {"step": "name"}
    await message.answer("📝 Введи название товара:")

# --- Обрабатываем шаги добавления ---
@dp.message()
async def process_message(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return  # игнорируем сообщения других

    if user_id not in product_data:
        return await message.answer("Напиши /add чтобы добавить товар.")

    step = product_data[user_id]["step"]

    # === 1. Название ===
    if step == "name":
        product_data[user_id]["name"] = message.text
        product_data[user_id]["step"] = "price"
        return await message.answer("💰 Введи цену товара (в ₽):")

    # === 2. Цена ===
    if step == "price":
        try:
            price = float(message.text)
        except ValueError:
            return await message.answer("⚠️ Введи число, например: 4999")
        product_data[user_id]["price"] = price
        product_data[user_id]["step"] = "image"
        return await message.answer("🖼 Отправь ссылку на изображение товара:")

    # === 3. Картинка ===
    if step == "image":
        product_data[user_id]["image_url"] = message.text
        product_data[user_id]["step"] = "is_used"
        return await message.answer("♻️ Это Б/У товар? (да/нет)")

    # === 4. Б/У ===
    if step == "is_used":
        text = message.text.lower()
        is_used = text in ["да", "yes", "true", "1"]
        product_data[user_id]["is_used"] = is_used

        # Формируем данные для API
        data = {
            "name": product_data[user_id]["name"],
            "price": product_data[user_id]["price"],
            "image_url": product_data[user_id]["image_url"],
            "is_used": is_used
        }

        # Отправляем на backend
        try:
            response = requests.post(API_URL, json=data, timeout=15)

            if response.status_code == 200:
                await message.answer("✅ Товар успешно добавлен!")
            else:
                await message.answer(f"⚠️ Ошибка при добавлении товара (код {response.status_code})")
        except Exception as e:
            await message.answer(f"❌ Ошибка при подключении к серверу:\n{e}")

        del product_data[user_id]  # очищаем состояние


# === Запуск ===
async def main():
    print("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())