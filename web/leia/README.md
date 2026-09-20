# Book de Leia Cervantes

Web de book para actriz: **foto book**, **video book**, **experiencia** y las
secciones que se quieran ir añadiendo. Archivos estáticos: sin base de datos,
sin servidor y sin cuota mensual.

```
.
├── index.html                    el armazón (no hay que tocarlo)
├── contenido.json                ← TODO EL CONTENIDO. Es lo que edita el panel
├── .pages.yml                    la configuración del panel
├── assets/
│   ├── css/estilos.css           colores, tipografías y diseño
│   ├── js/app.js                 el motor que pinta la web
│   └── img/                      las fotos
├── robots.txt, _headers          quién puede ver la web y cómo se cachea
└── .github/workflows/
    └── optimizar-fotos.yml       encoge las fotos pesadas que se suban
```

## El panel de control

Para cambiar cualquier cosa de la web **no hace falta tocar un archivo**:

1. Entra en **[app.pagescms.org](https://app.pagescms.org)** y accede con tu
   cuenta de GitHub.
2. Elige el repositorio `leia-cervantes`.
3. Verás seis apartados: **Portada, Foto book, Video book, Secciones nuevas,
   Experiencia y Contacto**. Rellenas, arrastras fotos, y le das a guardar.

Cada vez que guardas, la web se actualiza sola en un minuto aproximadamente.

### Subir fotos

En *Foto book* → *Fotos* → añadir. Arrastras el archivo y listo: **no hace
falta redimensionar nada**. Al publicar, una foto de 3 MB recién salida de la
cámara se convierte sola en una de 350 KB. Rellena siempre la *Descripción*:
es lo que lee quien no ve la imagen, y también Google.

En la rejilla las fotos se recortan al centro para que todas las filas queden
alineadas; enteras se ven al ampliarlas. Si a alguna el recorte le corta la
cabeza, pon `center 20%` en *Encuadre* (0% pegado arriba, 100% abajo).

### Subir vídeos

En cada vídeo rellena **solo una** de las tres casillas:

| Casilla | Qué poner | Cuándo |
|---|---|---|
| YouTube | la dirección entera (`https://youtu.be/AbC123`) | lo más cómodo; súbelo **como «oculto»** y solo se verá desde aquí |
| Vimeo | la dirección (`https://vimeo.com/123456`) | si quieres contraseña o bloquear la descarga |
| Archivo de vídeo | súbelo desde el panel | si prefieres no depender de nadie |

Un vídeo con las tres casillas vacías sencillamente no aparece, así que puedes
dejarlos preparados. El reproductor no se carga hasta que alguien pulsa el
play: la página entra rápida y no arrastra cookies de terceros de entrada.

### Añadir una sección nueva

En *Secciones nuevas* → añadir. Le pones título (Teatro, Danza, Publicidad…),
un texto de entrada si quieres, y dentro las fotos y los vídeos que sea. La
sección **aparece sola en el menú de arriba**, entre el video book y la
experiencia. Sin título no se muestra; vacía tampoco.

### Cambiar la foto de portada

La portada ocupa toda la pantalla y lleva **dos versiones**, porque una foto
vertical metida en una pantalla apaisada se queda en un primer plano de la
nariz:

- *Foto de portada (vertical)* — la del móvil.
- *Foto de portada (apaisada)* — la del ordenador. Que sea 16:9 y con aire
  alrededor.

La apaisada de ahora está hecha ensanchando el fondo gris del estudio a los
lados; por ser un ciclorama de degradado liso, el estirado no se nota.

## Cómo se publica

La web está en **Cloudflare Pages**, conectado a este repositorio: cada vez
que se guarda algo desde el panel, Cloudflare la publica sola en menos de un
minuto. No hay que hacer nada a mano.

Ajustes del proyecto en Cloudflare, por si hay que rehacerlo algún día:

| Ajuste | Valor |
|---|---|
| Framework preset | None |
| Build command | *(vacío)* |
| Build output directory | `/` |
| Production branch | `main` |

El único proceso automático que queda en GitHub es
`.github/workflows/optimizar-fotos.yml`: cuando se sube una foto pesada desde
el panel, la reduce y la vuelve a guardar aquí, y Cloudflare publica ya la
versión ligera. Por eso se pueden subir las fotos tal cual salen de la cámara.

**Dominio propio:** en Cloudflare, *Workers & Pages → el proyecto → Custom
domains → Set up a domain*. Si el dominio está comprado en Cloudflare, no hay
que tocar el DNS: se configura solo. Si está en otro sitio, Cloudflare te dice
qué registro añadir (un CNAME apuntando al dominio `.pages.dev` del proyecto).
El certificado HTTPS lo pone Cloudflare gratis.

## Quién puede ver la web

Ahora mismo: **cualquiera con el enlace, pero fuera de Google**. La web se abre
sin registrarse —para que una directora de casting entre al instante— pero
lleva instrucción de no indexar, así que no aparece en búsquedas ni en el
buscador de imágenes. La instrucción está en dos sitios, y hay que quitarla de
los dos para que sí aparezca: la etiqueta `robots` de `index.html` y las líneas
`X-Robots-Tag` de `_headers`.

**Para cerrarla del todo** (que haya que poner un correo y un código para
entrar, como la galería del fotógrafo): en Cloudflare, *Zero Trust → Access →
Applications → Add an application → Self-hosted*, se apunta al dominio de la
web y se añaden los correos que pueden entrar. Es gratis hasta 50 personas y se
desactiva igual de rápido. Ten en cuenta que añade fricción: quien reciba el
enlace tendrá que registrarse para ver el book.

**El repositorio es privado**, así que las fotos y el código no se pueden
curiosear desde GitHub aunque se conozca la dirección.

## Tocar el diseño

Los colores, las dos tipografías y la separación entre fotos están en las
primeras líneas de `assets/css/estilos.css`, en el bloque `:root`. El número
de columnas de la galería, unas líneas más abajo en `.galeria` (4 en pantalla
grande, 3 y 2 según se estrecha).

La web es blanca a propósito, sin modo oscuro, para que manden las fotos y se
vean igual en cualquier pantalla.

Para verla en tu ordenador antes de publicar hace falta un servidor local
(abierta con doble clic, el navegador no deja leer `contenido.json`). Lo más
cómodo es mirar directamente la web publicada, que se actualiza en un minuto.

## Qué poner en un book que funciona

Unas cuantas cosas que se dan por sabidas en casting y conviene respetar:

**Fotos.** Entre 10 y 20, no más. Quien hace el casting mira treinta books en
una tarde: treinta fotos parecidas cansan, doce buenas se recuerdan. Lo que no
puede faltar: un **primer plano limpio**, de frente, luz natural, fondo neutro,
sin maquillaje ni disfraz (es la foto por la que la van a reconocer el día de
la prueba); un **plano medio**; y un **plano entero** que deje ver cómo se
mueve y cuál es su complexión real. El resto, personaje o escena. Fotos
actuales: a los quince, una foto de hace dos años ya no sirve.

**Vídeo.** El reel, **90 segundos como mucho**, y lo mejor en los primeros
diez. Si todavía no hay material profesional, vale perfectamente una escena
grabada con el móvil en horizontal, con buena luz y **sonido limpio** — el
sonido malo tumba más pruebas que la imagen mala. Añade una presentación a
cámara de 30 segundos diciendo nombre, edad y de dónde es: se pide
constantemente.

**Experiencia.** En orden, lo más reciente arriba, y sin inflar. Si hay poco,
la formación y las habilidades sostienen el book perfectamente: patinar, montar
a caballo, tocar un instrumento o hablar valenciano nativo deciden castings
reales. Pon solo lo que pueda hacer delante de una cámara mañana mismo.

**Al ser menor.** En el contacto van siempre los datos del padre, la madre o
quien la represente, nunca los suyos. Nada de dirección, colegio ni horarios,
ni en los textos ni en el pie de las fotos. La edad real conviene que esté
(casting la necesita para permisos y horarios de rodaje), pero la fecha de
nacimiento exacta no hace falta.
