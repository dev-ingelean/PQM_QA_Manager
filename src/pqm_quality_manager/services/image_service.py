from pathlib import Path
from uuid import uuid4
from hashlib import sha256
from datetime import datetime
from PIL import Image, ImageOps
from pqm_quality_manager.config.settings import DATA_DIR, PHOTO_DIR, THUMB_DIR
from pqm_quality_manager.database.engine import SessionLocal
from pqm_quality_manager.database.models import InspectionEvidence, EvidenceImage
from pqm_quality_manager.services.inspection_service import InspectionService
from pqm_quality_manager.services.checkpoint_service import checkpoint
from pqm_quality_manager.services.file_storage import store, materialize

class ImageService:
    ALLOWED = {".jpg", ".jpeg", ".png"}
    def add(self, evidence_id: int, paths: list[str | Path]):
        added = []
        with SessionLocal() as s:
            e = s.get(InspectionEvidence, evidence_id)
            if not e: raise ValueError("No se encontró la evidencia.")
            InspectionService._editable(e.inspection)
            target_dir = PHOTO_DIR / e.inspection.uuid / e.code
            target_dir.mkdir(parents=True, exist_ok=True)
            for raw in paths:
                src = Path(raw)
                if src.suffix.lower() not in self.ALLOWED: raise ValueError(f"Formato no permitido: {src.name}")
                try:
                    with Image.open(src) as im:
                        im.verify()
                except Exception as exc:
                    raise ValueError(f"No se puede leer la imagen {src.name}: {exc}") from exc
                name = f"{uuid4().hex}{src.suffix.lower()}"
                dest = target_dir / name
                # Preserve original bytes and metadata without re-encoding.
                import shutil
                shutil.copy2(src, dest)
                hasher = sha256()
                with dest.open("rb") as image_file:
                    for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
                        hasher.update(chunk)
                digest = hasher.hexdigest()
                record = EvidenceImage(evidence_id=e.id, relative_path=dest.relative_to(DATA_DIR).as_posix(), original_name=src.name, order=len(e.images), size_bytes=dest.stat().st_size, sha256=digest)
                s.add(record); e.images.append(record); added.append(dest)
                store(s, record.relative_path, dest)
            e.inspection.updated_at = datetime.now()
            checkpoint(s, e.inspection, "Fotografías añadidas")
            s.commit()
        return added

    @staticmethod
    def absolute(relative_path):
        path = (DATA_DIR / relative_path).resolve()
        if DATA_DIR.resolve() not in path.parents: raise ValueError("Ruta de imagen inválida")
        with SessionLocal() as session:
            return materialize(session, relative_path, DATA_DIR)

    def delete(self, image_id):
        with SessionLocal() as s:
            img = s.get(EvidenceImage, image_id)
            if not img: return
            InspectionService._editable(img.evidence.inspection)
            path = self.absolute(img.relative_path)
            inspection = img.evidence.inspection
            img.evidence.images.remove(img)
            s.delete(img)
            inspection.updated_at = datetime.now()
            checkpoint(s, inspection, "Fotografía eliminada")
            s.commit()
            if path.exists(): path.unlink()

    @staticmethod
    def thumbnail_path(image: EvidenceImage):
        # Thumbnails are cache; resolve from UUID/evidence code and source filename.
        source = ImageService.absolute(image.relative_path)
        cache_dir = THUMB_DIR / image.evidence.inspection.uuid / image.evidence.code
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / f"{image.id}.jpg"
        if not target.exists() and source.exists():
            with Image.open(source) as im:
                im = ImageOps.exif_transpose(im).convert("RGB"); im.thumbnail((360, 240))
                im.save(target, "JPEG", quality=78, optimize=True)
        return target
