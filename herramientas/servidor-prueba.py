#!/usr/bin/env python3
"""
Servidor de PRUEBA para el panel del refugio. Simula lo justo de la API de
GitHub (refs, commits, árboles, blobs) y del script de traducción, para
probar el panel de punta a punta sin tocar el dépôt real.

    python3 herramientas/servidor-prueba.py --raiz /ruta/a/una/COPIA --puerto 8765
    → abrir http://localhost:8765/admin/?dev

Los commits del panel se materializan en --raiz (data/animales y img/animales).
¡Usar una copia, no el proyecto!

    --sin-traduccion   el servicio de traducción responde 503
    --lento            tarda 1 s por llamada a la API (probar los estados de carga)
"""
import argparse, base64, hashlib, json, os, re, sys, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SEGUIDOS = ("data/animales/", "img/animales/")
ARGS = None
ROOT = None
BLOBS = {}      # sha -> bytes
ARBOLES = {}    # id  -> {ruta: sha}
COMMITS = {}    # sha -> {"tree": id, "parents": [...], "message": str}
HEAD = {"sha": ""}
LOG = []


def sha_blob(datos: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(datos) + datos).hexdigest()


def sha_obj(tipo: str, contenido: str) -> str:
    return hashlib.sha1(f"{tipo}:{contenido}:{time.time_ns()}".encode()).hexdigest()


def escanear() -> dict:
    arbol = {}
    for p in sorted(ROOT.rglob("*")):
        if p.is_file():
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(SEGUIDOS):
                datos = p.read_bytes()
                s = sha_blob(datos)
                BLOBS[s] = datos
                arbol[rel] = s
    return arbol


