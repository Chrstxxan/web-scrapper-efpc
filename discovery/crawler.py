"""
módulo que faz a navegação nos sites (HTML-first)
"""
import time
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import (
    FILE_EXTENSIONS,
    REQUEST_DELAY,
    KEYWORDS,
    MIN_YEAR,
    MAX_CRAWL_DEPTH,
    PATH_INTEREST_HINTS,
)
from discovery.heuristics import is_relevant, extract_year
from discovery.domain_guard import (
    get_base_domain,
    is_external_page,
    is_blocked_domain,
)


def crawl(session, seed_cfg, state, downloader, storage, logger):
    entidade = seed_cfg.get("entidade", "DESCONHECIDA")
    seed_url = seed_cfg["seed"]
    allowed_paths = seed_cfg.get("allowed_paths", [])
    lock_seed_scope = seed_cfg.get("lock_seed_scope", False)

    seed_base_domain = get_base_domain(seed_url)
    seed_path = urlparse(seed_url).path.lower().rstrip("/")

    # fila com controle de profundidade
    queue = [(seed_url, 0)]

    stats = {
        "visited_pages": 0,
        "found_pdfs": 0,
        "js_signals": False,
        "accordion_years": False,
    }

    years_found = set()

    logger.info(f"[{entidade}] URLs iniciais na fila: 1")

    while queue:
        url, depth = queue.pop(0)
        state.save_queue([u for u, _ in queue])

        if url in state.visited_pages:
            continue

        if depth > MAX_CRAWL_DEPTH:
            continue

        logger.info(f"[{entidade}] Visitando: {url} (depth={depth})")

        # =========================================================
        # 🧩 CONTADORES POR PÁGINA
        # =========================================================
        valid_pdfs_found = 0
        ignored_pdfs_found = 0

        state.save_visited_page(url)
        stats["visited_pages"] += 1

        try:
            r = session.get(url, timeout=20)
            ct = r.headers.get("Content-Type", "")
            if "text/html" not in ct:
                continue
        except Exception as e:
            logger.error(f"[{entidade}] Erro ao acessar {url} | {e}")
            state.save_failed(url)
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # sinal simples de JS
        if soup.find("script"):
            stats["js_signals"] = True

        # detecção de accordion por ANO
        for txt in soup.stripped_strings:
            if re.fullmatch(r"20\d{2}", txt):
                years_found.add(int(txt))

        if len(years_found) >= 4:
            stats["accordion_years"] = True

        # =========================================================
        # 1. LINKS <a href="">
        # =========================================================
        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            href = urljoin(url, raw_href)
            text = a.get_text(strip=True)

            parsed = urlparse(href)
            path_lower = parsed.path.lower()
            # =====================================================
            # 🧹 FILTRO DE UI / COOKIES / POLÍTICAS (ANTI-LIXO)
            # =====================================================
            LOW_VALUE_HINTS = (
                "politica",
                "privacidade",
                "proteca",
                "lgpd",
                "termos",
                "uso",
                "cookie",
            )

            if any(h in path_lower for h in LOW_VALUE_HINTS):
                logger.debug(
                    f"[{entidade}] Link de política/cookie ignorado: {href}"
                )
                continue
            
            # texto do link também denuncia lixo
            text_lower = text.lower()
            if any(h in text_lower for h in LOW_VALUE_HINTS):
                logger.debug(
                    f"[{entidade}] Texto de link irrelevante ignorado: {text}"
                )
                continue

            if parsed.fragment:
                continue

            if is_blocked_domain(href):
                continue

            is_document = href.lower().endswith(FILE_EXTENSIONS)

            # HTML nunca sai do domínio
            if not is_document:
                if is_external_page(href, seed_base_domain):
                    continue

            # =====================================================
            # 🔒 SEED SCOPE LOCK (OPT-IN)
            # =====================================================
            if lock_seed_scope and not is_document:
                if seed_path and not path_lower.startswith(seed_path):
                    logger.debug(
                        f"[{entidade}] Seed lock ativo, ignorando fora do escopo: {href}"
                    )
                    continue

            # ---------------- DOCUMENTO ----------------
            if is_document:
                is_obvious_doc = (
                    "/wp-content/uploads/" in path_lower
                    or "/uploads/" in path_lower
                )

                if not is_obvious_doc:
                    if not is_relevant(text, href, KEYWORDS):
                        continue

                year = extract_year(f"{text} {href}")

                if year is not None and year < MIN_YEAR:
                    logger.info(
                        f"[{entidade}] Ignorado por data ({year} < {MIN_YEAR}): {href}"
                    )
                    ignored_pdfs_found += 1
                    state.visited_files.add(href)
                    continue

                stats["found_pdfs"] += 1
                valid_pdfs_found += 1
                state.visited_files.add(href)

                downloader(
                    session=session,
                    url=href,
                    state=state,
                    source_page=url,
                    anchor_text=text or "link",
                    detected_year=year,
                    entidade=entidade,
                )

            # ---------------- HTML ----------------
            else:
                is_interesting_path = any(h in path_lower for h in PATH_INTEREST_HINTS)

                if (
                    not is_interesting_path
                    and depth >= MAX_CRAWL_DEPTH
                    and not any(
                        k in path_lower
                        for k in (
                            "relatorio",
                            "documento",
                            "balancete",
                            "invest",
                            "transpar",
                            "pdf",
                            "download",
                            "arquivo",
                        )
                    )
                ):
                    continue

                if allowed_paths:
                    if not any(path_lower.startswith(p) for p in allowed_paths):
                        continue

                if href not in state.visited_pages and all(href != u for u, _ in queue):
                    queue.append((href, depth + 1))

        # =========================================================
        # 2. IFRAMES / FRAMES
        # =========================================================
        for frame in soup.find_all(["iframe", "frame"], src=True):
            frame_url = urljoin(url, frame["src"].strip())
            parsed = urlparse(frame_url)
            path_lower = parsed.path.lower()

            if parsed.fragment:
                continue

            if is_blocked_domain(frame_url):
                continue

            if is_external_page(frame_url, seed_base_domain):
                continue

            if lock_seed_scope:
                if seed_path and not path_lower.startswith(seed_path):
                    continue

            is_interesting_path = any(h in path_lower for h in PATH_INTEREST_HINTS)

            if (
                not is_interesting_path
                and depth >= MAX_CRAWL_DEPTH
                and not any(k in path_lower for k in ("pdf", "documento", "arquivo"))
            ):
                continue

            if allowed_paths:
                if not any(path_lower.startswith(p) for p in allowed_paths):
                    continue

            if frame_url not in state.visited_pages and all(
                frame_url != u for u, _ in queue
            ):
                queue.append((frame_url, depth + 1))

        # =========================================================
        # 3. PDFs embutidos em texto / JS
        # =========================================================
        for node in soup.find_all(string=True):
            raw = (node or "").strip()
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

                if is_blocked_domain(pdf_url):
                    continue

                year = extract_year(pdf_url)
                if year is not None and year < MIN_YEAR:
                    continue

                if pdf_url in state.visited_files:
                    continue

                stats["found_pdfs"] += 1
                valid_pdfs_found += 1
                state.visited_files.add(pdf_url)

                downloader(
                    session=session,
                    url=pdf_url,
                    state=state,
                    source_page=url,
                    anchor_text="detected_in_html",
                    detected_year=year,
                    entidade=entidade,
                )

        if valid_pdfs_found == 0 and ignored_pdfs_found > 0:
            logger.info(f"[{entidade}] Página exaurida (somente PDFs antigos): {url}")

        time.sleep(REQUEST_DELAY)

    logger.info(
        f"[{entidade}] Fila esgotada | "
        f"pages={stats['visited_pages']} "
        f"pdfs={stats['found_pdfs']} "
        f"js={stats['js_signals']} "
        f"accordion={stats['accordion_years']}"
    )

    return stats
