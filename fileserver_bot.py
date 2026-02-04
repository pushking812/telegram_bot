import logging
import os
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

import handlers
from storage import create_folder_structure
from handlers.remote_handlers import (
    ADD_CLIENT_NAME, ADD_CLIENT_URL,
    remote_add_client_name, remote_add_client_url
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Попытка прочитать токен из файла, иначе используйте переменную окружения TOKEN
TOKEN = None
if os.path.exists('telegrambot.apikey'):
    with open('telegrambot.apikey', 'r', encoding='utf-8') as f:
        TOKEN = f.read().strip()
if not TOKEN:
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or ''


def main():
    if not TOKEN:
        logger.error('Telegram token not found. Place it in telegrambot.apikey or set TELEGRAM_BOT_TOKEN env var.')
        return

    create_folder_structure()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CallbackQueryHandler(handlers.button_callback))
    
    # ConversationHandler для добавления клиента
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.remote_handlers.remote_add_client_start, pattern='^remote_add$')],
        states={
            ADD_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, remote_add_client_name)],
            ADD_CLIENT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, remote_add_client_url)]
        },
        fallbacks=[CallbackQueryHandler(handlers.button_callback, pattern='^remote_menu$')]
    )
    application.add_handler(conv_handler)

    application.add_handler(MessageHandler(filters.PHOTO, handlers.photo_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handlers.document_handler))
    application.add_handler(MessageHandler(filters.VIDEO, handlers.video_handler))
    application.add_handler(MessageHandler(filters.AUDIO, handlers.audio_handler))
    application.add_handler(MessageHandler(filters.VOICE, handlers.voice_handler))
    application.add_handler(MessageHandler(filters.Sticker.ALL, handlers.sticker_handler))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_handler))
    application.add_handler(MessageHandler(filters.COMMAND, handlers.unknown_command))

    application.add_error_handler(handlers.error_handler)

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
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")


if __name__ == '__main__':
    main()
