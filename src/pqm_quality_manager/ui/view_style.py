"""Shared presentation for the dashboard, history and inspection dialogs."""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QPen, QPainterPath
from functools import lru_cache
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel,
                               QHeaderView, QPushButton, QVBoxLayout, QListWidget, QStyledItemDelegate, QStyleOptionViewItem)
from pqm_quality_manager.ui.settings_style import SETTINGS_STYLE

VIEW_STYLE = SETTINGS_STYLE + """
QMainWindow, QDialog, QWidget#page { background: #f3f6f9; }
QLabel#pageTitle { color: #12365a; font-size: 26px; font-weight: 700; }
QLabel#metricValue { color: #176b9b; font-size: 30px; font-weight: 700; }
QTextEdit, QDateEdit, QDoubleSpinBox {
    background: white; color: #263746; border: 1px solid #cbd7e2;
    border-radius: 6px; padding: 8px; selection-background-color: #176b9b; selection-color: white;
}
QTextEdit:focus, QDateEdit:focus { border-color: #176b9b; }
QTextEdit:disabled, QDateEdit:disabled { background: #f1f4f7; color: #748493; }
QTableWidget { background: white; alternate-background-color: #f7fafc; border: 0; color: #263746;
    selection-background-color: #e0eff9; selection-color: #12365a; outline: 0; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #edf1f5; }
QHeaderView::section { padding: 12px 8px; background: #edf3f8; color: #607080;
    border: 0; border-bottom: 1px solid #dce5ed; font-weight: 600; }
QTableCornerButton::section { background: #edf3f8; border: 0; }
QListWidget { color: #263746; background: white; border: 1px solid #dce5ed; border-radius: 8px; outline: 0; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #edf1f5; }
QListWidget::item:selected { color: #12365a; background: #e0eff9; }
QListWidget::item:hover { background: #f0f6fa; }
QScrollArea { border: 0; background: transparent; }
QProgressBar { background: #e3ebf2; border: 0; border-radius: 5px; min-height: 9px; max-height: 9px; }
QProgressBar::chunk { background: #176b9b; border-radius: 5px; }
QSplitter::handle { background: transparent; width: 12px; }
QMenu { color: #263746; background: white; border: 1px solid #dce5ed; padding: 6px; }
QMenu::item { padding: 9px 18px; }
QMenu::item:selected { background: #e0eff9; }
QPushButton[class="danger"] { color: #a23535; border-color: #e5bcbc; }
"""

STATUS_NAMES = {"EN_ELABORACION": "En elaboración", "PENDIENTE_REVISION": "Pendiente de revisión",
                "APROBADA": "Aprobada", "RECHAZADA": "Rechazada", "CERRADA": "Cerrada"}
STATUS_COLORS = {"EN_ELABORACION": "#176b9b", "PENDIENTE_REVISION": "#936111",
                 "APROBADA": "#277445", "RECHAZADA": "#a23535", "CERRADA": "#607080"}


def button(text, callback, *, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.PointingHandCursor)
    if primary:
        widget.setProperty("class", "primary")
    widget.clicked.connect(callback)
    return widget


def page_header(layout, title, subtitle, action=None):
    row = QHBoxLayout(); titles = QVBoxLayout(); titles.setSpacing(5)
    heading = QLabel(title); heading.setObjectName("pageTitle")
    description = QLabel(subtitle); description.setObjectName("sectionDescription"); description.setWordWrap(True)
    titles.addWidget(heading); titles.addWidget(description); row.addLayout(titles, 1)
    if action is not None:
        row.addWidget(action, 0, Qt.AlignTop)
    layout.addLayout(row)


def card():
    frame = QFrame(); frame.setObjectName("settingsCard")
    layout = QVBoxLayout(frame); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(14)
    return frame, layout


def style_table(table):
    table.setAlternatingRowColors(True); table.setShowGrid(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().hide(); table.verticalHeader().setDefaultSectionSize(46)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setMinimumSectionSize(100)
    table.horizontalHeader().setDefaultSectionSize(145)
    table.horizontalHeader().setStretchLastSection(False)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.ElideRight)


def status_item(item, status):
    item.setText(STATUS_NAMES.get(status, status))
    item.setForeground(QColor(STATUS_COLORS.get(status, "#263746")))
    font = QFont(); font.setBold(True); item.setFont(font)
    item.setToolTip(STATUS_NAMES.get(status, status))


class EvidenceDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.decorationPosition = QStyleOptionViewItem.Right
        option.decorationAlignment = Qt.AlignRight | Qt.AlignVCenter


class EvidenceList(QListWidget):
    """Keep both the evidence title and its status visible as the sidebar resizes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(EvidenceDelegate(self))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_item_sizes()

    def refresh_item_sizes(self):
        from PySide6.QtGui import QFontMetrics
        width = max(120, self.viewport().width() - 24)
        for index in range(self.count()):
            item = self.item(index)
            metrics = QFontMetrics(item.font() if item.font().resolveMask() else self.font())
            text_width = width - (self.iconSize().width() + 8 if not item.icon().isNull() else 0)
            bounds = metrics.boundingRect(QRect(0, 0, text_width, 2000), Qt.TextWordWrap, item.text())
            item.setSizeHint(QSize(0, bounds.height() + 24))
            item.setToolTip(item.text())


@lru_cache(maxsize=1)
def conform_icon():
    pixmap = QPixmap(40, 40); pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen); painter.setBrush(QColor("#27834b")); painter.drawEllipse(1, 1, 18, 18)
    painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    check = QPainterPath(); check.moveTo(5.5, 10); check.lineTo(8.5, 13); check.lineTo(14.5, 7)
    painter.drawPath(check); painter.end()
    return QIcon(pixmap)


def evidence_status_item(item, status):
    item.setIcon(conform_icon() if status == "Conforme" else QIcon())
    title, separator, details = item.text().partition("\n")
    if separator:
        _, divider, photos = details.partition(" · ")
        item.setText(f"{title}\n{status}{divider}{photos}")
