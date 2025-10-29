from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Настройка движка и сессии
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False} # Только для SQLite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)