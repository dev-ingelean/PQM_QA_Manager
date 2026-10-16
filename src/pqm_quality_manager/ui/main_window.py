from pathlib import Path
from datetime import datetime
import json
from PySide6.QtCore import Qt, QDate, QSize, QTimer
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton, QLabel, QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QMessageBox, QDialog, QFormLayout, QDateEdit, QTextEdit, QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter, QGroupBox, QDoubleSpinBox, QFileDialog, QInputDialog, QProgressBar, QCheckBox, QSpinBox, QScrollArea)
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

NAVY = "#12365A"; BLUE = "#176B9B"; BG = "#F3F6F9"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PQM Quality Manager | INGELEAN S.A.S."); self.resize(1280, 800)
        self.service = InspectionService(); self.stack = QStackedWidget()
        root = QWidget(); outer = QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(225); side.setStyleSheet(f"QFrame#sidebar{{background:{NAVY};color:white;}} QLabel{{color:white;}}")
        sv = QVBoxLayout(side); brand = QLabel("INGELEAN\nPQM Quality Manager"); brand.setStyleSheet("font-size:18px;font-weight:700;padding:24px 12px;"); sv.addWidget(brand)
        self.pages = {}
        for title, key in [("Panel principal", "home"), ("Inspecciones", "history"), ("Configuración", "settings")]:
            b=QPushButton(title); b.setCursor(Qt.PointingHandCursor); b.setStyleSheet("text-align:left;padding:13px 16px;color:white;border:0;background:transparent;font-size:14px;"); b.clicked.connect(lambda _, k=key: self.navigate(k)); sv.addWidget(b)
        sv.addStretch(); sv.addWidget(QLabel("Versión 0.1.0", alignment=Qt.AlignCenter)); outer.addWidget(side); outer.addWidget(self.stack,1)
        self.setCentralWidget(root)
        self.pages["home"] = DashboardPage(self); self.pages["history"] = HistoryPage(self); settings_scroll = QScrollArea();settings_scroll.setWidgetResizable(True);settings_scroll.setWidget(SettingsPage(self));self.pages["settings"] = settings_scroll
        for page in self.pages.values(): self.stack.addWidget(page)
        self.setStyleSheet(f"QMainWindow{{background:{BG};}} QLabel{{color:#263746;}} QPushButton.primary{{background:{BLUE};color:white;border:0;border-radius:5px;padding:9px 14px;font-weight:600;}} QPushButton{{padding:7px 10px;}} QLineEdit,QComboBox,QDateEdit,QTextEdit,QSpinBox{{padding:6px;border:1px solid #ccd6df;border-radius:4px;background:white;}} QTableWidget{{background:white;gridline-color:#e3e8ed;}} QGroupBox{{font-weight:600;}}")
        self.navigate("home")

    def navigate(self, key):
        self.stack.setCurrentWidget(self.pages[key]); self.refresh()
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
        super().__init__(); self.main=main; lay=QVBoxLayout(self); header=QHBoxLayout(); title=QLabel("Panel principal"); title.setStyleSheet("font-size:26px;font-weight:700;"); header.addWidget(title); header.addStretch(); new=QPushButton("＋ Nueva inspección");new.setProperty("class","primary");new.clicked.connect(main.new_inspection);header.addWidget(new);lay.addLayout(header)
        self.cards=QGridLayout(); lay.addLayout(self.cards); lay.addWidget(QLabel("Inspecciones recientes")); self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["N.º PQM","Empresa","Fecha","Estado","Responsable"]); self.table.horizontalHeader().setStretchLastSection(True); self.table.cellDoubleClicked.connect(self.open_row); lay.addWidget(self.table)
    def refresh(self):
        data=self.main.service.dashboard()
        while self.cards.count():
            item=self.cards.takeAt(0); w=item.widget(); w and w.deleteLater()
        for i,(name,val) in enumerate([("Inspecciones",data["total"]),("En elaboración",data["EN_ELABORACION"]),("Pendientes de revisión",data["PENDIENTE_REVISION"]),("Aprobadas",data["APROBADA"]),("Con evidencias incompletas",data["incomplete"])]):
            card=QFrame();card.setStyleSheet("background:white;border:1px solid #e0e6eb;border-radius:8px;");v=QVBoxLayout(card); lab=QLabel(name);lab.setStyleSheet("color:#607080;");num=QLabel(str(val));num.setStyleSheet(f"font-size:25px;font-weight:700;color:{BLUE};");v.addWidget(lab);v.addWidget(num);self.cards.addWidget(card,0,i)
        recent=data["recent"];self.table.setRowCount(len(recent))
        for r,x in enumerate(recent):
            vals=[x.pqm_number,x.company,x.inspection_date.isoformat(),x.status,x.author]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))
            self.table.item(r,0).setData(Qt.UserRole,x.id)
    def open_row(self,row,col):
        it=self.table.item(row,0)
        if it: self.main.open_inspection(it.data(Qt.UserRole))

