from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
# 💡 УДАЛЕНЫ: joinedload и _get_category_query
from sqlalchemy.orm import Session
from sqlalchemy import asc 

# Импортируем Pydantic-схемы
from app.schemas.category import Category, CategoryCreate 
from app.dependencies import get_db

# Импортируем ORM-модели и CRUD
from app.models.category import Category as CategoryModel 
from app.crud import category as crud_category 

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)

@router.get("/", response_model=List[Category])
async def read_categories(db: Session = Depends(get_db)):
    """
    Возвращает список только родительских категорий. 
    Подкатегории загружаются автоматически благодаря lazy='selectin' в модели.
    """
    
    # 💡 ИСПРАВЛЕНИЕ: Простой запрос. Без joinedload.
    categories_from_db = db.query(CategoryModel).filter(
        CategoryModel.parent_id.is_(None)
    ).order_by(
        asc(CategoryModel.id) 
    ).all()

    if not categories_from_db:
        raise HTTPException(
            status_code=status.HTTP_4_NOT_FOUND, 
            detail="В базе данных нет доступных категорий."
        )
    
    # Pydantic (благодаря from_attributes) увидит поле .subcategories 
    # и выполнит lazy="selectin" для их загрузки.
    return categories_from_db

@router.get("/{category_id}", response_model=Category)
async def read_category(category_id: int, db: Session = Depends(get_db)):
    """Возвращает категорию по ее ID из БД, включая подкатегории."""
    
    # 💡 ИСПРАВЛЕНИЕ: Простой запрос.
    category = db.query(CategoryModel).filter(
        CategoryModel.id == category_id
    ).first()
    
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
        
    return category

@router.post("/", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(category: CategoryCreate, db: Session = Depends(get_db)):
    """Создание новой категории (Для Админа)."""
    
    db_category = crud_category.create_category(db=db, category=category)
    
    # Загружаем созданный объект (lazy="selectin" сработает при возврате)
    return db.query(CategoryModel).filter(CategoryModel.id == db_category.id).first()