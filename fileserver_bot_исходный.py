import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
import logging
import os
import requests
import re
import mimetypes
import uuid
import json
from urllib.parse import urlparse
from pathlib import Path
import math
import asyncio

# Включаем логирование для отладки
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получите токен у @BotFather
TOKEN = "8448738318:AAEq_3qdExIJd3T_2iD6ZmnF6Z2KVVnlxDw"

# Пути к папкам
BASE_DOWNLOADS_DIR = 'downloads'
COMMON_DIR = os.path.join(BASE_DOWNLOADS_DIR, 'common')
USERS_DIR = os.path.join(BASE_DOWNLOADS_DIR, 'users')

# Файлы для хранения данных
SETTINGS_FILE = 'user_settings.json'
LOG_FILE = 'file_transfer_log.json'
METADATA_FILE = 'file_metadata.json'

# Создаем структуру папок
def create_folder_structure():
    """Создает необходимую структуру папок"""
    os.makedirs(BASE_DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(COMMON_DIR, exist_ok=True)
    os.makedirs(USERS_DIR, exist_ok=True)

# Создаем структуру папок при запуске
create_folder_structure()

# Функции для работы с метаданными файлов
def load_metadata():
    """Загружает метаданные файлов"""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки метаданных: {e}")
            return {}
    return {}

def save_metadata(metadata):
    """Сохраняет метаданные файлов"""
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения метаданных: {e}")
        return False

def add_file_metadata(file_path, user_id, display_name, operation="upload", original_filename=None):
    """Добавляет метаданные для файла"""
    metadata = load_metadata()
    
    # Получаем относительный путь для ключа
    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path
    
    # Определяем тип папки
    folder_type = "personal"
    if file_path.startswith(COMMON_DIR):
        folder_type = "common"
    
    # Получаем информацию о файле
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # Добавляем запись
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
    """Обновляет время последнего доступа к файлу"""
    metadata = load_metadata()
    
    # Получаем относительный путь
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
    """Получает метаданные файла"""
    metadata = load_metadata()
    
    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path
    
    return metadata.get(rel_path)

def delete_file_metadata(file_path):
    """Удаляет метаданные файла"""
    metadata = load_metadata()
    
    if file_path.startswith(BASE_DOWNLOADS_DIR):
        rel_path = os.path.relpath(file_path, BASE_DOWNLOADS_DIR)
    else:
        rel_path = file_path
    
    if rel_path in metadata:
        del metadata[rel_path]
    
    return save_metadata(metadata)

# Функции для работы с логами
def load_logs():
    """Загружает логи файловых операций"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки логов: {e}")
            return []
    return []

def save_logs(logs):
    """Сохраняет логи файловых операций"""
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения логов: {e}")
        return False

def add_log_entry(user_id, display_name, operation, file_path, file_size, details=None):
    """Добавляет запись в лог"""
    logs = load_logs()
    
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'user_id': user_id,
        'display_name': display_name,
        'operation': operation,  # upload, download, delete, rename, etc.
        'file_path': file_path,
        'file_size': file_size,
        'details': details or {}
    }
    
    logs.append(log_entry)
    
    # Ограничиваем размер лога (последние 1000 записей)
    if len(logs) > 1000:
        logs = logs[-1000:]
    
    return save_logs(logs)

# Функции для работы с настройками пользователей
def load_user_settings():
    """Загружает настройки пользователей из файла"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")
            return {}
    return {}

