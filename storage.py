import os
import re
import uuid
import mimetypes
import requests
import logging
import time
from urllib.parse import urlparse

from constants import BASE_DOWNLOADS_DIR, COMMON_DIR, USERS_DIR
import metadata
import logs

logger = logging.getLogger(__name__)


def create_folder_structure():
    os.makedirs(BASE_DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(COMMON_DIR, exist_ok=True)
    os.makedirs(USERS_DIR, exist_ok=True)


def get_user_folder(user_id, folder_name=None):
    settings_folder = f"user_{user_id}" if folder_name is None else folder_name
    user_folder = os.path.join(USERS_DIR, settings_folder)
    os.makedirs(user_folder, exist_ok=True)
    return user_folder


def get_user_folder_path(user_id, folder_name=None):
    if folder_name is None:
        folder_name = f"user_{user_id}"
    return os.path.join(USERS_DIR, folder_name)


def get_user_default_folder(user_id):
    from settings import get_user_settings
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    personal_name = settings.get('personal_folder_name', f"user_{user_id}")
    if default_folder == 'common':
        return COMMON_DIR
    else:
        return get_user_folder(user_id, personal_name)


def get_unique_filename(directory, filename):
    if not os.path.exists(os.path.join(directory, filename)):
        return filename
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        if not os.path.exists(os.path.join(directory, new_filename)):
            return new_filename
        counter += 1


async def download_file_from_url(url, context, target_folder, user_id, display_name):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None, "Некорректная ссылка"

        filename = os.path.basename(parsed_url.path)
        if not filename or '.' not in filename:
            content_type = None
            try:
                response = requests.head(url, timeout=15)
                content_type = response.headers.get('content-type', '')
            except:
                pass
            extension = '.bin'
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    extension = ext
            filename = f"downloaded_{uuid.uuid4().hex[:8]}{extension}"

        filename = re.sub(r'[<>:\\"/\\|?*]', '_', filename)
        unique_filename = get_unique_filename(target_folder, filename)
        file_path = os.path.join(target_folder, unique_filename)

        # Повторные попытки скачивания с экспоненциальной задержкой
        max_retries = 3
        timeout_seconds = 120  # Максимальное время скачивания
        response = None
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, stream=True, timeout=timeout_seconds)
                response.raise_for_status()

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                break  # Успешное скачивание
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    # Экспоненциальная задержка: 5s, 10s, 15s
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"Попытка {attempt + 1}/{max_retries} скачивания {url} не удалась, ждем {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise

        actual_size = os.path.getsize(file_path)
        metadata.add_file_metadata(file_path, user_id, display_name, "upload", original_filename=filename)
        logs.add_log_entry(user_id, display_name, "upload", file_path, actual_size, {
            'source': 'url', 'url': url, 'original_filename': filename
        })
        return {
            'path': file_path,
            'filename': unique_filename,
            'original_filename': filename,
            'size': actual_size,
            'content_type': response.headers.get('content-type', 'unknown') if response else 'unknown',
            'url': url
        }, None
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла по ссылке {url}: {e}")
        if isinstance(e, requests.exceptions.Timeout):
            return None, f"⏱️ Истекло время ожидания. Сервер не отвечает быстро. Попробуйте позже."
        elif isinstance(e, requests.exceptions.ConnectionError):
            return None, f"📡 Ошибка соединения. Проверьте интернет или ссылку."
        else:
            return None, f"❌ Ошибка при скачивании: {str(e)}"
