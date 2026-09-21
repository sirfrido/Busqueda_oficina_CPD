"""Genera la portada apaisada a partir de la vertical.

La portada ocupa toda la pantalla. Una foto vertical metida en un monitor
apaisado se queda en un primer plano de la nariz, así que hace falta una
versión 16:9. Pedirla a mano es pedir demasiado: aquí se construye sola.

Cómo: se recorta en vertical justo alrededor de ella y se ensancha el lienzo
a los lados. El relleno no es el borde estirado —si ella toca el borde, eso
arrastra piel— sino el ciclorama reconstruido: se mide su color fila a fila
allí donde no está ella, y las filas tapadas se interpolan. Al ser un
degradado suave, no se nota la costura.

Si la foto es un primer plano que ocupa todo el ancho, no hay fondo que
reconstruir: entonces se recorta una banda 16:9 alrededor de la cara.
"""

from PIL import Image, ImageChops, ImageFilter, ImageStat
import json
import pathlib
import sys

ANCHO_MAX = 2560                         # el ancho máximo que se sirve (16:9)
SALIDA = pathlib.Path("portada-ancha.jpg")   # en la raíz: no es una foto subida
MARGEN = 0.06                            # aire por encima y por debajo de ella
ANCHA_SI_OCUPA = 0.80                    # a partir de aquí se trata como primer plano
CALIDAD = 82
LADO_ANALISIS = 160                      # ancho al que se reduce para medir


def _mascara_contra(peq, referencia, umbral):
    """Marca lo que se separa de un fondo dado (un color, o uno por fila)."""
    if isinstance(referencia, tuple):
        modelo = Image.new("RGB", peq.size, referencia)
    else:
        tira = Image.new("RGB", (1, len(referencia)))
        tira.putdata(referencia)
        modelo = tira.resize(peq.size)
    dif = ImageChops.difference(peq, modelo).convert("L")
    return dif.filter(ImageFilter.MedianFilter(3)).point(lambda v: 255 if v > umbral else 0)


