/* =========================================================
   Adopta Me Playa — lógica del sitio
   Datos editables: data/config.json y data/animales.json
   ========================================================= */
(() => {
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

let CONFIG = null;
let ANIMALES = [];
const guardado = localStorage.getItem('idioma');
let IDIOMA = ['es', 'en'].includes(guardado)
  ? guardado
  : ((navigator.language || 'es').toLowerCase().startsWith('en') ? 'en' : 'es');

/* ---------------- Traducción ---------------- */
function t(clave, vars = {}) {
  const dic = window.TEXTOS[IDIOMA] || window.TEXTOS.es;
  let s = dic[clave] ?? window.TEXTOS.es[clave] ?? clave;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll('{' + k + '}', v);
  return s;
}

function varsGlobales() {
  return {
    refugio: CONFIG?.refugio?.nombre || '',
    ano: CONFIG?.refugio?.fundado || ''
  };
}

function aplicarTraduccion() {
  const v = varsGlobales();
  document.documentElement.lang = t('html.lang');

  $$('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n, v); });
  $$('[data-i18n-html]').forEach(el => { el.innerHTML = t(el.dataset.i18nHtml, v); });
  $$('[data-i18n-attr]').forEach(el => {
    el.dataset.i18nAttr.split('|').forEach(par => {
      const [attr, clave] = par.split(':');
      el.setAttribute(attr, t(clave, v));
    });
  });

  if (CONFIG) {
    document.title = t('meta.titulo', v);
    $('meta[name="description"]')?.setAttribute('content', t('meta.desc', v));
  }
  $$('.idioma button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.idioma === IDIOMA)));
}

/* ---------------- Utilidades ---------------- */
const num = n => new Intl.NumberFormat(IDIOMA === 'en' ? 'en-US' : 'es-MX').format(n);
/* Siempre con el sufijo MXN: en Playa mucha gente lee "$" como dólares. */
const dinero = n => `$${num(n)} MXN`;

/* L'âge est un nombre plus une unité : 4 meses, 7 anos. edad_texto ne sert
   plus qu'aux approximations qu'aucun nombre ne peut dire, comme « 6-7 años ». */
function edadTexto(animal) {
  const fijo = animal?.edad_texto?.[IDIOMA] || animal?.edad_texto?.es;
  if (fijo) return fijo;
  const n = Number(animal?.edad) || 0;
  if (!n) return t('ficha.bebe');
  if (animal?.edad_unidad === 'meses') {
    return n === 1 ? t('ficha.mes') : t('ficha.meses', { n });
  }
  return n === 1 ? t('ficha.ano') : t('ficha.anos', { n });
}

function enlaceWA(mensaje) {
  const tel = (CONFIG?.contacto?.whatsapp || '').replace(/\D/g, '');
  return `https://wa.me/${tel}?text=${encodeURIComponent(mensaje)}`;
}

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* La asociación escribe solo en español; el inglés lo traduce el panel al publicar
   y puede faltar si el servicio de traducción no respondió ese día. Un texto en
   español vale más que un hueco en la ficha. */
const txt = (a, campo) => a?.[IDIOMA]?.[campo] || a?.es?.[campo] || '';
const caracter = a => (a?.[IDIOMA]?.caracter?.length ? a[IDIOMA].caracter : a?.es?.caracter) || [];
const razaTxt = a => a?.raza?.[IDIOMA] || a?.raza?.es || '';
const adoptadoTxt = a => t(a.sexo === 'hembra' ? 'cat.adoptada' : 'cat.adoptado');

/* Tampon « ADOPTADO » : encre rouge, double cadre, posé en travers de la photo.
   L'inclinaison varie un peu d'un animal à l'autre (de -10° à -16°), comme un vrai tampon donné à la main. */
const giroSello = a => -(10 + [...String(a.id || a.nombre)].reduce((n, c) => n + c.charCodeAt(0), 0) % 7);
const selloAdoptado = a => `<span class="sello" style="--giro:${giroSello(a)}deg">
  <span class="sello__palabra">${esc(adoptadoTxt(a))}</span>
  <span class="sello__sub" aria-hidden="true">${esc(CONFIG?.refugio?.nombre || 'Adopta Me Playa')}</span></span>`;

/* Donativo sugerido por especie : config.adopcion.donacion_sugerida.perro / .gato
   = { min, max }. Un número suelto (formato antiguo) vale para las dos especies. */
function rangoDonacion(especie) {
  const d = CONFIG?.adopcion?.donacion_sugerida;
  const r = (d && typeof d === 'object') ? d[especie] : { min: d, max: d };
  const min = Number(r?.min);
  if (!Number.isFinite(min)) return '';
  const max = Number(r.max ?? r.min);
  return min === max ? dinero(min) : `$${num(min)} – $${num(max)} MXN`;
}

/* =========================================================
   Hero — la tira de cápsulas
   ========================================================= */
/* Decap gère une seule liste de photos : la première sert de portrait. */
function fotoPrincipal(a) {
  return (a.fotos && a.fotos.length ? a.fotos[0] : a.foto) || '';
}

function pintarTira() {
  const cont = $('#tira');
  cont.innerHTML = ANIMALES.filter(a => !a.adoptado).slice(0, 5).map(a => `
    <a class="capsula" href="#adoptar" data-abrir="${a.id}">
      <img class="capsula__foto" src="${esc(fotoPrincipal(a))}" alt="${esc(a.nombre)}" loading="eager" width="160" height="160">
      <span class="capsula__nombre">${esc(a.nombre)}</span>
    </a>`).join('');
}

/* =========================================================
   Catálogo
   ========================================================= */
const filtros = { especie: 'todos', tamano: new Set(), energia: new Set(), q: '' };

function coincide(a) {
  if (filtros.especie !== 'todos' && a.especie !== filtros.especie) return false;
  if (filtros.tamano.size && !filtros.tamano.has(a.tamano)) return false;
  if (filtros.energia.size && !filtros.energia.has(a.energia)) return false;
  if (filtros.q) {
    const heno = [a.nombre, txt(a, 'resumen'), ...caracter(a)].join(' ').toLowerCase();
    if (!heno.includes(filtros.q)) return false;
  }
  return true;
}

function tarjeta(a) {
  const meta = [
    t(a.sexo === 'macho' ? 'ficha.macho' : 'ficha.hembra'),
    edadTexto(a),
    a.tamano ? t('cat.' + a.tamano) : ''
  ].filter(Boolean).join(' · ');

  return `<li class="${a.adoptado ? 'es-adoptado' : ''}">
    <button class="tarjeta" type="button" data-abrir="${a.id}">
      <span class="tarjeta__marco">
        ${a.adoptado ? selloAdoptado(a)
          : (a.urgente ? `<span class="tarjeta__urgente">${esc(t('cat.urgente'))}</span>` : '')}
        <img src="${esc(fotoPrincipal(a))}" alt="${esc(a.nombre)}" loading="lazy" width="300" height="300">
      </span>
      <span class="tarjeta__nombre">${esc(a.nombre)}</span>
      <span class="tarjeta__meta">${esc(meta)}</span>
      <span class="tarjeta__resumen">${esc(txt(a, 'resumen'))}</span>
      <span class="tarjeta__pie">
        <span class="tarjeta__ver">${esc(t('cat.ver'))}</span>
        <span class="tarjeta__flecha"><svg aria-hidden="true"><use href="#i-flecha"></use></svg></span>
      </span>
    </button>
  </li>`;
}

function pintarRejilla() {
  const lista = ANIMALES.filter(coincide);
  const rejilla = $('#rejilla');

  $('#conteo').textContent = lista.length === 1 ? t('cat.conteo_uno') : t('cat.conteo', { n: lista.length });

  rejilla.innerHTML = lista.length
    ? lista.map(tarjeta).join('')
    : `<li class="vacio"><h3>${esc(t('cat.vacio_t'))}</h3><p>${esc(t('cat.vacio_d'))}</p></li>`;
}

/* Los gatos no tienen tamaño ni energía en su ficha : con «Gatos» elegido,
   esos dos filtros se ocultan (y se vacían) en vez de dejar la rejilla vacía. */
function actualizarFiltrosEspecie() {
  const soloGatos = filtros.especie === 'gato';
  $$('.filtros__grupo').forEach(g => { g.hidden = soloGatos; });
  if (soloGatos) {
    filtros.tamano.clear();
    filtros.energia.clear();
    $$('[data-filtro="tamano"],[data-filtro="energia"]').forEach(b => b.setAttribute('aria-pressed', 'false'));
  }
}

function conectarFiltros() {
  $$('[data-filtro]').forEach(btn => {
    btn.addEventListener('click', () => {
      const { filtro, valor } = btn.dataset;

      if (filtro === 'especie') {
        filtros.especie = valor;
        $$('[data-filtro="especie"]').forEach(b =>
          b.setAttribute('aria-pressed', String(b.dataset.valor === valor)));
        actualizarFiltrosEspecie();
      } else {
        const set = filtros[filtro];
        const activo = !set.has(valor);
        activo ? set.add(valor) : set.delete(valor);
        btn.setAttribute('aria-pressed', String(activo));
      }
      pintarRejilla();
    });
  });

  $('#buscar').addEventListener('input', e => {
    filtros.q = e.target.value.trim().toLowerCase();
    pintarRejilla();
  });

  $('#limpiar').addEventListener('click', () => {
    filtros.especie = 'todos';
    filtros.tamano.clear();
    filtros.energia.clear();
    filtros.q = '';
    $('#buscar').value = '';
    $$('[data-filtro]').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.filtro === 'especie' && b.dataset.valor === 'todos')));
    actualizarFiltrosEspecie();
    pintarRejilla();
  });
}

/* =========================================================
   Ficha
   ========================================================= */
let animalEnFicha = null;

function pintarFicha(a) {
  animalEnFicha = a;
  /* On n'affiche que ce qui est explicitement renseigné : pour un animal réel,
     inventer un état sanitaire serait une faute. Un champ absent ne s'affiche pas. */
  const salud = [];
  if (a.esterilizado === true) salud.push(t('ficha.esterilizado'));
  else if (a.esterilizado === false) salud.push(t('ficha.esterilizado_pendiente'));
  if (a.vacunado) salud.push(t('ficha.vacunado'));
  if (a.desparasitado) salud.push(t('ficha.desparasitado'));
  if (a.cartilla) salud.push(t('ficha.cartilla'));
  if (a.microchip) salud.push(t('ficha.microchip'));

  /* Les chats n'ont ni poids, ni taille, ni énergie : seules les tuiles renseignées s'affichent. */
  const dato = (clave, valor) =>
    `<div class="dato"><div class="dato__k">${esc(t(clave))}</div><div class="dato__v">${esc(valor)}</div></div>`;
  const datos = [
    dato('ficha.sexo', t(a.sexo === 'macho' ? 'ficha.macho' : 'ficha.hembra')),
    dato('ficha.edad', edadTexto(a)),
    a.peso_kg > 0 ? dato('ficha.peso', `${num(a.peso_kg)} kg`) : '',
    a.tamano ? dato('ficha.tamano', t('cat.' + a.tamano)) : '',
    a.energia ? dato('ficha.energia', t('cat.e_' + a.energia)) : ''
  ].join('');

  const fotos = (a.fotos && a.fotos.length ? a.fotos : (a.foto ? [a.foto] : []));
  const varias = fotos.length > 1;
  const flecha = (dir, clave) => `<button type="button" class="carrusel__flecha carrusel__flecha--${dir < 0 ? 'ant' : 'sig'}" data-carrusel="${dir}" aria-label="${esc(t(clave))}">
      <svg aria-hidden="true"><use href="#i-flecha"></use></svg></button>`;

  $('#ficha-cuerpo').innerHTML = `
    <div class="ficha__marco">
      <div class="carrusel" role="group" aria-roledescription="carrusel" aria-label="${esc(t('ficha.fotos'))}">
        <div class="carrusel__pista" id="ficha-pista" tabindex="0">
          ${fotos.map((f, i) => `<div class="carrusel__dia" role="group" aria-label="${esc(t('ficha.foto_n', { n: i + 1, total: fotos.length }))}">
            <img class="carrusel__fondo" src="${esc(f)}" alt="" aria-hidden="true"${i ? ' loading="lazy"' : ''}>
            <img class="carrusel__foto" src="${esc(f)}" alt="${esc(a.nombre)}"${i ? ' loading="lazy"' : ''} width="880" height="660"></div>`).join('')}
        </div>
        ${varias ? `${flecha(-1, 'ficha.ant')}${flecha(1, 'ficha.sig')}
        <div class="carrusel__puntos" role="group">
          ${fotos.map((_, i) => `<button type="button" class="carrusel__punto" data-ir="${i}" aria-current="${i === 0}"
            aria-label="${esc(t('ficha.foto_n', { n: i + 1, total: fotos.length }))}"></button>`).join('')}
        </div>` : ''}
        ${a.adoptado ? selloAdoptado(a) : ''}
      </div>
    </div>
    <div class="ficha__texto">
      <div class="ficha__titulo">
        <h3 id="ficha-nombre">${esc(a.nombre)}</h3>
        ${(a.urgente && !a.adoptado) ? `<span class="tarjeta__urgente" style="position:static">${esc(t('cat.urgente'))}</span>` : ''}
      </div>
      ${razaTxt(a) ? `<p class="ficha__raza">${esc(razaTxt(a))}</p>` : ''}
      <p class="ficha__resumen">${esc(txt(a, 'resumen'))}</p>

      <div class="datos">${datos}</div>

      <div class="etiquetas">
        ${caracter(a).map(c => `<span class="etiqueta">${esc(c)}</span>`).join('')}
      </div>

      <p class="ficha__historia">${esc(txt(a, 'historia'))}</p>

      ${txt(a, 'aviso') ? `<div class="aviso-animal">
        <h4><svg aria-hidden="true"><use href="#i-alerta"></use></svg>${esc(t('ficha.aviso'))}</h4>
        <p>${esc(txt(a, 'aviso'))}</p>
      </div>` : ''}

      ${salud.length ? `<div class="salud">
        <h4>${esc(t('ficha.salud'))}</h4>
        <ul>
          ${salud.map(s => `<li><svg aria-hidden="true"><use href="#i-check"></use></svg>${esc(s)}</li>`).join('')}
        </ul>
      </div>` : ''}

      ${a.adoptado ? `<div class="ficha__adoptado">
        <h4><svg aria-hidden="true"><use href="#i-corazon"></use></svg>${esc(t('ficha.adoptado_t', { nombre: a.nombre }))}</h4>
        <p>${esc(t('ficha.adoptado_d'))}</p>
        <a class="btn" href="#adoptar" data-cerrar>${esc(t('ficha.ver_otros'))}</a>
      </div>` : `<div class="ficha__pie">
        <span class="cuota">${esc(t('ficha.cuota'))}<strong>${esc(rangoDonacion(a.especie))}</strong></span>
        <a class="btn" href="#solicitud" data-elegir="${a.id}">${esc(t('ficha.adoptar', { nombre: a.nombre }))}</a>
        <a class="btn btn--claro" target="_blank" rel="noopener" href="${esc(enlaceWA(t('wa.pregunta', { nombre: a.nombre })))}">
          <svg aria-hidden="true"><use href="#i-wa"></use></svg>${esc(t('ficha.preguntar'))}
        </a>
      </div>`}
    </div>`;

  const dlg = $('#ficha');
  if (!dlg.open) { dlg.showModal(); $('#ficha-cuerpo').scrollTop = 0; }
  marcarPunto();
  $$('.carrusel__foto').forEach(img => {
    if (img.complete) ajustarFoto(img);
    else img.addEventListener('load', () => ajustarFoto(img), { once: true });
  });
}

/* Una foto nunca se recorta de más : si sus proporciones se alejan del cuadro (más de un 20 %),
   se muestra ENTERA sobre un fondo desenfocado hecho con la misma imagen. Si casi encaja,
   llena el cuadro (el recorte es mínimo). */
function ajustarFoto(img) {
  const dia = img.closest('.carrusel__dia');
  if (!dia || !img.naturalWidth || !dia.clientHeight) return;
  const cuadro = dia.clientWidth / dia.clientHeight;
  const foto = img.naturalWidth / img.naturalHeight;
  dia.classList.toggle('carrusel__dia--entera', Math.abs(foto / cuadro - 1) > 0.2);
}

/* ---- Carrusel de fotos de la ficha : desliza con el dedo (scroll-snap), flechas, puntos, teclado ---- */
function fotoActual() {
  const pista = $('#ficha-pista');
  return pista ? Math.round(pista.scrollLeft / (pista.clientWidth || 1)) : 0;
}

function irAFoto(i) {
  const pista = $('#ficha-pista');
  if (!pista) return;
  const n = pista.children.length;
  const destino = Math.max(0, Math.min(n - 1, i));
  const reducido = matchMedia('(prefers-reduced-motion: reduce)').matches;
  pista.scrollTo({ left: destino * pista.clientWidth, behavior: reducido ? 'auto' : 'smooth' });
}

function marcarPunto() {
  const i = fotoActual();
  $$('.carrusel__punto').forEach((p, k) => p.setAttribute('aria-current', String(k === i)));
  const n = $('#ficha-pista')?.children.length || 0;
  $('.carrusel__flecha--ant')?.toggleAttribute('disabled', i <= 0);
  $('.carrusel__flecha--sig')?.toggleAttribute('disabled', i >= n - 1);
}

function conectarFicha() {
  const dlg = $('#ficha');

  document.addEventListener('click', e => {
    const abrir = e.target.closest('[data-abrir]');
    if (abrir) {
      const a = ANIMALES.find(x => x.id === abrir.dataset.abrir);
      if (a) { e.preventDefault(); pintarFicha(a); }
      return;
    }
    const elegir = e.target.closest('[data-elegir]');
    if (elegir) {
      const elegido = ANIMALES.find(x => x.id === elegir.dataset.elegir);
      if (elegido) { $('#p-animal').value = elegido.nombre; sincronizarEspecie(); }
      dlg.close();
    }
    if (e.target.closest('[data-cerrar]')) dlg.close();
  });

  const cuerpo = $('#ficha-cuerpo');
  cuerpo.addEventListener('click', e => {
    const flecha = e.target.closest('[data-carrusel]');
    if (flecha) { irAFoto(fotoActual() + Number(flecha.dataset.carrusel)); return; }
    const punto = e.target.closest('[data-ir]');
    if (punto) irAFoto(Number(punto.dataset.ir));
  });
  /* scroll ne remonte pas : écouteur en capture sur le conteneur de la fiche */
  cuerpo.addEventListener('scroll', e => { if (e.target.id === 'ficha-pista') marcarPunto(); }, true);

  dlg.addEventListener('keydown', e => {
    if (!$('#ficha-pista') || e.target.closest('input,textarea,select')) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); irAFoto(fotoActual() + 1); }
    if (e.key === 'ArrowLeft')  { e.preventDefault(); irAFoto(fotoActual() - 1); }
  });

  window.addEventListener('resize', () => $$('.carrusel__foto').forEach(ajustarFoto));
  $('#ficha-cerrar').addEventListener('click', () => dlg.close());
  dlg.addEventListener('close', () => { animalEnFicha = null; });
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
}

