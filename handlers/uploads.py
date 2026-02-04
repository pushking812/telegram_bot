import datetime
import os
import re
import logging
from telegram import InputFile
from storage import get_unique_filename
from settings import get_user_display_name
from metadata import add_file_metadata
from logs import add_log_entry

from .common import get_user_default_folder, update_file_access

logger = logging.getLogger(__name__)


async def send_file_to_user(chat_id, filepath, filename, context, user_id, display_name):
    try:
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            return False, "Файл слишком большой (максимум 50 МБ)"

        metadata = None
        try:
            from metadata import get_file_metadata
            metadata = get_file_metadata(filepath)
        except Exception:
            pass

        ext = os.path.splitext(filename)[1].lower()

        caption = f"📄 {filename}\n"
        if metadata:
            upload_time = datetime.datetime.fromisoformat(metadata['upload_time'])
            upload_str = upload_time.strftime("%d.%m.%Y %H:%M")
            caption += f"👤 Загрузил: {metadata.get('display_name', 'Неизвестно')}\n"
            caption += f"📅 Дата загрузки: {upload_str}\n"
            caption += f"📦 Размер: {metadata.get('file_size', file_size)} байт"

        with open(filepath, 'rb') as file:
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                await context.bot.send_photo(chat_id=chat_id, photo=InputFile(file, filename=filename), caption=caption)
            elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
                await context.bot.send_video(chat_id=chat_id, video=InputFile(file, filename=filename), caption=caption)
            elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
                await context.bot.send_audio(chat_id=chat_id, audio=InputFile(file, filename=filename), caption=caption)
            else:
                await context.bot.send_document(chat_id=chat_id, document=InputFile(file, filename=filename), caption=caption)

        update_file_access(filepath, user_id, display_name, "download")
        add_log_entry(user_id, display_name, "download", filepath, file_size)

        logger.info(f"Файл {filename} отправлен пользователю {user_id} ({display_name})")
        return True, None
    except Exception as e:
        logger.error(f"Ошибка при отправке файла {filename}: {e}")
        return False, str(e)


async def handle_file_upload(update, context, file_type):
    if update.message:
        user_id = update.effective_user.id
        display_name = get_user_display_name(user_id, update)
        message_id = update.message.message_id

        # get_user_default_folder requires get_user_folder callable; import lazily
        from storage import get_user_folder
        target_folder = get_user_default_folder(user_id, get_user_folder)
        settings_local = __import__('settings').get_user_settings(user_id)
        personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
        personal_folder_path_local = get_user_folder(user_id, personal_folder_name_local)
        folder_name = "личную папку" if target_folder == personal_folder_path_local else "общую папку"

        if file_type == 'photo':
            file_obj = update.message.photo[-1]
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

        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        unique_filename = get_unique_filename(target_folder, filename)
        file_path = os.path.join(target_folder, unique_filename)

        file = await context.bot.get_file(file_obj.file_id)

        await file.download_to_drive(file_path)

        file_size = os.path.getsize(file_path)
        size_str = f"{file_size / 1024:.1f} КБ" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} МБ"

        add_file_metadata(file_path, user_id, display_name, "upload", original_filename=original_filename)

        add_log_entry(user_id, display_name, "upload", file_path, file_size, {
            'source': 'telegram',
            'file_type': file_type,
            'original_filename': original_filename
        })

        upload_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

        await update.message.reply_text(
            f"✅ Файл сохранен в {folder_name}!\n\n"
            f"📄 Имя файла: {unique_filename}\n"
            f"👤 Загрузил: {display_name}\n"
            f"📅 Время загрузки: {upload_time}\n"
            f"📦 Размер: {size_str}",
            reply_to_message_id=message_id
        )

        logger.info(f"Пользователь {user_id} ({display_name}) загрузил файл {unique_filename} в {folder_name}")


async def photo_handler(update, context):
    await handle_file_upload(update, context, 'photo')


async def document_handler(update, context):
    await handle_file_upload(update, context, 'document')


async def video_handler(update, context):
    await handle_file_upload(update, context, 'video')


async def audio_handler(update, context):
    await handle_file_upload(update, context, 'audio')


async def voice_handler(update, context):
    await handle_file_upload(update, context, 'voice')


async def sticker_handler(update, context):
    await handle_file_upload(update, context, 'sticker')


__all__ = ['send_file_to_user', 'photo_handler', 'document_handler', 'video_handler', 'audio_handler', 'voice_handler', 'sticker_handler']
