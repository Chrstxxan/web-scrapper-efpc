'''
modulo orquestrador de tudo, todos os modulos trabalham juntos aqui.
'''
import requests
from pathlib import Path

from config import HEADERS
from logger import setup_logger
from state.state import State
from discovery.crawler import crawl
from downloader.downloader import download
from storage.index import append_index


SEEDS = [
    {
        "entidade": "Valia",
        "seed": "https://www.valia.com.br/planos-e-servicos/planos/",
        "allowed_paths": [
            "/planos-e-servicos/planos"
        ]
    },
    {
        "entidade": "FGVPrevi",
        "seed": "https://www.portalprev.com.br/FGVPrevi/FGVPrevi/Home/Biblioteca",
        "allowed_paths": [
            "/Biblioteca"
        ]
    },
]


def main():
    logger = setup_logger(Path("data/logs"))
    state = State(Path("data"))

    session = requests.Session()
    session.headers.update(HEADERS)

    for cfg in SEEDS:
        logger.info("=" * 60)
        logger.info(f"Iniciando entidade: {cfg['entidade']}")
        logger.info(f"Seed: {cfg['seed']}")
        logger.info(f"Allowed paths: {cfg.get('allowed_paths', [])}")

        crawl(
            session=session,
            seed_cfg=cfg,
            state=state,
            downloader=download,
            storage=append_index,
            logger=logger
        )

    logger.info("Scraper finalizado para todas as entidades.")


if __name__ == "__main__":
    main()
