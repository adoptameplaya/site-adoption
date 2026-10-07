#!/usr/bin/env python3
"""
Audit du site PUBLIÉ : pages, ressources, en-têtes, protections, données et contenus
encore factices. Aucune écriture, aucun envoi : uniquement des lectures.

    python3 herramientas/auditar-sitio.py                       # https://adoptameplaya.org
    python3 herramientas/auditar-sitio.py --ip 109.234.166.149  # si le DNS local est en retard
    python3 herramientas/auditar-sitio.py --repo .              # + contrôles sur le dépôt local

Sévérités :  ✗ BLOQUANT avant la production · ⚠ À FAIRE · ℹ info · ✓ ok
"""
import argparse, gzip, http.client, json, re, socket, ssl, sys, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="https://adoptameplaya.org")
ap.add_argument("--ip")
ap.add_argument("--repo", default=None)
A = ap.parse_args()
BASE = A.base.rstrip("/"); HOST = urllib.parse.urlparse(BASE).hostname

RES = {"✗": [], "⚠": [], "ℹ": [], "✓": 0}
def marca(nivel, texto):
    if nivel == "✓": RES["✓"] += 1
    else: RES[nivel].append(texto)
def sec(t): print(f"\n── {t}")
def ok(t):   marca("✓", t); print(f"  ✓ {t}")
def bad(t):  marca("✗", t); print(f"  ✗ BLOQUANT : {t}")
def warn(t): marca("⚠", t); print(f"  ⚠ {t}")
def info(t): marca("ℹ", t); print(f"  ℹ {t}")

class Conn(http.client.HTTPSConnection):
    def connect(self):
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(socket.create_connection((A.ip or self.host, 443), timeout=20), server_hostname=self.host)

def get(path, host=None, method="GET", gz=True):
    h = host or HOST
    try:
        c = Conn(h, timeout=25) if (A.ip or True) else None
        c.request(method, path, headers={"Host": h, "User-Agent": "auditar-sitio", **({"Accept-Encoding": "gzip"} if gz else {})})
        r = c.getresponse(); body = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}
        if hd.get("content-encoding") == "gzip": body = gzip.decompress(body)
        return r.status, hd, body
    except Exception as e:
        return 0, {}, str(e).encode()

def texto(b): return b.decode("utf-8", "replace")

# ───────────────────────────── 1. accès, HTTPS, domaines
sec("1. Accès et HTTPS")
s, h, b = get("/")
(ok if s == 200 else bad)(f"page d'accueil : HTTP {s}")
try:
    ctx = ssl.create_default_context()
    with ctx.wrap_socket(socket.create_connection((A.ip or HOST, 443), timeout=15), server_hostname=HOST) as ss:
        cert = ss.getpeercert()
    fin = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    dias = (fin - datetime.now(timezone.utc)).days
    (ok if dias > 20 else warn)(f"certificat HTTPS valide, expire dans {dias} jours (renouvellement AutoSSL automatique)")
except Exception as e:
    bad(f"certificat HTTPS : {e}")
try:
    c = http.client.HTTPConnection(A.ip or HOST, 80, timeout=15); c.request("GET", "/", headers={"Host": HOST}); r = c.getresponse()
    (ok if r.status in (301, 302, 308) and r.getheader("Location", "").startswith("https://") else bad)(f"HTTP → HTTPS : {r.status} → {r.getheader('Location')}")
except Exception as e: warn(f"test HTTP port 80 : {e}")
sw, hw, _ = get("/", host="www." + HOST)
if sw == 0: warn(f"www.{HOST} ne répond pas (pas de certificat/zone ?) : ajouter un alias www ou une redirection vers {HOST}")
elif sw in (301, 302, 308): ok(f"www.{HOST} redirige vers {hw.get('location')}")
else: info(f"www.{HOST} répond directement (HTTP {sw}) : un doublon de contenu pour Google si pas de redirection")

