from pathlib import Path
from datetime import datetime
import json
from PySide6.QtCore import Qt, QDate, QSize, QTimer
from PySide6.QtGui import QDesktopServices, QColor, QFont, QIcon, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton, QLabel, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QMessageBox, QDialog, QDateEdit, QTextEdit, QListWidget, QListWidgetItem, QSplitter, QGroupBox, QFileDialog, QInputDialog, QProgressBar, QCheckBox, QSpinBox, QScrollArea, QTabWidget, QMenu)
from sqlalchemy import select
from pqm_quality_manager.services.inspection_service import InspectionService, InspectionError
from pqm_quality_manager.services.image_service import ImageService
from pqm_quality_manager.services.pdf_service import PDFReportService
from pqm_quality_manager.services.backup_service import BackupService
from pqm_quality_manager.services.email_service import EmailService
from pqm_quality_manager.database.engine import SessionLocal
from pqm_quality_manager.database.models import AppSetting, Inspection, Report, EmailDispatch
from pqm_quality_manager.database import engine as database_engine
from pqm_quality_manager.services.file_storage import materialize
from pqm_quality_manager.services.checkpoint_service import history
from pqm_quality_manager.config.settings import DATA_DIR
from pqm_quality_manager.ui.database_settings import DatabaseSettings
from pqm_quality_manager.ui.settings_style import SETTINGS_STYLE, section_header, field

from pqm_quality_manager.ui.view_style import VIEW_STYLE, STATUS_NAMES, button, page_header, card, style_table, status_item, EvidenceList, evidence_status_item

