/* =========================================================
   Panel de Adopta Me Playa — alta, edición y baja de fichas.

   Sin dependencias. Habla directamente con la API de GitHub usando el
   token que entrega el inicio de sesión. Cada publicación es UN solo
   commit (la ficha y sus fotos), que lanza la reconstrucción del sitio.

   Adopta Me Playa escribe en español. El inglés se traduce solo al publicar
   (api/traducir.php); si el servicio no está disponible, la ficha se
   publica igual y el sitio muestra el español en inglés.
   ========================================================= */
(() => {
'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const dormir = ms => new Promise(ok => setTimeout(ok, ms));

/* ---------------- Configuración ---------------- */
/* ?dev solo funciona en localhost: apunta el panel a un GitHub simulado. */
const DEV = ['localhost', '127.0.0.1'].includes(location.hostname) && new URLSearchParams(location.search).has('dev');
const CFG = Object.assign({ repo: '', rama: 'main' }, window.ADMIN_CONFIG);
const TRADUCCION_AUTO = CFG.traduccionAuto === true || (DEV && new URLSearchParams(location.search).has('traduccion'));
const API = DEV ? `${location.origin}/mock/github` : 'https://api.github.com';
const URL_AUTH = '/api/auth';
const URL_TRADUCIR = DEV ? '/mock/traducir' : '/api/traducir';
const LLAVE = 'panel.token';

const ESPECIES = {
  perros: { singular: 'perro', nuevo: 'Añadir un perro', titulo: 'Nuevo perro', vacio: 'Aún no hay perros' },
  gatos:  { singular: 'gato',  nuevo: 'Añadir un gato',  titulo: 'Nuevo gato',  vacio: 'Aún no hay gatos' }
};
const MAX_FOTOS = 6;
const MAX_RASGOS = 5;

/* Rasgos de carácter más usados. [masculino, femenino, inglés]
   Los de la lista no necesitan traducción: ya está hecha. */
const RASGOS = [
  ['Protector', 'Protectora', 'Protective'],
  ['Tranquilo', 'Tranquila', 'Calm'],
  ['Cariñoso', 'Cariñosa', 'Affectionate'],
  ['Mimoso', 'Mimosa', 'Cuddly'],
  ['Juguetón', 'Juguetona', 'Playful'],
  ['Sociable', 'Sociable', 'Sociable'],
  ['Amistoso', 'Amistosa', 'Friendly'],
  ['Enérgico', 'Enérgica', 'Energetic'],
  ['Activo', 'Activa', 'Active'],
  ['Obediente', 'Obediente', 'Obedient'],
  ['Inteligente', 'Inteligente', 'Smart'],
  ['Independiente', 'Independiente', 'Independent'],
  ['Curioso', 'Curiosa', 'Curious'],
  ['Tímido', 'Tímida', 'Shy'],
  ['Miedoso', 'Miedosa', 'Fearful'],
  ['Leal', 'Leal', 'Loyal'],
  ['Fiel', 'Fiel', 'Faithful'],
  ['Dulce', 'Dulce', 'Sweet'],
  ['Noble', 'Noble', 'Noble'],
  ['Valiente', 'Valiente', 'Brave'],
  ['Paciente', 'Paciente', 'Patient'],
  ['Travieso', 'Traviesa', 'Mischievous']
];

const SALUD = ['esterilizado', 'vacunado', 'desparasitado', 'cartilla', 'microchip'];
/* La ficha tipo: todo hecho salvo el microchip, que se marca caso por caso. */
const SALUD_INICIAL = { esterilizado: true, vacunado: true, desparasitado: true, cartilla: true, microchip: false };
const CAMPOS_TXT = ['raza', 'resumen', 'historia', 'aviso', 'edadTexto'];

/* ---------------- Estado ---------------- */
let TOKEN = '';
let FICHAS = [];                 // { especie, id, ruta, datos }
let ARCHIVOS = new Set();        // rutas del repo bajo img/animales/
let TAB = 'perros';
let VISTA = 'carga';
let st = null;                   // estado del editor
let HASH_OK = '';
let IGNORAR_HASH = false;       // al devolver el hash tras un «¿salir sin guardar?» rechazado
const fotoLocal = new Map();     // ruta → URL temporal de las fotos subidas en esta sesión

/* =========================================================
   Utilidades
   ========================================================= */
function leerToken() { try { return localStorage.getItem(LLAVE) || ''; } catch { return ''; } }
function guardarToken(t) { try { t ? localStorage.setItem(LLAVE, t) : localStorage.removeItem(LLAVE); } catch { /* sin almacenamiento */ } }

function aviso(texto, tipo = '') {
  const el = $('#aviso');
  el.textContent = texto;
  el.className = 'panel__aviso' + (tipo ? ` panel__aviso--${tipo}` : '');
  el.hidden = false;
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => { el.hidden = true; }, tipo === 'error' ? 6500 : 3800);
}

function mostrar(vista) {
  VISTA = vista;
  for (const v of ['carga', 'entrada', 'lista', 'orden', 'editor']) $(`#vista-${v}`).hidden = v !== vista;
  $('#usuario').hidden = !TOKEN || vista === 'entrada' || vista === 'carga';
}

const slug = s => String(s).normalize('NFKD').replace(/[̀-ͯ]/g, '')
  .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const norm = s => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
const rutaAbs = r => '/' + String(r).replace(/^\/+/, '');
const srcFoto = r => fotoLocal.get(rutaAbs(r)) || rutaAbs(r);

function deB64(b64) {
  const bin = atob(String(b64).replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
function aB64(blob) {
  return new Promise((ok, ko) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => ko(r.error);
    r.readAsDataURL(blob);
  });
}

function edadES(d) {
  if (d.edad_texto?.es) return d.edad_texto.es;
  const n = Number(d.edad) || 0;
  if (!n) return 'Bebé';
  const meses = d.edad_unidad === 'meses';
  return `${n} ${meses ? (n === 1 ? 'mes' : 'meses') : (n === 1 ? 'año' : 'años')}`;
}

/* Una foto recién subida puede tardar en estar en el sitio: si la ruta
   falla, se pide al repositorio (público) en lugar de dejar un hueco. */
document.addEventListener('error', e => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement) || !img.dataset.ruta || img.dataset.intento || DEV) return;
  img.dataset.intento = '1';
  img.src = `https://raw.githubusercontent.com/${CFG.repo}/${CFG.rama}${rutaAbs(img.dataset.ruta)}`;
}, true);

/* =========================================================
   GitHub
   ========================================================= */
