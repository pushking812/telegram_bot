import os
import json
import datetime
import logging
from constants import BASE_DOWNLOADS_DIR, COMMON_DIR

logger = logging.getLogger(__name__)
METADATA_FILE = 'file_metadata.json'


def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки метаданных: {e}")
            return {}
    return {}


def save_metadata(metadata):
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения метаданных: {e}")
        return False


def add_file_metadata(file_path, user_id, display_name, operation="upload", original_filename=None):
    metadata = load_metadata()

    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path

    folder_type = "personal"
    if file_path.startswith(COMMON_DIR):
        folder_type = "common"

    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    file_name = os.path.basename(file_path)

    metadata[rel_path] = {
        'user_id': user_id,
        'display_name': display_name,
        'filename': original_filename or file_name,
        'file_size': file_size,
        'upload_time': datetime.datetime.now().isoformat(),
        'folder_type': folder_type,
        'last_access': datetime.datetime.now().isoformat()
    }

    return save_metadata(metadata)


def update_file_access(file_path, user_id, display_name, operation="download"):
    metadata = load_metadata()

    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path

    if rel_path in metadata:
        metadata[rel_path]['last_access'] = datetime.datetime.now().isoformat()
        metadata[rel_path]['last_access_by'] = {
            'user_id': user_id,
            'display_name': display_name
        }
        metadata[rel_path]['access_count'] = metadata[rel_path].get('access_count', 0) + 1

    return save_metadata(metadata)


def get_file_metadata(file_path):
    metadata = load_metadata()
    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path
    return metadata.get(rel_path)


def delete_file_metadata(file_path):
    metadata = load_metadata()
    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path
    if rel_path in metadata:
        del metadata[rel_path]
    return save_metadata(metadata)
