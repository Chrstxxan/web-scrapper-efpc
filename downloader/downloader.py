'''
modulo que cuida do download dos arquivos
'''
import hashlib
import re
import time
import requests
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime
from config import FILES_DIR


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name).lower()

def download(
    session,
    url,
    state,
    storage,
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

        last_exc = None

        for attempt in range(3):
            try:
                r = session.get(url, timeout=40)
                r.raise_for_status()
                content = r.content
                break

            except requests.HTTPError as e:
                last_exc = e
                if r.status_code in (429, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                raise

            except Exception as e:
                last_exc = e
                time.sleep(2)

        else:
            state.save_failed(url)
            raise last_exc

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
    dest.write_bytes(content)

    # =========================================================
    # PERSISTÊNCIA DE ESTADO
    # =========================================================
    state.save_hash(h)
    state.save_visited_file(url)

    storage({
        "file": filename,
        "original_name": original,
        "hash": h,
        "hash_algo": "sha256",
        "url": url,
        "source_page": source_page,
        "anchor_text": anchor_text,
        "detected_year": detected_year,
        "downloaded_at": datetime.utcnow().isoformat(),
        "size_bytes": len(content),
        "entidade": entidade,
    })