async function gh(ruta, { method = 'GET', body } = {}) {
  const r = await fetch(API + ruta, {
    method,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${TOKEN}`,
      ...(body ? { 'Content-Type': 'application/json' } : {})
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store'
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = new Error(datos.message || r.statusText || `Error ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return datos;
}
const REPO = () => `/repos/${CFG.repo}`;

async function verificarSesion() {
  const [u, repo] = await Promise.all([gh('/user'), gh(REPO())]);
  if (repo.permissions && !repo.permissions.push) {
    const e = new Error(`La cuenta ${u.login} no tiene permiso para modificar el sitio. Pide que te inviten como colaborador del sitio.`);
    e.status = 403; e.sinPermiso = true;
    throw e;
  }
  $('#usuario-nombre').textContent = u.login;
  $('#usuario-foto').src = u.avatar_url || '';
}

async function cargarFichas() {
  const ref = await gh(`${REPO()}/git/ref/heads/${CFG.rama}`);
  const commit = await gh(`${REPO()}/git/commits/${ref.object.sha}`);
  const arbol = await gh(`${REPO()}/git/trees/${commit.tree.sha}?recursive=1`);

  ARCHIVOS = new Set(arbol.tree.filter(n => n.type === 'blob' && n.path.startsWith('img/animales/')).map(n => n.path));
  const jsons = arbol.tree.filter(n => n.type === 'blob' && /^data\/animales\/(perros|gatos)\/[^/]+\.json$/.test(n.path));

  const leidas = await Promise.all(jsons.map(async n => {
    const b = await gh(`${REPO()}/git/blobs/${n.sha}`);
    const [, especie, id] = n.path.match(/^data\/animales\/(perros|gatos)\/([^/]+)\.json$/);
    let datos;
    try { datos = JSON.parse(deB64(b.content)); } catch { return null; }
    return { especie, id, ruta: n.path, datos };
  }));
  FICHAS = leidas.filter(Boolean);
}

/* Un commit atómico: blobs → árbol → commit → mover la rama.
   Si alguien más publicó en medio, se reintenta sobre la rama nueva. */
async function confirmarCambios(cambios, mensaje) {
  const entradas = [];
  for (const c of cambios) {
    if (c.borrar) { entradas.push({ path: c.path, mode: '100644', type: 'blob', sha: null }); continue; }
    const blob = await gh(`${REPO()}/git/blobs`, {
      method: 'POST',
      body: c.b64 !== undefined ? { content: c.b64, encoding: 'base64' } : { content: c.texto, encoding: 'utf-8' }
    });
    entradas.push({ path: c.path, mode: '100644', type: 'blob', sha: blob.sha });
  }
  for (let intento = 0; ; intento++) {
    const ref = await gh(`${REPO()}/git/ref/heads/${CFG.rama}`);
    const base = await gh(`${REPO()}/git/commits/${ref.object.sha}`);
    const arbol = await gh(`${REPO()}/git/trees`, { method: 'POST', body: { base_tree: base.tree.sha, tree: entradas } });
    const commit = await gh(`${REPO()}/git/commits`, {
      method: 'POST', body: { message: mensaje, tree: arbol.sha, parents: [ref.object.sha] }
    });
    try {
      await gh(`${REPO()}/git/refs/heads/${CFG.rama}`, { method: 'PATCH', body: { sha: commit.sha, force: false } });
      return commit.sha;
    } catch (e) {
      if (e.status === 422 && intento < 2) { await dormir(600); continue; }
      throw e;
    }
  }
}

/* Espera a que GitHub Actions reconstruya y suba el sitio. */
async function esperarSitio(sha, cancelado) {
  const t0 = Date.now();
  while (!cancelado() && Date.now() - t0 < 6 * 60 * 1000) {
    await dormir(5000);
    let r;
    try { r = await gh(`${REPO()}/actions/runs?head_sha=${sha}&per_page=5`); } catch { continue; }
    const run = r.workflow_runs?.[0];
    if (!run) { if (Date.now() - t0 > 40000) return 'sin-ejecucion'; continue; }
    if (run.status === 'completed') return run.conclusion === 'success' ? 'ok' : 'fallo';
  }
  return 'tarde';
}

/* =========================================================
   Traducción automática
   ========================================================= */
async function traducir(textos) {
  const r = await fetch(URL_TRADUCIR, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Token-GitHub': TOKEN },
    body: JSON.stringify({ de: 'es', a: 'en', textos })
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || !d.ok || !Array.isArray(d.textos) || d.textos.length !== textos.length) {
    const e = new Error(d.error || `El servicio de traducción respondió ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return d.textos;
}

/* Lo que hay que traducir: el español que cambió (o nunca se tradujo) y
   que nadie ha corregido a mano en inglés. */
function pendientes() {
  if (!TRADUCCION_AUTO) return [];
  const out = [];
  for (const c of CAMPOS_TXT) {
    const es = st.es[c].trim();
    if (!es) continue;
    if (st.en[c].trim() && (st.manual[c] || st.enBase[c] === es)) continue;
    out.push({ texto: es, aplicar: t => { st.en[c] = t; st.enBase[c] = es; } });
  }
  for (const r of st.rasgos) {
    if (!r.propio) continue;
    if (r.en && r.enBase === r.es) continue;
    out.push({ texto: r.es, aplicar: t => { r.en = t; r.enBase = r.es; } });
  }
  return out;
}

async function traducirPendientes() {
  const p = pendientes();
  if (!p.length) return 0;
  const t = await traducir(p.map(x => x.texto));
  p.forEach((x, i) => x.aplicar(t[i]));
  return p.length;
}

/* =========================================================
   Sesión
   ========================================================= */
function entrar() {
  $('#entrada-error').hidden = true;
  if (DEV) { guardarToken(TOKEN = 'dev'); return iniciar(); }

  const ventana = window.open(URL_AUTH, 'github-login', 'width=620,height=760');
  if (!ventana) {
    const e = $('#entrada-error');
    e.textContent = 'Tu navegador bloqueó la ventana de GitHub. Permite las ventanas emergentes para esta página y vuelve a probar.';
    e.hidden = false;
    return;
  }
  const PREFIJO = 'authorization:github:success:';
  const alRecibir = e => {
    if (e.origin !== location.origin || typeof e.data !== 'string') return;
    if (e.data === 'authorizing:github') { e.source.postMessage('authorizing:github', e.origin); return; }
    if (!e.data.startsWith(PREFIJO)) return;
    window.removeEventListener('message', alRecibir);
    try {
      TOKEN = JSON.parse(e.data.slice(PREFIJO.length)).token || '';
    } catch { TOKEN = ''; }
    if (!TOKEN) return;
    guardarToken(TOKEN);
    iniciar();
  };
  window.addEventListener('message', alRecibir);
}

function salir(motivo) {
  TOKEN = '';
  guardarToken('');
  FICHAS = [];
  st = null;
  mostrar('entrada');
  if (motivo) { const e = $('#entrada-error'); e.textContent = motivo; e.hidden = false; }
}

async function iniciar() {
  TOKEN = TOKEN || leerToken() || (DEV ? 'dev' : '');
  if (!TOKEN) return mostrar('entrada');
  mostrar('carga');
  try {
    await verificarSesion();
    await cargarFichas();
  } catch (e) {
    if (e.status === 401) return salir('La sesión caducó. Vuelve a entrar.');
    if (e.sinPermiso) return salir(e.message);
    salir(`No se pudo conectar con GitHub (${e.message}). Revisa tu conexión e inténtalo de nuevo.`);
    return;
  }
  ruta();
}

/* =========================================================
   Lista
   ========================================================= */
const porOrden = (a, b) => (a.datos.orden ?? 999) - (b.datos.orden ?? 999) || String(a.datos.nombre).localeCompare(b.datos.nombre);

function pintarLista() {
  const lista = FICHAS.filter(f => f.especie === TAB).sort(porOrden);
  for (const e of Object.keys(ESPECIES)) {
    $(`#n-${e}`).textContent = `(${FICHAS.filter(f => f.especie === e).length})`;
    $(`[data-especie="${e}"]`).setAttribute('aria-pressed', String(e === TAB));
  }
  $('#nuevo-texto').textContent = ESPECIES[TAB].nuevo;

  $('#lista').innerHTML = lista.length
    ? lista.map(carta).join('')
    : `<li class="vacio carta__vacia"><h3>${esc(ESPECIES[TAB].vacio)}</h3><p>Pulsa «${esc(ESPECIES[TAB].nuevo)}» para crear la primera ficha.</p></li>`;
}

function carta(f) {
  const d = f.datos;
  const foto = (d.fotos && d.fotos[0]) || d.foto || '';
  const meta = [d.sexo === 'macho' ? 'Macho' : d.sexo === 'hembra' ? 'Hembra' : '', edadES(d),
    d.tamano ? d.tamano[0].toUpperCase() + d.tamano.slice(1) : ''].filter(Boolean).join(' · ');
  return `<li class="${d.adoptado ? 'es-adoptado' : ''}"><article class="tarjeta carta">
    <span class="tarjeta__marco">
      ${d.adoptado ? `<span class="sello" style="--giro:${-(10 + [...String(d.id || d.nombre || '')].reduce((n, c) => n + c.charCodeAt(0), 0) % 7)}deg"><span class="sello__palabra">${d.sexo === 'hembra' ? 'Adoptada' : 'Adoptado'}</span><span class="sello__sub" aria-hidden="true">Adopta Me Playa</span></span>`
        : (d.urgente ? '<span class="tarjeta__urgente">Urgente</span>' : '')}
      ${foto ? `<img src="${esc(srcFoto(foto))}" data-ruta="${esc(foto)}" alt="" loading="lazy" width="300" height="300">` : '<span class="carta__sin-foto">Sin foto</span>'}
    </span>
    <span class="tarjeta__nombre">${esc(d.nombre)}</span>
    <span class="tarjeta__meta">${esc(meta)}</span>
    <span class="tarjeta__resumen">${esc(d.es?.resumen || '')}</span>
    <div class="carta__acciones">
      <a class="btn" href="#editar/${f.especie}/${esc(f.id)}"><svg aria-hidden="true"><use href="#i-lapiz"></use></svg>Editar</a>
      <button class="btn btn--claro btn--icono" type="button" data-borrar="${f.especie}/${esc(f.id)}" aria-label="Quitar a ${esc(d.nombre)}"><svg aria-hidden="true"><use href="#i-papelera"></use></svg></button>
    </div>
  </article></li>`;
}

/* =========================================================
   Ordenar las fichas (arrastrar y soltar, como en el móvil)
   El orden vive en el campo «orden» de cada ficha (de 10 en 10) ; el sitio lo respeta,
   y los animales adoptados van siempre al final, pase lo que pase.
   ========================================================= */
let ORDEN = { inicial: '', sucio: false };
const claveFicha = f => `${f.especie}/${f.id}`;
const esFija = li => li?.classList.contains('orden__fila--fija');
const filasOrden = () => [...$('#orden-lista').children];
const activasOrden = () => filasOrden().filter(li => !esFija(li));

function filaOrden(f) {
  const d = f.datos, fija = !!d.adoptado;
  const foto = (d.fotos && d.fotos[0]) || d.foto || '';
  const sexo = d.sexo === 'macho' ? 'Macho' : d.sexo === 'hembra' ? 'Hembra' : '';
  const meta = `<span class="orden__meta"><svg aria-hidden="true"><use href="#${f.especie === 'gatos' ? 'i-gato' : 'i-perro'}"></use></svg>${esc([f.especie === 'gatos' ? 'Gato' : 'Perro', sexo, edadES(d)].filter(Boolean).join(' · '))}</span>`;
  const img = `<img class="orden__foto" src="${foto ? esc(srcFoto(foto)) : ''}" alt="" width="58" height="58" draggable="false">`;
  return fija
    ? `<li class="orden__fila orden__fila--fija" data-k="${esc(claveFicha(f))}">${img}<div><div class="orden__nombre">${esc(d.nombre)}</div>${meta}</div><span class="orden__etiqueta">Adoptado/a · siempre al final</span></li>`
    : `<li class="orden__fila" data-k="${esc(claveFicha(f))}">
        <button class="orden__asa" type="button" aria-label="Mover a ${esc(d.nombre)}: arrastra, o usa las flechas arriba y abajo del teclado"><svg aria-hidden="true"><use href="#i-asa"></use></svg></button>
        <span class="orden__n"></span>${img}
        <div><div class="orden__nombre">${esc(d.nombre)}</div>${meta}</div>
        <div class="orden__mover">
          <button type="button" data-sube aria-label="Subir a ${esc(d.nombre)}"><svg aria-hidden="true"><use href="#i-flecha"></use></svg></button>
          <button type="button" data-baja aria-label="Bajar a ${esc(d.nombre)}"><svg aria-hidden="true"><use href="#i-flecha"></use></svg></button>
        </div>
      </li>`;
}

function abrirOrden() {
  const todas = [...FICHAS].sort(porOrden);
  $('#orden-lista').innerHTML = todas.filter(f => !f.datos.adoptado).map(filaOrden).join('') + todas.filter(f => f.datos.adoptado).map(filaOrden).join('');
  ORDEN = { inicial: '', sucio: false };
  refrescarOrden();
  ORDEN.inicial = activasOrden().map(li => li.dataset.k).join('|');
  $('#or-guardar').disabled = true;
  $('#orden-vivo').textContent = '';
  mostrar('orden');
}

/* números, flechas desactivadas en los extremos, corte de la franja de portada y botón «Guardar» */
function refrescarOrden() {
  const act = activasOrden();
  act.forEach((li, i) => {
    li.querySelector('.orden__n').textContent = i + 1;
    li.querySelector('[data-sube]').disabled = i === 0;
    li.querySelector('[data-baja]').disabled = i === act.length - 1;
    li.classList.toggle('orden__fila--corte', i === 4 && act.length > 5);
  });
  ORDEN.sucio = act.map(li => li.dataset.k).join('|') !== ORDEN.inicial;
  $('#or-guardar').disabled = !ORDEN.sucio;
}

/* anima a las demás fichas cuando una cambia de sitio (FLIP) */
function conAnimacion(cambio, excluir) {
  const filas = filasOrden().filter(x => x !== excluir);
  const antes = new Map(filas.map(x => [x, x.getBoundingClientRect().top]));
  cambio();
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  for (const x of filas) {
    const d = antes.get(x) - x.getBoundingClientRect().top;
    if (d) x.animate([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 170, easing: 'ease-out' });
  }
}

function anunciarOrden(li) {
  const act = activasOrden();
  $('#orden-vivo').textContent = `${li.querySelector('.orden__nombre').textContent}: posición ${act.indexOf(li) + 1} de ${act.length}.`;
}

function moverUno(li, sentido) {
  const lista = li.parentElement;
  if (sentido < 0) {
    const prev = li.previousElementSibling;
    if (!prev || esFija(prev)) return;
    conAnimacion(() => lista.insertBefore(li, prev));
  } else {
    const next = li.nextElementSibling;
    if (!next || esFija(next)) return;
    conAnimacion(() => lista.insertBefore(li, next.nextElementSibling));
  }
  refrescarOrden();
  anunciarOrden(li);
}

/* Arrastre con el puntero (ratón y dedo). Durante el arrastre NO se mueve nada en el documento
   (mover un nodo hace que el navegador pierda el puntero, sobre todo en el móvil) : la ficha sigue
   al dedo con una transformación y las demás se apartan con otra. Al soltar se reordena el listado. */
let ARRASTRE = null;
function colocarArrastre() {
  const A = ARRASTRE, li = A.li, lista = li.parentElement;
  const rel = (A.y - A.agarre) - lista.getBoundingClientRect().top;     // parte alta deseada, dentro del listado
  li.style.transform = `translateY(${rel - li.offsetTop}px)`;
  const centro = rel + li.offsetHeight / 2;
  const otros = A.filas.filter(x => x !== li);
  const destino = otros.filter(x => x.offsetTop + x.offsetHeight / 2 < centro).length;
  if (destino === A.destino) return;
  A.destino = destino;
  A.nuevo = [...otros]; A.nuevo.splice(destino, 0, li);
  A.nuevo.forEach((x, k) => {                                           // cada ficha va a la posición (hueco) que le toca
    if (x === li) return;
    const d = A.huecos[k] - x.offsetTop;
    x.style.transform = d ? `translateY(${d}px)` : '';
  });
}
function bucleArrastre() {
  if (!ARRASTRE) return;
  const y = ARRASTRE.y, h = innerHeight;
  if (y < 90) { scrollBy(0, -Math.min(18, (90 - y) / 4 + 4)); colocarArrastre(); }
  else if (y > h - 90) { scrollBy(0, Math.min(18, (y - (h - 90)) / 4 + 4)); colocarArrastre(); }
  ARRASTRE.raf = requestAnimationFrame(bucleArrastre);
}
function empezarArrastre(e) {
  const asa = e.target.closest('.orden__asa');
  if (!asa || e.button > 0 || ARRASTRE) return;
  const li = asa.closest('.orden__fila');
  e.preventDefault();
  try { asa.setPointerCapture(e.pointerId); } catch { /* sin captura : el arrastre sigue por los eventos del listado */ }
  const filas = activasOrden();
  ARRASTRE = {
    li, id: e.pointerId, y: e.clientY, agarre: e.clientY - li.getBoundingClientRect().top, raf: 0,
    filas, huecos: filas.map(x => x.offsetTop), destino: filas.indexOf(li), nuevo: filas
  };
  filas.forEach(x => { if (x !== li) x.classList.add('orden__fila--aparta'); });
  li.classList.add('orden__fila--arrastre');
  navigator.vibrate?.(8);
  colocarArrastre();
  ARRASTRE.raf = requestAnimationFrame(bucleArrastre);
}
function moverArrastre(e) {
  if (!ARRASTRE || e.pointerId !== ARRASTRE.id) return;
  ARRASTRE.y = e.clientY;
  colocarArrastre();
}
function soltarArrastre(e) {
  if (!ARRASTRE || (e.pointerId !== undefined && e.pointerId !== ARRASTRE.id)) return;
  const { li, raf, filas, nuevo } = ARRASTRE;
  cancelAnimationFrame(raf);
  ARRASTRE = null;
  const antes = li.getBoundingClientRect().top;
  filas.forEach(x => { x.style.transform = ''; x.classList.remove('orden__fila--aparta'); });
  li.classList.remove('orden__fila--arrastre');
  const lista = li.parentElement, ancla = filasOrden().find(esFija) || null;
  nuevo.forEach(x => lista.insertBefore(x, ancla));
  const d = antes - li.getBoundingClientRect().top;                      // la ficha se posa suavemente en su hueco
  if (d && !matchMedia('(prefers-reduced-motion: reduce)').matches) li.animate([{ transform: `translateY(${d}px)` }, { transform: 'none' }], { duration: 160, easing: 'ease-out' });
  refrescarOrden();
  anunciarOrden(li);
}

async function guardarOrden() {
  const claves = activasOrden().map(li => li.dataset.k);
  prog.abrir('Guardando el orden', ['Guardando el orden', 'Publicando en el sitio']);
  $('#or-guardar').disabled = true;
  let sha;
  try {
    prog.paso(0, 'curso');
    await cargarFichas();                                   // datos frescos : no se pisa nada que otra persona haya cambiado
    const frescas = new Map(FICHAS.map(f => [claveFicha(f), f]));
    const nuevas = FICHAS.filter(f => !f.datos.adoptado && !claves.includes(claveFicha(f))).sort(porOrden).map(claveFicha);
    const finales = [...nuevas, ...claves.filter(k => frescas.has(k) && !frescas.get(k).datos.adoptado)];
    const cambios = [];
    finales.forEach((k, i) => {
      const f = frescas.get(k), nuevo = (i + 1) * 10;
      if (f.datos.orden !== nuevo) cambios.push({ path: f.ruta, texto: JSON.stringify({ ...f.datos, orden: nuevo }, null, 2) + '\n' });
    });
    if (cambios.length) sha = await confirmarCambios(cambios, 'Cambia el orden de las fichas (panel)');
    prog.paso(0, 'ok');
    await cargarFichas();
  } catch (e) { $('#or-guardar').disabled = false; return fallo(e); }

  ORDEN.sucio = false;
  if (!sha) { prog.paso(1, 'ok', 'Ya estaba así'); prog.nota('El orden no había cambiado.'); prog.cerrable(); $('#dlg-progreso').addEventListener('close', () => { location.hash = `#${TAB}`; }, { once: true }); return; }
  prog.paso(1, 'curso');
  prog.nota('Listo: el nuevo orden está guardado. El sitio se actualiza solo en unos minutos.');
  prog.cerrable();
  $('#dlg-progreso').addEventListener('close', () => { prog.cancelado = true; location.hash = `#${TAB}`; }, { once: true });
  terminarPublicacion(sha);
}

/* =========================================================
   Editor — estado
   ========================================================= */
function estadoNuevo(especie) {
  const ordenes = FICHAS.map(f => f.datos.orden).filter(Number.isFinite);
  return {
    nuevo: true, especie, id: '', original: null, sucio: false,
    orden: ordenes.length ? Math.min(...ordenes) - 10 : 10,
    nombre: '', sexo: '', edad: '', unidad: 'anos', peso: '', tamano: '', energia: '', urgente: false, adoptado: false,
    salud: { ...SALUD_INICIAL },
    es: { raza: '', resumen: '', historia: '', aviso: '', edadTexto: '' },
    en: { raza: '', resumen: '', historia: '', aviso: '', edadTexto: '' },
    enBase: { raza: '', resumen: '', historia: '', aviso: '', edadTexto: '' },
    manual: { raza: false, resumen: false, historia: false, aviso: false, edadTexto: false },
    rasgos: [], fotos: []
  };
}

function estadoDesde(f) {
  const d = f.datos;
  const s = estadoNuevo(f.especie);
  Object.assign(s, {
    nuevo: false, id: f.id, original: d, orden: d.orden ?? 999,
    nombre: d.nombre || '', sexo: d.sexo || '',
    edad: Number(d.edad) ? String(d.edad) : '', unidad: d.edad_unidad === 'meses' ? 'meses' : 'anos',
    peso: d.peso_kg ? String(d.peso_kg) : '', tamano: d.tamano || '', energia: d.energia || '',
    urgente: !!d.urgente, adoptado: !!d.adoptado
  });
  for (const k of SALUD) s.salud[k] = !!d[k];

  const lee = (c, es, en) => { s.es[c] = es || ''; s.en[c] = en || ''; s.enBase[c] = es || ''; };
  lee('raza', d.raza?.es, d.raza?.en);
  lee('edadTexto', d.edad_texto?.es, d.edad_texto?.en);
  lee('resumen', d.es?.resumen, d.en?.resumen);
  lee('historia', d.es?.historia, d.en?.historia);
  lee('aviso', d.es?.aviso, d.en?.aviso);

  (d.es?.caracter || []).forEach((palabra, i) => {
    const k = RASGOS.findIndex(r => norm(r[0]) === norm(palabra) || norm(r[1]) === norm(palabra));
    s.rasgos.push(k >= 0 ? { k } : { propio: true, es: palabra, en: d.en?.caracter?.[i] || '', enBase: palabra });
  });

  const fotos = (d.fotos && d.fotos.length ? d.fotos : (d.foto ? [d.foto] : []));
  s.fotos = fotos.map(r => ({ ruta: r, url: srcFoto(r) }));
  return s;
}

function abrirEditor(especie, id) {
  const f = id ? FICHAS.find(x => x.especie === especie && x.id === id) : null;
  if (id && !f) { aviso('No encuentro esa ficha.', 'error'); location.hash = `#${especie}`; return; }
  TAB = especie;
  st = f ? estadoDesde(f) : estadoNuevo(especie);
  $('#ed-titulo').textContent = f ? `Editar a ${f.datos.nombre}` : ESPECIES[especie].titulo;
  $('#ed-publicar').textContent = f ? 'Guardar' : 'Publicar';
  $('#ed-estado').textContent = '';
  rellenarForm();
  mostrar('editor');
  window.scrollTo(0, 0);
}

function rellenarForm() {
  $('#f-nombre').value = st.nombre;
  $('#f-sexo').value = st.sexo;
  $('#f-edad').value = st.edad;
  $('#f-unidad').value = st.unidad;
  $('#f-peso').value = st.peso;
  $('#f-tamano').value = st.tamano;
  $('#f-energia').value = st.energia;
  $('#f-urgente').checked = st.urgente;
  $('#f-adoptado').checked = st.adoptado;
  /* Los gatos no llevan peso, tamano ni energia: solo sexo y edad. */
  $$('[data-solo="perros"]').forEach(el => { el.hidden = st.especie !== 'perros'; });
  for (const k of SALUD) $(`#f-${k}`).checked = st.salud[k];
  $('#f-raza').value = st.es.raza;
  $('#f-resumen').value = st.es.resumen;
  $('#f-historia').value = st.es.historia;
  $('#f-aviso').value = st.es.aviso;
  $('#f-edadtexto').value = st.es.edadTexto;
  $('#f-rasgo-otro').value = '';
  $$('.ed__campo--error').forEach(el => el.classList.remove('ed__campo--error'));
  $('#ed-ingles').open = !TRADUCCION_AUTO;     // a mano: abierta ; automática: cerrada
  $('#ed-ingles-manual').hidden = TRADUCCION_AUTO;
  $('#ed-ingles-auto').hidden = !TRADUCCION_AUTO;
  $('#ed-traducir').hidden = !TRADUCCION_AUTO;
  pintarFotos();
  pintarRasgos();
  pintarIngles();
}

function leerForm() {
  st.nombre = $('#f-nombre').value;
  st.sexo = $('#f-sexo').value;
  st.edad = $('#f-edad').value;
  st.unidad = $('#f-unidad').value;
  st.peso = $('#f-peso').value;
  st.tamano = $('#f-tamano').value;
  st.energia = $('#f-energia').value;
  st.urgente = $('#f-urgente').checked;
  st.adoptado = $('#f-adoptado').checked;
  for (const k of SALUD) st.salud[k] = $(`#f-${k}`).checked;
  st.es.raza = $('#f-raza').value;
  st.es.resumen = $('#f-resumen').value;
  st.es.historia = $('#f-historia').value;
  st.es.aviso = $('#f-aviso').value;
  st.es.edadTexto = $('#f-edadtexto').value;
}

/* =========================================================
   Editor — fotos
   ========================================================= */
function pintarFotos() {
  const img = $('#ed-foto-img');
  const fondo = $('#ed-foto-fondo');
  const principal = st.fotos[0];
  img.hidden = !principal;
  fondo.hidden = !principal;
  if (principal) {
    img.onload = ajustarFotoEditor;
    img.src = principal.url; img.dataset.ruta = principal.ruta || ''; delete img.dataset.intento;
    fondo.src = principal.url;
    if (img.complete) ajustarFotoEditor();
  }

  $('#ed-galeria').innerHTML = st.fotos.map((f, i) => `
    <div class="ed__mini">
      <button type="button" class="galeria__v" data-foto="${i}" aria-pressed="${i === 0}" aria-label="Foto ${i + 1}${i === 0 ? ' (principal)' : ': hacerla principal'}">
        <img src="${esc(f.url)}" data-ruta="${esc(f.ruta || '')}" alt="" width="64" height="64">
      </button>
      <button type="button" class="ed__mini-x" data-quitar="${i}" aria-label="Quitar la foto ${i + 1}"><svg aria-hidden="true"><use href="#i-cerrar"></use></svg></button>
    </div>`).join('') + (st.fotos.length && st.fotos.length < MAX_FOTOS
      ? '<button type="button" class="galeria__v ed__mas" id="ed-mas" aria-label="Añadir más fotos"><svg aria-hidden="true"><use href="#i-mas"></use></svg></button>' : '');
}

/* Misma regla que en el sitio: la foto se ve ENTERA sobre un fondo desenfocado cuando sus
   proporciones se alejan del cuadro (más de un 20 %); si casi encaja, llena el cuadro. */
function ajustarFotoEditor() {
  const marco = $('#ed-foto'), img = $('#ed-foto-img');
  if (!marco || !img.naturalWidth || !marco.clientHeight) return;
  const cuadro = marco.clientWidth / marco.clientHeight;
  marco.classList.toggle('ed__foto--entera', Math.abs(img.naturalWidth / img.naturalHeight / cuadro - 1) > 0.2);
}
window.addEventListener('resize', () => { if (VISTA === 'editor') ajustarFotoEditor(); });

/* Reduce la foto antes de subirla: una foto de móvil pesa 4-8 MB y el sitio solo necesita ~1400 px.
   Respeta la orientación EXIF. Tope duro: ninguna foto sube por encima de FOTO_MAX_KB, aunque sea
   muy detallada (se baja la calidad y, si hace falta, el tamaño, hasta llegar). */
const FOTO_MAX_PX = 1400;
const FOTO_MAX_KB = 300;
const pesoTxt = n => n >= 1048576 ? `${(n / 1048576).toFixed(1).replace('.', ',')} MB` : `${Math.round(n / 1024)} KB`;

async function procesarFoto(archivo) {
  let bmp;
  try {
    bmp = await createImageBitmap(archivo, { imageOrientation: 'from-image' });
  } catch {
    bmp = await new Promise((ok, ko) => {
      const i = new Image();
      i.onload = () => ok(i); i.onerror = ko;
      i.src = URL.createObjectURL(archivo);
    });
  }
  const w0 = bmp.width || bmp.naturalWidth, h0 = bmp.height || bmp.naturalHeight;
  let escala = Math.min(1, FOTO_MAX_PX / Math.max(w0, h0)), calidad = 0.84, blob = null;
  for (let intento = 0; intento < 9; intento++) {
    const cv = document.createElement('canvas');
    cv.width = Math.max(1, Math.round(w0 * escala)); cv.height = Math.max(1, Math.round(h0 * escala));
    const cx = cv.getContext('2d');
    cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height);
    cx.drawImage(bmp, 0, 0, cv.width, cv.height);
    blob = await new Promise(ok => cv.toBlob(ok, 'image/jpeg', calidad));
    if (!blob) throw new Error('canvas vacío');
    if (blob.size <= FOTO_MAX_KB * 1024 || Math.max(cv.width, cv.height) <= 800) break;
    if (calidad > 0.62) calidad = Math.max(0.62, calidad - 0.08); else escala *= 0.85;
  }
  bmp.close?.();
  return blob;
}

/* Miniatura (≈ 560 px) para las tarjetas de la portada: unos 40 KB en vez de 150-300 KB. Se sube junto a la foto
   con el sufijo «-m» ; el sitio la usa si existe. */
const MINI_PX = 560;
const rutaMini = r => String(r).replace(/\.jpe?g$/i, '-m.jpg');
async function procesarMiniatura(blob) {
  const bmp = await createImageBitmap(blob);
  const k = Math.min(1, MINI_PX / Math.max(bmp.width, bmp.height));
  const cv = document.createElement('canvas');
  cv.width = Math.max(1, Math.round(bmp.width * k)); cv.height = Math.max(1, Math.round(bmp.height * k));
  const cx = cv.getContext('2d');
  cx.fillStyle = '#fff'; cx.fillRect(0, 0, cv.width, cv.height);
  cx.drawImage(bmp, 0, 0, cv.width, cv.height);
  bmp.close?.();
  return new Promise(ok => cv.toBlob(ok, 'image/jpeg', 0.72));
}

async function añadirFotos(archivos) {
  const lista = [...archivos].filter(a => a.type.startsWith('image/') || /\.(jpe?g|png|webp|heic)$/i.test(a.name));
  if (!lista.length) { aviso('Eso no parece una foto.', 'error'); return; }
  let fallos = 0, antes = 0, despues = 0, hechas = 0;
  $('#ed-estado').textContent = 'Preparando las fotos…';
  for (const a of lista) {
    if (st.fotos.length >= MAX_FOTOS) { aviso(`Máximo ${MAX_FOTOS} fotos por animal.`, 'error'); break; }
    try {
      const blob = await procesarFoto(a);
      const mini = await procesarMiniatura(blob).catch(() => null);      // si falla, el sitio usa la foto completa
      st.fotos.push({ blob, mini, url: URL.createObjectURL(blob) });
      st.sucio = true;
      antes += a.size; despues += blob.size; hechas++;
    } catch { fallos++; }
  }
  $('#ed-estado').textContent = '';
  if (hechas && !fallos) aviso(`${hechas === 1 ? 'Foto lista' : `${hechas} fotos listas`}: se aligeró de ${pesoTxt(antes)} a ${pesoTxt(despues)} para que el sitio siga rápido.`);
  if (fallos) aviso(fallos === 1 ? 'No pude leer una de las fotos. Prueba con otra (JPG o PNG).' : `No pude leer ${fallos} fotos. Prueba con JPG o PNG.`, 'error');
  pintarFotos();
  $('.ed__foto-vacia')?.classList.remove('ed__campo--error');
}

/* =========================================================
   Editor — carácter
   ========================================================= */
function pintarRasgos() {
  const hembra = st.sexo === 'hembra';
  const elegidos = new Set(st.rasgos.filter(r => !r.propio).map(r => r.k));
  $('#ed-rasgos').innerHTML =
    RASGOS.map((r, i) => `<button type="button" class="etiqueta" data-rasgo="${i}" aria-pressed="${elegidos.has(i)}">${esc(hembra ? r[1] : r[0])}</button>`).join('') +
    st.rasgos.map((r, i) => r.propio
      ? `<button type="button" class="etiqueta etiqueta--propio" data-propio="${i}" aria-label="Quitar ${esc(r.es)}">${esc(r.es)} ✕</button>` : '').join('');
}

function añadirPropio() {
  const campo = $('#f-rasgo-otro');
  const palabra = campo.value.trim();
  if (!palabra) return;
  const ya = st.rasgos.some(r => norm(r.propio ? r.es : (st.sexo === 'hembra' ? RASGOS[r.k][1] : RASGOS[r.k][0])) === norm(palabra));
  if (ya) { campo.value = ''; return; }
  if (st.rasgos.length >= MAX_RASGOS) { aviso(`Máximo ${MAX_RASGOS} rasgos: quita uno para añadir otro.`, 'error'); return; }
  st.rasgos.push({ propio: true, es: palabra, en: '', enBase: '' });
  st.sucio = true;
  campo.value = '';
  pintarRasgos(); pintarIngles();
}

function alternarRasgo(i) {
  const pos = st.rasgos.findIndex(r => !r.propio && r.k === i);
  if (pos >= 0) st.rasgos.splice(pos, 1);
  else if (st.rasgos.length >= MAX_RASGOS) { aviso(`Máximo ${MAX_RASGOS} rasgos: quita uno para añadir otro.`, 'error'); return; }
  else st.rasgos.push({ k: i });
  st.sucio = true;
  pintarRasgos(); pintarIngles();
}

/* =========================================================
   Editor — versión en inglés
   ========================================================= */
function pintarIngles() {
  $('#e-raza').value = st.en.raza;
  $('#e-resumen').value = st.en.resumen;
  $('#e-historia').value = st.en.historia;
  $('#e-aviso').value = st.en.aviso;
  $('#e-edadtexto').value = st.en.edadTexto;
  /* Rasgos de la lista: su inglés ya está hecho. Rasgos propios: se escribe su inglés aquí. */
  $('#e-rasgos').innerHTML = st.rasgos.map((r, i) => r.propio
    ? `<label class="ed__rasgo-en"><span>${esc(r.es)} →</span><input type="text" data-en-rasgo="${i}" maxlength="24" value="${esc(r.en || '')}" placeholder="en inglés"></label>`
    : `<span class="etiqueta">${esc(RASGOS[r.k][2])}</span>`).join('') || '<span class="ayuda">Sin rasgos</span>';
  estadoIngles();
}

const ETQ_EN = { raza: 'la raza', resumen: 'el resumen', historia: 'la historia', aviso: 'el aviso', edadTexto: 'la edad' };

/* Qué falta en inglés (solo cuenta lo que ya tiene texto en español). */
function faltaIngles() {
  const out = [];
  for (const c of CAMPOS_TXT) if (st.es[c].trim() && !st.en[c].trim()) out.push(ETQ_EN[c]);
  if (st.rasgos.some(r => r.propio && !(r.en || '').trim())) out.push('el carácter');
  return out;
}

/* Lo que depende del español y puede cambiar al escribir: no toca los campos ingleses
   (así no se pierde el cursor). */
function estadoIngles() {
  for (const c of ['raza', 'aviso', 'edadTexto']) {
    const caja = document.querySelector(`[data-en-campo="${c}"]`);
    if (caja) caja.hidden = !st.es[c].trim();
  }
  for (const c of CAMPOS_TXT) {
    const o = document.querySelector(`[data-orig="${c}"]`);
    if (o) { o.textContent = st.es[c]; o.hidden = !st.es[c].trim(); }
  }
  const el = $('#ed-ingles-estado');
  if (TRADUCCION_AUTO) {
    const n = pendientes().length;
    el.textContent = !n ? 'al día' : n === 1 ? '1 texto se traducirá al publicar' : `${n} textos se traducirán al publicar`;
    el.dataset.estado = '';
  } else {
    const f = faltaIngles();
    el.textContent = f.length ? `· falta ${f.length > 1 ? f.slice(0, -1).join(', ') + ' y ' + f.at(-1) : f[0]}` : '· completa ✓';
    el.dataset.estado = f.length ? 'falta' : 'ok';
  }
}

/* =========================================================
   Editor — validar, construir y publicar
   ========================================================= */
function validar() {
  const falta = [];
  if (!st.nombre.trim()) falta.push(['nombre', 'el nombre']);
  if (!st.fotos.length) falta.push(['fotos', 'al menos una foto']);
  if (!st.sexo) falta.push(['sexo', 'el sexo']);
  if (st.edad === '' && !st.es.edadTexto.trim()) falta.push(['edad', 'la edad']);
  if (st.especie === 'perros') {
    if (!st.tamano) falta.push(['tamano', 'el tamaño']);
    if (!st.energia) falta.push(['energia', 'el nivel de energía']);
  }
  if (!st.es.resumen.trim()) falta.push(['resumen', 'el resumen']);
  if (!st.es.historia.trim()) falta.push(['historia', 'su historia']);

  $$('.ed__campo').forEach(el => el.classList.toggle('ed__campo--error', falta.some(f => f[0] === el.dataset.campo)));
  $('.ed__foto-vacia').classList.toggle('ed__campo--error', falta.some(f => f[0] === 'fotos'));
  if (!falta.length) return true;

  const [campo] = falta[0];
  const destino = campo === 'fotos' ? $('.ed__marco') : $(`.ed__campo[data-campo="${campo}"]`);
  destino?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const nombres = falta.map(f => f[1]);
  const lista = nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres.at(-1)}` : nombres[0];
  aviso(`Falta completar ${lista}.`, 'error');
  return false;
}

function idUnico() {
  if (st.id) return st.id;
  const base = slug(st.nombre) || 'animal';
  const usados = new Set(FICHAS.map(f => f.id));
  let id = base, n = 2;
  while (usados.has(id)) id = `${base}-${n++}`;
  return id;
}

function construirJSON(id, rutasFotos) {
  const o = st.original || {};
  const conocidas = new Set(['orden', 'id', 'nombre', 'raza', 'edad', 'edad_unidad', 'sexo', 'edad_texto', 'peso_kg',
    'tamano', 'energia', 'fotos', 'foto', 'urgente', 'adoptado', ...SALUD, 'es', 'en', 'especie']);
  const extra = Object.fromEntries(Object.entries(o).filter(([k]) => !conocidas.has(k)));

  const t = c => st.es[c].trim();
  const e = c => (st.en[c] || '').trim();
  const hembra = st.sexo === 'hembra';
  const caracterEs = st.rasgos.map(r => r.propio ? r.es : RASGOS[r.k][hembra ? 1 : 0]);
  const caracterEn = st.rasgos.map(r => r.propio ? (r.en || '') : RASGOS[r.k][2]);
  const todosEn = caracterEn.every(Boolean);

  const bilingue = c => ({ es: t(c), ...(e(c) ? { en: e(c) } : {}) });
  const peso = parseFloat(String(st.peso).replace(',', '.'));

  return {
    orden: st.orden,
    id,
    nombre: st.nombre.trim(),
    ...(t('raza') ? { raza: bilingue('raza') } : {}),
    edad: Number(st.edad) || 0,
    edad_unidad: st.unidad,
    sexo: st.sexo,
    ...(t('edadTexto') ? { edad_texto: bilingue('edadTexto') } : {}),
    ...(st.especie === 'perros' ? {
      peso_kg: Number.isFinite(peso) ? peso : 0,
      tamano: st.tamano,
      energia: st.energia
    } : {}),
    fotos: rutasFotos,
    urgente: !!st.urgente,
    ...(st.adoptado ? { adoptado: true } : {}),
    ...Object.fromEntries(SALUD.map(k => [k, !!st.salud[k]])),
    es: {
      resumen: t('resumen'),
      historia: t('historia'),
      ...(t('aviso') ? { aviso: t('aviso') } : {}),
      caracter: caracterEs
    },
    en: {
      ...(e('resumen') ? { resumen: e('resumen') } : {}),
      ...(e('historia') ? { historia: e('historia') } : {}),
      ...(t('aviso') && e('aviso') ? { aviso: e('aviso') } : {}),
      ...(caracterEs.length && todosEn ? { caracter: caracterEn } : {})
    },
    ...extra
  };
}

/* ---- ventana de progreso ---- */
const prog = {
  cancelado: false,
  abrir(titulo, pasos) {
    this.cancelado = false;
    $('#prog-t').textContent = titulo;
    $('#prog-pasos').innerHTML = pasos.map((p, i) => `<li data-i="${i}">${esc(p)}</li>`).join('');
    $('#prog-nota').textContent = '';
    $('#prog-botones').hidden = true;
    if (!$('#dlg-progreso').open) $('#dlg-progreso').showModal();
  },
  paso(i, estado, texto) {
    const li = $(`#prog-pasos [data-i="${i}"]`);
    if (!li) return;
    li.dataset.e = estado;
    if (texto) li.textContent = texto;
  },
  nota(t) { $('#prog-nota').textContent = t; },
  cerrable() { $('#prog-botones').hidden = false; }
};

