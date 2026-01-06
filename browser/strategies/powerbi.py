# browser/strategies/powerbi.py

import time
import csv
import io
import re
from typing import List, Dict, Optional


# =========================================================
# 🔧 HELPERS
# =========================================================

def _sleep_render():
    time.sleep(3)


def _get_powerbi_frame(page):
    for frame in page.frames:
        if frame.url and "powerbi" in frame.url.lower():
            return frame
    return None


def _find_comboboxes(frame):
    locator = frame.locator('[role="combobox"]')
    return [locator.nth(i) for i in range(locator.count())]


def _open_combobox(frame, combo):
    combo.click()
    time.sleep(1)


def _get_combobox_options(frame) -> List[str]:
    return frame.evaluate("""
    () => Array.from(document.querySelectorAll('[role="option"]'))
        .map(o => o.innerText.trim())
        .filter(t => t.length > 0)
    """)


def _select_combobox_option(frame, label: str):
    frame.evaluate(f"""
    () => {{
        const opts = document.querySelectorAll('[role="option"]');
        for (const o of opts) {{
            if (o.innerText.trim() === {label!r}) {{
                o.click();
                break;
            }}
        }}
    }}
    """)


def _extract_grid_rows(frame) -> List[Dict]:
    return frame.evaluate("""
    () => {
        const rows = [];
        document.querySelectorAll('[role="row"]').forEach(row => {
            const cells = row.querySelectorAll('[role="gridcell"]');
            if (!cells.length) return;

            const values = Array.from(cells).map(c => c.innerText.trim());
            rows.push(values);
        });
        return rows;
    }
    """)


def _parse_number_br(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# =========================================================
# 🚀 FUNÇÃO PRINCIPAL
# =========================================================

def extract_powerbi_tables(page):
    """
    Retorna lista de dicts no formato:
    {
        "filename": str,
        "csv_bytes": bytes
    }
    """

    outputs = []

    frame = _get_powerbi_frame(page)
    if not frame:
        return outputs

    _sleep_render()

    combos = _find_comboboxes(frame)
    if len(combos) < 2:
        return outputs

    combo_plano = combos[0]
    combo_data = combos[1]

    # =====================================================
    # 1️⃣ Selecionar DATA MAIS RECENTE
    # =====================================================
    _open_combobox(frame, combo_data)
    datas = _get_combobox_options(frame)
    if not datas:
        return outputs

    competencia = datas[0]
    _select_combobox_option(frame, competencia)
    _sleep_render()

    # =====================================================
    # 2️⃣ Iterar PLANOS
    # =====================================================
    _open_combobox(frame, combo_plano)
    planos = _get_combobox_options(frame)

    for plano in planos:
        _select_combobox_option(frame, plano)
        _sleep_render()

        raw_rows = _extract_grid_rows(frame)
        if not raw_rows:
            continue

        # =================================================
        # 3️⃣ Normalizar linhas
        # =================================================
        normalized = []

        for row in raw_rows:
            if len(row) < 4:
                continue

            segmento = row[0]
            qtd = _parse_number_br(row[1])
            valor = _parse_number_br(row[2])
            perc = _parse_number_br(row[3])

            nivel = "subtotal" if segmento.isupper() else "ativo"

            normalized.append({
                "plano": plano,
                "competencia": competencia,
                "segmento": segmento,
                "quantidade": qtd,
                "valor": valor,
                "percentual": perc,
                "nivel": nivel
            })

        if not normalized:
            continue

        # =================================================
        # 4️⃣ Gerar CSV em memória
        # =================================================
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "plano",
                "competencia",
                "segmento",
                "quantidade",
                "valor",
                "percentual",
                "nivel"
            ]
        )
        writer.writeheader()
        writer.writerows(normalized)

        csv_bytes = output.getvalue().encode("utf-8")
        output.close()

        safe_plano = re.sub(r"[^\w]+", "_", plano).upper()
        safe_comp = re.sub(r"[^\w]+", "_", competencia).upper()

        filename = f"{safe_comp}__{safe_plano}.csv"

        outputs.append({
            "filename": filename,
            "csv_bytes": csv_bytes
        })

    return outputs
