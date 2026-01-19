"""
modulo que controla o fallback relacionado a utilizacao de browser no scrapping
"""

import os
import re
import time
import requests
from urllib.parse import urljoin
from requests.exceptions import SSLError

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from browser.strategy_router import run_strategies
from storage.writer import store
from discovery.patterns import detect_patterns


# =========================================================
# CONFIG
# =========================================================
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"D:\playwright-browsers"

MAX_PAGES = 10
PAGE_TIMEOUT_MS = 20000
HARD_PAGE_BUDGET_SEC = 25


# =========================================================
# HELPERS
# =========================================================
def infer_year(text: str | None):
    if not text:
        return None
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else None


NON_HTML_EXTS = (".xml", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx")


def is_html_page(url: str) -> bool:
    return not url.lower().endswith(NON_HTML_EXTS)


# =========================================================
# MAIN
# =========================================================
def crawl_browser(seed_cfg, state, pages, downloader, storage, logger):

    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    session = requests.Session()

    with sync_playwright() as p:
        logger.warning(f"[{entidade}] Iniciando Playwright (STRONG MODE)")

        try:
            browser = p.chromium.launch(headless=True, timeout=30000)
        except PlaywrightTimeout:
            logger.error(f"[{entidade}] Timeout ao iniciar Chromium")
            return

        logger.warning(f"[{entidade}] Chromium iniciado")

        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # =========================================================
        # 📥 DOWNLOAD EVENT
        # =========================================================
        def handle_download(download):
            try:
                path = download.path()
                filename = download.suggested_filename
                content = path.read_bytes()

                logger.info(f"[{entidade}] Download capturado via browser: {filename}")

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=content,
                    meta={
                        "filename": filename,
                        "year": infer_year(filename),
                        "origin": "download_event",
                    },
                )
            except Exception as e:
                logger.error(f"[{entidade}] Erro ao processar download: {e}")

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

                logger.info(f"[{entidade}] PDF capturado via XHR: {pdf_url}")

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=body,
                    meta={
                        "url": pdf_url,
                        "year": infer_year(pdf_url),
                        "origin": "xhr",
                    },
                )
            except Exception:
                pass

        page.on("response", handle_response)

        # =========================================================
        # 🪟 POPUP / NOVA ABA
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

                logger.info(f"[{entidade}] PDF capturado via popup: {pdf_url}")

                try:
                    r = session.get(pdf_url, timeout=20)
                except SSLError:
                    r = session.get(pdf_url, timeout=20, verify=False)

                if r.ok and r.content:
                    store(
                        entidade=entidade,
                        source_page=page.url,
                        kind="pdf",
                        content=r.content,
                        meta={
                            "url": pdf_url,
                            "year": infer_year(pdf_url),
                            "origin": "popup",
                        },
                    )

                popup.close()
            except Exception:
                pass

        page.on("popup", handle_popup)

        # =========================================================
        # 🚀 LOOP PRINCIPAL
        # =========================================================
        logger.warning(
            f"[{entidade}] Usando browser fallback STRONG ({len(pages)} páginas)"
        )

        for i, url in enumerate(pages[:MAX_PAGES]):

            # =====================================================
            # 🚫 PATCH — NÃO NAVEGAR EM URL DE DOWNLOAD
            # =====================================================
            low = url.lower()
            if any(
                x in low
                for x in [
                    ".pdf",
                    "/arquivo/",
                    "/download",
                    "/uploads/",
                    "file=",
                ]
            ):
                logger.info(
                    f"[{entidade}] URL é download direto, pulando browser: {url}"
                )
                continue

            # =====================================================
            # 🌐 FILTRO HTML (AGORA SÓ HTML DE VERDADE CHEGA AQUI)
            # =====================================================
            if not is_html_page(url):
                logger.info(f"[{entidade}] Ignorando URL não-HTML: {url}")
                continue

            logger.info(f"[{entidade}] Browser visitando ({i+1}/{MAX_PAGES}): {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            except PlaywrightTimeout:
                continue

            try:
                page.wait_for_selector("body", timeout=5000)
            except PlaywrightTimeout:
                pass

            # =====================================================
            # 🧭 PATCH — LOAD MORE / VER MAIS
            # =====================================================
            try:
                for _ in range(10):  # limite de segurança
                    btn = page.locator(
                        "button:has-text('Ver mais'), "
                        "a:has-text('Ver mais'), "
                        "button:has-text('Carregar'), "
                        "button:has-text('Load')"
                    )

                    if btn.count() == 0:
                        break

                    b = btn.first
                    if not b.is_visible():
                        break

                    logger.info(f"[{entidade}] Clicando em 'Ver mais'")
                    b.click()
                    page.wait_for_timeout(1200)
            except Exception:
                pass

            # =====================================================
            # 🧭 PATCH — ATIVAR TODAS AS TABS VISÍVEIS
            # =====================================================
            try:
                tabs = page.locator("ul.nav-tabs a, .nav-tabs a, [role='tab']")
                for t in range(tabs.count()):
                    tab = tabs.nth(t)
                    try:
                        if tab.is_visible():
                            logger.info(
                                f"[{entidade}] Ativando tab: {(tab.inner_text() or '').strip()}"
                            )
                            tab.click()
                            page.wait_for_timeout(800)
                    except Exception:
                        pass
            except Exception:
                pass

            # =====================================================
            # 🧠 PIPELINE DE EXTRAÇÃO (COM ROTEAMENTO MULTIPREV)
            # =====================================================
            try:
                patterns = detect_patterns(page)
                logger.warning(f"[{entidade}] PATTERNS DETECTADOS: {patterns}")

                def run_pipeline_for_plan(plano_nome):
                    items = run_strategies(page, logger)

                    for idx, item in enumerate(items):

                        # =====================================================
                        # 🖼️ PNG (Power BI / screenshots)
                        # =====================================================
                        if isinstance(item, dict) and item.get("__kind__") == "png":
                            store(
                                entidade=entidade,
                                source_page=page.url,
                                kind="png",
                                content=item["__bytes__"],
                                meta={
                                    "filename": item.get("__filename__"),
                                    "strategy": "powerbi",
                                    "plano": plano_nome,
                                    "index": idx,
                                },
                            )
                            continue

                        # =====================================================
                        # 📊 CSV (Power BI)
                        # =====================================================
                        if isinstance(item, dict) and "csv_bytes" in item:
                            store(
                                entidade=entidade,
                                source_page=page.url,
                                kind="csv",
                                content=item["csv_bytes"],
                                meta={
                                    "filename": item.get("filename"),
                                    "strategy": "powerbi",
                                    "plano": plano_nome,
                                    "index": idx,
                                },
                            )
                            continue

                        # =====================================================
                        # 🔗 QUALQUER ITEM COM URL → FAIL-OPEN CONTROLADO
                        # =====================================================
                        if isinstance(item, dict):

                            link = (
                                item.get("__url__")
                                or item.get("url")
                                or item.get("href")
                            )

                            if isinstance(link, str) and link.startswith("http"):

                                # ---------------------------------------------
                                # 🌐 HTML intermediário → volta para o browser
                                # ---------------------------------------------
                                if not link.lower().endswith(".pdf"):
                                    if link not in state.visited_pages:
                                        logger.info(
                                            f"[{entidade}] Enfileirando página intermediária: {link}"
                                        )
                                        state.pages.append(link)
                                    continue

                                # ---------------------------------------------
                                # 📄 PDF final → downloader
                                # ---------------------------------------------
                                downloader(
                                    session=session,
                                    url=link,
                                    state=state,
                                    storage=storage,
                                    source_page=page.url,
                                    anchor_text=f"plano:{plano_nome}"
                                    if plano_nome
                                    else "document_library",
                                    detected_year=infer_year(link),
                                    entidade=entidade,
                                )
                                continue

                        # =====================================================
                        # 📋 Fallback — tabelas / blobs desconhecidos
                        # =====================================================
                        store(
                            entidade=entidade,
                            source_page=page.url,
                            kind="table",
                            content=item,
                            meta={
                                "strategy": "auto_detect",
                                "plano": plano_nome,
                                "index": idx,
                            },
                        )

                run_pipeline_for_plan(plano_nome=None)

            except Exception as e:
                logger.debug(f"[{entidade}] Erro ao rodar pipeline: {e}")

            # =====================================================
            # EXPANSÕES E CLIQUES FINAIS
            # =====================================================
            if not patterns.has_document_library:
                page.evaluate(
                    """
                    () => {
                        document.querySelectorAll('button, a, div, span').forEach(el => {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (/^20\\d{2}$/.test(t) || t === '+' || t.includes('ver')) {
                                try { el.click(); } catch(e) {}
                            }
                        });
                    }
                    """
                )

                try:
                    buttons = page.locator("button:visible, a:visible")
                    for j in range(buttons.count()):
                        el = buttons.nth(j)
                        text = (el.inner_text() or "").lower()
                        if "download" in text or "baixar" in text or "visualizar" in text:
                            try:
                                el.click()
                                page.wait_for_timeout(800)
                            except Exception:
                                pass
                except Exception:
                    pass

            for a in page.locator("a:visible").all():
                href = a.get_attribute("href")
                if not href or not href.lower().endswith(".pdf"):
                    continue

                pdf_url = urljoin(url, href)
                if pdf_url in state.visited_files:
                    continue

                try:
                    r = session.get(pdf_url, timeout=20)
                except SSLError:
                    r = session.get(pdf_url, timeout=20, verify=False)

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
                        "origin": "dom_visible",
                    },
                )

        logger.warning(f"[{entidade}] Browser fallback STRONG finalizado")
        browser.close()
