import sys
import logging
from PySide6.QtWidgets import QApplication, QMessageBox
from pqm_quality_manager.ui.main_window import MainWindow
from pqm_quality_manager.utils.logging_config import configure_logging

def main():
    configure_logging()
    app=QApplication(sys.argv);app.setApplicationName("PQM Quality Manager");app.setOrganizationName("INGELEAN S.A.S.")
    window=MainWindow();window.show()
    try:return app.exec()
    except Exception:
        logging.exception("Error no controlado en la aplicación")
        QMessageBox.critical(window,"Error","Ocurrió un error. Consulte el archivo de registro en la carpeta de datos.")
        return 1
