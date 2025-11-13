import os
import uuid
from typing import List
import aiofiles 
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Request
from urllib.parse import urlunparse # 💡 НОВЫЙ ИМПОРТ


router = APIRouter()

# --- Конфигурация ---
UPLOAD_FOLDER = "uploaded_images"
STATIC_BASE_PATH = "static/images"

os.makedirs(UPLOAD_FOLDER, exist_ok=True) 
# --------------------


@router.post("/upload/images/", response_model=List[str], status_code=status.HTTP_201_CREATED)
async def upload_images(
    request: Request,
    files: List[UploadFile] = File(..., description="Список файлов изображений для загрузки")
):
    """
    Принимает список файлов, сохраняет их локально асинхронно и возвращает список полных URL-адресов.
    """
    uploaded_urls = []
    
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Максимум 5 файлов за раз."
        )
        
    # 💡 ИСПРАВЛЕНИЕ 404: Формируем базовый URL (например, http://localhost:8888)
    # Это гарантирует, что даже если FE и BE на разных портах, ссылка будет работать.
    base_url = urlunparse((request.url.scheme, request.url.netloc, '', '', '', '')).rstrip('/')
    
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    
    for file in files:
        filename = file.filename
        
        # 1. Проверка расширения
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недопустимый тип файла: {filename}. Разрешены: {', '.join(allowed_extensions)}"
            )

        # 2. Генерируем уникальное имя файла
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        # 3. АСИНХРОННО сохраняем файл на диск
        try:
            async with aiofiles.open(file_path, "wb") as buffer:
                while content := await file.read(1024 * 1024):
                    await buffer.write(content)
            
            # 4. Формируем ПОЛНЫЙ публичный URL
            public_url = f"{base_url}/{STATIC_BASE_PATH}/{unique_filename}"
            uploaded_urls.append(public_url)
            
        except Exception as e:
            print(f"Ошибка сохранения файла {file.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Не удалось сохранить файл {file.filename}. Ошибка: {str(e)}"
            )
            
    return uploaded_urls
