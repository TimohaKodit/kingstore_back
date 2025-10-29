import os
import uuid
from typing import List

# 💡 НОВЫЙ ИМПОРТ: aiofiles для асинхронной работы с файлами
import aiofiles 
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Request

router = APIRouter()

# --- Конфигурация ---
# Директория для сохранения загруженных файлов (должна совпадать с main.py)
UPLOAD_FOLDER = "uploaded_images"
# Публичный префикс, по которому файлы обслуживаются (должен совпадать с main.py)
STATIC_BASE_PATH = "static/images"

# Убедимся, что папка для загрузки существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 
# --------------------


@router.post("/upload/images/", response_model=List[str], status_code=status.HTTP_201_CREATED)
async def upload_images(
    request: Request, # 💡 НОВОЕ: Получаем объект Request для определения базового URL
    files: List[UploadFile] = File(..., description="Список файлов изображений для загрузки")
):
    """
    Принимает список файлов, сохраняет их локально асинхронно и возвращает список полных URL-адресов.
    """
    uploaded_urls = []
    
    # Максимальное количество файлов для одной загрузки
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Максимальное количество файлов для одной загрузки: 5."
        )

    # Получаем базовый URL сервера (например, http://127.0.0.1:8888)
    base_url = str(request.base_url).rstrip('/')

    for file in files:
        # 1. Проверка расширения (добавлена проверка MIME-типа для надежности)
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        ext = os.path.splitext(file.filename)[1].lower()
        
        if file.content_type and not file.content_type.startswith('image/'):
             raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Неподдерживаемый MIME-тип файла: {file.content_type}. Ожидается изображение."
            )
        
        if ext not in allowed_extensions:
            # Если бот отправляет фото, расширение может быть пустым.
            # Если нет расширения, но это фото, мы примем его и добавим .jpg
            if file.content_type in ["image/jpeg", "image/jpg"] and not ext:
                ext = ".jpg"
            else:
                 raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Недопустимый тип файла: {file.filename}. Разрешены: {', '.join(allowed_extensions)}"
                )

        # 2. Генерируем уникальное имя файла
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        # 3. АСИНХРОННО сохраняем файл на диск
        try:
            # Используем aiofiles для неблокирующей записи
            async with aiofiles.open(file_path, "wb") as buffer:
                # Читаем из UploadFile по частям асинхронно и записываем
                while content := await file.read(1024 * 1024):  # Читаем чанками по 1MB
                    await buffer.write(content)
            
            # 4. Формируем ПОЛНЫЙ публичный URL
            # Используем базовый URL + публичный путь + имя файла
            public_url = f"{base_url}/{STATIC_BASE_PATH}/{unique_filename}"
            uploaded_urls.append(public_url)
            
        except Exception as e:
            # Логирование и возврат ошибки
            print(f"Ошибка сохранения файла {file.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Не удалось сохранить файл {file.filename}. Ошибка: {str(e)}"
            )
        finally:
            # В отличие от синхронного режима, здесь не нужно вручную закрывать file.file
            # Асинхронный цикл позаботится об этом.
            pass

    return uploaded_urls
