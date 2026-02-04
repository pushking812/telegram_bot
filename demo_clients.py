"""
Демонстрация системы удалённых клиентов
Для тестирования можно запустить несколько локальных клиентов с разными портами
"""

import subprocess
import time
import sys
import os

def start_local_client(client_id, folder, port):
    """Запустить локальный клиент в отдельном процессе"""
    print(f"\n🚀 Запуск клиента {client_id} на порту {port}...")
    
    cmd = [
        sys.executable, 'local_client.py',
        '--id', client_id,
        '--folder', folder,
        '--port', str(port)
    ]
    
    try:
        process = subprocess.Popen(cmd)
        return process
    except Exception as e:
        print(f"❌ Ошибка при запуске {client_id}: {e}")
        return None


def main():
    print("=" * 60)
    print("📡 Демонстрация системы удалённых хранилищ")
    print("=" * 60)
    print("\nЭтот скрипт запускает несколько локальных клиентов для демонстрации")
    print("работы распределённого хранилища файлов.")
    print("\nКлиенты будут доступны на:")
    print("  • Client 1: http://localhost:5001")
    print("  • Client 2: http://localhost:5002")
    print("  • Client 3: http://localhost:5003")
    print("\nДля регистрации в боте используйте эти URL с IP адресом локальной машины")
    print("=" * 60)
    
    clients_config = [
        {
            'id': 'demo_client_1',
            'folder': './test_downloads_1',
            'port': 5001
        },
        {
            'id': 'demo_client_2',
            'folder': './test_downloads_2',
            'port': 5002
        },
        {
            'id': 'demo_client_3',
            'folder': './test_downloads_3',
            'port': 5003
        }
    ]
    
    processes = []
    
    try:
        # Создаём папки для демо
        for config in clients_config:
            os.makedirs(config['folder'], exist_ok=True)
            print(f"✅ Создана папка: {config['folder']}")
        
        print("\nЗапуск клиентов...\n")
        
        # Запускаем клиентов
        for config in clients_config:
            process = start_local_client(
                config['id'],
                config['folder'],
                config['port']
            )
            if process:
                processes.append(process)
            time.sleep(1)
        
        print("\n" + "=" * 60)
        print("✅ Все клиенты запущены!")
        print("\nДля остановки нажмите Ctrl+C")
        print("=" * 60)
        
        # Ждём пока пользователь не остановит
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Остановка клиентов...")
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print("✅ Клиент остановлен")
            except:
                process.kill()
                print("⚠️ Клиент принудительно завершён")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    main()
