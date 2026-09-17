# Agente de búsqueda de oficinas y naves para CPD — Valencia

Agente autónomo que **busca cada día** oficinas y naves pequeñas en venta que
sirvan para montar la sede y un CPD propio, las filtra contra unos criterios
técnicos exigentes, y envía **un email con lo que cumple** y con el mensaje a la
propiedad **ya redactado** para pedir visita.

```
fuentes (portales, banca, subastas)
        ↓  deduplicación entre portales
zona (l'Horta Sud / DANA fuera) + superficie 150-300 m²
        ↓  ficha de detalle
señales heurísticas (potencia, cubierta, tipo de edificio, reforma)
        ↓  cualificación con Claude de lo que queda en duda
puntuación 0-100 con desglose
        ↓
email diario  +  cola de contactos pendientes de tu aprobación
```

## Qué busca exactamente

### El cribado: pocos vetos, muchas rampas

Un umbral binario tira cosas buenas por 10 m² o por 20.000 € negociables. Por eso
el cribado tiene dos niveles:

**Vetos** (descartan, sin matices) — lo que no tiene arreglo posible:
zona inundable o DANA · edificio de viviendas · bajo comercial o local a pie de
calle · alquiler · tipologías que no son nave ni oficina · y los extremos
absolutos: menos de 100 m², más de 600 m², más de 550.000 €, más de 30 min.

**Bandas con rampa** (restan puntos, no matan) — todo lo demás:

| Eje | Banda plena (0 puntos) | Zona gris (resta progresivo) | Veto |
|---|---|---|---|
| Superficie | 130-320 m² (ideal 150-300) | 100-130 y 320-500 m² | <100 o >600 m² |
| Precio | ≤ 400.000 € (≤350.000 suma) | 400.000-550.000 € | > 550.000 € |
| Distancia | ≤ 15 min | 15-30 min | > 30 min |
| €/m² | ≤ 2.600 €/m² (≤1.200 suma) | > 2.600 €/m² | — |

**Compensación:** pasarse en un eje se perdona; pasarse en dos exige 85+ puntos
en todo lo demás. Un ejemplo real: una nave de 400 m² (se pasa 80) a 300.000 €
sale *sumando*, porque 750 €/m² compensa de sobra los metros de más.

**Umbral adaptativo:** si en los últimos 7 días ha entrado poco, el listón baja
10 puntos para no dejarte a ciegas; si ha entrado mucho, sube 8 para que el
email siga siendo corto.

**Verificación con fotos:** antes de recomendar nada, el agente descarga las
fotos del anuncio y se las enseña a Claude («¿esto es una nave o un solar?»).
Nació de un caso real: un anuncio titulado *"Nave industrial en venta en
Burjassot"*, 400 m² a 750 €/m², que en las fotos era un terreno con maleza.
Si las fotos desmienten el anuncio, cae; si no hay fotos legibles o la ficha
tiene seis palabras, no se recomienda: baja a «Casi» con la advertencia.

**Nada se pierde en silencio:** lo que se queda a menos de 15 puntos del umbral
va al bloque «Casi» del email, en una línea y con el motivo («se pasa 30.000 €»,
«le faltan 12 m²»).

| Requisito | Cómo se aplica |
|---|---|
| **València capital o ≤ 20 min en coche** | Tabla de municipios + routing real (OSRM) cuando hay coordenadas |
| **Fuera de l'Horta Sud y zona DANA** | Veto por municipio (45 municipios), por barrio de València (La Torre, Castellar, Pinedo…) y por texto del anuncio |
| **Edificio de oficinas, no de viviendas** | Señales de texto + criterio del modelo; una nave en polígono cumple por naturaleza |
| **Azotea/cubierta para clima, ampliable** | Señales + pregunta obligatoria a la propiedad si no consta |
| **200-300 kW o más de potencia** | Detecta kW/kVA declarados, centro de transformación, media tensión, acometida industrial |
| **Poca reforma** | Penaliza "a reformar" / "en bruto"; premia "listo para entrar" |
| **Naves industriales pequeñas** | Opción preferida (azotea propia, sin vecinos): suman bonus y tienen sus propios extras |
| **Oficinas en plantas altas** | Bonus por última planta o planta alta: menos tubería hasta la azotea y lejos del agua |
| **Nada a pie de calle** | Bajo comercial, local de calle y entresuelo se descartan siempre |