async function publicar() {
  leerForm();
  if (!validar()) return;

  const id = idUnico();
  const esNueva = st.nuevo;
  const nombre = st.nombre.trim();
  const rutaJson = `data/animales/${st.especie}/${id}.json`;

  prog.abrir(esNueva ? `Publicando a ${nombre}` : `Guardando a ${nombre}`,
    [TRADUCCION_AUTO ? 'Traduciendo al inglés' : 'Comprobando el inglés', 'Preparando las fotos', 'Guardando la ficha', 'Publicando en el sitio']);
  $('#ed-publicar').disabled = true;
  let sha = '';

  try {
    /* 1. traducción — si falla, se decide con el usuario, no se bloquea */
    prog.paso(0, 'curso');
    if (!TRADUCCION_AUTO) {
      const f = faltaIngles();
      prog.paso(0, 'ok', f.length ? `Inglés incompleto (falta ${f.join(', ')}): se mostrará en español` : 'Versión en inglés completa');
    } else if (pendientes().length) {
      let sinTraduccion = null;
      try {
        await traducirPendientes();
        prog.paso(0, 'ok');
      } catch (err) {
        if (err.status === 503) {
          /* Traducción sin configurar (aún no hay clave): no es un fallo, se publica en español
             y el sitio mostrará ese texto en la versión inglesa. Sin preguntar. */
          prog.paso(0, 'ok', 'Sin traducción automática (aún no activada)');
        } else {
          sinTraduccion = err;
        }
      }
      if (sinTraduccion) {
        prog.paso(0, 'error', 'Traducción no disponible');
        const seguir = confirm(`No se pudo traducir al inglés (${sinTraduccion.message.replace(/\.$/, '')}).\n\n¿Publicar igualmente? La versión en inglés mostrará el texto en español.`);
        if (!seguir) { $('#dlg-progreso').close(); $('#ed-publicar').disabled = false; return; }
      }
    } else {
      prog.paso(0, 'ok', 'Traducción al día');
    }

    /* 2. fotos nuevas y fotos retiradas */
    prog.paso(1, 'curso');
    const cambios = [];
    const rutas = [];
    for (const f of st.fotos) {
      if (f.ruta) { rutas.push(rutaAbs(f.ruta)); continue; }
      const nombreArchivo = `${id}-${Math.random().toString(36).slice(2, 7)}.jpg`;
      cambios.push({ path: `img/animales/${nombreArchivo}`, b64: await aB64(f.blob) });
      if (f.mini) cambios.push({ path: rutaMini(`img/animales/${nombreArchivo}`), b64: await aB64(f.mini) });
      f._ruta = `/img/animales/${nombreArchivo}`;
      rutas.push(f._ruta);
    }
    const usadasPorOtras = new Set(FICHAS.filter(x => !(x.especie === st.especie && x.id === id))
      .flatMap(x => (x.datos.fotos || []).map(rutaAbs)));
    for (const r of (st.original?.fotos || []).map(rutaAbs)) {
      const path = r.slice(1);
      if (!rutas.includes(r) && !usadasPorOtras.has(r) && ARCHIVOS.has(path)) {
        cambios.push({ path, borrar: true });
        if (ARCHIVOS.has(rutaMini(path))) cambios.push({ path: rutaMini(path), borrar: true });
      }
    }
    prog.paso(1, 'ok');

    /* 3. un solo commit */
    prog.paso(2, 'curso');
    cambios.push({ path: rutaJson, texto: JSON.stringify(construirJSON(id, rutas), null, 2) + '\n' });
    sha = await confirmarCambios(cambios, `${esNueva ? 'Añade' : 'Actualiza'} la ficha de ${nombre} (panel)`);
    prog.paso(2, 'ok');

    for (const f of st.fotos) if (f._ruta) fotoLocal.set(f._ruta, f.url);
    st.sucio = false;
    await cargarFichas();
  } catch (e) {
    return fallo(e);
  }

  $('#ed-publicar').disabled = false;
  prog.paso(3, 'curso');
  prog.nota('Tu ficha ya está guardada. Puedes cerrar esta ventana: el sitio se actualiza solo en unos minutos.');
  prog.cerrable();
  const especie = st.especie;
  const alCerrar = () => { prog.cancelado = true; location.hash = `#${especie}`; };
  $('#dlg-progreso').addEventListener('close', alCerrar, { once: true });
  terminarPublicacion(sha);
}

