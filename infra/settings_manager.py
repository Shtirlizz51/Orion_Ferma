import json
from pathlib import Path
import logging

class SettingsManager:
    """
    Управляет сохранением и загрузкой настроек стратегии в JSON-файл.
    """
    _CONFIG_DIR = Path("config")
    _SETTINGS_FILE = _CONFIG_DIR / "strategy_settings.json"

    def __init__(self):
        self._CONFIG_DIR.mkdir(exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)

    def save_settings(self, settings_data: dict):
        """Сохраняет словарь с настройками в файл."""
        try:
            self._SETTINGS_FILE.write_text(json.dumps(settings_data, indent=4, ensure_ascii=False))
            self.logger.info("Настройки стратегии успешно сохранены.")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении настроек: {e}")
            return False

    def load_settings(self) -> dict:
        """Загружает настройки из файла. Возвращает пустой словарь, если файл не найден."""
        if not self._SETTINGS_FILE.exists():
            return {}
        
        try:
            settings_data = json.loads(self._SETTINGS_FILE.read_text())
            self.logger.info("Настройки стратегии успешно загружены.")
            return settings_data
        except json.JSONDecodeError:
            self.logger.error("Ошибка декодирования JSON в файле настроек. Будут использованы значения по умолчанию.")
            return {}
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке настроек: {e}")
            return {}