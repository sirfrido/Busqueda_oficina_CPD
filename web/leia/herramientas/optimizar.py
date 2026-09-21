"""Encoge las fotos que llegan del panel.

Así se puede subir la foto tal cual sale de la cámara: una de 3 MB se queda
en 350 KB sin que nadie tenga que acordarse de redimensionar nada.
"""

from PIL import Image, ImageOps
import pathlib
import sys

LADO_MAX = 2560          # más que esto no lo aprovecha ninguna pantalla
PESO_MAX = 450 * 1024    # a partir de aquí, se vuelve a comprimir
CALIDAD = 82


def main():
    carpeta = pathlib.Path("assets/img")
    if not carpeta.exists():
        return 0

    for f in sorted(carpeta.rglob("*")):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        peso = f.stat().st_size
        try:
            original = Image.open(f)
            formato = original.format          # se pierde al rotar: se lee antes
            im = ImageOps.exif_transpose(original)
        except Exception as e:
            print(f"  ! {f.name}: no se ha podido abrir ({e})")
            continue

        grande = max(im.size) > LADO_MAX
        if not grande and peso <= PESO_MAX:
            continue

        # Ojo: se conserva el nombre y el formato. Cambiar la extensión dejaría
        # a contenido.json apuntando a un archivo que ya no existe.
        if grande:
            im.thumbnail((LADO_MAX, LADO_MAX), Image.LANCZOS)
        if formato == "JPEG":
            im.convert("RGB").save(f, "JPEG", quality=CALIDAD, optimize=True, progressive=True)
        elif formato == "WEBP":
            im.save(f, "WEBP", quality=CALIDAD, method=6)
        else:
            im.save(f, formato, optimize=True)

        print(f"  · {f.name}: {peso // 1024} KB → {f.stat().st_size // 1024} KB  {im.size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
