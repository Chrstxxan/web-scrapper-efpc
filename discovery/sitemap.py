import requests
from xml.etree import ElementTree
from urllib.parse import urlparse

from discovery.domain_guard import is_blocked_domain, is_external_page


COMMON_SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
]


def discover_sitemap_urls(seed_url: str, logger) -> list[str]:
    base = f"{urlparse(seed_url).scheme}://{urlparse(seed_url).netloc}"
    urls = []

    for path in COMMON_SITEMAP_PATHS:
        url = base + path
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200 or "xml" not in r.headers.get("Content-Type", ""):
                continue

            tree = ElementTree.fromstring(r.text)
            for loc in tree.findall(".//{*}loc"):
                if loc.text:
                    urls.append(loc.text.strip())

            if urls:
                logger.info(f"[SITEMAP] {len(urls)} URLs encontradas em {url}")
                break

        except Exception:
            continue

    return urls


def filter_sitemap_urls(
    urls: list[str],
    seed_base_domain: str,
    allowed_paths: list[str],
) -> list[str]:

    filtered = []

    for url in urls:
        if is_blocked_domain(url):
            continue

        if is_external_page(url, seed_base_domain):
            continue

        parsed = urlparse(url)

        if allowed_paths:
            if not any(parsed.path.startswith(p) for p in allowed_paths):
                continue

        # ignora óbvios inúteis
        if any(
            bad in parsed.path.lower()
            for bad in (
                "contato", "privacidade", "termos", "login",
                "cadastro", "politica", "cookie", "faq",
            )
        ):
            continue

        filtered.append(url)

    return filtered