def save_user_settings(settings):
    """Сохраняет настройки пользователей в файл"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        return False

def get_user_settings(user_id):
    """Получает настройки пользователя"""
    settings = load_user_settings()
    user_id_str = str(user_id)
    
    if user_id_str not in settings:
        # Создаем настройки по умолчанию
        settings[user_id_str] = {
            'default_folder': 'personal',  # 'personal' или 'common'
            'personal_folder_name': f"user_{user_id}",
            'display_name': None,  # Пользовательское отображаемое имя
            'telegram_name': "",  # Имя из Telegram
            'created_at': datetime.datetime.now().isoformat()
        }
        save_user_settings(settings)
    
    return settings[user_id_str]

def update_user_settings(user_id, new_settings):
    """Обновляет настройки пользователя"""
    settings = load_user_settings()
    user_id_str = str(user_id)
    
    if user_id_str not in settings:
        settings[user_id_str] = {}
    
    settings[user_id_str].update(new_settings)
    settings[user_id_str]['updated_at'] = datetime.datetime.now().isoformat()
    
    return save_user_settings(settings)

def get_user_folder_path(user_id, folder_name=None):
    """Возвращает путь к папке пользователя по имени папки"""
    if folder_name is None:
        settings = get_user_settings(user_id)
        folder_name = settings.get('personal_folder_name', f"user_{user_id}")
    return os.path.join(USERS_DIR, folder_name)

def get_user_folder(user_id):
    """Возвращает путь к папке пользователя и создает ее если нет"""
    settings = get_user_settings(user_id)
    folder_name = settings.get('personal_folder_name', f"user_{user_id}")
    user_folder = os.path.join(USERS_DIR, folder_name)
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_default_folder(user_id):
    """Возвращает папку для загрузки по умолчанию"""
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    
    if default_folder == 'common':
        return COMMON_DIR
    else:
        return get_user_folder(user_id)

def get_user_display_name(user_id, update=None):
    """Возвращает отображаемое имя пользователя"""
    settings = get_user_settings(user_id)
    
    # Если есть пользовательское отображаемое имя
    if settings.get('display_name'):
        return settings['display_name']
    
    # Если есть имя из Telegram в настройках
    if settings.get('telegram_name'):
        return settings['telegram_name']
    
    # Если передан update, пытаемся получить имя из Telegram
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
        
        # Сохраняем имя из Telegram
        update_user_settings(user_id, {'telegram_name': display_name})
        return display_name
    
    # По умолчанию возвращаем user_id
    return f"Пользователь {user_id}"

# Функция для получения уникального имени файла
def get_unique_filename(directory, filename):
    """Возвращает уникальное имя файла, добавляя индекс при необходимости"""
    if not os.path.exists(os.path.join(directory, filename)):
        return filename
    
    name, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        if not os.path.exists(os.path.join(directory, new_filename)):
            return new_filename
        counter += 1

# Функция для скачивания файла по ссылке
async def download_file_from_url(url, context, target_folder, user_id, display_name):
    """Скачивает файл по ссылке и сохраняет в указанную папку"""
    try:
        # Проверяем, является ли строка URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None, "Некорректная ссылка"
        
        # Получаем имя файла из URL или генерируем случайное
        filename = os.path.basename(parsed_url.path)
        if not filename or '.' not in filename:
            # Если нет имени или расширения, генерируем случайное имя
            content_type = None
            try:
                # Делаем HEAD запрос для получения типа контента
                response = requests.head(url, timeout=5)
                content_type = response.headers.get('content-type', '')
            except:
                pass
            
            # Определяем расширение по типу контента
            extension = '.bin'
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    extension = ext
            
            filename = f"downloaded_{uuid.uuid4().hex[:8]}{extension}"
        
        # Очищаем имя файла от небезопасных символов
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Получаем уникальное имя файла
        unique_filename = get_unique_filename(target_folder, filename)
        
        # Полный путь для сохранения
        file_path = os.path.join(target_folder, unique_filename)
        
        # Скачиваем файл
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Определяем размер файла
        file_size = int(response.headers.get('content-length', 0))
        
        # Сохраняем файл
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Получаем информацию о файле
        actual_size = os.path.getsize(file_path)
        
        # Добавляем метаданные
        add_file_metadata(file_path, user_id, display_name, "upload", original_filename=filename)
        
        # Добавляем запись в лог
        add_log_entry(user_id, display_name, "upload", file_path, actual_size, {
            'source': 'url',
            'url': url,
            'original_filename': filename
        })
        
        return {
            'path': file_path,
            'filename': unique_filename,
            'original_filename': filename,
            'size': actual_size,
            'content_type': response.headers.get('content-type', 'unknown'),
            'url': url
        }, None
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла по ссылке {url}: {e}")
        return None, f"Ошибка при скачивании файла: {str(e)}"

# Функция для проверки, является ли текст ссылкой
def is_url(text):
    """Проверяет, является ли текст ссылкой"""
    url_pattern = re.compile(
        r'^https?://'  # http:// или https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # домен
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # или IP
        r'(?::\d+)?'  # порт
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    # Также проверяем простые шаблоны
    simple_patterns = [
        r'^https?://\S+',
        r'^www\.\S+',
        r'^\S+\.(com|ru|org|net|info|io|edu|gov|mil|biz|name|museum|co|uk|de|fr|jp|it|cn|br|au|us|ca|eu)\S*'
    ]
    
    if url_pattern.match(text):
        return True
    
    for pattern in simple_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False

# Функция команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляем сообщение с инлайн-кнопками при команде /start"""
    # Получаем настройки пользователя
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    folder_name = settings.get('personal_folder_name', f'user_{user_id}')
    
    # Обновляем имя из Telegram, если его еще нет
    if update.effective_user and not settings.get('telegram_name'):
        user = update.effective_user
        telegram_name = ""
        if user.first_name:
            telegram_name = user.first_name
        if user.last_name:
            if telegram_name:
                telegram_name += " "
            telegram_name += user.last_name
        if not telegram_name and user.username:
            telegram_name = user.username
        
        update_user_settings(user_id, {'telegram_name': telegram_name})
    
    # Создаем инлайн-кнопки
    keyboard = [
        [
            InlineKeyboardButton("Привет", callback_data='hello'),
            InlineKeyboardButton("Помощь", callback_data='help')
        ],
        [
            InlineKeyboardButton("Информация", callback_data='info'),
            InlineKeyboardButton("Файлы", callback_data='files_list')
        ],
        [
            InlineKeyboardButton("Настройки", callback_data='settings_menu'),
            InlineKeyboardButton("Скачать по ссылке", callback_data='download_help')
        ],
        [
            InlineKeyboardButton("📊 Логи операций", callback_data='view_logs')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Текущие настройки пользователя
    folder_info = "📁 Ваша папка" if default_folder == 'personal' else "🌐 Общая папка"
    
    # Отправляем меню с кнопками
    if update.message:
        await update.message.reply_text(
            f"Hello World! 🎉\n"
            f"Привет, {display_name}!\n\n"
            f"{folder_info} выбрана для загрузки по умолчанию\n\n"
            "Вы можете отправить мне:\n"
            "• Текстовое сообщение\n"
            "• Файл (фото, документ, видео, аудио)\n"
            "• Ссылку на файл для скачивания",
            reply_markup=reply_markup
        )
        logger.info(f"Пользователь {user_id} ({display_name}) запустил бота")

# Функция для отображения настроек
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    folder_name = settings.get('personal_folder_name', f'user_{user_id}')
    current_display_name = settings.get('display_name') or settings.get('telegram_name') or f"Пользователь {user_id}"
    
    # Создаем клавиатуру настроек
    keyboard = [
        [
            InlineKeyboardButton(
                "📁 Личная папка" if default_folder == 'personal' else "📁 Личная папка",
                callback_data='toggle_folder_personal'
            ),
            InlineKeyboardButton(
                "🌐 Общая папка" if default_folder == 'common' else "🌐 Общая папка",
                callback_data='toggle_folder_common'
            )
        ],
        [
            InlineKeyboardButton("✏️ Изменить имя", callback_data='change_display_name'),
            InlineKeyboardButton("📝 Имя папки", callback_data='change_folder_name')
        ],
        [
            InlineKeyboardButton("🗑️ Очистить мою папку", callback_data='clear_personal_folder')
        ],
        [
            InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu'),
            InlineKeyboardButton("📊 Статистика", callback_data='stats_info')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Получаем статистику по папкам
    personal_folder = get_user_folder(user_id)
    personal_files = len([f for f in os.listdir(personal_folder) if os.path.isfile(os.path.join(personal_folder, f))])
    common_files = len([f for f in os.listdir(COMMON_DIR) if os.path.isfile(os.path.join(COMMON_DIR, f))])
    
    # Текст сообщения
    message_text = f"⚙️ Настройки пользователя\n\n"
    message_text += f"👤 Текущее имя: {current_display_name}\n"
    message_text += f"🆔 ID пользователя: {user_id}\n"
    message_text += f"📁 Имя папки: {folder_name}\n"
    message_text += f"📂 Папка загрузки по умолчанию: {'Личная папка' if default_folder == 'personal' else 'Общая папка'}\n\n"
    message_text += f"📊 Статистика:\n"
    message_text += f"• Файлов в личной папке: {personal_files}\n"
    message_text += f"• Файлов в общей папке: {common_files}\n\n"
    message_text += f"Выберите действие:"
    
    return message_text, reply_markup

# Функция для отображения списка файлов с пагинацией
async def show_files_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0, items_per_page=10, folder_type=None):
    """Показывает список файлов в выбранной папке с пагинацией"""
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)
    
    # Определяем, какую папку показывать
    if folder_type is None:
        # Используем настройки пользователя по умолчанию
        settings = get_user_settings(user_id)
        folder_type = settings.get('files_view_mode', 'personal')
    
    # Получаем путь к папке
    if folder_type == 'common':
        target_folder = COMMON_DIR
        folder_name = "Общая папка"
    else:
        target_folder = get_user_folder(user_id)
        settings = get_user_settings(user_id)
        folder_name = settings.get('personal_folder_name', f'user_{user_id}')
    
    # Сохраняем режим просмотра в контексте
    context.user_data['current_folder_view'] = folder_type
    
    # Получаем все файлы из папки с метаданными
    files = []
    try:
        for filename in os.listdir(target_folder):
            filepath = os.path.join(target_folder, filename)
            if os.path.isfile(filepath):
                # Получаем метаданные файла
                metadata = get_file_metadata(filepath)
                
                size = os.path.getsize(filepath)
                filesize = f"{size / 1024:.1f} КБ" if size < 1024*1024 else f"{size / (1024*1024):.1f} МБ"
                
                # Форматируем информацию о загрузке
                upload_info = "Неизвестно"
                if metadata:
                    upload_time = datetime.datetime.fromisoformat(metadata['upload_time'])
                    upload_str = upload_time.strftime("%d.%m.%Y %H:%M")
                    upload_info = f"{metadata.get('display_name', 'Неизвестно')} ({upload_str})"
                
                files.append({
                    'name': filename,
                    'size': filesize,
                    'full_path': filepath,
                    'folder_type': folder_type,
                    'upload_info': upload_info,
                    'metadata': metadata
                })
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов: {e}")
        return None
    
    # Сортируем файлы по дате загрузки (новые сначала)
    files.sort(key=lambda x: (
        datetime.datetime.fromisoformat(x['metadata']['upload_time']) 
        if x['metadata'] and 'upload_time' in x['metadata'] 
        else datetime.datetime.min
    ), reverse=True)
    
    # Если файлов нет
    if not files:
        message_text = f"📂 Папка '{folder_name}' пуста.\n"
        message_text += "Отправьте файл или ссылку для загрузки."
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "📁 Личная папка" if folder_type == 'personal' else "📁 Личная папка",
                    callback_data='view_personal_files'
                ),
                InlineKeyboardButton(
                    "🌐 Общая папка" if folder_type == 'common' else "🌐 Общая папка",
                    callback_data='view_common_files'
                )
            ],
            [InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        return message_text, reply_markup
    
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(files) / items_per_page)
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_files = files[start_idx:end_idx]
    
    # Создаем клавиатуру
    keyboard = []
    
    # Добавляем кнопки для файлов
    for file_info in page_files:
        filename = file_info['name']
        filesize = file_info['size']
        upload_info = file_info['upload_info']
        
        # Обрезаем длинные имена файлов
        display_name = filename
        if len(display_name) > 25:
            display_name = display_name[:22] + "..."
        
        # Форматируем текст кнопки
        button_text = f"📄 {display_name} ({filesize})\n👤 {upload_info}"
        callback_data = f"file_send:{filename}:{page}:{folder_type}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Добавляем кнопки навигации между папками
    folder_buttons = []
    folder_buttons.append(
        InlineKeyboardButton(
            "📁 Личная папка" if folder_type == 'personal' else "📁 Личная папка",
            callback_data='view_personal_files'
        )
    )
    folder_buttons.append(
        InlineKeyboardButton(
            "🌐 Общая папка" if folder_type == 'common' else "🌐 Общая папка",
            callback_data='view_common_files'
        )
    )
    keyboard.append(folder_buttons)
    
    # Добавляем кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"files_page:{page-1}:{folder_type}"))
    
    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="files_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"files_page:{page+1}:{folder_type}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка для возврата в главное меню
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Текст сообщения
    message_text = f"📁 {folder_name} (страница {page+1}/{total_pages}):\n"
    message_text += f"Всего файлов: {len(files)}\n\n"
    message_text += "Нажмите на файл для отправки:\n"
    message_text += "📄 Имя файла (размер)\n👤 Кто загрузил (дата)\n"
    
    return message_text, reply_markup

