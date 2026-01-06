# browser/strategies/interactive_table.py

def extract_tables(page):
    tables = []

    for table in page.locator("table").all():
        rows = []
        for tr in table.locator("tr").all():
            row = [td.inner_text().strip() for td in tr.locator("th, td").all()]
            if row:
                rows.append(row)

        if rows:
            tables.append(rows)

    return tables
