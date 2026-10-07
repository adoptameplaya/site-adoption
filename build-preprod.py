#!/usr/bin/env python3
"""
Génère dist/refugio-preprod.zip : la version à déposer sur Netlify
tant que les vraies données du refuge ne sont pas arrivées.

Différences avec le site final :
  - noindex partout (robots.txt + netlify.toml + balise meta)
  - bandeau « sitio de demostración » en haut de page
  - les fichiers de travail (.md, servir.command, ce script) sont exclus

Usage : python3 build-preprod.py

Variables d'environnement :
  MODO     preprod (défaut) | produccion
  DESTINO  netlify (défaut) | o2switch
           o2switch ajoute api/ (PHP) et .htaccess, et ne produit ni
           _redirects ni _headers, qui ne servent qu'à Netlify.
  SITE_URL adresse publique (https://adoptameplaya.org) : réglée dans le
           canonical, dans la config du secours Decap
"""
import json, os, re, shutil, unicodedata, zipfile
from pathlib import Path

# preprod = bandeau de démo + noindex ; produccion = site public.
# Sur Netlify, se règle dans Site settings → Environment variables.
MODO = os.environ.get("MODO", "preprod").strip().lower()
PREPROD = MODO != "produccion"

# netlify = ancien hébergement ; o2switch = hébergement définitif (PHP + .htaccess).
DESTINO = os.environ.get("DESTINO", "netlify").strip().lower()
O2 = DESTINO == "o2switch"
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")

RACINE = Path(__file__).parent.resolve()
DIST   = RACINE / "dist"
BUILD  = DIST / "preprod"
ZIP    = DIST / "refugio-preprod.zip"

A_COPIER = ["index.html", "aviso-de-privacidad.html", "gracias.html", "cuestionario.html", "admin", "css", "js", "data", "img", "formularios"]
if O2:
    A_COPIER += ["api", ".htaccess"]

# Jamais dans le site publié : les secrets posés à la main sur le serveur,
# et les scories de macOS.
IGNORES = shutil.ignore_patterns("secrets.php", "secrets-*.php", ".DS_Store")


def preparer():
    if DIST.exists():
        shutil.rmtree(DIST)
    BUILD.mkdir(parents=True)
    for nom in A_COPIER:
        src = RACINE / nom
        dst = BUILD / nom
        if src.is_dir():
            shutil.copytree(src, dst, ignore=IGNORES)
        else:
            shutil.copy2(src, dst)


def ajustar_url():
    """Règle l'adresse publique là où elle est écrite en dur."""
    if not SITE_URL:
        return
    cfg = BUILD / "admin" / "decap" / "config.yml"
    if cfg.is_file():
        t = re.sub(r"(?m)^(\s*base_url:\s*).*$", lambda m: m.group(1) + SITE_URL, cfg.read_text(encoding="utf-8"))
        cfg.write_text(t, encoding="utf-8")
    for page in BUILD.glob("*.html"):
        t = page.read_text(encoding="utf-8")
        n = t.replace("https://ejemplo.org", SITE_URL)
        # Facebook, WhatsApp… exigen una dirección ABSOLUTA para la imagen de vista previa del enlace
        n = n.replace('content="img/ui/og.jpg"', f'content="{SITE_URL}/img/ui/og.jpg"')
        if n != t:
            page.write_text(n, encoding="utf-8")
    print(f"  adresse publique réglée : {SITE_URL}")


def nombre_seguro(nombre):
    """Ramène un nom de fichier à l'ASCII, accents aplatis, sans espaces.

    Une photo téléversée depuis un Mac s'appelle « capture d'écran … .png ».
    Entre la normalisation Unicode de macOS (NFD) et celle du navigateur
    (NFC), le dépôt et le disque finissent avec deux noms différents, et le
    site publie un lien mort. On normalise donc à la publication.
    """
    import unicodedata
    base, punto, ext = nombre.rpartition(".")
    base = base or nombre
    plano = unicodedata.normalize("NFKD", base)
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = re.sub(r"[^A-Za-z0-9._-]+", "-", plano).strip("-.") or "foto"
    return f"{plano.lower()}.{ext.lower()}" if punto else plano.lower()


