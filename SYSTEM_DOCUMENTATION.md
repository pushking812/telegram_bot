# 📋 Документация: Система распределённых локальных клиентов FileServer Bot

## 📑 Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Новые файлы](#новые-файлы)
3. [Установка и запуск](#установка-и-запуск)
4. [Примеры использования](#примеры-использования)
5. [API документация](#api-документация)
6. [Интеграция с ботом](#интеграция-с-ботом)

---

## 🏗️ Обзор архитектуры

### Компоненты системы

```
┌──────────────────────────────────────────────────────────────┐
│                    Telegram Bot (Replit)                     │
│  - fileserver_bot.py          Основной бот                   │
│  - handlers/remote_handlers.py Обработчики команд             │
│  - remote_storage.py          Менеджер удалённых клиентов    │
└──────────────┬───────────────────────────────────────────────┘
               │
         ┌─────┼─────┬──────────┬──────────┐
         │     │     │          │          │
         ▼     ▼     ▼          ▼          ▼
    ┌─────┐┌────┐┌─────┐┌──────┐┌──────┐
    │Client││Clnt││Clnt ││Clnt  ││Clnt  │
    │ 1    ││ 2  ││ 3   ││  4   ││  N   │
    │:5000 ││:500││:5002││:5003 ││:5004 │
    └─────┘└────┘└─────┘└──────┘└──────┘
    (PC 1)(PC 2)(Server)(NAS)(Remote)
```

### Поток данных

1. **Пользователь** отправляет команду в Telegram боту
2. **Telegram Bot** обрабатывает команду через `handlers/remote_handlers.py`
3. **RemoteStorageManager** управляет подключениями к клиентам
4. **Local Client** API обрабатывает запросы к локальным файлам

---

## 📂 Новые файлы

### Основные компоненты

#### `local_client.py` (325 строк)
- Flask приложение для локального доступа к файлам
- REST API с поддержкой загрузки/скачивания
- Логирование всех операций
- Проверка безопасности (предотвращение path traversal)

**Класс `LocalFileClient`:**
```python
def __init__(self, client_id, local_folder, host='localhost', port=5000)
def _setup_routes()          # Инициализация REST API
def run()                    # Запуск сервера
```

**Маршруты API:**
```
GET  /health                 # Проверка статуса
GET  /info                   # Информация о клиенте
GET  /list                   # Список файлов
POST /upload                 # Загрузка файла
GET  /download/<path>        # Скачивание файла
DELETE /delete/<path>        # Удаление файла
GET  /logs                   # Логи операций
```

#### `remote_storage.py` (340 строк)
- Менеджер удалённых клиентов
- Асинхронное взаимодействие с клиентами через aiohttp
- Сохранение конфигурации клиентов в JSON

**Класс `RemoteClient`:**
```python
def __init__(self, client_id, name, url)
def to_dict()                # Сериализация
def from_dict()              # Десериализация
```

**Класс `RemoteStorageManager`:**
```python
def add_client(client_id, name, url)
def remove_client(client_id)
def get_client(client_id)
def list_clients()
async def check_health(client_id)
async def get_client_info(client_id)
async def list_files(client_id, folder)
async def upload_file(client_id, file_path, subfolder)
async def download_file(client_id, remote_path, local_path)
async def delete_file(client_id, remote_path)
async def check_all_clients()
```

#### `handlers/remote_handlers.py` (321 строка)
- Telegram обработчики для управления клиентами
- ConversationHandler для добавления новых клиентов
- Вывод статуса и информации о клиентах

**Основные функции:**
```python
async def remote_storage_menu()              # Главное меню
async def remote_status()                    # Показать статусы
async def remote_add_client_start()          # Начало добавления
async def remote_add_client_name()           # Получить имя
async def remote_add_client_url()            # Получить URL
async def remote_browse_files()              # Просмотр файлов
async def remote_browse_client_files()       # Файлы на клиенте
async def remote_remove_client()             # Удаление клиента
async def remote_delete_confirm()            # Подтверждение
async def remote_delete_yes()                # Выполнение
```

### Документация

#### `REMOTE_CLIENTS_GUIDE.md`
Полное руководство по использованию системы:
- Описание архитектуры
- Установка и запуск
- API примеры
- Сценарии использования
- Мониторинг и логирование
- Продвинутые конфигурации
- Поиск и решение проблем

#### `UPDATE_v2.0.md`
Описание обновлений версии 2.0:
- Новые возможности
- Быстрый старт
- Структура файлов
- Примеры использования
- Информация о безопасности
- Дорожная карта развития

#### `QUICKSTART.md`
Краткое руководство для быстрого старта

### Утилиты

#### `run_local_client.bat` (Windows)
Батник для запуска локального клиента на Windows

#### `run_local_client.sh` (Linux/Mac)
Shell скрипт для запуска на Linux/Mac

#### `demo_clients.py`
Демонстрационный скрипт для запуска нескольких клиентов

---

## 💾 Файлы конфигурации

### `remote_clients.json`
```json
[
  {
    "client_id": "home_pc",
    "name": "Home PC",
    "url": "http://192.168.1.100:5000",
    "is_online": true,
    "last_check": "2024-02-04T10:30:15.123456",
    "folder_size": 5368709120,
    "file_count": 1024,
    "available_space": 536870912000
  }
]
```

### `.client_log.json` (в папке клиента)
```json
[
  {
    "timestamp": "2024-02-04T10:30:15.123456",
    "operation": "upload",
    "filename": "document.pdf",
    "subfolder": "documents",
    "client_id": "home_pc"
  }
]
```

---

## 🔧 Установка и запуск

### Требования
- Python 3.7+
- Flask 2.3.3
- Flask-CORS 4.0.0
- aiohttp 3.9.1 (для бота)

### Установка зависимостей

**На сервере бота:**
```bash
pip install -r requirements.txt
```

**На локальных машинах (клиентах):**
```bash
pip install -r requirements_client.txt
```

### Запуск локального клиента

```bash
# Базовый запуск
python local_client.py

# С параметрами
python local_client.py --id home_pc --folder /path/to/downloads --port 5000

# На Windows с полным путём
python local_client.py --id my_pc --folder C:\Users\John\Downloads --port 5000
```

### Запуск основного бота

```bash
# Обновлённый бот с поддержкой удалённых клиентов
python fileserver_bot.py
```

---

## 💡 Примеры использования

### Python код

```python
from remote_storage import get_remote_storage_manager
import asyncio

async def example():
    manager = get_remote_storage_manager()
    
    # Добавить клиента
    manager.add_client('home', 'Home PC', 'http://192.168.1.100:5000')
    
    # Проверить статус
    is_online = await manager.check_health('home')
    print(f"Клиент онлайн: {is_online}")
    
    # Получить информацию
    info = await manager.get_client_info('home')
    print(f"Размер: {info['folder_size']} байт")
    
    # Загрузить файл
    success, msg = await manager.upload_file('home', 'local_file.pdf', 'documents')
    print(f"Загружено: {success}")
    
    # Список файлов
    files = await manager.list_files('home', 'documents')
    for file in files['files']:
        print(f"- {file['name']} ({file['size']} байт)")

asyncio.run(example())
```

### cURL примеры

```bash
# Проверка здоровья
curl http://192.168.1.100:5000/health

# Получение информации
curl http://192.168.1.100:5000/info

# Список файлов
curl http://192.168.1.100:5000/list
curl "http://192.168.1.100:5000/list?folder=documents"

# Загрузка файла
curl -F "file=@document.pdf" http://192.168.1.100:5000/upload
curl -F "file=@photo.jpg" -F "subfolder=photos" http://192.168.1.100:5000/upload

# Скачивание файла
curl -O http://192.168.1.100:5000/download/document.pdf

# Удаление файла
curl -X DELETE http://192.168.1.100:5000/delete/document.pdf

# Получение логов
curl http://192.168.1.100:5000/logs?limit=50
```

---

## 📡 API Документация

### GET /health
Проверка статуса клиента

**Ответ:**
```json
{
  "status": "ok",
  "client_id": "home_pc",
  "local_folder": "/home/user/downloads",
  "available_space": 536870912000
}
```

### GET /info
Получение информации о клиенте

**Ответ:**
```json
{
  "client_id": "home_pc",
  "local_folder": "/home/user/downloads",
  "folder_size": 5368709120,
  "file_count": 1024,
  "available_space": 536870912000
}
```

### GET /list
Получение списка файлов

**Параметры:**
- `folder` (optional) - подпапка для просмотра

**Ответ:**
```json
{
  "client_id": "home_pc",
  "folder": "",
  "path": "/home/user/downloads",
  "folders": [
    {
      "name": "documents",
      "type": "dir",
      "modified": "2024-02-04T10:30:15"
    }
  ],
  "files": [
    {
      "name": "file.pdf",
      "type": "file",
      "size": 1048576,
      "modified": "2024-02-04T10:30:15",
      "hash": "5d41402abc4b2a76b9719d911017c592"
    }
  ]
}
```

### POST /upload
Загрузка файла

**Параметры (multipart/form-data):**
- `file` - файл для загрузки (required)
- `subfolder` - подпапка назначения (optional)

**Ответ:**
```json
{
  "status": "success",
  "filename": "document.pdf",
  "path": "documents/document.pdf",
  "size": 1048576
}
```

### GET /download/<path>
Скачивание файла

**Ответ:** Содержимое файла (binary)

### DELETE /delete/<path>
Удаление файла

**Ответ:**
```json
{
  "status": "success",
  "message": "File deleted"
}
```

### GET /logs
Получение логов операций

**Параметры:**
- `limit` - количество логов (по умолчанию: 100)

**Ответ:**
```json
{
  "client_id": "home_pc",
  "logs": [
    {
      "timestamp": "2024-02-04T10:30:15",
      "operation": "upload",
      "filename": "document.pdf",
      "subfolder": "documents"
    }
  ]
}
```

---

## 🎮 Интеграция с ботом

### Меню в Telegram

```
Главное меню
├── 📡 Удалённые хранилища
│   ├── 🔄 Обновить статус
│   ├── 📊 Статус клиентов
│   ├── 📂 Просмотр файлов
│   └── ➕ Добавить клиент
│       ├── Введите имя клиента
│       └── Введите URL клиента
├── ⚙️ Настройки
└── ... (другие опции)
```

### Обработанные callback'и

```python
'remote_menu'                  # Главное меню
'remote_refresh'               # Обновить статус
'remote_status'                # Показать статусы
'remote_add'                   # Добавить клиента
'remote_browse'                # Просмотр файлов
'remote_browse_client_<id>'    # Файлы на клиенте
'remote_delete_confirm_<id>'   # Подтверждение удаления
'remote_delete_yes_<id>'       # Выполнить удаление
```

### ConversationHandler состояния

```python
ADD_CLIENT_NAME = 0  # Ввод имени клиента
ADD_CLIENT_URL = 1   # Ввод URL клиента
```

---

## 🔐 Безопасность

### Реализованные проверки

1. **Path Traversal Protection**
   ```python
   # Предотвращение доступа за пределы папки
   if not target_path.startswith(os.path.abspath(self.local_folder)):
       return 403 # Access Denied
   ```

2. **Логирование операций**
   ```python
   # Все операции записываются в .client_log.json
   {
       "timestamp": "...",
       "operation": "...",
       "filename": "...",
       "client_id": "..."
   }
   ```

3. **Проверка доступности**
   ```python
   # Асинхронная проверка здоровья всех клиентов
   await manager.check_all_clients()
   ```

### Рекомендации для продакшена

1. **Firewall** - ограничьте доступ к портам клиентов
2. **VPN** - используйте для удалённого доступа
3. **HTTPS** - используйте reverse proxy (Nginx) с SSL
4. **Аутентификация** - добавьте API ключи (future)
5. **Шифрование** - кодируйте файлы при передаче (future)

---

## 📊 Мониторинг

### Проверка статуса клиентов

```python
manager = get_remote_storage_manager()

# Проверить одного клиента
is_online = await manager.check_health('home_pc')

# Проверить всех клиентов
statuses = await manager.check_all_clients()
for client_id, is_online in statuses.items():
    print(f"{client_id}: {'🟢' if is_online else '🔴'}")
```

### Просмотр логов клиента

```bash
curl http://192.168.1.100:5000/logs?limit=100
```

---

## 🚀 Развитие проекта

### Текущий статус
✅ Загрузка/скачивание файлов  
✅ Логирование операций  
✅ Проверка статуса клиентов  
✅ REST API  
✅ Telegram интеграция  

### План (будущие версии)
- [ ] Веб-интерфейс управления
- [ ] Аутентификация через API ключи
- [ ] Синхронизация между клиентами
- [ ] Зашифрованная передача
- [ ] Балансировка нагрузки
- [ ] Резервное копирование
- [ ] Веб-панель статистики

---

## 📞 Поддержка

Для получения помощи см.:
- [QUICKSTART.md](QUICKSTART.md) - быстрый старт
- [REMOTE_CLIENTS_GUIDE.md](REMOTE_CLIENTS_GUIDE.md) - полное руководство
- [UPDATE_v2.0.md](UPDATE_v2.0.md) - описание обновлений

---

**Версия 2.0** - February 4, 2026  
FileServer Bot - Distributed Local Clients System