/* =========================================================
   Pedido de formulario → FormSubmit
   Le refuge reçoit la demande, le visiteur reçoit le bon PDF.
   ========================================================= */
function llenarSelectAnimales() {
  const sel = $('#p-animal');
  const previo = sel.value;
  sel.innerHTML = `<option value="">${esc(t('sol.animal_cualquiera'))}</option>` +
    ANIMALES.filter(a => !a.adoptado).map(a => `<option value="${esc(a.nombre)}">${esc(a.nombre)} — ${esc(t(a.especie === 'gato' ? 'cat.gato' : 'cat.perro'))}</option>`).join('');
  if (previo) sel.value = previo;
}

/* L'espèce choisie suit l'animal sélectionné : on évite qu'on demande
   le formulaire chien pour un chat. */
function sincronizarEspecie() {
  const a = ANIMALES.find(x => x.nombre === $('#p-animal').value);
  if (!a) return;
  const radio = $(`.especie__btn input[value="${a.especie}"]`);
  if (radio && !radio.checked) {
    radio.checked = true;
    radio.closest('.especie')?.classList.remove('campo--error');
  }
}

/* Le PDF dépend de l'espèce ET de la langue affichée. Le lien doit être
   absolu : un chemin relatif est inutilisable depuis une boîte mail. On le
   construit sur l'origine courante, donc il suit Netlify puis le domaine
   définitif sans rien reconfigurer. */
