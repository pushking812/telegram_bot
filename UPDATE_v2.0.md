# 🤖 FileServer Bot - Обновления версии 2.0

## ✨ Новые возможности: Система распределённых локальных клиентов

### Краткое описание

Теперь бот поддерживает подключение **множественных локальных клиентов** для управления распределённым хранилищем файлов. Это позволяет:

✅ Подключить локальные папки downloads с разных компьютеров  
✅ Управлять файлами через один интерфейс Telegram бота  
✅ Масштабировать хранилище без перемещения файлов на облако  
✅ Работать с файлами на удалённых ПК, серверах, NAS  

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# На сервере с ботом (Replit)
pip install -r requirements.txt

# На локальных машинах (где будут клиенты)
pip install -r requirements_client.txt
```

### 2. Запуск локального клиента

На каждом компьютере, который вы хотите подключить:

**Windows:**
```bash
python local_client.py --id my_pc --folder C:\Users\YourName\Downloads --port 5000
# или используйте батник
run_local_client.bat
```

**Linux/Mac:**
```bash
python local_client.py --id my_pc --folder ~/Downloads --port 5000
# или используйте скрипт
chmod +x run_local_client.sh
./run_local_client.sh
```

### 3. Подключение к боту

В меню бота:
1. 📡 **Удалённые хранилища**
2. ➕ **Добавить клиент**
3. Введите имя и URL (например: `http://192.168.1.100:5000`)

---

## 📋 Структура новых файлов

```
fileserver_bot/
├── local_client.py              # 🖥️ Локальный клиент
├── remote_storage.py            # 🔗 Менеджер удалённых клиентов
├── handlers/
│   └── remote_handlers.py       # 🎮 Обработчики команд
├── requirements_client.txt      # 📦 Зависимости клиента
├── run_local_client.bat         # ▶️ Запуск на Windows
├── run_local_client.sh          # ▶️ Запуск на Linux/Mac
├── demo_clients.py              # 🧪 Демонстрация
└── REMOTE_CLIENTS_GUIDE.md      # 📖 Полное руководство
```

---

## 🎮 Использование через Telegram

### Главное меню
```
📡 Удалённые хранилища
├── 🔄 Обновить статус
├── 📊 Статус клиентов
├── 📂 Просмотр файлов
└── ➕ Добавить клиент
```

### Действия
- **Добавить клиент** - регистрация нового локального хранилища
- **Просмотреть файлы** - список файлов на клиенте
- **Удалить клиента** - отключение хранилища (файлы остаются)

---

## 🔌 API Локального Клиента

### Health Check
```bash
curl http://localhost:5000/health
```

### Список файлов
```bash
curl http://localhost:5000/list
curl http://localhost:5000/list?folder=subfolder
```

### Загрузка файла
```bash
curl -F "file=@document.pdf" http://localhost:5000/upload
```

### Скачивание файла
```bash
curl -O http://localhost:5000/download/file.pdf
```

---

## 💻 Примеры сценариев

### Сценарий 1: Домашний ПК + Рабочий сервер

```
Home PC (5000)
  ├── Личные документы
  └── Фотографии

Work Server (5001)
  ├── Архивные проекты
  └── Резервные копии

Bot управляет обоими хранилищами через один интерфейс
```

### Сценарий 2: Офисы в разных городах

```
London Office (5000)
  └── UK Documents

Tokyo Office (5000, разный хост)
  └── Asia Documents

Mumbai Office (5000, разный хост)
  └── India Documents

Все синхронизированы в одном боте!
```

### Сценарий 3: NAS + локальные кэши

```
NAS Storage (большое хранилище на 5000)
  └── Архив файлов

Fast Cache (SSD на 5001)
  └── Часто используемые файлы

Bot автоматически распределяет файлы
```

---

## 📊 Мониторинг

Каждый клиент отслеживает:

```json
{
  "client_id": "home_pc",
  "name": "Home PC",
  "url": "http://192.168.1.100:5000",
  "is_online": true,
  "folder_size": 5368709120,
  "file_count": 1024,
  "available_space": 536870912000
}
```

---

## ⚙️ Расширенная конфигурация

### Запуск как сервис (Windows)

```batch
# start_client.bat
python local_client.py --id home_pc --folder D:\Downloads --port 5000
```

Добавьте в Task Scheduler для автозагрузки.

### Запуск как сервис (Linux)

```ini
# /etc/systemd/system/local-client.service
[Unit]
Description=Local File Client for FileServer Bot
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/fileserver/local_client.py --id linux_pc --folder /mnt/files
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable local-client
sudo systemctl start local-client
```

---

## 🔒 Безопасность

### Текущая защита
✅ Предотвращение выхода за пределы папки  
✅ Логирование всех операций  
✅ Проверка доступности клиентов  

### Рекомендации для продакшена
- Используйте **firewall** для ограничения доступа
- Использите **VPN** для удалённого доступа
- Добавьте **аутентификацию** (будущая версия)
- Шифруйте **файлы при передаче** (будущая версия)

---

## 📚 Документация

Полное руководство: [REMOTE_CLIENTS_GUIDE.md](REMOTE_CLIENTS_GUIDE.md)

---

## 🐛 Проблемы и решения

### Клиент недоступен
```bash
# Проверьте доступность
curl http://192.168.1.100:5000/health

# Проверьте IP
ipconfig (Windows)
ifconfig (Linux)
```

### Медленная загрузка
- Проверьте скорость сети
- Используйте другой порт если есть конфликт

### Файлы не видны
- Проверьте права доступа к папке
- Убедитесь в формате пути

---

## 🚀 Следующие версии

- [ ] Веб-интерфейс управления
- [ ] Аутентификация через API ключи
- [ ] Синхронизация между клиентами
- [ ] Зашифрованная передача файлов
- [ ] Балансировка нагрузки
- [ ] Резервное копирование и восстановление

---

## 📞 Поддержка

Для вопросов или проблем см. [REMOTE_CLIENTS_GUIDE.md](REMOTE_CLIENTS_GUIDE.md)

---

**Версия 2.0** - February 4, 2026