# Функция для просмотра логов
async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0, items_per_page=10):
    """Показывает логи файловых операций"""
    logs = load_logs()
    
    if not logs:
        return "📊 Логи операций пусты.", None
    
    # Сортируем логи по времени (новые сначала)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Рассчитываем пагинацию
    total_pages = math.ceil(len(logs) / items_per_page)
    if page >= total_pages:
        page = total_pages - 1
    
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_logs = logs[start_idx:end_idx]
    
    # Формируем текст сообщения
    message_text = f"📊 Логи операций (страница {page+1}/{total_pages}):\n"
    message_text += f"Всего записей: {len(logs)}\n\n"
    
    for i, log in enumerate(page_logs, start=start_idx+1):
        timestamp = datetime.datetime.fromisoformat(log['timestamp'])
        time_str = timestamp.strftime("%d.%m.%Y %H:%M:%S")
        
        # Определяем иконку операции
        operation_icon = {
            'upload': '📤',
            'download': '📥',
            'delete': '🗑️',
            'rename': '✏️'
        }.get(log['operation'], '📝')
        
        # Обрезаем имя файла если слишком длинное
        file_path = log['file_path']
        if len(file_path) > 30:
            file_path = "..." + file_path[-27:]
        
        message_text += f"{i}. {operation_icon} {log['operation'].upper()} - {log['display_name']}\n"
        message_text += f"   📄 {file_path}\n"
        message_text += f"   📦 {log['file_size']} байт\n"
        message_text += f"   🕒 {time_str}\n\n"
    
    # Создаем клавиатуру
    keyboard = []
    
    # Добавляем кнопки пагинации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"logs_page:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="logs_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"logs_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Дополнительные кнопки
    keyboard.append([
        InlineKeyboardButton("🗑️ Очистить логи", callback_data="clear_logs"),
        InlineKeyboardButton("💾 Экспорт логов", callback_data="export_logs")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data='main_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    return message_text, reply_markup

# Функция отправки файла пользователю
async def send_file_to_user(chat_id, filepath, filename, context, user_id, display_name):
    """Отправляет файл пользователю"""
    try:
        # Проверяем размер файла (Telegram имеет ограничения)
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:  # 50 MB ограничение Telegram
            return False, "Файл слишком большой (максимум 50 МБ)"
        
        # Получаем метаданные файла
        metadata = get_file_metadata(filepath)
        
        # Определяем тип файла по расширению
        ext = os.path.splitext(filename)[1].lower()
        
        # Формируем подпись с информацией
        caption = f"📄 {filename}\n"
        if metadata:
            upload_time = datetime.datetime.fromisoformat(metadata['upload_time'])
            upload_str = upload_time.strftime("%d.%m.%Y %H:%M")
            caption += f"👤 Загрузил: {metadata.get('display_name', 'Неизвестно')}\n"
            caption += f"📅 Дата загрузки: {upload_str}\n"
            caption += f"📦 Размер: {metadata.get('file_size', file_size)} байт"
        
        # Открываем файл
        with open(filepath, 'rb') as file:
            # Отправляем файл в зависимости от типа
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=InputFile(file, filename=filename),
                    caption=caption
                )
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=InputFile(file, filename=filename),
                    caption=caption
                )
            elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=InputFile(file, filename=filename),
                    caption=caption
                )
            elif ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.zip', '.rar']:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(file, filename=filename),
                    caption=caption
                )
            else:
                # Для неизвестных типов отправляем как документ
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(file, filename=filename),
                    caption=caption
                )
        
        # Обновляем метаданные доступа
        update_file_access(filepath, user_id, display_name, "download")
        
        # Добавляем запись в лог
        add_log_entry(user_id, display_name, "download", filepath, file_size)
        
        logger.info(f"Файл {filename} отправлен пользователю {user_id} ({display_name})")
        return True, None
    except Exception as e:
        logger.error(f"Ошибка при отправке файла {filename}: {e}")
        return False, str(e)

