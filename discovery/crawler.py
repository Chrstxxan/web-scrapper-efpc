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

    # ===============================
    # STATS PARA DECISÃO DE FALLBACK
    # ===============================
    stats = {
        "visited_pages": 0,
        "found_pdfs": 0,
        "js_signals": False,
    }

    logger.info(f"[{entidade}] URLs iniciais na fila: 1")

    while queue:
        url = queue.pop(0)
        state.save_queue(queue)

        if url in state.visited_pages:
            continue

        logger.info(f"[{entidade}] Visitando: {url}")
        state.save_visited_page(url, entidade)
        stats["visited_pages"] += 1

        try:
            r = session.get(url, timeout=20)
            if "text/html" not in r.headers.get("Content-Type", ""):
                continue
        except Exception as e:
            logger.error(f"[{entidade}] Erro ao acessar {url} | {e}")
            state.save_failed(url)
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # 🔹 heurística simples: presença forte de JS
        if soup.find("script"):
            stats["js_signals"] = True

        # =========================================================
        # 1. LINKS <a href="">
        # =========================================================
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"].strip())
            text = a.get_text(strip=True)

            parsed = urlparse(href)

            # ignora fragmentos (#)
            if parsed.fragment:
                continue

            # escopo por entidade
            if allowed_paths:
                if not any(parsed.path.startswith(p) for p in allowed_paths):
                    continue

            # ---------------- DOCUMENTO ----------------
            if href.lower().endswith(FILE_EXTENSIONS):

                # 🟢 PDFs óbvios (WordPress, uploads, etc)
                is_obvious_doc = (
                    "/wp-content/uploads/" in href.lower()
                    or "/uploads/" in href.lower()
                )

                if not is_obvious_doc:
                    if not is_relevant(text, href, KEYWORDS):
                        continue

                year = extract_year(f"{text} {href}")

                if year is not None and year < MIN_YEAR:
                    logger.info(
                        f"[{entidade}] Ignorado por data ({year} < {MIN_YEAR}): {href}"
                    )
                    continue

                stats["found_pdfs"] += 1

                downloader(
                    session=session,
                    url=href,
                    state=state,
                    storage=storage,
                    source_page=url,
                    anchor_text=text,
                    detected_year=year,
                    entidade=entidade
                )

            # ---------------- HTML ----------------
            else:
                if href not in state.visited_pages and href not in queue:
                    queue.append(href)

        # =========================================================
        # 2. IFRAMES / FRAMES (sites antigos, AEROS etc)
        # =========================================================
        for frame in soup.find_all(["iframe", "frame"], src=True):
            frame_url = urljoin(url, frame["src"].strip())
            parsed = urlparse(frame_url)

            if parsed.fragment:
                continue

            if allowed_paths:
                if not any(parsed.path.startswith(p) for p in allowed_paths):
                    continue

            if frame_url not in state.visited_pages and frame_url not in queue:
                logger.debug(
                    f"[{entidade}] iframe encontrado: {frame_url}"
                )
                queue.append(frame_url)

        # =========================================================
        # 3. PDFs escondidos em HTML / JS / data-attrs
        # =========================================================
        for node in soup.find_all(string=True):
            if not node:
                continue

            raw = node.strip()
            if ".pdf" not in raw.lower():
                continue

            parts = [p for p in raw.split() if ".pdf" in p.lower()]
            for part in parts:
                if not part.lower().endswith(".pdf"):
                    continue

                pdf_url = urljoin(url, part)
                parsed = urlparse(pdf_url)

                if parsed.fragment:
                    continue

                if allowed_paths:
                    if not any(parsed.path.startswith(p) for p in allowed_paths):
                        continue

                year = extract_year(pdf_url)

                if year is not None and year < MIN_YEAR:
                    continue

                if pdf_url not in state.visited_files:
                    stats["found_pdfs"] += 1

                    logger.info(
                        f"[{entidade}] PDF detectado via HTML bruto: {pdf_url}"
                    )

                    downloader(
                        session=session,
                        url=href,
                        state=state,
                        storage=storage,
                        source_page=url,
                        anchor_text=text,
                        detected_year=year,
                        entidade=entidade
                    )

        time.sleep(REQUEST_DELAY)

    logger.info(
        f"[{entidade}] Fila esgotada | "
        f"pages={stats['visited_pages']} "
        f"pdfs={stats['found_pdfs']} "
        f"js={stats['js_signals']}"
    )

    return stats
