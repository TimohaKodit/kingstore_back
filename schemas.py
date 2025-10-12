from pydantic import BaseModel

class ProductBase(BaseModel):
    name: str
    price: float
    image_url: str
    is_used: bool

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int

    class Config:
        orm_mode = True
