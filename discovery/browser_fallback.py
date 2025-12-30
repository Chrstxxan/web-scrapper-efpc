'''
modulo que controla o fallback relacionado a utilizacao de browser no scrapping
'''
import os
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# caminho onde o playwright instala os browsers
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"D:\playwright-browsers"


def crawl_browser(seed_cfg, state, pages, downloader, storage, logger):
    seed = seed_cfg["seed"]
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")

    session = requests.Session()

    with sync_playwright() as p:
        logger.warning(f"[{entidade}] Iniciando Playwright")

        try:
            browser = p.chromium.launch(headless=True, timeout=30000)
        except PlaywrightTimeout:
            logger.error(f"[{entidade}] Timeout ao iniciar Chromium")
            return

        logger.warning(f"[{entidade}] Chromium iniciado")

        page = browser.new_page()

        # =========================================================
        # CAPTURA DE DOWNLOAD REAL (blob / js / GA style)
        # =========================================================
        def handle_download(download):
            try:
                path = download.path()
                filename = download.suggested_filename

                logger.info(
                    f"[{entidade}] Download capturado via browser: {filename}"
                )

                content = path.read_bytes()

                downloader(
                    session=None,
                    url=f"browser://{filename}",
                    state=state,
                    storage=storage,
                    source_page=seed,
                    anchor_text="browser_download_event",
                    detected_year=None,
                    entidade=entidade,
                    content_override=content
                )

            except Exception as e:
                logger.error(
                    f"[{entidade}] Erro ao processar download via browser: {e}"
                )

        page.on("download", handle_download)

        logger.warning(
            f"[{entidade}] Usando browser fallback "
            f"({len(pages)} páginas descobertas)"
        )

        MAX_PAGES = 15

        for i, url in enumerate(pages[:MAX_PAGES]):
            logger.info(
                f"[{entidade}] Browser visitando ({i+1}/{MAX_PAGES}): {url}"
            )

            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # 🔹 DISPARA POSSÍVEIS DOWNLOADS VIA JS
                page.evaluate("""
                () => {
                    const BLOCKLIST = [
                        'privacidade',
                        'privacy',
                        'cookies',
                        'lgpd',
                        'termos',
                        'terms'
                    ];

                    const candidates = Array.from(
                        document.querySelectorAll('a, button')
                    ).filter(el => {
                        const text = (el.innerText || '').toLowerCase();
                        const href = (el.href || '').toLowerCase();

                        if (BLOCKLIST.some(b => text.includes(b) || href.includes(b))) {
                            return false;
                        }

                        return true;
                    });

                    if (candidates.length > 0) {
                        candidates[0].click();
                        return true;
                    }

                    return false;
                }
                """)

                page.wait_for_timeout(3000)

            except Exception as e:
                logger.debug(
                    f"[{entidade}] Erro ao abrir {url}: {e}"
                )
                continue

        logger.warning(
            f"[{entidade}] Browser fallback finalizado "
            f"(paginas_visitadas={min(len(pages), MAX_PAGES)})"
        )

        browser.close()
