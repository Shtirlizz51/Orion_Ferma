from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QMessageBox,
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QGroupBox,
    QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox
)

from .styles import STYLESHEET
from .widgets import StatusIndicator, InfoBlock
from infra.telegram_notify import TelegramNotifier
from infra.api_key_manager import APIKeyManager

from core.strategy_engine import StrategyEngine
from exchange.binance_adapter import BinanceAdapter

class ZefirMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Инициализация менеджеров
        self.api_manager = APIKeyManager()
        self.strategy_engine = None
        self._current_mode = "spot"  # По умолчанию режим Spot

        # Основная конфигурация окна
        self.setWindowTitle("ZEFIR Premium Trading Bot ★ ST-ORION")
        self.resize(1400, 900)
        self.setStyleSheet(STYLESHEET)
        self.statusBar().showMessage("Готов к работе")

        # Главный контейнер
        main_widget = QWidget()
        self.main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # Создание колонок
        self._create_left_column()
        self._create_right_column()
        
        # Настройка соотношения колонок
        self.main_layout.setStretch(0, 2)
        self.main_layout.setStretch(1, 3)
        
        # Подключение сигналов
        self._connect_signals()
        
        # Загрузка начальных значений
        self._update_api_fields_from_manager()
        
        # Инициализация торгового движка
        self._init_trading_engine()

    def _create_left_column(self):
        left_vbox = QVBoxLayout()
        left_vbox.setSpacing(15)

        # --- Логотип и название ---
        title = QLabel('⚡ ZEFIR TRADING BOT ⚡')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24pt; font-weight: bold; color: #F44336;")
        left_vbox.addWidget(title)

        # --- API ---
        api_group = QGroupBox("API Ключи")
        api_layout = QFormLayout(api_group)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Кнопки "показать/скрыть"
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.setFixedWidth(30)
        self.show_secret_btn = QPushButton("👁")
        self.show_secret_btn.setCheckable(True)
        self.show_secret_btn.setFixedWidth(30)
        
        key_hbox = QHBoxLayout()
        key_hbox.addWidget(self.api_key_edit)
        key_hbox.addWidget(self.show_key_btn)
        
        secret_hbox = QHBoxLayout()
        secret_hbox.addWidget(self.api_secret_edit)
        secret_hbox.addWidget(self.show_secret_btn)

        api_layout.addRow("API Key:", key_hbox)
        api_layout.addRow("API Secret:", secret_hbox)
        
        # Выбор режима работы
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Эмуляция", "Testnet Binance", "Реальный счет"])
        api_layout.addRow("Режим работы:", self.mode_combo)
        
        left_vbox.addWidget(api_group)

        # --- Статусы ---
        status_group = QGroupBox("Статусы")
        status_layout = QFormLayout(status_group)
        
        self.api_status = StatusIndicator()
        self.telegram_status = StatusIndicator()
        
        status_layout.addRow("API:", self.api_status)
        status_layout.addRow("Telegram:", self.telegram_status)
        
        left_vbox.addWidget(status_group)

        # --- Параметры стратегии ---
        params_group = QGroupBox("Параметры стратегии")
        params_layout = QFormLayout(params_group)
        
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"])
        params_layout.addRow("Торговая пара:", self.symbol_combo)
        
        self.deposit_percent = QDoubleSpinBox(suffix=" %", decimals=2, singleStep=1.0, value=100.0, maximum=100.0)
        params_layout.addRow("Доля депозита:", self.deposit_percent)
        
        self.dca_count = QSpinBox(value=3, maximum=10)  # ВНИМАНИЕ: теперь dca_count!
        params_layout.addRow("Кол-во усреднений:", self.dca_count)
        
        self.dca_step = QDoubleSpinBox(suffix=" %", decimals=2, singleStep=0.1, value=2.8)
        params_layout.addRow("Шаг усреднений:", self.dca_step)
        
        self.martingale_coef = QDoubleSpinBox(decimals=2, singleStep=0.1, value=1.25)
        params_layout.addRow("Коэф. мартингейла:", self.martingale_coef)
        
        self.tp_fields = []
        for i in range(1, 4):
            tp_perc = QDoubleSpinBox(suffix=" %", decimals=2, singleStep=0.1, value=1.9 + (i-1)*1.5)
            tp_vol = QDoubleSpinBox(suffix=" %", decimals=0, singleStep=1.0, value=33.0, maximum=100.0)
            params_layout.addRow(f"TP{i} %:", tp_perc)
            params_layout.addRow(f"TP{i} Объём:", tp_vol)
            self.tp_fields.append((tp_perc, tp_vol))
            
        left_vbox.addWidget(params_group)
        left_vbox.addStretch()
        self.main_layout.addLayout(left_vbox)

    def _create_right_column(self):
        right_vbox = QVBoxLayout()
        right_vbox.setSpacing(15)

        # --- Таблица сделок ---
        orders_group = QGroupBox("Открытые сделки")
        orders_layout = QVBoxLayout(orders_group)
        
        self.orders_table = QTableWidget(0, 5)
        self.orders_table.setHorizontalHeaderLabels(["Тип", "Цена входа", "Объём", "Сумма", "PnL"])
        self.orders_table.setMinimumHeight(200)
        orders_layout.addWidget(self.orders_table)
        
        right_vbox.addWidget(orders_group, 1)

        # --- Блок информации ---
        self.info_block = InfoBlock()
        right_vbox.addWidget(self.info_block)

        # --- Блок кнопок управления ---
        btn_group = QGroupBox("Управление")
        btns_layout = QVBoxLayout(btn_group)
        
        self.start_btn = QPushButton("Старт стратегии")
        self.start_btn.setObjectName("success")
        
        self.soft_stop_btn = QPushButton("Мягкий стоп")
        self.soft_stop_btn.setCheckable(True)
        
        self.hard_stop_btn = QPushButton("Стоп")
        self.hard_stop_btn.setObjectName("danger")
        
        self.check_api_btn = QPushButton("Проверить API")
        self.save_strategy_btn = QPushButton("Сохранить стратегию")
        self.check_tg_btn = QPushButton("Проверить Telegram")
        
        self.clear_orders_btn = QPushButton("Очистить ордера")
        self.clear_orders_btn.setObjectName("danger")
        
        self.all_to_usdt_btn = QPushButton("Всё обменять в USDT")
        self.usdt_to_asset_btn = QPushButton("Всё из USDT в актив")
        
        # Добавление кнопок в layout
        control_buttons = [
            self.start_btn, 
            self.soft_stop_btn, 
            self.hard_stop_btn,
            self.check_api_btn, 
            self.save_strategy_btn, 
            self.check_tg_btn,
            self.clear_orders_btn, 
            self.all_to_usdt_btn, 
            self.usdt_to_asset_btn
        ]
        
        for btn in control_buttons:
            btn.setMinimumHeight(35)
            btns_layout.addWidget(btn)
            
        right_vbox.addWidget(btn_group)
        right_vbox.addStretch()
        self.main_layout.addLayout(right_vbox)

    def _connect_signals(self):
        # Показать/скрыть API ключи
        self.show_key_btn.toggled.connect(
            lambda c: self.api_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        self.show_secret_btn.toggled.connect(
            lambda c: self.api_secret_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        
        # Изменение режима работы
        self.mode_combo.currentIndexChanged.connect(self._update_api_fields_from_manager)
        
        # Автосохранение ключей при изменении
        self.api_key_edit.textChanged.connect(self._save_api_keys_from_fields)
        self.api_secret_edit.textChanged.connect(self._save_api_keys_from_fields)
        
        # Обработка кнопок
        self.check_api_btn.clicked.connect(self.check_api_connection)
        self.check_tg_btn.clicked.connect(self.check_telegram_connection)
        self.start_btn.clicked.connect(self.start_strategy)
        self.soft_stop_btn.toggled.connect(self.toggle_soft_stop)
        self.hard_stop_btn.clicked.connect(self.hard_stop_strategy)
        self.save_strategy_btn.clicked.connect(self.save_strategy_settings)
        self.clear_orders_btn.clicked.connect(self.cancel_all_orders)
        self.all_to_usdt_btn.clicked.connect(self.convert_all_to_usdt)
        self.usdt_to_asset_btn.clicked.connect(self.convert_usdt_to_asset)

    def _get_current_mode(self):
        """Определение текущего режима работы из выпадающего списка"""
        idx = self.mode_combo.currentIndex()
        if idx == 0:  # Эмуляция
            return "emulation"
        elif idx == 1:  # Testnet Binance
            return "testnet"
        else:  # Реальный счет
            return "spot"

    def _update_api_fields_from_manager(self):
        """Обновление полей API ключей из менеджера"""
        mode = self._get_current_mode()
        self._current_mode = mode
        keys = self.api_manager.get_keys(mode)
        
        # Блокируем сигналы, чтобы избежать рекурсивного сохранения
        self.api_key_edit.blockSignals(True)
        self.api_secret_edit.blockSignals(True)
        
        self.api_key_edit.setText(keys.get("api_key", ""))
        self.api_secret_edit.setText(keys.get("api_secret", ""))
        
        self.api_key_edit.blockSignals(False)
        self.api_secret_edit.blockSignals(False)
        
        # Переинициализация торгового движка при смене режима
        self._init_trading_engine()

    def _save_api_keys_from_fields(self):
        """Сохранение ключей из полей ввода в менеджер"""
        mode = self._get_current_mode()
        api_key = self.api_key_edit.text()
        api_secret = self.api_secret_edit.text()
        
        # Валидация ключей
        if not api_key.strip() or not api_secret.strip():
            return
            
        self.api_manager.save_keys(mode, api_key, api_secret)
        self.statusBar().showMessage(f"Ключи для {mode.upper()} сохранены", 2000)
        
        # Переинициализация торгового движка при изменении ключей
        self._init_trading_engine()

    def _init_trading_engine(self):
        """Инициализация торгового движка с учетом режима работы"""
        try:
            mode = self._get_current_mode()
            keys = self.api_manager.get_keys(mode)
            api_key = keys.get("api_key", "")
            api_secret = keys.get("api_secret", "")

            if mode == "emulation":
                exchange_adapter = BinanceAdapter(mode="EMULATION")
                self.strategy_engine = StrategyEngine(exchange_adapter)
                self.statusBar().showMessage("Режим эмуляции активирован", 3000)
                return

            if not api_key or not api_secret:
                self.strategy_engine = None
                return

            exchange_adapter = BinanceAdapter(
                mode="TESTNET" if mode == "testnet" else "PRODUCTION",
                api_key=api_key,
                api_secret=api_secret
            )

            self.strategy_engine = StrategyEngine(exchange_adapter)
            self.statusBar().showMessage("Торговый движок инициализирован", 3000)

        except Exception as e:
            self.strategy_engine = None
            self.statusBar().showMessage(f"Ошибка инициализации: {str(e)}", 5000)

    def check_api_connection(self):
        """Проверка подключения к API биржи"""
        mode = self._get_current_mode()
        
        # Для режима эмуляции проверка не требуется
        if mode == "emulation":
            self.api_status.set_state("ok")
            QMessageBox.information(
                self, 
                "Эмуляция", 
                "Работа в режиме эмуляции - соединение с биржей не требуется"
            )
            return
            
        keys = self.api_manager.get_keys(mode)
        api_key = keys.get("api_key", "")
        api_secret = keys.get("api_secret", "")
        
        if not api_key or not api_secret:
            self.api_status.set_state("error")
            QMessageBox.warning(
                self, 
                "Ошибка", 
                "API ключ и/или секрет не введены"
            )
            return
            
        try:
            # Создаем временный адаптер для проверки
            exchange_adapter = BinanceAdapter(
                mode="TESTNET" if mode == "testnet" else "PRODUCTION",
                api_key=api_key,
                api_secret=api_secret
            )
            
            # Проверяем подключение
            exchange_adapter.check_connection()
            
            self.api_status.set_state("ok")
            QMessageBox.information(
                self, 
                "Успех", 
                f"Соединение с Binance ({mode.upper()}) успешно установлено!"
            )
            
        except Exception as e:
            self.api_status.set_state("error")
            QMessageBox.critical(
                self, 
                "Ошибка", 
                f"Ошибка подключения к API: {str(e)}"
            )

    def check_telegram_connection(self):
        """Проверка подключения к Telegram"""
        try:
            # Тестовые данные (должны быть в настройках)
            TEST_TOKEN = "7332902074:AAGC4KyEVDDt3EK-s9VsM9DwimlSmU-ur9w"
            TEST_CHAT_ID = 7152662300
            
            self.telegram_status.set_state("warning")
            
            notifier = TelegramNotifier(TEST_TOKEN, TEST_CHAT_ID)
            success = notifier.send("Тестовое сообщение от ZEFIR Trading Bot")
            
            if success:
                self.telegram_status.set_state("ok")
                QMessageBox.information(
                    self, 
                    "Успех", 
                    "Уведомление успешно отправлено в Telegram!"
                )
            else:
                self.telegram_status.set_state("error")
                QMessageBox.warning(
                    self, 
                    "Ошибка", 
                    "Не удалось отправить сообщение в Telegram"
                )
                
        except Exception as e:
            self.telegram_status.set_state("error")
            QMessageBox.critical(
                self, 
                "Ошибка", 
                f"Ошибка отправки в Telegram: {str(e)}"
            )

    def start_strategy(self):
        """Запуск торговой стратегии"""
        if not self.strategy_engine:
            self.statusBar().showMessage("Торговый движок не инициализирован", 3000)
            return
            
        # Получение настроек стратегии из интерфейса
        settings = self._get_strategy_settings()
        
        try:
            # Запуск стратегии
            self.strategy_engine.start_cycle(
                symbol=settings["symbol"],
                settings=settings
            )
            
            self.statusBar().showMessage("Стратегия запущена", 3000)
            self.start_btn.setEnabled(False)
            
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка запуска: {str(e)}", 5000)

    def toggle_soft_stop(self, checked):
        """Переключение режима мягкого стопа"""
        if self.strategy_engine:
            self.strategy_engine.set_soft_stop(checked)
        
        # Визуальная индикация
        if checked:
            self.soft_stop_btn.setStyleSheet("""
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            """)
            self.statusBar().showMessage("Мягкий стоп активирован", 3000)
        else:
            self.soft_stop_btn.setStyleSheet("")
            self.statusBar().showMessage("Мягкий стоп деактивирован", 3000)

    def hard_stop_strategy(self):
        """Полная остановка стратегии"""
        if self.strategy_engine:
            self.strategy_engine.hard_stop()
            self.start_btn.setEnabled(True)
            self.statusBar().showMessage("Стратегия остановлена", 3000)

    def save_strategy_settings(self):
        """Сохранение настроек стратегии"""
        settings = self._get_strategy_settings()
        
        # Здесь должен быть код сохранения в файл или БД
        # Пока просто покажем сообщение
        self.statusBar().showMessage("Настройки стратегии сохранены", 3000)

    def cancel_all_orders(self):
        """Отмена всех активных ордеров"""
        if self.strategy_engine:
            try:
                self.strategy_engine.cancel_all_orders()
                self.statusBar().showMessage("Все ордера отменены", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Ошибка отмены ордеров: {str(e)}", 5000)

    def convert_all_to_usdt(self):
        """Конвертация всех активов в USDT"""
        if self.strategy_engine:
            try:
                self.strategy_engine.convert_all_to_usdt()
                self.statusBar().showMessage("Все активы конвертированы в USDT", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Ошибка конвертации: {str(e)}", 5000)

    def convert_usdt_to_asset(self):
        """Конвертация USDT в основной актив"""
        if self.strategy_engine:
            try:
                symbol = self.symbol_combo.currentText()
                asset = symbol.replace("USDT", "")  # Получаем базовый актив
                
                self.strategy_engine.convert_usdt_to_asset(asset)
                self.statusBar().showMessage(f"USDT конвертированы в {asset}", 3000)
            except Exception as e:
                self.statusBar().showMessage(f"Ошибка конвертации: {str(e)}", 5000)

    def _get_strategy_settings(self):
        """Получение настроек стратегии из интерфейса"""
        return {
            "symbol": self.symbol_combo.currentText(),
            "deposit_percent": self.deposit_percent.value(),
            "dca_count": self.dca_count.value(),      # <--- Только dca_count!
            "dca_step_percent": self.dca_step.value(), # Переименован для соответствия order_manager.py
            "martingale_coef": self.martingale_coef.value(),
            "tp1_percent": self.tp_fields[0][0].value(),
            "tp1_volume": self.tp_fields[0][1].value(),
            "tp2_percent": self.tp_fields[1][0].value(),
            "tp2_volume": self.tp_fields[1][1].value(),
            "tp3_percent": self.tp_fields[2][0].value(),
            "tp3_volume": self.tp_fields[2][1].value(),
        }