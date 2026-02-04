@echo off
REM Скрипт для запуска локального клиента на Windows
REM Использование: run_local_client.bat [ID] [FOLDER] [PORT]

setlocal enabledelayedexpansion

REM Параметры по умолчанию
set CLIENT_ID=windows_pc
set DOWNLOAD_FOLDER=%USERPROFILE%\Downloads
set PORT=5000

REM Если переданы параметры
if not "%1"=="" set CLIENT_ID=%1
if not "%2"=="" set DOWNLOAD_FOLDER=%2
if not "%3"=="" set PORT=%3

echo.
echo ============================================
echo   Local File Client - FileServer Bot
echo ============================================
echo.
echo Client ID: %CLIENT_ID%
echo Folder:   %DOWNLOAD_FOLDER%
echo Port:     %PORT%
echo URL:      http://localhost:%PORT%
echo.
echo Запуск...
echo.

python local_client.py --id %CLIENT_ID% --folder %DOWNLOAD_FOLDER% --port %PORT%

pause
