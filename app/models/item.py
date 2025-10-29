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
