'''
modulo que cuida do download dos arquivos
'''
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime
from config import FILES_DIR

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name).lower()

def download(session, url, state, storage, source_page, anchor_text, detected_year):
    if url in state.visited_files:
        return

    r = session.get(url, timeout=40)
    r.raise_for_status()

    h = sha256(r.content)
    if h in state.hashes:
        return

    parsed = urlparse(url)
    original = sanitize(Path(unquote(parsed.path)).name)

    FILES_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{h}__{original}"
    dest = FILES_DIR / filename
    dest.write_bytes(r.content)

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
        "size_bytes": len(r.content)
    })
