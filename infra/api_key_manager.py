import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Dict
import logging

class APIKeyManager:
    _CONFIG_DIR = Path("config")
    _KEYS_FILE = _CONFIG_DIR / "api_keys.json"
    _ENC_KEY_FILE = _CONFIG_DIR / ".encryption.key"

    def __init__(self):
        self._CONFIG_DIR.mkdir(exist_ok=True)
        self._keys = {"spot": {}, "testnet": {}, "emulation": {}}  # Добавлен emulation для совместимости
        self._cipher = self._init_cipher()
        self._load_keys()
        self.logger = logging.getLogger("APIKeyManager")

    def _init_cipher(self) -> Fernet:
        if not self._ENC_KEY_FILE.exists():
            self._ENC_KEY_FILE.write_bytes(Fernet.generate_key())
        return Fernet(self._ENC_KEY_FILE.read_bytes())

    def _load_keys(self):
        if self._KEYS_FILE.exists():
            try:
                encrypted = json.loads(self._KEYS_FILE.read_text())
                self._keys = {
                    mode: {k: self._cipher.decrypt(v.encode()).decode() 
                          for k, v in data.items() if v}
                    for mode, data in encrypted.items()
                }
            except Exception as e:
                self.logger.error(f"Ошибка загрузки ключей: {e}")
                self._keys = {"spot": {}, "testnet": {}, "emulation": {}}

    def save_keys(self, mode: str, api_key: str, api_secret: str):
        """Сохранение ключей с шифрованием"""
        self._keys[mode] = {
            "api_key": api_key,
            "api_secret": api_secret
        }
        # Добавляем пустые словари для совместимости режимов
        for m in ["spot", "testnet", "emulation"]:
            if m not in self._keys:
                self._keys[m] = {}
        encrypted = {
            mode: {k: self._cipher.encrypt(v.encode()).decode() 
                  for k, v in data.items()}
            for mode, data in self._keys.items()
        }
        self._KEYS_FILE.write_text(json.dumps(encrypted, indent=2))
        
    def get_keys(self, mode: str) -> Dict[str, str]:
        """Получение ключей для указанного режима (spot/testnet/emulation)"""
        return self._keys.get(mode, {})
