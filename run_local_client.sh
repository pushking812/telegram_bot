#!/bin/bash

# Скрипт для запуска локального клиента на Linux/Mac
# Использование: ./run_local_client.sh [ID] [FOLDER] [PORT]

# Параметры по умолчанию
CLIENT_ID="linux_pc"
DOWNLOAD_FOLDER="$HOME/Downloads"
PORT="5000"

# Если переданы параметры
if [ ! -z "$1" ]; then CLIENT_ID="$1"; fi
if [ ! -z "$2" ]; then DOWNLOAD_FOLDER="$2"; fi
if [ ! -z "$3" ]; then PORT="$3"; fi

echo ""
echo "============================================"
echo "  Local File Client - FileServer Bot"
echo "============================================"
echo ""
echo "Client ID: $CLIENT_ID"
echo "Folder:   $DOWNLOAD_FOLDER"
echo "Port:     $PORT"
echo "URL:      http://localhost:$PORT"
echo ""
echo "Запуск..."
echo ""

# Убедимся что папка существует
mkdir -p "$DOWNLOAD_FOLDER"

# Запускаем клиента
python3 local_client.py --id "$CLIENT_ID" --folder "$DOWNLOAD_FOLDER" --port "$PORT"
