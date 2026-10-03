/* =========================================================
   Cuestionario de adopción — page web du questionnaire PDF.
   Les questions viennent de data/cuestionario.json : le refuge
   peut les modifier sans toucher à ce fichier.
   ========================================================= */
(() => {
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const params = new URLSearchParams(location.search);
const guardado = localStorage.getItem('idioma');
let IDIOMA = ['es', 'en'].includes(params.get('lang')) ? params.get('lang')
           : (['es', 'en'].includes(guardado) ? guardado : 'es');

const ESPECIE = ['perro', 'gato'].includes(params.get('especie')) ? params.get('especie') : 'perro';

let CONFIG = null, CUESTIONARIO = null;

function t(clave, vars = {}) {
  const dic = window.TEXTOS[IDIOMA] || window.TEXTOS.es;
  let s = dic[clave] ?? window.TEXTOS.es[clave] ?? clave;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll('{' + k + '}', v);
  return s;
}

const enlaceWA = msg =>
  `https://wa.me/${(CONFIG?.contacto?.whatsapp || '').replace(/\D/g, '')}?text=${encodeURIComponent(msg)}`;

/* ---------------- Rendu des questions ---------------- */
function campo(p) {
  const id = `q${String(p.n).padStart(2, '0')}`;
  const etiqueta = esc(p[IDIOMA] || p.es);

  if (p.tipo === 'sino') {
    return `<div class="cue-p" data-q="${id}">
      <p class="cue-p__label"><span class="cue-p__n">${p.n}</span>${etiqueta}</p>
      <div class="cue-sino">
        <label class="cue-sino__op"><input type="radio" name="${id}" value="si" required><span>${esc(t('cue.si'))}</span></label>
        <label class="cue-sino__op"><input type="radio" name="${id}" value="no" required><span>${esc(t('cue.no'))}</span></label>
      </div>
      <input class="cue-comentario" name="${id}_c" data-i18n-attr="placeholder:cue.comentario" placeholder="${esc(t('cue.comentario'))}">
    </div>`;
  }

  const control = p.tipo === 'largo'
    ? `<textarea id="${id}" name="${id}" required rows="3"></textarea>`
    : `<input id="${id}" name="${id}" required>`;

  return `<div class="cue-p" data-q="${id}">
    <label class="cue-p__label" for="${id}"><span class="cue-p__n">${p.n}</span>${etiqueta}</label>
    ${control}
  </div>`;
}

function pintar() {
  const bloque = CUESTIONARIO[ESPECIE];
  const secciones = bloque?.secciones || [];

  if (!secciones.length) {                 // questionnaire chat pas encore prêt
    $('#cue-no-disponible').hidden = false;
    $('#cue-wa-sin').href = enlaceWA(t('wa.general'));
    return;
  }

  $('#cue-form').hidden = false;
  $('#cue-progreso').hidden = false;
  $('#cue-intro').textContent = bloque.intro?.[IDIOMA] || bloque.intro?.es || '';

  $('#cue-secciones').innerHTML = secciones.map((s, i) => `
    <fieldset class="bloque cue-seccion">
      <legend><span class="cue-seccion__n">${i + 1}</span>${esc(s[IDIOMA] || s.es)}</legend>
      ${s.preguntas.map(campo).join('')}
    </fieldset>`).join('');

  const pdf = (CONFIG.solicitud?.formularios || {})[ESPECIE]?.[IDIOMA] || '';
  const enlacePdf = $('#cue-pdf');
  if (pdf) { enlacePdf.href = pdf; enlacePdf.parentElement.hidden = false; }
  else enlacePdf.parentElement.hidden = true;

  actualizarProgreso();
}

/* ---------------- Progression ---------------- */
function obligatorios() {
  return $$('#cue-secciones .cue-p').map(p => {
    const radios = $$('input[type="radio"]', p);
    if (radios.length) return { el: p, lleno: radios.some(r => r.checked) };
    const c = $('input,textarea', p);
    return { el: p, lleno: !!c.value.trim() };
  });
}

function actualizarProgreso() {
  const lista = obligatorios();
  const hechas = lista.filter(x => x.lleno).length;
  const total = lista.length;
  $('#cue-barra').style.width = total ? `${Math.round(hechas / total * 100)}%` : '0%';
  $('#cue-progreso-txt').textContent = t('cue.progreso', { hechas, total });
}

/* ---------------- Mise en forme pour l'e-mail ---------------- */
function textoCuestionario() {
  const lineas = [];
  for (const s of CUESTIONARIO[ESPECIE].secciones) {
    lineas.push('', `== ${(s[IDIOMA] || s.es).toUpperCase()} ==`);
    for (const p of s.preguntas) {
      const id = `q${String(p.n).padStart(2, '0')}`;
      const etiqueta = p[IDIOMA] || p.es;
      if (p.tipo === 'sino') {
        const sel = $(`input[name="${id}"]:checked`);
        const com = $(`input[name="${id}_c"]`).value.trim();
        lineas.push(`${p.n}. ${etiqueta}`,
                    `   > ${sel ? t(sel.value === 'si' ? 'cue.si' : 'cue.no') : '—'}${com ? ` · ${com}` : ''}`);
      } else {
        lineas.push(`${p.n}. ${etiqueta}`, `   > ${$(`#${id}`).value.trim() || '—'}`);
      }
    }
  }
  return lineas.join('\n').trim();
}

/* ---------------- Envoi ---------------- */
function conectarEnvio() {
  const form = $('#cue-form');
  const estado = $('#cue-estado');
  const boton = $('#cue-enviar');
  form.action = CONFIG.solicitud?.endpoint || '';

  const avisar = (titulo, texto) => {
    estado.dataset.tipo = 'err';
    estado.innerHTML = `<h3>${esc(titulo)}</h3><p>${esc(texto)}</p>`;
    estado.classList.remove('oculto');
  };

  form.addEventListener('submit', e => {
    $$('.cue-p--error').forEach(el => el.classList.remove('cue-p--error'));
    $$('.campo--error').forEach(el => el.classList.remove('campo--error'));

    const faltan = obligatorios().filter(x => !x.lleno);
    if (faltan.length) {
      e.preventDefault();
      faltan.forEach(x => x.el.classList.add('cue-p--error'));
      avisar(t('cue.revisa'), faltan.length === 1 ? t('cue.faltan_1') : t('cue.faltan', { n: faltan.length }));
      faltan[0].el.scrollIntoView({ block: 'center' });
      return;
    }

    const email = $('#cue-email');
    if (!email.checkValidity()) {
      e.preventDefault();
      email.closest('.campo').classList.add('campo--error');
      avisar(t('cue.revisa'), t('sol.faltan_campos'));
      email.focus();
      return;
    }

    if (!$('#cue-acepto').checked) {
      e.preventDefault();
      avisar(t('cue.revisa'), t('cue.falta_acepto'));
      $('#cue-acepto').focus();
      return;
    }

    /* Tout part dans un seul champ texte : 44 réponses en champs séparés
       donneraient un e-mail illisible, et des noms de champs accentués
       nous ont déjà coûté une auto-réponse perdue. */
    const nombre = $('#q01').value.trim();
    const animal = $('#cue-animal').value.trim();
    const cabecera = [
      `${t('cue.animal')} ${animal || '—'}`,
      `${t('cue.fecha')}: ${$('#cue-fecha').value || '—'}`,
      `${t('cue.email')}: ${email.value.trim()}`,
      `${t('cue.lugar')}: ${$('#cue-lugar').value.trim() || '—'}`,
      `${t('cue.declaracion')} → ${t('cue.acepto')}`,
    ].join('\n');

    form._subject.value = `${t('cue.asunto')} — ${nombre}${animal ? ' · ' + animal : ''}`;
    form.name.value = nombre;
    form.Animal.value = animal || '—';
    form.Cuestionario.value = `${cabecera}\n\n${textoCuestionario()}`;
    form._autoresponse.value = t('cue.auto', {
      nombre,
      refugio: CONFIG.refugio?.nombre || '',
      wa_enlace: enlaceWA(t('wa.general'))
    });

    const wa = t('cue.wa_msg', {
      nombre,
      animal: animal ? t('cue.wa_msg_animal', { animal }) : ''
    });
    form._next.value = new URL(
      `gracias.html?lang=${IDIOMA}&de=cuestionario&wa=${encodeURIComponent(wa)}`,
      location.href).href;

    // le champ email doit porter ce nom exact : FormSubmit y lit le destinataire
    const oculto = document.createElement('input');
    oculto.type = 'hidden'; oculto.name = 'email'; oculto.value = email.value.trim();
    form.append(oculto);

    estado.classList.add('oculto');
    boton.setAttribute('aria-busy', 'true');
    boton.querySelector('span').textContent = t('cue.enviando');
  });

  form.addEventListener('input', e => {
    e.target.closest('.cue-p')?.classList.remove('cue-p--error');
    e.target.closest('.campo')?.classList.remove('campo--error');
    actualizarProgreso();
  });
  form.addEventListener('change', actualizarProgreso);
}

/* ---------------- Traduction de la page ---------------- */
function aplicarTraduccion() {
  document.documentElement.lang = t('html.lang');
  document.title = `${t('cue.titulo')} | ${CONFIG?.refugio?.nombre || ''}`;
  $$('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  $$('[data-i18n-attr]').forEach(el => {
    el.dataset.i18nAttr.split('|').forEach(par => {
      const [attr, clave] = par.split(':');
      el.setAttribute(attr, t(clave));
    });
  });
  $$('[data-refugio="nombre"]').forEach(el => el.textContent = CONFIG?.refugio?.nombre || '');
  $$('.idioma button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.idioma === IDIOMA)));
}

/* ---------------- Arranque ---------------- */
async function iniciar() {
  try {
    [CONFIG, CUESTIONARIO] = await Promise.all([
      fetch('data/config.json?v=47').then(r => r.json()),
      fetch('data/cuestionario.json?v=47').then(r => r.json())
    ]);
  } catch (err) {
    console.error('[cuestionario]', err);
    return;
  }

  aplicarTraduccion();
  pintar();
  if (!$('#cue-form').hidden) conectarEnvio();

  const animal = params.get('animal');
  if (animal) $('#cue-animal').value = animal;
  $('#cue-fecha').value = new Date().toISOString().slice(0, 10);

  $$('.idioma button').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.idioma === IDIOMA) return;
    IDIOMA = b.dataset.idioma;
    localStorage.setItem('idioma', IDIOMA);
    const u = new URL(location.href);
    u.searchParams.set('lang', IDIOMA);
    location.replace(u.href);     // rechargement : 44 questions à retraduire
  }));
}

document.addEventListener('DOMContentLoaded', iniciar);
})();
