import datetime
import os
import math
import asyncio
import re
import logging
from typing import Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes

# Импортируем функции из модулей
from constants import BASE_DOWNLOADS_DIR, COMMON_DIR, USERS_DIR
from settings import get_user_settings, update_user_settings, get_user_display_name
from metadata import get_file_metadata, add_file_metadata, delete_file_metadata, load_metadata, save_metadata
from logs import load_logs, save_logs, add_log_entry
from storage import get_user_folder, create_folder_structure, download_file_from_url, get_unique_filename
from utils import is_url, format_size

# Логирование
logger = logging.getLogger(__name__)


async def safe_edit_message(query, text, reply_markup=None):
    """Безопасно обновляет текст сообщения: если текст пустой (или содержит
    только невидимые символы), обновляем только reply_markup, иначе обновляем текст.
    """
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

def get_user_default_folder(user_id: int) -> str:
    """Получает папку для загрузки по умолчанию для пользователя"""
    settings = get_user_settings(user_id)
    default_folder = settings.get('default_folder', 'personal')
    
    if default_folder == 'common':
        return COMMON_DIR
    else:
        return get_user_folder(user_id)

# Основная функция для просмотра настроек
async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None):
    """Показывает меню настроек пользователя"""
    if user_id is None:
        user_id = update.effective_user.id
    # При вызове из callback-контекста иногда передаётся объект CallbackQuery
    # (или даже None), поэтому передаём update только если он не None и имеет
    # атрибут `effective_user`.
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
            InlineKeyboardButton(
                "📁 Личная папка",
                callback_data='toggle_folder_personal'
            ),
            InlineKeyboardButton(
                "🌐 Общая папка",
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
    settings_local = get_user_settings(user_id)
    personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
    personal_folder = get_user_folder(user_id, personal_folder_name_local)
    # Рекурсивный подсчет файлов
    personal_files = 0
    for _, _, filenames in os.walk(personal_folder):
        for f in filenames:
            personal_files += 1
    common_files = 0
    for _, _, filenames in os.walk(COMMON_DIR):
        for f in filenames:
            common_files += 1
    
    # Текст сообщения
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

# Функция для отображения списка файлов с пагинацией
async def show_files_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0, items_per_page=10, folder_type=None, user_id: int = None):
    """Показывает список файлов в выбранной папке с пагинацией"""
    if user_id is None:
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
        settings = get_user_settings(user_id)
        personal_folder_name = settings.get('personal_folder_name', f'user_{user_id}')
        target_folder = get_user_folder(user_id, personal_folder_name)
        folder_name = personal_folder_name
    
    # Сохраняем режим просмотра в контексте
    context.user_data['current_folder_view'] = folder_type
    
    # Получаем все файлы из папки с метаданными (рекурсивно)
    files = []
    try:
        for root, dirs, filenames in os.walk(target_folder):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                # Получаем метаданные файла
                metadata = get_file_metadata(filepath)
                
                size = os.path.getsize(filepath)
                filesize = format_size(size)
                
                # Форматируем информацию о загрузке
                upload_info = "Неизвестно"
                if metadata:
                    upload_time = datetime.datetime.fromisoformat(metadata['upload_time'])
                    upload_str = upload_time.strftime("%d.%m.%Y %H:%M")
                    upload_info = f"{metadata.get('display_name', 'Неизвестно')} ({upload_str})"
                
                # Получаем относительный путь для отображения
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
        
        # Обрезаем название для одинаковой ширины кнопок в 3 строки
        max_name_len = 65
        if len(filename) > max_name_len:
            display_name = filename[:max_name_len-1] + "…"
        else:
            display_name = filename
        
        # Добавляем переносы строк в название для выравнивания высоты кнопок
        # Это гарантирует, что обе кнопки будут иметь одинаковую высоту
        display_name_lines = display_name.split('\n')
        while len(display_name_lines) < 3:
            display_name_lines.append(" ")
        display_name = '\n'.join(display_name_lines[:3])
        
        # Подготавливаем инфо об авторе и дате
        upload_parts = upload_info.split(' (')
        author = upload_parts[0] if upload_parts else "Неизвестно"
        date_str = upload_parts[1].rstrip(')') if len(upload_parts) > 1 else ""
        
        # Объединяем параметры в одну строку и добавляем пустые строки для выравнивания высоты
        params_text = f"{filesize} | {author} | {date_str}\n\n"
        
        # Используем короткий идентификатор вместо полного пути в callback_data
        import hashlib
        file_id_hash = hashlib.sha1(file_info['full_path'].encode('utf-8')).hexdigest()
        # Сохраняем соответствие id -> путь в глобальном хранилище бота
        try:
            context.bot_data.setdefault('file_map', {})
            context.bot_data['file_map'][file_id_hash] = file_info['full_path']
        except Exception:
            pass
        callback_data = f"file_send:{file_id_hash}:{page}:{folder_type}"
        
        # Создаем ряд из двух кнопок для одного файла
        # Первая - название (большая), вторая - все параметры вместе
        file_row = [
            InlineKeyboardButton(f"📄 {display_name}", callback_data=callback_data),
            InlineKeyboardButton(f"💾 {params_text}", callback_data=callback_data)
        ]
        keyboard.append(file_row)
    
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
    
    # Невидимый заполнитель для Telegram API
    message_text = '\u200b'
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

