# browser/strategies/accordion.py

def run_accordion_strategy(page):
    page.evaluate("""
    () => {
        document.querySelectorAll('button, a, div, span').forEach(el => {
            const t = (el.innerText || '').trim();
            if (/^20\\d{2}$/.test(t) || t.includes('ver') || t.includes('mais')) {
                try { el.click(); } catch(e) {}
            }
        });
    }
    """)
