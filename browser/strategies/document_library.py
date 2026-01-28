from urllib.parse import urljoin


FILE_EXTS = (".pdf", ".xls", ".xlsx", ".doc", ".docx", ".zip")

KEYWORDS = (
    "relatório", "demonstrativo", "balancete",
    "investimento", "plano", "ata", "regulamento",
    "contábil", "atuarial"
)

# =====================================================
# 🎯 FILTRO DURO — INVESTIMENTOS (DI + POLÍTICAS)
# =====================================================
REQUIRED_TERMS = (
    "demonstrativo",
    "investimento",
    "investimentos",
    "d-i",
    "di_",
    "di-",
    "politica",
    "política",
)

def is_investment_related(url: str, text: str) -> bool:
    u = url.lower()
    t = (text or "").lower()

    return any(term in u or term in t for term in REQUIRED_TERMS)

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
        
        # =====================================================
        # 🎯 FILTRO DURO — INVESTIMENTOS (DI + POLÍTICAS)
        # =====================================================
        if not is_investment_related(url, text):
            continue
        
        print(f"[DocumentLibrary] candidato detectado: {url}")
        
        outputs.append({
            "__kind__": "url",
            "__url__": url,
        })

    return outputs
