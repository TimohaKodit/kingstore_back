from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, schemas
from models import engine
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os



# --- Настройка соединения с БД ---
DATABASE_URL = "sqlite:///./catalog.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
models.Base.metadata.create_all(bind=engine)
# --- Конец настройки ---

app = FastAPI()
frontend_dir = os.path.join(os.path.dirname(__file__), "../frontend/dist")

if os.path.exists(frontend_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
else:
    print("⚠️ Frontend не найден. Собери его перед деплоем!")

# Разрешаем нашему frontend-приложению обращаться к этому серверу (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Для разработки. На проде надо указать URL Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# === НАШИ API-ЭНДПОИНТЫ ===

# 1. Получить список всех товаров
@app.get("/products/", response_model=list[schemas.Product])
def get_all_products(db: Session = Depends(get_db), search: str | None= None):
    products = db.query(models.Product).all()

    if search:
        search_term = f"%{search}%"
        products = db.query(models.Product).filter(
            or_(
                models.Product.name.ilike(search_term),
                models.Product.description.ilike(search_term)
            )
        ).all()
    return products

# 2. Создать новый товар
@app.post("/products/", response_model=schemas.Product)
def create_new_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    # В реальном проекте здесь нужна проверка, что это делает админ!
    db_product = models.Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

# 3. Изменить цену товара
@app.put("/products/{product_id}/price", response_model=schemas.Product)
def update_product_price(product_id: int, new_price: float, db: Session = Depends(get_db)):
    # В реальном проекте здесь нужна проверка, что это делает админ!
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    db_product.price = new_price
    db.commit()
    db.refresh(db_product)
    return db_product