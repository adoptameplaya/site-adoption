#!/usr/bin/env python3
"""
Prueba herramientas/actualizar-servidor.sh con un «GitHub» local (repositorio
git de verdad) y carpetas temporales: nada real se toca.

    python3 herramientas/probar-servidor.py
"""
import os, subprocess, sys, tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent / "actualizar-servidor.sh"
ok = fail = 0
def check(n, c, d=""):
    global ok, fail
    if c: ok += 1; print("  ✓", n)
    else: fail += 1; print("  ✗", n, "→", d)

def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True,
                          env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")).stdout

def publicar(origen: Path, trabajo: Path, archivos: dict):
    """Simula a GitHub Actions: rama huérfana «despliegue» con el sitio construido, forzada."""
    if trabajo.exists():
        import shutil; shutil.rmtree(trabajo)
    trabajo.mkdir(parents=True)
    git(trabajo, "init", "-q", "-b", "despliegue")
    for ruta, cont in archivos.items():
        p = trabajo / ruta; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(cont)
    git(trabajo, "add", "-A", "-f"); git(trabajo, "commit", "-q", "-m", "build")
    git(trabajo, "push", "-q", "--force", str(origen), "despliegue")

def correr(t: Path, dest: Path, url=None):
    env = dict(os.environ, HOME=str(t / "home"), URL_REPO=url or str(t / "origen.git"),
               REPO=str(t / "home" / "adoptameplaya-sitio"), DEST=str(dest), REGISTRO=str(t / "home" / "log.txt"))
    r = subprocess.run(["/bin/sh", str(SCRIPT)], env=env, capture_output=True, text=True)
    log = (t / "home" / "log.txt").read_text() if (t / "home" / "log.txt").exists() else ""
    return r.returncode, r.stderr, log

with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp); (t / "home").mkdir()
    origen = t / "origen.git"; subprocess.run(["git", "init", "-q", "--bare", str(origen)], check=True)
    v1 = {"index.html": "<h1>v1</h1>", ".htaccess": "# v1", "css/a.css": "a{}", "api/auth.php": "<?php //1", "img/x.jpg": "JPG"}
    publicar(origen, t / "ci", v1)

    print("— primer despliegue en una carpeta recién creada por cPanel")
    dest = t / "home" / "adoptameplaya.org"
    (dest / "cgi-bin").mkdir(parents=True); (dest / ".well-known" / "acme-challenge").mkdir(parents=True)
    (dest / ".well-known" / "acme-challenge" / "token").write_text("T"); (dest / "error_log").write_text("e")
    rc, err, log = correr(t, dest)
    check("termina bien", rc == 0, err)
    check("copia el sitio (incluido .htaccess)", (dest / "index.html").read_text() == "<h1>v1</h1>" and (dest / ".htaccess").exists() and (dest / "img" / "x.jpg").exists())
    check("no copia la carpeta .git", not (dest / ".git").exists())
    check("respeta cgi-bin y .well-known (validación del certificado)", (dest / "cgi-bin").is_dir() and (dest / ".well-known" / "acme-challenge" / "token").exists())
    check("deja la marca de «carpeta gestionada»", (dest / ".sitio-adoptameplaya").exists())
    check("lo anota en el registro", "publicado" in log, log)

    print("— sin novedades")
    antes = (t / "home" / "log.txt").read_text()
    rc, err, log = correr(t, dest)
    check("no hace nada y no ensucia el registro", rc == 0 and log == antes, log)

    print("— nueva versión + un secreto puesto a mano en el servidor")
    (dest / "api" / "secrets.php").write_text("<?php SECRETO")
    v2 = {"index.html": "<h1>v2</h1>", ".htaccess": "# v2", "css/b.css": "b{}", "api/auth.php": "<?php //2", "img/x.jpg": "JPG"}
    publicar(origen, t / "ci", v2)                          # historia reescrita (force-push), como en GitHub Actions
    rc, err, log = correr(t, dest)
    check("termina bien tras un force-push", rc == 0, err)
    check("aplica los cambios", (dest / "index.html").read_text() == "<h1>v2</h1>" and (dest / "css" / "b.css").exists())
    check("retira lo que ya no existe", not (dest / "css" / "a.css").exists())
    check("api/secrets.php intacto", (dest / "api" / "secrets.php").read_text() == "<?php SECRETO")
    check(".well-known intacto tras --delete", (dest / ".well-known" / "acme-challenge" / "token").exists())

    print("— el servidor modificó un fichero sin que haya versión nueva")
    (dest / ".htaccess").write_text("# cPanel añadió su bloque PHP")
    rc, err, log = correr(t, dest)
    check("no lo pisa mientras no haya cambios en GitHub", rc == 0 and (dest / ".htaccess").read_text().startswith("# cPanel"))

    print("— GUARDARRAÍL: la carpeta es de OTRO sitio (el caso wptonyoo.fr)")
    for nombre, previo in (("index.php", {"index.php": "<?php //otro"}), ("WordPress", {"wp-config.php": "x"}), ("index.html ajeno", {"index.html": "MI OTRO SITIO"})):
        ajeno = t / "home" / f"otro-{nombre.split()[0]}"
        ajeno.mkdir(parents=True)
        for k, c in previo.items(): (ajeno / k).write_text(c)
        # copia de trabajo limpia para que sea «primera vez» en esta carpeta
        import shutil; shutil.rmtree(t / "home" / "adoptameplaya-sitio", ignore_errors=True)
        antes = {p.name: p.read_text() for p in ajeno.iterdir()}
        rc, err, log = correr(t, ajeno)
        despues = {p.name: p.read_text() for p in ajeno.iterdir()}
        check(f"se niega ante {nombre}", rc == 1 and "ya contiene" in err, (rc, err))
        check(f"…y no toca NADA ({nombre})", antes == despues, set(despues) ^ set(antes))

    print("— GUARDARRAÍL: public_html y carpeta personal")
    ph = t / "home" / "public_html"; ph.mkdir()
    rc, err, _ = correr(t, ph); check("public_html → se niega", rc == 1 and "public_html" in err, (rc, err))
    rc, err, _ = correr(t, t / "home"); check("carpeta personal → se niega", rc == 1, (rc, err))
    rc, err, _ = correr(t, t / "home" / "no-existe"); check("carpeta inexistente → error claro", rc == 1 and "no existe" in err, (rc, err))

    print("— errores de red")
    import shutil; shutil.rmtree(t / "home" / "adoptameplaya-sitio", ignore_errors=True)
    rc, err, log = correr(t, dest, url=str(t / "no-hay-repo.git"))
    check("repositorio inaccesible → error registrado, sin romper el sitio", rc == 1 and "ERROR" in log and (dest / "index.html").exists(), (rc, log))

print(f"\n{ok} correctos, {fail} fallidos"); sys.exit(1 if fail else 0)
