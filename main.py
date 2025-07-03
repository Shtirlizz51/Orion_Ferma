import sys
import logging
import os
from decimal import Decimal
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from gui.main_window import ZefirMainWindow

def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов, если её нет
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(logs_dir, 'star_orion.log'), encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Создаем отдельный обработчик для критических ошибок
    error_handler = logging.FileHandler(os.path.join(logs_dir, 'errors.log'), encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Добавляем обработчик ошибок к root logger
    logging.getLogger().addHandler(error_handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    """Обработчик необработанных исключений"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger = logging.getLogger(__name__)
    logger.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))
    
    # Показываем диалог с ошибкой пользователю
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Критическая ошибка")
        msg.setText("Произошла критическая ошибка приложения.")
        msg.setDetailedText(f"{exc_type.__name__}: {exc_value}")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

def check_dependencies():
    """Проверка зависимостей"""
    try:
        import requests
        import decimal
        from PyQt6 import QtCore, QtWidgets
        return True
    except ImportError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Отсутствует зависимость: {e}")
        return False

def initialize_decimal_precision():
    """Устанавливает точность для Decimal вычислений"""
    from decimal import getcontext
    getcontext().prec = 28  # Высокая точность для финансовых расчетов

def main():
    """Основная функция запуска приложения"""
    try:
        # Настройка логирования
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Запуск приложения Star Orion")
        
        # Проверка зависимостей
        if not check_dependencies():
            logger.error("Не удалось запустить приложение: отсутствуют зависимости")
            return 1
        
        # Настройка Decimal
        initialize_decimal_precision()
        
        # Установка обработчика исключений
        sys.excepthook = handle_exception
        
        # Создание приложения Qt
        app = QApplication(sys.argv)
        app.setApplicationName("Star Orion")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("Shtirlizz51")
        
        # Настройка стилей (опционально)
        app.setStyle('Fusion')  # Современный стиль
        
        logger.info("Инициализация главного окна")
        
        # Создание главного окна
        try:
            window = ZefirMainWindow()
            window.show()
            
            # Таймер для периодической проверки состояния
            status_timer = QTimer()
            status_timer.timeout.connect(lambda: logger.debug("Приложение работает"))
            status_timer.start(60000)  # Каждую минуту
            
            logger.info("Главное окно создано и показано")
            
        except Exception as e:
            logger.error(f"Ошибка создания главного окна: {e}")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Ошибка запуска")
            msg.setText("Не удалось создать главное окно приложения.")
            msg.setDetailedText(str(e))
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return 1
        
        # Запуск цикла обработки событий
        logger.info("Запуск цикла обработки событий Qt")
        result = app.exec()
        
        logger.info(f"Приложение завершено с кодом: {result}")
        return result
        
    except Exception as e:
        # Критическая ошибка при запуске
        print(f"Критическая ошибка при запуске: {e}")
        if 'logger' in locals():
            logger.critical(f"Критическая ошибка при запуске: {e}")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)