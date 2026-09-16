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

| Requisito | Cómo se aplica |
|---|---|
| **150-300 m²** | Filtro duro, con ±10 % de tolerancia (los anuncios mienten con los metros) |
| **València capital o ≤ 20 min en coche** | Tabla de municipios + routing real (OSRM) cuando hay coordenadas |
| **Fuera de l'Horta Sud y zona DANA** | Veto por municipio (45 municipios), por barrio de València (La Torre, Castellar, Pinedo…) y por texto del anuncio |
| **Edificio de oficinas, no de viviendas** | Señales de texto + criterio del modelo; una nave en polígono cumple por naturaleza |
| **Azotea/cubierta para clima, ampliable** | Señales + pregunta obligatoria a la propiedad si no consta |
| **200-300 kW o más de potencia** | Detecta kW/kVA declarados, centro de transformación, media tensión, acometida industrial |
| **Poca reforma** | Penaliza "a reformar" / "en bruto"; premia "listo para entrar" |
| **Naves industriales pequeñas** | Tratadas como candidatas de primera, con sus propios extras (muelle, altura libre, puerta de camión) |

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
todos los rediseños. `oficinas diagnostico` dice cuál hay que retocar.

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
