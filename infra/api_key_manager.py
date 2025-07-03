import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Dict, Optional
import logging

class APIKeyManager:
    _CONFIG_DIR = Path("config")
    _KEYS_FILE = _CONFIG_DIR / "api_keys.json"
    _ENC_KEY_FILE = _CONFIG_DIR / ".encryption.key"

    def __init__(self):
        self._CONFIG_DIR.mkdir(exist_ok=True)
        # Устанавливаем структуру по умолчанию
        self._keys = {"spot": {}, "testnet": {}, "emulation": {}}
        self._cipher = self._init_cipher()
        self._load_keys()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _init_cipher(self) -> Fernet:
        if not self._ENC_KEY_FILE.exists():
            key = Fernet.generate_key()
            self._ENC_KEY_FILE.write_bytes(key)
            return Fernet(key)
        return Fernet(self._ENC_KEY_FILE.read_bytes())

    def _load_keys(self):
        if not self._KEYS_FILE.exists():
            # Если файла нет, сохраняем пустую структуру
            self.save_all_keys()
            return

        try:
            encrypted_data = json.loads(self._KEYS_FILE.read_text())
            # Дешифруем только существующие ключи
            for mode, data in encrypted_data.items():
                if mode in self._keys: # Убедимся, что режим поддерживается
                    self._keys[mode] = {
                        k: self._cipher.decrypt(v.encode()).decode()
                        for k, v in data.items() if v
                    }
        except Exception as e:
            self.logger.error(f"Ошибка загрузки или дешифровки ключей: {e}. Будет использована пустая структура.")
            self._keys = {"spot": {}, "testnet": {}, "emulation": {}}

    def save_all_keys(self):
        """Шифрует и сохраняет все ключи в файл."""
        encrypted = {}
        for mode, data in self._keys.items():
            encrypted[mode] = {
                k: self._cipher.encrypt(v.encode()).decode()
                for k, v in data.items() if v
            }
        self._KEYS_FILE.write_text(json.dumps(encrypted, indent=4))

    def save_keys(self, mode: str, api_key: str, api_secret: str):
        """Сохраняет ключи для одного режима и обновляет файл."""
        if mode in self._keys:
            self._keys[mode] = {"api_key": api_key, "api_secret": api_secret}
            self.save_all_keys()
        
    def get_keys(self, mode: str) -> Dict[str, str]:
        """Получает ключи для указанного режима (spot/testnet/emulation)."""
        return self._keys.get(mode, {})
