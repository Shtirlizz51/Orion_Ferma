import requests
from threading import Thread
import logging

class TelegramNotifier:
    def __init__(self, token: str, chat_id: int):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.logger = logging.getLogger("TelegramNotifier")
        
    def send(self, message: str, silent: bool = False) -> bool:
        try:
            Thread(target=self._send_thread, args=(message, silent)).start()
            return True
        except Exception as e:
            self.logger.error(f"Telegram error: {e}")
            return False

    def _send_thread(self, message: str, silent: bool):
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'disable_notification': silent
        }
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=5
            )
            if not response.ok:
                self.logger.warning(f"API error: {response.text}")
        except Exception as e:
            self.logger.error(f"Connection error: {e}")