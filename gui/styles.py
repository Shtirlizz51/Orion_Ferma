# gui/styles.py

STYLESHEET = """
QWidget {
    background-color: #2E2F30;
    color: #F0F0F0;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 10pt;
}

QMainWindow {
    background-color: #252627;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #4A4B4C;
    border-radius: 6px;
    margin-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
}

QLabel {
    font-weight: normal;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #3C3D3E;
    border: 1px solid #5A5B5C;
    border-radius: 4px;
    padding: 5px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0078D7;
}

QPushButton {
    background-color: #0078D7;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 12px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #0084E8;
}

QPushButton:pressed {
    background-color: #006AC1;
}

/* "Опасные" кнопки */
QPushButton#danger {
    background-color: #D32F2F;
}
QPushButton#danger:hover {
    background-color: #E53935;
}
QPushButton#danger:pressed {
    background-color: #C62828;
}

/* "Успешные" кнопки */
QPushButton#success {
    background-color: #388E3C;
}
QPushButton#success:hover {
    background-color: #43A047;
}
QPushButton#success:pressed {
    background-color: #2E7D32;
}


QTableWidget {
    background-color: #3C3D3E;
    border: 1px solid #4A4B4C;
    gridline-color: #4A4B4C;
}

QHeaderView::section {
    background-color: #2E2F30;
    border: 1px solid #4A4B4C;
    padding: 4px;
    font-weight: bold;
}

QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
"""
