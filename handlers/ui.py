import asyncio
import datetime
import os
import math
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from constants import COMMON_DIR
from settings import get_user_settings, get_user_display_name
from storage import get_user_folder
from metadata import get_file_metadata
from utils import format_size
from logs import load_logs

from .common import safe_edit_message

logger = logging.getLogger(__name__)


async def show_settings(update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    if user_id is None:
        user_id = update.effective_user.id
    try:
        if update is not None and hasattr(update, 'effective_user'):
            display_name = get_user_display_name(user_id, update)
        else:
            display_name = get_user_display_name(user_id)
    except Exception:
        display_name = get_user_display_name(user_id)
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    folder_name = settings.get('personal_folder_name', f'user_{user_id}')

    keyboard = [
        [
            InlineKeyboardButton("📁 Личная папка", callback_data='toggle_folder_personal'),
            InlineKeyboardButton("🌐 Общая папка", callback_data='toggle_folder_common')
        ],
        [
            InlineKeyboardButton("✏️ Изменить имя", callback_data='change_display_name'),
            InlineKeyboardButton("📝 Имя папки", callback_data='change_folder_name')
        ],
        [InlineKeyboardButton("🗑️ Очистить мою папку", callback_data='clear_personal_folder')],
        [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu'), InlineKeyboardButton("📊 Статистика", callback_data='stats_info')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    settings_local = get_user_settings(user_id)
    personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
    personal_folder = get_user_folder(user_id, personal_folder_name_local)
    personal_files = 0
    for _, _, filenames in os.walk(personal_folder):
        for f in filenames:
            personal_files += 1
    common_files = 0
    for _, _, filenames in os.walk(COMMON_DIR):
        for f in filenames:
            common_files += 1

    message_text = f"⚙️ Настройки пользователя\n\n"
    message_text += f"👤 Текущее имя: {display_name}\n"
    message_text += f"🆔 ID пользователя: {user_id}\n"
    message_text += f"📁 Имя папки: {folder_name}\n"
    message_text += f"📂 Папка загрузки по умолчанию: {'Личная папка' if default_folder == 'personal' else 'Общая папка'}\n\n"
    message_text += f"📊 Статистика:\n"
    message_text += f"• Файлов в личной папке: {personal_files}\n"
    message_text += f"• Файлов в общей папке: {common_files}\n\n"
    message_text += f"Выберите действие:"

    return message_text, reply_markup


async def show_files_list(update, context: ContextTypes.DEFAULT_TYPE, page=0, items_per_page=10, folder_type=None, user_id: int = None):
    if user_id is None:
        user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)

    if folder_type is None:
        settings = get_user_settings(user_id)
        folder_type = settings.get('files_view_mode', 'personal')

    if folder_type == 'common':
        target_folder = COMMON_DIR
        folder_name = "Общая папка"
    else:
        settings = get_user_settings(user_id)
        personal_folder_name = settings.get('personal_folder_name', f'user_{user_id}')
        target_folder = get_user_folder(user_id, personal_folder_name)
        folder_name = personal_folder_name

    context.user_data['current_folder_view'] = folder_type
    files = []
    try:
        for root, dirs, filenames in os.walk(target_folder):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                metadata = get_file_metadata(filepath)

                size = os.path.getsize(filepath)
                filesize = format_size(size)

                upload_info = "Неизвестно"
                if metadata:
                    upload_time = datetime.datetime.fromisoformat(metadata['upload_time'])
                    upload_str = upload_time.strftime("%d.%m.%Y %H:%M")
                    upload_info = f"{metadata.get('display_name', 'Неизвестно')} ({upload_str})"

                rel_path = os.path.relpath(filepath, target_folder)

                files.append({
                    'name': rel_path,
                    'size': filesize,
                    'full_path': filepath,
                    'folder_type': folder_type,
                    'upload_info': upload_info,
                    'metadata': metadata
                })
    except Exception as e:
        logging.getLogger(__name__).error(f"Ошибка при получении списка файлов: {e}")
        return None

    files.sort(key=lambda x: (
        datetime.datetime.fromisoformat(x['metadata']['upload_time'])
        if x['metadata'] and 'upload_time' in x['metadata']
        else datetime.datetime.min
    ), reverse=True)

    if not files:
        message_text = f"📂 Папка '{folder_name}' пуста.\n"
        message_text += "Отправьте файл или ссылку для загрузки."

        keyboard = [
            [InlineKeyboardButton("📁 Личная папка", callback_data='view_personal_files'), InlineKeyboardButton("🌐 Общая папка", callback_data='view_common_files')],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        return message_text, reply_markup

    total_pages = math.ceil(len(files) / items_per_page)
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_files = files[start_idx:end_idx]

    keyboard = []

    import hashlib
    for file_info in page_files:
        filename = file_info['name']
        filesize = file_info['size']
        upload_info = file_info['upload_info']

        max_name_len = 65
        if len(filename) > max_name_len:
            display_name = filename[:max_name_len-1] + "…"
        else:
            display_name = filename

        display_name_lines = display_name.split('\n')
        while len(display_name_lines) < 3:
            display_name_lines.append(" ")
        display_name = '\n'.join(display_name_lines[:3])

        upload_parts = upload_info.split(' (')
        author = upload_parts[0] if upload_parts else "Неизвестно"
        date_str = upload_parts[1].rstrip(')') if len(upload_parts) > 1 else ""

        params_text = f"{filesize} | {author} | {date_str}\n\n"

        file_id_hash = hashlib.sha1(file_info['full_path'].encode('utf-8')).hexdigest()
        try:
            context.bot_data.setdefault('file_map', {})
            context.bot_data['file_map'][file_id_hash] = file_info['full_path']
        except Exception:
            pass
        callback_data = f"file_send:{file_id_hash}:{page}:{folder_type}"

        file_row = [InlineKeyboardButton(f"📄 {display_name}", callback_data=callback_data), InlineKeyboardButton(f"💾 {params_text}", callback_data=callback_data)]
        keyboard.append(file_row)

    folder_buttons = [InlineKeyboardButton("📁 Личная папка", callback_data='view_personal_files'), InlineKeyboardButton("🌐 Общая папка", callback_data='view_common_files')]
    keyboard.append(folder_buttons)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"files_page:{page-1}:{folder_type}"))

    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="files_info"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"files_page:{page+1}:{folder_type}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = '\u200b'
    return message_text, reply_markup


async def show_logs(update, context: ContextTypes.DEFAULT_TYPE, page=0, items_per_page=10):
    logs = load_logs()

    if not logs:
        return "📊 Логи операций пусты.", None

    logs.sort(key=lambda x: x['timestamp'], reverse=True)

    total_pages = math.ceil(len(logs) / items_per_page)
    if page >= total_pages:
        page = total_pages - 1

    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_logs = logs[start_idx:end_idx]

    message_text = f"📊 Логи операций (страница {page+1}/{total_pages}):\n"
    message_text += f"Всего записей: {len(logs)}\n\n"

    for i, log in enumerate(page_logs, start=start_idx+1):
        timestamp = datetime.datetime.fromisoformat(log['timestamp'])
        time_str = timestamp.strftime("%d.%m.%Y %H:%M:%S")

        operation_icon = {'upload': '📤', 'download': '📥', 'delete': '🗑️', 'rename': '✏️'}.get(log['operation'], '📝')

        file_path = log['file_path']
        if len(file_path) > 30:
            file_path = "..." + file_path[-27:]

        message_text += f"{i}. {operation_icon} {log['operation'].upper()} - {log['display_name']}\n"
        message_text += f"   📄 {file_path}\n"
        message_text += f"   📦 {log['file_size']} байт\n"
        message_text += f"   🕒 {time_str}\n\n"

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"logs_page:{page-1}"))

    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="logs_info"))

    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"logs_page:{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🗑️ Очистить логи", callback_data="clear_logs"), InlineKeyboardButton("💾 Экспорт логов", callback_data="export_logs")])
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    return message_text, reply_markup


