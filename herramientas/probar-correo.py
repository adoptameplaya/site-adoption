#!/usr/bin/env python3
"""
Prueba api/enviar.php (envío de formularios por correo desde el servidor del sitio) con el servidor
integrado de PHP. NADA sale de la máquina : los correos se escriben como archivos .eml en una carpeta
temporal (ADOPTAME_CORREO_PRUEBA).

    python3 herramientas/probar-correo.py

Necesita PHP ≥ 8.0 ($PHP_BIN, ~/.local/php/bin/php o el PATH).
"""
import email, email.policy, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parent
ok_n = fail_n = 0


def check(nombre, cond, detalle=""):
    global ok_n, fail_n
    if cond:
        ok_n += 1
        print("  ✓", nombre)
    else:
        fail_n += 1
        print("  ✗", nombre, "→", detalle)


def buscar_php():
    for c in (os.environ.get("PHP_BIN"), os.path.expanduser("~/.local/php/bin/php"), shutil.which("php")):
        if c and os.access(c, os.X_OK):
            return c
    sys.exit("No encuentro PHP. Define PHP_BIN=/ruta/a/php")


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Servidor:
    def __init__(self, php, raiz, correos, respaldo, secretos=None):
        self.raiz, self.correos, self.respaldo = Path(raiz), Path(correos), Path(respaldo)
        if secretos is not None:
            (self.raiz / "api" / "secrets.php").write_text("<?php return " + json.dumps(secretos).replace("{", "[").replace("}", "]").replace('":', '"=>') + ";", encoding="utf-8")
        self.puerto = puerto_libre()
        env = dict(os.environ, ADOPTAME_CORREO_PRUEBA=str(correos), ADOPTAME_RESPALDO=str(respaldo))
        self.proc = subprocess.Popen([php, "-S", f"127.0.0.1:{self.puerto}", "-t", str(raiz)], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", self.puerto), 0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    def parar(self):
        self.proc.terminate()

    def post(self, cuerpo, origen="auto", metodo="POST", bruto=None):
        url = f"http://127.0.0.1:{self.puerto}/api/enviar.php"
        datos = bruto if bruto is not None else json.dumps(cuerpo).encode("utf-8")
        cab = {"Content-Type": "application/json"}
        if origen == "auto":
            cab["Origin"] = f"http://127.0.0.1:{self.puerto}"
        elif origen:
            cab["Origin"] = origen
        req = urllib.request.Request(url, data=None if metodo == "GET" else datos, headers=cab, method=metodo)
        try:
            r = urllib.request.urlopen(req, timeout=20)
            return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}

    def reiniciar_limites(self):
        shutil.rmtree(self.respaldo / "limites", ignore_errors=True)

    def correos_escritos(self):
        return sorted(self.correos.glob("*.eml")) if self.correos.exists() else []


def leer(eml):
    return email.message_from_bytes(Path(eml).read_bytes(), policy=email.policy.default)


def cuerpo_texto(m):
    parte = m.get_body(preferencelist=("plain",))
    return parte.get_content() if parte else ""


def cuerpo_html(m):
    parte = m.get_body(preferencelist=("html",))
    return parte.get_content() if parte else ""


def asunto(m):
    return str(m["Subject"])


def base(**extra):
    d = {"tipo": "hogar", "idioma": "es", "especie": "", "nombre": "María Pérez", "email": "maria@example.com", "animal": "",
         "texto": "== INFORMACIÓN BÁSICA ==\n1. Nombre completo\n   > María Pérez\n16. ¿Qué comportamientos…?\n   > [x] Ansiedad por separación ligera\n" * 2,
         "t": int((time.time() - 120) * 1000), "hp": ""}
    d.update(extra)
    return d