def sanear_fotos(animales):
    """Renomme dans le site publié toute photo au nom non ASCII, et signale
    celles qui manquent — mieux vaut un avertissement au build qu'un 404."""
    medios = BUILD / "img" / "animales"
    renombradas, ausentes = 0, []

    disponibles = {}
    if medios.is_dir():
        for p in medios.iterdir():
            if p.is_file():
                disponibles[unicodedata.normalize("NFC", p.name)] = p

    for a in animales:
        nuevas = []
        for ruta in a.get("fotos", []):
            archivo = unicodedata.normalize("NFC", ruta.rsplit("/", 1)[-1])
            p = disponibles.get(archivo)
            if p is None:
                ausentes.append((a.get("nombre"), ruta))
                continue
            seguro = nombre_seguro(p.name)
            if seguro != p.name:
                destino = medios / seguro
                p.rename(destino)
                disponibles[unicodedata.normalize("NFC", seguro)] = destino
                disponibles.pop(archivo, None)
                renombradas += 1
            nuevas.append(f"/img/animales/{seguro}")
        a["fotos"] = nuevas

    if renombradas:
        print(f"  photos renommées pour le web : {renombradas}")
    for nombre, ruta in ausentes:
        print(f"  ⚠ photo introuvable, retirée de la fiche {nombre} : {ruta}")
    sin_foto = [a.get("nombre") for a in animales if not a.get("fotos")]
    if sin_foto:
        print(f"  ⚠ fiches sans aucune photo : {', '.join(sin_foto)}")


def ensamblar_animales():
    """Une fiche = un fichier, pour que l'admin offre une vraie liste par espèce.
    Le site, lui, ne lit qu'un seul animales.json : on l'assemble ici.

    L'espèce vient du dossier, pas d'un champ : impossible de se tromper.
    L'ordre vient du champ « orden », croissant, puis du nom.
    """
    import json
    animales = []
    for carpeta, especie in (("perros", "perro"), ("gatos", "gato")):
        origen = RACINE / "data" / "animales" / carpeta
        if not origen.is_dir():
            continue
        for ruta in sorted(origen.glob("*.json")):
            with open(ruta, encoding="utf-8") as f:
                a = json.load(f)
            a["especie"] = especie
            a.setdefault("orden", 999)
            animales.append(a)

    animales.sort(key=lambda a: (a.get("orden", 999), a.get("nombre", "")))
    sanear_fotos(animales)
    perros = sum(1 for a in animales if a["especie"] == "perro")
    print(f"  fiches assemblées : {len(animales)} ({perros} chiens, {len(animales)-perros} chats)")

    destino = BUILD / "data"
    destino.mkdir(parents=True, exist_ok=True)
    with open(destino / "animales.json", "w", encoding="utf-8") as f:
        json.dump({"animales": animales}, f, ensure_ascii=False, indent=2)

    # les fiches individuelles n'ont rien à faire sur le site publié
    sueltas = destino / "animales"
    if sueltas.is_dir():
        shutil.rmtree(sueltas)


def noindex():
    """Balise meta sur les deux pages HTML."""
    balise = '<meta name="robots" content="noindex,nofollow">\n'
    for page in ("index.html", "aviso-de-privacidad.html", "gracias.html", "cuestionario.html"):
        p = BUILD / page
        s = p.read_text()
        if 'name="robots"' in s:
            s = re.sub(r'<meta name="robots"[^>]*>', balise.strip(), s)
        else:
            s = s.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + balise, 1)
        p.write_text(s)