Todo esto vive en [`config/criteria.yaml`](config/criteria.yaml) y
[`config/zonas.yaml`](config/zonas.yaml): se cambia sin tocar código.

**Principio de diseño:** sólo se descarta con evidencia. Que un anuncio no diga
nada de la potencia no lo elimina — lo manda a la lista de "para vigilar" y
convierte el silencio en una pregunta concreta a la propiedad.

## Instalación

```bash
git clone https://github.com/sirfrido/Busqueda_oficina_CPD.git
cd Busqueda_oficina_CPD
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # o: pip install -r requirements.txt
cp .env.example .env             # y rellena SMTP, ANTHROPIC_API_KEY, etc.
```

Prueba sin tocar la red ni enviar nada:

```bash
oficinas buscar --fuentes demo --sin-email
open data/out/informe-*.html
```

## Uso

```bash
oficinas buscar                  # la pasada diaria completa
oficinas buscar --sin-email      # sin enviar: deja el HTML en data/out/
oficinas diagnostico             # ¿qué fuentes responden? ¿cuáles hay que arreglar?
oficinas estado                  # estadísticas y mejores candidatos guardados
oficinas contactos --completo    # cola de emails a la propiedad, con el texto
oficinas contactar --aprobar 3   # envía ESE email
oficinas contactar --aprobar 3 --para comercial@agencia.com
oficinas contactar --descartar 3
oficinas informe --limite 20     # regenerar el informe desde la base de datos
```

## El email a la propiedad

El agente redacta él mismo la solicitud de visita, con las preguntas que ese
anuncio concreto deja abiertas (una por tema, sin repetirse). Se presenta el uso
real —oficina + CPD pequeño—, porque ocultarlo sólo adelanta un "no" a la
segunda visita.

Tres modos, en `MODO_CONTACTO`:

| Modo | Comportamiento |
|---|---|
| `borrador` *(por defecto)* | Redacta, guarda un `.eml` y lo deja **pendiente de tu aprobación**. El email diario trae un botón `mailto:` con el texto ya puesto (sale desde tu cuenta) y el comando para que lo envíe el agente. |
| `auto` | El agente envía por su cuenta los contactos que superan el umbral (72/100). Actívalo cuando lleves unos días viendo que lo que propone tiene sentido. |
| `off` | No prepara contactos. |

Nada sale hacia un tercero en modo `borrador`, ni por error ni por una lectura
optimista de un anuncio.

## Ejecución diaria

**GitHub Actions** (incluido, `.github/workflows/busqueda-diaria.yml`): corre a
las 07:15 hora de Valencia. Configura los secretos del repositorio
(`SMTP_*`, `EMAIL_*`, `ANTHROPIC_API_KEY`, `IDEALISTA_*`) y la variable
`MODO_CONTACTO`. La base de datos se conserva entre ejecuciones con `actions/cache`
—es la memoria que evita repetirte los mismos anuncios cada mañana.

**Cron en tu máquina o servidor:**

```cron
15 7 * * * cd /ruta/Busqueda_oficina_CPD && .venv/bin/oficinas buscar >> data/agente.log 2>&1
```

## Fuentes

21 fuentes configuradas en [`config/fuentes.yaml`](config/fuentes.yaml):

- **Portales generalistas:** Idealista (API oficial), Fotocasa, Habitaclia,
  pisos.com, yaencontre, Milanuncios.
- **Especializado local:** Inmovalencia (naves y oficinas, fuerte en Paterna) y
  plantillas para añadir los portales industriales que quieras.
- **Banca y servicers (embargos y adjudicados):** Diglo (ex Haya), Servihabitat,
  Altamira/doValue, Aliseda, Solvia, Casaktua, CaixaBank, BBVA Vivienda, Sareb.
- **Subastas:** Portal de Subastas del BOE (judiciales y notariales).

Cada fuente declara sus selectores CSS; si el portal cambia el maquetado, el
adaptador cae automáticamente al **JSON-LD** incrustado, que sobrevive a casi
todos los rediseños.

