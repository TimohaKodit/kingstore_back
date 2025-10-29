from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.category import Category as CategoryModel
from app.schemas.category import CategoryCreate

def get_category(db: Session, category_id: int) -> Optional[CategoryModel]:
    """Получить категорию по ID."""
    return db.query(CategoryModel).filter(CategoryModel.id == category_id).first()

def get_categories(db: Session, skip: int = 0, limit: int = 100) -> List[CategoryModel]:
    """Получить список всех категорий."""
    return db.query(CategoryModel).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate) -> CategoryModel:
    """Создать новую категорию."""
    db_category = CategoryModel(name=category.name)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category