# Обработчик нажатий инлайн-кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем нажатия инлайн-кнопок"""
    query = update.callback_query
    await query.answer()  # Обязательно! Подтверждаем нажатие
    
    user_id = query.from_user.id
    display_name = get_user_display_name(user_id, update)
    callback_data = query.data
    
    logger.info(f"Пользователь {user_id} ({display_name}) нажал: {callback_data}")
    
    try:
        # Обработка нажатия на файл
        if callback_data.startswith('file_send:'):
            # Извлекаем информацию о файле
            parts = callback_data.split(':')
            if len(parts) >= 4:
                filename = parts[1]
                page = int(parts[2])
                folder_type = parts[3]
                
                # Определяем путь к папке
                if folder_type == 'common':
                    filepath = os.path.join(COMMON_DIR, filename)
                else:
                    filepath = os.path.join(get_user_folder(user_id), filename)
                
                # Проверяем существование файла
                if not os.path.exists(filepath):
                    await query.message.reply_text(f"❌ Файл '{filename}' не найден.")
                    return
                
                # Проверяем доступ к файлу (для личной папки другого пользователя)
                if folder_type == 'personal':
                    # Извлекаем user_id из имени папки или пути
                    file_folder = os.path.dirname(filepath)
                    folder_user_id = None
                    try:
                        # Пытаемся получить user_id из имени папки
                        folder_name = os.path.basename(file_folder)
                        if folder_name.startswith('user_'):
                            folder_user_id = int(folder_name.split('_')[1])
                    except:
                        pass
                    
                    # Если файл из чужой личной папки
                    if folder_user_id and folder_user_id != user_id:
                        await query.message.reply_text("❌ У вас нет доступа к этому файлу.")
                        return
                
                # Отправляем сообщение о начале отправки
                status_msg = await query.message.reply_text(f"📤 Отправляю файл '{filename}'...")
                
                # Отправляем файл
                success, error = await send_file_to_user(
                    chat_id=query.message.chat_id,
                    filepath=filepath,
                    filename=filename,
                    context=context,
                    user_id=user_id,
                    display_name=display_name
                )
                
                # Удаляем сообщение о статусе
                await status_msg.delete()
                
                if not success:
                    await query.message.reply_text(f"❌ Ошибка при отправке файла: {error}")
                
                # Обновляем список файлов
                await show_files_updated(query, context, page, folder_type)
        
        # Обработка пагинации списка файлов
        elif callback_data.startswith('files_page:'):
            parts = callback_data.split(':')
            page = int(parts[1])
            folder_type = parts[2] if len(parts) > 2 else 'personal'
            result = await show_files_list(update, context, page, folder_type=folder_type)
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Обработка пагинации логов
        elif callback_data.startswith('logs_page:'):
            page = int(callback_data.split(':')[1])
            result = await show_logs(update, context, page)
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Просмотр личных файлов
        elif callback_data == 'view_personal_files':
            # Проверяем текущий режим просмотра
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'personal':
                # Уже в личной папке - просто подтверждаем нажатие
                await query.answer("Вы уже в личной папке")
                return
            
            result = await show_files_list(update, context, folder_type='personal')
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Просмотр общих файлов
        elif callback_data == 'view_common_files':
            # Проверяем текущий режим просмотра
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'common':
                # Уже в общей папке - просто подтверждаем нажатие
                await query.answer("Вы уже в общей папке")
                return
            
            result = await show_files_list(update, context, folder_type='common')
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Просмотр логов
        elif callback_data == 'view_logs':
            result = await show_logs(update, context)
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Очистка логов
        elif callback_data == 'clear_logs':
            if save_logs([]):
                await query.answer("✅ Логи очищены", show_alert=True)
            else:
                await query.answer("❌ Ошибка при очистке логов", show_alert=True)
            
            # Возвращаемся к просмотру логов
            result = await show_logs(update, context)
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Экспорт логов
        elif callback_data == 'export_logs':
            logs = load_logs()
            if logs:
                # Создаем текстовый файл с логами
                log_text = "📊 Логи файловых операций\n\n"
                for log in logs[-100:]:  # Последние 100 записей
                    timestamp = datetime.datetime.fromisoformat(log['timestamp'])
                    time_str = timestamp.strftime("%d.%m.%Y %H:%M:%S")
                    log_text += f"{time_str} - {log['operation']} - {log['display_name']}\n"
                    log_text += f"  Файл: {log['file_path']}\n"
                    log_text += f"  Размер: {log['file_size']} байт\n\n"
                
                # Отправляем как текстовый файл
                await query.message.reply_document(
                    document=InputFile.from_bytes(log_text.encode('utf-8'), filename='logs.txt'),
                    caption="📊 Экспорт логов операций"
                )
            else:
                await query.answer("Логи пусты", show_alert=True)
        
        # Обработка кнопки "Файлы"
        elif callback_data == 'files_list':
            result = await show_files_list(update, context)
            if result:
                message_text, reply_markup = result
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
        
        # Обработка кнопки "Настройки"
        elif callback_data == 'settings_menu':
            message_text, reply_markup = await show_settings(update, context)
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
        
        # Переключение на личную папку по умолчанию
        elif callback_data == 'toggle_folder_personal':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'personal':
                await query.answer("Папка загрузки по умолчанию уже настроена на личную папку")
                return
            
            update_user_settings(user_id, {'default_folder': 'personal'})
            message_text, reply_markup = await show_settings(update, context)
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
            await query.message.reply_text("✅ Папка загрузки по умолчанию изменена на личную")
        
        # Переключение на общую папку по умолчанию
        elif callback_data == 'toggle_folder_common':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'common':
                await query.answer("Папка загрузки по умолчанию уже настроена на общую папку")
                return
            
            update_user_settings(user_id, {'default_folder': 'common'})
            message_text, reply_markup = await show_settings(update, context)
            await query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup
            )
            await query.message.reply_text("✅ Папка загрузки по умолчанию изменена на общую")
        
        # Изменение отображаемого имени
        elif callback_data == 'change_display_name':
            context.user_data['awaiting_display_name'] = True
            await query.message.reply_text(
                "✏️ Введите новое отображаемое имя:\n"
                "(может содержать любые символы)\n"
                "Для отмены введите /cancel"
            )
        
        # Очистка личной папки
        elif callback_data == 'clear_personal_folder':
            user_folder = get_user_folder(user_id)
            file_count = 0
            deleted_files = []
            
            try:
                for filename in os.listdir(user_folder):
                    filepath = os.path.join(user_folder, filename)
                    if os.path.isfile(filepath):
                        # Получаем метаданные перед удалением
                        metadata = get_file_metadata(filepath)
                        file_size = os.path.getsize(filepath)
                        
                        # Удаляем файл
                        os.remove(filepath)
                        file_count += 1
                        
                        # Удаляем метаданные
                        delete_file_metadata(filepath)
                        
                        # Добавляем запись в лог
                        add_log_entry(user_id, display_name, "delete", filepath, file_size, {
                            'reason': 'clear_folder'
                        })
                        
                        deleted_files.append(filename)
                
                await query.message.reply_text(f"✅ Удалено {file_count} файлов из личной папки")
                
                # Обновляем меню настроек
                message_text, reply_markup = await show_settings(update, context)
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
            except Exception as e:
                await query.message.reply_text(f"❌ Ошибка при очистке папки: {e}")
        
        # Изменение имени папки
        elif callback_data == 'change_folder_name':
            # Сохраняем текущее имя папки перед изменением
            settings = get_user_settings(user_id)
            old_folder_name = settings.get('personal_folder_name', f"user_{user_id}")
            context.user_data['old_folder_name'] = old_folder_name
            context.user_data['awaiting_folder_name'] = True
            
            await query.message.reply_text(
                "✏️ Введите новое имя для вашей личной папки:\n"
                "(только буквы, цифры и символы -_)\n"
                "Для отмены введите /cancel"
            )
        
        # Статистика
        elif callback_data == 'stats_info':
            user_id = update.effective_user.id
            personal_folder = get_user_folder(user_id)
            
            # Подсчитываем файлы
            personal_files = len([f for f in os.listdir(personal_folder) if os.path.isfile(os.path.join(personal_folder, f))])
            common_files = len([f for f in os.listdir(COMMON_DIR) if os.path.isfile(os.path.join(COMMON_DIR, f))])
            
            # Получаем логи
            logs = load_logs()
            user_logs = [log for log in logs if log['user_id'] == user_id]
            
            # Подсчитываем размеры
            def get_folder_size(folder):
                total_size = 0
                for filename in os.listdir(folder):
                    filepath = os.path.join(folder, filename)
                    if os.path.isfile(filepath):
                        total_size += os.path.getsize(filepath)
                return total_size
            
            personal_size = get_folder_size(personal_folder)
            common_size = get_folder_size(COMMON_DIR)
            
            # Форматируем размеры
            def format_size(size):
                if size < 1024:
                    return f"{size} Б"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.1f} КБ"
                elif size < 1024 * 1024 * 1024:
                    return f"{size / (1024 * 1024):.1f} МБ"
                else:
                    return f"{size / (1024 * 1024 * 1024):.2f} ГБ"
            
            await query.message.reply_text(
                f"📊 Статистика системы:\n\n"
                f"👤 Ваши данные:\n"
                f"• Отображаемое имя: {display_name}\n"
                f"• Ваших операций в логах: {len(user_logs)}\n\n"
                f"📁 Личная папка:\n"
                f"• Файлов: {personal_files}\n"
                f"• Размер: {format_size(personal_size)}\n\n"
                f"🌐 Общая папка:\n"
                f"• Файлов: {common_files}\n"
                f"• Размер: {format_size(common_size)}\n\n"
                f"💾 Всего файлов: {personal_files + common_files}\n"
                f"📦 Общий размер: {format_size(personal_size + common_size)}"
            )
        
        # Обработка кнопки "Главное меню"
        elif callback_data == 'main_menu':
            # Создаем инлайн-кнопки
            keyboard = [
                [
                    InlineKeyboardButton("Привет", callback_data='hello'),
                    InlineKeyboardButton("Помощь", callback_data='help')
                ],
                [
                    InlineKeyboardButton("Информация", callback_data='info'),
                    InlineKeyboardButton("Файлы", callback_data='files_list')
                ],
                [
                    InlineKeyboardButton("Настройки", callback_data='settings_menu'),
                    InlineKeyboardButton("Скачать по ссылке", callback_data='download_help')
                ],
                [
                    InlineKeyboardButton("📊 Логи операций", callback_data='view_logs')
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"Hello World! 🎉\nВыберите действие:\n\n"
                     "Вы можете отправить мне:\n"
                     "• Текстовое сообщение\n"
                     "• Файл (фото, документ, видео, аудио)\n"
                     "• Ссылку на файл для скачивания",
                reply_markup=reply_markup
            )
        
        # Обработка других кнопок
        elif callback_data == 'hello':
            display_name = get_user_display_name(user_id, update)
            await query.message.reply_text(f"И тебе привет, {display_name}! 👋")
        elif callback_data == 'help':
            await query.message.reply_text(
                "Я здесь, чтобы помочь! Используйте кнопки для навигации.\n\n"
                "📁 Система папок:\n"
                "• Личная папка - доступна только вам\n"
                "• Общая папка - доступна всем пользователям\n\n"
                "⚙️ Настройки:\n"
                "• Выберите папку загрузки по умолчанию\n"
                "• Измените отображаемое имя\n"
                "• Измените имя личной папки\n"
                "• Просматривайте статистику\n\n"
                "📂 Файлы:\n"
                "• Загружайте файлы и ссылки\n"
                "• Просматривайте сохраненные файлы с информацией о загрузке\n"
                "• Отправляйте файлы из бота\n\n"
                "📊 Логи:\n"
                "• Все операции с файлами логируются\n"
                "• Можно просмотреть историю операций"
            )
        elif callback_data == 'info':
            await query.message.reply_text(
                "Это демонстрационный бот с системой папок, созданный на Python.\n\n"
                "📁 Структура папок:\n"
                "• Личные папки пользователей\n"
                "• Общая папка для всех\n\n"
                "⚙️ Настройки:\n"
                "• Выбор папки загрузки по умолчанию\n"
                "• Индивидуальные имена пользователей\n"
                "• Индивидуальные имена папок\n\n"
                "📥 Функции:\n"
                "• Скачивание файлов по ссылкам\n"
                "• Сохранение с оригинальными именами\n"
                "• Просмотр и отправка файлов с метаданными\n"
                "• Логирование всех операций"
            )
        elif callback_data == 'download_help':
            user_id = update.effective_user.id
            settings = get_user_settings(user_id)
            default_folder = settings.get('default_folder', 'personal')
            folder_name = "личную папку" if default_folder == 'personal' else "общую папку"
            
            await query.message.reply_text(
                f"📥 Отправьте мне ссылку на файл для скачивания!\n\n"
                f"Файл будет сохранен в {folder_name}.\n\n"
                "Примеры поддерживаемых ссылок:\n"
                "• http://example.com/file.pdf\n"
                "• https://site.com/image.jpg\n"
                "• www.domain.com/video.mp4\n\n"
                "⚙️ Чтобы изменить папку загрузки по умолчанию, используйте меню Настройки."
            )
        elif callback_data in ['files_info', 'logs_info']:
            await query.answer("Информация о странице", show_alert=False)
        else:
            await query.message.reply_text("Неизвестная команда")
    
    except Exception as e:
        # Логируем ошибку, но не прерываем работу бота
        logger.error(f"Ошибка при обработке callback: {e}")
        # Если это ошибка "message not modified", просто игнорируем её
        if "Message is not modified" in str(e):
            await query.answer()
        else:
            # Для других ошибок можно уведомить пользователя
            await query.message.reply_text("Произошла ошибка при обработке запроса")

# Функция для обновления списка файлов после отправки
async def show_files_updated(query, context, page=0, folder_type=None):
    """Обновляет список файлов после отправки"""
    await asyncio.sleep(1)  # Небольшая задержка
    result = await show_files_list(query, context, page, folder_type=folder_type)
    if result:
        message_text, reply_markup = result
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup
        )