class HistoryPage(QWidget):
    def __init__(self,main):
        super().__init__();self.main=main;v=QVBoxLayout(self);top=QHBoxLayout();title=QLabel("Historial de inspecciones");title.setStyleSheet("font-size:24px;font-weight:700;");top.addWidget(title);top.addStretch();b=QPushButton("＋ Nueva inspección");b.setProperty("class","primary");b.clicked.connect(main.new_inspection);top.addWidget(b);v.addLayout(top)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText("Buscar por número PQM o empresa…");self.search.textChanged.connect(self.refresh);filters.addWidget(self.search,1);self.status=QComboBox();self.status.addItems(["Todos","EN_ELABORACION","PENDIENTE_REVISION","APROBADA","RECHAZADA","CERRADA"]);self.status.currentTextChanged.connect(self.refresh);filters.addWidget(self.status);v.addLayout(filters)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(["N.º PQM","Empresa","Fecha","Responsable","Estado","Documentación","Última modificación"]);self.table.horizontalHeader().setStretchLastSection(True);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.cellDoubleClicked.connect(self.open_row);v.addWidget(self.table)
        actions=QHBoxLayout()
        for label,fn in [("Abrir",self.open_selected),("Ver informe",self.view_report),("PDF borrador",self.pdf),("PDF final",self.final_pdf),("Duplicar",self.duplicate),("Eliminar",self.delete),("Actualizar",self.refresh)]:
            b=QPushButton(label);b.clicked.connect(fn);actions.addWidget(b)
        actions.addStretch();v.addLayout(actions)
    def refresh(self,*_):
        if not hasattr(self,"table"):return
        rows=self.main.service.list(self.search.text() if hasattr(self,"search") else "",self.status.currentText() if hasattr(self,"status") else "Todos")
        self.table.setRowCount(len(rows))
        for r,x in enumerate(rows):
            p=self.main.service.progress(x.id); vals=[x.pqm_number,x.company,x.inspection_date.isoformat(),x.author,x.status,f"{p['documented']}/35 ({p['percent']}%)",x.updated_at.strftime("%Y-%m-%d %H:%M")]
            for c,val in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(val)))
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
        with SessionLocal() as s:
            report=s.scalar(select(Report).where(Report.inspection_id==iid).order_by(Report.created_at.desc()))
            path=materialize(s, report.path, DATA_DIR) if report else None
        if not path or not path.exists():return QMessageBox.information(self,"Informe","Esta inspección todavía no tiene un PDF guardado.")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
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
    def __init__(self,parent,prefill=None):
        super().__init__(parent);self.setWindowTitle("Nueva inspección PQM");self.resize(520,420);v=QVBoxLayout(self);form=QFormLayout();self.date=QDateEdit(QDate.currentDate());self.date.setCalendarPopup(True);self.company=QLineEdit();self.pqm=QLineEdit();self.act=QLineEdit();self.author=QLineEdit();self.obs=QTextEdit();self.obs.setMaximumHeight(80)
        for label,w in [("Fecha de inspección",self.date),("Empresa o cliente *",self.company),("Número de registro PQM *",self.pqm),("Número de acta *",self.act),("Persona que elabora *",self.author),("Observaciones",self.obs)]:form.addRow(label,w)
        if prefill:
            self.company.setText(prefill.company);self.act.setText(prefill.act_number);self.author.setText(prefill.author);self.obs.setPlainText(prefill.observations)
        v.addLayout(form);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def values(self):
        return dict(inspection_date=self.date.date().toPython(),company=self.company.text(),pqm_number=self.pqm.text(),act_number=self.act.text(),author=self.author.text(),observations=self.obs.toPlainText())

