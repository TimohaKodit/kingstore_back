# from pydantic import BaseModel, Field
# from typing import Optional

# # Импортируем схему категории для вложенности
# from .category import Category as CategorySchema 

# # Базовая схема
# class ItemBase(BaseModel):
#     name: str = Field(..., max_length=100)
#     description: Optional[str] = None
#     price: float = Field(..., gt=0)
#     image_url: Optional[str] = None
#     is_active: bool = True
    
#     # --- НОВЫЕ ПОЛЯ ---
#     category_id: int # ID категории, обязательное поле
#     memory: Optional[str] = None
#     color: Optional[str] = None

# # Схема для создания (POST запросы)
# class ItemCreate(ItemBase):
#     pass

# # Схема для обновления (PUT/PATCH запросы)
# class ItemUpdate(ItemBase):
#     name: Optional[str] = None
#     price: Optional[float] = None
#     category_id: Optional[int] = None # Теперь опционально при обновлении
#     # Все поля опциональны при обновлении

# # Схема для чтения (отправка клиенту)
# class Item(ItemBase):
#     id: int 
#     # Заменяем category_id на полный объект Category для удобства фронтенда
#     category: CategorySchema # <--- Полный объект категории

#     # Удаляем поля, которые теперь вложены в category
#     # category_id не нужно явно указывать, если мы используем `category`

#     class Config:
#         from_attributes = True

from pydantic import BaseModel, Field
from typing import Optional, List

# Импортируем схему категории
from .category import Category as CategorySchema 

# Базовая схема
class ItemBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    price: float = Field(..., ge=-1.0)
    # 💡 Изменили: Теперь это список URL-адресов, а не один URL
    image_urls: List[str] = Field(default_factory=list, description="Список URL-адресов изображений")
    is_active: bool = True
    
    category_id: int 
    memory: Optional[str] = None
    color: Optional[str] = None

# Схема для создания (POST запросы)
class ItemCreate(ItemBase):
    pass

# Схема для обновления (PUT/PATCH запросы)
class ItemUpdate(ItemBase):
    name: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None
    is_active: Optional[bool] = None 
    # image_urls теперь также опционально для обновления
    image_urls: Optional[List[str]] = Field(None, description="Список URL-адресов изображений")

# Схема для чтения (отправка клиенту)
class Item(ItemBase):
    id: int 
    category: CategorySchema 

    class Config:
        from_attributes = True

# ---------------------------------------------------------
# Схемы для Заказов (оставлены без изменений для контекста)
# ---------------------------------------------------------
class FrontendItemDetails(BaseModel):
    name: str
    price: float
    memory: Optional[str] = None
    color: Optional[str] = None

class OrderSubmission(BaseModel):
    fio: str = Field(..., description="ФИО клиента")
    phone: str = Field(..., description="Телефон клиента")
    email: str = Field(..., description="Почта клиента")
    telegram_username: Optional[str] = Field(None, description="Никнейм в Telegram")
    address: str = Field(..., description="Адрес доставки или 'Самовывоз'")
    comment: Optional[str] = Field(None, description="Комментарии к заказу")
    delivery_method: str = Field(..., description="Способ получения ('delivery' или 'pickup')")
    total_price: float = Field(..., description="Общая сумма заказа")
    items: List[FrontendItemDetails]

class ItemAdminList(BaseModel):
    """
    Схема для краткого вывода товаров для Админа. 
    Содержит только требуемые поля. Исключает вложенную Category.
    """
    id: int 
    name: str = Field(..., max_length=100)
    price: float = Field(..., gt=0)
    
    # Требуемые характеристики
    memory: Optional[str] = None
    color: Optional[str] = None
    
    # 💡 ВАЖНО: Мы не включаем:
    # - category: CategorySchema (избегаем ошибки 422)
    # - description, image_url, is_active (по вашему запросу)

    class Config:
        # Эта настройка позволяет Pydantic читать данные из SQLAlchemy модели
        from_attributes = True