# ───────────────────────────── 2. pages
sec("2. Pages")
for p in ("/", "/cuestionario.html", "/gracias.html", "/aviso-de-privacidad.html", "/admin/", "/robots.txt", "/version.txt", "/data/animales.json", "/data/config.json", "/data/cuestionario.json"):
    s, h, b = get(p); (ok if s == 200 else bad)(f"{p} → HTTP {s}")
s404, h404, b404 = get("/esta-pagina-no-existe")
(ok if s404 == 404 else warn)(f"page inexistante → HTTP {s404}")
if s404 == 404 and "adopta" not in texto(b404).lower(): info("la page 404 est celle, générique, du serveur (une page 404 aux couleurs du site serait un plus)")

# ───────────────────────────── 3. ressources de la page d'accueil
sec("3. Ressources de la page d'accueil")
s, h, home = get("/"); html = texto(home)
refs = set(re.findall(r'(?:src|href)="([^"#]+)"', html))
externos, locales = set(), []
for r in sorted(refs):
    if r.startswith(("mailto:", "tel:", "javascript:", "data:")): continue
    if re.match(r"https?://", r) or r.startswith("//"):
        externos.add(urllib.parse.urlparse(r).hostname); continue
    locales.append(r)
roto = []
for r in locales:
    path = "/" + r.split("?")[0].lstrip("/")
    st, hh, bb = get(path, method="GET", gz=False)
    if st != 200: roto.append((r, st))
(ok if not roto else bad)(f"{len(locales)} ressources locales : " + ("toutes en HTTP 200" if not roto else f"cassées → {roto}"))
info("domaines externes appelés : " + (", ".join(sorted(externos)) or "aucun") + "  (à citer dans l'avis de confidentialité)")
for m in re.finditer(r'<meta[^>]+(?:name|property)="([^"]+)"[^>]+content="([^"]*)"', html):
    pass
og = re.search(r'property="og:image"[^>]+content="([^"]+)"', html)
if og:
    u = og.group(1)
    if not re.match(r"https?://", u): warn(f"og:image est un chemin relatif ({u}) : Facebook/WhatsApp exigent une adresse ABSOLUE pour l'aperçu du lien")
    st, _, _ = get("/" + u.lstrip("/").split("?")[0] if not re.match(r"https?://", u) else urllib.parse.urlparse(u).path)
    (ok if st == 200 else warn)(f"image d'aperçu social ({u}) : HTTP {st}" + ("" if st == 200 else " → les liens partagés n'auront pas d'image"))
can = re.search(r'rel="canonical" href="([^"]+)"', html)
(ok if can and can.group(1).rstrip("/") == BASE else warn)(f"canonical : {can.group(1) if can else 'absent'}")
(ok if re.search(r'<html[^>]+lang="', html) else warn)("attribut lang sur <html>")
(ok if re.search(r'name="description"', html) else warn)("meta description présente")
mode = re.search(r"mode=(\w+)", texto(get("/version.txt")[2]))
modo = mode.group(1) if mode else "?"
robots_meta = bool(re.search(r'name="robots"[^>]+noindex', html))
info(f"mode de publication : {modo} · balise noindex : {'oui' if robots_meta else 'non'}")
rb = texto(get("/robots.txt")[2])
(info if modo == "preprod" else (ok if "Disallow: /\n" not in rb + "\n" else bad))(f"robots.txt : {rb.splitlines()[1:3]}")
if modo == "produccion":
    s, _, _ = get("/sitemap.xml"); (ok if s == 200 else warn)("sitemap.xml " + ("présent" if s == 200 else "absent : utile pour que Google découvre les fiches"))

