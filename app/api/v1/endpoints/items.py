# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from typing import List

# from app.schemas.item import Item as ItemSchema, ItemCreate, ItemUpdate
# from app.models.item import Item as ItemModel
# from app.crud import item as crud_item
# from app.dependencies import get_db

# router = APIRouter()

# # --- Роуты для Клиента (Telegram Mini App) ---
# @router.get("/", response_model=List[ItemSchema])
# def read_active_items(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
#     """Получить список активных товаров (для отображения в приложении)."""
#     items = crud_item.get_active_items(db, skip=skip, limit=limit)
#     return items

# @router.get("/{item_id}", response_model=ItemSchema)
# def read_item(item_id: int, db: Session = Depends(get_db)):
#     """Получить конкретный товар по ID."""
#     db_item = crud_item.get_item(db, item_id=item_id)
#     if db_item is None:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return db_item

# # --- Роуты для Админа (Доступ должен быть ограничен!) ---
# @router.post("/", response_model=ItemSchema, status_code=201)
# def create_item(item: ItemCreate, db: Session = Depends(get_db)):
#     """Создать новый товар."""
#     return crud_item.create_item(db=db, item=item)

# @router.put("/{item_id}", response_model=ItemSchema)
# def update_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
#     """Обновить существующий товар."""
#     db_item = crud_item.get_item(db, item_id=item_id)
#     if db_item is None:
#         raise HTTPException(status_code=404, detail="Item not found")
#     return crud_item.update_item(db=db, db_item=db_item, item_update=item)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.item import Item as ItemSchema, ItemCreate, ItemUpdate
from app.models.item import Item as ItemModel # Импорт модели ORM
from app.schemas.category import Category as CategorySchema # Импорт схемы категории
from app.crud import item as crud_item
from app.dependencies import get_db

router = APIRouter()

# ----------------------------------------------------------------------
# --- Вспомогательные функции ---
# ----------------------------------------------------------------------

def _add_category_to_item(db_item: ItemModel) -> ItemSchema:
    """
    Преобразует модель ItemModel в схему ItemSchema, 
    добавляя вложенную схему Category.
    """
    # Создаем объект ItemSchema из ItemModel
    item_schema = ItemSchema.model_validate(db_item)
    
    # Заменяем category_id на вложенный объект Category
    if db_item.category:
        item_schema.category = CategorySchema.model_validate(db_item.category)
    else:
        # Если категории нет, может потребоваться установка Category = None или дефолтное значение
        # Однако Pydantic требует заполненного поля category в Item, если это не Optional
        # Предполагаем, что category_id обязателен, или схема Item.category должна быть Optional
        pass 
        
    return item_schema

# ----------------------------------------------------------------------
# --- Роуты для Клиента (Telegram Mini App) ---
# ----------------------------------------------------------------------

@router.get("/", response_model=List[ItemSchema])
def read_active_items(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    """Получить список активных товаров (для отображения в приложении)."""
    db_items = crud_item.get_active_items(db, skip=skip, limit=limit)
    # Обрабатываем список товаров, добавляя информацию о категории и список URL
    return [_add_category_to_item(item) for item in db_items]

@router.get("/{item_id}", response_model=ItemSchema)
def read_item(item_id: int, db: Session = Depends(get_db)):
    """Получить конкретный товар по ID."""
    db_item = crud_item.get_item(db, item_id=item_id)
    
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
        
    # Обрабатываем единственный товар
    return _add_category_to_item(db_item)

# ----------------------------------------------------------------------
# --- Роуты для Админа ---
# ----------------------------------------------------------------------

@router.post("/", response_model=ItemSchema, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Создать новый товар."""
    # item.image_urls содержит список имен файлов, переданный из Admin UI (получен из uploads.py)
    db_item = crud_item.create_item(db=db, item=item)
    return _add_category_to_item(db_item) # Возвращаем собранный Pydantic объект

@router.put("/{item_id}", response_model=ItemSchema)
def update_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    """Обновить существующий товар."""
    # item.image_urls содержит список имен файлов, если они были обновлены
    db_item = crud_item.update_item(db=db, item_id=item_id, item_in=item)
    
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
        
    return _add_category_to_item(db_item)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Удалить товар (деактивировать)."""
    db_item = crud_item.delete_item(db=db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}