# Обработчик текстовых сообщений
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем текстовые сообщения"""
    if update.message:
        user_text = update.message.text
        user_id = update.effective_user.id
        display_name = get_user_display_name(user_id, update)
        message_id = update.message.message_id
        
        logger.info(f"Пользователь {user_id} ({display_name}) написал: {user_text}")
        
        # Проверяем, ожидаем ли мы новое отображаемое имя
        if context.user_data.get('awaiting_display_name', False):
            if user_text.lower() == '/cancel':
                context.user_data.pop('awaiting_display_name', None)
                await update.message.reply_text("❌ Изменение имени отменено")
                return
            
            # Проверяем длину имени
            if len(user_text) > 50:
                await update.message.reply_text(
                    "❌ Слишком длинное имя (максимум 50 символов).\n"
                    "Попробуйте снова или введите /cancel для отмены."
                )
                return
            
            # Обновляем отображаемое имя
            update_user_settings(user_id, {'display_name': user_text})
            context.user_data.pop('awaiting_display_name', None)
            
            await update.message.reply_text(f"✅ Отображаемое имя изменено на '{user_text}'")
            
            # Показываем обновленные настройки
            message_text, reply_markup = await show_settings(update, context)
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup
            )
            return
        
        # Проверяем, ожидаем ли мы новое имя папки
        if context.user_data.get('awaiting_folder_name', False):
            if user_text.lower() == '/cancel':
                context.user_data.pop('awaiting_folder_name', None)
                context.user_data.pop('old_folder_name', None)
                await update.message.reply_text("❌ Изменение имени папки отменено")
                return
            
            # Проверяем валидность имени папки
            if re.match(r'^[a-zA-Z0-9_\-]{1,50}$', user_text):
                # Получаем старое имя папки из контекста
                old_folder_name = context.user_data.get('old_folder_name')
                if not old_folder_name:
                    await update.message.reply_text("❌ Ошибка: не найдено старое имя папки. Попробуйте еще раз.")
                    return
                
                new_folder_name = user_text
                
                # Если новое имя совпадает со старым
                if old_folder_name == new_folder_name:
                    await update.message.reply_text("❌ Новое имя совпадает со старым. Введите другое имя.")
                    return
                
                # Проверяем, не существует ли уже папка с таким именем
                new_folder_path = os.path.join(USERS_DIR, new_folder_name)
                if os.path.exists(new_folder_path):
                    await update.message.reply_text(f"❌ Папка с именем '{new_folder_name}' уже существует. Введите другое имя.")
                    return
                
                # Получаем старый путь к папке
                old_folder_path = os.path.join(USERS_DIR, old_folder_name)
                
                # Проверяем, существует ли старая папка
                if not os.path.exists(old_folder_path):
                    # Если старая папка не существует, просто создаем новую
                    os.makedirs(new_folder_path, exist_ok=True)
                    # Обновляем настройки
                    update_user_settings(user_id, {'personal_folder_name': new_folder_name})
                    await update.message.reply_text(
                        f"✅ Имя папки изменено на '{new_folder_name}'\n"
                        f"Старая папка не найдена, создана новая."
                    )
                else:
                    # Пытаемся переименовать папку
                    try:
                        # Получаем список файлов в старой папке для обновления метаданных
                        old_files = []
                        for filename in os.listdir(old_folder_path):
                            filepath = os.path.join(old_folder_path, filename)
                            if os.path.isfile(filepath):
                                old_files.append((filename, filepath))
                        
                        # Переименовываем папку
                        os.rename(old_folder_path, new_folder_path)
                        
                        # Обновляем настройки
                        update_user_settings(user_id, {'personal_folder_name': new_folder_name})
                        
                        # Обновляем пути в метаданных
                        metadata = load_metadata()
                        updated_count = 0
                        for old_filename, old_filepath in old_files:
                            old_rel_path = os.path.relpath(old_filepath, BASE_DOWNLOADS_DIR)
                            new_filepath = os.path.join(new_folder_path, old_filename)
                            new_rel_path = os.path.relpath(new_filepath, BASE_DOWNLOADS_DIR)
                            
                            if old_rel_path in metadata:
                                metadata[new_rel_path] = metadata[old_rel_path]
                                del metadata[old_rel_path]
                                updated_count += 1
                        
                        if updated_count > 0:
                            save_metadata(metadata)
                        
                        await update.message.reply_text(
                            f"✅ Папка успешно переименована в '{new_folder_name}'\n"
                            f"Обновлено записей в метаданных: {updated_count}"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка переименования папки: {e}")
                        await update.message.reply_text(
                            f"❌ Ошибка при переименовании папки: {str(e)}\n"
                            f"Папка не была переименована."
                        )
                        return
                
                # Очищаем контекст
                context.user_data.pop('awaiting_folder_name', None)
                context.user_data.pop('old_folder_name', None)
                
                # Показываем обновленные настройки
                message_text, reply_markup = await show_settings(update, context)
                await update.message.reply_text(
                    text=message_text,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "❌ Неверное имя папки.\n"
                    "Используйте только буквы, цифры и символы -_\n"
                    "Максимум 50 символов.\n"
                    "Попробуйте снова или введите /cancel для отмены."
                )
            return
        
        # Проверяем, является ли текст ссылкой
        if is_url(user_text):
            # Получаем папку для загрузки по умолчанию
            target_folder = get_user_default_folder(user_id)
            folder_name = "личную папку" if target_folder == get_user_folder(user_id) else "общую папку"
            
            # Отправляем сообщение о начале загрузки
            status_msg = await update.message.reply_text(
                f"🔍 Проверяю ссылку...\n"
                f"Файл будет сохранен в {folder_name}",
                reply_to_message_id=message_id
            )
            
            # Скачиваем файл по ссылке
            file_info, error = await download_file_from_url(user_text, context, target_folder, user_id, display_name)
            
            if error:
                await status_msg.edit_text(f"❌ Ошибка: {error}")
            else:
                # Удаляем сообщение о статусе
                await status_msg.delete()
                
                # Форматируем размер файла
                size = file_info['size']
                if size < 1024:
                    size_str = f"{size} байт"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} КБ"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} МБ"
                
                # Получаем информацию о загрузчике
                upload_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
                
                # Отправляем информацию о скачанном файле
                await update.message.reply_text(
                    f"✅ Файл успешно скачан в {folder_name}!\n\n"
                    f"📄 Имя файла: {file_info['filename']}\n"
                    f"👤 Загрузил: {display_name}\n"
                    f"📅 Время загрузки: {upload_time}\n"
                    f"📦 Размер: {size_str}\n"
                    f"📁 Тип: {file_info['content_type']}",
                    reply_to_message_id=message_id
                )
        else:
            # Обычный текст
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Вы написали: {user_text}",
                reply_to_message_id=message_id
            )

# Обработчик файлов (общая функция для всех типов файлов)
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, file_type):
    """Обрабатывает загрузку файлов любого типа"""
    if update.message:
        user_id = update.effective_user.id
        display_name = get_user_display_name(user_id, update)
        message_id = update.message.message_id
        
        # Получаем папку для загрузки по умолчанию
        target_folder = get_user_default_folder(user_id)
        folder_name = "личную папку" if target_folder == get_user_folder(user_id) else "общую папку"
        
        # Обработка в зависимости от типа файла
        if file_type == 'photo':
            file_obj = update.message.photo[-1]  # Берем фото с самым высоким разрешением
            filename = f"photo_{file_obj.file_id}.jpg"
            original_filename = "photo.jpg"
        elif file_type == 'document':
            file_obj = update.message.document
            filename = file_obj.file_name or f"document_{file_obj.file_id}"
            original_filename = file_obj.file_name
        elif file_type == 'video':
            file_obj = update.message.video
            filename = getattr(file_obj, 'file_name', f"video_{file_obj.file_id}.mp4")
            original_filename = getattr(file_obj, 'file_name', "video.mp4")
        elif file_type == 'audio':
            file_obj = update.message.audio
            title = file_obj.title or "Без названия"
            performer = file_obj.performer or "Неизвестный исполнитель"
            if title != "Без названия":
                filename = f"{performer} - {title}.mp3" if performer != "Неизвестный исполнитель" else f"{title}.mp3"
            else:
                filename = f"audio_{file_obj.file_id}.mp3"
            original_filename = filename
        elif file_type == 'voice':
            file_obj = update.message.voice
            timestamp = int(update.message.date.timestamp())
            filename = f"voice_{timestamp}.ogg"
            original_filename = "voice.ogg"
        elif file_type == 'sticker':
            file_obj = update.message.sticker
            emoji = file_obj.emoji or "sticker"
            extension = ".webp"
            if file_obj.is_animated:
                extension = ".tgs"
            elif file_obj.is_video:
                extension = ".webm"
            filename = f"sticker_{emoji}{extension}"
            original_filename = filename
        else:
            return
        
        # Очищаем имя файла
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        unique_filename = get_unique_filename(target_folder, filename)
        file_path = os.path.join(target_folder, unique_filename)
        
        # Получаем информацию о файле
        file = await context.bot.get_file(file_obj.file_id)
        
        # Скачиваем файл
        await file.download_to_drive(file_path)
        
        # Получаем размер файла
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size / 1024:.1f} КБ" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} МБ"
        
        # Добавляем метаданные
        add_file_metadata(file_path, user_id, display_name, "upload", original_filename=original_filename)
        
        # Добавляем запись в лог
        add_log_entry(user_id, display_name, "upload", file_path, file_size, {
            'source': 'telegram',
            'file_type': file_type,
            'original_filename': original_filename
        })
        
        # Получаем информацию о загрузчике
        upload_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Отвечаем пользователю
        await update.message.reply_text(
            f"✅ Файл сохранен в {folder_name}!\n\n"
            f"📄 Имя файла: {unique_filename}\n"
            f"👤 Загрузил: {display_name}\n"
            f"📅 Время загрузки: {upload_time}\n"
            f"📦 Размер: {size_str}",
            reply_to_message_id=message_id
        )
        
        logger.info(f"Пользователь {user_id} ({display_name}) загрузил файл {unique_filename} в {folder_name}")

# Обработчики для разных типов файлов
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'photo')

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'document')

async def video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'video')

async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'audio')

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'voice')

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_file_upload(update, context, 'sticker')

# Обработчик неизвестных команд
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатываем неизвестные команды"""
    if update.message:
        # Ответ с reply на неизвестную команду
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Неизвестная команда. Используйте /start для начала работы.",
            reply_to_message_id=update.message.message_id
        )