# restes du modèle de démonstration dans les pages publiées (nom, adresse, e-mail inventés)
RESTES = ("Patitas del Caribe", "patitasdelcaribe", "Calle 34 Norte", "ejemplo.org", "PENDIENTE-LEGAL", "REEMPLAZAR")
for pagina in ("/", "/aviso-de-privacidad.html", "/cuestionario.html", "/gracias.html", "/data/config.json"):
    t = texto(get(pagina)[2])
    for resto in RESTES:
        if resto in t and not (resto == "REEMPLAZAR" and pagina == "/data/config.json"):
            bad(f"{pagina} contient « {resto} » (reste du modèle de démonstration)")
            break
    else:
        ok(f"{pagina} : aucun reste du modèle")

# ───────────────────────────── 4. en-têtes et compression
sec("4. En-têtes de sécurité, cache, compression")
s, h, _ = get("/")
for k in ("x-content-type-options", "referrer-policy"):
    (ok if k in h else warn)(f"en-tête {k} : {h.get(k, 'absent')}")
(info if "strict-transport-security" not in h else ok)(f"HSTS : {h.get('strict-transport-security', 'absent (à activer seulement après le lancement, il est difficile à annuler)')}")
s, h, _ = get("/css/style.css"); (ok if h.get("content-encoding") == "gzip" else warn)(f"compression gzip des CSS : {h.get('content-encoding', 'non')}")
s, h, _ = get("/data/animales.json"); (ok if "no-cache" in h.get("cache-control", "") else warn)(f"JSON jamais mis en cache : {h.get('cache-control', 'absent')}")
s, h, _ = get("/admin/")
csp = h.get("content-security-policy", "")
(ok if "script-src 'self'" in csp else bad)("panel : politique CSP restrictive (seuls ses propres scripts s'exécutent)")
(ok if "noindex" in h.get("x-robots-tag", "") else bad)(f"panel : X-Robots-Tag = {h.get('x-robots-tag', 'absent')}")
(ok if "no-store" in h.get("cache-control", "") else warn)(f"panel : Cache-Control = {h.get('cache-control', 'absent')}")

# ───────────────────────────── 5. chemins qui ne doivent PAS être servis
sec("5. Protection des fichiers internes")
for p in ("/.git/config", "/.git/HEAD", "/api/_comun.php", "/api/secrets.php", "/api/secrets.example.php", "/.htaccess", "/herramientas/",
          "/.sitio-adoptameplaya", "/deploy-ftp.py", "/build-preprod.py", "/ADMIN.md", "/README.md", "/.github/workflows/desplegar.yml", "/netlify.toml", "/secrets-adoptameplaya.php"):
    s, _, b = get(p)
    if s in (401, 403, 404): ok(f"{p} → {s}")
    else: bad(f"{p} est ACCESSIBLE (HTTP {s})")
s, h, b = get("/api/traducir.php"); (ok if s == 405 and b'"ok":false' in b else bad)(f"PHP s'exécute : /api/traducir.php → {s} {texto(b)[:60]}")
s, h, b = get("/api/auth"); loc = h.get("location", "")
(ok if s == 302 and "client_id=Ov23" in loc and "redirect_uri=https%3A%2F%2F" in loc else bad)(f"/api/auth → {s} vers GitHub avec client_id et redirect_uri")
s, h, b = get("/api/callback"); (ok if s == 400 else warn)(f"/api/callback sans code → {s}")

