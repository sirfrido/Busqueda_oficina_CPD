/* ════════════════════════════════════════════════════════════════════════
   DATOS DEL BOOK  —  este es el ÚNICO archivo que necesitas editar.

   Reglas para no romper nada:
     · Cada texto va entre comillas "así".
     · Cada línea termina en coma.
     · Si no quieres un apartado, déjalo vacío ("" o []) y desaparece solo.
     · Para escribir comillas dentro de un texto, usa \" .
   ════════════════════════════════════════════════════════════════════════ */

window.DATOS = {

  /* ── Portada ─────────────────────────────────────────────────────────── */
  nombre:    "Leia",
  apellidos: "Apellido Apellido",        // "" si prefieres solo el nombre
  marca:     "Leia",                     // lo que aparece arriba a la izquierda
  titular:   "Actriz",
  presentacion:
    "Aquí van dos o tres líneas contando quién es Leia: su energía, lo que " +
    "mejor se le da en escena y qué tipo de proyectos busca. Breve y directo: " +
    "quien lo lee está decidiendo en diez segundos si sigue mirando.",

  foto_principal: "assets/img/foto-01.svg",   // la foto grande de la portada
  cv_pdf: "",                                 // ej: "assets/cv-leia.pdf" ("" = sin botón)

  /* Los 4 datos que se ven en la portada, debajo de la presentación */
  chips: ["10 años", "1,40 m", "Valencia", "Español · Valenciano · Inglés"],

  /* ── Ficha técnica (columna izquierda de Experiencia) ────────────────── */
  ficha: {
    "Edad":            "10 años",
    "Edad que aparenta": "9 - 12",
    "Altura":          "1,40 m",
    "Talla":           "10 años",
    "Calzado":         "35",
    "Ojos":            "Marrones",
    "Pelo":            "Castaño largo",
    "Residencia":      "Valencia",
    "Disponibilidad":  "Viajar dentro de España"
  },

  idiomas: [
    { nombre: "Español",    nivel: "Nativo" },
    { nombre: "Valenciano", nivel: "Nativo" },
    { nombre: "Inglés",     nivel: "Intermedio" }
  ],

  habilidades: [
    "Danza clásica", "Canto", "Natación", "Patinaje",
    "Bicicleta", "Piano", "Improvisación"
  ],

  /* ── Créditos ────────────────────────────────────────────────────────── */
  /* Quita los bloques que no tenga todavía y añade los que vengan.        */
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
        { anio: "2023", titulo: "Danza clásica",
          personaje: "", direccion: "", productora: "Conservatorio / Escuela" }
      ]
    }
  ],

  /* ── Foto book ───────────────────────────────────────────────────────── */
  /* Copia las fotos en assets/img/ y añade una línea por foto.            */
  /* "tipo" crea los filtros de arriba. Usa siempre los mismos nombres.    */
  fotos: [
    { archivo: "assets/img/foto-01.svg", tipo: "Primer plano",  alt: "Leia, primer plano en exterior" },
    { archivo: "assets/img/foto-02.svg", tipo: "Primer plano",  alt: "Leia, primer plano sonriendo" },
    { archivo: "assets/img/foto-03.svg", tipo: "Plano medio",   alt: "Leia, plano medio con fondo neutro" },
    { archivo: "assets/img/foto-04.svg", tipo: "Plano medio",   alt: "Leia, plano medio de perfil" },
    { archivo: "assets/img/foto-05.svg", tipo: "Plano entero",  alt: "Leia, plano entero de cuerpo completo" },
    { archivo: "assets/img/foto-06.svg", tipo: "Plano entero",  alt: "Leia, plano entero en movimiento" },
    { archivo: "assets/img/foto-07.svg", tipo: "Personaje",     alt: "Leia caracterizada como personaje" },
    { archivo: "assets/img/foto-08.svg", tipo: "Personaje",     alt: "Leia en una escena" },
    { archivo: "assets/img/foto-09.svg", tipo: "Personaje",     alt: "Leia con vestuario de época" }
  ],

  /* ── Video book ──────────────────────────────────────────────────────── */
  /* Para cada vídeo rellena SOLO una de estas tres opciones:              */
  /*   youtube: "ID"   → de https://youtu.be/ID  o  ?v=ID                  */
  /*   vimeo:   "ID"   → de https://vimeo.com/ID                           */
  /*   archivo: "assets/video/reel.mp4"  (vídeo subido a la propia web)    */
  /* "portada" es la imagen que se ve antes de darle al play (opcional).   */
  videos: {
    destacado: {
      titulo: "Reel 2026",
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
  /* Leia es menor: aquí van SIEMPRE los datos de quien la representa,     */
  /* nunca los suyos ni la dirección de casa.                              */
  contacto: {
    titulo: "Representación",
    persona: "Alex (padre)",
    email: "alex@hampastudio.com",
    telefono: "",                        // ej: "+34 600 000 000" ("" = no se muestra)
    nota: "Para castings, pruebas y disponibilidad, escribid al correo. " +
          "Respondo el mismo día.",
    redes: [
      // { nombre: "Instagram", url: "https://instagram.com/usuario" }
    ]
  }

};
