import os
import re
import datetime
import logging
from telegram.ext import ContextTypes

from constants import USERS_DIR, BASE_DOWNLOADS_DIR
from settings import get_user_display_name, get_user_settings, update_user_settings
from storage import get_user_folder, download_file_from_url
from metadata import load_metadata, save_metadata
from utils import is_url
from .common import get_user_default_folder

logger = logging.getLogger(__name__)


async def text_handler(update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_text = update.message.text
        user_id = update.effective_user.id
        display_name = get_user_display_name(user_id, update)
        message_id = update.message.message_id

        logger.info(f"Пользователь {user_id} ({display_name}) написал: {user_text}")

        if context.user_data.get('awaiting_display_name', False):
            if user_text.lower() == '/cancel':
                context.user_data.pop('awaiting_display_name', None)
                await update.message.reply_text("❌ Изменение имени отменено")
                return

            if len(user_text) > 50:
                await update.message.reply_text("❌ Слишком длинное имя (максимум 50 символов).\nПопробуйте снова или введите /cancel для отмены.")
                return

            update_user_settings(user_id, {'display_name': user_text})
            context.user_data.pop('awaiting_display_name', None)

            await update.message.reply_text(f"✅ Отображаемое имя изменено на '{user_text}'")

            from .ui import show_settings
            message_text, reply_markup = await show_settings(update, context, user_id)
            await update.message.reply_text(text=message_text, reply_markup=reply_markup)
            return

        if context.user_data.get('awaiting_folder_name', False):
            if user_text.lower() == '/cancel':
                context.user_data.pop('awaiting_folder_name', None)
                context.user_data.pop('old_folder_name', None)
                await update.message.reply_text("❌ Изменение имени папки отменено")
                return

            if re.match(r'^[a-zA-Z0-9_\-]{1,50}$', user_text):
                old_folder_name = context.user_data.get('old_folder_name')
                if not old_folder_name:
                    await update.message.reply_text("❌ Ошибка: не найдено старое имя папки. Попробуйте еще раз.")
                    return

                new_folder_name = user_text

                if old_folder_name == new_folder_name:
                    await update.message.reply_text("❌ Новое имя совпадает со старым. Введите другое имя.")
                    return

                new_folder_path = os.path.join(USERS_DIR, new_folder_name)
                if os.path.exists(new_folder_path):
                    await update.message.reply_text(f"❌ Папка с именем '{new_folder_name}' уже существует. Введите другое имя.")
                    return

                old_folder_path = os.path.join(USERS_DIR, old_folder_name)

                if not os.path.exists(old_folder_path):
                    os.makedirs(new_folder_path, exist_ok=True)
                    update_user_settings(user_id, {'personal_folder_name': new_folder_name})
                    await update.message.reply_text(f"✅ Имя папки изменено на '{new_folder_name}'\nСтарая папка не найдена, создана новая.")
                else:
                    try:
                        old_files = []
                        for root, dirs, filenames in os.walk(old_folder_path):
                            for filename in filenames:
                                filepath = os.path.join(root, filename)
                                old_files.append((filename, filepath))

                        os.rename(old_folder_path, new_folder_path)

                        update_user_settings(user_id, {'personal_folder_name': new_folder_name})

                        metadata = load_metadata()
                        updated_count = 0
                        for old_filename, old_filepath in old_files:
                            old_rel_path = os.path.relpath(old_filepath, BASE_DOWNLOADS_DIR)
                            rel_path_in_folder = os.path.relpath(old_filepath, old_folder_path)
                            new_filepath = os.path.join(new_folder_path, rel_path_in_folder)
                            new_rel_path = os.path.relpath(new_filepath, BASE_DOWNLOADS_DIR)

                            if old_rel_path in metadata:
                                metadata[new_rel_path] = metadata[old_rel_path]
                                del metadata[old_rel_path]
                                updated_count += 1

                        if updated_count > 0:
                            save_metadata(metadata)

                        await update.message.reply_text(f"✅ Папка успешно переименована в '{new_folder_name}'\nОбновлено записей в метаданных: {updated_count}")
                    except Exception as e:
                        logging.getLogger(__name__).error(f"Ошибка переименования папки: {e}")
                        await update.message.reply_text(f"❌ Ошибка при переименовании папки: {str(e)}\nПапка не была переименована.")
                        return

                context.user_data.pop('awaiting_folder_name', None)
                context.user_data.pop('old_folder_name', None)

                from .ui import show_settings
                message_text, reply_markup = await show_settings(update, context, user_id)
                await update.message.reply_text(text=message_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text("❌ Неверное имя папки.\nИспользуйте только буквы, цифры и символы -_\nМаксимум 50 символов.\nПопробуйте снова или введите /cancel для отмены.")
            return

        if is_url(user_text):
            target_folder = get_user_default_folder(user_id, get_user_folder)
            settings_local = get_user_settings(user_id)
            personal_folder_name_local = settings_local.get('personal_folder_name', f"user_{user_id}")
            personal_folder_path_local = get_user_folder(user_id, personal_folder_name_local)
            folder_name = "личную папку" if target_folder == personal_folder_path_local else "общую папку"

            status_msg = await update.message.reply_text(f"🔍 Проверяю ссылку...\nФайл будет сохранен в {folder_name}", reply_to_message_id=message_id)

            file_info, error = await download_file_from_url(user_text, context, target_folder, user_id, display_name)

            if error:
                await status_msg.edit_text(f"❌ Ошибка: {error}")
            else:
                await status_msg.delete()

                size = file_info['size']
                if size < 1024:
                    size_str = f"{size} байт"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} КБ"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} МБ"

                upload_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

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
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Вы написали: {user_text}", reply_to_message_id=message_id)


async def unknown_command(update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Неизвестная команда. Используйте /start для начала работы.", reply_to_message_id=update.message.message_id)


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    error_msg = str(context.error)
    if "Message is not modified" in error_msg:
        logging.getLogger(__name__).warning(f"Игнорируем ошибку: {error_msg}")
        return
    logging.getLogger(__name__).error(f"Ошибка при обработке update {update}: {context.error}")


__all__ = ['text_handler', 'unknown_command', 'error_handler']
