# 👨‍💻 Примеры интеграции для разработчиков

## Использование RemoteStorageManager в вашем коде

### 1. Базовое использование

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def example_basic():
    """Базовый пример использования"""
    manager = get_remote_storage_manager()
    
    # Получить список всех клиентов
    clients = manager.list_clients()
    print(f"Подключено клиентов: {len(clients)}")
    
    for client in clients:
        print(f"  - {client.name} ({client.client_id}): {client.url}")

asyncio.run(example_basic())
```

### 2. Добавление нового клиента программно

```python
from remote_storage import get_remote_storage_manager

def add_client_example():
    """Добавление клиента программно"""
    manager = get_remote_storage_manager()
    
    # Добавляем новый клиент
    success = manager.add_client(
        client_id='home_london',
        name='Home - London',
        url='http://192.168.1.50:5000'
    )
    
    if success:
        print("✅ Клиент успешно добавлен")
    else:
        print("❌ Клиент уже существует или ошибка при добавлении")

add_client_example()
```

### 3. Проверка статуса клиента

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def check_client_status():
    """Проверка статуса клиента"""
    manager = get_remote_storage_manager()
    
    client_id = 'home_pc'
    
    # Проверить здоровье (онлайн/офлайн)
    is_online = await manager.check_health(client_id)
    print(f"Клиент онлайн: {is_online}")
    
    if is_online:
        # Получить информацию
        info = await manager.get_client_info(client_id)
        if info:
            print(f"Размер папки: {info['folder_size']} байт")
            print(f"Файлов: {info['file_count']}")
            print(f"Доступно места: {info['available_space']} байт")

asyncio.run(check_client_status())
```

### 4. Работа с файлами

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def file_operations():
    """Операции с файлами"""
    manager = get_remote_storage_manager()
    
    # Получить список файлов
    files_data = await manager.list_files('home_pc', 'documents')
    if files_data:
        print("Папки:")
        for folder in files_data['folders']:
            print(f"  📁 {folder['name']}")
        
        print("Файлы:")
        for file in files_data['files']:
            print(f"  📄 {file['name']} ({file['size']} байт)")
    
    # Загрузить файл
    success, msg = await manager.upload_file(
        'home_pc',
        'C:\\Users\\John\\document.pdf',
        'documents'
    )
    if success:
        print(f"✅ Файл загружен: {msg}")
    else:
        print(f"❌ Ошибка: {msg}")
    
    # Скачать файл
    success, msg = await manager.download_file(
        'home_pc',
        'documents/document.pdf',
        'C:\\Downloads\\document.pdf'
    )
    if success:
        print("✅ Файл скачан")
    else:
        print(f"❌ Ошибка: {msg}")
    
    # Удалить файл
    success, msg = await manager.delete_file(
        'home_pc',
        'documents/document.pdf'
    )
    if success:
        print("✅ Файл удалён")
    else:
        print(f"❌ Ошибка: {msg}")

asyncio.run(file_operations())
```

### 5. Проверка всех клиентов

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def check_all_clients():
    """Проверка всех клиентов"""
    manager = get_remote_storage_manager()
    
    print("Проверка статуса всех клиентов...\n")
    
    statuses = await manager.check_all_clients()
    
    for client_id, is_online in statuses.items():
        client = manager.get_client(client_id)
        status = "🟢 онлайн" if is_online else "🔴 офлайн"
        print(f"{client.name}: {status}")

asyncio.run(check_all_clients())
```

## Интеграция с Telegram ботом

### 1. Обработчик команды для просмотра статуса

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from remote_storage import get_remote_storage_manager

