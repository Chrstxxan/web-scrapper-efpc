'''
modulo que faz a navegacao nos sites (tem filtragem aqui tambem)
'''
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import FILE_EXTENSIONS, REQUEST_DELAY, KEYWORDS, MIN_YEAR
from discovery.heuristics import is_relevant, extract_year


def crawl(session, seed_cfg, state, downloader, storage, logger):
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    seed_url = seed_cfg["seed"]
    allowed_paths = seed_cfg.get("allowed_paths", [])

    queue = [seed_url]

    logger.info(f"[{entidade}] URLs iniciais na fila: 1")

    while queue:
        url = queue.pop(0)
        state.save_queue(queue)

        if url in state.visited_pages:
            continue

        logger.info(f"[{entidade}] Visitando: {url}")
        state.save_visited_page(url)

        try:
            r = session.get(url, timeout=20)
            if "text/html" not in r.headers.get("Content-Type", ""):
                continue
        except Exception as e:
            logger.error(f"[{entidade}] Erro ao acessar {url} | {e}")
            state.save_failed(url)
            continue

        soup = BeautifulSoup(r.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"].strip())
            text = a.get_text(strip=True)

            parsed = urlparse(href)

            # 🔹 ignora fragmentos (#)
            if parsed.fragment:
                continue

            # 🔹 escopo por entidade (ESSENCIAL)
            if allowed_paths:
                if not any(parsed.path.startswith(p) for p in allowed_paths):
                    continue

            # 📄 DOCUMENTO
            if href.lower().endswith(FILE_EXTENSIONS):
                if not is_relevant(text, href, KEYWORDS):
                    continue

                year = extract_year(f"{text} {href}")

                # 📅 REGRA DE DATA (a que você definiu)
                if year is not None and year < MIN_YEAR:
                    logger.info(
                        f"[{entidade}] Ignorado por data ({year} < {MIN_YEAR}): {href}"
                    )
                    continue

                downloader(
                    session=session,
                    url=href,
                    state=state,
                    storage=storage,
                    source_page=url,
                    anchor_text=text,
                    detected_year=year
                )

            # 🌐 PÁGINA HTML
            else:
                if href not in state.visited_pages:
                    queue.append(href)

        time.sleep(REQUEST_DELAY)

    logger.info(f"[{entidade}] Fila esgotada.")
