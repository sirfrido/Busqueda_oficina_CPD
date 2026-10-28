"""Hojas de miniaturas con los logotipos de las marcas mixtas y gráficas.

En el PDF del BOPI su nombre va dentro de la imagen, así que el cribado por
texto no las ve: estas hojas son para revisarlas a ojo (o con un modelo con
visión). Cada miniatura lleva la fecha del BOPI y la página del PDF, para
localizar la ficha si algo se parece.

    python -m marcas.logos data/out/marcas/pdf data/out/marcas/logos

Necesita `pdfimages` (poppler-utils) y Pillow.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ANCHO, ALTO, COLUMNAS, FILAS = 200, 150, 8, 6


def hojas(dir_pdf: Path, salida: Path) -> list[Path]:
    from PIL import Image, ImageDraw

    salida.mkdir(parents=True, exist_ok=True)
    miniaturas: list[tuple[str, int, Path]] = []
    tmp = Path(tempfile.mkdtemp(prefix="logos-"))
    for pdf in sorted(dir_pdf.glob("*.pdf")):
        destino = tmp / pdf.stem
        destino.mkdir()
        subprocess.run(["pdfimages", "-j", "-p", str(pdf), str(destino / "i")], check=True, capture_output=True)
        for img in sorted(destino.iterdir()):
            miniaturas.append((pdf.stem, int(img.name.split("-")[1]), img))

    por_hoja = COLUMNAS * FILAS
    rutas = []
    for n, inicio in enumerate(range(0, len(miniaturas), por_hoja)):
        hoja = Image.new("RGB", (COLUMNAS * ANCHO, FILAS * ALTO), "white")
        dibujo = ImageDraw.Draw(hoja)
        for k, (fecha, pagina, img) in enumerate(miniaturas[inicio : inicio + por_hoja]):
            x, y = (k % COLUMNAS) * ANCHO, (k // COLUMNAS) * ALTO
            try:
                im = Image.open(img).convert("RGB")
            except OSError:
                continue
            im.thumbnail((ANCHO - 6, ALTO - 22))
            hoja.paste(im, (x + 3, y + 3))
            dibujo.text((x + 3, y + ALTO - 17), f"{fecha[:5]} p{pagina}", fill="red")
            dibujo.rectangle([x, y, x + ANCHO - 1, y + ALTO - 1], outline="#ccc")
        ruta = salida / f"logos-{n:02d}.png"
        hoja.save(ruta)
        rutas.append(ruta)
    print(f"{len(miniaturas)} logotipos en {len(rutas)} hojas: {salida}")
    return rutas


if __name__ == "__main__":
    hojas(Path(sys.argv[1]), Path(sys.argv[2]))
