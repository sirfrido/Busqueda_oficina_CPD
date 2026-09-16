# Manual de operación

## El primer día

1. `cp .env.example .env` y rellena SMTP + destinatarios.
2. `oficinas buscar --fuentes demo --sin-email` → abre `data/out/informe-*.html`
   y comprueba que el formato te sirve.
3. `oficinas diagnostico` → verás qué fuentes responden hoy. Es normal que
   varias salgan `vacía`: los portales cambian el HTML y hay que ajustar
   selectores (abajo).
4. `oficinas buscar --sin-email` → primera pasada real. Revisa los descartes con
   `oficinas estado`.
5. Cuando el resultado te cuadre, quita `--sin-email` y programa la ejecución
   diaria.

## Arreglar una fuente que devuelve 0

```bash
oficinas diagnostico --fuentes fotocasa -v
```

1. Abre el listado en el navegador, inspecciona una tarjeta de resultado.
2. Copia el selector CSS del contenedor (`item`) y de cada campo.
3. Edítalos en `config/fuentes.yaml` y vuelve a ejecutar el diagnóstico.

Si el portal renderiza con JavaScript y no hay HTML útil, hay dos salidas
limpias: usar su API si la ofrece, o suscribirse a sus alertas por email y
añadir un adaptador que lea el buzón. El scraping con navegador headless contra
un portal que lo prohíbe expresamente no es una opción recomendable.

## Interpretar el email

- **Semáforo:** ✅ confirmado en el anuncio · ❓ hay que preguntarlo · ❌ incumple.
- **"Por confirmar":** las preguntas que irán en el email a la propiedad.
- **Puntuación:** el desglose muestra de dónde sale cada punto. Si algo puntúa
  raro, ahí se ve por qué.
- **"Para vigilar":** cumple los filtros duros pero el anuncio no dice nada de
  potencia o cubierta. En Valencia esto es la mayoría: casi ningún anuncio de
  oficina menciona la potencia disponible.

## Sobre la potencia eléctrica (lo que ningún portal te va a decir)

Ningún anuncio publica la capacidad de acceso de la red. El agente puede
detectar indicios (centro de transformación, media tensión, nave en polígono)
y preguntar, pero la respuesta firme la da la distribuidora:

1. Pide a la propiedad el **CUPS** y la potencia contratada actual.
2. Consulta la **capacidad de acceso** en el mapa de la distribuidora
   (i-DE / Iberdrola Distribución para casi toda la provincia de Valencia).
3. Para 200-300 kW normalmente hace falta **suministro en media tensión con CT
   propio**; en un edificio de oficinas hay que confirmar que queda capacidad
   libre en el CT del edificio, y en nave, que la línea lo admite.

Por eso la pregunta de potencia va **siempre** en el email a la propiedad,
aunque el anuncio parezca claro.

## Coste aproximado

- Portales y BOE: gratis.
- API de Idealista: plan gratuito limitado; el resto según su tarifa.
- Claude: se llama como mucho a `LLM_MAX_ANUNCIOS` anuncios al día (40 por
  defecto), con caché de prompt en el bloque de sistema. Para bajarlo:
  `LLM_EFFORT=low` o `LLM_MAX_ANUNCIOS=15`.

## Cuándo pasar a `MODO_CONTACTO=auto`

Cuando lleves una o dos semanas y se cumplan las tres:

1. Los candidatos con ≥ 72 puntos te parecen todos razonables.
2. No hay falsos positivos de zona (nada de l'Horta Sud colándose).
3. El texto de `config/plantillas.yaml` te representa tal cual está.

Hasta entonces, `borrador` + el botón `mailto:` del email es igual de rápido y
no compromete tu nombre con una agencia por un fallo de parsing.
