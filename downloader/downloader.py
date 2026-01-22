'''
modulo que cuida do download dos arquivos
'''
import hashlib
import re
import time
import requests
from requests.exceptions import SSLError
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime
from config import FILES_DIR
from config import MIN_YEAR
from storage.writer import store


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name).lower()


def download(
    session,
    url,
    state,
    source_page,
    anchor_text,
    detected_year,
    entidade: str | None = None,
    content_override: bytes | None = None
):

    # =========================================================
    # DEDUPE POR URL
    # =========================================================
    if url in state.visited_files:
        return

    # =========================================================
    # 🔥 FILTRO FINAL DE ANO (REGRA ABSOLUTA)
    # =========================================================
    year = detected_year

    # tenta inferir o ano se não veio pronto
    if year is None:
        candidates = f"{anchor_text or ''} {url}"
        matches = re.findall(r"(20\d{2})", candidates)
        if matches:
            year = max(int(y) for y in matches)

    # bloqueio duro
    if year is not None and year < MIN_YEAR:
        state.save_failed(url)
        return
    
    # =========================================================
    # OBTENÇÃO DO CONTEÚDO
    # =========================================================
    if content_override is not None:
        # conteúdo vindo do Playwright
        content = content_override

    else:
        if session is None:
            raise RuntimeError(
                "Downloader precisa de uma session válida "
                "quando não há content_override"
            )

        for attempt in range(3):
            try:
                try:
                    r = session.get(url, timeout=40)
                except SSLError:
                    # 🔥 PATCH: retry automático sem verificação SSL
                    r = session.get(url, timeout=40, verify=False)

                r.raise_for_status()
                content = r.content
                break

            except requests.HTTPError as e:
                last_exc = e
                status = e.response.status_code if e.response else None

                # erros comuns em sites institucionais
                if status in (404, 403):
                    state.save_failed(url)
                    return  # 🔹 não derruba o crawler

                if status in (429, 503):
                    time.sleep(3 * (attempt + 1))
                    continue

                state.save_failed(url)
                return

            except Exception as e:
                last_exc = e
                time.sleep(2)

        else:
            state.save_failed(url)
            return

    # =========================================================
    # DEDUPE POR HASH
    # =========================================================
    h = sha256(content)
    if h in state.hashes:
        return

    # =========================================================
    # NOME ORIGINAL
    # =========================================================
    parsed = urlparse(url)

    if parsed.scheme == "browser":
        original = sanitize(parsed.path)
    else:
        original = sanitize(Path(unquote(parsed.path)).name)

    base_dir = FILES_DIR

    if entidade:
        safe_entidade = sanitize(entidade)
        base_dir = FILES_DIR / safe_entidade

    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{h}__{original}"
    dest = base_dir / filename
    print(f"[DOWNLOADER] arquivo gravado -> {dest.resolve()}")
    dest.write_bytes(content)

    # =========================================================
    # PERSISTÊNCIA DE ESTADO
    # =========================================================
    state.save_hash(h)
    state.save_visited_file(url)

    store(
    entidade=entidade,
    source_page=source_page,
    kind="pdf",
    content=content,
    meta={
        "filename": filename,
        "original_name": original,
        "hash": h,
        "hash_algo": "sha256",
        "url": url,
        "anchor_text": anchor_text,
        "detected_year": detected_year,
        "downloaded_at": datetime.utcnow().isoformat(),
        "size_bytes": len(content),
    },
)

