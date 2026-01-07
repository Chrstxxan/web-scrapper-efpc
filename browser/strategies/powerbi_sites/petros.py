# browser/strategies/powerbi_sites/petros.py
# ============================================================
# PETROS – Power BI FULL TABLE Screenshot (Scroll + Stitch)
# ============================================================

import time
import re
import io
import hashlib
from typing import List, Dict
from PIL import Image


# ============================================================
# HELPERS
# ============================================================

def _safe_name(text: str) -> str:
    return re.sub(r"[^\w]+", "_", text).upper()


def _get_powerbi_frame(page):
    for frame in page.frames:
        if frame.url and (
            "powerbi" in frame.url.lower()
            or "analysis.windows.net" in frame.url.lower()
        ):
            return frame
    return None


def _open_slicer(frame):
    frame.locator('[role="combobox"]').first.click()
    time.sleep(1)


def _get_slicer_options(frame) -> List[str]:
    return frame.evaluate("""
        () => Array.from(document.querySelectorAll('[role="option"]'))
            .map(o => o.innerText.trim())
            .filter(Boolean)
    """)


def _select_option(frame, label: str):
    frame.evaluate(f"""
        () => {{
            const opts = document.querySelectorAll('[role="option"]');
            for (const o of opts) {{
                if (o.innerText.trim() === {label!r}) {{
                    o.click();
                    return;
                }}
            }}
        }}
    """)


def _grid_signature(frame) -> str:
    """Hash visual simples pra garantir que o grid mudou"""
    return frame.evaluate("""
        () => {
            const grid = document.querySelector('div[role="grid"]');
            return grid ? grid.innerText.slice(0, 2000) : '';
        }
    """)


def _wait_grid_change(frame, old_sig, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        sig = _grid_signature(frame)
        if sig != old_sig:
            return
        time.sleep(0.5)


# ============================================================
# SCROLL + STITCH
# ============================================================

def _scroll_and_capture(frame) -> bytes:
    grid = frame.locator("div[role='grid']").first
    screenshots = []

    last_scroll = -1

    while True:
        # screenshot visível
        png = grid.screenshot()
        screenshots.append(Image.open(io.BytesIO(png)))

        # scroll
        scroll_pos = frame.evaluate("""
            () => {
                const g = document.querySelector('div[role="grid"]');
                g.scrollTop += g.clientHeight;
                return g.scrollTop;
            }
        """)

        time.sleep(1)

        if scroll_pos == last_scroll:
            break

        last_scroll = scroll_pos

    # stitch vertical
    width = max(img.width for img in screenshots)
    height = sum(img.height for img in screenshots)

    final_img = Image.new("RGB", (width, height))
    y = 0
    for img in screenshots:
        final_img.paste(img, (0, y))
        y += img.height

    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
# ENTRYPOINT
# ============================================================

def extract(page) -> List[Dict]:
    outputs = []

    time.sleep(6)  # Power BI load real

    frame = _get_powerbi_frame(page)
    if not frame:
        return []

    _open_slicer(frame)
    planos = _get_slicer_options(frame)

    if not planos:
        return []

    last_sig = _grid_signature(frame)

    for plano in planos:
        _open_slicer(frame)
        _select_option(frame, plano)

        _wait_grid_change(frame, last_sig)
        last_sig = _grid_signature(frame)

        png_bytes = _scroll_and_capture(frame)

        outputs.append({
            "__kind__": "png",
            "__filename__": f"PETROS__{_safe_name(plano)}.png",
            "__bytes__": png_bytes
        })

    return outputs
