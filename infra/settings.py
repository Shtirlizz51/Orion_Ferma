import json
from pathlib import Path
import logging

class Settings:
    SETTINGS_FILE = Path("config/settings.json")

    def __init__(self):
        self._data = {}
        self.logger = logging.getLogger("Settings")
        self._load()

    def _load(self):
        if self.SETTINGS_FILE.exists():
            try:
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки настроек: {e}")
                self._data = {}
        else:
            self._data = {}

    def save(self):
        try:
            self.SETTINGS_FILE.parent.mkdir(exist_ok=True)
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек: {e}")

    def set(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        # Для dca_count также поддерживаем старое dca_levels ради обратной совместимости
        if key == "dca_count":
            if "dca_count" in self._data:
                return self._data["dca_count"]
            elif "dca_levels" in self._data:
                return self._data["dca_levels"]
        return self._data.get(key, default)

    def all(self):
        # Переименовать dca_levels в dca_count если нужно
        result = self._data.copy()
        if "dca_levels" in result and "dca_count" not in result:
            result["dca_count"] = result["dca_levels"]
            del result["dca_levels"]
        return result