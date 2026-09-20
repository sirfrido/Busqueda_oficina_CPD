/* ═══════════════════════════════════════════════════════════════════════
   Book de Leia Cervantes — lógica de la web.
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

  var nombreCompleto = [D.nombre, D.apellidos].filter(Boolean).join(" ");

  /* ── Textos sueltos (nombre, marca, titular…) ───────────────────────── */

  function pintarTextos() {
    $$("[data-campo]").forEach(function (el) {
      var valor = D[el.dataset.campo];
      if (valor) el.textContent = valor;
      else el.remove();
    });

    if (nombreCompleto) document.title = nombreCompleto + " — Actriz";

    var foto = $("#foto-principal"), ancha = $("#portada-ancha");
    if (D.foto_principal) foto.src = D.foto_principal;
    foto.alt = nombreCompleto ? nombreCompleto + ", retrato" : "";
    if (D.portada_encuadre) foto.style.objectPosition = D.portada_encuadre;
    if (D.foto_principal_ancha) ancha.srcset = D.foto_principal_ancha;
    else ancha.remove();

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
      bloque.appendChild(crear("h3", "creditos__categoria", grupo.categoria));

      var ul = crear("ul", "creditos__lista");
      grupo.trabajos.forEach(function (t) {
        var li = document.createElement("li");
        li.appendChild(crear("span", "creditos__anio", t.anio || ""));

        var datos = document.createElement("div");
        var linea = crear("p", "creditos__trabajo");
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

  function pintarGaleria() {
    if (!fotos.length) { $("#fotos").remove(); return; }
    var galeria = $("#galeria");

    fotos.forEach(function (foto, i) {
      var fig = document.createElement("figure");

      var btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-label", "Ampliar: " + (foto.alt || "foto " + (i + 1)));
      btn.addEventListener("click", function () { abrirVisor(i); });

      var img = document.createElement("img");
      img.src = foto.archivo;
      img.alt = foto.alt || "";
      img.loading = i < 5 ? "eager" : "lazy";
      img.decoding = "async";
      if (foto.encuadre) img.style.objectPosition = foto.encuadre;

      btn.appendChild(img);
      fig.appendChild(btn);
      galeria.appendChild(fig);
    });
  }

  /* ── Visor ──────────────────────────────────────────────────────────── */

  var visor = $("#visor"), visorImg = $("#visor-img"), visorPie = $("#visor-pie");
  var indice = 0, focoPrevio = null;

  function abrirVisor(i) {
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
    if (!fotos.length) return;
    indice = (i + fotos.length) % fotos.length;
    var foto = fotos[indice];
    visorImg.src = foto.archivo;
    visorImg.alt = foto.alt || "";
    visorPie.textContent = (indice + 1) + " / " + fotos.length;

    // Precarga la anterior y la siguiente: el salto sale instantáneo
    [1, -1].forEach(function (paso) {
      var vecina = fotos[(indice + paso + fotos.length) % fotos.length];
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
      if (e.key === "Tab") {                  // el foco no se escapa del visor
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
    if (v.youtube)      fuente = { tipo: "youtube", id: idYoutube(v.youtube) };
    else if (v.vimeo)   fuente = { tipo: "vimeo",   id: idVimeo(v.vimeo) };
    else if (v.archivo) fuente = { tipo: "archivo", id: v.archivo };

    if (!fuente) {
      /* Sin vídeo todavía: se explica qué hay que rellenar */
      var aviso = crear("div", "video__aviso");
      aviso.appendChild(crear("p", null, "Aquí irá el vídeo."));
      var p = crear("p", null, "En datos.js: ");
      ["youtube", "vimeo", "archivo"].forEach(function (campo, i) {
        if (i) p.appendChild(document.createTextNode(i === 2 ? " o " : ", "));
        p.appendChild(crear("code", null, campo));
      });
      p.style.margin = "0";
      aviso.appendChild(p);
      marco.appendChild(aviso);
    } else {
      /* El reproductor no se carga hasta que se pulsa play: la página entra
         rápida y no arrastra cookies de terceros de entrada. */
      var portada = document.createElement("button");
      portada.type = "button";
      portada.className = "video__portada";
      portada.setAttribute("aria-label", "Reproducir: " + (v.titulo || "vídeo"));

      if (v.portada || fuente.tipo === "youtube") {
        var img = document.createElement("img");
        img.src = v.portada || "https://i.ytimg.com/vi/" + fuente.id + "/hqdefault.jpg";
        img.alt = ""; img.loading = "lazy";
        portada.appendChild(img);
      }

      portada.appendChild(crear("span", "video__play", "▶"));
      portada.addEventListener("click", function () { reproducir(marco, fuente, v); });
      marco.appendChild(portada);
    }

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

    if (v.destacado) { $("#video-destacado").appendChild(crearVideo(v.destacado)); hay = true; }
    (v.otros || []).forEach(function (uno) { $("#videos-lista").appendChild(crearVideo(uno)); hay = true; });

    if (!hay) $("#videos").remove();
  }

  /* ── Contacto ───────────────────────────────────────────────────────── */

  function pintarContacto() {
    var c = D.contacto || {};
    var cont = $("#contacto-datos");

    if (c.titulo)  cont.appendChild(crear("h3", "etiqueta", c.titulo));
    if (c.persona) cont.appendChild(crear("p", "contacto__persona", c.persona));
    if (c.nota)    cont.appendChild(crear("p", "contacto__nota", c.nota));

    var enlaces = crear("div", "contacto__enlaces");
    if (c.email) {
      var mail = crear("a", "boton boton--oscuro", c.email);
      mail.href = "mailto:" + c.email + "?subject=" +
        encodeURIComponent("Casting para " + (D.nombre || ""));
      enlaces.appendChild(mail);
    }
    if (c.telefono) {
      var tel = crear("a", "boton boton--oscuro", c.telefono);
      tel.href = "tel:" + c.telefono.replace(/\s/g, "");
      enlaces.appendChild(tel);
    }
    if (enlaces.children.length) cont.appendChild(enlaces);

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

  /* ── Marca en el menú la sección que se está viendo ─────────────────── */

  function conectarMenu() {
    if (!("IntersectionObserver" in window)) return;

    var espia = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) {
        if (!e.isIntersecting) return;
        $$(".barra__menu a").forEach(function (a) {
          a.classList.toggle("activo", a.getAttribute("href") === "#" + e.target.id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });

    $$("main section[id]").forEach(function (s) { espia.observe(s); });
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
})();
