from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGroupBox, QFormLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor

class StatusIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.state = "off"
        self.setFixedSize(20, 20)

    def set_state(self, state: str):
        self.state = state
        self.update()

    def set_ok(self, text=None):
        self.set_state("ok")

    def set_error(self, text=None):
        self.set_state("error")

    def set_warning(self, text=None):
        self.set_state("warning")

    def set_off(self, text=None):
        self.set_state("off")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(150, 150, 150)
        if self.state == "ok":
            color = QColor(0, 200, 0)
        elif self.state == "error":
            color = QColor(220, 30, 30)
        elif self.state == "warning":
            color = QColor(255, 200, 0)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

class InfoBlock(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        info_group = QGroupBox("Текущая информация")
        self.form_layout = QFormLayout(info_group)
        self.form_layout.setSpacing(10)
        self.price_label = QLabel("...")
        self.pnl_label = QLabel("...")
        self.start_balance_label = QLabel("...")
        self.current_balance_label = QLabel("...")
        self.cycle_pnl_label = QLabel("...")
        self.autosave_label = QLabel("Выключено")
        self.mode_label = QLabel("Spot")
        self.pnl_label.setStyleSheet("font-weight: bold;")
        self.cycle_pnl_label.setStyleSheet("font-weight: bold;")
        self.form_layout.addRow("Текущая цена:", self.price_label)
        self.form_layout.addRow("Дневной PnL:", self.pnl_label)
        self.form_layout.addRow("Стартовый баланс:", self.start_balance_label)
        self.form_layout.addRow("Текущий баланс:", self.current_balance_label)
        self.form_layout.addRow("PnL по циклу:", self.cycle_pnl_label)
        self.form_layout.addRow("Автосохранение:", self.autosave_label)
        self.form_layout.addRow("Режим:", self.mode_label)
        main_layout.addWidget(info_group)

    def update_data(self, data: dict):
        self.price_label.setText(data.get("price", "..."))
        self.start_balance_label.setText(data.get("start_balance", "..."))
        self.current_balance_label.setText(data.get("current_balance", "..."))
        self.autosave_label.setText(data.get("autosave", "Выключено"))
        self.mode_label.setText(data.get("mode", "Spot"))
        pnl = data.get("pnl", "...")
        self.pnl_label.setText(pnl)
        if str(pnl).startswith('+'):
            self.pnl_label.setStyleSheet("color: #388E3C; font-weight: bold;")
        elif str(pnl).startswith('-'):
            self.pnl_label.setStyleSheet("color: #D32F2F; font-weight: bold;")
        else:
            self.pnl_label.setStyleSheet("color: #F0F0F0; font-weight: bold;")
        cycle_pnl = data.get("cycle_pnl", "...")
        self.cycle_pnl_label.setText(cycle_pnl)
        if str(cycle_pnl).startswith('+'):
            self.cycle_pnl_label.setStyleSheet("color: #388E3C; font-weight: bold;")
        elif str(cycle_pnl).startswith('-'):
            self.cycle_pnl_label.setStyleSheet("color: #D32F2F; font-weight: bold;")
        else:
            self.cycle_pnl_label.setStyleSheet("color: #F0F0F0; font-weight: bold;")