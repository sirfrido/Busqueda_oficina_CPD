/* ════════════════════════════════════════════════════════════════════════
   DATOS DEL BOOK  —  este es el ÚNICO archivo que necesitas editar.

   Reglas para no romper nada:
     · Cada texto va entre comillas "así".
     · Cada línea termina en coma.
     · Si no quieres un apartado, déjalo vacío ("" o []) y desaparece solo.
     · Para escribir comillas dentro de un texto, usa \" .
   ════════════════════════════════════════════════════════════════════════ */

window.DATOS = {

  /* ── Identidad ───────────────────────────────────────────────────────── */
  nombre:    "Leia",                    // lo que sale enorme en la portada
  apellidos: "Cervantes Hernández",
  marca:     "Leia Cervantes",          // el nombre de la barra superior
  titular:   "Actriz",

  foto_principal: "assets/img/foto-01.svg",   // la foto de portada, a pantalla completa

  presentacion:
    "Dos o tres líneas contando quién es Leia: su energía, lo que mejor se le " +
    "da en escena y qué tipo de proyectos busca. Breve y directo: quien lo lee " +
    "está decidiendo en diez segundos si sigue mirando.",

  /* ── Ficha técnica ───────────────────────────────────────────────────── */
  ficha: {
    "Edad":              "15 años",
    "Edad que aparenta": "14 - 17",
    "Altura":            "1,54 m",
    "Talla":             "S",            // ←
    "Calzado":           "38",           // ← estos cuatro los he puesto a ojo:
    "Ojos":              "Marrones",     // ←   revísalos antes de publicar
    "Pelo":              "Castaño largo",// ←
    "Residencia":        "Valencia",
    "Disponibilidad":    "Viajar dentro de España"
  },

  idiomas: [
    { nombre: "Español",    nivel: "Nativo" },
    { nombre: "Valenciano", nivel: "Nativo" },
    { nombre: "Inglés",     nivel: "Intermedio" }
  ],

  habilidades: [
    "Danza", "Canto", "Natación", "Patinaje", "Bicicleta", "Improvisación"
  ],

  /* ── Créditos ────────────────────────────────────────────────────────── */
  /* Quita los bloques que todavía no tenga y añade los que vayan llegando. */
  creditos: [
    {
      categoria: "Cine",
      trabajos: [
        { anio: "2026", titulo: "Título del cortometraje", personaje: "Personaje",
          direccion: "Nombre de dirección", productora: "Productora" }
      ]
    },
    {
      categoria: "Televisión",
      trabajos: [
        { anio: "2025", titulo: "Título de la serie", personaje: "Personaje episódico",
          direccion: "Nombre de dirección", productora: "Cadena / Productora" }
      ]
    },
    {
      categoria: "Teatro",
      trabajos: [
        { anio: "2025", titulo: "Título de la obra", personaje: "Personaje",
          direccion: "Nombre de dirección", productora: "Compañía / Sala" }
      ]
    },
    {
      categoria: "Publicidad",
      trabajos: [
        { anio: "2025", titulo: "Marca", personaje: "Protagonista",
          direccion: "Nombre de dirección", productora: "Agencia" }
      ]
    },
    {
      categoria: "Formación",
      trabajos: [
        { anio: "2024 - actualidad", titulo: "Interpretación ante la cámara",
          personaje: "", direccion: "Profesor/a", productora: "Escuela" },
        { anio: "2023", titulo: "Danza",
          personaje: "", direccion: "", productora: "Conservatorio / Escuela" }
      ]
    }
  ],

  /* ── Foto book ───────────────────────────────────────────────────────── */
  /* Copia las fotos en assets/img/ y pon una línea por foto. El orden de    */
  /* esta lista es el orden en que se ven. Empieza por las mejores.          */
  /* En la rejilla la foto se recorta al centro; entera se ve al ampliarla.  */
  /* Si a alguna el recorte le sienta mal, añádele:  encuadre: "center 20%"  */
  /* (0% = pegado arriba, 100% = pegado abajo).                              */
  fotos: [
    { archivo: "assets/img/foto-01.svg", alt: "Leia, primer plano" },
    { archivo: "assets/img/foto-02.svg", alt: "Leia, primer plano en blanco y negro" },
    { archivo: "assets/img/foto-03.svg", alt: "Leia, plano medio" },
    { archivo: "assets/img/foto-04.svg", alt: "Leia, plano medio de perfil" },
    { archivo: "assets/img/foto-05.svg", alt: "Leia, plano entero" },
    { archivo: "assets/img/foto-06.svg", alt: "Leia, plano entero de espaldas" },
    { archivo: "assets/img/foto-07.svg", alt: "Leia sentada, plano americano" },
    { archivo: "assets/img/foto-08.svg", alt: "Leia, retrato de tres cuartos" },
    { archivo: "assets/img/foto-09.svg", alt: "Leia sonriendo, primer plano" },
    { archivo: "assets/img/foto-10.svg", alt: "Leia en movimiento" }
  ],

  /* ── Video book ──────────────────────────────────────────────────────── */
  /* Para cada vídeo rellena SOLO una de estas tres opciones:               */
  /*   youtube: "ID"   → de https://youtu.be/ID  o  ?v=ID                   */
  /*   vimeo:   "ID"   → de https://vimeo.com/ID                            */
  /*   archivo: "assets/video/reel.mp4"  (vídeo subido a la propia web)     */
  /* "portada" es la imagen que se ve antes de darle al play (opcional).    */
  videos: {
    destacado: {
      titulo: "Reel",
      descripcion: "Montaje de escenas. Minuto y medio.",
      youtube: "",
      vimeo: "",
      archivo: "",
      portada: ""
    },
    otros: [
      { titulo: "Escena dramática", descripcion: "Fragmento de \"Título\" (2026)",
        youtube: "", vimeo: "", archivo: "", portada: "" },
      { titulo: "Escena de comedia", descripcion: "Self-tape",
        youtube: "", vimeo: "", archivo: "", portada: "" },
      { titulo: "Presentación a cámara", descripcion: "30 segundos",
        youtube: "", vimeo: "", archivo: "", portada: "" }
    ]
  },

  /* ── Contacto ────────────────────────────────────────────────────────── */
  /* Leia es menor: aquí van siempre los datos de quien la representa,      */
  /* nunca los suyos ni la dirección de casa.                               */
  contacto: {
    titulo: "Representación",
    persona: "Alex Cervantes (padre)",
    email: "alex@hampastudio.com",
    telefono: "",                        // ej: "+34 600 000 000" ("" = no se muestra)
    nota: "Para castings, pruebas y disponibilidad, escribid al correo.",
    redes: [
      // { nombre: "Instagram", url: "https://instagram.com/usuario" }
    ]
  }

};
