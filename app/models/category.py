from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base # Импортируем базовый класс

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)

    # 💡 ИСПРАВЛЕНИЕ: Явное определение рекурсивной связи
    # Мы используем 'back_populates' для явного связывания двух сторон.

    # 1. Связь "Многие-к-Одному" (many-to-one)
    #    'parent' - это объект родительской категории, к которому 
    #    принадлежит эта категория (через parent_id).
    parent = relationship(
        "Category",
        remote_side=[id], # Указывает, что 'id' - это удаленная сторона
        back_populates="subcategories" # Связь с 'subcategories'
    )

    # 2. Связь "Один-ко-Многим" (one-to-many)
    #    'subcategories' - это список дочерних объектов Category, 
    #    которые ссылаются на этот 'id'.
    subcategories = relationship(
        "Category",
        back_populates="parent", # Связь с 'parent'
        cascade="all, delete-orphan", # Обычная каскадная операция
        lazy="selectin" # Оставляем 'selectin', так как это надежный метод
    )

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"