'''
modulo de heuristicas do sistema
'''
import re

def is_relevant(text: str, url: str, keywords: list[str]) -> bool:
    combined = f"{text} {url}".lower()
    return any(k in combined for k in keywords)

def extract_year(text: str) -> int | None:
    years = re.findall(r"(20\d{2})", text)
    years = [int(y) for y in years if 2000 <= int(y) <= 2100]
    return max(years) if years else None