> ⚠️ **Los selectores no están validados contra los portales en vivo**: el
> entorno donde se desarrolló esto tiene la salida a internet restringida por
> política de red (403 en el proxy para todos los dominios inmobiliarios), así
> que están escritos a partir de la estructura conocida de cada portal. El
> primer día, ejecuta `oficinas diagnostico` desde tu máquina y ajusta lo que
> salga `vacía` siguiendo [`docs/OPERACION.md`](docs/OPERACION.md). Lo que sí
> está probado de extremo a extremo es el pipeline completo (filtros, zonas,
> puntuación, informe y contactos), con 38 tests.

Estados de `oficinas diagnostico`:

| Estado | Significa |
|---|---|
| `ok` | La fuente devuelve anuncios |
| `vacía` | El portal respondió pero no se extrajo nada → ajustar selectores |
| `sin-red` | No se pudo conectar (proxy, DNS, 403 del portal) |
| `robots` | El `robots.txt` del portal no permite esa ruta |
| `inactiva` | Desactivada en `config/fuentes.yaml` |

### Sobre legalidad y buenas maneras

- El cliente HTTP **consulta `robots.txt`**, respeta `Crawl-delay`, se identifica
  con un User-Agent con email de contacto, espacia las peticiones y cachea.
- Donde hay **API oficial** (Idealista) se usa la API, no scraping.
- Portales con protección anti-bot agresiva (Milanuncios) vienen **desactivados**;
  actívalos tú si aceptas sus condiciones.
- Los datos recogidos son para uso propio de búsqueda; no se republican.

## Cualificación con Claude

Lo que no resuelve el diccionario de señales lo resuelve el modelo
(`claude-opus-5` por defecto, salida estructurada con JSON Schema). Lee la ficha
y decide si el inmueble está en edificio terciario, si la cubierta admite
máquinas y si la potencia es ampliable, respondiendo `si`/`no`/`verificar` —con
instrucción explícita de no inventar— y redacta las preguntas que faltan.

Sin `ANTHROPIC_API_KEY` el agente **sigue funcionando** sólo con heurísticas: el
modelo afina, no es imprescindible. El gasto se acota con `LLM_MAX_ANUNCIOS`
(40/día por defecto) y sólo se llama para anuncios que ya pasaron los filtros
baratos.

## Puntuación

0-100 con desglose visible en el email (cada punto sumado o restado se explica,
para poder ajustar los pesos viendo resultados reales).

| Tramo | Significado |
|---|---|
| ≥ 72 | Encaja en todo: el agente prepara el contacto con la propiedad |

| ≥ 55 | Entra en el email diario |
| 38-55 | "Para vigilar": cumple lo básico pero el anuncio calla lo importante |
| < 38 | Descartado |

Pesos en `src/oficinas/scoring.py` (`PESOS`), umbrales en `config/criteria.yaml`.

## Estructura

```
config/          criterios, zonas, fuentes y plantillas de email (editables)
src/oficinas/
  pipeline.py    orquestación de la pasada diaria
  fetch.py       HTTP educado: robots.txt, rate limit, caché, reintentos
  sources/       adaptadores: API de Idealista, HTML genérico, sitemap, BOE, fixture
  senales.py     detección heurística (con manejo de negaciones)
  qualifier.py   cualificación con Claude (salida estructurada)
  filtros.py     filtros duros
  scoring.py     puntuación con desglose
  geo.py         zonas vetadas, riesgo de inundación, minutos en coche
  storage.py     memoria en SQLite
  notify/        informe diario en HTML
  outreach/      redacción y cola de contactos con la propiedad
tests/           38 pruebas, incluyendo una pasada completa sin red
```

## Tests

```bash
pip install pytest && python -m pytest -q
```

## Ajustes habituales

| Quiero… | Dónde |
|---|---|
| Cambiar metros, precio o umbrales | `config/criteria.yaml` |
| Añadir/quitar un municipio vetado | `config/zonas.yaml` |
| Activar una fuente o arreglar selectores | `config/fuentes.yaml` |
| Cambiar el texto del email a la propiedad | `config/plantillas.yaml` |
| Ajustes propios sin tocar el repo | `config/local.yaml` (ver `local.yaml.example`) |
