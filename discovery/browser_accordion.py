# discovery/browser_accordion.py
import re
import requests
from playwright.sync_api import sync_playwright

KEYWORDS = [
    "balancete",
    "demonstrativo",
    "investimento",
    "orçamento",
    "receita",
    "despesa",
    "contábil",
    "atuarial",
]

MIN_YEAR = 2022


def crawl_browser_accordion(seed_cfg, state, downloader, storage, logger):
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    seed = seed_cfg["seed"]

    session = requests.Session()

    with sync_playwright() as p:
        logger.warning(f"[{entidade}] Browser ACCORDION iniciado")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 🔹 captura PDFs via XHR / fetch / inline
        def handle_response(response):
            ct = response.headers.get("content-type", "").lower()
            if "pdf" not in ct:
                return

            try:
                content = response.body()
            except Exception:
                return

            pdf_url = response.url

            logger.info(f"[{entidade}] PDF capturado via browser: {pdf_url}")

            downloader(
                session=session,
                url=pdf_url,
                state=state,
                storage=storage,
                source_page=seed,
                anchor_text="browser_accordion",
                detected_year=None,
                entidade=entidade,
                content_override=content,
            )

        page.on("response", handle_response)

        page.goto(seed, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 🔹 encontra elementos que parecem anos
        year_elements = []
        for el in page.query_selector_all("button, div, a, span"):
            try:
                txt = (el.inner_text() or "").strip()
            except Exception:
                continue

            if re.fullmatch(r"20\d{2}", txt):
                year_elements.append((int(txt), el))

        year_elements.sort(reverse=True)

        logger.info(f"[{entidade}] Anos detectados: {[y for y, _ in year_elements]}")

        for year, year_el in year_elements:
            if year < MIN_YEAR:
                continue

            logger.info(f"[{entidade}] Expandindo ano {year}")

            try:
                year_el.scroll_into_view_if_needed()
                year_el.click()
            except Exception:
                continue

            page.wait_for_timeout(2000)

            # 🔹 dentro do ano, clicar em itens relevantes
            for el in page.query_selector_all("a, button"):
                try:
                    txt = (el.inner_text() or "").lower()
                except Exception:
                    continue

                if not any(k in txt for k in KEYWORDS):
                    continue

                try:
                    el.scroll_into_view_if_needed()
                    el.click()
                    page.wait_for_timeout(1500)
                except Exception:
                    continue

        page.wait_for_timeout(3000)
        browser.close()

        logger.warning(f"[{entidade}] Browser ACCORDION finalizado")
