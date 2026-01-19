import requests
from pathlib import Path
from urllib.parse import urlparse

from config import HEADERS
from logger import setup_logger
from state.state import State

from discovery.crawler import crawl
from discovery.evaluator import should_escalate, should_try_sitemap
from discovery.browser_fallback import crawl_browser
from discovery.sitemap import discover_sitemap_urls, filter_sitemap_urls
from discovery.domain_guard import get_base_domain

from downloader.downloader import download
from storage.index import append_index


# ==================================================
# HELPERS
# ==================================================

NON_HTML_EXTS = (
    ".xml", ".pdf", ".zip",
    ".doc", ".docx",
    ".xls", ".xlsx",
)

def is_html_page(url: str) -> bool:
    return not url.lower().endswith(NON_HTML_EXTS)


def filter_pages_for_seed(pages: list[str], seed_url: str) -> list[str]:
    seed_host = urlparse(seed_url).hostname or ""
    return [
        p for p in pages
        if urlparse(p).hostname
        and urlparse(p).hostname.endswith(seed_host)
    ]


# ==================================================
# SEEDS
# ==================================================

SEEDS = [
    {
        "entidade": "EQT Prev",
        "seed": "https://eqtprev.com.br/index.php/demonstrativo-d-i/",
        "allowed_paths": []
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
        mode = cfg.get("mode")

        logger.info("=" * 60)
        logger.info(f"Iniciando entidade: {entidade}")
        logger.info(f"Seed: {seed_url}")

        # ==================================================
        # 🚨 POWER BI MODE (FORÇADO)
        # ==================================================
        if mode == "powerbi":
            logger.warning(
                f"[{entidade}] Seed marcada como POWER BI. "
                f"Pulando HTML crawler e indo direto para browser."
            )

            crawl_browser(
                seed_cfg=cfg,
                state=state,
                pages=[seed_url],
                downloader=download,
                storage=append_index,
                logger=logger
            )
            continue

        # ==================================================
        # 1️⃣ HTML FIRST
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
        # 1️⃣.5 SITEMAP (APENAS DESCOBERTA)
        # ==================================================
        if should_try_sitemap(stats):
            logger.warning(f"[{entidade}] HTML fraco. Tentando sitemap.")

            seed_base = get_base_domain(seed_url)

            sitemap_urls = discover_sitemap_urls(seed_url, logger)
            sitemap_urls = filter_sitemap_urls(
                sitemap_urls,
                seed_base_domain=seed_base,
                allowed_paths=cfg.get("allowed_paths", [])
            )

            # 🔥 FILTRO CRÍTICO: sitemap só fornece HTML
            sitemap_urls = [u for u in sitemap_urls if is_html_page(u)]

            new_pages = [
                u for u in sitemap_urls
                if u not in state.visited_pages
            ]

            if new_pages:
                logger.warning(
                    f"[{entidade}] Sitemap adicionou {len(new_pages)} novas páginas."
                )

                for u in new_pages:
                    state.visited_pages.add(u)

                stats = crawl(
                    session=session,
                    seed_cfg=cfg,
                    state=state,
                    downloader=download,
                    storage=append_index,
                    logger=logger
                )
            else:
                logger.info(f"[{entidade}] Sitemap não trouxe páginas úteis.")

        # ==================================================
        # 2️⃣ BROWSER FALLBACK (EXECUÇÃO REAL)
        # ==================================================
        if should_escalate(stats):
            all_pages = list(state.visited_pages)

            pages = [
                p for p in filter_pages_for_seed(all_pages, seed_url)
                if is_html_page(p)
            ]

            logger.warning(
                f"[{entidade}] HTML insuficiente "
                f"(pages={stats['visited_pages']}, pdfs={stats['found_pdfs']}). "
                f"Usando browser fallback com {len(pages)} páginas."
            )

            if not pages:
                logger.warning(
                    f"[{entidade}] Nenhuma página HTML válida para fallback."
                )
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
