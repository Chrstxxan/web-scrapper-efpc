"""
cérebro do crawler: decide e orquestra estratégias de extração
"""

from discovery.patterns import detect_patterns
from browser.strategies.accordion import run_accordion_strategy
from browser.strategies.interactive_table import extract_tables
from browser.strategies.powerbi import extract_powerbi_tables
from browser.strategies.document_library import extract_document_library
from browser.strategies.js_pdf_links import extract_js_pdf_links
from browser.strategies.list_links import extract_list_links
from browser.strategies.form_state_machine import (
    detect_form_state_machine,
    run_form_state_machine,
)


def run_strategies(page, logger):
    """
    Executa estratégias baseadas em padrões detectados na página.
    Retorna sempre uma lista de itens extraídos (pode ser vazia).
    """

    extracted_items = []

    # ======================================================
    # 🔍 DETECÇÃO INICIAL
    # ======================================================
    patterns = detect_patterns(page)
    logger.info(f"[PATTERNS][INIT] {patterns}")

    # ======================================================
    # 🔥 POWER BI — PRIORIDADE CONDICIONAL (ROBUSTA)
    # ======================================================
    if patterns.is_powerbi:

        try:
            # PDFs explícitos OU endpoints de download
            download_links = page.locator(
                "a[href$='.pdf'], "
                "a[href*='.pdf?'], "
                "a[href*='/Arquivo/'], "
                "a[onclick*='Arquivo'], "
                "a[href*='Download']"
            )

            if download_links.count() > 0:
                logger.info(
                    "📄 Links de download detectados — ignorando Power BI nesta página"
                )
            else:
                logger.info("🚀 Estratégia dominante: Power BI")
                extracted_items.extend(extract_powerbi_tables(page))
                return extracted_items

        except Exception as e:
            logger.debug(f"[PowerBI] Falha ao avaliar prioridade: {e}")

    # ======================================================
    # 🧠 FORM STATE MACHINE
    # ======================================================
    try:
        if detect_form_state_machine(page):
            logger.warning("🧠 Estratégia: Form State Machine")
            items = run_form_state_machine(page, logger)
            if items:
                return items
    except Exception as e:
        logger.debug(f"[FormState] Falha: {e}")

    # ======================================================
    # 🔗 LIST LINKS (PDF DIRETO NO HREF)  ← 🔥 NOVA STRATEGY
    # ======================================================
    try:
        list_links = extract_list_links(page)
        if list_links:
            logger.info(f"[LIST_LINKS] {len(list_links)} links encontrados")
            extracted_items.extend(list_links)
            # ❗ NÃO RETORNA — deixa o browser pipeline decidir

    except Exception as e:
        logger.debug(f"[ListLinks] Falha: {e}")

    # ======================================================
    # 🔄 REDETECTA PADRÕES
    # ======================================================
    patterns = detect_patterns(page)
    logger.info(f"[PATTERNS][POST-MENU] {patterns}")

    # ======================================================
    # 1️⃣ ACCORDION
    # ======================================================
    if patterns.has_accordion_years:
        logger.info("▶️ Estratégia: Accordion")
        try:
            run_accordion_strategy(page)
            page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug(f"[Accordion] Falha: {e}")

    # ======================================================
    # 2️⃣ TABELA
    # ======================================================
    if patterns.has_table or patterns.has_dropdown:
        logger.info("▶️ Estratégia: Tabela interativa")
        try:
            extracted_items.extend(extract_tables(page))
        except Exception as e:
            logger.debug(f"[Table] Falha: {e}")

    # ======================================================
    # 3️⃣ DOCUMENT LIBRARY
    # ======================================================
    if patterns.has_document_library:
        logger.info("▶️ Estratégia: Document library")
        try:
            extracted_items.extend(extract_document_library(page))
        except Exception as e:
            logger.debug(f"[DocumentLibrary] Falha: {e}")

    # ======================================================
    # 4️⃣ JS PDF LINKS
    # ======================================================
    try:
        js_links = extract_js_pdf_links(page)
        if js_links:
            logger.info(f"[JS-PDF] {len(js_links)} links encontrados")
            extracted_items.extend(js_links)
    except Exception as e:
        logger.debug(f"[JS-PDF] Falha: {e}")

    return extracted_items
