#!/usr/bin/env python3
"""
Genera el archivo de secretos del servidor (secrets-adoptameplaya.php) EN TU
MAC, sin pasar por el navegador ni por el editor de cPanel (que puede traducir
el codigo).

Un solo pegado: el SECRETO CLIENTE de GitHub. Nada de lo que escribes se muestra
jamas en pantalla. Antes de escribir el archivo, se comprueba con GitHub que el
par ID cliente / secreto es valido.

    python3 herramientas/rellenar-secretos.py [--sin-verificacion]

Resultado: ~/Desktop/Claude/secrets-adoptameplaya.php (permisos 600).
Despues se sube a /home/cupa8096 con "Televerser" y se BORRA del Mac.
"""
import base64, getpass, json, os, re, sys, urllib.error, urllib.request
from pathlib import Path

DESTINO = Path.home() / "Desktop" / "Claude" / "secrets-adoptameplaya.php"
ID_POR_DEFECTO = "Ov23lifoMfpwD7eFa4Dm"      # publico: figura en la pagina de la aplicacion OAuth
RE_ID = re.compile(r"Ov23[A-Za-z0-9]{16}")
RE_SECRETO = re.compile(r"[0-9a-f]{40}")


def php(s: str) -> str:
    """Cadena PHP entre comillas simples: solo \\ y ' necesitan escape."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def generar(client_id: str, client_secret: str, deepl_key: str = "",
            repo: str = "adoptameplaya/site-adoption", site_url: str = "https://adoptameplaya.org") -> str:
    return f"""<?php
/* Secretos de adoptameplaya.org
   Este archivo NO va en GitHub. Vive en /home/cupa8096, FUERA de la carpeta web:
   ninguna direccion de internet puede llegar hasta aqui. */
return [
    'github_client_id'     => {php(client_id)},
    'github_client_secret' => {php(client_secret)},

    'github_repo'          => {php(repo)},
    'site_url'             => {php(site_url)},

    /* Clave de DeepL (termina en :fx). Vacia = el panel funciona igual,
       pero las fichas se publican sin version en ingles automatica. */
    'deepl_key'            => {php(deepl_key)},
];
"""


def diagnosticar(valor: str, esperado: str) -> str:
    """Explica QUE se ha pegado, sin mostrar su contenido."""
    n = len(valor)
    if n == 0:
        return "No he recibido nada."
    if esperado == "secreto":
        if RE_ID.fullmatch(valor):
            return "Eso es el ID cliente (empieza por Ov23), no el secreto."
        if n % 2 == 0 and valor[: n // 2] == valor[n // 2:] and RE_SECRETO.fullmatch(valor[: n // 2]):
            return f"Se ha pegado DOS veces ({n} caracteres). Pega solo una."
        return f"Recibidos {n} caracteres; un secreto de GitHub tiene 40 (cifras y letras a-f)."
    if RE_SECRETO.fullmatch(valor):
        return "Eso parece un SECRETO, no el ID cliente. No lo pegues aqui."
    return f"Recibidos {n} caracteres; el ID cliente empieza por Ov23 y tiene 20."


def pedir(texto: str, esperado: str, patron) -> str:
    for _ in range(4):
        valor = getpass.getpass(texto).strip()          # getpass: NUNCA se muestra
        if patron.fullmatch(valor):
            return valor
        print("   ->", diagnosticar(valor, esperado), "Vuelve a intentarlo.\n")
    sys.exit("Demasiados intentos. No se ha escrito nada.")


def verificar(cid: str, secreto: str) -> str:
    """'ok' | 'rechazado' | 'inconcluso'. GitHub acepta el par (404: token inexistente)
    o lo rechaza con 401; el secreto no sale de este equipo salvo hacia api.github.com."""
    req = urllib.request.Request(
        f"https://api.github.com/applications/{cid}/token", method="POST",
        data=json.dumps({"access_token": "gho_comprobacion_inexistente"}).encode(),
        headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{secreto}".encode()).decode(),
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "User-Agent": "adopta-me-playa-rellenar-secretos"})
    try:
        urllib.request.urlopen(req, timeout=20)
        return "ok"
    except urllib.error.HTTPError as e:
        return "rechazado" if e.code == 401 else ("ok" if e.code in (404, 422) else "inconcluso")
    except Exception:
        return "inconcluso"


def main():
    print(__doc__)
    cid = ID_POR_DEFECTO
    verificacion = "--sin-verificacion" not in sys.argv

    for intento in range(3):
        secreto = pedir("Pega el SECRETO CLIENTE (no se ve al pegarlo) y pulsa Entrar : ", "secreto", RE_SECRETO)
        if not verificacion:
            break
        print("   Comprobando con GitHub...")
        r = verificar(cid, secreto)
        if r == "ok":
            print("   OK: GitHub acepta este par ID cliente / secreto.\n")
            break
        if r == "inconcluso":
            print("   No he podido comprobarlo (sin conexion?). Se escribe igualmente.\n")
            break
        print("   GitHub RECHAZA este par. Dos causas posibles:")
        print("     - el secreto no es el mas reciente (genera uno nuevo y borra los demas), o")
        print("     - el ID cliente memorizado no es el de tu aplicacion.")
        if intento < 2:
            cid = pedir("Pega el ID CLIENTE de tu aplicacion (empieza por Ov23) : ", "id", RE_ID)
    else:
        sys.exit("GitHub no acepta ese par. No se ha escrito nada.")

    if DESTINO.exists():
        print(f"(Se reemplaza el archivo anterior: {DESTINO.name})")
    DESTINO.write_text(generar(cid, secreto), encoding="utf-8")
    os.chmod(DESTINO, 0o600)
    print(f"LISTO: {DESTINO}")
    print(f"       ID cliente : {cid[:4]}...{cid[-2:]} ({len(cid)} caracteres)")
    print(f"       secreto    : {len(secreto)} caracteres (no se muestra)")
    print("\nSiguiente: subir ese archivo a /home/cupa8096 (marcando 'Ecraser'), y borrarlo del Mac:")
    print(f"       rm -P '{DESTINO}'")
    input("\nPulsa Entrar para cerrar.")


if __name__ == "__main__":
    main()
