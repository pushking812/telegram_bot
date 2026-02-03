import os
import json
import datetime
import logging

logger = logging.getLogger(__name__)
LOG_FILE = 'file_transfer_log.json'


def load_logs():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки логов: {e}")
            return []
    return []


def save_logs(logs):
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения логов: {e}")
        return False


def add_log_entry(user_id, display_name, operation, file_path, file_size, details=None):
    logs = load_logs()
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'user_id': user_id,
        'display_name': display_name,
        'operation': operation,
        'file_path': file_path,
        'file_size': file_size,
        'details': details or {}
    }
    logs.append(log_entry)
    if len(logs) > 1000:
        logs = logs[-1000:]
    return save_logs(logs)