# ───────────────────────────── 6. données publiées
sec("6. Fiches publiées")
s, h, b = get("/data/animales.json")
try: animales = json.loads(b)["animales"]; ok(f"{len(animales)} fiches lisibles ({sum(a['especie']=='perro' for a in animales)} chiens, {sum(a['especie']=='gato' for a in animales)} chats)")
except Exception as e: bad(f"animales.json illisible : {e}"); animales = []
EJEMPLO = {"coco", "rocky", "canela", "bruno", "frida"}
ids = [a.get("id") for a in animales]
(ok if len(ids) == len(set(ids)) else bad)("identifiants uniques")
ej = [a["nombre"] for a in animales if a.get("id") in EJEMPLO]
if ej: bad(f"{len(ej)} fiches d'EXEMPLE encore publiées (animaux fictifs, photos de banque d'images) : {', '.join(ej)}")
resumenes = [a.get("es", {}).get("resumen", "") for a in animales]
historias = {}
for a in animales:
    nom = a["nombre"]; es, en = a.get("es", {}), a.get("en", {})
    if a.get("id") in EJEMPLO: continue
    fal = [k for k in ("resumen", "historia") if not es.get(k)]
    if fal: bad(f"{nom} : texte espagnol manquant ({', '.join(fal)})")
    falen = [k for k in ("resumen", "historia") if es.get(k) and not en.get(k)]
    if falen: warn(f"{nom} : pas de version anglaise pour {', '.join(falen)} (le site affiche l'espagnol)")
    if len(es.get("resumen", "")) < 25: warn(f"{nom} : résumé très court ({es.get('resumen','')!r}) — texte provisoire ?")
    if not a.get("fotos"): bad(f"{nom} : aucune photo")
    if a["especie"] == "perro":
        for k in ("peso_kg", "tamano", "energia"):
            if not a.get(k): warn(f"{nom} : {k} manquant")
    if not (a.get("edad") or a.get("edad_texto")): warn(f"{nom} : âge manquant")
    historias.setdefault(es.get("historia", ""), []).append(nom)
    if re.search(r"refugio|shelter", json.dumps(es | en, ensure_ascii=False), re.I): warn(f"{nom} : le texte parle encore d'un « refugio / shelter »")
    for ph in a.get("fotos", []):
        st, hh, _ = get(ph if ph.startswith("/") else "/" + ph, method="HEAD", gz=False)
        kb = int(hh.get("content-length", 0)) // 1024
        if st != 200: bad(f"{nom} : photo introuvable {ph} (HTTP {st})")
        elif kb > 400: warn(f"{nom} : photo lourde ({kb} Ko) : {ph.split('/')[-1]} — ralentit le site sur mobile")
for hist, noms in historias.items():
    if hist and len(noms) > 1: warn(f"même histoire pour {', '.join(noms)} (texte copié/provisoire ?)")
for a in animales:
    if a.get("id") not in EJEMPLO and sum(1 for r in resumenes if r and r == a.get("es", {}).get("resumen")) > 1:
        warn(f"{a['nombre']} : son résumé est identique à celui d'une autre fiche"); break

# ───────────────────────────── 7. configuration : dons, contacts
sec("7. Configuration affichée au public")
s, h, b = get("/data/config.json"); C = json.loads(b)
d = C.get("donaciones", {})
sp = d.get("spei", {})
if sp.get("activo") and (sp.get("clabe", "").endswith("1234567890") or sp.get("cuenta") == "0123456789"):
    bad(f"CLABE / compte bancaire FACTICES affichés ({sp.get('clabe')}) : un donateur pourrait virer de l'argent au mauvais endroit")
pp = d.get("paypal", {}); mp = d.get("mercadopago", {}); wi = d.get("wise", {})
if pp.get("activo") and re.fullmatch(r"https://paypal\.me/?", pp.get("url", "")): bad("PayPal : lien sans identifiant (https://paypal.me/) → mène à la page d'accueil de PayPal")
if mp.get("activo") and re.fullmatch(r"https://mpago\.la/?", mp.get("url", "")): bad("Mercado Pago : lien sans identifiant (https://mpago.la/)")
if wi.get("activo") and not wi.get("url"): warn("Wise activé sans lien : le bloc renvoie vers l'e-mail de l'association")
if not C.get("redes", {}).get("instagram"): info("pas d'Instagram renseigné (l'icône est masquée)")
if not C.get("redes", {}).get("facebook"): warn("pas de Facebook renseigné")
form = C.get("solicitud", {}).get("formularios", {})
gq = json.loads(texto(get("/data/cuestionario.json")[2]))
for esp, langs in form.items():
    hay_web = bool(gq.get(esp, {}).get("secciones"))
    for lg, ruta in langs.items():
        if ruta: continue
        if hay_web: info(f"formulaire {esp}/{lg} : pas de PDF, le questionnaire en ligne suffit (lien PDF masqué, e-mail automatique vers la page web)")
        else: warn(f"formulaire {esp}/{lg} : ni PDF ni questionnaire en ligne → la demande d'adoption reçoit une réponse « on vous l'envoie »")