async def remote_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для просмотра статуса удалённых клиентов"""
    manager = get_remote_storage_manager()
    
    # Проверяем статус всех клиентов
    statuses = await manager.check_all_clients()
    
    # Формируем сообщение
    text = "📡 *Статус удалённых хранилищ*\n\n"
    
    clients = manager.list_clients()
    if not clients:
        text += "Клиентов не подключено"
    else:
        for client in clients:
            status_icon = "🟢" if statuses.get(client.client_id, False) else "🔴"
            text += f"{status_icon} *{client.name}*\n"
            
            if statuses.get(client.client_id):
                info = await manager.get_client_info(client.client_id)
                if info:
                    size_mb = info.get('folder_size', 0) / (1024 * 1024)
                    text += f"   📊 Размер: {size_mb:.2f} МБ\n"
                    text += f"   📁 Файлов: {info.get('file_count', 0)}\n"
            text += "\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')
```

### 2. Встроенная команда /remote

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from remote_storage import get_remote_storage_manager

async def remote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /remote для управления удалёнными клиентами"""
    manager = get_remote_storage_manager()
    
    clients = manager.list_clients()
    
    # Создаём кнопки для каждого клиента
    keyboard = []
    for client in clients:
        keyboard.append([
            InlineKeyboardButton(
                f"{client.name}",
                callback_data=f"remote_client_{client.client_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить клиент", callback_data="remote_add"),
        InlineKeyboardButton("🔄 Обновить", callback_data="remote_refresh")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📡 *Удалённые хранилища*\n\n"
        f"Подключено клиентов: {len(clients)}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# В main():
# application.add_handler(CommandHandler("remote", remote_command))
```

### 3. Обработчик загрузки на удалённый клиент

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from remote_storage import get_remote_storage_manager
import os

SELECT_CLIENT, SELECT_SUBFOLDER = range(2)

async def upload_to_remote_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало загрузки на удалённый клиент"""
    manager = get_remote_storage_manager()
    clients = manager.list_clients()
    
    if not clients:
        await update.message.reply_text("❌ Нет подключённых клиентов")
        return ConversationHandler.END
    
    # Показываем список клиентов
    keyboard = []
    for client in clients:
        keyboard.append([
            InlineKeyboardButton(
                f"{client.name}",
                callback_data=f"upload_client_{client.client_id}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выберите клиент для загрузки:",
        reply_markup=reply_markup
    )
    
    return SELECT_CLIENT

async def upload_to_remote_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор подпапки для загрузки"""
    query = update.callback_query
    await query.answer()
    
    client_id = query.data.replace("upload_client_", "")
    context.user_data['remote_client_id'] = client_id
    
    manager = get_remote_storage_manager()
    client = manager.get_client(client_id)
    
    # Получаем список папок
    files_data = await manager.list_files(client_id)
    
    if not files_data:
        await query.edit_message_text("❌ Не удалось получить список папок")
        return ConversationHandler.END
    
    folders = files_data.get('folders', [])
    
    keyboard = []
    for folder in folders:
        keyboard.append([
            InlineKeyboardButton(
                f"📁 {folder['name']}",
                callback_data=f"upload_folder_{folder['name']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("📁 Корневая папка", callback_data="upload_folder_root")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите папку на {client.name}:",
        reply_markup=reply_markup
    )
    
    return SELECT_SUBFOLDER

async def upload_to_remote_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загрузка файла"""
    query = update.callback_query
    await query.answer()
    
    subfolder = query.data.replace("upload_folder_", "")
    if subfolder == "root":
        subfolder = ""
    
    context.user_data['remote_subfolder'] = subfolder
    
    await query.edit_message_text(
        "Отправьте файл для загрузки"
    )
    
    return ConversationHandler.END  # Ожидаем файл в message_handler

# В main():
# conv_handler = ConversationHandler(
#     entry_points=[CommandHandler("upload_remote", upload_to_remote_start)],
#     states={
#         SELECT_CLIENT: [CallbackQueryHandler(...)],
#         SELECT_SUBFOLDER: [CallbackQueryHandler(...)]
#     },
#     fallbacks=[...]
# )
# application.add_handler(conv_handler)
```

## REST API примеры для интеграции

### 1. Прямое взаимодействие с локальным клиентом

```python
import aiohttp
import asyncio

async def direct_api_example():
    """Прямая работа с API клиента"""
    
    async with aiohttp.ClientSession() as session:
        # Получить статус
        async with session.get('http://192.168.1.100:5000/health') as resp:
            health = await resp.json()
            print(f"Статус: {health['status']}")
        
        # Получить список файлов
        async with session.get('http://192.168.1.100:5000/list') as resp:
            files = await resp.json()
            print(f"Файлов: {len(files['files'])}")
        
        # Загрузить файл
        with open('test.pdf', 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f)
            data.add_field('subfolder', 'documents')
            
            async with session.post(
                'http://192.168.1.100:5000/upload',
                data=data
            ) as resp:
                result = await resp.json()
                print(f"Загружено: {result['filename']}")

asyncio.run(direct_api_example())
```

### 2. Обработка ошибок при работе с удалённым клиентом

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def robust_file_operation():
    """Работа с файлами с обработкой ошибок"""
    manager = get_remote_storage_manager()
    
    client_id = 'home_pc'
    
    try:
        # Проверяем доступность клиента
        is_online = await manager.check_health(client_id)
        
        if not is_online:
            print(f"⚠️ Клиент {client_id} офлайн")
            return False
        
        # Пытаемся загрузить файл
        success, msg = await manager.upload_file(
            client_id,
            'local_file.pdf',
            'documents'
        )
        
        if not success:
            print(f"❌ Ошибка загрузки: {msg}")
            return False
        
        print(f"✅ Файл успешно загружен: {msg}")
        return True
        
    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

asyncio.run(robust_file_operation())
```

## Примеры мониторинга

### 1. Периодическая проверка статуса

```python
import asyncio
import time
from remote_storage import get_remote_storage_manager
from datetime import datetime

async def monitor_clients():
    """Периодический мониторинг клиентов"""
    manager = get_remote_storage_manager()
    
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Проверка статуса...")
        
        statuses = await manager.check_all_clients()
        
        for client_id, is_online in statuses.items():
            client = manager.get_client(client_id)
            status = "🟢" if is_online else "🔴"
            print(f"  {status} {client.name}")
        
        # Ждём 5 минут перед следующей проверкой
        await asyncio.sleep(300)

# Запустить в фоне
# asyncio.create_task(monitor_clients())
```

### 2. Статистика по клиентам

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def get_statistics():
    """Получение статистики по клиентам"""
    manager = get_remote_storage_manager()
    
    total_size = 0
    total_files = 0
    online_count = 0
    
    clients = manager.list_clients()
    
    for client in clients:
        info = await manager.get_client_info(client.client_id)
        
        if info:
            total_size += info.get('folder_size', 0)
            total_files += info.get('file_count', 0)
            
        is_online = await manager.check_health(client.client_id)
        if is_online:
            online_count += 1
    
    print(f"📊 Общая статистика:")
    print(f"  Клиентов: {len(clients)}")
    print(f"  Онлайн: {online_count}/{len(clients)}")
    print(f"  Общий размер: {total_size / (1024**3):.2f} ГБ")
    print(f"  Всего файлов: {total_files}")

asyncio.run(get_statistics())
```

---

**Больше примеров найдете в документации!**

[SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) - Полная документация  
[REMOTE_CLIENTS_GUIDE.md](REMOTE_CLIENTS_GUIDE.md) - Руководство пользователя
