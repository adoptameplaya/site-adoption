#!/usr/bin/env python3
"""
Prueba los scripts PHP de api/ (auth, callback, traducir) con el servidor
integrado de PHP, sin tocar nada real.

    python3 herramientas/probar-api.py

Dos series :
  1. «red»  : los archivos reales; los casos de rechazo llaman al GitHub real
              con credenciales falsas (hace falta conexión a internet).
  2. «stub» : los mismos archivos, con SOLO la función http() sustituida por un
              GitHub y un DeepL simulados, para recorrer los casos de éxito.

Necesita PHP (≥ 8.0, con curl). Se busca en $PHP_BIN, en ~/.local/php/bin/php
y en el PATH. Los archivos de prueba se crean en una carpeta temporal.
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

AQUI = Path(__file__).parent
API = AQUI.parent / "api"


def buscar_php():
    for c in (os.environ.get("PHP_BIN"), os.path.expanduser("~/.local/php/bin/php"), shutil.which("php")):
        if c and os.access(c, os.X_OK):
            return c
    sys.exit("No encuentro PHP. Define PHP_BIN=/ruta/a/php")


STUB = r'''/* STUB DE PRUEBA : sustituye únicamente http(); el resto del archivo es el real. */
function http(string $metodo, string $url, array $cabeceras = [], ?string $cuerpo = null, int $limite = 15): array
{
    $cfg = json_decode((string) @file_get_contents(__DIR__ . '/stub.cfg'), true) ?: [];
    file_put_contents(__DIR__ . '/stub.log', json_encode(['m' => $metodo, 'u' => $url, 'h' => $cabeceras, 'b' => $cuerpo], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);
    if (strpos($url, 'github.com/login/oauth/access_token') !== false) {
        return [200, $cfg['token_body'] ?? '{}'];
    }
    if (strpos($url, 'api.github.com/repos/') !== false) {
        $auth = implode(' ', $cabeceras);
        if (strpos($auth, 'Bearer good') !== false) return [200, json_encode(['permissions' => ['push' => true]])];
        if (strpos($auth, 'Bearer ro') !== false)   return [200, json_encode(['permissions' => ['push' => false, 'pull' => true]])];
        return [401, '{"message":"Bad credentials"}'];
    }
    if (strpos($url, 'deepl.com/v2/translate') !== false) {
        $st = $cfg['deepl_status'] ?? 200;
        if ($st !== 200) return [$st, '{}'];
        $pedido = json_decode((string) $cuerpo, true);
        $n = $cfg['deepl_count'] ?? count($pedido['text']);
        $out = [];
        for ($k = 0; $k < $n; $k++) $out[] = ['detected_source_language' => 'ES', 'text' => 'EN: ' . ($pedido['text'][$k] ?? '?')];
        return [200, json_encode(['translations' => $out], JSON_UNESCAPED_UNICODE)];
    }
    return [599, ''];
}
'''


def preparar(destino: Path, con_stub: bool):
    destino.mkdir(parents=True)
    for f in ("_comun.php", "auth.php", "callback.php", "traducir.php"):
        shutil.copy(API / f, destino / f)
    if con_stub:
        p = destino / "_comun.php"
        s = p.read_text(encoding="utf-8")
        i = s.index("/* Petición HTTPS sencilla con cURL")
        p.write_text(s[:i] + STUB, encoding="utf-8")


def main():
    php = buscar_php()
    print(subprocess.run([php, "-v"], capture_output=True, text=True).stdout.splitlines()[0])
    for f in sorted(API.glob("*.php")):
        r = subprocess.run([php, "-l", str(f)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
    print("sintaxis OK en", len(list(API.glob("*.php"))), "archivos\n")

    env = dict(os.environ, PHP_BIN=php)
    fallos = 0
    with tempfile.TemporaryDirectory() as tmp:
        for nombre, script, stub in (("red", "probar-api-red.py", False), ("stub", "probar-api-stub.py", True)):
            carpeta = Path(tmp) / nombre
            preparar(carpeta, stub)
            print(f"=== serie «{nombre}» ===")
            r = subprocess.run([sys.executable, str(AQUI / script), str(carpeta)], env=env)
            fallos += r.returncode
            print()
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