async function terminarPublicacion(sha) {
  const r = await esperarSitio(sha, () => prog.cancelado);
  if (prog.cancelado) return;
  if (r === 'ok') { prog.paso(3, 'ok', 'Lista para publicarse'); prog.nota('¡Listo! En un par de minutos se verá en la página.'); }
  else if (r === 'fallo') { prog.paso(3, 'error', 'El sitio no se pudo reconstruir'); prog.nota('La ficha está guardada, pero la publicación falló. Avisa a quien administra el sitio.'); }
  else { prog.paso(3, 'ok', 'Guardado'); prog.nota('Guardado. Aparecerá en el sitio en unos minutos.'); }
}

function fallo(e) {
  $('#ed-publicar').disabled = false;
  if (e.status === 401) { $('#dlg-progreso').close(); return salir('La sesión caducó. Vuelve a entrar: tu ficha sigue en pantalla.'); }
  const li = $('#prog-pasos [data-e="curso"]');
  if (li) li.dataset.e = 'error';
  const permiso = e.status === 403 || e.status === 404;
  prog.nota(permiso
    ? 'GitHub no te deja guardar en este sitio. Revisa que tu cuenta tenga acceso de escritura al sitio.'
    : `No se pudo guardar: ${e.message}. No se perdió nada de lo que escribiste; inténtalo de nuevo.`);
  prog.cerrable();
}

