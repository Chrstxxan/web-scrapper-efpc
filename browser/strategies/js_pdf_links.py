import re
from urllib.parse import urljoin

PDF_REGEX = re.compile(
    r"(https?:\/\/[^\s'\"()]+\.pdf|\/[^\s'\"()]+\.pdf)",
    re.IGNORECASE
)

def extract_js_pdf_links(page):
    """
    Extrai PDFs escondidos em onclick, data-href, data-url etc.
    NÃO clica em nada.
    """

    found = set()

    elements = page.locator("[onclick], [data-href], [data-url]").all()

    for el in elements:
        try:
            attrs = [
                el.get_attribute("onclick"),
                el.get_attribute("data-href"),
                el.get_attribute("data-url"),
            ]

            for attr in attrs:
                if not attr:
                    continue

                for match in PDF_REGEX.findall(attr):
                    url = match
                    if url.startswith("/"):
                        url = urljoin(page.url, url)
                    found.add(url)
        except Exception:
            pass

    return [{"__kind__": "url", "__url__": u} for u in found]
