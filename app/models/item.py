from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey

from app.db.base import Base

class Item(Base):
    """Модель товара для базы данных."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    image_url = Column(String) 
    is_active = Column(Boolean, default=True) 
    
    # --- НОВЫЕ ПОЛЯ ---
    # Связь с категорией
    category_id = Column(Integer, nullable=False) 
    
    # Специфические поля для устройств
    memory = Column(String(50), nullable=True) # Пример: '64 GB', '256 GB'
    color = Column(String(50), nullable=True)  # Пример: 'Space Gray', 'Midnight'

    # Отношение к категории
    # <--- Добавили