def analizar(im):
    """Reduce la foto y separa a Leia del fondo. Devuelve (peq, mascara, perfil).

    Dos pasadas: el ciclorama es un degradado, así que compararlo con un color
    único marca medio fondo como si fuera ella. La primera pasada sirve solo
    para poder medir el fondo fila a fila; la segunda ya afina la silueta.
    """
    peq = im.resize((LADO_ANALISIS, round(LADO_ANALISIS * im.height / im.width)))
    w, h = peq.size
    c = max(3, w // 12)
    esquinas = [(0, 0, c, c), (w - c, 0, w, c), (0, h - c, c, h), (w - c, h - c, w, h)]
    medias = [ImageStat.Stat(peq.crop(e)).mean for e in esquinas]
    color = tuple(round(sum(m[i] for m in medias) / len(medias)) for i in range(3))

    burda = _mascara_contra(peq, color, 34)
    perfil = perfil_del_ciclorama(peq, burda, color)
    return peq, _mascara_contra(peq, perfil, 26), perfil


def caja_del_sujeto(peq, mascara, escala):
    """Dónde está ella, en coordenadas de la foto grande.

    Por columnas y filas, no con getbbox: una sola mota de ruido en una
    esquina estiraría la caja hasta el borde.
    """
    ancho, alto = peq.size
    mx = mascara.load()
    cols = [sum(1 for y in range(alto) if mx[x, y]) for x in range(ancho)]
    filas = [sum(1 for x in range(ancho) if mx[x, y]) for y in range(alto)]

    minimo_col = max(2, round(alto * 0.02))
    minimo_fila = max(2, round(ancho * 0.02))
    xs = [i for i, v in enumerate(cols) if v >= minimo_col]
    ys = [i for i, v in enumerate(filas) if v >= minimo_fila]
    if not xs or not ys:
        return None

    x0, x1, y0, y1 = xs[0], xs[-1] + 1, ys[0], ys[-1] + 1
    ocupa = ((x1 - x0) * (y1 - y0)) / (ancho * alto)
    if not 0.05 < ocupa < 0.99:
        return None
    return tuple(round(v * escala) for v in (x0, y0, x1, y1))


def perfil_del_ciclorama(peq, mascara, fondo):
    """El color del fondo fila a fila, medido donde no está ella."""
    ancho, alto = peq.size
    px, mx = peq.load(), mascara.load()
    perfil = []

    for y in range(alto):
        libres = [px[x, y] for x in range(ancho) if mx[x, y] == 0]
        if len(libres) >= max(4, ancho // 20):
            libres.sort(key=lambda c: c[0] + c[1] + c[2])
            perfil.append(libres[len(libres) // 2])      # mediana
        else:
            perfil.append(None)                          # fila tapada por ella

    if all(v is None for v in perfil):
        return [fondo] * alto

    # Las filas tapadas se rellenan interpolando entre las que sí se midieron
    conocidas = [i for i, v in enumerate(perfil) if v is not None]
    for i, v in enumerate(perfil):
        if v is not None:
            continue
        antes = max((k for k in conocidas if k < i), default=None)
        despues = min((k for k in conocidas if k > i), default=None)
        if antes is None:
            perfil[i] = perfil[despues]
        elif despues is None:
            perfil[i] = perfil[antes]
        else:
            t = (i - antes) / (despues - antes)
            perfil[i] = tuple(round(perfil[antes][c] * (1 - t) + perfil[despues][c] * t)
                              for c in range(3))

    # Suavizado vertical, para que no queden escalones
    radio = max(2, alto // 16)
    suave = []
    for i in range(alto):
        trozo = perfil[max(0, i - radio):i + radio + 1]
        suave.append(tuple(round(sum(c[k] for c in trozo) / len(trozo)) for k in range(3)))
    return suave


def recorte_vertical(im, caja):
    """Recorta alrededor de ella, con un poco de aire arriba y abajo."""
    if caja is None:
        return 0, round(im.height * 0.75)
    _, y0, _, y1 = caja
    aire = round((y1 - y0) * MARGEN)
    arriba = max(0, y0 - aire)
    abajo = im.height if y1 >= im.height - 2 else min(im.height, y1 + aire)
    if abajo - arriba < im.height * 0.25:
        return 0, round(im.height * 0.75)
    return arriba, abajo


def banda_de_primer_plano(im, caja):
    """Sin fondo que reconstruir: una banda 16:9 a la altura de la cara."""
    alto_banda = round(im.width * 9 / 16)
    if caja:
        cara = caja[1] + round((caja[3] - caja[1]) * 0.18)
        arriba = cara - round(alto_banda * 0.42)
    else:
        arriba = round(im.height * 0.12)
    arriba = min(max(arriba, 0), im.height - alto_banda)
    return im.crop((0, arriba, im.width, arriba + alto_banda))


def ensanchar(im, arriba, abajo, perfil, centro_x):
    """Lleva el recorte a 16:9 rellenando los lados con el ciclorama."""
    recorte = im.crop((0, arriba, im.width, abajo))
    w, h = recorte.size
    ancho_final = round(h * 16 / 9)

    if ancho_final <= w:
        x = min(max(centro_x - ancho_final // 2, 0), w - ancho_final)
        return recorte.crop((x, 0, x + ancho_final, h))

    # El perfil está medido sobre la foto pequeña: se recorta a las filas del
    # recorte y se estira a lo ancho.
    alto_perfil = len(perfil)
    y0 = round(arriba / im.height * alto_perfil)
    y1 = max(y0 + 1, round(abajo / im.height * alto_perfil))
    tira = Image.new("RGB", (1, y1 - y0))
    tira.putdata(perfil[y0:y1])
    fondo = tira.resize((ancho_final, h), Image.BICUBIC)

    x0 = min(max(round(ancho_final / 2 - centro_x), 0), ancho_final - w)
    fondo.paste(recorte, (x0, 0))
    return fondo


def main():
    datos = json.loads(pathlib.Path("contenido.json").read_text(encoding="utf-8"))
    origen = (datos.get("identidad") or {}).get("portada", "").lstrip("/")
    if not origen or not pathlib.Path(origen).exists():
        print(f"  ! No encuentro la portada ({origen or 'sin definir'}).")
        return 0

    im = Image.open(origen).convert("RGB")
    peq, mascara, perfil = analizar(im)
    caja = caja_del_sujeto(peq, mascara, im.width / peq.width)

    ocupa = (caja[2] - caja[0]) / im.width if caja else 0
    if ocupa >= ANCHA_SI_OCUPA:
        ancha = banda_de_primer_plano(im, caja)
        modo = f"primer plano (ocupa {ocupa:.0%} del ancho): banda 16:9"
    else:
        arriba, abajo = recorte_vertical(im, caja)
        centro_x = (caja[0] + caja[2]) // 2 if caja else im.width // 2
        ancha = ensanchar(im, arriba, abajo, perfil, centro_x)
        modo = (f"recorte {arriba}-{abajo}, lienzo ensanchado · "
                f"{'sujeto localizado' if caja else 'sin localizar'}")

    # Si la foto no da para 2560 px, se guarda a su tamaño natural: ampliar
    # no añade detalle, solo peso y desenfoque.
    ancho = min(ANCHO_MAX, ancha.width)
    ancha = ancha.resize((ancho, round(ancho * 9 / 16)), Image.LANCZOS)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    ancha.save(SALIDA, "JPEG", quality=CALIDAD, optimize=True, progressive=True)

    print(f"  · {origen} {im.size} → {SALIDA.name} {ancha.size[0]}x{ancha.size[1]} "
          f"({SALIDA.stat().st_size // 1024} KB)")
    print(f"    {modo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