function enlaceFormulario(especie) {
  const ruta = (CONFIG.solicitud?.formularios || {})[especie]?.[IDIOMA] || '';
  if (!ruta) return '';
  if (/^https?:\/\//i.test(ruta)) return ruta;
  const base = CONFIG.solicitud?.url_base || location.origin;
  return new URL(ruta, base.replace(/\/?$/, '/')).href;
}

function enlaceCuestionarioWeb(especie, animal) {
  const base = CONFIG.solicitud?.url_base || location.origin;
  const u = new URL('cuestionario.html', base.replace(/\/?$/, '/'));
  u.searchParams.set('especie', especie);
  u.searchParams.set('lang', IDIOMA);
  if (animal) u.searchParams.set('animal', animal);
  return u.href;
}

/* Espèces dont le questionnaire en ligne existe (rempli par iniciar). Tant
   qu'on ne sait pas, on suppose qu'il existe : la page elle-même renvoie
   vers WhatsApp s'il était vide. */
const CUESTIONARIO_WEB = {};

function textoAutoRespuesta(nombre, especie, animal) {
  const enlace = enlaceFormulario(especie);
  /* Lien wa.me cliquable plutôt qu'un numéro à recopier : le questionnaire
     rempli revient directement sur WhatsApp, ce qui sert d'alerte au refuge
     sans aucune automatisation à maintenir. */
  const vars = {
    nombre,
    refugio: CONFIG.refugio?.nombre || '',
    enlace,
    wa_enlace: 'https://wa.me/' + (CONFIG.contacto?.whatsapp || '').replace(/\D/g, ''),
    whatsapp: CONFIG.contacto?.whatsapp_visible || '',
    enlace_web: enlaceCuestionarioWeb(especie, animal)
  };
  /* PDF + web → auto_con ; web seul (cas des chats) → auto_web ; rien → auto_sin */
  const hayWeb = CUESTIONARIO_WEB[especie] !== false;
  return t(enlace ? 'sol.auto_con' : (hayWeb ? 'sol.auto_web' : 'sol.auto_sin'), vars);
}

function conectarPedido() {
  const form = $('#pedido');
  if (form && CONFIG.solicitud?.endpoint) form.action = CONFIG.solicitud.endpoint;
  const estado = $('#pedido-estado');
  const boton = $('#pedido-enviar');
  if (!form) return;

  const mostrar = (tipo, titulo, texto) => {
    estado.dataset.tipo = tipo;
    estado.innerHTML = `<h3>${esc(titulo)}</h3><p>${esc(texto)}</p>`;
    estado.classList.remove('oculto');
    estado.scrollIntoView({ block: 'nearest' });
  };

  form.addEventListener('submit', e => {
    $$('.campo--error', form).forEach(el => el.classList.remove('campo--error'));

    const especie = form.querySelector('input[name="especie"]:checked')?.value;
    if (!especie) {
      e.preventDefault();
      $('.especie', form).classList.add('campo--error');
      mostrar('err', t('sol.revisa_t'), t('sol.falta_especie'));
      $('.especie__btn input', form).focus();
      return;
    }

    const invalidos = $$('input,select', form).filter(c =>
      c.type !== 'radio' && c.type !== 'hidden' && c.name !== '_honey' && !c.checkValidity());
    if (invalidos.length) {
      e.preventDefault();
      invalidos.forEach(c => c.closest('.campo')?.classList.add('campo--error'));
      mostrar('err', t('sol.revisa_t'), t('sol.faltan_campos'));
      invalidos[0].focus();
      return;
    }

    /* Envoi natif, pas AJAX, et sans _captcha=false : FormSubmit désactive
       l'auto-réponse dans ces deux cas. C'est documenté chez eux et ça nous a
       coûté deux essais à blanc. On renseigne donc les champs techniques juste
       avant de laisser le navigateur poster le formulaire lui-même. */
    const nombre = form.nombre.value.trim();
    const apellido = form.apellido.value.trim();
    form._subject.value = `${t('sol.asunto')} — ${nombre} ${apellido}`;
    form.name.value = `${nombre} ${apellido}`;
    form._autoresponse.value = textoAutoRespuesta(nombre, especie, form.animal.value);
    form._next.value = new URL('gracias.html?lang=' + IDIOMA, location.origin + location.pathname.replace(/[^/]*$/, '')).href;

    estado.classList.add('oculto');
    boton.setAttribute('aria-busy', 'true');
    boton.querySelector('span').textContent = t('sol.enviando');
  });

  form.addEventListener('input', e => {
    e.target.closest('.campo')?.classList.remove('campo--error');
    if (e.target.name === 'especie') $('.especie', form).classList.remove('campo--error');
  });

  $('#p-animal').addEventListener('change', sincronizarEspecie);
}

/* =========================================================
   Apoyar
   ========================================================= */
function pintarApoyo() {
  const d = CONFIG.donaciones || {};
  const bloques = [];

  if (d.paypal?.activo) {
    bloques.push(`
      <article class="medio">
        <span class="medio__icono" style="background:var(--lavanda)"><svg aria-hidden="true"><use href="#i-tarjeta"></use></svg></span>
        <h3>${esc(t('ap.paypal_t'))}</h3>
        <p class="medio__cuerpo">${esc(t('ap.paypal_d'))}</p>
        <a class="btn btn--bloque" target="_blank" rel="noopener" href="${esc(d.paypal.url)}">${esc(t('ap.paypal_b'))}</a>
      </article>`);
  }

  if (d.wise?.activo) {
    const destino = d.wise.url || ('mailto:' + (CONFIG.contacto?.email || ''));
    bloques.push(`
      <article class="medio">
        <span class="medio__icono" style="background:var(--menta)"><svg aria-hidden="true"><use href="#i-globo"></use></svg></span>
        <h3>${esc(t('ap.wise_t'))}</h3>
        <p class="medio__cuerpo">${esc(t('ap.wise_d'))}</p>
        <a class="btn btn--bloque" target="_blank" rel="noopener" href="${esc(destino)}">${esc(t('ap.wise_b'))}</a>
      </article>`);
  }

  if (d.mercadopago?.activo) {
    const filas = [
      ['ap.beneficiario', d.mercadopago.titular, false],
      ['ap.clabe', d.mercadopago.clabe, true]
    ];
    bloques.push(`
      <article class="medio">
        <span class="medio__icono" style="background:var(--coral)"><svg aria-hidden="true"><use href="#i-cartera"></use></svg></span>
        <h3>${esc(t('ap.mp_t'))}</h3>
        <p class="medio__cuerpo">${esc(t('ap.mp_d'))}</p>
        <div class="medio__datos">
          ${filas.map(([k, v, copiable]) => `
            <div class="dato-copia">
              <div class="dato-copia__k">${esc(t(k))}</div>
              <div class="dato-copia__fila">
                <span class="dato-copia__v">${esc(v || '—')}</span>
                ${copiable ? `<button class="copiar" type="button" data-copiar="${esc(v || '')}">${esc(t('ap.copiar'))}</button>` : ''}
              </div>
            </div>`).join('')}
        </div>
      </article>`);
  }

  $('#medios').innerHTML = bloques.join('');


  $('#deseos').innerHTML = (CONFIG.lista_deseos || []).map(x =>
    `<li><svg aria-hidden="true"><use href="#i-caja"></use></svg>${esc(x[IDIOMA] || x.es)}</li>`).join('');

  $('#wa-deseos').href = enlaceWA(t('wa.deseos'));
  $('#wa-voluntario').href = enlaceWA(t('wa.voluntario'));
  $('#wa-hogar').href = enlaceWA(t('wa.hogar'));
  $('#wa-flotante').href = enlaceWA(t('wa.general'));
}

function conectarCopiar() {
  document.addEventListener('click', async e => {
    const btn = e.target.closest('[data-copiar]');
    if (!btn) return;
    try {
      await navigator.clipboard.writeText(btn.dataset.copiar);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = btn.dataset.copiar;
      document.body.append(ta); ta.select();
      document.execCommand('copy'); ta.remove();
    }
    const antes = btn.textContent;
    btn.textContent = t('ap.copiado');
    btn.dataset.copiado = 'si';
    setTimeout(() => { btn.textContent = antes; delete btn.dataset.copiado; }, 1800);
  });
}

/* =========================================================
   Refugio: datos de contacto y pie
   ========================================================= */
function pintarRefugio() {
  const r = CONFIG.refugio || {}, c = CONFIG.contacto || {}, redes = CONFIG.redes || {};

  $$('[data-refugio="nombre"]').forEach(el => el.textContent = r.nombre || '');
  $$('[data-refugio="nombre_corto"]').forEach(el => el.textContent = r.nombre_corto || r.nombre || '');

  const mail = $('[data-contacto="email"]');
  if (mail) { mail.textContent = c.email || ''; mail.href = 'mailto:' + (c.email || ''); }

  const wa = $('[data-contacto="wa"]');
  if (wa) { wa.textContent = 'WhatsApp ' + (c.whatsapp_visible || ''); wa.href = enlaceWA(t('wa.general')); wa.target = '_blank'; wa.rel = 'noopener'; }

  const iconos = { facebook: 'i-fb', instagram: 'i-ig' };
  $('#redes').innerHTML = Object.entries(iconos)
    .filter(([k]) => redes[k])
    .map(([k, ic]) => `<a href="${esc(redes[k])}" target="_blank" rel="noopener" aria-label="${k}"><svg aria-hidden="true"><use href="#${ic}"></use></svg></a>`)
    .join('');

  $('#ano').textContent = new Date().getFullYear();

  const ld = {
    '@context': 'https://schema.org',
    '@type': 'NGO',
    name: r.nombre,
    legalName: r.razon_social,
    address: {
      '@type': 'PostalAddress',
      addressLocality: r.ciudad,
      addressRegion: r.estado,
      addressCountry: 'MX'
    },
    telephone: '+' + (c.whatsapp || ''),
    email: c.email,
    // les clés commençant par _ sont des notes de documentation dans config.json,
    // jamais des données : les exclure partout où on itère sur les valeurs.
    sameAs: Object.entries(redes).filter(([k, v]) => !k.startsWith('_') && v).map(([, v]) => v)
  };
  const anterior = $('script[type="application/ld+json"]');
  const s = anterior || document.createElement('script');
  s.type = 'application/ld+json';
  s.textContent = JSON.stringify(ld);
  if (!anterior) document.head.append(s);
}

/* =========================================================
   Menú móvil e idioma
   ========================================================= */
function conectarInterfaz() {
  const btn = $('#menu-btn'), nav = $('#nav');

  btn.addEventListener('click', () => {
    const abierto = nav.dataset.abierto === 'si';
    nav.dataset.abierto = abierto ? 'no' : 'si';
    btn.setAttribute('aria-expanded', String(!abierto));
  });

  const cerrarMenu = () => {
    if (nav.dataset.abierto !== 'si') return;
    nav.dataset.abierto = 'no';
    btn.setAttribute('aria-expanded', 'false');
  };

  /* Un clic ailleurs, Échap ou un changement de largeur referment le menu. */
  document.addEventListener('click', e => {
    if (!e.target.closest('#nav') && !e.target.closest('#menu-btn')) cerrarMenu();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrarMenu(); });
  addEventListener('resize', cerrarMenu);
  nav.addEventListener('click', e => {
    if (e.target.tagName === 'A') { nav.dataset.abierto = 'no'; btn.setAttribute('aria-expanded', 'false'); }
  });

  $$('.idioma button').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.idioma === IDIOMA) return;
    IDIOMA = b.dataset.idioma;
    localStorage.setItem('idioma', IDIOMA);
    repintar();
  }));
}

