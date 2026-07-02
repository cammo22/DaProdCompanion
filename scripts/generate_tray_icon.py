"""
Genera l'icona della system tray come file .ico multi-risoluzione, con lo
stesso gradiente blu usato per il blob CSS dell'avatar (vedi
app/src/renderer/avatar/style.css) cosi' l'icona nella tray e l'overlay sul
desktop sono coerenti visivamente. Nessun asset grafico esterno disponibile:
e' un placeholder generato via codice, sostituibile in futuro con un'icona
disegnata a mano senza cambiare come viene caricata (tray.ts).

Uso: uv run --with pillow python scripts/generate_tray_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "resources" / "icons" / "tray-icon.ico"

# Stessi tre stop del radial-gradient CSS dell'avatar: #8ab4ff -> #4a5cff (65%) -> #2f3bb0
STOP_0 = (138, 180, 255)
STOP_1 = (74, 92, 255)
STOP_65 = 0.65
STOP_2 = (47, 59, 176)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def color_at(t: float) -> tuple[int, int, int]:
    if t <= STOP_65:
        return lerp(STOP_0, STOP_1, t / STOP_65)
    return lerp(STOP_1, STOP_2, (t - STOP_65) / (1 - STOP_65))


def render(size: int) -> Image.Image:
    # Sovracampionamento 4x poi downscale, per bordi lisci alle risoluzioni piccole (16/32px).
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center_x, center_y = big * 0.4, big * 0.35
    max_r = big * 0.62
    steps = 80
    for i in range(steps, 0, -1):
        t = i / steps
        r = max_r * t
        color = color_at(t)
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=(*color, 255),
        )

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    images[-1].save(
        OUTPUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"Icona scritta in {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