def bandeau():
    """Bandeau de démonstration + ses textes, sans toucher aux fichiers source."""
    (BUILD / "js" / "demo.js").write_text(
        "/* Bandeau de préprod. Ce fichier n'existe que dans la version de démonstration. */\n"
        "Object.assign(window.TEXTOS.es, {\n"
        '  "demo.t": "Sitio de demostración.",\n'
        '  "demo.d": "Los animales, el nombre de la asociación y los datos bancarios son de ejemplo. '
        'Nada de esta página es real todavía."\n'
        "});\n"
        "Object.assign(window.TEXTOS.en, {\n"
        '  "demo.t": "Demo site.",\n'
        '  "demo.d": "The animals, the association name and the bank details are placeholders. '
        'Nothing on this page is real yet."\n'
        "});\n"
    )

    css = BUILD / "css" / "style.css"
    css.write_text(css.read_text() + """
/* ---- Bandeau de préprod (version de démonstration uniquement) ---- */
.demo-aviso{
  background:var(--tinta);color:var(--crema);
  padding:10px 16px;text-align:center;
  font-size:.85rem;font-weight:700;line-height:1.4;
}
.demo-aviso strong{color:var(--naranja)}
@media (max-width:520px){.demo-aviso{font-size:.78rem;padding:9px 12px}}
""")

    p = BUILD / "index.html"
    s = p.read_text()

    ancre = '<!-- ================= BARRA ================= -->'
    assert ancre in s, "ancre de la barre introuvable"
    s = s.replace(ancre,
        '<p class="demo-aviso"><strong data-i18n="demo.t"></strong> '
        '<span data-i18n="demo.d"></span></p>\n\n' + ancre, 1)

    ancre_js = '<script src="js/app.js'
    i = s.index(ancre_js)
    version = re.search(r'js/i18n\.js(\?v=\d+)?', s).group(1) or ''
    s = s[:i] + f'<script src="js/demo.js{version}"></script>\n' + s[i:]

    p.write_text(s)


def verifier_formularios():
    """Un lien mort dans l'auto-réponse ne se voit qu'au premier adoptant."""
    import json
    cfg = json.load(open(BUILD / "data" / "config.json"))
    formularios = cfg.get("solicitud", {}).get("formularios", {})
    for especie, langues in formularios.items():
        for lang, ruta in langues.items():
            if not ruta:
                print(f"  · {especie}/{lang} : pas de PDF → l'auto-réponse ne renvoie qu'au questionnaire en ligne")
            elif not (BUILD / ruta).exists():
                raise SystemExit(f"ERREUR : config.json référence {ruta} pour {especie}/{lang}, "
                                 f"mais le fichier est absent du build.")
            else:
                ko = (BUILD / ruta).stat().st_size / 1024
                print(f"  · {especie}/{lang} : {ruta} ({ko:.0f} Ko)")


def verifier_cuestionario():
    """Le questionnaire se modifie à la main dans data/cuestionario.json : une
    question sans traduction ou un numéro en double ne se voit qu'à l'envoi."""
    import json
    datos = json.load(open(BUILD / "data" / "cuestionario.json"))
    for especie in ("perro", "gato"):
        bloque = datos.get(especie, {})
        secciones = bloque.get("secciones", [])
        if not secciones:
            print(f"  · questionnaire {especie} : vide → la page renvoie vers WhatsApp")
            continue
        errores, numeros = [], []
        for lang in ("es", "en"):
            if not bloque.get("intro", {}).get(lang): errores.append(f"intro {lang} vide")
            if "intro_pdf" in bloque and not bloque["intro_pdf"].get(lang): errores.append(f"intro_pdf {lang} vide")
        for s in secciones:
            for lang in ("es", "en"):
                if not s.get(lang): errores.append(f"section « {s.get('id')} » sans {lang}")
            for q in s.get("preguntas", []):
                numeros.append(q.get("n"))
                if q.get("tipo") not in ("texto", "largo", "sino"): errores.append(f"question {q.get('n')} : tipo « {q.get('tipo')} » inconnu")
                for lang in ("es", "en"):
                    if not str(q.get(lang, "")).strip(): errores.append(f"question {q.get('n')} sans {lang}")
        if numeros != list(range(1, len(numeros) + 1)):
            errores.append(f"numéros de questions non consécutifs à partir de 1 : {numeros}")
        if errores:
            raise SystemExit(f"ERREUR : data/cuestionario.json ({especie}) : " + " ; ".join(errores))
        print(f"  · questionnaire {especie} : {len(numeros)} questions, {len(secciones)} sections, ES/EN complets")


