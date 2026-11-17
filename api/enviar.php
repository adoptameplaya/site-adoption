<?php
/* Recibe los formularios del sitio (solicitud de formulario, cuestionario de adopción,
   cuestionario de hogar temporal) y los envía POR CORREO desde el servidor del propio sitio :
     · a la asociación (con «Responder» dirigido a la persona) ;
     · a la persona, con un correo de confirmación con logo y botones.

   Responde enseguida (JSON). Si algo falla, el navegador usa FormSubmit como respaldo,
   así que aquí se prefiere rechazar con un error claro antes que aceptar algo dudoso.

   Interruptor : 'envio_directo' => 'no' en el archivo de secretos desactiva este envío
   (el sitio vuelve entero a FormSubmit) sin tocar el código. */
declare(strict_types=1);
require __DIR__ . '/_comun.php';
require __DIR__ . '/_correo.php';

const MAX_CUERPO = 70000;

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_salida(405, ['ok' => false, 'error' => 'Método no permitido.']);
}
if (secreto('envio_directo', 'si') === 'no') {
    json_salida(503, ['ok' => false, 'error' => 'Envío directo desactivado.']);
}

/* 1. Solo desde este sitio (Origin o Referer) */
function origen_permitido(): bool
{
    $hosts = ['adoptameplaya.org', 'www.adoptameplaya.org'];
    $propio = parse_url(secreto('site_url'), PHP_URL_HOST);
    if (is_string($propio) && $propio !== '') {
        $hosts[] = strtolower($propio);
        $hosts[] = 'www.' . strtolower($propio);
    }
    if ((string) getenv('ADOPTAME_CORREO_PRUEBA') !== '') {
        array_push($hosts, 'localhost', '127.0.0.1');
    }
    foreach (['HTTP_ORIGIN', 'HTTP_REFERER'] as $k) {
        $v = (string) ($_SERVER[$k] ?? '');
        if ($v !== '') {
            $h = parse_url($v, PHP_URL_HOST);
            return is_string($h) && in_array(strtolower($h), $hosts, true);
        }
    }
    return false;
}
if (!origen_permitido()) {
    json_salida(403, ['ok' => false, 'error' => 'Origen no permitido.']);
}

/* 2. Tamaño y formato */
if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > MAX_CUERPO) {
    json_salida(413, ['ok' => false, 'error' => 'Demasiado texto.']);
}
$crudo = (string) file_get_contents('php://input', false, null, 0, MAX_CUERPO + 1);
if (strlen($crudo) > MAX_CUERPO) {
    json_salida(413, ['ok' => false, 'error' => 'Demasiado texto.']);
}
$p = json_decode($crudo, true);
if (!is_array($p)) {
    json_salida(400, ['ok' => false, 'error' => 'Petición no válida.']);
}
$texto_de = static fn(string $k): string => is_string($p[$k] ?? null) ? $p[$k] : '';

/* 3. Robots : campo trampa (se responde «ok» para no darles pistas) y tiempo mínimo de relleno */
if ($texto_de('hp') !== '') {
    json_salida(200, ['ok' => true]);
}
$tipo = $texto_de('tipo');
if (!in_array($tipo, ['solicitud', 'adopcion', 'hogar'], true)) {
    json_salida(400, ['ok' => false, 'error' => 'Petición no válida.']);
}
$t0 = $p['t'] ?? null;
$minimo = $tipo === 'solicitud' ? 4 : 25;                      // segundos desde que se abrió la página
if ((string) getenv('ADOPTAME_CORREO_PRUEBA') !== '' && (string) getenv('ADOPTAME_TIEMPO_MIN') !== '') {
    $minimo = (int) getenv('ADOPTAME_TIEMPO_MIN');
}
if (!(is_int($t0) || is_float($t0)) || (time() - (int) ($t0 / 1000)) < $minimo) {
    json_salida(400, ['ok' => false, 'error' => 'Demasiado rápido.']);
}

/* 4. Datos */
$idioma = $texto_de('idioma') === 'en' ? 'en' : 'es';
$especie = $tipo === 'hogar' ? '' : ($texto_de('especie') === 'gato' ? 'gato' : ($texto_de('especie') === 'perro' ? 'perro' : ''));
$d = [
    'tipo'    => $tipo,
    'idioma'  => $idioma,
    'especie' => $especie,
    'nombre'  => una_linea($texto_de('nombre'), 120),
    'apellido' => una_linea($texto_de('apellido'), 120),
    'email'   => una_linea($texto_de('email'), 160),
    'animal'  => una_linea($texto_de('animal'), 80),
    'texto'   => $tipo === 'solicitud' ? '' : texto_libre($texto_de('texto'), 40000),
];
if ($d['animal'] === '—' || $d['animal'] === '-') {
    $d['animal'] = '';
}
if ($d['nombre'] === '' || !correo_valido($d['email'])
    || ($tipo !== 'hogar' && $especie === '')
    || ($tipo !== 'solicitud' && strlen($d['texto']) < 30)) {
    json_salida(400, ['ok' => false, 'error' => 'Faltan datos.']);
}

/* 5. Límites : por dirección IP, por correo y en total (se superan → el navegador usa FormSubmit, con su verificación) */
$ip = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
if (!permitir('ip:' . $ip, 6, 3600) || !permitir('correo:' . strtolower($d['email']), 4, 86400) || !permitir('total', 300, 86400)) {
    json_salida(429, ['ok' => false, 'error' => 'Demasiadas solicitudes.']);
}

/* 6. Doble clic : la misma solicitud en 10 minutos no se envía dos veces */
$huella = 'dup:' . sha1($tipo . '|' . strtolower($d['email']) . '|' . $d['texto'] . '|' . $d['animal'] . '|' . $especie);
if (!permitir($huella, 1, 600)) {
    json_salida(200, ['ok' => true, 'repetida' => true]);
}

/* 7. Respaldo (30 días) y envío */
guardar_respaldo($d + ['fecha_utc' => gmdate('c')]);

$a = correo_asociacion($d);
$para = secreto('correo_asociacion', (string) (sitio_config()['contacto']['email'] ?? ''));
if (!enviar_correo($para, $a['asunto'], $a['texto'], null, $d['email'])) {
    error_log('[enviar] no se pudo enviar el correo a la asociación (' . $tipo . ')');
    olvidar($huella);                                           // que un reintento no se tome por «repetida»
    json_salida(502, ['ok' => false, 'error' => 'No se pudo enviar.']);
}

$s = correo_solicitante($d);
$copia = enviar_correo($d['email'], $s['asunto'], $s['texto'], $s['html'], $para, true);
if (!$copia) {
    error_log('[enviar] no se pudo enviar la confirmación a la persona (' . $tipo . ')');
}
json_salida(200, ['ok' => true, 'confirmacion' => $copia]);
