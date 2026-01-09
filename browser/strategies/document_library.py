from urllib.parse import urljoin


FILE_EXTS = (".pdf", ".xls", ".xlsx", ".doc", ".docx", ".zip")

KEYWORDS = (
    "relatório", "demonstrativo", "balancete",
    "investimento", "plano", "ata", "regulamento",
    "contábil", "atuarial"
)


def extract_document_library(page):
    outputs = []

    links = page.locator("a[href]").all()

    for a in links:
        try:
            href = a.get_attribute("href")
            text = (a.inner_text() or "").lower()
        except Exception:
            continue

        if not href:
            continue

        url = urljoin(page.url, href)

        if not url.lower().endswith(FILE_EXTS):
            continue

        # filtro semântico leve (evita menu / lixo)
        if not any(k in text for k in KEYWORDS):
            continue

        print(f"[DocumentLibrary] candidato detectado: {url}")
        
        outputs.append({
            "__kind__": "url",
            "__url__": url,
        })

    return outputs
