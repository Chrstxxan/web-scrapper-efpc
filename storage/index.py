'''
modulo que cria a parte de metadata
'''
import json
from pathlib import Path
from datetime import datetime

INDEX_PATH = Path("data/index.jsonl")

def append_index(meta: dict):
    meta["indexed_at"] = datetime.utcnow().isoformat()

    with open(INDEX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
