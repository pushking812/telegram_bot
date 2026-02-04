import os
import logging
from telegram import InputFile

from constants import COMMON_DIR
from settings import get_user_settings, get_user_display_name
from storage import get_user_folder
from metadata import get_file_metadata, delete_file_metadata
from logs import load_logs, save_logs, add_log_entry

from .ui import show_files_list, show_logs, show_settings, show_files_updated, show_main_menu
from .uploads import send_file_to_user
from .common import safe_edit_message

logger = logging.getLogger(__name__)


async def button_callback(update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    display_name = get_user_display_name(user_id, update)
    callback_data = query.data

    logger.info(f"Пользователь {user_id} ({display_name}) нажал: {callback_data}")

    try:
        # File send
        if callback_data.startswith('file_send:'):
            parts = callback_data.split(':')
            if len(parts) >= 4:
                file_id_or_name = parts[1]
                page = int(parts[2])
                folder_type = parts[3]

                if folder_type == 'common':
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

                filename = os.path.basename(filepath)
                if not os.path.exists(filepath):
                    await query.message.reply_text(f"❌ Файл '{filename}' не найден.")
                    return

                if folder_type == 'personal':
                    file_folder = os.path.dirname(filepath)
                    folder_user_id = None
                    try:
                        folder_name = os.path.basename(file_folder)
                        if folder_name.startswith('user_'):
                            folder_user_id = int(folder_name.split('_')[1])
                    except:
                        pass

                    if folder_user_id and folder_user_id != user_id:
                        await query.message.reply_text("❌ У вас нет доступа к этому файлу.")
                        return

                status_msg = await query.message.reply_text(f"📤 Отправляю файл '{filename}'...")

                success, error = await send_file_to_user(
                    chat_id=query.message.chat_id,
                    filepath=filepath,
                    filename=filename,
                    context=context,
                    user_id=user_id,
                    display_name=display_name
                )

                await status_msg.delete()

                if not success:
                    await query.message.reply_text(f"❌ Ошибка при отправке файла: {error}")

                await show_files_updated(query, context, page, folder_type)

        # Files pagination
        elif callback_data.startswith('files_page:'):
            parts = callback_data.split(':')
            page = int(parts[1])
            folder_type = parts[2] if len(parts) > 2 else 'personal'
            result = await show_files_list(update, context, page, folder_type=folder_type, user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # Logs pagination
        elif callback_data.startswith('logs_page:'):
            page = int(callback_data.split(':')[1])
            result = await show_logs(update, context, page)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # View personal files
        elif callback_data == 'view_personal_files':
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'personal':
                await query.answer("Вы уже в личной папке")
                return
            result = await show_files_list(update, context, folder_type='personal', user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # View common files
        elif callback_data == 'view_common_files':
            current_view = context.user_data.get('current_folder_view', '')
            if current_view == 'common':
                await query.answer("Вы уже в общей папке")
                return
            result = await show_files_list(update, context, folder_type='common', user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # View logs
        elif callback_data == 'view_logs':
            result = await show_logs(update, context)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # Clear logs
        elif callback_data == 'clear_logs':
            if save_logs([]):
                await query.answer("✅ Логи очищены", show_alert=True)
            else:
                await query.answer("❌ Ошибка при очистке логов", show_alert=True)

            result = await show_logs(update, context)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # Export logs
        elif callback_data == 'export_logs':
            logs = load_logs()
            if logs:
                log_text = "📊 Логи файловых операций\n\n"
                for log in logs[-100:]:
                    timestamp = datetime.datetime.fromisoformat(log['timestamp'])
                    time_str = timestamp.strftime("%d.%m.%Y %H:%M:%S")
                    log_text += f"{time_str} - {log['operation']} - {log['display_name']}\n"
                    log_text += f"  Файл: {log['file_path']}\n"
                    log_text += f"  Размер: {log['file_size']} байт\n\n"

                await query.message.reply_document(
                    document=InputFile.from_bytes(log_text.encode('utf-8'), filename='logs.txt'),
                    caption="📊 Экспорт логов операций"
                )
            else:
                await query.answer("Логи пусты", show_alert=True)

        # Files list
        elif callback_data == 'files_list':
            result = await show_files_list(update, context, user_id=user_id)
            if result:
                message_text, reply_markup = result
                await safe_edit_message(query, message_text, reply_markup)

        # Settings menu
        elif callback_data == 'settings_menu':
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)

        # Toggle default folder to personal
        elif callback_data == 'toggle_folder_personal':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'personal':
                await query.answer("Папка загрузки по умолчанию уже настроена на личную папку")
                return
            from settings import update_user_settings
            update_user_settings(user_id, {'default_folder': 'personal'})
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)
            await query.message.reply_text("✅ Папка загрузки по умолчанию изменена на личную")

        # Toggle default folder to common
        elif callback_data == 'toggle_folder_common':
            settings = get_user_settings(user_id)
            if settings.get('default_folder', 'personal') == 'common':
                await query.answer("Папка загрузки по умолчанию уже настроена на общую папку")
                return
            from settings import update_user_settings
            update_user_settings(user_id, {'default_folder': 'common'})
            message_text, reply_markup = await show_settings(update, context, user_id)
            await safe_edit_message(query, message_text, reply_markup)
            await query.message.reply_text("✅ Папка загрузки по умолчанию изменена на общую")

        # Change display name
        elif callback_data == 'change_display_name':
            context.user_data['awaiting_display_name'] = True
            await query.message.reply_text("✏️ Введите новое отображаемое имя:\n(может содержать любые символы)\nДля отмены введите /cancel")

        # Clear personal folder
        elif callback_data == 'clear_personal_folder':
            settings_cp = get_user_settings(user_id)
            user_folder_name_cp = settings_cp.get('personal_folder_name', f"user_{user_id}")
            user_folder = get_user_folder(user_id, user_folder_name_cp)
            file_count = 0
            deleted_files = []

            try:
                for root, dirs, filenames in os.walk(user_folder, topdown=False):
                    for filename in filenames:
                        filepath = os.path.join(root, filename)
                        metadata = get_file_metadata(filepath)
                        file_size = os.path.getsize(filepath)

                        os.remove(filepath)
                        file_count += 1

                        delete_file_metadata(filepath)

                for root, dirs, filenames in os.walk(user_folder, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        try:
                            os.rmdir(dir_path)
                        except OSError:
                            pass

                        add_log_entry(user_id, display_name, "delete", filepath, file_size, {'reason': 'clear_folder'})
                        deleted_files.append(filename)

                await query.message.reply_text(f"✅ Удалено {file_count} файлов из личной папки")

                message_text, reply_markup = await show_settings(update, context, user_id)
                await safe_edit_message(query, message_text, reply_markup)
            except Exception as e:
                await query.message.reply_text(f"❌ Ошибка при очистке папки: {e}")

        # Change folder name (start)
        elif callback_data == 'change_folder_name':
            settings = get_user_settings(user_id)
            old_folder_name = settings.get('personal_folder_name', f"user_{user_id}")
            context.user_data['old_folder_name'] = old_folder_name
            context.user_data['awaiting_folder_name'] = True

            await query.message.reply_text("✏️ Введите новое имя для вашей личной папки:\n(только буквы, цифры и символы -_)\nДля отмены введите /cancel")

        # Stats info
        elif callback_data == 'stats_info':
            settings_stats = get_user_settings(user_id)
            personal_folder_name_stats = settings_stats.get('personal_folder_name', f"user_{user_id}")
            personal_folder = get_user_folder(user_id, personal_folder_name_stats)

            personal_files = 0
            for _, _, filenames in os.walk(personal_folder):
                for f in filenames:
                    personal_files += 1
            common_files = 0
            for _, _, filenames in os.walk(COMMON_DIR):
                for f in filenames:
                    common_files += 1

            logs = load_logs()
            user_logs = [log for log in logs if log['user_id'] == user_id]

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

        # Main menu
        elif callback_data == 'main_menu':
            message_text, reply_markup = await show_main_menu(update, context)
            await safe_edit_message(query, message_text, reply_markup)
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
            pass  # Удалено: ссылки обрабатываются при копировании в чат
        elif callback_data in ['files_info', 'logs_info']:
            await query.answer("Информация о странице", show_alert=False)
        else:
            await query.message.reply_text("Неизвестная команда")

    except Exception as e:
        logger.error(f"Ошибка при обработке callback: {e}")
        if "Message is not modified" in str(e):
            await query.answer()
        else:
            await query.message.reply_text("Произошла ошибка при обработке запроса")


__all__ = ['button_callback']