/* ---- borrar ---- */
async function quitar(especie, id) {
  const f = FICHAS.find(x => x.especie === especie && x.id === id);
  if (!f) return;
  $('#borrar-nombre').textContent = f.datos.nombre;
  const dlg = $('#dlg-borrar');
  dlg.returnValue = '';
  dlg.showModal();
  await new Promise(ok => dlg.addEventListener('close', ok, { once: true }));
  if (dlg.returnValue !== 'si') return;

  prog.abrir(`Quitando a ${f.datos.nombre}`, ['Quitando la ficha', 'Publicando en el sitio']);
  let sha;
  try {
    prog.paso(0, 'curso');
    const usadas = new Set(FICHAS.filter(x => x !== f).flatMap(x => (x.datos.fotos || []).map(rutaAbs)));
    const cambios = [{ path: f.ruta, borrar: true }];
    for (const r of (f.datos.fotos || []).map(rutaAbs)) {
      if (!usadas.has(r) && ARCHIVOS.has(r.slice(1))) {
        cambios.push({ path: r.slice(1), borrar: true });
        if (ARCHIVOS.has(rutaMini(r.slice(1)))) cambios.push({ path: rutaMini(r.slice(1)), borrar: true });
      }
    }
    sha = await confirmarCambios(cambios, `Quita la ficha de ${f.datos.nombre} (panel)`);
    prog.paso(0, 'ok');
    await cargarFichas();
    pintarLista();
  } catch (e) { return fallo(e); }

  prog.paso(1, 'curso');
  prog.nota('Listo: la ficha ya no está. El sitio se actualiza solo en unos minutos.');
  prog.cerrable();
  $('#dlg-progreso').addEventListener('close', () => { prog.cancelado = true; }, { once: true });
  terminarPublicacion(sha);
}

