"""
modulo que decide se o crawler HTML falhou e precisa escalar para browser.
"""
def should_escalate(stats):

    # 🔥 Achou PDFs, MAS página é JS / accordion → precisa browser
    if stats["found_pdfs"] > 0:
        if stats["js_signals"] or stats["accordion_years"]:
            return True
        return False

    # Navegou pouco demais → provavelmente conteúdo dinâmico
    if stats["visited_pages"] <= 3:
        return True

    # Muitos scripts = JS-driven
    if stats["js_signals"]:
        return True

    # Caso conservador
    return True

def should_try_sitemap(stats: dict) -> bool:
    """
    Decide se vale a pena tentar sitemap
    """
    if stats["found_pdfs"] > 0 and not stats["accordion_years"]:
        return False

    if stats["visited_pages"] >= 30:
        return False

    # pouco conteúdo + nada encontrado
    return True