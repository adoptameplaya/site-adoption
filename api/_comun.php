<?php
/* Utilidades compartidas por los scripts de api/. Este archivo no responde
   a ninguna petición: el nombre con guion bajo lo protege el .htaccess. */
declare(strict_types=1);

/* Nunca mostrar errores PHP al visitante: corromperían la respuesta JSON
   y revelarían rutas del servidor. Quedan en el registro de errores. */
ini_set('display_errors', '0');

/* Los secretos NO están en el repositorio (es público). Se buscan, por orden:
     1. un nivel POR ENCIMA de la carpeta web del dominio, p. ej.
        /home/cuenta/secrets-adoptameplaya.php  → recomendado: no se puede servir
        nunca por la web, ni aunque falle la configuración del servidor;
     2. api/secrets.php, dentro de la carpeta web (protegido por api/.htaccess).
   Ver api/secrets.example.php. */
function secreto(string $clave, string $porDefecto = ''): string
{
    static $todos = null;
    if ($todos === null) {
        $todos = [];
        $candidatos = [];
        $raiz = (string) ($_SERVER['DOCUMENT_ROOT'] ?? '');
        if ($raiz !== '') {
            $candidatos[] = dirname(rtrim($raiz, '/')) . '/secrets-adoptameplaya.php';
        }
        $candidatos[] = __DIR__ . '/secrets.php';
        foreach ($candidatos as $ruta) {
            if (is_file($ruta)) {
                $leidos = require $ruta;
                if (is_array($leidos)) {
                    $todos = $leidos;
                    break;
                }
            }
        }
    }
    $v = $todos[$clave] ?? $porDefecto;
    return is_string($v) ? trim($v) : $porDefecto;
}

/* Origen público del sitio, p. ej. https://adoptameplaya.org
   Se prefiere el valor configurado a la cabecera Host, que viene del cliente. */
function origen(): string
{
    $fijo = rtrim(secreto('site_url'), '/');
    if ($fijo !== '') {
        return $fijo;
    }
    $host = $_SERVER['HTTP_HOST'] ?? '';
    if (!preg_match('/^[a-z0-9.-]+(:\d+)?$/i', $host)) {
        http_response_code(400);
        exit('Host no válido.');
    }
    return 'https://' . $host;
}

function json_salida(int $codigo, array $datos)
{
    http_response_code($codigo);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($datos, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

/* Petición HTTPS sencilla con cURL. Devuelve [código, cuerpo]. */
function http(string $metodo, string $url, array $cabeceras = [], ?string $cuerpo = null, int $limite = 15): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST  => $metodo,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => $cabeceras,
        CURLOPT_TIMEOUT        => $limite,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    if ($cuerpo !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $cuerpo);
    }
    $respuesta = curl_exec($ch);
    $codigo = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    return [$codigo, $respuesta === false ? '' : (string) $respuesta];
}
