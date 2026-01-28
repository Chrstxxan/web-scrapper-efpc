"""
modulo que controla o fallback relacionado a utilizacao de browser no scrapping
"""

import os
import re

import requests
from urllib.parse import urljoin, urlparse
from requests.exceptions import SSLError
import hashlib

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from browser.strategy_router import run_strategies
from storage.writer import store
from discovery.patterns import detect_patterns
from config import MIN_YEAR


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

def normalize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-. ]+", "_", name)
    return name[:200]

def short_hash(data: bytes, size=8) -> str:
    return hashlib.sha256(data).hexdigest()[:size]

# =========================================================
# MAIN
# =========================================================
def crawl_browser(seed_cfg, state, pages, downloader, storage, logger):

    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    session = requests.Session()

    # =====================================================
    # 🔒 SEED ANCHOR CONFIG (OPT-IN)
    # =====================================================
    lock_seed_scope = seed_cfg.get("lock_seed_scope", False)
    seed_anchor_path = seed_cfg.get("seed_anchor_path")

    if seed_anchor_path:
        seed_anchor_path = seed_anchor_path.lower().rstrip("/")


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
                content = path.read_bytes()

                original_name = download.suggested_filename or "arquivo.pdf"
                original_name = normalize_filename(original_name)

                h = short_hash(content)
                final_name = f"{h}__{original_name}"

                if download.url:
                    state.visited_files.add(download.url)

                logger.info(
                    f"[{entidade}] Download capturado via browser: {final_name}"
                )

                store(
                    entidade=entidade,
                    source_page=page.url,
                    kind="pdf",
                    content=content,
                    meta={
                        "filename": final_name,
                        "original_filename": original_name,
                        "year": infer_year(original_name),
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

                state.visited_files.add(pdf_url)

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

                    state.visited_files.add(pdf_url)

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

        seed_base_url = seed_cfg["seed"].rstrip("/")

        for i, url in enumerate(pages[:MAX_PAGES]):

            # =====================================================
            # 🔒 SEED ANCHOR — NÃO BLOQUEAR A PRIMEIRA PÁGINA
            # =====================================================
            if lock_seed_scope and seed_anchor_path:

                # ✅ sempre permitir a própria seed
                if url.rstrip("/") != seed_base_url:

                    path = urlparse(url).path.lower().rstrip("/")

                    if not path.startswith(seed_anchor_path):
                        logger.info(
                            f"[{entidade}] Browser fora do anchor, ignorando: {url}"
                        )
                        continue

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
            # 🔓 PATCH A — EXPANDIR TODOS OS ACCORDIONS (ANO / MÊS)
            # =====================================================
            try:
                accordion_buttons = page.locator(
                    "button[aria-expanded='false'], "
                    ".accordion-button.collapsed, "
                    "[role='button'][aria-expanded='false']"
                )

                for idx in range(accordion_buttons.count()):
                    btn = accordion_buttons.nth(idx)
                    try:
                        if btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(600)
                    except Exception:
                        pass
            except Exception:
                pass

            # =====================================================
            # 🧭 PATCH — LOAD MORE / VER MAIS (SMART)
            # =====================================================
            try:
                # 1️⃣ Se já existem PDFs visíveis, NÃO clicar
                existing_pdfs = page.locator("a[href*='.pdf' i]")
                if existing_pdfs.count() > 0:
                    logger.info(
                        f"[{entidade}] PDFs já visíveis ({existing_pdfs.count()}), ignorando 'Ver mais'"
                    )
                else:
                    for _ in range(5):  # limite de segurança menor
                        btn = page.locator(
                            "main button:has-text('Ver mais'), "
                            "article button:has-text('Ver mais'), "
                            "section button:has-text('Ver mais')"
                        )

                        if btn.count() == 0:
                            break

                        b = btn.first
                        if not b.is_visible():
                            break

                        # 2️⃣ Snapshot antes do clique
                        before = page.locator("a[href*='.pdf' i]").count()

                        logger.info(f"[{entidade}] Clicando em 'Ver mais' contextual")
                        b.click()
                        page.wait_for_timeout(1200)

                        # 3️⃣ Snapshot depois
                        after = page.locator("a[href*='.pdf' i]").count()

                        # 4️⃣ Se não liberou nada novo → para
                        if after <= before:
                            logger.info(
                                f"[{entidade}] 'Ver mais' não liberou novos PDFs, parando"
                            )
                            break

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
            # 🧭 PATCH — MENU LATERAL (SPA / SIDEBAR)
            # =====================================================
            try:
                # só tenta se ainda NÃO existem PDFs visíveis
                if page.locator("a[href*='.pdf' i]").count() == 0:

                    sidebar_links = page.locator("aside a:visible, nav a:visible")

                    for i in range(sidebar_links.count()):
                        el = sidebar_links.nth(i)
                        try:
                            text = (el.inner_text() or "").strip().lower()

                            if "demonstrativo de investimentos" in text:
                                logger.warning(
                                    f"[{entidade}] Ativando menu lateral SPA: {text}"
                                )
                                el.click()
                                page.wait_for_timeout(2000)
                                break

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

                    # =====================================================
                    # 📚 DOCUMENT LIBRARY — DISPARO VIA BROWSER + FALLBACK
                    # =====================================================
                    for item in items:
                        if not isinstance(item, dict):
                            continue

                        url = item.get("__url__") or item.get("url")
                        if not isinstance(url, str):
                            continue

                        if not url.lower().endswith(".pdf"):
                            continue

                        logger.info(f"[{entidade}] Disparando download (document_library): {url}")

                        # -------------------------------------------------
                        # 1️⃣ TENTATIVA PRINCIPAL — browser CONTROLADO
                        # -------------------------------------------------
                        try:
                            with page.expect_download(timeout=20000) as download_info:
                                page.evaluate("(url) => window.open(url, '_blank')", url)

                            download = download_info.value

                            path = download.path()
                            content = path.read_bytes()

                            original_name = (
                                download.suggested_filename
                                or url.split("/")[-1]
                                or "arquivo.pdf"
                            )
                            original_name = normalize_filename(original_name)

                            h = short_hash(content)
                            final_name = f"{h}__{original_name}"

                            store(
                                entidade=entidade,
                                source_page=page.url,
                                kind="pdf",
                                content=content,
                                meta={
                                    "filename": final_name,
                                    "original_filename": original_name,
                                    "url": url,
                                    "year": infer_year(original_name) or infer_year(url),
                                    "origin": "document_library_browser",
                                },
                            )

                            state.visited_files.add(url)

                            logger.info(
                                f"[{entidade}] Download concluído via browser controlado: {final_name}"
                            )

                            continue

                        except Exception as e:
                            logger.warning(
                                f"[{entidade}] Browser download falhou, usando fallback: {e}"
                            )

                        # -------------------------------------------------
                        # 2️⃣ FALLBACK — requests/downloader
                        # -------------------------------------------------
                        logger.info(f"[{entidade}] Fallback downloader (document_library): {url}")

                        downloader(
                            session=session,
                            url=url,
                            state=state,
                            source_page=page.url,
                            anchor_text="document_library",
                            detected_year=infer_year(url),
                            entidade=entidade,
                        )

                        # 🧘‍♂️ throttle leve entre downloads
                        page.wait_for_timeout(700)

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

                                if not link.lower().endswith(".pdf"):

                                    # =====================================================
                                    # 🔒 SEED ANCHOR — NÃO REENFILEIRAR FORA DO ESCOPO
                                    # =====================================================
                                    if lock_seed_scope and seed_anchor_path:
                                        path = urlparse(link).path.lower().rstrip("/")
                                        if not path.startswith(seed_anchor_path):
                                            logger.info(
                                                f"[{entidade}] Link fora do anchor ignorado: {link}"
                                            )
                                            continue

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
            if not patterns.has_document_library and patterns.has_popup_links:
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

            # =====================================================
            # 🔒 COLETAR HREFS VISÍVEIS (SNAPSHOT SEGURO)
            # =====================================================
            try:
                hrefs = page.eval_on_selector_all(
                    "a:visible",
                    "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
                )
            except Exception:
                hrefs = []

            for href in hrefs:
                if ".pdf" not in href.lower():
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

                year = infer_year(pdf_url)
                if year is not None and year < MIN_YEAR:
                    logger.info(
                        f"[{entidade}] Ignorado por data ({year} < {MIN_YEAR}): {pdf_url}"
                    )
                    continue

                downloader(
                    session=session,
                    url=pdf_url,
                    state=state,
                    source_page=page.url,
                    anchor_text="dom_visible",
                    detected_year=year,
                    entidade=entidade,
                )

                state.visited_files.add(pdf_url)

        logger.warning(f"[{entidade}] Browser fallback STRONG finalizado")
        browser.close()