/* =========================================================
   Rutas (el botón «atrás» del móvil funciona)
   ========================================================= */
function ruta() {
  if (!TOKEN) return mostrar('entrada');
  const [a, b, c] = location.hash.replace(/^#\/?/, '').split('/');

  if (VISTA === 'editor' && st?.sucio && HASH_OK && !(a === 'editar' || a === 'nuevo')) {
    if (!confirm('Tienes cambios sin publicar. ¿Salir y perderlos?')) {
      IGNORAR_HASH = true; location.hash = HASH_OK; return;
    }
  }
  if (VISTA === 'orden' && ORDEN.sucio && a !== 'ordenar') {
    if (!confirm('Cambiaste el orden y no lo has guardado. ¿Salir y perderlo?')) { IGNORAR_HASH = true; location.hash = HASH_OK; return; }
  }
  HASH_OK = location.hash;

  if (a === 'ordenar') return abrirOrden();
  if (a === 'nuevo' && ESPECIES[b]) return abrirEditor(b, null);
  if (a === 'editar' && ESPECIES[b] && c) return abrirEditor(b, decodeURIComponent(c));
  if (ESPECIES[a]) TAB = a;
  st = null;
  pintarLista();
  mostrar('lista');
}

function volver() {
  location.hash = `#${st?.especie || TAB}`;
}

/* =========================================================
   Conexiones
   ========================================================= */
function conectar() {
  $('#entrar').addEventListener('click', entrar);
  $('#salir').addEventListener('click', () => salir());
  window.addEventListener('hashchange', () => { if (IGNORAR_HASH) { IGNORAR_HASH = false; return; } if (TOKEN && VISTA !== 'carga') ruta(); });
  window.addEventListener('beforeunload', e => { if ((VISTA === 'editor' && st?.sucio) || (VISTA === 'orden' && ORDEN.sucio)) { e.preventDefault(); e.returnValue = ''; } });

  /* lista */
  $$('[data-especie]').forEach(b => b.addEventListener('click', () => { location.hash = `#${b.dataset.especie}`; }));
  $('#nuevo').addEventListener('click', () => { location.hash = `#nuevo/${TAB}`; });
  $('#ordenar').addEventListener('click', () => { location.hash = '#ordenar'; });

  /* ordenar */
  const olista = $('#orden-lista');
  olista.addEventListener('pointerdown', empezarArrastre);
  olista.addEventListener('pointermove', moverArrastre);
  olista.addEventListener('pointerup', soltarArrastre);
  olista.addEventListener('pointercancel', soltarArrastre);
  olista.addEventListener('lostpointercapture', soltarArrastre);
  olista.addEventListener('click', e => {
    const li = e.target.closest('.orden__fila');
    if (!li) return;
    if (e.target.closest('[data-sube]')) moverUno(li, -1);
    else if (e.target.closest('[data-baja]')) moverUno(li, 1);
  });
  olista.addEventListener('keydown', e => {
    const asa = e.target.closest('.orden__asa');
    if (!asa || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    e.preventDefault();
    moverUno(asa.closest('.orden__fila'), e.key === 'ArrowUp' ? -1 : 1);
    asa.focus();
  });
  $('#or-volver').addEventListener('click', () => { location.hash = `#${TAB}`; });
  $('#or-cancelar').addEventListener('click', () => { location.hash = `#${TAB}`; });
  $('#or-guardar').addEventListener('click', guardarOrden);
  $('#lista').addEventListener('click', e => {
    const b = e.target.closest('[data-borrar]');
    if (b) { const [esp, id] = b.dataset.borrar.split('/'); quitar(esp, id); }
  });

  /* editor */
  $('#ed-volver').addEventListener('click', volver);
  $('#ed-cancelar').addEventListener('click', volver);
  $('#ed-form').addEventListener('submit', e => { e.preventDefault(); publicar(); });
  $('#prog-cerrar').addEventListener('click', () => $('#dlg-progreso').close());

  $('#ed-form').addEventListener('input', e => {
    if (!st) return;
    st.sucio = true;
    e.target.closest('.ed__campo')?.classList.remove('ed__campo--error');
    if (e.target.dataset.enRasgo !== undefined) {
      const r = st.rasgos[Number(e.target.dataset.enRasgo)];
      if (r) { r.en = e.target.value; r.enBase = r.es; }
      estadoIngles();
      return;
    }
    const en = { 'e-raza': 'raza', 'e-resumen': 'resumen', 'e-historia': 'historia', 'e-aviso': 'aviso', 'e-edadtexto': 'edadTexto' }[e.target.id];
    if (en) { st.en[en] = e.target.value; st.manual[en] = true; estadoIngles(); return; }
    if (e.target.id === 'f-rasgo-otro') return;
    leerForm();
    if (e.target.id === 'f-sexo') pintarRasgos();
    estadoIngles();
  });
  $('#ed-form').addEventListener('keydown', e => {
    if (e.key !== 'Enter' || e.target.tagName !== 'INPUT') return;
    e.preventDefault();
    if (e.target.id === 'f-rasgo-otro') añadirPropio();
  });

  /* fotos */
  const archivos = $('#ed-archivos');
  $('#ed-foto').addEventListener('click', () => archivos.click());
  archivos.addEventListener('change', () => { añadirFotos(archivos.files).then(() => { archivos.value = ''; }); });
  $('#ed-galeria').addEventListener('click', e => {
    if (e.target.closest('#ed-mas')) { archivos.click(); return; }
    const x = e.target.closest('[data-quitar]');
    if (x) { st.fotos.splice(Number(x.dataset.quitar), 1); st.sucio = true; pintarFotos(); return; }
    const v = e.target.closest('[data-foto]');
    if (v) {
      const i = Number(v.dataset.foto);
      if (i > 0) { st.fotos.unshift(...st.fotos.splice(i, 1)); st.sucio = true; pintarFotos(); }
    }
  });
  const marco = $('.ed__marco');
  ['dragenter', 'dragover'].forEach(n => marco.addEventListener(n, e => { e.preventDefault(); $('#ed-foto').classList.add('ed__arrastre'); }));
  ['dragleave', 'drop'].forEach(n => marco.addEventListener(n, () => $('#ed-foto').classList.remove('ed__arrastre')));
  marco.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer?.files?.length) añadirFotos(e.dataTransfer.files); });

  /* carácter */
  $('#ed-rasgos').addEventListener('click', e => {
    const r = e.target.closest('[data-rasgo]');
    if (r) return alternarRasgo(Number(r.dataset.rasgo));
    const p = e.target.closest('[data-propio]');
    if (p) { st.rasgos.splice(Number(p.dataset.propio), 1); st.sucio = true; pintarRasgos(); pintarIngles(); }
  });
  $('#ed-rasgo-add').addEventListener('click', añadirPropio);

  /* inglés y opciones */
  $('#ed-traducir').addEventListener('click', async () => {
    leerForm();
    const estado = $('#ed-traducir-estado');
    const btn = $('#ed-traducir');
    btn.disabled = true; estado.textContent = 'Traduciendo…';
    try {
      const n = await traducirPendientes();
      estado.textContent = n ? 'Listo. Revisa los textos de arriba; puedes corregir lo que quieras.' : 'Ya estaba todo traducido.';
      pintarIngles();
    } catch (err) {
      estado.textContent = `No se pudo traducir: ${err.message}`;
    }
    btn.disabled = false;
  });
  $('#ed-primero').addEventListener('click', () => {
    const otros = FICHAS.filter(f => !(f.especie === st.especie && f.id === st.id)).map(f => f.datos.orden).filter(Number.isFinite);
    st.orden = (otros.length ? Math.min(...otros) : 10) - 10;
    st.sucio = true;
    aviso('Saldrá el primero del sitio al guardar.');
  });
}

conectar();
iniciar();
})();