function repintar() {
  aplicarTraduccion();
  /* La fiche est un gabarit rendu une seule fois à l'ouverture : sans ça,
     basculer ES/EN la laissait dans la langue précédente. */
  if (animalEnFicha && $('#ficha').open) {
    const desplazamiento = $('#ficha-cuerpo').scrollTop;
    pintarFicha(animalEnFicha);
    $('#ficha-cuerpo').scrollTop = desplazamiento;
  }
  pintarRejilla();
  pintarApoyo();
  pintarRefugio();
  llenarSelectAnimales();
}

/* =========================================================
   Arranque
   ========================================================= */
async function iniciar() {
  try {
    const [cfg, ani] = await Promise.all([
      fetch('data/config.json?v=47').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch('data/animales.json?v=47').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    ]);
    CONFIG = cfg;
    // Decap écrit { "animales": [...] } ; on accepte aussi l'ancien tableau nu.
    ANIMALES = Array.isArray(ani) ? ani : (ani.animales || []);
    ANIMALES.sort((a, b) => Number(!!a.adoptado) - Number(!!b.adoptado));
  } catch (err) {
    console.error('[refugio] datos no cargados:', err);
    const aviso = () => {
      const el = document.createElement('div');
      el.className = 'aviso-datos contenedor';
      el.innerHTML = `<h3>${esc(t('err.datos_t'))}</h3><p>${esc(t('err.datos_d'))}</p>
        <code>python3 -m http.server 8123</code>`;
      return el;
    };
    $('#tira').replaceWith(aviso());
    $('#rejilla').replaceWith(aviso());
    $('#conteo').textContent = t('err.datos_t');
    aplicarTraduccion();
    return;
  }

  fetch('data/cuestionario.json?v=47').then(r => r.json()).then(q => {
    for (const esp of ['perro', 'gato']) CUESTIONARIO_WEB[esp] = !!q[esp]?.secciones?.length;
  }).catch(() => {});

  aplicarTraduccion();
  pintarRefugio();
  pintarTira();
  pintarRejilla();
  pintarApoyo();
  llenarSelectAnimales();

  conectarFiltros();
  conectarFicha();
  conectarCopiar();
  conectarPedido();
  conectarInterfaz();
}

document.addEventListener('DOMContentLoaded', iniciar);
})();
