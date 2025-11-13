from sqlalchemy.orm import Session
from app.models.item import Item as ItemModel
from app.schemas.item import ItemCreate, ItemUpdate
from typing import List, Optional
from sqlalchemy import select
# --- Вспомогательные функции для работы с image_urls ---

# 1. Конвертирует список URL в строку для сохранения в БД
def _list_to_str(urls: List[str]) -> str:
    """Преобразует список URL в строку, разделенную запятыми, для хранения в базе данных."""
    # Убеждаемся, что все элементы - строки и объединяем их.
    return ",".join(str(url).strip() for url in urls) if urls else ""

# 2. Конвертирует строку из БД обратно в список URL
def _str_to_list(url_str: Optional[str]) -> List[str]:
    """Преобразует строку URL из базы данных обратно в список."""
    if not url_str:
        return []
    # Фильтруем пустые строки, которые могут возникнуть из-за лишних запятых
    return [url.strip() for url in url_str.split(',') if url.strip()]

# ----------------------------------------------------------------------
# --- CRUD-операции ---
# ----------------------------------------------------------------------

def get_item(db: Session, item_id: int) -> Optional[ItemModel]:
    """Получить товар по ID."""
    return db.query(ItemModel).filter(ItemModel.id == item_id).first()

def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[ItemModel]:
    """
    Получает список всех товаров из базы данных.
    """
    # Используем SQLAlchemy 2.0 style select
    statement = select(ItemModel).offset(skip).limit(limit)
    
    # Выполняем запрос и возвращаем список объектов модели
    items = db.execute(statement).scalars().all()
    
    return items


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

def delete_item(db: Session, item_id: int) -> bool:
    """
    Удаляет товар из базы данных по ID.

    :param db: Сессия базы данных.
    :param item_id: ID удаляемого товара.
    :return: True, если товар был найден и удален, False в противном случае.
    """
    # Предполагается, что Item — это ваша модель SQLAlchemy
    from app.models.item import Item # Убедитесь, что эта строка соответствует вашему пути импорта
    
    db_item = db.query(Item).filter(Item.id == item_id).first()
    
    if db_item is None:
        return False # Товар не найден
        
    db.delete(db_item)
    db.commit()
    return True # Успешно удалено