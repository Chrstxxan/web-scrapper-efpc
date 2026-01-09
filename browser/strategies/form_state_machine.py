# browser/strategies/form_state_machine.py

import re
import time
from playwright.sync_api import Page


GENERATE_KEYWORDS = (
    "gerar",
    "buscar",
    "consultar",
    "aplicar",
    "pesquisar",
)

PDF_EXT = ".pdf"


def detect_form_state_machine(page: Page) -> bool:
    """
    Detecta páginas que exigem múltiplos formulários
    antes de liberar documentos.
    """

    selects = page.locator("select:visible")
    if selects.count() < 2:
        return False

    for btn in page.locator("button:visible, input[type=submit]:visible").all():
        text = (btn.inner_text() or "").lower()
        if any(k in text for k in GENERATE_KEYWORDS):
            return True

    return False


def _select_most_recent_option(select):
    """
    Seleciona a opção mais recente do select:
    - último item válido
    - ignora placeholders
    """

    options = select.locator("option").all()
    valid = []

    for opt in options:
        value = opt.get_attribute("value")
        text = (opt.inner_text() or "").strip()

        if not value or not text:
            continue

        if re.search(r"selecione|todos|--", text.lower()):
            continue

        valid.append(value)

    if not valid:
        return False

    # mais recente = último
    select.select_option(valid[-1])
    return True


def run_form_state_machine(page: Page, logger):
    """
    Executa o fluxo:
    plano → período mais recente → gerar → coletar PDFs
    """

    logger.warning("[FORM-STATE] Strategy ativada (form combinatório)")

    collected = []
    seen = set()

    # 🔹 1. detectar selects
    selects = page.locator("select:visible")
    if selects.count() < 2:
        logger.warning("[FORM-STATE] selects insuficientes")
        return []

    # 🔹 2. selecionar opções mais recentes
    for i in range(selects.count()):
        ok = _select_most_recent_option(selects.nth(i))
        if not ok:
            logger.warning(f"[FORM-STATE] select {i} sem opções válidas")

    time.sleep(1)

    # 🔹 3. clicar botão gerar/buscar
    clicked = False
    for btn in page.locator("button:visible, input[type=submit]:visible").all():
        text = (btn.inner_text() or "").lower()
        if any(k in text for k in GENERATE_KEYWORDS):
            btn.click()
            clicked = True
            logger.info("[FORM-STATE] botão de geração acionado")
            break

    if not clicked:
        logger.warning("[FORM-STATE] botão gerar não encontrado")
        return []

    page.wait_for_timeout(2500)

    # 🔹 4. coletar PDFs do estado atual
    for a in page.locator("a[href$='.pdf']").all():
        href = a.get_attribute("href")
        if not href:
            continue

        if href in seen:
            continue

        seen.add(href)
        collected.append(
            {
                "__kind__": "url",
                "__url__": href,
            }
        )

    logger.warning(
        f"[FORM-STATE] {len(collected)} PDFs coletados (período mais recente)"
    )

    return collected