def main():
    php = buscar_php()
    print(subprocess.run([php, "-v"], capture_output=True, text=True).stdout.splitlines()[0])
    for f in ("_correo.php", "enviar.php"):
        r = subprocess.run([php, "-l", str(RAIZ / "api" / f)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
    print("sintaxis OK\n")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raiz = tmp / "web"
        (raiz / "api").mkdir(parents=True)
        (raiz / "data").mkdir()
        for f in ("_comun.php", "_correo.php", "enviar.php"):
            shutil.copy(RAIZ / "api" / f, raiz / "api" / f)
        shutil.copy(RAIZ / "data" / "config.json", raiz / "data" / "config.json")
        S = Servidor(php, raiz, tmp / "correos", tmp / "respaldo")
        try:
            print("— solicitud correcta (hogar temporal)")
            c, r = S.post(base())
            check("responde 200 ok", c == 200 and r.get("ok") is True, (c, r))
            mails = S.correos_escritos()
            check("se escriben 2 correos (asociación + persona)", len(mails) == 2, len(mails))
            if len(mails) == 2:
                a, p = leer(mails[0]), leer(mails[1])
                check("asociación : destinatario = el de config.json", "adoptameplaya@gmail.com" in str(a["To"]), a["To"])
                check("asociación : asunto con el nombre", asunto(a) == "Cuestionario de hogar temporal — María Pérez", asunto(a))
                check("asociación : «Responder» va a la persona", "maria@example.com" in str(a["Reply-To"]), a["Reply-To"])
                check("asociación : el cuerpo lleva las respuestas", "[x] Ansiedad por separación ligera" in cuerpo_texto(a))
                check("asociación : remitente del dominio", "@adoptameplaya.org" in str(a["From"]), a["From"])
                check("persona : destinatario correcto", "maria@example.com" in str(p["To"]), p["To"])
                check("persona : asunto en español", asunto(p) == "Recibimos tu cuestionario de hogar temporal", asunto(p))
                h = cuerpo_html(p)
                check("persona : HTML con logo, título y botón de WhatsApp",
                      "favicon-192.png" in h and "¡Gracias por querer ser hogar temporal!" in h and "Escribirnos por WhatsApp" in h and "wa.me/17142248714" in h)
                check("persona : copia de las respuestas", "Copia de tus respuestas" in h and "Ansiedad por separación ligera" in h)
                check("persona : parte de texto plano presente", "Hola María Pérez" in cuerpo_texto(p))
                check("persona : marcado como automático", "auto-generated" in str(p["Auto-Submitted"]))
            check("se guarda un respaldo", len(list((tmp / "respaldo").glob("*.json"))) == 1)

            print("— seguridad de los datos")
            n0 = len(S.correos_escritos())
            c, r = S.post(base(nombre='<b>Mal</b>\r\nBcc: robot@evil.test', email="otro1@example.com", texto="x" * 40 + "\n<script>alert(1)</script>"))
            check("acepta pero sanea", c == 200, (c, r))
            nuevos = S.correos_escritos()[n0:]
            if len(nuevos) == 2:
                crudo = Path(nuevos[0]).read_text(encoding="utf-8", errors="replace") + Path(nuevos[1]).read_text(encoding="utf-8", errors="replace")
                check("ninguna cabecera inyectada (Bcc)", "\r\nBcc:" not in crudo and "\nBcc:" not in crudo)
                h = cuerpo_html(leer(nuevos[1]))
                check("el HTML escapa el nombre y el texto (sin <script> ni <b>)", "<script>" not in h and "<b>Mal" not in h and "&lt;b&gt;Mal" in h)
            else:
                check("2 correos nuevos", False, len(nuevos))

            print("— robots y abusos")
            n1 = len(S.correos_escritos())
            c, r = S.post(base(email="bot@example.com", hp="soy un robot"))
            check("campo trampa : responde ok pero NO envía", c == 200 and len(S.correos_escritos()) == n1, (c, len(S.correos_escritos()), n1))
            c, r = S.post(base(email="rapido@example.com", t=int(time.time() * 1000)))
            check("demasiado rápido : 400", c == 400, (c, r))
            c, r = S.post(base(email="sin-t@example.com", t=None))
            check("sin marca de tiempo : 400", c == 400, (c, r))
            c, r = S.post(base(email="x@example.com"), origen="https://evil.example")
            check("origen ajeno : 403", c == 403, (c, r))
            c, r = S.post(base(email="x@example.com"), origen=None)
            check("sin Origin ni Referer : 403", c == 403, (c, r))
            c, r = S.post(None, metodo="GET")
            check("GET : 405", c == 405, (c, r))
            c, r = S.post(None, bruto=b"{no es json")
            check("JSON roto : 400", c == 400, (c, r))
            c, r = S.post(None, bruto=json.dumps(base(texto="y" * 90000)).encode())
            check("cuerpo enorme : 413", c == 413, (c, r))
            for mal, nombre in (({"email": "no-es-un-correo"}, "correo inválido"), ({"nombre": ""}, "sin nombre"),
                                ({"texto": "corto"}, "texto demasiado corto"), ({"tipo": "otro"}, "tipo desconocido")):
                c, r = S.post(base(**mal))
                check(f"{nombre} : 400", c == 400, (c, r))
            check("nada de lo anterior envió correos", len(S.correos_escritos()) == n1)

            print("— doble clic y límites")
            S.reiniciar_limites()
            d = base(email="doble@example.com")
            c1, r1 = S.post(d)
            n2 = len(S.correos_escritos())
            c2, r2 = S.post(d)
            check("la misma solicitud dos veces : se envía una sola", c1 == 200 and c2 == 200 and r2.get("repetida") and len(S.correos_escritos()) == n2, (r1, r2))
            codigos = []
            for k in range(6):
                c, r = S.post(base(email="limite@example.com", texto=f"respuesta distinta número {k} " * 4))
                codigos.append(c)
            check("más de 4 por correo al día : 429", codigos[:4] == [200] * 4 and 429 in codigos[4:], codigos)
            S.reiniciar_limites()
            codigos = [S.post(base(email=f"ip{k}@example.com", texto=f"otra respuesta {k} " * 5))[0] for k in range(8)]
            check("más de 6 por hora desde la misma dirección : 429", codigos[:6] == [200] * 6 and codigos[6:] == [429, 429], codigos)
            S.reiniciar_limites()

            print("— solicitud de formulario (formulario pequeño de la portada) y versión en inglés")
            c, r = S.post(base(tipo="solicitud", especie="gato", idioma="en", animal="THEODOR", texto="", email="ana@example.com", nombre="Ana", t=int((time.time() - 30) * 1000)))
            check("responde 200", c == 200 and r.get("ok"), (c, r))
            m = S.correos_escritos()[-2:]
            a, p = leer(m[0]), leer(m[1])
            check("asociación : asunto de solicitud", asunto(a) == "Solicitud de formulario de adopción — Ana", asunto(a))
            h = cuerpo_html(p)
            check("persona (EN) : título y botones", "Thank you for your interest in adopting!" in h and "Fill in the form online" in h and "Download the form as a PDF" in h)
            check("botón en línea con especie, idioma y animal", "cuestionario.html?especie=gato&amp;lang=en&amp;animal=THEODOR" in h, h[:0])
            check("botón PDF del gato en inglés", "formularios/Adoption_Questionnaire_Cat_EN.pdf" in h)
            check("asunto de la persona en inglés", asunto(p) == "Your adoption form · Adopta Me Playa", asunto(p))

            print("— cuestionario de adopción")
            c, r = S.post(base(tipo="adopcion", especie="perro", animal="DOBBY", email="luis@example.com", nombre="Luis"))
            check("responde 200", c == 200 and r.get("ok"), (c, r))
            m = S.correos_escritos()[-2:]
            a, p = leer(m[0]), leer(m[1])
            check("asociación : asunto con el animal", asunto(a) == "Cuestionario de adopción — Luis · DOBBY", asunto(a))
            check("persona : menciona al animal", "para DOBBY" in cuerpo_texto(p), cuerpo_texto(p)[:200])
        finally:
            S.parar()

        print("— interruptor «envio_directo = no»")
        raiz2 = tmp / "web2"
        shutil.copytree(raiz, raiz2)
        S2 = Servidor(php, raiz2, tmp / "correos2", tmp / "respaldo2", secretos={"envio_directo": "no"})
        try:
            c, r = S2.post(base(email="off@example.com"))
            check("desactivado : 503 y nada enviado", c == 503 and not S2.correos_escritos(), (c, r))
        finally:
            S2.parar()

    print(f"\n{ok_n} correctos, {fail_n} fallidos")
    sys.exit(1 if fail_n else 0)


if __name__ == "__main__":
    main()
