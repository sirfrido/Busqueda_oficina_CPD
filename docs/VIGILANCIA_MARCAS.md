# Vigilancia de la marca HAMPA STUDIO en el BOPI

Cada **miércoles** el agente lee las solicitudes de marca publicadas en el
Boletín Oficial de la Propiedad Industrial desde la última pasada, busca las que
se parecen a HAMPA STUDIO y te envía un email con cada una, el motivo y **la
fecha límite para oponerte** (dos meses desde la publicación, art. 19 de la Ley
17/2001 de Marcas).

```
OEPM (Tomo 1 del BOPI en PDF, API pública)  +  imarcas.com (respaldo)
        ↓  se combinan por número de solicitud; se saltan los BOPI ya revisados
cribado local: parecido escrito y sonoro con «HAMPA» (sin red ni modelo)
        ↓
Claude revisa TODAS las denominaciones: fonética, gráfica y conceptual,
teniendo en cuenta las clases de Niza
        ↓  con una marca de control escondida para comprobar que funciona
email: riesgo alto / medio / bajo, motivo, recomendación y plazo de oposición
```

## Por qué fallaba el escenario de Make

1. **La URL ya no existe.** `sede.oepm.gob.es/bopiweb/descargaPublicaciones/formBusqueda.action`
   redirige ahora a la portada de oepm.es: la OEPM está migrando el BOPI a una
   aplicación nueva (`sede.oepm.gob.es/bopi/`). La antigua sigue, de momento,
   en `consultas2.oepm.es/bopiweb/...`. El primer módulo HTTP recibía la portada,
   el regex de `cargaForm(...TOMO 1` no encontraba nada y el escenario se paraba.
2. **El cortafuegos de la OEPM bloquea servidores en la nube.** Desde un centro
   de datos responde 403 o 503 (F5). Make, GitHub Actions o cualquier servidor
   pueden caer en ese bloqueo cualquier día.
3. **Sólo leía el BOPI del día.** El BOPI sale de lunes a viernes; ejecutado los
   miércoles, el escenario miraba el del miércoles y se perdía los otros cuatro.
4. **El canario no probaba nada.** El prompt decía a Claude cuál era la marca
   de prueba, así que «detectarla» no demostraba que el análisis funcionase.
5. **El regex del PDF** (`541\s*\n\s*\n...`) depende de cómo PDF.co parta las
   líneas; cualquier cambio de maquetación deja la lista vacía sin avisar.

## Qué hace distinto

- **Dos fuentes.** La oficial: el Tomo 1 del BOPI en PDF, que la aplicación
  nueva de la OEPM sirve por una API pública sin registro
  (`sede.oepm.gob.es/apibopiweb`). Y de respaldo, el listado diario de
  imarcas.com, que dejó de publicarse el 19/10/2026. Si una cae, lo dice al
  pie del email y sigue con la otra.
- **Cubre la semana entera** y recuerda qué BOPI ya revisó
  (`data/marcas/bopi_revisados.json`): si un día se publica tarde, entra en la
  pasada siguiente en vez de perderse.
- **Claude ve todas las denominaciones**, no sólo las que un regex deja pasar,
  y devuelve JSON validado contra un esquema.
- **Canario ciego**: la marca de control va con un número normal, en una
  posición al azar y sin que el prompt la mencione. Si Claude no la detecta, el
  email dice «Test del sistema: FALLO».
- **Nada se pierde en silencio**: lo que se parece mucho por escrito pero
  Claude descarta sale en un bloque aparte; sin `ANTHROPIC_API_KEY` el agente
  sigue avisando sólo con el cribado local.

## Puesta en marcha

1. En GitHub → *Settings → Secrets and variables → Actions*, los mismos secretos
   que el informe de oficinas: `ANTHROPIC_API_KEY`, `SMTP_HOST`, `SMTP_PUERTO`,
   `SMTP_USUARIO`, `SMTP_PASSWORD`, `EMAIL_REMITENTE`, `EMAIL_DESTINATARIOS`
   (o `MARCAS_DESTINATARIOS` si el aviso va a otra dirección).
2. Pon tus **clases de Niza** en `config/marcas.yaml` (`clases_niza`). Sin ellas
   el análisis supone las de un estudio creativo (9, 16, 35, 41, 42).
3. El workflow `.github/workflows/vigilancia-marcas.yml` corre los miércoles a
   las 08:00 (hora de Madrid en invierno). Para probarlo ya: *Actions →
   Vigilancia de marcas → Run workflow*.

En tu máquina:

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m marcas.cli diagnostico            # ¿qué fuentes responden?
PYTHONPATH=src python -m marcas.cli revisar --sin-email    # informe en data/out/marcas/
PYTHONPATH=src python -m marcas.cli revisar --desde 2026-10-01 --hasta 2026-10-21
```

## Ajustes

| Quiero… | Dónde |
|---|---|
| Vigilar otra marca o cambiar el núcleo distintivo | `marca`, `nucleo` en `config/marcas.yaml` |
| Indicar mis clases y mi actividad | `clases_niza`, `actividad` |
| Más o menos sensibilidad del cribado local | `umbral_local` (0-1; 0.85 por defecto) |
| Otro día u hora | `cron` en el workflow |
| Otro modelo o esfuerzo | `modelo`, `effort` (o `MODELO_MARCAS`, `EFFORT_MARCAS`) |

El análisis usa la API de Claude con `fallbacks: "default"`: si el modelo
rechazara una petición, la API la reintenta con otro modelo automáticamente.

## Limitaciones

- Antes de oponerte, comprueba el expediente en el
  [Localizador de la OEPM](https://consultas2.oepm.es/LocalizadorWeb/).
- En el PDF del BOPI, las marcas **mixtas o gráficas** (más de la mitad) llevan
  el nombre dentro de la imagen, y el texto sale como «(marca gráfica o
  mixta)». La pasada semanal en Claude mira esos logotipos aparte; el cribado
  automático por texto no los ve.
- No sustituye a un agente de la propiedad industrial: decide con él si una
  alerta «alto» merece oposición.
