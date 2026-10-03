#!/usr/bin/env python3
"""
Prueba deploy-ftp.py contra un servidor FTP FALSO y estricto (en memoria):
envío incremental, supresión, secretos intactos, y sobre todo el
guardarraíl que impide pisar otro sitio alojado en la misma cuenta.

    python3 herramientas/probar-despliegue.py
"""
import ftplib, importlib.util, os, posixpath, sys, tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("dep", Path(__file__).parent.parent / "deploy-ftp.py")
dep = importlib.util.module_from_spec(spec); spec.loader.exec_module(dep)

FS, DIRS = {}, {""}
FALLAR_EN = {"n": None, "cuenta": 0}          # hace fallar el N-ésimo envío, una vez


class Falso:
    def __init__(self, **k): pass
    def connect(self, h, p): pass
    def login(self, u, m): pass
    def prot_p(self): pass
    def cwd(self, d): pass
    def mkd(self, d):
        if d in DIRS: raise ftplib.error_perm("550 existe")
        if posixpath.dirname(d) not in DIRS: raise ftplib.error_perm("550 falta el padre")
        DIRS.add(d)
    def rmd(self, d):
        if any(f.startswith(d + "/") for f in FS): raise ftplib.error_perm("550 no vacío")
        DIRS.discard(d)
    def nlst(self):
        nombres = {f.split("/")[0] for f in FS} | {d.split("/")[0] for d in DIRS if d}
        if not nombres: raise ftplib.error_perm("550 No files found")
        return sorted(nombres)
    def retrbinary(self, cmd, cb):
        p = cmd[5:]
        if p not in FS: raise ftplib.error_perm("550 no existe")
        cb(FS[p])
    def storbinary(self, cmd, fh):
        p = cmd[5:]
        if posixpath.dirname(p) not in DIRS: raise ftplib.error_perm("550 sin carpeta")
        if FALLAR_EN["n"] is not None:
            FALLAR_EN["cuenta"] += 1
            if FALLAR_EN["cuenta"] == FALLAR_EN["n"]:
                FALLAR_EN["n"] = None
                raise ConnectionResetError("corte de red simulado")
        FS[p] = fh.read()
    def delete(self, p):
        if p not in FS: raise ftplib.error_perm("550 no existe")
        del FS[p]
    def rename(self, a, b):
        if b in FS: raise ftplib.error_perm("550 existe")
        FS[b] = FS.pop(a)
    def quit(self): pass
    def close(self): pass


ftplib.FTP_TLS = Falso; ftplib.FTP = Falso
ok = fail = 0
def check(n, c, d=""):
    global ok, fail
    if c: ok += 1; print("  ✓", n)
    else: fail += 1; print("  ✗", n, "→", d)

def reset(contenido=None, dirs=()):
    FS.clear(); DIRS.clear(); DIRS.add("")
    FALLAR_EN.update(n=None, cuenta=0)
    for d in dirs: DIRS.add(d)
    FS.update(contenido or {})

def conectar(): return dep.Ftp("h", "u", "p", "dir", tls=True)

def intentar(racine):
    """Devuelve None si el despliegue termina, o el mensaje si se detiene."""
    try:
        dep.deployer(racine, conectar()); return None
    except SystemExit as e:
        return str(e)

with tempfile.TemporaryDirectory() as t:
    racine = Path(t)
    (racine / "index.html").write_text("<h1>refugio</h1>")
    (racine / ".htaccess").write_text("# nuestro")
    (racine / "css").mkdir(); (racine / "css" / "style.css").write_text("a{}")
    (racine / "api").mkdir(); (racine / "api" / "auth.php").write_text("<?php")
    os.environ.pop("FTP_ALLOW_OVERWRITE", None)

    print("— carpeta vacía (la de un dominio recién creado en cPanel)")
    reset(dirs=["cgi-bin"])
    msg = intentar(racine)
    check("se despliega", msg is None and FS.get("index.html") == b"<h1>refugio</h1>", msg)
    check("deja el manifiesto", dep.MANIFESTE in FS)

    print("— cPanel ya creó un .htaccess (versión de PHP elegida)")
    reset({".htaccess": b"# php handler de cPanel"}, dirs=["cgi-bin"])
    msg = intentar(racine); check("no bloquea: se despliega", msg is None and "index.html" in FS, msg)

    print("— OTRO SITIO en la carpeta (el caso wptonyoo.fr)")
    for nombre, previo in (("index.html", {"index.html": b"MI OTRO SITIO"}),
                           ("index.php", {"index.php": b"<?php //otro"}),
                           ("WordPress", {"wp-config.php": b"x"})):
        reset(previo); antes = dict(FS)
        msg = intentar(racine)
        check(f"se detiene ante {nombre}", msg is not None and "ARRÊT" in msg, msg)
        check(f"…y no modifica NADA ({nombre})", FS == antes, set(FS) ^ set(antes))
    reset({"index.html": b"MI OTRO SITIO"})
    check("el mensaje nombra la causa y la salida", "FTP_DIR" in (intentar(racine) or "") and "FTP_ALLOW_OVERWRITE" in (intentar(racine) or ""))

    print("— salida de emergencia explícita")
    reset({"index.html": b"MI OTRO SITIO"}); os.environ["FTP_ALLOW_OVERWRITE"] = "1"
    msg = intentar(racine); os.environ.pop("FTP_ALLOW_OVERWRITE")
    check("FTP_ALLOW_OVERWRITE=1 permite continuar", msg is None and FS["index.html"] == b"<h1>refugio</h1>", msg)

    print("— primer envío interrumpido, luego reintento")
    reset(dirs=["cgi-bin"]); FALLAR_EN.update(n=3, cuenta=0)
    try: dep.deployer(racine, conectar()); cayo = False
    except ConnectionResetError: cayo = True
    check("el corte de red interrumpe el envío", cayo)
    check("quedó el marcador de «carpeta gestionada»", FS.get(dep.MANIFESTE) == b"{}", FS.get(dep.MANIFESTE))
    msg = intentar(racine)
    check("el reintento NO se bloquea con sus propios archivos", msg is None, msg)
    check("…y completa el sitio", all(f in FS for f in ("index.html", ".htaccess", "css/style.css", "api/auth.php")), sorted(FS))
    check("sin archivos temporales", not [f for f in FS if f.endswith(".deploy-tmp")])

    print("— despliegues siguientes")
    FS["api/secrets.php"] = b"SECRETO"; DIRS.add("api")
    (racine / "css" / "style.css").write_text("a{color:red}")
    (racine / "api" / "auth.php").unlink()
    msg = intentar(racine)
    check("cambio aplicado", msg is None and FS["css/style.css"] == b"a{color:red}", msg)
    check("fichero retirado del repositorio → retirado del servidor", "api/auth.php" not in FS)
    check("secrets.php puesto a mano: intacto", FS.get("api/secrets.php") == b"SECRETO")
    check("el guardarraíl no vuelve a molestar (hay manifiesto)", msg is None)

print(f"\n{ok} correctos, {fail} fallidos"); sys.exit(1 if fail else 0)
