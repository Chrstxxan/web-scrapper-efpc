'''
cerebro do crawler, decide estrategia de extracao de arquivos do site.
'''
from discovery.patterns import detect_patterns

from browser.strategies.accordion import run_accordion_strategy
from browser.strategies.interactive_table import extract_tables
from browser.strategies.powerbi import extract_powerbi_tables
from browser.strategies.document_library import extract_document_library
from browser.strategies.js_pdf_links import extract_js_pdf_links
from browser.strategies.window_open import hook_window_open
from browser.strategies.aggressive_downloads import aggressive_click_downloads
from browser.strategies.form_state_machine import detect_form_state_machine, run_form_state_machine


def run_strategies(page, logger):
    """
    Executa estratégias baseadas em padrões detectados na página.
    Retorna sempre uma lista de itens extraídos (pode ser vazia).
    """

    patterns = detect_patterns(page)
    logger.info(f"[PATTERNS] {patterns}")

    extracted_items = []

    # ======================================================
    # 🔥 POWER BI — PRIORIDADE ABSOLUTA (inalterado)
    # ======================================================
    if patterns.is_powerbi:
        logger.info("🚀 Estratégia dominante: Power BI")
        try:
            extracted_items.extend(extract_powerbi_tables(page))
        except Exception as e:
            logger.debug(f"[PowerBI] Falha: {e}")

        return extracted_items

    # ======================================================
    # 🧠 FORM STATE MACHINE (NOVO — COMPLEMENTAR)
    # ======================================================
    try:
        if detect_form_state_machine(page):
            logger.warning("🧠 Estratégia: Form State Machine (combinatória)")
            items = run_form_state_machine(page, logger)

            # ⚠️ IMPORTANTE:
            # se encontrou PDFs, já é estado final → não roda accordion/table
            if items:
                return items
    except Exception as e:
        logger.debug(f"[FormState] Falha: {e}")

    # ======================================================
    # 📚 DOCUMENT LIBRARY (lista grande de PDFs)
    # ======================================================
    if patterns.has_document_library:
        logger.info("▶️ Estratégia: Document library (links diretos)")
        try:
            extracted_items.extend(extract_document_library(page))
        except Exception as e:
            logger.debug(f"[DocumentLibrary] Falha: {e}")
        # ⚠️ não retorna — pode coexistir

    # ======================================================
    # 🔗 PDFs escondidos em JS (onclick / data-*)
    # ======================================================
    try:
        js_links = extract_js_pdf_links(page)
        if js_links:
            logger.info(f"[JS-PDF] {len(js_links)} links encontrados")
            extracted_items.extend(js_links)
    except Exception as e:
        logger.debug(f"[JS-PDF] {e}")

    # ======================================================
    # 1️⃣ ACCORDION (anos / seções ocultas)
    # ======================================================
    if patterns.has_accordion_years:
        logger.info("▶️ Estratégia: Accordion (expandir anos)")
        try:
            run_accordion_strategy(page)
            page.wait_for_timeout(800)
        except Exception as e:
            logger.debug(f"[Accordion] Falha: {e}")

    # ======================================================
    # 2️⃣ TABELA HTML / JS INTERATIVA
    # ======================================================
    if patterns.has_table or patterns.has_dropdown:
        logger.info("▶️ Estratégia: Tabela interativa genérica")
        try:
            extracted_items.extend(extract_tables(page))
        except Exception as e:
            logger.debug(f"[Table] Falha: {e}")

    return extracted_items

