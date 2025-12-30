'''
modulo orquestrador de tudo, todos os modulos trabalham juntos aqui.
'''
import requests
from pathlib import Path

from config import HEADERS
from logger import setup_logger
from state.state import State
from discovery.crawler import crawl
from discovery.evaluator import should_escalate
from discovery.browser_fallback import crawl_browser
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
    {
        "entidade": "ACEPREV",
        "seed": "https://aceprev.com.br/planos",
        "allowed_paths": [
            "/planos"
        ]
    },
    {
        "entidade": "AEROS",
        "seed": "https://www.aeros.com.br",
        "allowed_paths": []  # escopo livre
    },
]

def main():
    logger = setup_logger(Path("data/logs"))
    state = State(Path("data"))

    session = requests.Session()
    session.headers.update(HEADERS)

    for cfg in SEEDS:
        entidade = cfg.get("entidade", "DESCONHECIDA")

        logger.info("=" * 60)
        logger.info(f"Iniciando entidade: {entidade}")
        logger.info(f"Seed: {cfg['seed']}")
        logger.info(f"Allowed paths: {cfg.get('allowed_paths', [])}")

        # ===============================
        # 1. HTML FIRST
        # ===============================
        stats = crawl(
            session=session,
            seed_cfg=cfg,
            state=state,
            downloader=download,
            storage=append_index,
            logger=logger
        )

        # ===============================
        # 2. DECISÃO DE ESCALONAMENTO
        # ===============================
        if should_escalate(stats):
            pages = state.get_pages_for_entity(entidade)

            logger.warning(
                f"[{entidade}] Nenhum PDF encontrado via HTML "
                f"(pages={stats['visited_pages']}, js={stats['js_signals']}). "
                f"Escalando para browser fallback com {len(pages)} páginas."
            )

            crawl_browser(
                seed_cfg=cfg,
                state=state,
                pages=pages,
                downloader=download,
                storage=append_index,
                logger=logger
            )
        else:
            logger.info(
                f"[{entidade}] HTML crawler suficiente "
                f"(pdfs={stats['found_pdfs']})."
            )

    logger.info("Scraper finalizado para todas as entidades.")

if __name__ == "__main__":
    main()
