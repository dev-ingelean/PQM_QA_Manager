"""Connection form available both in Settings and before database startup."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout,
)
from sqlalchemy import text
from pqm_quality_manager.config.database_connection import (
    ConnectionConfig, ConnectionConfigError, connection_error, load_connection, save_connection,
)
from pqm_quality_manager.database.engine import make_engine


class TestSignals(QObject):
    done = Signal(bool, str)


class ConnectionTest(QRunnable):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.signals = TestSignals()

    def run(self):
        candidate = None
        try:
            candidate = make_engine(self.config.url(), initialize=False)
            with candidate.connect() as connection:
                connection.execute(text("SELECT 1"))
            self.signals.done.emit(True, "Conexión correcta.")
        except Exception as error:
            self.signals.done.emit(False, connection_error(error))
        finally:
            if candidate is not None:
                candidate.dispose()


class DatabaseSettings(QGroupBox):
    saved = Signal()

    def __init__(self, parent=None, *, recovery=False):
        super().__init__("Base de datos", parent)
        self.recovery = recovery
        layout = QVBoxLayout(self)
        self.mode = QComboBox()
        self.mode.addItem("PostgreSQL en servidor", "postgresql")
        self.mode.addItem("SQLite en este equipo", "sqlite")
        self.host = QLineEdit(); self.host.setPlaceholderText("IP o nombre del PC servidor")
        self.port = QSpinBox(); self.port.setRange(1, 65535)
        self.database = QLineEdit(); self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.show_password = QPushButton("Mostrar contraseña"); self.show_password.setCheckable(True)
        self.show_password.toggled.connect(self.toggle_password)
        self.sslmode = QComboBox()
        for label, mode in (("Red local (sin TLS)", "disable"), ("Según el servidor", "prefer"),
                            ("Requerir TLS", "require"), ("Verificar certificado", "verify-ca"),
                            ("Verificar certificado y nombre", "verify-full")):
            self.sslmode.addItem(label, mode)
        form = QFormLayout()
        for label, widget in (("Ubicación de los datos", self.mode), ("Servidor", self.host),
                              ("Puerto", self.port), ("Base de datos", self.database),
                              ("Usuario", self.username), ("Contraseña", self.password),
                              ("Conexión", self.sslmode)):
            form.addRow(label, widget)
        form.addRow("", self.show_password)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.test_button = QPushButton("Probar conexión")
        self.save_button = QPushButton("Guardar y conectar" if recovery else "Guardar conexión")
        self.test_button.clicked.connect(self.test_connection)
        self.save_button.clicked.connect(self.save)
        buttons.addWidget(self.test_button); buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.status = QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        note = QLabel("La conexión se guarda en este equipo. " +
                      ("" if recovery else "Se aplicará al volver a abrir la aplicación. ") +
                      "Cambiar de base de datos no traslada los registros existentes.")
        note.setWordWrap(True); layout.addWidget(note)
        self.task = None
        self.testing = False
        try:
            self.initial = load_connection()
        except Exception as error:
            self.status.setText(connection_error(error))
            try:
                self.initial = load_connection(include_password=False)
            except Exception:
                self.initial = ConnectionConfig(backend="postgresql")
        self.mode.setCurrentIndex(self.mode.findData(self.initial.backend))
        self.host.setText(self.initial.host); self.port.setValue(self.initial.port)
        self.database.setText(self.initial.database); self.username.setText(self.initial.username)
        self.password.setText(self.initial.password)
        self.sslmode.setCurrentIndex(self.sslmode.findData(self.initial.options.get("sslmode", "prefer")))
        self.mode.currentIndexChanged.connect(self.update_mode)
        self.update_mode()

    def toggle_password(self, show):
        self.password.setEchoMode(QLineEdit.Normal if show else QLineEdit.Password)
        self.show_password.setText("Ocultar contraseña" if show else "Mostrar contraseña")

    def update_mode(self):
        enabled = self.mode.currentData() == "postgresql" and not self.testing
        for widget in (self.host, self.port, self.database, self.username, self.password,
                       self.sslmode, self.show_password):
            widget.setEnabled(enabled)

    def config(self):
        options = dict(self.initial.options)
        options["sslmode"] = self.sslmode.currentData() or "prefer"
        return ConnectionConfig(backend=self.mode.currentData(), host=self.host.text().strip(),
                                port=self.port.value(), database=self.database.text().strip(),
                                username=self.username.text().strip(), password=self.password.text(),
                                sqlite_path=self.initial.sqlite_path, options=options)

    def test_connection(self):
        try:
            config = self.config()
            config.url()
        except Exception as error:
            self.status.setText(connection_error(error)); return
        self.testing = True
        self.mode.setEnabled(False); self.update_mode()
        self.test_button.setEnabled(False); self.save_button.setEnabled(False)
        self.status.setText("Comprobando conexión…")
        self.task = ConnectionTest(config)
        self.task.signals.done.connect(self.test_finished)
        QThreadPool.globalInstance().start(self.task)

    def test_finished(self, success, message):
        self.testing = False
        self.mode.setEnabled(True); self.update_mode()
        self.test_button.setEnabled(True); self.save_button.setEnabled(True)
        self.status.setText(message)

    def save(self):
        try:
            save_connection(self.config())
        except ConnectionConfigError as error:
            self.status.setText(str(error))
            return
        except Exception:
            self.status.setText("No se pudo guardar. Revise los campos y los permisos de la carpeta de datos.")
            return
        self.status.setText("Conexión guardada." if self.recovery else
                            "Conexión guardada. Cierre y vuelva a abrir la aplicación para aplicarla.")
        self.saved.emit()


class DatabaseConnectionDialog(QDialog):
    def __init__(self, error, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar conexión a la base de datos")
        self.resize(560, 540)
        layout = QVBoxLayout(self)
        message = QLabel(connection_error(error)); message.setWordWrap(True)
        layout.addWidget(message)
        self.form = DatabaseSettings(recovery=True)
        self.form.saved.connect(self.accept)
        layout.addWidget(self.form)
        cancel = QPushButton("Salir"); cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)
