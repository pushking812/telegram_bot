# 🚀 Быстрый старт: Удалённые локальные клиенты

## За 5 минут к готовой системе!

### Шаг 1️⃣: На локальной машине (где папка downloads)

```bash
# Установка
pip install Flask==2.3.3 Flask-CORS==4.0.0

# Запуск клиента
python local_client.py --id my_home_pc --folder C:\Users\YourName\Downloads --port 5000
```

**Будет видно:**
```
============================================
  🚀 Local Client #my_home_pc запущен
  📁 Папка: C:\Users\YourName\Downloads
  🌐 API: http://localhost:5000
============================================
```

### Шаг 2️⃣: Узнайте IP адрес локальной машины

**Windows:**
```cmd
ipconfig
```
Ищите `IPv4 Address` в разделе Ethernet или Wi-Fi (например: `192.168.1.100`)

**Linux/Mac:**
```bash
ifconfig
```

### Шаг 3️⃣: В Telegram боте

1. Нажмите 📡 **Удалённые хранилища**
2. Нажмите ➕ **Добавить клиент**
3. Введите имя: `Home PC`
4. Введите URL: `http://192.168.1.100:5000`
5. ✅ Готово!

---

## 🧪 Тестирование

### Проверить доступность
```bash
curl http://192.168.1.100:5000/health
```

Ответ:
```json
{
  "status": "ok",
  "client_id": "my_home_pc",
  "available_space": 536870912000
}
```

### Список файлов
```bash
curl http://192.168.1.100:5000/list
```

### Загрузить файл
```bash
curl -F "file=@document.pdf" http://192.168.1.100:5000/upload
```

---

## 💡 Советы

### Запуск нескольких клиентов с разными портами
```bash
# Терминал 1
python local_client.py --id client1 --port 5000

# Терминал 2
python local_client.py --id client2 --port 5001

# Терминал 3
python local_client.py --id client3 --port 5002
```

### Без аргументов (значения по умолчанию)
```bash
python local_client.py
# Использует: ID=случайный, папка=./downloads_local, порт=5000
```

### Батник для Windows
```batch
@echo off
python local_client.py --id home_pc --folder C:\Users\YourName\Downloads --port 5000
pause
```

Сохраните как `start_client.bat` и двойной клик для запуска.

---

## 🔧 Расширенные параметры

```
--id          Уникальный ID клиента
              По умолчанию: случайные 8 символов
              Пример: --id home_pc

--folder      Путь к папке downloads
              По умолчанию: ./downloads_local
              Пример: --folder C:\Users\John\Downloads

--host        IP/hostname для API
              По умолчанию: 0.0.0.0 (слушает на всех)
              Пример: --host 0.0.0.0

--port        Порт для API
              По умолчанию: 5000
              Пример: --port 5001
```

---

## ⚠️ Проблемы?

### "Connection refused"
- Убедитесь что клиент запущен
- Проверьте правильность IP и порта
- Проверьте firewall

### "Folder not found"
- Путь должен быть полный: `C:\Users\...` или `/home/...`
- Папка будет создана автоматически если её нет

### "Permission denied"
- Убедитесь что у процесса есть права на доступ к папке

---

## 📚 Ссылки

- Полное руководство: [REMOTE_CLIENTS_GUIDE.md](REMOTE_CLIENTS_GUIDE.md)
- Обновления v2.0: [UPDATE_v2.0.md](UPDATE_v2.0.md)

---

**Готово! Ваша распределённая система файлов работает! 🎉**
