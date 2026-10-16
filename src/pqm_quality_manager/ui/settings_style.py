"""Shared layout and styling for connection and application settings."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy

SETTINGS_STYLE = """
QGroupBox#settingsCard, QFrame#settingsCard {
    background: #ffffff; border: 1px solid #dce5ed; border-radius: 12px;
}
QLabel { color: #263746; background: transparent; border: none; }
QLabel#sectionTitle { font-size: 19px; font-weight: 700; color: #12365a; }
QLabel#sectionDescription, QLabel#fieldLabel, QLabel#settingsHint { color: #607080; }
QLabel#fieldLabel { font-size: 12px; font-weight: 600; }
QLabel#settingsHint { font-size: 12px; }
QLabel#connectionStatus { padding: 10px 12px; background: #edf4fa; color: #235979; border-radius: 6px; }
QLabel#activeDatabase { padding: 7px 12px; color: #176b9b; background: #e7f2fa; border-radius: 12px; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox {
    min-height: 22px; padding: 8px 10px; color: #263746;
    background: #ffffff; border: 1px solid #cbd7e2; border-radius: 6px;
    selection-background-color: #176b9b; selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #176b9b; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: #f1f4f7; color: #748493; }
QPushButton { padding: 9px 16px; color: #263746; background: #ffffff; border: 1px solid #cbd7e2; border-radius: 6px; font-weight: 600; }
QPushButton:hover { background: #edf4fa; border-color: #9ab7ce; }
QPushButton[class="primary"] { background: #176b9b; color: #ffffff; border: 1px solid #176b9b; }
QPushButton[class="primary"]:hover { background: #12577f; }
QPushButton:disabled { background: #edf1f5; color: #8493a0; border-color: #dce5ed; }
QPushButton#passwordToggle { padding: 8px 12px; }
QTabWidget::pane { border: 0; background: transparent; }
QTabBar::tab { padding: 12px 20px; margin-right: 8px; color: #607080; border-bottom: 3px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #176b9b; border-bottom-color: #176b9b; }
QTabBar::tab:hover { color: #12365a; background: #eaf1f7; }
QCheckBox { color: #263746; spacing: 8px; }
"""


def section_header(layout, title, description):
    heading = QLabel(title); heading.setObjectName("sectionTitle")
    description_label = QLabel(description); description_label.setObjectName("sectionDescription")
    description_label.setWordWrap(True)
    heading.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    description_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    header = QVBoxLayout(); header.setSpacing(6); header.setContentsMargins(0, 0, 0, 0)
    header.addWidget(heading); header.addWidget(description_label)
    layout.addLayout(header)
    layout.addSpacing(6)


def field(grid, row, column, label, control, *, span=1):
    container = QWidget()
    container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    layout = QVBoxLayout(container); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
    layout.setAlignment(Qt.AlignTop)
    caption = QLabel(label); caption.setObjectName("fieldLabel")
    caption.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    caption.setBuddy(control)
    layout.addWidget(caption); layout.addWidget(control)
    grid.addWidget(container, row, column, 1, span)
