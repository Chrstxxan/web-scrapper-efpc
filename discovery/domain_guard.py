from urllib.parse import urlparse

BLOCKED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "whatsapp.com",
    "wa.me",
    "t.me",
    "telegram.org",
    "google.com",
    "googleusercontent.com",
    "gstatic.com",
    "doubleclick.net",
}

def get_base_domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host

def is_external_page(url: str, seed_base: str) -> bool:
    host = urlparse(url).hostname or ""
    return not host.endswith(seed_base)

def is_blocked_domain(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host.endswith(d) for d in BLOCKED_DOMAINS)