def update_file_access(filepath, user_id, display_name, operation):
    """Обновляет метаданные доступа к файлу"""
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
        
        # Сохраняем обновленные метаданные
        metadata_dict = load_metadata()
        rel_path = os.path.relpath(filepath, BASE_DOWNLOADS_DIR)
        metadata_dict[rel_path] = metadata
        save_metadata(metadata_dict)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    display_name = get_user_display_name(user_id, update)
    
    # Создаем главное меню
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
    
    await update.message.reply_text(
        f"Hello World! 🎉\nВыберите действие:\n\n"
        f"Вы можете отправить мне:\n"
        f"• Текстовое сообщение\n"
        f"• Файл (фото, документ, видео, аудио)\n"
        f"• Ссылку на файл для скачивания",
        reply_markup=reply_markup
    )

# Функция для обновления списка файлов после отправки
async def show_files_updated(query, context, page=0, folder_type=None):
    """Обновляет список файлов после отправки"""
    await asyncio.sleep(1)  # Небольшая задержка
    user_id = query.from_user.id
    result = await show_files_list(query, context, page, folder_type=folder_type, user_id=user_id)
    if result:
        message_text, reply_markup = result
        await safe_edit_message(query, message_text, reply_markup)

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
                file_id_or_name = parts[1]
                page = int(parts[2])
                folder_type = parts[3]
                
                # Определяем путь к папке
                if folder_type == 'common':
                    # Сначала пытаемся разрешить по id, затем по имени
                    filepath = None
                    file_map = context.bot_data.get('file_map', {})
                    if file_id_or_name in file_map:
                        filepath = file_map[file_id_or_name]
                    else:
                        filepath = os.path.join(COMMON_DIR, file_id_or_name)
                else:
                    settings_person = get_user_settings(user_id)
                    personal_folder_name_person = settings_person.get('personal_folder_name', f"user_{user_id}")
                    file_map = context.bot_data.get('file_map', {})
                    if file_id_or_name in file_map:
                        filepath = file_map[file_id_or_name]
                    else:
                        filepath = os.path.join(get_user_folder(user_id, personal_folder_name_person), file_id_or_name)
                
                # Проверяем существование файла
                # Имя файла для отображения/логов
                filename = os.path.basename(filepath)
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
            result = await show_files_list(update, context, page, folder_type=folder_type, user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
        # Обработка пагинации логов
        elif callback_data.startswith('logs_page:'):
            page = int(callback_data.split(':')[1])
            result = await show_logs(update, context, page)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
        # Просмотр личных файлов
        elif callback_data == 'view_personal_files':
            # Проверяем текущий режим просмотра
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'personal':
                # Уже в личной папке - просто подтверждаем нажатие
                await query.answer("Вы уже в личной папке")
                return
            
            result = await show_files_list(update, context, folder_type='personal', user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
        # Просмотр общих файлов
        elif callback_data == 'view_common_files':
            # Проверяем текущий режим просмотра
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'common':
                # Уже в общей папке - просто подтверждаем нажатие
                await query.answer("Вы уже в общей папке")
                return
            
            result = await show_files_list(update, context, folder_type='common', user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
        # Просмотр логов
        elif callback_data == 'view_logs':
            result = await show_logs(update, context)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
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
                await safe_edit_message(query, message_text, reply_markup)
        
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
            result = await show_files_list(update, context, user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)
        
        # Обработка кнопки "Настройки"
        elif callback_data == 'settings_menu':
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)
        
        # Переключение на личную папку по умолчанию
        elif callback_data == 'toggle_folder_personal':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'personal':
                await query.answer("Папка загрузки по умолчанию уже настроена на личную папку")
                return
            
            update_user_settings(user_id, {'default_folder': 'personal'})
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)
            await query.message.reply_text("✅ Папка загрузки по умолчанию изменена на личную")
        
        # Переключение на общую папку по умолчанию
        elif callback_data == 'toggle_folder_common':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'common':
                await query.answer("Папка загрузки по умолчанию уже настроена на общую папку")
                return
            
            update_user_settings(user_id, {'default_folder': 'common'})
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)
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
            settings_cp = get_user_settings(user_id)
            user_folder_name_cp = settings_cp.get('personal_folder_name', f"user_{user_id}")
            user_folder = get_user_folder(user_id, user_folder_name_cp)
            file_count = 0
            deleted_files = []
            
            try:
                # Рекурсивно удаляем все файлы в папке и подпапках
                for root, dirs, filenames in os.walk(user_folder, topdown=False):
                    for filename in filenames:
                        filepath = os.path.join(root, filename)
                        # Получаем метаданные перед удалением
                        metadata = get_file_metadata(filepath)
                        file_size = os.path.getsize(filepath)
                        
                        # Удаляем файл
                        os.remove(filepath)
                        file_count += 1
                        
                        # Удаляем метаданные
                        delete_file_metadata(filepath)
                
                # Удаляем пустые подпапки (topdown=False обрабатывает снизу вверх)
                for root, dirs, filenames in os.walk(user_folder, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            os.rmdir(dir_path)
                        except OSError:
                            pass
                        
                        # Добавляем запись в лог
                        add_log_entry(user_id, display_name, "delete", filepath, file_size, {
                            'reason': 'clear_folder'
                        })
                        
                        deleted_files.append(filename)
                
                await query.message.reply_text(f"✅ Удалено {file_count} файлов из личной папки")
                
                # Обновляем меню настроек
                message_text, reply_markup = await show_settings(update, context, user_id)
                await safe_edit_message(query, message_text, reply_markup)
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
            settings_stats = get_user_settings(user_id)
            personal_folder_name_stats = settings_stats.get('personal_folder_name', f"user_{user_id}")
            personal_folder = get_user_folder(user_id, personal_folder_name_stats)
            
            # Рекурсивный подсчет файлов
            personal_files = 0
            for _, _, filenames in os.walk(personal_folder):
                for f in filenames:
                    personal_files += 1
            common_files = 0
            for _, _, filenames in os.walk(COMMON_DIR):
                for f in filenames:
                    common_files += 1
            
            # Получаем логи
            logs = load_logs()
            user_logs = [log for log in logs if log['user_id'] == user_id]
            
            # Подсчитываем размеры (рекурсивно)
            def get_folder_size(folder):
                total_size = 0
                for root, dirs, filenames in os.walk(folder):
                    for filename in filenames:
                        filepath = os.path.join(root, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, IOError):
                            pass
                return total_size
            
            personal_size = get_folder_size(personal_folder)
            common_size = get_folder_size(COMMON_DIR)
            
            # Форматируем размеры
            def format_size_stat(size):
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
                f"• Размер: {format_size_stat(personal_size)}\n\n"
                f"🌐 Общая папка:\n"
                f"• Файлов: {common_files}\n"
                f"• Размер: {format_size_stat(common_size)}\n\n"
                f"💾 Всего файлов: {personal_files + common_files}\n"
                f"📦 Общий размер: {format_size_stat(personal_size + common_size)}"
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
            message_text, reply_markup = await show_settings(update, context, user_id)
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
                        # Получаем список файлов в старой папке для обновления метаданных (рекурсивно)
                        old_files = []
                        for root, dirs, filenames in os.walk(old_folder_path):
                            for filename in filenames:
                                filepath = os.path.join(root, filename)
                                old_files.append((filename, filepath))
                        
                        # Переименовываем папку
                        os.rename(old_folder_path, new_folder_path)
                        
                        # Обновляем настройки
                        update_user_settings(user_id, {'personal_folder_name': new_folder_name})
                        
                        # Обновляем пути в метаданных (включая вложенные файлы)
                        metadata = load_metadata()
                        updated_count = 0
                        for old_filename, old_filepath in old_files:
                            old_rel_path = os.path.relpath(old_filepath, BASE_DOWNLOADS_DIR)
                            # Вычисляем новый путь, сохраняя структуру подпапок
                            rel_path_in_folder = os.path.relpath(old_filepath, old_folder_path)
                            new_filepath = os.path.join(new_folder_path, rel_path_in_folder)
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
                message_text, reply_markup = await show_settings(update, context, user_id)
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
            settings_local = get_user_settings(user_id)
            personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
            personal_folder_path_local = get_user_folder(user_id, personal_folder_name_local)
            folder_name = "личную папку" if target_folder == personal_folder_path_local else "общую папку"
            
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
                
                # Получаем информацию о загрузке
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
        settings_local = get_user_settings(user_id)
        personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
        personal_folder_path_local = get_user_folder(user_id, personal_folder_name_local)
        folder_name = "личную папку" if target_folder == personal_folder_path_local else "общую папку"
        
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
        
        # Получаем информацию о загрузке
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
