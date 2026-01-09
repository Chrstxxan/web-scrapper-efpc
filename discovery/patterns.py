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

    # 🧾 form + botão (já existe)
    has_form_download: bool = False

    # 📚 biblioteca de documentos
    has_document_library: bool = False

    # 🔥 Power BI
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

    # ------------------------------------------------------
    # Accordion por ano
    # ------------------------------------------------------
    if re.search(r"\b20\d{2}\b", text):
        patterns.has_accordion_years = True

    # ------------------------------------------------------
    # Botões de download
    # ------------------------------------------------------
    if (
        page.locator("text=Download").count() > 0
        or page.locator("text=Baixar").count() > 0
        or page.locator("text=Visualizar").count() > 0
    ):
        patterns.has_download_buttons = True

    # ------------------------------------------------------
    # Dropdown
    # ------------------------------------------------------
    if page.locator("select").count() > 0:
        patterns.has_dropdown = True

    # ------------------------------------------------------
    # Tabela
    # ------------------------------------------------------
    if page.locator("table").count() > 0:
        patterns.has_table = True

    # ------------------------------------------------------
    # Popup
    # ------------------------------------------------------
    if page.locator("a[target='_blank']").count() > 0:
        patterns.has_popup_links = True

    # ------------------------------------------------------
    # MULTI-PLAN SELECTOR (ex: MultiPrev)
    # ------------------------------------------------------
    if (
        page.locator("text=Plano").count() >= 3
        and page.locator("a, button, div").count() > 10
    ):
        patterns.has_plan_selector = True

    # ------------------------------------------------------
    # FORM-DRIVEN DOWNLOAD (mais restritivo)
    # ------------------------------------------------------
    if (
        patterns.has_dropdown
        and page.locator("button:has-text('Baixar')").count() > 0
        and page.locator("select option").count() >= 4
    ):
        patterns.has_form_download = True

    # ------------------------------------------------------
    # DOCUMENT LIBRARY (lista grande de PDFs)
    # ------------------------------------------------------
    file_links = page.locator(
        "a[href$='.pdf'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.doc'], a[href$='.docx'], a[href$='.zip']"
    )

    if file_links.count() >= 5:
        patterns.has_document_library = True

    # ------------------------------------------------------
    # POWER BI
    # ------------------------------------------------------
    if (
        "powerbi" in html
        or "app.powerbi.com" in html
        or "reportembed" in html
        or page.locator("iframe[src*='powerbi']").count() > 0
        or page.locator("[role='grid']").count() > 0
    ):
        patterns.is_powerbi = True
        patterns.has_dropdown = True
        patterns.has_table = True

    return patterns
