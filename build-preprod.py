#!/usr/bin/env python3
"""
Génère dist/refugio-preprod.zip : la version à déposer sur Netlify
tant que les vraies données du refuge ne sont pas arrivées.

Différences avec le site final :
  - noindex partout (robots.txt + netlify.toml + balise meta)
  - bandeau « sitio de demostración » en haut de page
  - les fichiers de travail (.md, servir.command, ce script) sont exclus

Usage : python3 build-preprod.py
"""
import json, os, re, shutil, zipfile
from pathlib import Path

# preprod = bandeau de démo + noindex ; produccion = site public.
# Sur Netlify, se règle dans Site settings → Environment variables.
MODO = os.environ.get("MODO", "preprod").strip().lower()
PREPROD = MODO != "produccion"

RACINE = Path(__file__).parent.resolve()
DIST   = RACINE / "dist"
BUILD  = DIST / "preprod"
ZIP    = DIST / "refugio-preprod.zip"

A_COPIER = ["index.html", "aviso-de-privacidad.html", "gracias.html", "cuestionario.html", "admin", "css", "js", "data", "img", "formularios"]


def preparer():
    if DIST.exists():
        shutil.rmtree(DIST)
    BUILD.mkdir(parents=True)
    for nom in A_COPIER:
        src = RACINE / nom
        dst = BUILD / nom
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


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
        '  "demo.d": "Los animales, el nombre del refugio y los datos bancarios son de ejemplo. '
        'Nada de esta página es real todavía."\n'
        "});\n"
        "Object.assign(window.TEXTOS.en, {\n"
        '  "demo.t": "Demo site.",\n'
        '  "demo.d": "The animals, the shelter name and the bank details are placeholders. '
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
                print(f"  · {especie}/{lang} : pas de formulaire → l'auto-réponse annoncera un envoi manuel")
            elif not (BUILD / ruta).exists():
                raise SystemExit(f"ERREUR : config.json référence {ruta} pour {especie}/{lang}, "
                                 f"mais le fichier est absent du build.")
            else:
                ko = (BUILD / ruta).stat().st_size / 1024
                print(f"  · {especie}/{lang} : {ruta} ({ko:.0f} Ko)")


def fichiers_netlify():
    """robots.txt et en-têtes, adaptés au mode.

    Ce netlify.toml est celui du SITE PUBLIÉ (dossier dist/preprod). Il ne
    décrit pas la construction : celle-ci est pilotée par le netlify.toml
    à la racine du dépôt, que Netlify lit avant de lancer le build.
    """
    if PREPROD:
        robots = ("# Préprod : rien ne doit être indexé tant que les données sont fictives.\n"
                  "User-agent: *\n"
                  "Disallow: /\n")
        cabeceras = ("# Ceinture et bretelles : robots.txt seul ne suffit pas toujours.\n"
                     "[[headers]]\n"
                     '  for = "/*"\n'
                     "  [headers.values]\n"
                     '    X-Robots-Tag = "noindex, nofollow"\n')
    else:
        robots = ("User-agent: *\n"
                  "Allow: /\n"
                  "Disallow: /admin/\n")
        cabeceras = ("# L'espace d'administration ne doit jamais être indexé.\n"
                     "[[headers]]\n"
                     '  for = "/admin/*"\n'
                     "  [headers.values]\n"
                     '    X-Robots-Tag = "noindex, nofollow"\n')

    (BUILD / "robots.txt").write_text(robots)
    (BUILD / "netlify.toml").write_text(
        "# Fichier du site publié. La construction est décrite à la racine du dépôt.\n"
        "[build]\n"
        '  publish = "."\n\n'
        + cabeceras +
        "\n# Les JSON changent souvent, ils ne doivent pas rester en cache :\n"
        "# une fiche modifiée dans l'admin doit apparaître tout de suite.\n"
        "[[headers]]\n"
        '  for = "/data/*"\n'
        "  [headers.values]\n"
        '    Cache-Control = "public, max-age=0, must-revalidate"\n'
    )


def zipper():
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for chemin in sorted(BUILD.rglob("*")):
            if chemin.is_file() and not chemin.name.startswith("."):
                z.write(chemin, chemin.relative_to(BUILD))
    return ZIP


if __name__ == "__main__":
    preparer()
    if PREPROD:
        noindex()
        bandeau()
    fichiers_netlify()
    verifier_formularios()
    print(f"  mode : {'préprod (noindex + bandeau)' if PREPROD else 'PRODUCTION'}")
    chemin = zipper()
    poids = chemin.stat().st_size / 1024
    with zipfile.ZipFile(chemin) as z:
        fichiers = z.namelist()
    print(f"✓ {chemin.relative_to(RACINE)} — {poids:.0f} Ko, {len(fichiers)} fichiers")
    for f in fichiers:
        print("   ", f)