class InspectionEditor(QDialog):
    def __init__(self,parent,iid):
        super().__init__(parent);self.main=parent;self.iid=iid;self.service=parent.service;self.images=ImageService();self.setWindowTitle("Inspección PQM");self.resize(1180,760);self.current=None
        self._loading = False
        self._saving = False
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1500)
        self.autosave_timer.timeout.connect(self.autosave)
        outer=QVBoxLayout(self); self.heading=QLabel();self.heading.setStyleSheet("font-size:22px;font-weight:700;");outer.addWidget(self.heading)
        self.save_status = QLabel("Sin cambios pendientes"); outer.addWidget(self.save_status)
        self.progress_label=QLabel();outer.addWidget(self.progress_label);self.progress=QProgressBar();outer.addWidget(self.progress)
        split=QSplitter();self.list=QListWidget();self.list.currentItemChanged.connect(self.select_evidence);split.addWidget(self.list)
        right=QWidget();rv=QVBoxLayout(right);self.info=QLabel();self.info.setStyleSheet("font-size:16px;font-weight:700;");rv.addWidget(self.info)
        self.general=QGroupBox("Datos generales");gf=QFormLayout(self.general);self.date=QDateEdit();self.date.setCalendarPopup(True);self.company=QLineEdit();self.pqm=QLineEdit();self.act=QLineEdit();self.author=QLineEdit();self.generalobs=QTextEdit();self.generalobs.setMaximumHeight(55);self.conclusion=QLineEdit()
        for label,w in [("Fecha",self.date),("Empresa",self.company),("N.º PQM",self.pqm),("Acta",self.act),("Elaborado por",self.author),("Observaciones generales",self.generalobs),("Conclusión técnica",self.conclusion)]:gf.addRow(label,w)
        rv.addWidget(self.general)
        self.detail=QGroupBox("Registro de evidencia");df=QFormLayout(self.detail);self.state=QComboBox();self.state.addItems(["Pendiente","Conforme","No conforme","No aplica"]);self.measure=QLineEdit();self.unit=QLineEdit();self.obs=QTextEdit();self.obs.setMaximumHeight(60);self.na=QLineEdit();self.na.setPlaceholderText("Obligatoria para No aplica")
        df.addRow("Evaluación",self.state);df.addRow("Medición",self.measure);df.addRow("Unidad",self.unit);df.addRow("Observaciones",self.obs);df.addRow("Justificación No aplica",self.na);rv.addWidget(self.detail)
        photos=QHBoxLayout();self.gallery=QListWidget();self.gallery.setViewMode(QListWidget.IconMode);self.gallery.setIconSize(QSize(100,72));self.gallery.setMinimumHeight(115);photos.addWidget(self.gallery,1);pbtn=QVBoxLayout();self.add_photo_button=QPushButton("Agregar fotos");self.add_photo_button.clicked.connect(self.add_photos);self.delete_photo_button=QPushButton("Eliminar foto");self.delete_photo_button.clicked.connect(self.delete_photo);view=QPushButton("Ver foto");view.clicked.connect(self.view_photo);pbtn.addWidget(self.add_photo_button);pbtn.addWidget(self.delete_photo_button);pbtn.addWidget(view);pbtn.addStretch();photos.addLayout(pbtn);rv.addLayout(photos)
        actions=QHBoxLayout();saveev=QPushButton("Guardar evidencia");saveev.clicked.connect(self.save_evidence);actions.addWidget(saveev);actions.addStretch();split.addWidget(right);split.setSizes([270,850]);outer.addWidget(split,1)
        bottom=QHBoxLayout();save=QPushButton("Guardar datos generales");save.clicked.connect(self.save_general);bottom.addWidget(save);bottom.addStretch()
        for label,target in [("Enviar a revisión","PENDIENTE_REVISION"),("Aprobar","APROBADA"),("Rechazar","RECHAZADA"),("Cerrar","CERRADA")]:
            b=QPushButton(label);b.clicked.connect(lambda _,t=target:self.transition(t));bottom.addWidget(b)
        checkpoints=QPushButton("Ver checkpoints");checkpoints.clicked.connect(self.show_checkpoints);bottom.addWidget(checkpoints)
        pdf=QPushButton("Generar PDF borrador");pdf.clicked.connect(self.pdf);bottom.addWidget(pdf);send=QPushButton("Enviar PDF aprobado");send.clicked.connect(self.send_report);bottom.addWidget(send);outer.addLayout(bottom);self.load()
        for widget in (self.company, self.pqm, self.act, self.author, self.conclusion, self.measure, self.unit, self.na):
            widget.textChanged.connect(self.schedule_save)
        for widget in (self.generalobs, self.obs):
            widget.textChanged.connect(self.schedule_save)
        self.date.dateChanged.connect(self.schedule_save)
        self.state.currentTextChanged.connect(self.schedule_save)
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
            dialog = QDialog(self); dialog.setWindowTitle("Últimos 100 checkpoints"); dialog.resize(800, 600)
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
        self.heading.setText(f"PQM {item.pqm_number} · {item.company} · {item.status}");self.date.setDate(QDate(item.inspection_date.year,item.inspection_date.month,item.inspection_date.day));self.company.setText(item.company);self.pqm.setText(item.pqm_number);self.act.setText(item.act_number);self.author.setText(item.author);self.generalobs.setPlainText(item.observations);self.conclusion.setText(item.conclusion)
        self.list.clear(); categories=[]
        for e in item.evidences:
            if e.category not in categories:
                categories.append(e.category);head=QListWidgetItem("▸ "+e.category);head.setFlags(Qt.NoItemFlags);head.setBackground(Qt.lightGray);self.list.addItem(head)
            x=QListWidgetItem(f"{e.order:02d}. {e.title}  ·  {e.status}  ·  {len(e.images)} foto(s)");x.setData(Qt.UserRole,e.id);self.list.addItem(x)
        self.progress.setValue(p["percent"]);self.progress_label.setText(f"Documentadas: {p['documented']}/35   |   Conformes: {p['Conforme']}   |   No conformes: {p['No conforme']}   |   No aplica: {p['No aplica']}   |   Pendientes: {p['Pendiente']}")
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
                if path.exists():entry.setIcon(QPixmap(str(path)))
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
    def __init__(self,main):
        super().__init__();self.main=main;v=QVBoxLayout(self);title=QLabel("Configuración y respaldo");title.setStyleSheet("font-size:24px;font-weight:700;");v.addWidget(title)
        info=QLabel("Base de datos: " + ("PostgreSQL en servidor" if database_engine.engine.dialect.name == "postgresql" else "SQLite local") + ". Las inspecciones, checkpoints, fotos y PDF se guardan en la base de datos. La conexión se configura abajo (requiere reiniciar). Las credenciales SMTP se guardan en el almacén seguro del sistema.");info.setWordWrap(True);v.addWidget(info)
        self.database_settings = DatabaseSettings();v.addWidget(self.database_settings)
        group=QGroupBox("Correo para Calidad (SMTP)");form=QFormLayout(group);self.host=QLineEdit();self.port=QSpinBox();self.port.setRange(1,65535);self.port.setValue(587);self.sender=QLineEdit();self.username=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);self.recipients=QLineEdit();self.ssl=QCheckBox("Usar SSL implícito");
        for label,w in [("Servidor SMTP",self.host),("Puerto",self.port),("Correo remitente",self.sender),("Usuario",self.username),("Contraseña",self.password),("Destinatarios separados por coma",self.recipients)]:form.addRow(label,w)
        form.addRow("Seguridad",self.ssl);v.addWidget(group);buttons=QHBoxLayout();save=QPushButton("Guardar configuración");save.clicked.connect(self.save_config);test=QPushButton("Enviar prueba de conexión");test.clicked.connect(self.test_email);backup=QPushButton("Crear respaldo ZIP");backup.clicked.connect(self.backup);restore=QPushButton("Restaurar respaldo");restore.clicked.connect(self.restore);[buttons.addWidget(b) for b in (save,test,backup,restore)];v.addLayout(buttons);v.addStretch();self.load_config()
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

