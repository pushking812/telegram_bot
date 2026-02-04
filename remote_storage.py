"""
Управление удалёнными хранилищами (Remote Storage Handler)
Позволяет работать с локальными клиентами подключёнными через API
"""

import os
import json
import logging
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

REMOTE_CLIENTS_FILE = 'remote_clients.json'


class RemoteClient:
    """Представление удалённого клиента"""
    
    def __init__(self, client_id: str, name: str, url: str):
        self.client_id = client_id
        self.name = name
        self.url = url.rstrip('/')
        self.is_online = False
        self.last_check = None
        self.folder_size = 0
        self.file_count = 0
        self.available_space = 0
    
    def to_dict(self):
        return {
            'client_id': self.client_id,
            'name': self.name,
            'url': self.url,
            'is_online': self.is_online,
            'last_check': self.last_check,
            'folder_size': self.folder_size,
            'file_count': self.file_count,
            'available_space': self.available_space
        }
    
    @staticmethod
    def from_dict(data):
        client = RemoteClient(data['client_id'], data['name'], data['url'])
        client.is_online = data.get('is_online', False)
        client.last_check = data.get('last_check')
        client.folder_size = data.get('folder_size', 0)
        client.file_count = data.get('file_count', 0)
        client.available_space = data.get('available_space', 0)
        return client


class RemoteStorageManager:
    """Менеджер удалённых хранилищ"""
    
    def __init__(self):
        self.clients: Dict[str, RemoteClient] = {}
        self._load_clients()
    
    def _load_clients(self):
        """Загрузить список клиентов"""
        if os.path.exists(REMOTE_CLIENTS_FILE):
            try:
                with open(REMOTE_CLIENTS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for client_data in data:
                        client = RemoteClient.from_dict(client_data)
                        self.clients[client.client_id] = client
                logger.info(f"Загружено {len(self.clients)} удалённых клиентов")
            except Exception as e:
                logger.error(f"Ошибка загрузки клиентов: {e}")
    
    def _save_clients(self):
        """Сохранить список клиентов"""
        try:
            data = [client.to_dict() for client in self.clients.values()]
            with open(REMOTE_CLIENTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения клиентов: {e}")
    
    def add_client(self, client_id: str, name: str, url: str) -> bool:
        """Добавить новый удалённый клиент"""
        if client_id in self.clients:
            logger.warning(f"Клиент {client_id} уже зарегистрирован")
            return False
        
        client = RemoteClient(client_id, name, url)
        self.clients[client_id] = client
        self._save_clients()
        logger.info(f"✅ Добавлен клиент {name} ({client_id}): {url}")
        return True
    
    def remove_client(self, client_id: str) -> bool:
        """Удалить удалённый клиент"""
        if client_id not in self.clients:
            return False
        
        del self.clients[client_id]
        self._save_clients()
        logger.info(f"❌ Удалён клиент {client_id}")
        return True
    
    def get_client(self, client_id: str) -> Optional[RemoteClient]:
        """Получить клиента по ID"""
        return self.clients.get(client_id)
    
    def list_clients(self) -> List[RemoteClient]:
        """Получить список всех клиентов"""
        return list(self.clients.values())
    
    async def check_health(self, client_id: str) -> bool:
        """Проверить статус клиента"""
        client = self.get_client(client_id)
        if not client:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{client.url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        client.is_online = True
                        client.last_check = datetime.now().isoformat()
                        data = await resp.json()
                        client.available_space = data.get('available_space', 0)
                        self._save_clients()
                        return True
        except Exception as e:
            logger.debug(f"Клиент {client_id} недоступен: {e}")
        
        client.is_online = False
        client.last_check = datetime.now().isoformat()
        self._save_clients()
        return False
    
    async def get_client_info(self, client_id: str) -> Optional[Dict]:
        """Получить информацию о клиенте"""
        client = self.get_client(client_id)
        if not client:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{client.url}/info", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        client.folder_size = data.get('folder_size', 0)
                        client.file_count = data.get('file_count', 0)
                        self._save_clients()
                        return data
        except Exception as e:
            logger.error(f"Ошибка получения информации о клиенте {client_id}: {e}")
        
        return None
    
    async def list_files(self, client_id: str, folder: str = '') -> Optional[Dict]:
        """Получить список файлов на удалённом клиенте"""
        client = self.get_client(client_id)
        if not client:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{client.url}/list"
                params = {'folder': folder} if folder else {}
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов: {e}")
        
        return None
    
    async def upload_file(self, client_id: str, file_path: str, subfolder: str = '') -> Tuple[bool, str]:
        """Загрузить файл на удалённый клиент"""
        client = self.get_client(client_id)
        if not client:
            return False, "Клиент не найден"
        
        if not os.path.exists(file_path):
            return False, "Файл не найден"
        
        try:
            with open(file_path, 'rb') as f:
                async with aiohttp.ClientSession() as session:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=os.path.basename(file_path))
                    data.add_field('subfolder', subfolder)
                    
                    url = f"{client.url}/upload"
                    async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            logger.info(f"✅ Файл загружен на {client.name}: {result.get('filename')}")
                            return True, result.get('filename', '')
                        else:
                            error = await resp.text()
                            return False, f"Ошибка: {error}"
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            return False, str(e)
    
    async def download_file(self, client_id: str, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """Скачать файл с удалённого клиента"""
        client = self.get_client(client_id)
        if not client:
            return False, "Клиент не найден"
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{client.url}/download/{remote_path}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status == 200:
                        # Убеждаемся что директория существует
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        
                        with open(local_path, 'wb') as f:
                            f.write(await resp.read())
                        
                        logger.info(f"✅ Файл скачан с {client.name}: {os.path.basename(local_path)}")
                        return True, ""
                    else:
                        error = await resp.text()
                        return False, f"Ошибка: {error}"
        except Exception as e:
            logger.error(f"Ошибка скачивания файла: {e}")
            return False, str(e)
    
    async def delete_file(self, client_id: str, remote_path: str) -> Tuple[bool, str]:
        """Удалить файл на удалённом клиенте"""
        client = self.get_client(client_id)
        if not client:
            return False, "Клиент не найден"
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{client.url}/delete/{remote_path}"
                async with session.delete(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.info(f"✅ Файл удалён на {client.name}")
                        return True, ""
                    else:
                        error = await resp.text()
                        return False, f"Ошибка: {error}"
        except Exception as e:
            logger.error(f"Ошибка удаления файла: {e}")
            return False, str(e)
    
    async def check_all_clients(self) -> Dict[str, bool]:
        """Проверить статус всех клиентов"""
        results = {}
        tasks = [self.check_health(client_id) for client_id in self.clients.keys()]
        
        if tasks:
            statuses = await asyncio.gather(*tasks)
            for client_id, status in zip(self.clients.keys(), statuses):
                results[client_id] = status
        
        return results


# Глобальный экземпляр менеджера
_remote_storage_manager = None


def get_remote_storage_manager() -> RemoteStorageManager:
    """Получить глобальный экземпляр менеджера"""
    global _remote_storage_manager
    if _remote_storage_manager is None:
        _remote_storage_manager = RemoteStorageManager()
    return _remote_storage_manager
