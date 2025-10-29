from app.db.session import SessionLocal

def get_db():
    """Зависимость для получения сессии базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()