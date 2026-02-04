"""
Local Client для управления локальной папкой downloads
Запускается на каждом локальном компьютере и предоставляет API для доступа к файлам
"""

import os
import json
import uuid
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import threading

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class LocalFileClient:
    def __init__(self, client_id, local_folder, host='localhost', port=5000):
        """
        Инициализация локального клиента
        
        Args:
            client_id: Уникальный ID клиента
            local_folder: Путь к локальной папке downloads
            host: Host для запуска API
            port: Port для запуска API
        """
        self.client_id = client_id
        self.local_folder = os.path.abspath(local_folder)
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)
        
        # Создаем папку если её нет
        os.makedirs(self.local_folder, exist_ok=True)
        
        # Инициализируем логирование операций
        self.operations_log = self._load_operations_log()
        
        self._setup_routes()
        
    def _setup_routes(self):
        """Настройка маршрутов Flask API"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Проверка статуса клиента"""
            return jsonify({
                'status': 'ok',
                'client_id': self.client_id,
                'local_folder': self.local_folder,
                'available_space': self._get_available_space()
            })
        
        @self.app.route('/info', methods=['GET'])
        def info():
            """Информация о клиенте"""
            return jsonify({
                'client_id': self.client_id,
                'local_folder': self.local_folder,
                'folder_size': self._get_folder_size(),
                'file_count': self._count_files(),
                'available_space': self._get_available_space()
            })
        
        @self.app.route('/list', methods=['GET'])
        def list_files():
            """Получить список файлов в папке"""
            try:
                folder = request.args.get('folder', '')
                target_path = os.path.join(self.local_folder, folder)
                
                # Security check - предотвращаем выход за пределы папки
                target_path = os.path.abspath(target_path)
                if not target_path.startswith(os.path.abspath(self.local_folder)):
                    return jsonify({'error': 'Access denied'}), 403
                
                if not os.path.exists(target_path):
                    return jsonify({'error': 'Folder not found'}), 404
                
                files = []
                dirs = []
                
                for item in os.listdir(target_path):
                    item_path = os.path.join(target_path, item)
                    stat = os.stat(item_path)
                    
                    if os.path.isdir(item_path):
                        dirs.append({
                            'name': item,
                            'type': 'dir',
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                    else:
                        files.append({
                            'name': item,
                            'type': 'file',
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'hash': self._get_file_hash(item_path)
                        })
                
                # Сортируем папки и файлы
                dirs.sort(key=lambda x: x['name'])
                files.sort(key=lambda x: x['name'])
                
                return jsonify({
                    'client_id': self.client_id,
                    'folder': folder,
                    'path': target_path,
                    'folders': dirs,
                    'files': files
                })
            except Exception as e:
                logger.error(f"Error listing files: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            """Загрузить файл на локальный клиент"""
            try:
                if 'file' not in request.files:
                    return jsonify({'error': 'No file provided'}), 400
                
                file = request.files['file']
                subfolder = request.form.get('subfolder', '')
                
                if file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400
                
                target_dir = os.path.join(self.local_folder, subfolder)
                os.makedirs(target_dir, exist_ok=True)
                
                # Security check
                target_dir = os.path.abspath(target_dir)
                if not target_dir.startswith(os.path.abspath(self.local_folder)):
                    return jsonify({'error': 'Access denied'}), 403
                
                # Сохраняем файл
                file_path = os.path.join(target_dir, file.filename)
                file_path = self._get_unique_path(file_path)
                file.save(file_path)
                
                # Логируем операцию
                self._log_operation('upload', file.filename, subfolder)
                
                return jsonify({
                    'status': 'success',
                    'filename': os.path.basename(file_path),
                    'path': os.path.relpath(file_path, self.local_folder),
                    'size': os.path.getsize(file_path)
                })
            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/download/<path:file_path>', methods=['GET'])
        def download_file(file_path):
            """Скачать файл с локального клиента"""
            try:
                full_path = os.path.join(self.local_folder, file_path)
                full_path = os.path.abspath(full_path)
                
                # Security check
                if not full_path.startswith(os.path.abspath(self.local_folder)):
                    return jsonify({'error': 'Access denied'}), 403
                
                if not os.path.exists(full_path):
                    return jsonify({'error': 'File not found'}), 404
                
                if not os.path.isfile(full_path):
                    return jsonify({'error': 'Not a file'}), 400
                
                # Логируем операцию
                self._log_operation('download', os.path.basename(full_path), os.path.dirname(file_path))
                
                return send_file(full_path, as_attachment=True)
            except Exception as e:
                logger.error(f"Error downloading file: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/delete/<path:file_path>', methods=['DELETE'])
        def delete_file(file_path):
            """Удалить файл на локальном клиенте"""
            try:
                full_path = os.path.join(self.local_folder, file_path)
                full_path = os.path.abspath(full_path)
                
                # Security check
                if not full_path.startswith(os.path.abspath(self.local_folder)):
                    return jsonify({'error': 'Access denied'}), 403
                
                if not os.path.exists(full_path):
                    return jsonify({'error': 'File not found'}), 404
                
                os.remove(full_path)
                self._log_operation('delete', os.path.basename(full_path), os.path.dirname(file_path))
                
                return jsonify({'status': 'success', 'message': 'File deleted'})
            except Exception as e:
                logger.error(f"Error deleting file: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/logs', methods=['GET'])
        def get_logs():
            """Получить логи операций"""
            limit = request.args.get('limit', 100, type=int)
            return jsonify({
                'client_id': self.client_id,
                'logs': self.operations_log[-limit:]
            })
    
    def _log_operation(self, operation, filename, subfolder=''):
        """Логирование операции"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'filename': filename,
            'subfolder': subfolder,
            'client_id': self.client_id
        }
        self.operations_log.append(log_entry)
        self._save_operations_log()
    
    def _load_operations_log(self):
        """Загрузить логи операций"""
        log_file = os.path.join(self.local_folder, '.client_log.json')
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_operations_log(self):
        """Сохранить логи операций"""
        log_file = os.path.join(self.local_folder, '.client_log.json')
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.operations_log[-1000:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving logs: {e}")
    
    def _get_file_hash(self, file_path):
        """Получить MD5 хеш файла"""
        try:
            md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    md5.update(chunk)
            return md5.hexdigest()
        except:
            return None
    
    def _get_unique_path(self, file_path):
        """Получить уникальный путь файла"""
        if not os.path.exists(file_path):
            return file_path
        
        name, ext = os.path.splitext(file_path)
        counter = 1
        while True:
            new_path = f"{name}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
    
    def _get_folder_size(self):
        """Получить размер папки в байтах"""
        total = 0
        for dirpath, dirnames, filenames in os.walk(self.local_folder):
            for filename in filenames:
                if not filename.startswith('.'):
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total += os.path.getsize(file_path)
                    except:
                        pass
        return total
    
    def _count_files(self):
        """Подсчитать количество файлов"""
        count = 0
        for dirpath, dirnames, filenames in os.walk(self.local_folder):
            for filename in filenames:
                if not filename.startswith('.'):
                    count += 1
        return count
    
    def _get_available_space(self):
        """Получить доступное место на диске"""
        try:
            import shutil
            stat = shutil.disk_usage(self.local_folder)
            return stat.free
        except:
            return None
    
    def run(self):
        """Запустить API сервер"""
        logger.info(f"🚀 Local Client #{self.client_id} запущен")
        logger.info(f"📁 Папка: {self.local_folder}")
        logger.info(f"🌐 API: http://{self.host}:{self.port}")
        logger.info(f"✅ Доступные функции:")
        logger.info(f"   - /health (статус)")
        logger.info(f"   - /info (информация)")
        logger.info(f"   - /list (список файлов)")
        logger.info(f"   - /upload (загрузка файлов)")
        logger.info(f"   - /download/<path> (скачивание)")
        logger.info(f"   - /delete/<path> (удаление)")
        logger.info(f"   - /logs (логи операций)")
        
        self.app.run(host=self.host, port=self.port, debug=False)


def main():
    """Точка входа - запуск локального клиента"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Local File Client for FileServer Bot')
    parser.add_argument('--id', type=str, default=str(uuid.uuid4())[:8], 
                       help='Client ID (default: random)')
    parser.add_argument('--folder', type=str, default='./downloads_local',
                       help='Local downloads folder (default: ./downloads_local)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='API host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                       help='API port (default: 5000)')
    
    args = parser.parse_args()
    
    client = LocalFileClient(
        client_id=args.id,
        local_folder=args.folder,
        host=args.host,
        port=args.port
    )
    client.run()


if __name__ == '__main__':
    main()
