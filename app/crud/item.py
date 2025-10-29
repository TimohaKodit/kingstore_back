# from sqlalchemy.orm import Session
# from app.models.item import Item
# from app.schemas.item import ItemCreate, ItemUpdate
# from typing import List, Optional

# def get_item(db: Session, item_id: int) -> Optional[Item]:
#     """Получить товар по ID."""
#     return db.query(Item).filter(Item.id == item_id).first()

# def get_active_items(db: Session, skip: int = 0, limit: int = 100) -> List[Item]:
#     """Получить список активных товаров (для фронтенда)."""
#     return db.query(Item).filter(Item.is_active == True).offset(skip).limit(limit).all()

# def create_item(db: Session, item: ItemCreate) -> Item:
#     """Создать новый товар."""
#     db_item = Item(**item.model_dump())
#     db.add(db_item)
#     db.commit()
#     db.refresh(db_item)
#     return db_item

# def update_item(db: Session, db_item: Item, item_update: ItemUpdate) -> Item:
#     """Обновить существующий товар."""
#     update_data = item_update.model_dump(exclude_unset=True)
#     for key, value in update_data.items():
#         setattr(db_item, key, value)
    
#     db.add(db_item)
#     db.commit()
#     db.refresh(db_item)
#     return db_item

from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.item import Item as ItemModel
from app.schemas.item import ItemCreate, ItemUpdate

# ----------------------------------------------------------------------
# 💡 Вспомогательные функции для конвертации Image URLs
# ----------------------------------------------------------------------

# Разделитель: запятая (,) используется, как в исходном коде, 
# но для большей надежности рекомендуется использовать более сложный разделитель, например, "|||".
def _list_to_str(image_urls: List[str]) -> str:
    """Конвертирует список URL-адресов в строку, разделенную запятыми."""
    # Фильтруем пустые строки на всякий случай
    return ",".join(url.strip() for url in image_urls if url.strip())

def _str_to_list(image_urls_str: Optional[str]) -> List[str]:
    """Конвертирует строку, разделенную запятыми, обратно в список URL-адресов."""
    if not image_urls_str:
        return []
    # Удаляем пробелы и фильтруем пустые строки
    return [url.strip() for url in image_urls_str.split(',') if url.strip()]

# ----------------------------------------------------------------------
# --- CRUD-операции ---
# ----------------------------------------------------------------------

def get_item(db: Session, item_id: int) -> Optional[ItemModel]:
    """Получить товар по ID."""
    return db.query(ItemModel).filter(ItemModel.id == item_id).first()

def get_active_items(db: Session, skip: int = 0, limit: int = 100) -> List[ItemModel]:
    """Получить список активных товаров."""
    return db.query(ItemModel).filter(ItemModel.is_active == True).offset(skip).limit(limit).all()

def create_item(db: Session, item: ItemCreate) -> ItemModel:
    """Создать новый товар, используя model_dump для автоматического сбора полей."""
    
    # 1. Преобразуем список URL в строку для сохранения в БД
    image_urls_str = _list_to_str(item.image_urls)
    
    # 2. 💡 Рефакторинг: Используем model_dump, чтобы автоматически получить все поля,
    # исключая 'image_urls' (которое является списком)
    item_data = item.model_dump(exclude={'image_urls'})

    # 3. Создаем модель, используя распакованные данные и добавляя строку URL
    db_item = ItemModel(
        **item_data,
        image_url=image_urls_str  # Сохраняем строку в правильное поле БД (image_url)
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, db_item: ItemModel, item_update: ItemUpdate) -> ItemModel:
    """Обновить существующий товар."""
    update_data = item_update.model_dump(exclude_unset=True)

    # 💡 ИСПРАВЛЕНИЕ: Обрабатываем обновление списка URL-адресов.
    if 'image_urls' in update_data:
        image_urls_list = update_data.pop('image_urls')
        # Преобразуем список URL в строку для сохранения в БД.
        # Заменяем Pydantic-ключ 'image_urls' на SQLAlchemy-ключ 'image_url'.
        update_data['image_url'] = _list_to_str(image_urls_list) 

    for key, value in update_data.items():
        # Устанавливаем атрибуты модели БД на основе данных обновления
        setattr(db_item, key, value)
        
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: int):
    """Удалить товар."""
    db_item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
        return {"ok": True}
    return None