# Обработчик ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логируем ошибки"""
    error_msg = str(context.error)
    
    # Игнорируем ошибку "Message is not modified"
    if "Message is not modified" in error_msg:
        logger.warning(f"Игнорируем ошибку: {error_msg}")
        return
    
    logger.error(f"Ошибка при обработке update {update}: {context.error}")

def main():
    """Основная функция запуска бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики в правильном порядке
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчики для файлов (должны быть перед текстовым обработчиком)
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    application.add_handler(MessageHandler(filters.VIDEO, video_handler))
    application.add_handler(MessageHandler(filters.AUDIO, audio_handler))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    application.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    
    # Текстовый обработчик (обрабатывает и обычный текст, и ссылки)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Обработчик неизвестных команд
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("=" * 60)
    print("🤖 Бот запущен...")
    print("📱 Найдите бота в Telegram и отправьте /start")
    print("=" * 60)
    print("✅ Функции бота:")
    print("1. 📁 Личные папки пользователей")
    print("2. 🌐 Общая папка для всех пользователей")
    print("3. ⚙️ Настройка папки загрузки по умолчанию")
    print("4. ✏️ Изменение отображаемого имени пользователя")
    print("5. 📊 Логирование всех файловых операций (JSON)")
    print("6. 📄 Отображение метаданных файлов (кто загрузил, когда)")
    print("7. 🔍 Просмотр и экспорт логов операций")
    print("=" * 60)
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        print(f"❌ Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()