from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base

# Указываем, что наша база данных будет простым файлом catalog.db
DATABASE_URL = "sqlite:///./catalog.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()

# Описываем таблицу "products"
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True) # Уникальный номер
    name = Column(String, index=True) # Название
    description = Column(String) # Описание
    price = Column(Float) # Цена
    image_url = Column(String) # Ссылка на картинку
    is_used = Column(Boolean, default=False) # Метка "б/у" (да/нет)

# Создаём эту таблицу в базе данных
Base.metadata.create_all(bind=engine)