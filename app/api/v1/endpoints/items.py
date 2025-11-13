from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from app.core.config import settings

# 💡 Импортируем схемы
from app.schemas.item import Item as ItemSchema, ItemCreate, ItemUpdate
from app.schemas.category import Category as CategorySchema 

# 💡 Импортируем модели
from app.dependencies import get_db
from app.models.category import Category as CategoryModel 
from app.models.item import Item as ItemModel 

# 🛑 Импортируем ВСЕ функции CRUD
from app.crud.item import get_items, get_item, create_item, update_item, delete_item

def _format_image_url(relative_url: Any) -> str:
    """Конвертирует относительный путь в абсолютный, с проверкой STATIC_URL."""
    if not isinstance(settings.STATIC_URL, str) or not settings.STATIC_URL:
        return ''
    base_url = settings.STATIC_URL.rstrip('/') + '/'
    if isinstance(relative_url, str):
        
        # Убираем возможный дубликат /static/ (если он есть в БД)
        if relative_url.startswith('/static/'):
            relative_url = relative_url.replace('/static/', '', 1).lstrip('/')
        
        # Убираем начальный слеш из относительного пути, чтобы избежать двойного слеша
        relative_url = relative_url.lstrip('/')
        
        # 🛑 ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Соединяем базовый URL и относительный путь
        # Пример: base_url (https://apkintim.duckdns.org/) + relative_url (images/файл.jpg)
        return f"{base_url}{relative_url}"
    return ''
def _get_image_urls(item: Any) -> List[str]:
    """
    Безопасно извлекает URL из ORM-объекта, проверяя и plural (image_urls), и singular (image_url).
    """
    
    # 1. Пытаемся получить желаемый plural name: image_urls
    raw_urls = getattr(item, 'image_urls', None)
    
    # 2. Если plural не найден или пуст, пробуем singular name: image_url
    if raw_urls is None or (isinstance(raw_urls, list) and len(raw_urls) == 0):
         raw_urls = getattr(item, 'image_url', None)
         
    # 3. Обработка: если найдена одна строка, оборачиваем ее в список
    if isinstance(raw_urls, str):
        # Если это одна строка, оборачиваем в список, чтобы соответствовать схеме
        return [raw_urls]
            
    # 4. Если это список, возвращаем его. Если None или другой тип, возвращаем пустой список.
    if isinstance(raw_urls, list):
        return raw_urls
    
    return []

# --- Вспомогательная функция для обогащения (Админ) ---
def _add_category_to_item(db_item: ItemModel, db: Session) -> ItemSchema:
    """Извлекает категорию, собирает полный словарь данных (Для Админа)."""
    
    category_data: Optional[CategoryModel] = db.query(CategoryModel).filter(
        CategoryModel.id == db_item.category_id
    ).first()
    
    category_schema: Optional[CategorySchema] = None
    if category_data:
        category_schema = CategorySchema.model_validate(category_data)
        
    item_data_dict = db_item.__dict__.copy()
    item_data_dict.pop('_sa_instance_state', None) 
    item_data_dict['category'] = category_schema 

    # 🛑 ФИКС: Используем безопасную функцию извлечения URL
    relative_urls = _get_image_urls(db_item)
    
    absolute_urls = []
    for url in relative_urls:
        if isinstance(url, str): 
            absolute_urls.append(_format_image_url(url))
            
    item_data_dict['image_urls'] = [url for url in absolute_urls if url]

    return ItemSchema.model_validate(item_data_dict)


def _process_item_data(item: Any) -> Dict[str, Any]:
    """
    (Клиентская функция)
    Обрабатывает данные одного товара, форматируя URL изображения.
    """
    
    item_dict = item.__dict__.copy() 
    item_dict.pop('_sa_instance_state', None)
    
    # 🛑 ФИКС: Используем безопасную функцию извлечения URL
    relative_urls = _get_image_urls(item)
    
    absolute_urls = []
    for url in relative_urls:
        if isinstance(url, str): 
            absolute_urls.append(_format_image_url(url))

    item_dict['image_urls'] = [url for url in absolute_urls if url]
    
    # 4. Удаляем ключ 'category', если он не был загружен (для Pydantic)
    if 'category' in item_dict:
        if item_dict['category'] is None or hasattr(item_dict['category'], '__dict__'):
            item_dict.pop('category', None)
            
    return item_dict

# --- Настройка роутера ---
router = APIRouter(
    prefix="/items",
    tags=["Items"],
)

# --- Роуты для Клиента (Telegram Mini App) ---
@router.get("/", response_model=List[ItemSchema])
def read_active_items(db: Session = Depends(get_db)):
    items = get_items(db) 
    formatted_items_as_dicts = [_process_item_data(item) for item in items]
    return [ItemSchema.model_validate(data) for data in formatted_items_as_dicts]

@router.get("/{item_id}", response_model=ItemSchema)
def read_item(item_id: int, db: Session = Depends(get_db)):
    item = get_item(db, item_id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    item_data_dict = _process_item_data(item)
    return ItemSchema.model_validate(item_data_dict)

# --- Роуты для Админа (сокращены для экономии места) ---
# ... (остальные роуты без изменений)
# Вы можете оставить их из предыдущей версии или убедиться, что они присутствуют.

@router.post("/", response_model=ItemSchema, status_code=status.HTTP_201_CREATED)
def create_item_endpoint(item: ItemCreate, db: Session = Depends(get_db)):
    new_item = create_item(db=db, item=item)
    return _add_category_to_item(new_item, db)

@router.put("/{item_id}", response_model=ItemSchema)
def update_item_endpoint(item_id: int, item: ItemUpdate, db: Session = Depends(get_db)):
    db_item = get_item(db, item_id=item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    updated_item = update_item(db=db, db_item=db_item, item_update=item)
    return _add_category_to_item(updated_item, db)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    success = delete_item(db, item_id=item_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Товар с ID {item_id} не найден.")
    return

@router.get("/all", response_model=List[ItemSchema])
def read_all_items_admin(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    items = get_items(db, skip=skip, limit=limit)
    return [_add_category_to_item(item, db) for item in items]