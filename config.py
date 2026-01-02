'''
modulo para configuracoes do sistema
'''
from pathlib import Path

# diretorios padrao do sistema para salvamento dos docs
DATA_DIR = Path("data")
FILES_DIR = DATA_DIR / "files"

# extensoes que o sistema aceita baixar
FILE_EXTENSIONS = (
    ".pdf", ".zip",
    ".doc", ".docx",
    ".xls", ".xlsx"
)

# palavras-chave que tornam o doc relevante
KEYWORDS = [
    "balancete", "balanço", "demonstrativo",
    "investimento", "investimentos",
    "relatório", "estatuto",
    "regulamento", "ata",
    "eleição", "tributação",
    "perfil", "política"
]

# regra mínima de ano
MIN_YEAR = 2022

# info que os sites recebem quando o sistema ta mandando requisicoes pra eles
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"), 
           "Accept": "application/pdf, application/octet-stream, /", "Accept-Language": "pt-BR, pt;q=0.9", "Connection": "keep-alive",}

REQUEST_DELAY = 0.5

MAX_CRAWL_DEPTH = 5

PATH_INTEREST_HINTS = [
    "transparencia",
    "demonstrativo",
    "balancete",
    "investimento",
    "contabil",
    "atuarial",
    "relatorio",
    "prestacao",
    "financeiro",
    "governanca",
]