"""
Browser interactive scraper
- Navbar
- Accordion por ano
- Captura real de PDFs
"""
from playwright.sync_api import sync_playwright
import re
from config import MIN_YEAR
from urllib.parse import urlparse


YEAR_RE = re.compile(r"20\d{2}")

def crawl_browser_interactive(
    seed_cfg,
    state,
    downloader,
    storage,
    logger,
):
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    seed_url = seed_cfg["seed"]

    logger.warning(f"[{entidade}] Iniciando browser INTERACTIVE")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ===============================
        # CAPTURA DE PDF (qualquer forma)
        # ===============================
        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                if "pdf" not in ct.lower():
                    return

                content = resp.body()
                url = resp.url

                if url in state.visited_files:
                    return

                logger.info(f"[{entidade}] PDF capturado via browser: {url}")

                downloader(
                    session=None,
                    url=url,
                    content_override=content,
                    state=state,
                    source_page=page.url,
                    anchor_text="browser_interactive",
                    detected_year=None,
                    entidade=entidade,
                )
            except Exception as e:
                logger.error(f"[{entidade}] Erro ao capturar PDF: {e}")

        page.on("response", on_response)

        # ===============================
        # ABERTURA DA PÁGINA
        # ===============================
        page.goto(seed_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # ===============================
        # NAVBAR — clique semântico
        # ===============================
        NAV_TARGETS = [
            "econômico",
            "financeiro",
            "investimentos",
            "demonstrações",
            "contábeis",
        ]

        for txt in NAV_TARGETS:
            try:
                el = page.get_by_text(txt, exact=False).first
                el.click(timeout=3000)
                page.wait_for_timeout(1200)
            except Exception:
                continue

        # ===============================
        # EXPANSÃO DE ANOS
        # ===============================
        year_buttons = page.query_selector_all("text=/20\\d{2}/")

        for btn in year_buttons:
            try:
                label = btn.inner_text().strip()
                if not YEAR_RE.fullmatch(label):
                    continue

                year = int(label)
                if year < MIN_YEAR:
                    continue

                btn.click()
                page.wait_for_timeout(1200)

            except Exception:
                continue

        # ===============================
        # CLIQUE EM ÍCONES DE PDF
        # ===============================
        for el in page.query_selector_all("a, button"):
            try:
                txt = (el.inner_text() or "").lower()
                if "pdf" in txt or "download" in txt:
                    el.click()
                    page.wait_for_timeout(800)
            except Exception:
                continue

        page.wait_for_timeout(3000)
        browser.close()

        logger.warning(f"[{entidade}] Browser INTERACTIVE finalizado")