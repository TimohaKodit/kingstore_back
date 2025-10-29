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
from typing import List, Any

# Импорты схем и моделей
from app.schemas.item import Item as ItemSchema, ItemCreate, ItemUpdate
from app.models.item import Item as ItemModel
# 💡 Импортируем CRUD-операции для товаров
from app.crud import item as crud_item 
from app.dependencies import get_db

# Импортируем карту фиксированных категорий
from app.schemas.category import CATEGORY_MAP 

router = APIRouter()

# ----------------------------------------------------------------------
# 💡 ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВНЕДРЕНИЯ КАТЕГОРИИ И ОБРАБОТКИ URL-АДРЕСОВ
# ----------------------------------------------------------------------
def _add_category_to_item(db_item: ItemModel) -> ItemSchema:
    """
    Преобразует объект ItemModel (SQLAlchemy) в ItemSchema (Pydantic),
    добавляя вложенный объект Category и конвертируя строку URL в список.
    """
    category_data = CATEGORY_MAP.get(db_item.category_id)
    
    if not category_data:
        print(f"ERROR: Item ID {db_item.id} has invalid category_id {db_item.category_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Invalid category ID in database for item {db_item.id}. Category ID: {db_item.category_id}"
        )

    # 💡 Конвертируем строку image_urls обратно в список List[str]
    image_urls_list = crud_item._str_to_list(db_item.image_url)
    
    # 2. Создаем Pydantic-схему, используя атрибуты SQLAlchemy объекта 
    #    и вручную внедряя 'category' и список 'image_urls'.
    item_data = db_item.__dict__.copy()
    
    # Заменяем строковое поле 'image_urls' на List[str]
    item_data['image_urls'] = image_urls_list 
    
    # Создаем Pydantic-объект
    return ItemSchema(
        **item_data, 
        category=category_data
    )

# ----------------------------------------------------------------------
# --- Роуты для Клиента (Telegram Mini App) ---
# ----------------------------------------------------------------------
@router.get("/", response_model=List[ItemSchema])
def read_active_items(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    """Получить список активных товаров (для отображения в приложении)."""
    db_items = crud_item.get_active_items(db, skip=skip, limit=limit)
    
    # Обрабатываем каждый товар для добавления вложенной категории и списка URL
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
    db_item = crud_item.create_item(db=db, item=item)
    return _add_category_to_item(db_item) # Возвращаем собранный Pydantic объект

@router.put("/{item_id}", response_model=ItemSchema)
def update_item(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    """Обновить существующий товар."""
    db_item = crud_item.get_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
        
    updated_item = crud_item.update_item(db=db, db_item=db_item, item_update=item)
    return _add_category_to_item(updated_item) # Возвращаем собранный Pydantic объект
