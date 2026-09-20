/* ═══════════════════════════════════════════════════════════════════════
   Book de Leia — lógica de la web.
   No hace falta tocar este archivo: todo el contenido está en datos.js.
   ═══════════════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  var D = window.DATOS || {};
  var $  = function (sel) { return document.querySelector(sel); };
  var $$ = function (sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); };

  function crear(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto != null && texto !== "") el.textContent = texto;
    return el;
  }

  /* ── Textos sueltos (nombre, titular, presentación…) ────────────────── */

  function pintarTextos() {
    $$("[data-campo]").forEach(function (el) {
      var valor = D[el.dataset.campo];
      if (valor) el.textContent = valor;
      else if (el.dataset.campo === "apellidos") el.remove();
    });

    document.title = [D.nombre, D.apellidos].filter(Boolean).join(" ") + " — Book de actriz";

    if (D.foto_principal) {
      var foto = $("#foto-principal");
      foto.src = D.foto_principal;
      foto.alt = [D.nombre, D.apellidos].filter(Boolean).join(" ") + ", foto principal";
    }

    var lista = $("#chips-hero");
    (D.chips || []).forEach(function (t) { lista.appendChild(crear("li", null, t)); });

    if (D.cv_pdf) {
      var boton = $("#boton-cv");
      boton.href = D.cv_pdf;
      boton.setAttribute("download", "");
      boton.hidden = false;
    }

    $("#anio").textContent = new Date().getFullYear();
  }

  /* ── Ficha, idiomas y habilidades ───────────────────────────────────── */

  function pintarFicha() {
    var dl = $("#ficha-datos");
    Object.keys(D.ficha || {}).forEach(function (clave) {
      if (!D.ficha[clave]) return;
      dl.appendChild(crear("dt", null, clave));
      dl.appendChild(crear("dd", null, D.ficha[clave]));
    });

    if ((D.idiomas || []).length) {
      var dlIdiomas = $("#ficha-idiomas");
      D.idiomas.forEach(function (i) {
        dlIdiomas.appendChild(crear("dt", null, i.nombre));
        dlIdiomas.appendChild(crear("dd", null, i.nivel));
      });
      $("#bloque-idiomas").hidden = false;
    }

    if ((D.habilidades || []).length) {
      var ul = $("#ficha-habilidades");
      D.habilidades.forEach(function (h) { ul.appendChild(crear("li", null, h)); });
      $("#bloque-habilidades").hidden = false;
    }
  }

  /* ── Créditos ───────────────────────────────────────────────────────── */

  function pintarCreditos() {
    var cont = $("#creditos");

    (D.creditos || []).forEach(function (grupo) {
      if (!grupo.trabajos || !grupo.trabajos.length) return;

      var bloque = crear("div", "creditos__grupo");
      bloque.appendChild(crear("h3", "creditos__titulo", grupo.categoria));

      var ul = crear("ul", "creditos__lista");
      grupo.trabajos.forEach(function (t) {
        var li = document.createElement("li");
        li.appendChild(crear("span", "creditos__anio", t.anio || ""));

        var datos = document.createElement("div");
        var linea = crear("p", "creditos__titulo-trabajo");
        linea.textContent = t.titulo || "";
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

      bloque.appendChild(ul);
      cont.appendChild(bloque);
    });
  }

  /* ── Foto book ──────────────────────────────────────────────────────── */

  var fotos = (D.fotos || []).filter(function (f) { return f && f.archivo; });
  var visibles = fotos.slice();

  function pintarGaleria() {
    var galeria = $("#galeria");
    if (!fotos.length) { $("#fotos").remove(); return; }

    fotos.forEach(function (foto, i) {
      var fig = document.createElement("figure");
      fig.dataset.tipo = foto.tipo || "";

      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-label", "Ampliar: " + (foto.alt || "foto " + (i + 1)));
      btn.addEventListener("click", function () { abrirVisor(visibles.indexOf(foto)); });

      var img = document.createElement("img");
      img.src = foto.archivo;
      img.alt = foto.alt || "";
      img.loading = i < 3 ? "eager" : "lazy";
      img.decoding = "async";

      btn.appendChild(img);
      fig.appendChild(btn);
      if (foto.tipo) fig.appendChild(crear("figcaption", null, foto.tipo));
      galeria.appendChild(fig);
    });

    pintarFiltros();
  }

  function pintarFiltros() {
    var tipos = [];
    fotos.forEach(function (f) { if (f.tipo && tipos.indexOf(f.tipo) === -1) tipos.push(f.tipo); });
    if (tipos.length < 2) return;

    var cont = $("#filtros-fotos");
    ["Todas"].concat(tipos).forEach(function (tipo, i) {
      var btn = crear("button", "filtro", tipo);
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.setAttribute("aria-selected", i === 0 ? "true" : "false");
      btn.addEventListener("click", function () { filtrar(tipo, btn); });
      cont.appendChild(btn);
    });
  }

  function filtrar(tipo, boton) {
    $$("#filtros-fotos .filtro").forEach(function (b) {
      b.setAttribute("aria-selected", String(b === boton));
    });

    visibles = tipo === "Todas" ? fotos.slice() : fotos.filter(function (f) { return f.tipo === tipo; });

    $$("#galeria figure").forEach(function (fig) {
      fig.hidden = !(tipo === "Todas" || fig.dataset.tipo === tipo);
    });
  }

  /* ── Visor a pantalla completa ──────────────────────────────────────── */

  var visor = $("#visor"), visorImg = $("#visor-img"), visorPie = $("#visor-pie");
  var indice = 0, focoPrevio = null;

  function abrirVisor(i) {
    if (i < 0) i = 0;
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
    if (!visibles.length) return;
    indice = (i + visibles.length) % visibles.length;
    var foto = visibles[indice];
    visorImg.src = foto.archivo;
    visorImg.alt = foto.alt || "";
    visorPie.textContent = (foto.tipo ? foto.tipo + " · " : "") + (indice + 1) + " / " + visibles.length;

    // Precarga la siguiente y la anterior para que el salto sea instantáneo
    [1, -1].forEach(function (paso) {
      var vecina = visibles[(indice + paso + visibles.length) % visibles.length];
      if (vecina) new Image().src = vecina.archivo;
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
      if (e.key === "Tab") {            // el foco no se escapa del visor
        var focos = $$("#visor button");
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

  /* ── Video book ─────────────────────────────────────────────────────── */

  /* Acepta tanto el ID como la URL entera pegada del navegador */
  function idYoutube(v) {
    var m = String(v).match(/(?:youtu\.be\/|v=|embed\/|shorts\/)([\w-]{6,})/);
    return m ? m[1] : String(v).trim();
  }
  function idVimeo(v) {
    var m = String(v).match(/vimeo\.com\/(?:video\/)?(\d+)/);
    return m ? m[1] : String(v).trim();
  }

  function crearVideo(v) {
    var art = crear("article", "video");
    var marco = crear("div", "video__marco");

    var fuente = null;
    if (v.youtube) fuente = { tipo: "youtube", id: idYoutube(v.youtube) };
    else if (v.vimeo) fuente = { tipo: "vimeo", id: idVimeo(v.vimeo) };
    else if (v.archivo) fuente = { tipo: "archivo", id: v.archivo };

    if (!fuente) {
      /* Sin vídeo todavía: se explica qué hay que rellenar */
      var aviso = crear("div", "video__aviso");
      aviso.appendChild(crear("strong", null, "Falta el vídeo"));
      var p = crear("p", null, "En datos.js, rellena ");
      p.appendChild(crear("code", null, "youtube"));
      p.appendChild(document.createTextNode(", "));
      p.appendChild(crear("code", null, "vimeo"));
      p.appendChild(document.createTextNode(" o "));
      p.appendChild(crear("code", null, "archivo"));
      p.appendChild(document.createTextNode("."));
      p.style.margin = "0";
      aviso.appendChild(p);
      marco.appendChild(aviso);
    } else {
      /* Portada: el reproductor no se carga hasta que se pulsa play.
         Así la web va rápida y no se cargan cookies de terceros de entrada. */
      var portada = document.createElement("button");
      portada.type = "button";
      portada.className = "video__portada";
      portada.setAttribute("aria-label", "Reproducir: " + (v.titulo || "vídeo"));

      if (v.portada) {
        var img = document.createElement("img");
        img.src = v.portada; img.alt = ""; img.loading = "lazy";
        portada.appendChild(img);
      } else if (fuente.tipo === "youtube") {
        var miniatura = document.createElement("img");
        miniatura.src = "https://i.ytimg.com/vi/" + fuente.id + "/hqdefault.jpg";
        miniatura.alt = ""; miniatura.loading = "lazy";
        portada.appendChild(miniatura);
      }

      portada.appendChild(crear("span", "video__play", "▶"));
      portada.addEventListener("click", function () { reproducir(marco, fuente, v); });
      marco.appendChild(portada);
    }

    art.appendChild(marco);
    if (v.titulo) {
      art.appendChild(crear("h3", "video__titulo", v.titulo));
    }
    if (v.descripcion) art.appendChild(crear("p", "video__desc", v.descripcion));
    return art;
  }

  function reproducir(marco, fuente, v) {
    marco.textContent = "";

    if (fuente.tipo === "archivo") {
      var video = document.createElement("video");
      video.src = fuente.id;
      video.controls = true; video.autoplay = true; video.playsInline = true;
      if (v.portada) video.poster = v.portada;
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

  function pintarVideos() {
    var v = D.videos || {};
    var hay = false;

    if (v.destacado) {
      $("#video-destacado").appendChild(crearVideo(v.destacado));
      hay = true;
    }
    (v.otros || []).forEach(function (uno) {
      $("#videos-lista").appendChild(crearVideo(uno));
      hay = true;
    });

    if (!hay) $("#videos").remove();
  }

  /* ── Contacto ───────────────────────────────────────────────────────── */

  function pintarContacto() {
    var c = D.contacto || {};
    var cont = $("#contacto-datos");

    cont.appendChild(crear("h3", null, c.titulo || "Contacto"));
    if (c.persona) cont.appendChild(crear("p", "contacto__persona", c.persona));
    if (c.nota)    cont.appendChild(crear("p", "contacto__nota", c.nota));

    var enlaces = crear("div", "contacto__enlaces");
    if (c.email) {
      var mail = crear("a", "boton boton--solido", c.email);
      mail.href = "mailto:" + c.email + "?subject=" +
        encodeURIComponent("Casting para " + (D.nombre || ""));
      enlaces.appendChild(mail);
    }
    if (c.telefono) {
      var tel = crear("a", "boton", c.telefono);
      tel.href = "tel:" + c.telefono.replace(/\s/g, "");
      enlaces.appendChild(tel);
    }
    cont.appendChild(enlaces);

    if ((c.redes || []).length) {
      var redes = crear("div", "contacto__redes");
      c.redes.forEach(function (r) {
        var a = crear("a", null, r.nombre);
        a.href = r.url; a.target = "_blank"; a.rel = "noopener";
        redes.appendChild(a);
      });
      cont.appendChild(redes);
    }
  }

  /* ── Menú, navegación y animaciones ─────────────────────────────────── */

  function conectarMenu() {
    var btn = $("#menu-btn"), menu = $("#menu");

    btn.addEventListener("click", function () {
      var abierto = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!abierto));
      btn.setAttribute("aria-label", abierto ? "Abrir menú" : "Cerrar menú");
      menu.classList.toggle("menu--abierto", !abierto);
    });

    $$("#menu a").forEach(function (a) {
      a.addEventListener("click", function () {
        btn.setAttribute("aria-expanded", "false");
        menu.classList.remove("menu--abierto");
      });
    });

    var cabecera = $("#cabecera");
    addEventListener("scroll", function () {
      cabecera.classList.toggle("cabecera--pegada", scrollY > 12);
    }, { passive: true });
  }

  function conectarObservadores() {
    if (!("IntersectionObserver" in window)) return;

    /* Marca en el menú la sección que se está viendo */
    var secciones = $$("main section[id]");
    var espia = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        $$("#menu a").forEach(function (a) {
          a.classList.toggle("activo", a.getAttribute("href") === "#" + e.target.id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    secciones.forEach(function (s) { espia.observe(s); });

    /* Aparición suave de los bloques al bajar */
    var revelador = new IntersectionObserver(function (entradas, obs) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add("revelar--visible");
        obs.unobserve(e.target);
      });
    }, { rootMargin: "0px 0px -8% 0px" });

    $$(".seccion__cabecera, .ficha, .creditos__grupo, .galeria figure, .video, .contacto")
      .forEach(function (el) { el.classList.add("revelar"); revelador.observe(el); });
  }

  /* ── Arranque ───────────────────────────────────────────────────────── */

  pintarTextos();
  pintarFicha();
  pintarCreditos();
  pintarGaleria();
  pintarVideos();
  pintarContacto();
  conectarVisor();
  conectarMenu();
  conectarObservadores();
})();
