"""
Обработчики команд для управления удалёнными клиентами
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import asyncio

from remote_storage import get_remote_storage_manager

logger = logging.getLogger(__name__)

# States для ConversationHandler
ADD_CLIENT_NAME, ADD_CLIENT_URL = range(2)


async def remote_storage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню удалённых хранилищ"""
    manager = get_remote_storage_manager()
    clients = manager.list_clients()
    
    # Проверяем статус всех клиентов
    statuses = await manager.check_all_clients()
    
    keyboard = []
    
    if clients:
        keyboard.append([InlineKeyboardButton("🔄 Обновить статус", callback_data="remote_refresh")])
        keyboard.append([InlineKeyboardButton("📊 Статус клиентов", callback_data="remote_status")])
        keyboard.append([InlineKeyboardButton("📂 Просмотр файлов", callback_data="remote_browse")])
    
    keyboard.append([InlineKeyboardButton("➕ Добавить клиент", callback_data="remote_add")])
    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status_text = "📡 *Удалённые хранилища*\n\n"
    
    if clients:
        status_text += f"Подключено клиентов: {len(clients)}\n\n"
        
        for client in clients:
            status_icon = "🟢" if statuses.get(client.client_id, False) else "🔴"
            status_text += f"{status_icon} *{client.name}* (`{client.client_id}`)\n"
            status_text += f"  URL: {client.url}\n"
            if client.folder_size > 0:
                size_mb = client.folder_size / (1024 * 1024)
                status_text += f"  Размер: {size_mb:.2f} МБ ({client.file_count} файлов)\n"
            status_text += "\n"
    else:
        status_text += "Клиентов не подключено.\n\nНажмите *Добавить клиент* для подключения."
    
    await update.callback_query.edit_message_text(
        text=status_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def remote_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус всех клиентов"""
    manager = get_remote_storage_manager()
    clients = manager.list_clients()
    
    status_text = "📊 *Статус клиентов*\n\n"
    
    if not clients:
        status_text += "Клиентов не подключено."
    else:
        # Проверяем статус
        for client in clients:
            info = await manager.get_client_info(client.client_id)
            is_online = await manager.check_health(client.client_id)
            
            status_icon = "🟢" if is_online else "🔴"
            status_text += f"{status_icon} *{client.name}*\n"
            status_text += f"ID: `{client.client_id}`\n"
            status_text += f"URL: `{client.url}`\n"
            
            if is_online:
                if info:
                    size_mb = info.get('folder_size', 0) / (1024 * 1024)
                    status_text += f"Размер: {size_mb:.2f} МБ\n"
                    status_text += f"Файлов: {info.get('file_count', 0)}\n"
                status_text += f"✅ Статус: Онлайн\n"
            else:
                status_text += f"❌ Статус: Офлайн\n"
            
            status_text += "\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=status_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def remote_add_client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления клиента"""
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="remote_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="📝 Введите имя клиента:",
        reply_markup=reply_markup
    )
    
    return ADD_CLIENT_NAME


async def remote_add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить имя клиента"""
    context.user_data['client_name'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="remote_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌐 Введите URL клиента (например: http://192.168.1.100:5000):",
        reply_markup=reply_markup
    )
    
    return ADD_CLIENT_URL


async def remote_add_client_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить URL и добавить клиента"""
    url = update.message.text
    name = context.user_data.get('client_name', 'Unknown')
    
    manager = get_remote_storage_manager()
    
    # Генерируем ID на основе имени
    import uuid
    client_id = str(uuid.uuid4())[:8]
    
    # Проверяем доступность
    is_available = await manager.check_health(client_id)
    manager.add_client(client_id, name, url)
    
    status = "✅ Клиент успешно добавлен!" if is_available else "⚠️ Клиент добавлен, но недоступен (проверьте URL и статус)"
    
    text = f"{status}\n\n🔍 Детали:\n"
    text += f"Имя: {name}\n"
    text += f"URL: {url}\n"
    text += f"ID: `{client_id}`"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="remote_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    return ConversationHandler.END


