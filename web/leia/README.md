# Book de Leia Cervantes

Web de book para actriz: **experiencia**, **foto book** y **video book** en una
sola página. Son archivos estáticos (HTML, CSS y JS): no hay base de datos, no
hay que instalar nada y se puede subir a cualquier hosting.

```
web/leia/
├── index.html              la página (no hace falta tocarla)
├── assets/
│   ├── css/estilos.css     colores, tipografías y diseño
│   ├── js/datos.js         ← TODO EL CONTENIDO SE EDITA AQUÍ
│   ├── js/app.js           la lógica (no hace falta tocarla)
│   └── img/                las fotos
└── README.md
```

## Cómo verla en tu ordenador

Haz doble clic en `index.html`. Se abre en el navegador y funciona todo.

## Cómo cambiar el contenido

Abre `assets/js/datos.js` con cualquier editor de texto. Está todo comentado y
en orden: nombre, presentación, ficha, idiomas, habilidades, créditos, fotos,
vídeos y contacto. Cada apartado que dejes vacío (`""` o `[]`) desaparece solo
de la web.

### Añadir fotos

1. Copia la foto en `assets/img/` (por ejemplo `leia-05.jpg`).
2. Añade una línea en el apartado `fotos` de `datos.js`:

```js
{ archivo: "assets/img/leia-05.jpg", alt: "Leia, primer plano" },
```

- El orden de la lista es el orden en que se ven. Empieza por las mejores.
- `alt` es la descripción para quien no ve la imagen (y para Google). Escríbela.
- En la rejilla las fotos se **recortan al centro** para que todas las filas
  queden alineadas; enteras se ven al ampliarlas. Si a alguna el recorte le
  sienta mal, añádele `encuadre: "center 20%"` (0% pegado arriba, 100% abajo).
- Tamaño recomendado: **1600 px por el lado largo** y **menos de 400 KB** por
  foto (JPG calidad 80). Fotos de 5 MB recién salidas de la cámara hacen que la
  web tarde en cargar y ese es el momento en que la gente se va.

Las 12 fotos que hay ahora (`leia-01.jpg` … `leia-12.jpg`) salen de la sesión
de Manuel Orts, elegidas una por toma: cada foto estaba en color y en blanco y
negro, y poner las dos versiones de la misma toma no aporta nada en un book.

### Cambiar la foto de portada

La portada ocupa toda la pantalla, así que lleva **dos versiones**, porque una
foto vertical metida en una pantalla apaisada se queda en un primer plano de la
nariz:

- `portada.jpg` — vertical, la que se ve en el móvil.
- `portada-ancha.jpg` — apaisada, la que se ve en ordenador.

Las dos están en `datos.js` (`foto_principal` y `foto_principal_ancha`). La
apaisada de ahora está hecha ensanchando el fondo gris del estudio a los lados,
que por ser un ciclorama liso se estira sin que se note. Si pones otra, que sea
16:9 y con aire alrededor.

### Añadir vídeos

En el apartado `videos` de `datos.js`, para cada vídeo rellena **solo una** de
estas tres opciones:

| Opción | Qué poner | Cuándo usarla |
|---|---|---|
| `youtube` | el ID o la URL entera (`https://youtu.be/AbC123`) | lo más cómodo; súbelo **como «oculto»**, así solo se ve desde aquí |
| `vimeo` | el ID o la URL (`https://vimeo.com/123456`) | si quieres control de descarga y contraseña |
| `archivo` | `"assets/video/reel.mp4"` | si prefieres no depender de nadie (crea la carpeta `assets/video/`) |

`portada` es opcional: la imagen que se ve antes de darle al play. Si es de
YouTube y no pones ninguna, se coge la miniatura automáticamente.

El reproductor **no se carga hasta que alguien pulsa play**: la página va rápida
y no se cargan cookies de terceros de entrada.

### Cambiar los colores, las tipografías o el número de columnas

Todo está en las primeras líneas de `assets/css/estilos.css`, en el bloque
`:root`: los colores, las dos tipografías y `--hueco`, la separación entre
fotos. El número de columnas de la galería está unas líneas más abajo, en
`.galeria` (5 en pantalla grande, 4, 3 y 2 según se estrecha).

La web es blanca a propósito, como la referencia: sin modo oscuro, para que
las fotos manden y se vean igual en cualquier pantalla.

## Cómo publicarla en internet

Tres opciones, de más fácil a más control:

1. **Netlify Drop** — entra en [app.netlify.com/drop](https://app.netlify.com/drop)
   y arrastra la carpeta `leia`. En diez segundos tienes una URL. Gratis.
2. **GitHub Pages** — en los ajustes del repositorio, *Pages* → rama y carpeta
   `/web/leia`. Gratis, con la URL del repositorio.
3. **Tu propio dominio** (p. ej. `leia.com` o `leia.hampastudio.com`) — sube la
   carpeta por FTP a cualquier hosting, o conecta el dominio a Netlify.

Cuando tengas la URL definitiva, ponla en `index.html` en la etiqueta
`og:image` para que se vea bien la miniatura al compartir por WhatsApp.

## Qué poner en un book que funciona

Unas cuantas cosas que se dan por sabidas en casting y conviene respetar:

**Fotos.** Entre 10 y 20, no más. Quien hace el casting mira treinta books en una
tarde: treinta fotos parecidas cansan, doce buenas se recuerdan. Lo que no puede
faltar: un **primer plano limpio**, de frente, luz natural, fondo neutro, sin
maquillaje ni disfraz (es la foto por la que la van a reconocer el día de la
prueba); un **plano medio**; y un **plano entero** que deje ver cómo se mueve y
cuál es su complexión real. El resto, personaje o escena. Fotos actuales: a los
quince, una foto de hace dos años ya no sirve.

**Vídeo.** El reel, **90 segundos como mucho**, y lo mejor en los primeros diez.
Si todavía no hay material profesional, vale perfectamente una escena grabada con
el móvil en horizontal, con buena luz y **sonido limpio** — el sonido malo tumba
más pruebas que la imagen mala. Añade una presentación a cámara de 30 segundos
diciendo nombre, edad y de dónde es: se pide constantemente.

**Experiencia.** En orden, lo más reciente arriba, y sin inflar. Si hay poco,
la formación y las habilidades sostienen el book perfectamente: patinar, montar
a caballo, tocar un instrumento o hablar valenciano nativo deciden castings
reales. Pon solo lo que pueda hacer delante de una cámara mañana mismo.

**Al ser menor.** En el contacto van siempre los datos del padre, la madre o
quien la represente, nunca los suyos. Nada de dirección, colegio ni horarios, ni
en los textos ni en el pie de las fotos. La edad real conviene que esté (casting
la necesita para permisos y horarios de rodaje), pero la fecha de nacimiento
exacta no hace falta.