async def show_files_updated(query, context, page=0, folder_type=None):
    await asyncio.sleep(1)
    user_id = query.from_user.id
    result = await show_files_list(query, context, page, folder_type=folder_type, user_id=user_id)
    if result:
        message_text, reply_markup = result
        await safe_edit_message(query, message_text, reply_markup)


async def show_main_menu(update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает главное меню"""
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)

    keyboard = [
        [InlineKeyboardButton("Привет", callback_data='hello'), InlineKeyboardButton("Помощь", callback_data='help')],
        [InlineKeyboardButton("Информация", callback_data='info'), InlineKeyboardButton("Файлы", callback_data='files_list')],
        [InlineKeyboardButton("Настройки", callback_data='settings_menu'), InlineKeyboardButton("📊 Логи операций", callback_data='view_logs')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"Приветствую тебя, {display_name}! 🎉\nВыберите действие:\n\n"
        f"Вы можете отправить мне:\n"
        f"• Текстовое сообщение\n"
        f"• Файл (фото, документ, видео, аудио)\n"
        f"• Ссылку на файл для скачивания"
    )
    
    return message_text, reply_markup


async def start(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)

    keyboard = [
        [InlineKeyboardButton("Привет", callback_data='hello'), InlineKeyboardButton("Помощь", callback_data='help')],
        [InlineKeyboardButton("Информация", callback_data='info'), InlineKeyboardButton("Файлы", callback_data='files_list')],
        [InlineKeyboardButton("Настройки", callback_data='settings_menu'), InlineKeyboardButton("📊 Логи операций", callback_data='view_logs')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Приветствую тебя, {display_name}! 🎉\nВыберите действие:\n\n"
        f"Вы можете отправить мне:\n"
        f"• Текстовое сообщение\n"
        f"• Файл (фото, документ, видео, аудио)\n"
        f"• Ссылку на файл для скачивания",
        reply_markup=reply_markup
    )

__all__ = [
    'start', 'show_settings', 'show_files_list', 'show_logs', 'show_files_updated', 'show_main_menu'
]
