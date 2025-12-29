'''
modulo de configuracao do logger do sistema
'''
import logging
from pathlib import Path

def setup_logger(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scraper.log"

    logger = logging.getLogger("SCRAPER_PLANOS")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        "%d-%m-%Y %H:%M:%S"
    )

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)

    logger.addHandler(sh)
    logger.addHandler(fh)

    return logger
