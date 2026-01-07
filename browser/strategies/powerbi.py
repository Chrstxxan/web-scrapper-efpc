# browser/strategies/powerbi.py
# =========================================================
# Power BI Strategy Router
# =========================================================

import time
from urllib.parse import urlparse

from browser.strategies.powerbi_sites import petros


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _is_powerbi_page(page) -> bool:
    for frame in page.frames:
        if not frame.url:
            continue
        u = frame.url.lower()
        if (
            "powerbi" in u
            or "analysis.windows.net" in u
        ):
            return True
    return False


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# ---------------------------------------------------------
# FALLBACK GENÉRICO
# ---------------------------------------------------------

def _generic_powerbi_extract(page):
    time.sleep(5)
    return []


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def extract_powerbi_tables(page):
    """
    Retorna:
    [
      {
        "filename": str,
        "csv_bytes": bytes
      }
    ]
    """

    if not _is_powerbi_page(page):
        return []

    domain = _get_domain(page.url)

    # =====================================================
    # PETROS
    # =====================================================

    if domain.endswith("petros.com.br"):
        try:
            return petros.extract(page)
        except Exception as e:
            print(f"[POWERBI][PETROS] Erro: {e}")
            return []

    # =====================================================
    # FALLBACK
    # =====================================================

    return _generic_powerbi_extract(page)
