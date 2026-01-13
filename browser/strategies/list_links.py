# browser/strategies/list_links.py

from urllib.parse import urljoin


def extract_list_links(page):
    """
    Extrai links diretos para PDFs presentes em listas ou conteúdo editorial.
    Não clica, não executa JS, apenas lê o DOM.
    """

    items = []
    seen = set()

    anchors = page.locator("a[href$='.pdf'], a[href*='.pdf?']")

    for i in range(anchors.count()):
        a = anchors.nth(i)

        try:
            if not a.is_visible():
                continue

            href = a.get_attribute("href")
            if not href:
                continue

            pdf_url = urljoin(page.url, href)
            if pdf_url in seen:
                continue

            text = (a.inner_text() or "").strip()

            seen.add(pdf_url)

            items.append({
                "__kind__": "url",
                "__url__": pdf_url,
                "anchor_text": text,
                "strategy": "list_links",
            })

        except Exception:
            continue

    return items
