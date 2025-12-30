"""
modulo que decide se o crawler HTML falhou e precisa escalar para browser.
"""
def should_escalate(stats):

    # Achou PDF? sem browser
    if stats["found_pdfs"] > 0:
        return False

    # Navegou pouco demais → provavelmente conteúdo dinâmico
    if stats["visited_pages"] <= 3:
        return True

    # Muitos scripts = JS-driven
    if stats["js_signals"]:
        return True

    # Caso conservador: não achou nada relevante
    return True
