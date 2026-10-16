from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
from tempfile import TemporaryDirectory
from pqm_quality_manager.config.settings import DATA_DIR, DB_PATH
from pqm_quality_manager.database.engine import engine
import sqlite3

class BackupService:
    def create(self, destination: str | Path | None = None) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = Path(destination) if destination else DATA_DIR / f"respaldo_pqm_{stamp}.zip"
        with TemporaryDirectory() as tmp:
            db_copy = Path(tmp) / "database.sqlite3"
            source = sqlite3.connect(DB_PATH); target = sqlite3.connect(db_copy)
            source.backup(target); target.close(); source.close()
            with ZipFile(dest, "w", ZIP_DEFLATED) as z:
                z.write(db_copy, "database/pqm_quality_manager.sqlite3")
                for folder in ("photos", "reports"):
                    root = DATA_DIR / folder
                    if root.exists():
                        for file in root.rglob("*"):
                            if file.is_file(): z.write(file, file.relative_to(DATA_DIR).as_posix())
        return dest

    def restore(self, archive: str | Path) -> None:
        # Validate names and content before writing. DB is first extracted to a temp location.
        with TemporaryDirectory() as tmp:
            temp = Path(tmp)
            with ZipFile(archive) as z:
                if len(z.infolist()) > 20000 or sum(info.file_size for info in z.infolist()) > 10 * 1024**3:
                    raise ValueError("El respaldo supera los límites de contenido permitidos.")
                for info in z.infolist():
                    dest = (temp / info.filename).resolve()
                    if temp.resolve() not in dest.parents and dest != temp.resolve(): raise ValueError("El ZIP contiene una ruta insegura.")
                z.extractall(temp)
            db = temp / "database/pqm_quality_manager.sqlite3"
            if not db.exists(): raise ValueError("El respaldo no contiene la base de datos.")
            con = sqlite3.connect(db)
            check = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
            if check != "ok": raise ValueError(f"La base de datos del respaldo no es íntegra: {check}")
            # Keep a pre-restore snapshot, then replace files using validated relative paths.
            safety = self.create(DATA_DIR / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.zip")
            engine.dispose()
            src = sqlite3.connect(db); dst = sqlite3.connect(DB_PATH); src.backup(dst); dst.close(); src.close()
            for folder in ("photos", "reports"):
                incoming = temp / folder
                if incoming.exists():
                    target = DATA_DIR / folder; target.mkdir(exist_ok=True)
                    import shutil
                    shutil.rmtree(target)
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(incoming, target, dirs_exist_ok=True)

