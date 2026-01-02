"""
modulo orquestrador de tudo, todos os modulos trabalham juntos aqui.
"""
import requests
from pathlib import Path
from urllib.parse import urlparse

from config import HEADERS
from logger import setup_logger
from state.state import State

from discovery.crawler import crawl
from discovery.evaluator import should_escalate
from discovery.browser_fallback import crawl_browser

from downloader.downloader import download
from storage.index import append_index


def filter_pages_for_seed(pages: list[str], seed_url: str) -> list[str]:
    seed_host = urlparse(seed_url).hostname or ""
    return [
        p for p in pages
        if urlparse(p).hostname and urlparse(p).hostname.endswith(seed_host)
    ]


SEEDS = [
    {
        "entidade": "AEROS",
        "seed": "https://www.aeros.com.br",
        "allowed_paths": []
    },
    {
        "entidade": "AGROS",
        "seed": "https://www.agros.org.br/institucional/transparencia-demonstrativos",
        "allowed_paths": []
    },
    {
        "entidade": "ALBAPREV",
        "seed": "https://albaprev.com.br/transparencia/",
        "allowed_paths": ["/transparencia/"]
    },
]

def main():
    logger = setup_logger(Path("data/logs"))
    state = State(Path("data"))

    session = requests.Session()
    session.headers.update(HEADERS)

    for cfg in SEEDS:
        if not isinstance(cfg, dict):
            logger.error(f"Seed inválido: {cfg}")
            continue

        entidade = cfg.get("entidade", "DESCONHECIDA")
        seed_url = cfg["seed"]

        logger.info("=" * 60)
        logger.info(f"Iniciando entidade: {entidade}")
        logger.info(f"Seed: {seed_url}")

        # ==================================================
        # 1. HTML FIRST
        # ==================================================
        stats = crawl(
            session=session,
            seed_cfg=cfg,
            state=state,
            downloader=download,
            storage=append_index,
            logger=logger
        )

        # ==================================================
        # 2. BROWSER FALLBACK LEVE (SE NECESSÁRIO)
        # ==================================================
        if should_escalate(stats):
            all_pages = list(state.visited_pages)
            pages = filter_pages_for_seed(all_pages, seed_url)

            logger.warning(
                f"[{entidade}] HTML insuficiente "
                f"(pages={stats['visited_pages']}, pdfs={stats['found_pdfs']}). "
                f"Usando browser fallback leve com {len(pages)} páginas filtradas."
            )

            if not pages:
                logger.warning(f"[{entidade}] Nenhuma página válida para fallback.")
                continue

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
