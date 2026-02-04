# 📡 Система Удалённых Локальных Клиентов

##概念

Система позволяет подключать несколько локальных клиентов к основному боту, создавая распределённое хранилище файлов. Каждый локальный клиент:

- 🖥️ Запускается на отдельном компьютере
- 📁 Управляет своей папкой `downloads`
- 🌐 Предоставляет REST API для доступа к файлам
- 🔗 Регистрируется в центральном боте

## Архитектура

```
┌─────────────────────────────────┐
│  Telegram Bot (Replit)          │
│  - Основное хранилище           │
│  - Управление клиентами         │
│  - Распределение файлов         │
└────────┬────────────────────────┘
         │
    ┌────┴────┬────────┬────────┐
    │          │        │        │
    ▼          ▼        ▼        ▼
┌────────┐┌────────┐┌────────┐┌────────┐
│Client 1││Client 2││Client 3││Client N│
│local_  ││local_  ││local_  ││local_  │
│client  ││client  ││client  ││client  │
└────────┘└────────┘└────────┘└────────┘
(Home PC) (Work PC) (Server) (NAS)
```

## Установка и Запуск

### 1️⃣ Установка зависимостей для клиента

На каждом локальном компьютере:

```bash
# На локальной машине (не на Replit)
pip install -r requirements_client.txt
```

### 2️⃣ Запуск локального клиента

```bash
# Простой запуск (порт 5000, папка ./downloads_local)
python local_client.py

# С указанием параметров
python local_client.py --id home_pc --folder /path/to/downloads --port 5000

# На Windows можно указать полный путь
python local_client.py --id my_pc --folder C:\Users\YourName\Documents\downloads --port 5000
```

Параметры:
- `--id` - уникальный ID клиента (по умолчанию: случайный)
- `--folder` - путь к папке downloads (по умолчанию: ./downloads_local)
- `--host` - IP/hostname (по умолчанию: 0.0.0.0, слушает на всех интерфейсах)
- `--port` - порт API (по умолчанию: 5000)

### 3️⃣ Подключение клиента к боту

В меню бота:
1. Откройте раздел "⚙️ Настройки" или используйте команду `/remote`
2. Нажмите "➕ Добавить удалённый клиент"
3. Введите имя клиента (например: "Home PC")
4. Введите URL: `http://<IP_АДРЕС>:<ПОРТ>`
   - Для локальной сети: `http://192.168.1.100:5000`
   - Для удалённого доступа: `http://example.com:5000`

## API Эндпоинты Клиента

### Статус
```
GET /health
GET /info
```

### Файловые операции
```
GET  /list?folder=subfolder
POST /upload (multipart/form-data)
GET  /download/<path>
DELETE /delete/<path>
```

### Логирование
```
GET /logs?limit=100
```

## Примеры использования

### Проверка статуса клиента
```bash
curl http://192.168.1.100:5000/health
```

### Получение информации
```bash
curl http://192.168.1.100:5000/info
```

### Получение списка файлов
```bash
curl http://192.168.1.100:5000/list
curl http://192.168.1.100:5000/list?folder=subfolder
```

### Загрузка файла
```bash
curl -F "file=@document.pdf" \
     -F "subfolder=documents" \
     http://192.168.1.100:5000/upload
```

### Скачивание файла
```bash
curl -O http://192.168.1.100:5000/download/documents/document.pdf
```

### Удаление файла
```bash
curl -X DELETE http://192.168.1.100:5000/delete/documents/document.pdf
```

## Использование в боте

### В коде Python
```python
from remote_storage import get_remote_storage_manager

manager = get_remote_storage_manager()

# Добавить клиента
manager.add_client('home_pc', 'Home PC', 'http://192.168.1.100:5000')

# Получить информацию
info = await manager.get_client_info('home_pc')

# Загрузить файл
success, msg = await manager.upload_file('home_pc', 'local_file.pdf', 'documents')

# Скачать файл
success, msg = await manager.download_file('home_pc', 'documents/file.pdf', 'local_path.pdf')

# Удалить файл
success, msg = await manager.delete_file('home_pc', 'documents/file.pdf')

# Проверить статус всех клиентов
statuses = await manager.check_all_clients()
```

## Безопасность

⚠️ **Важно:**

1. **Локальная сеть**: API клиентов не защищён паролем - используйте только в доверенной локальной сети
2. **Удалённый доступ**: Для удалённого доступа используйте:
   - Firewall с ограничениями IP
   - Reverse Proxy (Nginx) с аутентификацией
   - VPN для доступа к клиентам
3. **Пути**: Система предотвращает доступ за пределы основной папки
4. **Расширения файлов**: Ограничивайте расширения на уровне обработчиков бота

## Примеры сценариев

### Сценарий 1: Домашний компьютер + Replit бот
```bash
# На домашнем ПК
python local_client.py --id home_pc --folder /home/user/downloads

# В боте добавляем
# URL: http://192.168.1.100:5000 (локальный IP)
# или http://home_pc.local:5000 (если доступно)
```

### Сценарий 2: Несколько офисов
```bash
# Office 1
python local_client.py --id office_london --folder /mnt/files

# Office 2
python local_client.py --id office_tokyo --folder /data/downloads

# В боте регистрируем оба
# URL1: http://office1.company.com:5000
# URL2: http://office2.company.com:5000
```

### Сценарий 3: NAS + персональный компьютер
```bash
# NAS (большое хранилище)
python local_client.py --id nas_storage --folder /mnt/nas/files --port 5001

# PC (быстрый доступ)
python local_client.py --id pc_cache --folder /home/user/fast_cache --port 5002
```

## Мониторинг и Логирование

Логи операций сохраняются в `.client_log.json`:
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

## Продвинутые конфигурации

### Запуск как сервис (Windows)

Создайте батник `start_client.bat`:
```batch
@echo off
cd C:\path\to\fileserver_bot
python local_client.py --id my_pc --folder C:\Users\YourName\Downloads --port 5000
pause
```

Используйте Task Scheduler для автозагрузки.

### Запуск как сервис (Linux)

Создайте файл `/etc/systemd/system/local-client.service`:
```ini
[Unit]
Description=Local File Client for FileServer Bot
After=network.target

[Service]
Type=simple
User=fileserver
WorkingDirectory=/home/fileserver/fileserver_bot
ExecStart=/usr/bin/python3 local_client.py --id linux_client --folder /mnt/files
Restart=always

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable local-client
sudo systemctl start local-client
```

## Поиск и решение проблем

### Клиент не доступен
```bash
# Проверить доступность
curl http://192.168.1.100:5000/health

# Проверить IP адрес
ipconfig (Windows)
ifconfig (Linux/Mac)
```

### Файлы не загружаются
- Проверьте права доступа к папке
- Убедитесь что папка существует и доступна для записи

### Медленная работа
- Проверьте скорость сети между ботом и клиентом
- Используйте `--port` отличный от стандартного если есть конфликты

## Дополнительные возможности

### Для будущих версий:
- [ ] Шифрование файлов
- [ ] Аутентификация по API ключам
- [ ] Синхронизация между клиентами
- [ ] Балансировка нагрузки
- [ ] Кэширование часто используемых файлов
- [ ] Веб-интерфейс для управления клиентами