for esp in ("perro", "gato"):
    bq = gq.get(esp, {})
    qs = [q for s_ in bq.get("secciones", []) for q in s_.get("preguntas", [])]
    if not qs: warn(f"questionnaire web {esp} : vide (la page renvoie vers WhatsApp)"); continue
    falta = [q["n"] for q in qs if not q.get("es") or not q.get("en")]
    if falta or [q["n"] for q in qs] != list(range(1, len(qs) + 1)): bad(f"questionnaire {esp} : questions sans traduction ou numérotation cassée ({falta})")
    else: ok(f"questionnaire {esp} : {len(qs)} questions, ES/EN complets, numérotation continue")
info(f"don suggéré : {C.get('adopcion', {}).get('donacion_sugerida')}")
info(f"WhatsApp : {C.get('contacto', {}).get('whatsapp_visible')} · e-mail : {C.get('contacto', {}).get('email')} · fondée : {C.get('refugio', {}).get('fundado')}")

# ───────────────────────────── 8. dépôt local (facultatif)
if A.repo:
    sec("8. Dépôt local")
    R = Path(A.repo)
    refs_foto = set()
    for f in R.glob("data/animales/*/*.json"):
        for ph in json.loads(f.read_text(encoding="utf-8")).get("fotos", []): refs_foto.add(ph.lstrip("/").split("/")[-1])
    sobran = [p for p in (R / "img/animales").glob("*") if p.is_file() and p.name not in refs_foto and not p.name.startswith(".")]
    if sobran: warn(f"{len(sobran)} photos non utilisées dans img/animales (≈ {sum(p.stat().st_size for p in sobran)//1024} Ko publiés pour rien) : " + ", ".join(sorted(p.name for p in sobran)[:8]))
    else: ok("aucune photo orpheline")
    i18n = (R / "js/i18n.js").read_text(encoding="utf-8")
    es_b, en_b = i18n.split("\n  en: {")[0], i18n.split("\n  en: {")[1]
    k_es, k_en = set(re.findall(r'^\s+"([^"]+)":', es_b, re.M)), set(re.findall(r'^\s+"([^"]+)":', en_b, re.M))
    (ok if k_es == k_en else bad)(f"traductions ES/EN : {len(k_es)} / {len(k_en)} clés" + ("" if k_es == k_en else f" · écart : {sorted(k_es ^ k_en)}"))
    ap_ = (R / "aviso-de-privacidad.html").read_text(encoding="utf-8")
    if re.search(r"armando un mensaje de WhatsApp|no tiene base de datos", ap_): bad("avis de confidentialité périmé : il reprend l'ancien texte du modèle (envoi par WhatsApp, « aucune base de données »)")
    else:
        faltan = [n for n in ("FormSubmit", "GitHub", "O2switch", "Google Fonts") if n not in ap_]
        (bad if faltan else ok)("avis de confidentialité : cite les vrais circuits (FormSubmit, GitHub, O2switch, Google Fonts)" if not faltan else f"avis de confidentialité : ne cite pas {', '.join(faltan)}")

# ───────────────────────────── bilan
print("\n" + "═" * 62)
print(f"BILAN : {RES['✓']} contrôles réussis · {len(RES['✗'])} bloquant(s) · {len(RES['⚠'])} à faire · {len(RES['ℹ'])} info")
if RES["✗"]:
    print("\nBLOQUANTS avant la production :")
    for t in RES["✗"]: print(f"  ✗ {t}")
if RES["⚠"]:
    print("\nÀ FAIRE :")
    for t in RES["⚠"]: print(f"  ⚠ {t}")
sys.exit(1 if RES["✗"] else 0)
