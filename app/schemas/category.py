# from pydantic import BaseModel, Field
# from typing import List, Dict

# # --- Pydantic Схема Категории ---
# class CategoryBase(BaseModel):
#     name: str = Field(..., max_length=50)

# class Category(CategoryBase):
#     id: int

#     class Config:
#         from_attributes = True

# # -----------------------------------------------------------------
# # --- ЖЕСТКО ЗАДАННЫЙ СПИСОК КАТЕГОРИЙ (ЗАМЕНА БАЗЫ ДАННЫХ) ---
# # -----------------------------------------------------------------

# FIXED_CATEGORIES: List[Category] = [
#     Category(id=1, name="iPhone"),
#     Category(id=2, name="iPad"),
#     Category(id=3, name="Apple Watch"),
#     Category(id=4, name="AirPods"),
#     Category(id=5, name="Macbook"),
#     Category(id=6, name="Красота и уход"),
#     Category(id=7, name="Аксессуары"),
#     Category(id=8, name="Б/У товары"),
# ]

# # Удобный словарь для быстрого поиска категории по ID
# CATEGORY_MAP: Dict[int, Category] = {cat.id: cat for cat in FIXED_CATEGORIES}

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

# --- Pydantic Схема Категории (с поддержкой вложенности) ---

class Category(BaseModel):
    id: int
    name: str = Field(..., max_length=50)
    # Поле для рекурсивного отображения подкатегорий
    subcategories: List['Category'] = [] 

    class Config:
        from_attributes = True

# Обязательно для рекурсивных схем
Category.model_rebuild()