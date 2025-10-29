from fastapi import APIRouter, HTTPException
from typing import List
from sqlalchemy.orm import Session
from fastapi import Depends

# Импортируем фиксированные категории и Pydantic модель
from app.schemas.category import Category, FIXED_CATEGORIES, CATEGORY_MAP 
# NOTE: Для этого роутера больше не нужна база данных, поэтому Depends(get_db) удален

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)

@router.get("/", response_model=List[Category])
async def read_categories():
    """Возвращает жестко заданный список всех категорий."""
    return FIXED_CATEGORIES

@router.get("/{category_id}", response_model=Category)
async def read_category(category_id: int):
    """Возвращает категорию по ее фиксированному ID."""
    category = CATEGORY_MAP.get(category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category
