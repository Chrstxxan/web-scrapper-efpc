# browser/strategy_router.py

from discovery.patterns import detect_patterns
from browser.strategies.accordion import run_accordion_strategy
from browser.strategies.interactive_table import extract_tables
from browser.strategies.powerbi import extract_powerbi_tables


def run_strategies(page, logger):
    """
    Executa estratégias baseadas em padrões detectados na página.
    Retorna sempre uma lista de tabelas extraídas (pode ser vazia).
    """

    patterns = detect_patterns(page)
    logger.info(f"[PATTERNS] {patterns}")

    extracted_tables = []

    # ======================================================
    # 🔥 POWER BI — PRIORIDADE MÁXIMA
    # ======================================================
    if patterns.is_powerbi:
        logger.info("🚀 Estratégia dominante: Power BI")
        try:
            tables = extract_powerbi_tables(page)
            extracted_tables.extend(tables)
        except Exception as e:
            logger.debug(f"[PowerBI] Falha: {e}")

        # ⚠️ Power BI já controla dropdown + grid
        # não faz sentido cair em estratégias genéricas
        return extracted_tables

    # ======================================================
    # 1️⃣ ACCORDION (anos, seções ocultas)
    # ======================================================
    if patterns.has_accordion_years:
        logger.info("▶️ Estratégia: Accordion (expandir anos)")
        try:
            run_accordion_strategy(page)
            page.wait_for_timeout(800)
        except Exception as e:
            logger.debug(f"[Accordion] Falha: {e}")

    # ======================================================
    # 2️⃣ TABELA HTML / JS INTERATIVA (fallback)
    # ======================================================
    if patterns.has_table or patterns.has_dropdown:
        logger.info("▶️ Estratégia: Tabela interativa genérica")
        try:
            tables = extract_tables(page)
            extracted_tables.extend(tables)
        except Exception as e:
            logger.debug(f"[Table] Falha: {e}")

    return extracted_tables
