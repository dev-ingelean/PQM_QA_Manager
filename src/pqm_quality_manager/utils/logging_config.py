import logging
from pqm_quality_manager.config.settings import LOG_DIR

def configure_logging():
    logging.basicConfig(filename=LOG_DIR / "pqm_quality_manager.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s", encoding="utf-8")
