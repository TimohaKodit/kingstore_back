import os
import uuid
import logging
from typing import List, Optional

# 💡 НОВЫЙ ИМПОРТ: aiofiles для асинхронной работы с файлами
import aiofiles 
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Request
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Конфигурация ---
# Директория для сохранения загруженных файлов (должна совпадать с main.py)
UPLOAD_FOLDER = "uploaded_images"
# Публичный префикс, по которому файлы обслуживаются (должен совпадать с main.py)
# STATIC_BASE_PATH = "static/images" # Нам больше не нужен этот путь в возвращаемом значении

# Убедимся, что папка для загрузки существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 
# --------------------

# Разрешенные типы файлов и расширения
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def check_file_extension(filename: str) -> Optional[str]:
    """Проверяет расширение файла и возвращает его в нижнем регистре."""
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
        if f".{ext}" in ALLOWED_EXTENSIONS:
            return f".{ext}"
    return None


@router.post("/upload/images/", response_model=List[str], status_code=status.HTTP_201_CREATED)
async def upload_images(
    request: Request,
    files: List[UploadFile] = File(..., description="Список файлов изображений для загрузки")
):
    """
    Принимает список файлов, сохраняет их локально асинхронно и возвращает список уникальных имен файлов.
    Эти имена файлов будут сохранены в БД как 'image_urls'.
    """
    uploaded_filenames = [] # 💡 ИЗМЕНЕНИЕ: Теперь храним только имена файлов
    
    if not files:
        raise HTTPException(status_code=400, detail="Необходимо загрузить хотя бы один файл.")
        
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Максимальное количество файлов для одной загрузки — 5."
        )

    for file in files:
        # Проверка размера (хотя UploadFile может быть большим, асинхронная проверка сложна. 
        # Доверяем фронтенду или проверяем после загрузки, но здесь пока просто проверка расширения)
        
        ext = check_file_extension(file.filename)
        if not ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недопустимый тип файла: {file.filename}. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 2. Генерируем уникальное имя файла
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        # 3. АСИНХРОННО сохраняем файл на диск
        try:
            # Важно: Сбрасываем указатель файла в начало, если он был прочитан ранее
            await file.seek(0) 
            # Используем aiofiles для неблокирующей записи
            async with aiofiles.open(file_path, "wb") as buffer:
                # Читаем из UploadFile по частям асинхронно и записываем
                while content := await file.read(1024 * 1024):  # Читаем чанками по 1MB
                    await buffer.write(content)
            
            # 4. Сохраняем ТОЛЬКО имя файла, которое будет добавлено в БД
            uploaded_filenames.append(unique_filename)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения файла {file.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Не удалось сохранить файл {file.filename}. Ошибка: {str(e)}"
            )
        finally:
            await file.close() # Закрываем UploadFile

    # 💡 ВОЗВРАЩАЕМ СПИСОК ИМЕН ФАЙЛОВ
    return JSONResponse(content=uploaded_filenames, status_code=status.HTTP_201_CREATED)
