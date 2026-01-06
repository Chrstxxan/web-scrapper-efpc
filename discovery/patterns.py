# discovery/patterns.py

from dataclasses import dataclass
from playwright.sync_api import Page
import re


@dataclass
class PagePatterns:
    has_accordion_years: bool = False
    has_download_buttons: bool = False
    has_dropdown: bool = False
    has_table: bool = False
    has_popup_links: bool = False

    # 🔥 PATCH CRÍTICO
    is_powerbi: bool = False


def detect_patterns(page: Page) -> PagePatterns:
    patterns = PagePatterns()

    try:
        text = page.inner_text("body").lower()
    except Exception:
        text = ""

    html = ""
    try:
        html = page.content().lower()
    except Exception:
        pass

    # ======================================================
    # 🔹 ACCORDION POR ANO
    # ======================================================
    if re.search(r"\b20\d{2}\b", text):
        patterns.has_accordion_years = True

    # ======================================================
    # 🔹 BOTÕES DE DOWNLOAD
    # ======================================================
    if (
        page.locator("text=Download").count() > 0
        or page.locator("text=Baixar").count() > 0
        or page.locator("text=Visualizar").count() > 0
    ):
        patterns.has_download_buttons = True

    # ======================================================
    # 🔹 DROPDOWN
    # ======================================================
    if page.locator("select").count() > 0:
        patterns.has_dropdown = True

    # ======================================================
    # 🔹 TABELA HTML CLÁSSICA
    # ======================================================
    if page.locator("table").count() > 0:
        patterns.has_table = True

    # ======================================================
    # 🔹 LINKS COM POPUP
    # ======================================================
    if page.locator("a[target='_blank']").count() > 0:
        patterns.has_popup_links = True

    # ======================================================
    # 🔹 POWER BI EMBED (iframes / grid / canvas)
    # ======================================================
    if (
        "powerbi" in html
        or "app.powerbi.com" in html
        or "reportembed" in html
        or page.locator("iframe[src*='powerbi']").count() > 0
        or page.locator("[role='grid']").count() > 0
        or page.locator("[aria-label*='Power BI']").count() > 0
    ):
        patterns.is_powerbi = True
        patterns.has_table = True
        patterns.has_dropdown = True

    return patterns