async def remote_browse_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр файлов на удалённом клиенте"""
    manager = get_remote_storage_manager()
    clients = manager.list_clients()
    
    if not clients:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text="Нет подключённых клиентов",
            reply_markup=reply_markup
        )
        return
    
    # Показываем список клиентов
    keyboard = []
    for client in clients:
        is_online = await manager.check_health(client.client_id)
        status = "🟢" if is_online else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {client.name}",
                callback_data=f"remote_browse_client_{client.client_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="remote_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="📂 Выберите клиент:",
        reply_markup=reply_markup
    )


async def remote_browse_client_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать файлы на клиенте"""
    client_id = update.callback_query.data.replace("remote_browse_client_", "")
    
    manager = get_remote_storage_manager()
    client = manager.get_client(client_id)
    
    if not client:
        await update.callback_query.answer("Клиент не найден", show_alert=True)
        return
    
    files_data = await manager.list_files(client_id)
    
    if not files_data:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_browse")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text=f"❌ Не удалось получить список файлов на {client.name}",
            reply_markup=reply_markup
        )
        return
    
    # Формируем список файлов
    text = f"📂 *{client.name}* - Файлы\n\n"
    
    folders = files_data.get('folders', [])
    files = files_data.get('files', [])
    
    if folders:
        text += "*Папки:*\n"
        for folder in folders:
            text += f"  📁 {folder['name']}\n"
        text += "\n"
    
    if files:
        text += "*Файлы:*\n"
        for file in files[:20]:  # Показываем первые 20
            size_kb = file.get('size', 0) / 1024
            text += f"  📄 {file['name']} ({size_kb:.2f} КБ)\n"
        
        if len(files) > 20:
            text += f"\n... и ещё {len(files) - 20} файлов"
    else:
        text += "*Файлов не найдено*"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_browse")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def remote_remove_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить клиента"""
    manager = get_remote_storage_manager()
    clients = manager.list_clients()
    
    keyboard = []
    for client in clients:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ {client.name}",
                callback_data=f"remote_delete_confirm_{client.client_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="remote_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text="🗑️ Выберите клиента для удаления:",
        reply_markup=reply_markup
    )


async def remote_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтвердить удаление клиента"""
    client_id = update.callback_query.data.replace("remote_delete_confirm_", "")
    
    manager = get_remote_storage_manager()
    client = manager.get_client(client_id)
    
    if not client:
        await update.callback_query.answer("Клиент не найден", show_alert=True)
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"remote_delete_yes_{client_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data="remote_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=f"⚠️ Вы уверены что хотите удалить клиента *{client.name}*?\n\nСами файлы на клиенте не будут удалены.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def remote_delete_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполнить удаление клиента"""
    client_id = update.callback_query.data.replace("remote_delete_yes_", "")
    
    manager = get_remote_storage_manager()
    client = manager.get_client(client_id)
    
    if manager.remove_client(client_id):
        text = f"✅ Клиент *{client.name}* удалён из списка"
    else:
        text = "❌ Ошибка при удалении клиента"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="remote_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def remote_browse_client_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать файлы на клиенте"""
    client_id = update.callback_query.data.replace("remote_browse_client_", "")
    
    manager = get_remote_storage_manager()
    client = manager.get_client(client_id)
    
    if not client:
        await update.callback_query.answer("Клиент не найден", show_alert=True)
        return
    
    files_data = await manager.list_files(client_id)
    
    if not files_data:
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_browse")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            text=f"❌ Не удалось получить список файлов на {client.name}",
            reply_markup=reply_markup
        )
        return
    
    # Формируем список файлов
    text = f"📂 *{client.name}* - Файлы\n\n"
    
    folders = files_data.get('folders', [])
    files = files_data.get('files', [])
    
    if folders:
        text += "*Папки:*\n"
        for folder in folders:
            text += f"  📁 {folder['name']}\n"
        text += "\n"
    
    if files:
        text += "*Файлы:*\n"
        for file in files[:20]:  # Показываем первые 20
            size_kb = file.get('size', 0) / 1024
            text += f"  📄 {file['name']} ({size_kb:.2f} КБ)\n"
        
        if len(files) > 20:
            text += f"\n... и ещё {len(files) - 20} файлов"
    else:
        text += "*Файлов не найдено*"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="remote_browse")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


__all__ = [
    'ADD_CLIENT_NAME', 'ADD_CLIENT_URL',
    'remote_storage_menu', 'remote_status', 'remote_add_client_start',
    'remote_add_client_name', 'remote_add_client_url',
    'remote_browse_files', 'remote_browse_client_files',
    'remote_remove_client', 'remote_delete_confirm', 'remote_delete_yes'
]
