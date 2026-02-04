import datetime
import os
import logging
from telegram.ext import ContextTypes

from constants import BASE_DOWNLOADS_DIR, COMMON_DIR
from settings import get_user_settings, get_user_display_name
from metadata import get_file_metadata, load_metadata, save_metadata

logger = logging.getLogger(__name__)


async def safe_edit_message(query, text, reply_markup=None):
    try:
        if text is None:
            clean = ''
        else:
            clean = text.replace('\u200b', '').replace('\uFEFF', '').strip()

        if not clean:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        else:
            await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.exception(f"Ошибка при безопасном обновлении сообщения: {e}")
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception:
            pass


def get_user_default_folder(user_id: int, get_user_folder):
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    if default_folder == 'common':
        return COMMON_DIR
    else:
        return get_user_folder(user_id)


def update_file_access(filepath, user_id, display_name, operation):
    metadata = get_file_metadata(filepath)
    if metadata:
        if 'access_log' not in metadata:
            metadata['access_log'] = []

        metadata['access_log'].append({
            'user_id': user_id,
            'display_name': display_name,
            'operation': operation,
            'timestamp': datetime.datetime.now().isoformat()
        })

        metadata_dict = load_metadata()
        rel_path = os.path.relpath(filepath, BASE_DOWNLOADS_DIR)
        metadata_dict[rel_path] = metadata
        save_metadata(metadata_dict)
