/* ═══════════════════════════════════════════════════════════════════════
   Book de Leia Cervantes — motor de la web.

   Todo el contenido vive en contenido.json, que es lo que edita el panel.
   Este archivo solo lo pinta: normalmente no hay que tocarlo.
   ═══════════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };

  /* La portada apaisada la fabrica herramientas/portada.py y siempre se llama
     igual. NO se guarda en contenido.json a propósito: el panel borra del
     contenido todo campo que no aparezca en sus formularios, y así ya se
     perdió una vez, dejando la web sirviendo la foto vertical en ordenador. */
  var PORTADA_ANCHA = "portada-ancha.jpg";

  function crear(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto != null && texto !== "") el.textContent = texto;
    return el;
  }

  /* El panel guarda las rutas con barra inicial; la web las quiere sin ella */
  function ruta(v) { return String(v || "").replace(/^\//, ""); }

  function vacio(v) { return v == null || v === "" || (Array.isArray(v) && !v.length); }

  /* Un título como "Teatro y danza" se convierte en el ancla #teatro-y-danza */
  function anclaDe(texto, respaldo) {
    var a = String(texto || "").toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    return a || respaldo;
  }

  /* ── Portada ────────────────────────────────────────────────────────── */

  function pintarPortada(id) {
    var sec = crear("section", "hero");
    sec.id = "inicio";

    var picture = crear("picture", "hero__imagen");
    var fuente = document.createElement("source");
    fuente.media = "(min-aspect-ratio: 4/5)";      // pantallas apaisadas
    fuente.srcset = PORTADA_ANCHA;
    picture.appendChild(fuente);

    var img = crear("img", "hero__fondo");
    img.alt = [id.nombre, id.apellidos].filter(Boolean).join(" ") + ", retrato";
    img.setAttribute("fetchpriority", "high");

    /* Si la apaisada todavía no se ha fabricado (los dos minutos justos
       después de cambiar la foto), se cae a la vertical en vez de dejar un
       hueco roto. */
    img.addEventListener("error", function alFallar() {
      img.removeEventListener("error", alFallar);
      if (fuente.parentNode) fuente.parentNode.removeChild(fuente);
      img.src = ruta(id.portada);
    });

    img.src = ruta(id.portada);
    picture.appendChild(img);
    sec.appendChild(picture);

    var centro = crear("div", "hero__centro");
    centro.appendChild(crear("h1", "hero__nombre", id.nombre));
    if (id.apellidos) centro.appendChild(crear("p", "hero__apellidos", id.apellidos));

    var primera = $("#contenido").querySelector("section[id]");
    var boton = crear("a", "boton boton--claro", id.boton || "Ver foto book");
    boton.href = "#" + (primera ? primera.id : "contenido");
    centro.appendChild(boton);

    sec.appendChild(centro);
    $("#portada").appendChild(sec);
  }

  /* ── Barra superior ─────────────────────────────────────────────────── */

  function pintarBarra(id) {
    var barra = $("#barra");

    var marca = crear("div", "barra__marca");
    var enlace = crear("a", null, id.marca || id.nombre);
    enlace.href = "#inicio";
    marca.appendChild(enlace);
    if (id.titular) marca.appendChild(crear("span", null, id.titular));
    barra.appendChild(marca);

    var nav = crear("nav", "barra__menu");
    nav.setAttribute("aria-label", "Navegación principal");
    [].forEach.call($("#contenido").querySelectorAll("section[id]"), function (sec) {
      var a = crear("a", null, sec.dataset.menu || sec.id);
      a.href = "#" + sec.id;
      nav.appendChild(a);
    });
    barra.appendChild(nav);
    barra.hidden = false;
  }

  /* ── Armazón de sección ─────────────────────────────────────────────── */

  function seccion(id, titulo, conTitulo) {
    var sec = crear("section", conTitulo === false ? null : "seccion");
    sec.id = id;
    sec.dataset.menu = titulo;
    if (conTitulo !== false && titulo) sec.appendChild(crear("h2", "seccion__titulo", titulo));
    else if (titulo) sec.setAttribute("aria-label", titulo);
    $("#contenido").appendChild(sec);
    return sec;
  }

  /* ── Galerías ───────────────────────────────────────────────────────── */

  function pintarGaleria(destino, fotos) {
    var lista = (fotos || []).filter(function (f) { return f && f.archivo; });
    if (!lista.length) return false;

    var rejilla = crear("div", "galeria");
    lista.forEach(function (foto, i) {
      var fig = document.createElement("figure");

      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-label", "Ampliar: " + (foto.alt || "foto " + (i + 1)));
      btn.addEventListener("click", function () { abrirVisor(lista, i); });

      var img = document.createElement("img");
      img.src = ruta(foto.archivo);
      img.alt = foto.alt || "";
      img.loading = i < 4 ? "eager" : "lazy";
      img.decoding = "async";
      if (foto.encuadre) img.style.objectPosition = foto.encuadre;

      btn.appendChild(img);
      fig.appendChild(btn);
      rejilla.appendChild(fig);
    });

    destino.appendChild(rejilla);
    return true;
  }

  /* ── Visor ──────────────────────────────────────────────────────────── */

  var visor = $("#visor"), visorImg = $("#visor-img"), visorPie = $("#visor-pie");
  var album = [], indice = 0, focoPrevio = null;

  function abrirVisor(fotos, i) {
    album = fotos;
    focoPrevio = document.activeElement;
    visor.hidden = false;
    document.body.classList.add("sin-scroll");
    mostrar(i);
    $("#visor-cerrar").focus();
  }

  function cerrarVisor() {
    visor.hidden = true;
    document.body.classList.remove("sin-scroll");
    if (focoPrevio) focoPrevio.focus();
  }

  function mostrar(i) {
    if (!album.length) return;
    indice = (i + album.length) % album.length;
    var foto = album[indice];
    visorImg.src = ruta(foto.archivo);
    visorImg.alt = foto.alt || "";
    visorPie.textContent = (indice + 1) + " / " + album.length;

    // Precarga la anterior y la siguiente: el salto sale instantáneo
    [1, -1].forEach(function (paso) {
      var vecina = album[(indice + paso + album.length) % album.length];
      if (vecina) new Image().src = ruta(vecina.archivo);
    });
  }

  function conectarVisor() {
    $("#visor-cerrar").addEventListener("click", cerrarVisor);
    $("#visor-prev").addEventListener("click", function () { mostrar(indice - 1); });
    $("#visor-next").addEventListener("click", function () { mostrar(indice + 1); });
    visor.addEventListener("click", function (e) { if (e.target === visor) cerrarVisor(); });

    document.addEventListener("keydown", function (e) {
      if (visor.hidden) return;
      if (e.key === "Escape")     cerrarVisor();
      if (e.key === "ArrowLeft")  mostrar(indice - 1);
      if (e.key === "ArrowRight") mostrar(indice + 1);
      if (e.key === "Tab") {                  // el foco no se escapa del visor
        var focos = [].slice.call(visor.querySelectorAll("button"));
        var pos = focos.indexOf(document.activeElement);
        e.preventDefault();
        focos[(pos + (e.shiftKey ? -1 : 1) + focos.length) % focos.length].focus();
      }
    });

    var inicioX = null;
    visor.addEventListener("touchstart", function (e) { inicioX = e.changedTouches[0].clientX; }, { passive: true });
    visor.addEventListener("touchend", function (e) {
      if (inicioX === null) return;
      var delta = e.changedTouches[0].clientX - inicioX;
      if (Math.abs(delta) > 55) mostrar(indice + (delta < 0 ? 1 : -1));
      inicioX = null;
    }, { passive: true });
  }

  /* ── Vídeos ─────────────────────────────────────────────────────────── */

  /* Acepta tanto el ID como la URL entera pegada del navegador */
  function idYoutube(v) {
    var m = String(v).match(/(?:youtu\.be\/|v=|embed\/|shorts\/|live\/)([\w-]{6,})/);
    return m ? m[1] : String(v).trim();
  }
  function idVimeo(v) {
    var m = String(v).match(/vimeo\.com\/(?:video\/)?(\d+)/);
    return m ? m[1] : String(v).trim();
  }

  function fuenteDe(v) {
    if (v.youtube) return { tipo: "youtube", id: idYoutube(v.youtube) };
    if (v.vimeo)   return { tipo: "vimeo",   id: idVimeo(v.vimeo) };
    if (v.archivo) return { tipo: "archivo", id: ruta(v.archivo) };
    return null;
  }

  function crearVideo(v) {
    var fuente = fuenteDe(v);
    if (!fuente) return null;                  // vídeo sin rellenar: no se pinta

    var art = crear("article", "video");
    var marco = crear("div", "video__marco");

    /* El reproductor no se carga hasta que se pulsa play: la página entra
       rápida y no arrastra cookies de terceros de entrada. */
    var portada = document.createElement("button");
    portada.type = "button";
    portada.className = "video__portada";
    portada.setAttribute("aria-label", "Reproducir: " + (v.titulo || "vídeo"));

    if (v.portada || fuente.tipo === "youtube") {
      var img = document.createElement("img");
      img.src = v.portada ? ruta(v.portada)
                          : "https://i.ytimg.com/vi/" + fuente.id + "/hqdefault.jpg";
      img.alt = ""; img.loading = "lazy";
      // Si la miniatura no carga, mejor el fondo liso que un icono roto
      img.addEventListener("error", function () { img.remove(); });
      portada.appendChild(img);
    }

    portada.appendChild(crear("span", "video__play", "▶"));
    portada.addEventListener("click", function () { reproducir(marco, fuente, v); });
    marco.appendChild(portada);

    art.appendChild(marco);
    if (v.titulo)      art.appendChild(crear("h3", "video__titulo", v.titulo));
    if (v.descripcion) art.appendChild(crear("p", "video__desc", v.descripcion));
    return art;
  }

  function reproducir(marco, fuente, v) {
    marco.textContent = "";

    if (fuente.tipo === "archivo") {
      var video = document.createElement("video");
      video.src = fuente.id;
      video.controls = true; video.autoplay = true; video.playsInline = true;
      if (v.portada) video.poster = ruta(v.portada);
      marco.appendChild(video);
      return;
    }

    var iframe = document.createElement("iframe");
    iframe.src = fuente.tipo === "youtube"
      ? "https://www.youtube-nocookie.com/embed/" + fuente.id + "?autoplay=1&rel=0&modestbranding=1"
      : "https://player.vimeo.com/video/" + fuente.id + "?autoplay=1";
    iframe.title = v.titulo || "Vídeo";
    iframe.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen";
    iframe.allowFullscreen = true;
    marco.appendChild(iframe);
  }

  function pintarVideos(destino, destacado, otros) {
    var hay = false;

    if (destacado) {
      var uno = crearVideo(destacado);
      if (uno) { destino.appendChild(uno); hay = true; }
    }

    var rejilla = crear("div", "videos");
    (otros || []).forEach(function (v) {
      var art = crearVideo(v);
      if (art) { rejilla.appendChild(art); hay = true; }
    });
    if (rejilla.children.length) destino.appendChild(rejilla);

    return hay;
  }

  /* ── Experiencia ────────────────────────────────────────────────────── */

  function pintarExperiencia(e) {
    if (vacio(e.ficha) && vacio(e.creditos) && vacio(e.intro)) return;
    var sec = seccion("experiencia", e.titulo || "Experiencia");

    if (e.intro) sec.appendChild(crear("p", "seccion__lead", e.intro));

    var caja = crear("div", "experiencia");
    var lado = crear("aside", "ficha");
    lado.setAttribute("aria-label", "Ficha de la actriz");

    function bloque(titulo, pares, clave, valor) {
      if (vacio(pares)) return;
      var div = crear("div");
      div.appendChild(crear("h3", "etiqueta", titulo));
      var dl = document.createElement("dl");
      pares.forEach(function (p) {
        if (!p[clave]) return;
        dl.appendChild(crear("dt", null, p[clave]));
        dl.appendChild(crear("dd", null, p[valor]));
      });
      div.appendChild(dl);
      lado.appendChild(div);
    }

    bloque("Ficha", e.ficha, "campo", "valor");
    bloque("Idiomas", e.idiomas, "idioma", "nivel");

    if (!vacio(e.habilidades)) {
      var div = crear("div");
      div.appendChild(crear("h3", "etiqueta", "Habilidades"));
      var ul = crear("ul", "habilidades");
      e.habilidades.forEach(function (h) { if (h) ul.appendChild(crear("li", null, h)); });
      div.appendChild(ul);
      lado.appendChild(div);
    }

    if (lado.children.length) caja.appendChild(lado);

    var creditos = crear("div", "creditos");
    (e.creditos || []).forEach(function (grupo) {
      if (vacio(grupo.trabajos)) return;
      var bloq = crear("div", "creditos__grupo");
      bloq.appendChild(crear("h3", "creditos__categoria", grupo.categoria));

      var ul = crear("ul", "creditos__lista");
      grupo.trabajos.forEach(function (t) {
        if (!t.titulo && !t.anio) return;
        var li = document.createElement("li");
        li.appendChild(crear("span", "creditos__anio", t.anio || ""));

        var datos = document.createElement("div");
        var linea = crear("p", "creditos__trabajo", t.titulo || "");
        if (t.personaje) {
          linea.appendChild(document.createTextNode(" — "));
          linea.appendChild(crear("span", "creditos__personaje", t.personaje));
        }
        datos.appendChild(linea);

        var meta = [];
        if (t.direccion)  meta.push("Dir. " + t.direccion);
        if (t.productora) meta.push(t.productora);
        if (t.nota)       meta.push(t.nota);
        if (meta.length) datos.appendChild(crear("p", "creditos__meta", meta.join(" · ")));

        li.appendChild(datos);
        ul.appendChild(li);
      });

      bloq.appendChild(ul);
      creditos.appendChild(bloq);
    });

    if (creditos.children.length) caja.appendChild(creditos);
    if (caja.children.length) sec.appendChild(caja);
  }

  /* ── Contacto ───────────────────────────────────────────────────────── */

  function pintarContacto(c, nombre) {
    if (vacio(c.email) && vacio(c.telefono) && vacio(c.persona)) return;
    var sec = seccion("contacto", c.titulo || "Contacto");
    var caja = crear("div", "contacto");

    if (c.etiqueta) caja.appendChild(crear("h3", "etiqueta", c.etiqueta));
    if (c.persona)  caja.appendChild(crear("p", "contacto__persona", c.persona));
    if (c.nota)     caja.appendChild(crear("p", "contacto__nota", c.nota));

    var enlaces = crear("div", "contacto__enlaces");
    if (c.email) {
      var mail = crear("a", "boton boton--oscuro", c.email);
      mail.href = "mailto:" + c.email + "?subject=" + encodeURIComponent("Casting para " + (nombre || ""));
      enlaces.appendChild(mail);
    }
    if (c.telefono) {
      var tel = crear("a", "boton boton--oscuro", c.telefono);
      tel.href = "tel:" + c.telefono.replace(/\s/g, "");
      enlaces.appendChild(tel);
    }
    if (enlaces.children.length) caja.appendChild(enlaces);

    if (!vacio(c.redes)) {
      var redes = crear("div", "contacto__redes");
      c.redes.forEach(function (r) {
        if (!r.url) return;
        var a = crear("a", null, r.nombre || r.url);
        a.href = r.url; a.target = "_blank"; a.rel = "noopener";
        redes.appendChild(a);
      });
      if (redes.children.length) caja.appendChild(redes);
    }

    sec.appendChild(caja);
  }

  /* ── Pie ────────────────────────────────────────────────────────────── */

  function pintarPie(id) {
    var pie = $("#pie");
    pie.appendChild(crear("p", null,
      (id.marca || id.nombre) + " · © " + new Date().getFullYear()));
    pie.appendChild(crear("p", null,
      "Las imágenes y los vídeos de esta web no pueden reproducirse sin autorización."));
    pie.hidden = false;
  }

  /* ── Marca en el menú la sección que se está viendo ─────────────────── */

  function conectarMenu() {
    if (!("IntersectionObserver" in window)) return;

    var espia = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        [].forEach.call(document.querySelectorAll(".barra__menu a"), function (a) {
          a.classList.toggle("activo", a.getAttribute("href") === "#" + e.target.id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });

    [].forEach.call($("#contenido").querySelectorAll("section[id]"), function (s) { espia.observe(s); });
  }

  /* ── Montaje ────────────────────────────────────────────────────────── */

  function pintar(D) {
    var id = D.identidad || {};

    // 1. Foto book
    var fb = D.foto_book || {};
    if (!vacio(fb.fotos)) {
      var sFotos = seccion("fotos", fb.titulo || "Foto book", false);
      pintarGaleria(sFotos, fb.fotos);
    }

    // 2. Video book
    var vb = D.video_book || {};
    var sVideos = seccion("videos", vb.titulo || "Video book");
    if (!pintarVideos(sVideos, vb.destacado, vb.videos)) sVideos.remove();

    // 3. Secciones añadidas desde el panel (teatro, danza, lo que haga falta)
    (D.secciones || []).forEach(function (s, i) {
      if (!s.titulo) return;
      var sec = seccion(anclaDe(s.titulo, "seccion-" + (i + 1)), s.titulo);
      var algo = false;
      if (s.texto) { sec.appendChild(crear("p", "seccion__lead", s.texto)); algo = true; }
      if (pintarGaleria(sec, s.fotos)) algo = true;
      if (pintarVideos(sec, null, s.videos)) algo = true;
      if (!algo) sec.remove();
    });

    // 4. Experiencia y contacto
    if (D.experiencia) pintarExperiencia(D.experiencia);
    if (D.contacto)    pintarContacto(D.contacto, id.nombre);

    // 5. Marco: portada, barra y pie
    if (id.portada) pintarPortada(id);
    pintarBarra(id);
    pintarPie(id);

    var nombre = [id.nombre, id.apellidos].filter(Boolean).join(" ");
    if (nombre) document.title = nombre + " — " + (id.titular || "Actriz");

    conectarVisor();
    conectarMenu();
  }

  function error(mensaje) {
    var p = crear("p", "aviso", mensaje);
    $("#contenido").appendChild(p);
  }

  /* Si la página trae el contenido incrustado (vistas previas, copias para
     abrir con doble clic), se usa ese y no se pide nada al servidor. */
  var incrustado = document.getElementById("contenido-json");
  if (incrustado) {
    try { return pintar(JSON.parse(incrustado.textContent)); }
    catch (e) { error("El contenido incrustado no es válido (" + e.message + ")."); return; }
  }

  fetch("contenido.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(pintar)
    .catch(function (e) {
      if (location.protocol === "file:") {
        error("Para ver la web en tu ordenador hace falta un servidor local; " +
              "abierta con doble clic, el navegador no deja leer contenido.json. " +
              "Lo más fácil es mirarla directamente en la web publicada.");
      } else {
        error("No se ha podido cargar el contenido (" + e.message + ").");
      }
    });
})();