def fichiers_netlify():
    """robots.txt, _redirects et _headers du site publié.

    On n'écrit PAS de netlify.toml ici : celui de la racine du dépôt décrit
    déjà la construction, et en avoir deux rendait les redirections
    silencieusement inopérantes. Les fichiers _redirects et _headers posés
    dans le dossier publié, eux, sont sans ambiguïté.
    """
    if PREPROD:
        robots = ("# Préprod : rien ne doit être indexé tant que les données sont fictives.\n"
                  "User-agent: *\n"
                  "Disallow: /\n")
        cabeceras = ("/*\n"
                     "  X-Robots-Tag: noindex, nofollow\n")
    else:
        robots = ("User-agent: *\n"
                  "Allow: /\n"
                  "Disallow: /admin/\n"
                  + (f"\nSitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else ""))
        cabeceras = ("/admin/*\n"
                     "  X-Robots-Tag: noindex, nofollow\n")

    (BUILD / "robots.txt").write_text(robots)

    # Marqueur de build : permet de vérifier depuis l'extérieur quelle
    # version est réellement en ligne, et quand elle a été construite.
    import subprocess
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RACINE,
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        sha = "?"
    (BUILD / "version.txt").write_text(
        f"commit={sha or '?'}\nmode={'preprod' if PREPROD else 'produccion'}\ndestino={DESTINO}\n"
        f"construit={__import__('datetime').datetime.utcnow().isoformat(timespec='seconds')}Z\n"
    )

    if O2:
        return   # sur O2switch, c'est le .htaccess qui fait ce travail

    # Decap appelle ces deux chemins pour l'authentification GitHub.
    (BUILD / "_redirects").write_text(
        "/api/auth      /.netlify/functions/auth      200\n"
        "/api/callback  /.netlify/functions/callback  200\n"
    )

    (BUILD / "_headers").write_text(
        cabeceras +
        "\n# Les JSON changent à chaque modification faite dans l'admin :\n"
        "# ils ne doivent jamais rester en cache.\n"
        "/data/*\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
    )


def sitemap():
    """Production seulement : une carte du site pour Google. Les fiches s'ouvrent dans une fenêtre
    de la page d'accueil (pas d'adresse propre) ; l'avis de confidentialité est en noindex, il n'a
    donc pas sa place ici."""
    if PREPROD or not SITE_URL:
        return
    hoy = __import__("datetime").date.today().isoformat()
    (BUILD / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}/</loc><lastmod>{hoy}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
        '</urlset>\n', encoding="utf-8")


# Animaux de la démonstration : leurs fiches ne doivent jamais partir en production.
FICHES_EXEMPLE = {"coco", "rocky", "canela", "bruno", "frida"}
# Restes du modèle de démonstration : nom, adresse et e-mail inventés.
RESTES_MODELE = ("Patitas del Caribe", "patitasdelcaribe", "Calle 34 Norte", "ejemplo.org", "PENDIENTE-LEGAL")


def clabe_valide(clabe):
    """CLABE bancaire mexicaine : 18 chiffres, le dernier est une clé de contrôle (poids 3-7-1)."""
    if not re.fullmatch(r"\d{18}", str(clabe)):
        return False
    pesos = [3, 7, 1] * 6
    total = sum((int(c) * pesos[i]) % 10 for i, c in enumerate(clabe[:17]))
    return (10 - total % 10) % 10 == int(clabe[17])


def verificar_produccion():
    """MODO=produccion : refuse de construire tant qu'il reste des données de démonstration.

    Un faux lien de don publié peut envoyer l'argent au mauvais endroit : mieux vaut un build
    qui échoue (le site reste sur sa version précédente) qu'un site faux en ligne.
    FORZAR_PRODUCCION=1 désactive ce contrôle, à n'utiliser qu'en connaissance de cause."""
    if PREPROD or os.environ.get("FORZAR_PRODUCCION") == "1":
        return
    problemas = []
    if not SITE_URL:
        problemas.append("SITE_URL n'est pas définie (adresse canonique, sitemap, image de partage)")

    cfg = json.loads((BUILD / "data" / "config.json").read_text(encoding="utf-8"))
    d = cfg.get("donaciones", {})
    pp = d.get("paypal", {})
    if pp.get("activo") and (not pp.get("url") or re.fullmatch(r"https://paypal\.me/?", pp["url"])):
        problemas.append("don paypal : lien vide ou sans identifiant (à renseigner, ou « activo »: false)")
    mp = d.get("mercadopago", {})
    if mp.get("activo"):
        if not clabe_valide(mp.get("clabe", "")):
            problemas.append("don Mercado Pago : CLABE absente ou invalide (18 chiffres, clé de contrôle)")
        if not mp.get("titular"):
            problemas.append("don Mercado Pago : bénéficiaire absent")
    wi = d.get("wise", {})
    if wi.get("activo") and not wi.get("url"):
        problemas.append("don wise : lien vide (à renseigner, ou « activo »: false)")

    animales = json.loads((BUILD / "data" / "animales.json").read_text(encoding="utf-8"))["animales"]
    ejemplo = sorted(a["nombre"] for a in animales if a.get("id") in FICHES_EXEMPLE)
    if ejemplo:
        problemas.append("fiches d'exemple encore présentes : " + ", ".join(ejemplo))

    for pagina in sorted(BUILD.glob("*.html")):
        texto = pagina.read_text(encoding="utf-8")
        for resto in RESTES_MODELE:
            if resto in texto:
                problemas.append(f"{pagina.name} contient « {resto} »" +
                                 (" : compléter la raison sociale et le domicile du responsable, puis retirer cette marque"
                                  if resto == "PENDIENTE-LEGAL" else " (reste du modèle de démonstration)"))
    if problemas:
        print("\n✗ PRODUCTION REFUSÉE : le site contient encore des données de démonstration.")
        for p in problemas:
            print("   -", p)
        raise SystemExit("\nCorriger ces points (ou FORZAR_PRODUCCION=1 pour passer outre), puis relancer.")
    print("  ✓ contrôle de production : aucune donnée de démonstration détectée")


def zipper():
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for chemin in sorted(BUILD.rglob("*")):
            if chemin.is_file() and not chemin.name.startswith("."):
                z.write(chemin, chemin.relative_to(BUILD))
    return ZIP


if __name__ == "__main__":
    preparer()
    ensamblar_animales()
    if PREPROD:
        noindex()
        bandeau()
    ajustar_url()
    fichiers_netlify()
    sitemap()
    verifier_formularios()
    verifier_cuestionario()
    verificar_produccion()
    print(f"  mode : {'préprod (noindex + bandeau)' if PREPROD else 'PRODUCTION'} · destino : {DESTINO}")
    chemin = zipper()
    poids = chemin.stat().st_size / 1024
    with zipfile.ZipFile(chemin) as z:
        fichiers = z.namelist()
    print(f"✓ {chemin.relative_to(RACINE)} — {poids:.0f} Ko, {len(fichiers)} fichiers")
    for f in fichiers:
        print("   ", f)