NAVY = "#12365A"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PQM Quality Manager | INGELEAN S.A.S."); self.resize(1280, 800)
        self.service = InspectionService(); self.stack = QStackedWidget()
        root = QWidget(); outer = QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(225); side.setStyleSheet(f"QFrame#sidebar{{background:{NAVY};color:white;}} QLabel{{color:white;}}")
        sv = QVBoxLayout(side);sv.setContentsMargins(16, 24, 16, 20);sv.setSpacing(8)
        brand = QLabel();brand.setObjectName("sidebarLogo");brand.setAlignment(Qt.AlignCenter)
        brand.setAccessibleName("Logo de INGELEAN");brand.setFixedHeight(68)
        logo_path = Path(__file__).resolve().parents[1] / "static" / "reports" / "logo-ingelean.png"
        logo = QPixmap(str(logo_path)).scaled(346, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setDevicePixelRatio(2);brand.setPixmap(logo)
        brand.setStyleSheet("background:white;border-radius:8px;padding:10px;");sv.addWidget(brand)
        product = QLabel("PQM Quality Manager");product.setWordWrap(True);product.setAlignment(Qt.AlignCenter);product.setStyleSheet("font-size:13px;color:#c4d9e9;padding:4px 0 20px;");sv.addWidget(product)
        self.nav_buttons = {}
        self.pages = {}
        for title, key in [("Panel principal", "home"), ("Inspecciones", "history"), ("Configuración", "settings")]:
            b=QPushButton(title); b.setCursor(Qt.PointingHandCursor); b.setCheckable(True);b.setStyleSheet("QPushButton{text-align:left;padding:13px 12px;color:#d5e3ed;border:0;border-radius:6px;background:transparent;font-size:14px;} QPushButton:hover{background:#1b456b;} QPushButton:checked{background:#23577f;color:white;font-weight:700;}");self.nav_buttons[key]=b; b.clicked.connect(lambda _, k=key: self.navigate(k)); sv.addWidget(b)
        sv.addStretch(); sv.addWidget(QLabel("Versión 0.1.0", alignment=Qt.AlignCenter)); outer.addWidget(side); outer.addWidget(self.stack,1)
        self.setCentralWidget(root)
        self.pages["home"] = DashboardPage(self); self.pages["history"] = HistoryPage(self); settings_scroll = QScrollArea();settings_scroll.setWidgetResizable(True);settings_scroll.setWidget(SettingsPage(self));self.pages["settings"] = settings_scroll
        for page in self.pages.values(): self.stack.addWidget(page)
        self.setStyleSheet(VIEW_STYLE)
        self.navigate("home")

    def navigate(self, key):
        self.stack.setCurrentWidget(self.pages[key])
        for name, nav in self.nav_buttons.items():nav.setChecked(name == key)
        self.refresh()
    def refresh(self):
        for p in self.pages.values():
            if hasattr(p,"refresh"): p.refresh()
    def new_inspection(self, prefill=None):
        dlg=InspectionForm(self, prefill)
        if dlg.exec() == QDialog.Accepted:
            try:
                vals=dlg.values(); iid=self.service.create(**vals)
                self.open_inspection(iid); self.refresh()
            except Exception as e: QMessageBox.warning(self,"No se pudo guardar",str(e))
    def open_inspection(self, iid):
        try:
            dlg=InspectionEditor(self,iid); dlg.exec(); self.refresh()
        except Exception as e: QMessageBox.critical(self,"Error",str(e))

class DashboardPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main; self.setObjectName("page")
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 26, 28, 28); lay.setSpacing(20)
        page_header(lay, "Panel principal", "Consulta el avance de las inspecciones y continúa con tu trabajo.",
                    button("＋ Nueva inspección", main.new_inspection, primary=True))
        self.cards = QGridLayout(); self.cards.setSpacing(14); lay.addLayout(self.cards)
        recent_card, content = card()
        heading = QLabel("Inspecciones recientes"); heading.setObjectName("sectionTitle"); content.addWidget(heading)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["N.º PQM", "Empresa", "Fecha", "Estado", "Responsable"])
        style_table(self.table)
        self.table.cellDoubleClicked.connect(self.open_row); content.addWidget(self.table)
        self.empty_hint = QLabel("Todavía no hay inspecciones. Crea la primera para comenzar.")
        self.empty_hint.setObjectName("settingsHint"); self.empty_hint.setWordWrap(True); content.addWidget(self.empty_hint)
        lay.addWidget(recent_card, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange_cards()

    def arrange_cards(self):
        widgets = [self.cards.itemAt(i).widget() for i in range(self.cards.count())]
        while self.cards.count():self.cards.takeAt(0)
        columns = 5 if self.width() >= 1000 else 3 if self.width() >= 700 else 2
        for index, widget in enumerate(widgets):self.cards.addWidget(widget, index // columns, index % columns)
        for index in range(5):self.cards.setColumnStretch(index, 1 if index < columns else 0)
    def refresh(self):
        data=self.main.service.dashboard()
        while self.cards.count():
            item=self.cards.takeAt(0); w=item.widget()
            if w:w.hide();w.deleteLater()
        for i,(name,val) in enumerate([("Inspecciones",data["total"]),("En elaboración",data["EN_ELABORACION"]),("Pendientes de revisión",data["PENDIENTE_REVISION"]),("Aprobadas",data["APROBADA"]),("Con evidencias incompletas",data["incomplete"])]):
            metric, v = card(); lab=QLabel(name);lab.setObjectName("sectionDescription");lab.setWordWrap(True);num=QLabel(str(val));num.setObjectName("metricValue");v.addWidget(lab);v.addWidget(num);self.cards.addWidget(metric,0,i)
        self.arrange_cards()
        recent=data["recent"];self.table.setRowCount(len(recent));self.empty_hint.setVisible(not recent)
        for r,x in enumerate(recent):
            vals=[x.pqm_number,x.company,x.inspection_date.isoformat(),x.status,x.author]
            for c,v in enumerate(vals):
                cell = QTableWidgetItem(str(v)); cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                cell.setToolTip(str(v)); self.table.setItem(r,c,cell)
            status_item(self.table.item(r,3), x.status)
            self.table.item(r,0).setData(Qt.UserRole,x.id)
    def open_row(self,row,col):
        it=self.table.item(row,0)
        if it: self.main.open_inspection(it.data(Qt.UserRole))

class HistoryPage(QWidget):
    def __init__(self, main):
        super().__init__(); self.main = main; self.setObjectName("page")
        v = QVBoxLayout(self); v.setContentsMargins(28, 26, 28, 28); v.setSpacing(20)
        page_header(v, "Inspecciones", "Busca, revisa y administra los registros de tus clientes.",
                    button("＋ Nueva inspección", main.new_inspection, primary=True))
        panel, content = card(); v.addWidget(panel, 1)
        filters = QGridLayout();filters.setHorizontalSpacing(16)
        self.search = QLineEdit(); self.search.setPlaceholderText("Número PQM o nombre de la empresa")
        self.search.textChanged.connect(self.refresh)
        self.status = QComboBox(); self.status.addItem("Todos los estados", "Todos")
        for code, name in STATUS_NAMES.items():self.status.addItem(name, code)
        self.status.currentIndexChanged.connect(self.refresh)
        field(filters, 0, 0, "Buscar inspección", self.search)
        field(filters, 0, 1, "Estado", self.status)
        filters.setColumnStretch(0, 3); filters.setColumnStretch(1, 2); content.addLayout(filters)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["N.º PQM", "Empresa", "Fecha", "Responsable", "Estado", "Documentación", "Última modificación"])
        style_table(self.table)
        self.table.cellDoubleClicked.connect(self.open_row); content.addWidget(self.table, 1)
        self.result_label = QLabel();self.result_label.setObjectName("settingsHint");content.addWidget(self.result_label)
        actions = QHBoxLayout()
        actions.addWidget(button("Abrir inspección", self.open_selected, primary=True))
        reports = QPushButton("Informes"); menu = QMenu(reports)
        for label, callback in (("Ver último informe", self.view_report), ("Generar PDF borrador", self.pdf), ("Generar PDF final", self.final_pdf)):
            menu.addAction(label, callback)
        reports.setMenu(menu); actions.addWidget(reports)
        actions.addWidget(button("Duplicar", self.duplicate)); actions.addStretch()
        remove = button("Eliminar", self.delete);remove.setProperty("class", "danger");actions.addWidget(remove)
        actions.addWidget(button("Actualizar", self.refresh)); content.addLayout(actions)
    def refresh(self,*_):
        if not hasattr(self,"table"):return
        rows=self.main.service.list(self.search.text() if hasattr(self,"search") else "",self.status.currentData() if hasattr(self,"status") else "Todos")
        self.table.setRowCount(len(rows))
        self.result_label.setText(f"{len(rows)} inspección(es) encontradas" if rows else "No hay inspecciones que coincidan con la búsqueda.")
        for r,x in enumerate(rows):
            p=self.main.service.progress(x.id); vals=[x.pqm_number,x.company,x.inspection_date.isoformat(),x.author,x.status,f"{p['documented']}/35 ({p['percent']}%)",x.updated_at.strftime("%Y-%m-%d %H:%M")]
            for c,val in enumerate(vals):
                cell = QTableWidgetItem(str(val)); cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                cell.setToolTip(str(val)); self.table.setItem(r,c,cell)
            status_item(self.table.item(r,4), x.status)
            self.table.item(r,0).setData(Qt.UserRole,x.id)
    def selected_id(self):
        row=self.table.currentRow(); item=self.table.item(row,0) if row>=0 else None
        return item.data(Qt.UserRole) if item else None
    def open_row(self,row,col):
        item=self.table.item(row,0)
        if item:self.main.open_inspection(item.data(Qt.UserRole))
    def open_selected(self):
        iid=self.selected_id()
        if iid:self.main.open_inspection(iid)
    def pdf(self):
        iid=self.selected_id()
        if not iid:return QMessageBox.information(self,"PDF","Seleccione una inspección.")
        try:
            path=PDFReportService().generate(iid,"BORRADOR");QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as e:QMessageBox.warning(self,"No se pudo generar el PDF",str(e))
    def final_pdf(self):
        iid=self.selected_id()
        if not iid:return QMessageBox.information(self,"PDF final","Seleccione una inspección.")
        try:
            path=PDFReportService().generate(iid,"FINAL");QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as e:QMessageBox.warning(self,"No se pudo generar el PDF final",str(e))
    def view_report(self):
        iid=self.selected_id()
        if not iid:return QMessageBox.information(self,"Informe","Seleccione una inspección.")
        try:
            path=PDFReportService().latest_path(iid)
            if path is None:
                return QMessageBox.information(self,"Informe","Esta inspección todavía no tiene un PDF guardado.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as error:
            QMessageBox.warning(self,"No se pudo abrir el informe",str(error))
    def duplicate(self):
        iid=self.selected_id()
        if iid:
            try:self.main.open_inspection(self.main.service.duplicate(iid))
            except Exception as e:QMessageBox.warning(self,"No se pudo duplicar",str(e))
    def delete(self):
        iid=self.selected_id()
        if not iid:return
        if QMessageBox.question(self,"Eliminar inspección","Se ocultará del historial para conservar la trazabilidad. ¿Desea continuar?")==QMessageBox.Yes:
            try:self.main.service.soft_delete(iid);self.refresh()
            except Exception as e:QMessageBox.warning(self,"Error",str(e))

class InspectionForm(QDialog):
    def __init__(self, parent, prefill=None):
        super().__init__(parent); self.setWindowTitle("Nueva inspección PQM"); self.resize(720, 640)
        self.setStyleSheet(VIEW_STYLE)
        v = QVBoxLayout(self);v.setContentsMargins(24, 24, 24, 24);v.setSpacing(18)
        page_header(v, "Nueva inspección", "Completa los datos iniciales. Los campos con * son obligatorios.")
        panel, content = card();form = QGridLayout();form.setHorizontalSpacing(20);form.setVerticalSpacing(14)
        form.setColumnStretch(0, 1);form.setColumnStretch(1, 1)
        self.date=QDateEdit(QDate.currentDate());self.date.setCalendarPopup(True);self.date.setDisplayFormat("yyyy-MM-dd")
        self.company=QLineEdit();self.pqm=QLineEdit();self.act=QLineEdit();self.author=QLineEdit()
        self.obs=QTextEdit();self.obs.setMaximumHeight(100)
        field(form, 0, 0, "Empresa o cliente *", self.company, span=2)
        field(form, 1, 0, "Número PQM *", self.pqm);field(form, 1, 1, "Número de acta *", self.act)
        field(form, 2, 0, "Fecha de inspección", self.date);field(form, 2, 1, "Elaborado por *", self.author)
        field(form, 3, 0, "Observaciones", self.obs, span=2);content.addLayout(form);v.addWidget(panel)
        if prefill:
            self.company.setText(prefill.company);self.act.setText(prefill.act_number);self.author.setText(prefill.author);self.obs.setPlainText(prefill.observations)
        v.addStretch();actions=QHBoxLayout();actions.addStretch()
        actions.addWidget(button("Cancelar", self.reject));actions.addWidget(button("Crear inspección", self.accept, primary=True));v.addLayout(actions)
    def values(self):
        return dict(inspection_date=self.date.date().toPython(),company=self.company.text(),pqm_number=self.pqm.text(),act_number=self.act.text(),author=self.author.text(),observations=self.obs.toPlainText())

class InspectionEditor(QDialog):
    def __init__(self, parent, iid):
        super().__init__(parent);self.main=parent;self.iid=iid;self.service=parent.service;self.images=ImageService()
        self.setWindowTitle("Inspección PQM");self.resize(1180, 800);self.setStyleSheet(VIEW_STYLE);self.current=None
        self._loading=False;self._saving=False
        self.autosave_timer=QTimer(self);self.autosave_timer.setSingleShot(True);self.autosave_timer.setInterval(1500)
        self.autosave_timer.timeout.connect(self.autosave)
        outer=QVBoxLayout(self);outer.setContentsMargins(24, 22, 24, 22);outer.setSpacing(16)
        self.heading=QLabel();self.heading.setObjectName("pageTitle");self.heading.setWordWrap(True);outer.addWidget(self.heading)
        self.save_status=QLabel("Sin cambios pendientes");self.save_status.setObjectName("settingsHint")
        self.save_status.setWordWrap(True);outer.addWidget(self.save_status)
        self.progress_label=QLabel();self.progress_label.setObjectName("sectionDescription");self.progress_label.setWordWrap(True)
        outer.addWidget(self.progress_label);self.progress=QProgressBar();self.progress.setTextVisible(False);outer.addWidget(self.progress)
        self.tabs=QTabWidget();self.tabs.setDocumentMode(True);outer.addWidget(self.tabs, 1)

        general_page=QWidget();general_layout=QVBoxLayout(general_page);general_layout.setContentsMargins(0, 16, 0, 0)
        self.general=QGroupBox();self.general.setObjectName("settingsCard")
        general_content=QVBoxLayout(self.general);general_content.setContentsMargins(22, 22, 22, 22);general_content.setSpacing(14)
        section_header(general_content, "Datos generales", "Información del cliente, responsable y conclusiones de la inspección.")
        self.date=QDateEdit();self.date.setCalendarPopup(True);self.date.setDisplayFormat("yyyy-MM-dd")
        self.company=QLineEdit();self.pqm=QLineEdit();self.act=QLineEdit();self.author=QLineEdit()
        self.generalobs=QTextEdit();self.generalobs.setMaximumHeight(100);self.conclusion=QLineEdit()
        grid=QGridLayout();grid.setHorizontalSpacing(20);grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1);grid.setColumnStretch(1, 1)
        field(grid, 0, 0, "Empresa o cliente", self.company);field(grid, 0, 1, "Elaborado por", self.author)
        field(grid, 1, 0, "Número PQM", self.pqm);field(grid, 1, 1, "Número de acta", self.act)
        field(grid, 2, 0, "Fecha de inspección", self.date);field(grid, 2, 1, "Conclusión técnica", self.conclusion)
        field(grid, 3, 0, "Observaciones generales", self.generalobs, span=2);general_content.addLayout(grid)
        general_layout.addWidget(self.general);general_layout.addStretch()
        general_scroll=QScrollArea();general_scroll.setWidgetResizable(True);general_scroll.setWidget(general_page)
        self.tabs.addTab(general_scroll, "Datos generales")

        evidence_page=QWidget();evidence_layout=QVBoxLayout(evidence_page);evidence_layout.setContentsMargins(0, 16, 0, 0)
        split=QSplitter();split.setChildrenCollapsible(False)
        self.list=EvidenceList();self.list.setIconSize(QSize(20, 20));self.list.setTextElideMode(Qt.ElideNone);self.list.setMinimumWidth(220);self.list.setWordWrap(True);self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(self.select_evidence);split.addWidget(self.list)
        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(12, 0, 0, 0);rv.setSpacing(12)
        self.info=QLabel("Selecciona una evidencia para comenzar");self.info.setObjectName("sectionTitle")
        self.info.setWordWrap(True);self.info.setContentsMargins(20, 8, 20, 8);rv.addWidget(self.info)
        evidence_content=QWidget();evidence_body=QVBoxLayout(evidence_content)
        evidence_body.setContentsMargins(0, 0, 8, 0);evidence_body.setSpacing(18)
        evidence_body.setAlignment(Qt.AlignTop)
        evidence_scroll=QScrollArea();evidence_scroll.setWidgetResizable(True)
        evidence_scroll.setWidget(evidence_content);rv.addWidget(evidence_scroll, 1)
        self.detail=QGroupBox();self.detail.setObjectName("settingsCard")
        detail_content=QVBoxLayout(self.detail);detail_content.setContentsMargins(20, 22, 20, 22);detail_content.setSpacing(14);detail_content.setAlignment(Qt.AlignTop)
        section_header(detail_content, "Evaluación de la evidencia", "Registra el resultado, la medición y las observaciones.")
        self.state=QComboBox();self.state.addItems(["Pendiente", "Conforme", "No conforme", "No aplica"])
        self.measure=QLineEdit();self.unit=QLineEdit();self.obs=QTextEdit();self.obs.setMaximumHeight(100)
        self.na=QLineEdit();self.na.setPlaceholderText("Obligatoria cuando la evaluación es No aplica")
        detail_grid=QGridLayout();detail_grid.setHorizontalSpacing(16);detail_grid.setVerticalSpacing(14)
        detail_grid.setColumnStretch(0, 1);detail_grid.setColumnStretch(1, 1);detail_grid.setAlignment(Qt.AlignTop)
        field(detail_grid, 0, 0, "Evaluación", self.state, span=2)
        field(detail_grid, 1, 0, "Medición", self.measure);field(detail_grid, 1, 1, "Unidad", self.unit)
        field(detail_grid, 2, 0, "Observaciones", self.obs, span=2)
        field(detail_grid, 3, 0, "Justificación de No aplica", self.na, span=2)
        detail_content.addLayout(detail_grid)
        evidence_body.addWidget(self.detail)
        photo_panel, photo_layout=card()
        section_header(photo_layout, "Fotografías de la evidencia", "Agrega originales y revisa las imágenes asociadas.")
        self.gallery=QListWidget();self.gallery.setViewMode(QListWidget.IconMode);self.gallery.setResizeMode(QListWidget.Adjust)
        self.gallery.setIconSize(QSize(160, 110));self.gallery.setSpacing(8);self.gallery.setFixedHeight(180)
        photo_layout.addWidget(self.gallery, 1)
        photo_actions=QHBoxLayout()
        self.add_photo_button=button("Agregar fotos", self.add_photos, primary=True)
        self.delete_photo_button=button("Eliminar foto", self.delete_photo);self.delete_photo_button.setProperty("class", "danger")
        photo_actions.addWidget(self.add_photo_button);photo_actions.addWidget(button("Ver foto", self.view_photo));photo_actions.addStretch()
        photo_actions.addWidget(self.delete_photo_button);photo_layout.addLayout(photo_actions)
        evidence_body.addWidget(photo_panel)
        evidence_body.addStretch()
        split.addWidget(right);split.setStretchFactor(0, 1);split.setStretchFactor(1, 3);split.setSizes([280, 800])
        evidence_layout.addWidget(split);self.tabs.addTab(evidence_page, "Evidencias")

        bottom=QHBoxLayout();bottom.setSpacing(10)
        bottom.addWidget(button("Guardar avance", self.save_general, primary=True))
        bottom.addWidget(button("Ver checkpoints", self.show_checkpoints));bottom.addStretch()
        documents=QPushButton("Documentos");documents_menu=QMenu(documents)
        documents_menu.addAction("Generar PDF borrador", self.pdf)
        documents_menu.addAction("Enviar PDF aprobado", self.send_report)
        documents.setMenu(documents_menu);bottom.addWidget(documents)
        transitions=QPushButton("Cambiar estado");transition_menu=QMenu(transitions)
        for label, target in (("Enviar a revisión", "PENDIENTE_REVISION"), ("Aprobar", "APROBADA"),
                              ("Rechazar", "RECHAZADA"), ("Cerrar inspección", "CERRADA")):
            transition_menu.addAction(label, lambda checked=False, t=target:self.transition(t))
        transitions.setMenu(transition_menu);bottom.addWidget(transitions);outer.addLayout(bottom)
        self.load()
        for widget in (self.company, self.pqm, self.act, self.author, self.conclusion, self.measure, self.unit, self.na):
            widget.textChanged.connect(self.schedule_save)
        for widget in (self.generalobs, self.obs):widget.textChanged.connect(self.schedule_save)
        self.date.dateChanged.connect(self.schedule_save);self.state.currentTextChanged.connect(self.schedule_save)
    def general_values(self):
        return dict(inspection_date=self.date.date().toPython(), company=self.company.text(),
                    pqm_number=self.pqm.text(), act_number=self.act.text(), author=self.author.text(),
                    observations=self.generalobs.toPlainText(), conclusion=self.conclusion.text())
    def schedule_save(self, *args):
        if not self._loading:
            self.save_status.setText("Cambios pendientes de guardar…")
            self.autosave_timer.start()
    def autosave(self):
        if self._loading or self._saving:
            return False
        self.autosave_timer.stop()
        self._saving = True
        try:
            general = self.general_values()
            if self.general.isEnabled() and general != self.general_snapshot:
                self.service.update_general(self.iid, **general)
                self.general_snapshot = general
            if self.detail.isEnabled() and self.current and self.evidence_values() != self.evidence_snapshot:
                status, measured_value, unit, observations, na_reason = self.evidence_values()
                self.service.save_evidence(self.current, status=status, measured_value=measured_value,
                                          unit=unit, observations=observations, na_reason=na_reason)
                self.evidence_snapshot = self.evidence_values()
                for index in range(self.list.count()):
                    entry = self.list.item(index)
                    if entry.data(Qt.UserRole) == self.current:
                        evidence_status_item(entry, status)
                        self.list.refresh_item_sizes()
                        break
            self.save_status.setText("Avance guardado · " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            return True
        except InspectionError as error:
            self.save_status.setText("No se guardó: " + str(error))
            return False
        except Exception:
            self.save_status.setText("No se guardó el avance. Revise los campos obligatorios y la conexión; pulse Guardar para reintentar.")
            return False
        finally:
            self._saving = False
    def reject(self):
        if self.autosave():
            super().reject()
        else:
            QMessageBox.warning(self, "Cambios pendientes", "No se pudo guardar. Revise los datos y la conexión antes de cerrar.")
    def closeEvent(self, event):
        if self.autosave():
            event.accept()
        else:
            event.ignore()
            QMessageBox.warning(self, "Cambios pendientes", "No se pudo guardar. Revise los datos y la conexión antes de cerrar.")
    def show_checkpoints(self):
        if not self.autosave():
            return
        try:
            with SessionLocal() as session:
                checkpoints = history(session, self.iid)
            dialog = QDialog(self); dialog.setWindowTitle("Últimos 100 checkpoints"); dialog.resize(800, 600);dialog.setStyleSheet(VIEW_STYLE)
            layout = QVBoxLayout(dialog); entries = QComboBox(); preview = QTextEdit(); preview.setReadOnly(True)
            for entry in checkpoints:
                entries.addItem(f"#{entry.id} · {entry.created_at:%Y-%m-%d %H:%M:%S} · {entry.reason}", entry.snapshot)
            entries.currentIndexChanged.connect(lambda _: preview.setPlainText(json.dumps(json.loads(entries.currentData()), indent=2, ensure_ascii=False) if entries.currentData() else "Sin checkpoints"))
            preview.setPlainText(json.dumps(json.loads(entries.currentData()), indent=2, ensure_ascii=False) if entries.currentData() else "Sin checkpoints")
            layout.addWidget(entries); layout.addWidget(preview); dialog.exec()
        except Exception:
            QMessageBox.warning(self, "Checkpoints", "No se pudo consultar el historial. Revise la conexión.")
    def load(self):
        item = self.service.get(self.iid)
        p = self.service.progress(self.iid)
        self._loading = True
        self.autosave_timer.stop()
        self.list.blockSignals(True)
        self.current = None
        self.evidence_snapshot = self.evidence_values()
        self.gallery.clear()
        reference = item.pqm_number if item.pqm_number.upper().startswith("PQM") else f"PQM {item.pqm_number}"
        self.heading.setText(f"{reference} · {item.company}");self.date.setDate(QDate(item.inspection_date.year,item.inspection_date.month,item.inspection_date.day));self.company.setText(item.company);self.pqm.setText(item.pqm_number);self.act.setText(item.act_number);self.author.setText(item.author);self.generalobs.setPlainText(item.observations);self.conclusion.setText(item.conclusion)
        self.list.clear(); categories=[]
        for e in item.evidences:
            if e.category not in categories:
                categories.append(e.category);head=QListWidgetItem("▸ "+e.category);head.setFlags(Qt.NoItemFlags);head.setBackground(QColor("#edf3f8"));head.setForeground(QColor("#12365a"));font=QFont();font.setBold(True);head.setFont(font);self.list.addItem(head)
            x=QListWidgetItem(f"{e.order:02d}. {e.title}\n{e.status} · {len(e.images)} foto(s)");x.setData(Qt.UserRole,e.id);evidence_status_item(x, e.status);self.list.addItem(x)
        self.list.refresh_item_sizes()
        self.progress.setValue(p["percent"]);self.progress_label.setText(f"{STATUS_NAMES.get(item.status, item.status)}   ·   Documentadas: {p['documented']}/35   |   Conformes: {p['Conforme']}   |   No conformes: {p['No conforme']}   |   No aplica: {p['No aplica']}   |   Pendientes: {p['Pendiente']}")
        editable=item.status in {"EN_ELABORACION","RECHAZADA"}
        for w in [self.general,self.detail,self.add_photo_button,self.delete_photo_button]:w.setEnabled(editable)
        self.general_snapshot = self.general_values()
        self.list.blockSignals(False)
        self._loading = False
        self.detail.setEnabled(False)
        self.add_photo_button.setEnabled(False)
        self.delete_photo_button.setEnabled(False)
    def select_evidence(self,current,previous=None):
        if not current or current.data(Qt.UserRole) is None:return
        if not self.save_if_dirty():
            self.list.blockSignals(True)
            self.list.setCurrentItem(previous)
            self.list.blockSignals(False)
            return
        self._loading = True
        try:
            e=self.service.evidence(current.data(Qt.UserRole))
            editable=e.inspection.status in {"EN_ELABORACION", "RECHAZADA"}
            for widget in (self.detail, self.add_photo_button, self.delete_photo_button):
                widget.setEnabled(editable)
            self.current=e.id;self.info.setText(f"{e.category}  |  {e.code} — {e.title}");self.state.setCurrentText(e.status);self.measure.setText(e.measured_value);self.unit.setText(e.unit);self.obs.setPlainText(e.observations);self.na.setText(e.na_reason);self.evidence_snapshot=self.evidence_values();self.gallery.clear()
            for img in e.images:
                path=self.images.thumbnail_path(img);entry=QListWidgetItem(img.original_name);entry.setData(Qt.UserRole,img.id)
                if path.exists():entry.setIcon(QIcon(str(path)))
                self.gallery.addItem(entry)
        except Exception as ex:QMessageBox.warning(self,"Error",str(ex))
        finally:self._loading = False
    def evidence_values(self):
        return (self.state.currentText(),self.measure.text(),self.unit.text(),self.obs.toPlainText(),self.na.text())
    def save_if_dirty(self):
        return self.autosave()
    def save_evidence(self):
        if self.autosave():
            selected = self.current
            self.load()
            self._select_by_id(selected)
        else:
            QMessageBox.warning(self, "No se pudo guardar", self.save_status.text())
    def add_photos(self):
        if not self.current or not self.autosave():return
        paths=QFileDialog.getOpenFileNames(self,"Seleccionar fotografías", "", "Imágenes (*.jpg *.jpeg *.png)")[0]
        if paths:
            try:
                selected=self.current;self.images.add(selected,paths);self.load();self._select_by_id(selected)
            except Exception as e:QMessageBox.warning(self,"No se pudieron agregar las fotografías",str(e))
    def _select_by_id(self,eid):
        for i in range(self.list.count()):
            it=self.list.item(i)
            if it.data(Qt.UserRole)==eid:self.list.setCurrentItem(it);return
    def delete_photo(self):
        if not self.autosave():return
        it=self.gallery.currentItem()
        if it and QMessageBox.question(self,"Eliminar fotografía",f"¿Retirar {it.text()} de la evidencia? Se conservará el original para el historial.")==QMessageBox.Yes:
            try:
                selected=self.current;self.images.delete(it.data(Qt.UserRole));self.load();self._select_by_id(selected)
            except Exception as e:QMessageBox.warning(self,"No se pudo eliminar",str(e))
    def view_photo(self):
        it=self.gallery.currentItem()
        if not it:return
        try:
            e=self.service.evidence(self.current);img=next(x for x in e.images if x.id==it.data(Qt.UserRole));path=self.images.absolute(img.relative_path);QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as e:QMessageBox.warning(self,"No se pudo abrir",str(e))
    def save_general(self):
        self.save_evidence()
    def transition(self,target):
        if not self.autosave():return
        actor,ok=QInputDialog.getText(self,"Confirmar cambio de estado","Responsable:")
        if not ok:return
        notes,ok=QInputDialog.getText(self,"Observaciones","Observaciones de la acción:")
        if not ok:return
        try:self.service.transition(self.iid,target,actor,notes);self.load();QMessageBox.information(self,"Estado actualizado",f"La inspección quedó en {target}.")
        except Exception as e:QMessageBox.warning(self,"No se pudo cambiar el estado",str(e))
    def pdf(self):
        if not self.autosave():return
        try:
            p=PDFReportService().generate(self.iid,"BORRADOR");QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
        except Exception as e:QMessageBox.warning(self,"Error de PDF",str(e))
    def send_report(self):
        with SessionLocal() as s:
            item=s.get(Inspection,self.iid)
            if not item or item.status not in {"APROBADA","CERRADA"}:
                return QMessageBox.warning(self,"Inspección no aprobada","Solo se puede remitir el PDF final de una inspección aprobada.")
            report=s.scalar(select(Report).where(Report.inspection_id==self.iid,Report.report_type=="FINAL").order_by(Report.version.desc()))
            if not report:
                try:PDFReportService().generate(self.iid,"FINAL")
                except Exception as e:return QMessageBox.warning(self,"No se pudo generar el PDF final",str(e))
                report=s.scalar(select(Report).where(Report.inspection_id==self.iid,Report.report_type=="FINAL").order_by(Report.version.desc()))
            report_path=materialize(s, report.path, DATA_DIR)
            settings={x.key:x.value for x in s.scalars(select(AppSetting)).all()}
            pqm,company=item.pqm_number,item.company
        confirm=QMessageBox.question(self,"Confirmar envío",f"Enviar el informe aprobado de {pqm} – {company} a:\n{settings.get('smtp_recipients','(sin destinatario)')}?",QMessageBox.Yes|QMessageBox.No)
        if confirm!=QMessageBox.Yes:return
        recipient=settings.get("smtp_recipients","")
        try:
            import keyring
            password=keyring.get_password("PQM Quality Manager",settings.get("smtp_username","")) or ""
            if not password:raise ValueError("No hay contraseña SMTP guardada en el almacén seguro.")
            if not report_path.exists():raise ValueError("No se encuentra el PDF final registrado.")
            EmailService().send(host=settings["smtp_host"],port=settings.get("smtp_port","587"),username=settings.get("smtp_username",""),password=password,sender=settings["smtp_sender"],recipients=[x.strip() for x in recipient.split(",") if x.strip()],subject=f"Entrega Informe PQM – {pqm} – {company}",body=f"Buen día,\n\nSe remite el informe técnico de inspección y entrega correspondiente al tablero PQM identificado con el registro {pqm}, asociado a {company}, para la revisión y gestión correspondiente del área de Calidad.\n\nSe adjunta el documento con las evidencias fotográficas, verificaciones realizadas y observaciones técnicas.\n\nCordialmente,\nINGELEAN S.A.S.",attachment=report_path,use_ssl=settings.get("smtp_ssl")=="1",use_starttls=settings.get("smtp_ssl")!="1")
            result="ENVIADO";detail="El servidor SMTP confirmó el envío."
        except Exception as e:result="ERROR";detail=str(e)
        with SessionLocal() as s:s.add(EmailDispatch(inspection_id=self.iid,recipient=recipient,result=result,detail=detail));s.commit()
        if result=="ENVIADO":QMessageBox.information(self,"Correo enviado",detail)
        else:QMessageBox.warning(self,"No se pudo enviar",detail)

class SettingsPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setStyleSheet(SETTINGS_STYLE)
        outer = QVBoxLayout(self); outer.setContentsMargins(28, 26, 28, 28); outer.setSpacing(20)
        header = QHBoxLayout()
        titles = QVBoxLayout(); titles.setSpacing(5)
        title = QLabel("Configuración"); title.setStyleSheet("font-size:28px;font-weight:700;color:#12365a;")
        subtitle = QLabel("Administra la conexión, el correo y las copias de tus datos.")
        subtitle.setObjectName("sectionDescription"); subtitle.setWordWrap(True)
        titles.addWidget(title); titles.addWidget(subtitle); header.addLayout(titles, 1)
        active = QLabel("PostgreSQL en servidor" if database_engine.engine.dialect.name == "postgresql" else "SQLite local")
        active.setObjectName("activeDatabase"); active.setToolTip("Base de datos utilizada en esta sesión")
        header.addWidget(active, 0, Qt.AlignTop); outer.addLayout(header)
        self.tabs = QTabWidget(); self.tabs.setDocumentMode(True); outer.addWidget(self.tabs, 1)

        database_page = QWidget(); database_layout = QVBoxLayout(database_page)
        database_layout.setContentsMargins(0, 20, 0, 0)
        self.database_settings = DatabaseSettings(); database_layout.addWidget(self.database_settings)
        database_layout.addStretch(); self.tabs.addTab(database_page, "Base de datos")

        email_page = QWidget(); email_layout = QVBoxLayout(email_page)
        email_layout.setContentsMargins(0, 20, 0, 0)
        group = QGroupBox(); group.setObjectName("settingsCard")
        content = QVBoxLayout(group); content.setContentsMargins(24, 24, 24, 24); content.setSpacing(14)
        section_header(content, "Correo para Calidad", "Configura el remitente y los destinatarios de los informes aprobados.")
        self.host = QLineEdit(); self.host.setPlaceholderText("smtp.empresa.com")
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(587)
        self.sender = QLineEdit(); self.sender.setPlaceholderText("calidad@empresa.com")
        self.username = QLineEdit(); self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.recipients = QLineEdit(); self.recipients.setPlaceholderText("destinatario@empresa.com, otro@empresa.com")
        self.ssl = QCheckBox("Usar SSL implícito")
        form = QGridLayout(); form.setHorizontalSpacing(20); form.setVerticalSpacing(16)
        form.setColumnStretch(0, 1); form.setColumnStretch(1, 1)
        field(form, 0, 0, "Servidor SMTP", self.host); field(form, 0, 1, "Puerto", self.port)
        field(form, 1, 0, "Usuario", self.username); field(form, 1, 1, "Contraseña", self.password)
        field(form, 2, 0, "Correo remitente", self.sender, span=2)
        field(form, 3, 0, "Destinatarios · separados por coma", self.recipients, span=2)
        content.addLayout(form); content.addWidget(self.ssl)
        buttons = QHBoxLayout(); buttons.addStretch()
        test = QPushButton("Enviar correo de prueba"); test.clicked.connect(self.test_email)
        save = QPushButton("Guardar correo"); save.setProperty("class", "primary"); save.clicked.connect(self.save_config)
        buttons.addWidget(test); buttons.addWidget(save); content.addLayout(buttons)
        hint = QLabel("La contraseña del correo se guarda en el almacén seguro del sistema.")
        hint.setObjectName("settingsHint"); hint.setWordWrap(True); content.addWidget(hint)
        email_layout.addWidget(group); email_layout.addStretch(); self.tabs.addTab(email_page, "Correo")

        backup_page = QWidget(); backup_layout = QVBoxLayout(backup_page)
        backup_layout.setContentsMargins(0, 20, 0, 0); backup_layout.setSpacing(18)
        for title_text, description, action_text, callback, primary in (
            ("Crear una copia de seguridad", "Guarda un respaldo de las inspecciones, fotografías e informes.",
             "Crear respaldo ZIP", self.backup, True),
            ("Restaurar un respaldo", "Recupera los datos de una copia anterior. Se pedirá confirmación antes de reemplazarlos.",
             "Seleccionar respaldo", self.restore, False),
        ):
            card = QGroupBox(); card.setObjectName("settingsCard")
            content = QVBoxLayout(card); content.setContentsMargins(24, 24, 24, 24); content.setSpacing(14)
            section_header(content, title_text, description)
            row = QHBoxLayout(); row.addStretch(); button = QPushButton(action_text)
            if primary: button.setProperty("class", "primary")
            button.clicked.connect(callback); row.addWidget(button); content.addLayout(row)
            backup_layout.addWidget(card)
        backup_layout.addStretch(); self.tabs.addTab(backup_page, "Respaldos")
        self.load_config()
    def load_config(self):
        with SessionLocal() as s:
            vals={x.key:x.value for x in s.scalars(select(AppSetting)).all()}
        self.host.setText(vals.get("smtp_host",""));self.port.setValue(int(vals.get("smtp_port",587)));self.sender.setText(vals.get("smtp_sender",""));self.username.setText(vals.get("smtp_username",""));self.recipients.setText(vals.get("smtp_recipients",""));self.ssl.setChecked(vals.get("smtp_ssl","0")=="1")
        try:
            import keyring;self.password.setText(keyring.get_password("PQM Quality Manager",self.username.text()) or "")
        except Exception:pass
    def save_config(self):
        values={"smtp_host":self.host.text().strip(),"smtp_port":str(self.port.value()),"smtp_sender":self.sender.text().strip(),"smtp_username":self.username.text().strip(),"smtp_recipients":self.recipients.text().strip(),"smtp_ssl":"1" if self.ssl.isChecked() else "0"}
        try:
            import keyring
            if self.password.text():keyring.set_password("PQM Quality Manager",self.username.text(),self.password.text())
        except Exception as e:return QMessageBox.warning(self,"Almacén seguro no disponible",str(e))
        with SessionLocal() as s:
            for k,val in values.items():
                o=s.get(AppSetting,k)
                if o:o.value=val
                else:s.add(AppSetting(key=k,value=val))
            s.commit()
        QMessageBox.information(self,"Configuración","La configuración se guardó.")
    def test_email(self):
        if not self.host.text() or not self.sender.text() or not self.recipients.text():return QMessageBox.warning(self,"Datos requeridos","Configure servidor, remitente y destinatario.")
        if QMessageBox.question(self,"Enviar correo de prueba",f"Se enviará un mensaje real a {self.recipients.text()}. ¿Continuar?",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        try:EmailService().send(host=self.host.text(),port=self.port.value(),username=self.username.text(),password=self.password.text(),sender=self.sender.text(),recipients=[x.strip() for x in self.recipients.text().split(",") if x.strip()],subject="Prueba SMTP – PQM Quality Manager",body="Prueba de envío de correo desde PQM Quality Manager.",attachment=self._test_pdf(),use_ssl=self.ssl.isChecked(),use_starttls=not self.ssl.isChecked());QMessageBox.information(self,"Prueba enviada","El servidor SMTP confirmó el envío de la prueba.")
        except Exception as e:QMessageBox.warning(self,"Falló la conexión SMTP",str(e))
    def _test_pdf(self):
        from reportlab.pdfgen import canvas
        from pqm_quality_manager.config.settings import DATA_DIR
        p=DATA_DIR/"prueba_correo.pdf";c=canvas.Canvas(str(p));c.drawString(50,800,"Prueba de conexión PQM");c.save();return p
    def backup(self):
        path=QFileDialog.getSaveFileName(self,"Guardar respaldo",str(Path.home()/"respaldo_pqm.zip"),"Archivo ZIP (*.zip)")[0]
        if path:
            try:p=BackupService().create(path);QMessageBox.information(self,"Respaldo creado",f"Respaldo guardado en:\n{p}")
            except Exception as e:QMessageBox.critical(self,"Error de respaldo",str(e))
    def restore(self):
        path=QFileDialog.getOpenFileName(self,"Seleccionar respaldo", "", "Archivo ZIP (*.zip)")[0]
        if path and QMessageBox.warning(self,"Restaurar respaldo","Se reemplazará la base de datos actual. Se guardará antes un respaldo preventivo. ¿Continuar?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            try:BackupService().restore(path);QMessageBox.information(self,"Restauración","El respaldo se restauró. Cierre y vuelva a abrir la aplicación.")
            except Exception as e:QMessageBox.critical(self,"Error de restauración",str(e))

