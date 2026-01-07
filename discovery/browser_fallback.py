"""
modulo que controla o fallback relacionado a utilizacao de browser no scrapping
"""

import os
import re
import time
import threading
import requests
from urllib.parse import urljoin, urlparse
from browser.strategy_router import run_strategies
from storage.writer import store
from discovery.patterns import detect_patterns

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# =========================================================
# CONFIG
# =========================================================
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"D:\playwright-browsers"

MAX_PAGES = 10
PAGE_TIMEOUT_MS = 20000
HARD_PAGE_BUDGET_SEC = 25


def infer_year(text: str | None):
    if not text:
        return None
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else None


def crawl_browser(seed_cfg, state, pages, downloader, storage, logger):

    seed = seed_cfg["seed"]
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    seed_domain = urlparse(seed).hostname or ""

    session = requests.Session()

    with sync_playwright() as p:
        logger.warning(f"[{entidade}] Iniciando Playwright (STRONG MODE)")

        try:
            browser = p.chromium.launch(headless=True, timeout=30000)
        except PlaywrightTimeout:
            logger.error(f"[{entidade}] Timeout ao iniciar Chromium")
            return

        logger.warning(f"[{entidade}] Chromium iniciado")

        # 🔧 contexto correto (downloads + popups)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # =========================================================
        # 📥 DOWNLOAD EVENT (nativo)
        # =========================================================
        def handle_download(download):
            try:
                path = download.path()
                filename = download.suggested_filename
                content = path.read_bytes()

                logger.info(
                    f"[{entidade}] Download capturado via browser: {filename}"
                )

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=content,
                    meta={
                        "filename": filename,
                        "year": infer_year(filename),
                        "origin": "dom_visible"
                    }
                )
            except Exception as e:
                logger.error(
                    f"[{entidade}] Erro ao processar download via browser: {e}"
                )

        page.on("download", handle_download)

        # =========================================================
        # 📡 XHR / FETCH PDF
        # =========================================================
        def handle_response(response):
            try:
                ct = response.headers.get("content-type", "").lower()
                if "pdf" not in ct:
                    return

                pdf_url = response.url
                if pdf_url in state.visited_files:
                    return

                body = response.body()
                if not body or len(body) < 5000:
                    return

                logger.info(
                    f"[{entidade}] PDF capturado via XHR/fetch: {pdf_url}"
                )

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=body,
                    meta={
                        "url": pdf_url,
                        "year": infer_year(pdf_url),
                        "origin": "xhr"
                    }
                )
            except Exception:
                pass

        page.on("response", handle_response)

        # =========================================================
        # 🪟 POPUP / NOVA ABA (window.open → PDF)
        # =========================================================
        def handle_popup(popup):
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=10000)
                pdf_url = popup.url

                if not pdf_url.lower().endswith(".pdf"):
                    return

                if pdf_url in state.visited_files:
                    popup.close()
                    return

                logger.info(
                    f"[{entidade}] PDF capturado via nova aba: {pdf_url}"
                )

                r = session.get(pdf_url, timeout=20)
                if r.ok and r.content:
                    store(
                        entidade=entidade,
                        source_page=page.url,
                        kind="pdf",
                        content=r.content,
                        meta={
                            "url": pdf_url,
                            "year": infer_year(pdf_url),
                            "origin": "popup"
                        }
                    )

                popup.close()

            except Exception as e:
                logger.debug(
                    f"[{entidade}] Erro ao processar popup PDF: {e}"
                )

        page.on("popup", handle_popup)

        # =========================================================
        # 🚀 LOOP PRINCIPAL
        # =========================================================
        logger.warning(
            f"[{entidade}] Usando browser fallback STRONG "
            f"({len(pages)} páginas descobertas)"
        )

        for i, url in enumerate(pages[:MAX_PAGES]):
            if url in state.visited_pages:
                continue

            logger.info(
                f"[{entidade}] Browser visitando ({i+1}/{MAX_PAGES}): {url}"
            )

            start_time = time.time()

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT_MS
                )
            except PlaywrightTimeout:
                continue

            # =====================================================
            # ⏳ ESPERA REAL PARA POWER BI / IFRAMES DINÂMICOS
            # =====================================================
            try:
                page.wait_for_selector(
                    "iframe, div[role='grid'], canvas",
                    timeout=20000
                )
                logger.info(f"[{entidade}] Power BI / iframe detectado")
            except PlaywrightTimeout:
                logger.warning(f"[{entidade}] Nenhum Power BI detectado (seguindo)")

            try:
                page.wait_for_selector(
                    "a, button, [role=button]",
                    timeout=5000
                )
            except PlaywrightTimeout:
                pass

            # ⛔ corte duro ANTES das estratégias
            if time.time() - start_time > HARD_PAGE_BUDGET_SEC:
                logger.warning(f"[{entidade}] Budget excedido antes das estratégias")
                continue

            # =====================================================
            # 🧠 DETECÇÃO DE PADRÕES + ESTRATÉGIAS AUTOMÁTICAS
            # =====================================================
            try:
                patterns = detect_patterns(page)
                logger.warning(f"[{entidade}] PATTERNS DETECTADOS: {patterns}")

                tables = run_strategies(page, logger)

                for idx, item in enumerate(tables):

                    # 🖼️ Power BI Screenshot (PNG)
                    if isinstance(item, dict) and item.get("__kind__") == "png":
                        store(
                            entidade=entidade,
                            source_page=page.url,
                            kind="png",
                            content=item["__bytes__"],
                            meta={
                                "filename": item.get("__filename__"),
                                "strategy": "powerbi_screenshot",
                                "index": idx
                            }
                        )

                    # 🔥 Power BI exporta CSV
                    elif isinstance(item, dict) and "csv_bytes" in item:
                        store(
                            entidade=entidade,
                            source_page=page.url,
                            kind="csv",
                            content=item["csv_bytes"],
                            meta={
                                "filename": item.get("filename"),
                                "strategy": "powerbi",
                                "index": idx
                            }
                        )

                    # 🔹 Fluxo antigo (JSON)
                    else:
                        store(
                            entidade=entidade,
                            source_page=page.url,
                            kind="table",
                            content=item,
                            meta={
                                "strategy": "auto_detect",
                                "index": idx
                            }
                        )

            except Exception as e:
                logger.debug(f"[{entidade}] Erro ao rodar estratégias: {e}")

            if time.time() - start_time > HARD_PAGE_BUDGET_SEC:
                continue

            # =====================================================
            # EXPANDIR ACCORDIONS
            # =====================================================
            page.evaluate("""
            () => {
                document.querySelectorAll('button, a, div, span').forEach(el => {
                    const t = (el.innerText || '').trim();
                    if (
                        /^20\\d{2}$/.test(t) ||
                        t === '+' ||
                        t === '▸' ||
                        t.toLowerCase().includes('ver')
                    ) {
                        try { el.click(); } catch(e) {}
                    }
                });
            }
            """)

            # =====================================================
            # 🔥 PATCH CRÍTICO — CLIQUE EM BOTÕES DE DOWNLOAD JS
            # =====================================================
            try:
                buttons = page.locator("button:visible, a:visible")
                for i in range(buttons.count()):
                    el = buttons.nth(i)
                    text = (el.inner_text() or "").lower()

                    if "download" in text or "baixar" in text or "visualizar" in text:
                        logger.info(
                            f"[{entidade}] Clique forçado em botão de download JS"
                        )
                        try:
                            el.click()
                            page.wait_for_timeout(800)
                        except Exception:
                            pass
            except Exception:
                pass

            # =====================================================
            # PDFs VISÍVEIS NO DOM
            # =====================================================
            for a in page.locator("a:visible").all():
                href = a.get_attribute("href")
                if not href or not href.lower().endswith(".pdf"):
                    continue

                pdf_url = urljoin(url, href)
                if pdf_url in state.visited_files:
                    continue

                r = session.get(pdf_url, timeout=20)
                if not r.ok or not r.content:
                    continue

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=r.content,
                    meta={
                        "url": pdf_url,
                        "year": infer_year(pdf_url),
                        "origin": "dom_visible"
                    }
                )

        logger.warning(
            f"[{entidade}] Browser fallback STRONG finalizado"
        )

        browser.close()
