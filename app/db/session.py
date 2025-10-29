from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# -------------------------------------------------------------------
# Условная инициализация Engine
# -------------------------------------------------------------------

# Проверяем, если строка подключения (DATABASE_URL) начинается с 'sqlite'
if settings.DATABASE_URL.startswith("sqlite"):
    # Настройки для SQLite (используется для локальной разработки)
    engine = create_engine(
        settings.DATABASE_URL,
        # Опция connect_args={"check_same_thread": False} КРИТИЧЕСКИ важна
        # для SQLite в многопоточных средах (как FastAPI/Uvicorn),
        # чтобы избежать ошибок
        connect_args={"check_same_thread": False},
        isolation_level="SERIALIZABLE" # Рекомендуется для SQLite
    )
else:
    # Настройки для PostgreSQL, MySQL и других удаленных БД (используется на хостинге)
    engine = create_engine(
        settings.DATABASE_URL,
        # Опция pool_pre_ping=True помогает поддерживать соединение 
        # с удаленной БД на хостинге живым
        pool_pre_ping=True
    )

# Создание фабрики сессий, которую мы будем использовать в зависимостях FastAPI
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Движок (engine) экспортируется для использования в main.py (для Base.metadata.create_all)
