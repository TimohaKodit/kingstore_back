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
import json
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from typing import List

# Базовый класс для моделей
from app.db.base import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    price = Column(Float)
    is_active = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # 💡 ИЗМЕНЕНИЕ: Используем скрытый столбец для хранения списка URL как JSON-строки
    # Это позволяет хранить List[str] в одном столбце типа String.
    _image_urls = Column('image_urls', String, nullable=True, default='[]') 

    # Отношения с другими таблицами
    variants = relationship("ItemVariant", back_populates="item", cascade="all, delete-orphan")
    category = relationship("Category", back_populates="items")
    
    # 💡 @hybrid_property: Позволяет работать с полем как с List[str] в Python-коде
    @hybrid_property
    def image_urls(self) -> List[str]:
        """Преобразует JSON-строку в список при чтении (GET)."""
        if self._image_urls:
            try:
                # json.loads() всегда возвращает str, dict, list (т.е. [] или None)
                return json.loads(self._image_urls) or []
            except json.JSONDecodeError:
                return []
        return []

    @image_urls.setter
    def image_urls(self, urls: List[str]):
        """Преобразует список в JSON-строку при записи (POST/PUT)."""
        if urls is not None:
            self._image_urls = json.dumps(urls)
        else:
            self._image_urls = '[]'
            
    def __repr__(self):
        return f"<Item(name='{self.name}', price={self.price}, image_urls='{self.image_urls}')>"


class ItemVariant(Base):
    __tablename__ = "item_variants"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    memory = Column(String, nullable=True)
    color = Column(String, nullable=True)
    price_modifier = Column(Float, default=0.0)

    # Отношение к родительской модели Item
    item = relationship("Item", back_populates="variants")

