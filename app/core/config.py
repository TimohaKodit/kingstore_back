from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Класс для хранения настроек приложения."""
    DATABASE_URL: str
    BOT_TOKEN: str
    API_URL: str 
    ADMIN_ID: int 

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True

settings = Settings()