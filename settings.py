import os
import json
import datetime
import logging

logger = logging.getLogger(__name__)
SETTINGS_FILE = 'user_settings.json'


def load_user_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            return {}
    return {}


def save_user_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False


def get_user_settings(user_id):
    settings = load_user_settings()
    user_id_str = str(user_id)
    if user_id_str not in settings:
        settings[user_id_str] = {
            'default_folder': 'personal',
            'personal_folder_name': f"user_{user_id}",
            'display_name': None,
            'telegram_name': "",
            'created_at': datetime.datetime.now().isoformat()
        }
        save_user_settings(settings)
    return settings[user_id_str]


def update_user_settings(user_id, new_settings):
    settings = load_user_settings()
    user_id_str = str(user_id)
    if user_id_str not in settings:
        settings[user_id_str] = {}
    settings[user_id_str].update(new_settings)
    settings[user_id_str]['updated_at'] = datetime.datetime.now().isoformat()
    return save_user_settings(settings)


def get_user_display_name(user_id, update=None):
    settings = get_user_settings(user_id)
    if settings.get('display_name'):
        return settings['display_name']
    if settings.get('telegram_name'):
        return settings['telegram_name']
    if update and update.effective_user:
        user = update.effective_user
        display_name = ""
        if user.first_name:
            display_name = user.first_name
        if user.last_name:
            if display_name:
                display_name += " "
            display_name += user.last_name
        if not display_name and user.username:
            display_name = user.username
        update_user_settings(user_id, {'telegram_name': display_name})
        return display_name
    return f"Пользователь {user_id}"