def materializar(arbol: dict):
    """Refleja el árbol en el disco, para poder construir el sitio después."""
    actuales = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob("*")
                if p.is_file() and p.relative_to(ROOT).as_posix().startswith(SEGUIDOS)}
    for rel, p in actuales.items():
        if rel not in arbol:
            p.unlink()
    for rel, s in arbol.items():
        destino = ROOT / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists() or sha_blob(destino.read_bytes()) != s:
            destino.write_bytes(BLOBS[s])


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        # En pruebas, nunca servir de la caché del navegador.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/mock/" in (args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _autorizado(self):
        return self.headers.get("Authorization", "") == "Bearer dev" or self.headers.get("X-Token-GitHub") == "dev"

    # ------------------------------------------------------------ GET
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/mock/github/"):
            return self.github("GET", u.path[len("/mock/github"):], parse_qs(u.query))
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/mock/traducir":
            return self.traducir()
        if u.path.startswith("/mock/github/"):
            return self.github("POST", u.path[len("/mock/github"):], {})
        self.send_error(404)

    def do_PATCH(self):
        u = urlparse(self.path)
        if u.path.startswith("/mock/github/"):
            return self.github("PATCH", u.path[len("/mock/github"):], {})
        self.send_error(404)

    # ------------------------------------------------------------ traducción
    def traducir(self):
        if not self._autorizado():
            return self._json(401, {"ok": False, "error": "Sesión no válida."})
        d = self._cuerpo()
        if ARGS.sin_traduccion:
            return self._json(503, {"ok": False, "error": "La traducción automática aún no está configurada."})
        LOG.append(("traducir", d.get("textos")))
        return self._json(200, {"ok": True, "textos": ["[EN] " + t for t in d.get("textos", [])]})

    # ------------------------------------------------------------ GitHub
    def github(self, metodo, ruta, q):
        if ARGS.lento:
            time.sleep(1)
        if not self._autorizado():
            return self._json(401, {"message": "Bad credentials"})
        m = re.match(r"^/repos/([^/]+)/([^/]+)(/.*)?$", ruta)
        if ruta == "/user":
            return self._json(200, {"login": "tester", "avatar_url": ""})
        if not m:
            return self._json(404, {"message": "Not Found"})
        sub = m.group(3) or ""

        if sub == "" and metodo == "GET":
            return self._json(200, {"full_name": f"{m.group(1)}/{m.group(2)}", "permissions": {"push": not ARGS.solo_lectura}})

        if sub == "/git/ref/heads/main" and metodo == "GET":
            return self._json(200, {"object": {"sha": HEAD["sha"]}})

        mc = re.match(r"^/git/commits/([0-9a-f]+)$", sub)
        if mc and metodo == "GET":
            c = COMMITS.get(mc.group(1))
            return self._json(200, {"sha": mc.group(1), "tree": {"sha": c["tree"]}}) if c else self._json(404, {"message": "Not Found"})

        mt = re.match(r"^/git/trees/([0-9a-f]+)$", sub)
        if mt and metodo == "GET":
            a = ARBOLES.get(mt.group(1))
            if a is None:
                return self._json(404, {"message": "Not Found"})
            return self._json(200, {"tree": [{"path": r, "type": "blob", "mode": "100644", "sha": s} for r, s in a.items()], "truncated": False})

        mb = re.match(r"^/git/blobs/([0-9a-f]+)$", sub)
        if mb and metodo == "GET":
            b = BLOBS.get(mb.group(1))
            return self._json(200, {"content": base64.b64encode(b).decode(), "encoding": "base64"}) if b is not None else self._json(404, {"message": "Not Found"})

        if sub == "/git/blobs" and metodo == "POST":
            d = self._cuerpo()
            datos = base64.b64decode(d["content"]) if d.get("encoding") == "base64" else d["content"].encode("utf-8")
            s = sha_blob(datos)
            BLOBS[s] = datos
            return self._json(201, {"sha": s})

        if sub == "/git/trees" and metodo == "POST":
            d = self._cuerpo()
            base = dict(ARBOLES.get(d.get("base_tree"), {}))
            for e in d["tree"]:
                if e["sha"] is None:
                    if e["path"] not in base:
                        return self._json(422, {"message": f"tree.sha nulo para una ruta inexistente: {e['path']}"})
                    del base[e["path"]]
                else:
                    if e["sha"] not in BLOBS:
                        return self._json(422, {"message": "blob desconocido"})
                    base[e["path"]] = e["sha"]
            tid = sha_obj("tree", json.dumps(sorted(base.items())))
            ARBOLES[tid] = base
            return self._json(201, {"sha": tid})

        if sub == "/git/commits" and metodo == "POST":
            d = self._cuerpo()
            sha = sha_obj("commit", d["message"])
            COMMITS[sha] = {"tree": d["tree"], "parents": d["parents"], "message": d["message"]}
            return self._json(201, {"sha": sha})

        if sub == "/git/refs/heads/main" and metodo == "PATCH":
            d = self._cuerpo()
            c = COMMITS.get(d["sha"])
            if not c or c["parents"] != [HEAD["sha"]]:
                return self._json(422, {"message": "Update is not a fast forward"})
            HEAD["sha"] = d["sha"]
            materializar(ARBOLES[c["tree"]])
            LOG.append(("commit", c["message"], sorted(ARBOLES[c["tree"]])))
            print(f"  ✔ commit: {c['message']}", file=sys.stderr)
            return self._json(200, {"ref": "refs/heads/main", "object": {"sha": d["sha"]}})

        if sub.startswith("/actions/runs") and metodo == "GET":
            return self._json(200, {"workflow_runs": [{"status": "completed", "conclusion": "success"}]})

        return self._json(404, {"message": f"Mock: ruta no implementada {metodo} {sub}"})


def main():
    global ARGS, ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-traduccion", action="store_true")
    ap.add_argument("--solo-lectura", action="store_true")
    ap.add_argument("--lento", action="store_true")
    ARGS = ap.parse_args()
    ROOT = Path(ARGS.raiz).resolve()
    if (ROOT / ".git").exists():
        sys.exit("¡--raiz parece un repositorio real! Usa una copia.")

    arbol = escanear()
    tid = sha_obj("tree", "inicial")
    ARBOLES[tid] = arbol
    HEAD["sha"] = sha_obj("commit", "inicial")
    COMMITS[HEAD["sha"]] = {"tree": tid, "parents": [], "message": "inicial"}
    print(f"Servidor de prueba en http://localhost:{ARGS.puerto}/admin/?dev   (raíz: {ROOT}, {len(arbol)} archivos seguidos)", file=sys.stderr)
    ThreadingHTTPServer(("127.0.0.1", ARGS.puerto), H).serve_forever()


if __name__ == "__main__":
    main()
