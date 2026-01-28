from pathlib import Path
from datetime import datetime
from storage.index import append_index


BASE_DIR = Path("data")


def store(
    *,
    entidade: str,
    source_page: str,
    kind: str,                 # "pdf" | "table" | "csv" | "png"
    content,
    meta: dict | None = None
):
    meta = meta or {}
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    entidade_dir = BASE_DIR / entidade
    entidade_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================
    # PDF / BINÁRIO
    # =====================================================
    if kind == "pdf":
        out_dir = entidade_dir / "pdfs"
        out_dir.mkdir(exist_ok=True)

        fname = meta.get("filename") or f"{ts}.pdf"
        path = out_dir / fname

        with open(path, "wb") as f:
            f.write(content)

        append_index({
            "entidade": entidade,
            "kind": "pdf",
            "file": str(path),
            "source_page": source_page,
            "meta": meta
        })

    # =====================================================
    # TABELA (JSON)
    # =====================================================
    elif kind == "table":
        out_dir = entidade_dir / "tables"
        out_dir.mkdir(exist_ok=True)

        fname = f"{ts}.json"
        path = out_dir / fname

        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        append_index({
            "entidade": entidade,
            "kind": "table",
            "file": str(path),
            "source_page": source_page,
            "meta": meta
        })

    # =====================================================
    # CSV (Power BI)
    # =====================================================
    elif kind == "csv":
        out_dir = entidade_dir / "tables"
        out_dir.mkdir(exist_ok=True)

        fname = meta.get("filename") or f"{ts}.csv"
        path = out_dir / fname

        with open(path, "wb") as f:
            f.write(content)

        append_index({
            "entidade": entidade,
            "kind": "csv",
            "file": str(path),
            "source_page": source_page,
            "meta": meta
        })

    # =====================================================
    # PNG (SCREENSHOT POWER BI)
    # =====================================================
    elif kind == "png":
        out_dir = entidade_dir / "images"
        out_dir.mkdir(exist_ok=True)

        fname = meta.get("filename") or f"{ts}.png"
        path = out_dir / fname

        with open(path, "wb") as f:
            f.write(content)

        append_index({
            "entidade": entidade,
            "kind": "png",
            "file": str(path),
            "source_page": source_page,
            "meta": meta
        })

    else:
        raise ValueError(f"Tipo de storage desconhecido: {kind}")
