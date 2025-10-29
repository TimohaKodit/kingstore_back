import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

# ИМПОРТИРУЕМ OrderSubmission - это модель, которая приходит с фронтенда!
from app.schemas.order import OrderSubmission, OrderCreate
from app.core.config import settings 

router = APIRouter()
logger = logging.getLogger(__name__)

# URL для отправки сообщений Telegram API
TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"

def format_order_message(order_data: OrderSubmission, order_id: int) -> str:
    """Форматирует сообщение о заказе для отправки администратору, используя OrderSubmission."""
    # Обратите внимание: сигнатура изменена на OrderSubmission
    
    items_list = ""
    for item in order_data.items:
        options = []
        if item.memory and item.memory != '-':
            options.append(item.memory)
        if item.color and item.color != '-':
            options.append(item.color)
        
        options_str = f" ({', '.join(options)})" if options else ""
        # Обратите внимание: item.price уже число, используем форматирование для читаемости
        items_list += f"— {item.name}{options_str} **{item.price:,.0f} ₽**\n" 
        
    delivery_str = "Доставка" if order_data.delivery_method == 'delivery' else "Самовывоз"
    comment_str = order_data.comment or "Нет"
    telegram_str = f"👤 Telegram: @{order_data.telegram_username.lstrip('@')}\n" if order_data.telegram_username else ""
    message = (
        f"🔔 *НОВЫЙ ЗАКАЗ* (ID: {order_id}) 🔔\n\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"👤 Клиент: {order_data.fio}\n" 
        f"📞 Телефон: `{order_data.phone}`\n" 
        f"📧 Почта: {order_data.email}\n" 
        f"{telegram_str}\n" # ВКЛЮЧАЕМ НИКНЕЙМ
        f"📦 Получение: {delivery_str}\n"
        f"🏠 Адрес: {order_data.address}\n\n"
        f"📝 Комментарий: {comment_str}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"*🛒 Товары (Итого: {len(order_data.items)} позиций):*\n{items_list}\n"
        f"💰 *ОБЩАЯ СУММА:* **{order_data.total_price:,.0f} ₽**"
    )
    return message


@router.post("/orders/submit", status_code=status.HTTP_201_CREATED) # ИЗМЕНЯЕМ URL на /orders/submit
async def submit_order(order: OrderSubmission): # ИЗМЕНЯЕМ ТИП НА OrderSubmission
    
    # 1. Генерация временного ID (в реальном проекте здесь сохраняется в БД)
    # Используем уникальный ID на основе хэша
    new_order_id = abs(hash(order.phone + order.fio)) % 100000 

    # 2. Форматирование и отправка сообщения администратору
    try:
        message_text = format_order_message(order, new_order_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TELEGRAM_API_URL,
                json={
                    "chat_id": settings.ADMIN_ID, 
                    "text": message_text,
                    "parse_mode": "Markdown"
                }
            )
            response.raise_for_status()
            logger.info(f"Уведомление о заказе {new_order_id} отправлено админу.")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Ошибка отправки уведомления в Telegram: {e.response.text}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отправке уведомления: {e}")

    # 3. Возвращаем ответ фронтенду
    return {"message": "Заказ успешно оформлен", "order_id": new_order_id}