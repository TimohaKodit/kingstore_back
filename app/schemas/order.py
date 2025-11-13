from pydantic import BaseModel, Field
from typing import List, Optional
# =========================================================
# НОВЫЕ СХЕМЫ ДЛЯ ПРИЕМА ДАННЫХ С ФРОНТЕНДА (SPA-магазина)
# =========================================================

class FrontendItemDetails(BaseModel):
    """Модель одного товара, как он приходит с JavaScript фронтенда."""
    name: str
    price: float
    memory: Optional[str] = None
    color: Optional[str] = None

class OrderSubmission(BaseModel):
    """Полная модель заказа, приходящая с фронтенда для отправки в чат-бот."""
    fio: str = Field(..., description="ФИО клиента")
    phone: str = Field(..., description="Телефон клиента")
    email: str = Field(..., description="Почта клиента") # Новое поле с фронтенда
    telegram_username: Optional[str] = Field(None, description="Никнейм в Telegram")
    address: str = Field(..., description="Адрес доставки или 'Самовывоз'")
    comment: Optional[str] = Field(None, description="Комментарии к заказу")
    delivery_method: str = Field(..., description="Способ получения ('delivery' или 'pickup')")
    payment_method: Optional[str] = Field(None, description="Способ оплаты")
    total_price: float = Field(..., description="Общая сумма заказа")
    items: List[FrontendItemDetails]

class OrderItemBase(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0) # Количество должно быть больше 0
    
class OrderItemCreate(OrderItemBase):
    pass

class OrderItem(OrderItemBase):
    id: int
    order_id: int
    
    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    # Данные, которые приходят с фронтенда
    user_id: int               # Telegram ID пользователя, который делает заказ
    full_name: str
    phone_number: str
    shipping_address: str
    items: List[OrderItemCreate] # Список товаров в заказе

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    status: str = "PENDING"
    
    class Config:
        from_attributes = True