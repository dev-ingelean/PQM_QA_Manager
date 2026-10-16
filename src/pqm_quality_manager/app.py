import sys
import logging
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox
from pqm_quality_manager.ui.main_window import MainWindow
from pqm_quality_manager.utils.logging_config import configure_logging

def configure_theme(app):
    """Keep native controls and dialogs readable alongside the light UI styles."""
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.Window: "#F3F6F9",
        QPalette.WindowText: "#263746",
        QPalette.Base: "#FFFFFF",
        QPalette.AlternateBase: "#EDF2F6",
        QPalette.Text: "#263746",
        QPalette.Button: "#E6EDF3",
        QPalette.ButtonText: "#263746",
        QPalette.ToolTipBase: "#FFFFFF",
        QPalette.ToolTipText: "#263746",
        QPalette.Highlight: "#176B9B",
        QPalette.HighlightedText: "#FFFFFF",
        QPalette.PlaceholderText: "#607080",
        QPalette.Link: "#176B9B",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#657582"))
    app.setPalette(palette)

def main():
    configure_logging()
    app=QApplication(sys.argv);app.setApplicationName("PQM Quality Manager");app.setOrganizationName("INGELEAN S.A.S.")
    configure_theme(app)
    window=MainWindow();window.show()
    try:return app.exec()
    except Exception:
        logging.exception("Error no controlado en la aplicación")
        QMessageBox.critical(window,"Error","Ocurrió un error. Consulte el archivo de registro en la carpeta de datos.")
        return 1
