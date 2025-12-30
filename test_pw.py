from playwright.sync_api import sync_playwright

print("Iniciando playwright")

with sync_playwright() as p:
    print("Playwright OK")
    browser = p.chromium.launch(headless=True)
    print("Chromium OK")
    browser.close()

print("Finalizado")
