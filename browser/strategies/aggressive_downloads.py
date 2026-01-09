def aggressive_click_downloads(page, logger):
    """
    Último recurso.
    Clica em tudo que parece download / pdf.
    """

    logger.warning("[AGGRESSIVE] Ativando modo agressivo")

    try:
        buttons = page.locator("a, button, span, div").all()

        for el in buttons:
            try:
                text = (el.inner_text() or "").lower()
                href = el.get_attribute("href") or ""

                if (
                    "pdf" in text
                    or "download" in text
                    or "baixar" in text
                    or href.lower().endswith(".pdf")
                ):
                    el.click(timeout=1000)
                    page.wait_for_timeout(600)
            except Exception:
                pass
    except Exception:
        pass
