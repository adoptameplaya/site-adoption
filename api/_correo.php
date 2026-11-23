<?php
/* Piezas del envío de formularios por correo (lo usa api/enviar.php).
   Este archivo no responde a ninguna petición: el nombre con guion bajo
   lo protege el .htaccess.

   Los correos salen del servidor del propio sitio (SPF y DKIM del dominio ya
   están en el DNS de O2switch). FormSubmit queda solo como respaldo en el navegador. */
declare(strict_types=1);

/* ------------------------------------------------------------ utilidades */

/* Configuración PÚBLICA del sitio (data/config.json), leída del disco : nunca del cliente. */
function sitio_config(): array
{
    static $c = null;
    if ($c === null) {
        $ruta = dirname(__DIR__) . '/data/config.json';
        $leido = is_file($ruta) ? json_decode((string) file_get_contents($ruta), true) : null;
        $c = is_array($leido) ? $leido : [];
    }
    return $c;
}

function esc(string $s): string
{
    return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/* Corta a $max BYTES sin partir un carácter UTF-8. */
function cortar(string $s, int $max): string
{
    if (strlen($s) <= $max) {
        return $s;
    }
    $s = substr($s, 0, $max);
    while ($s !== '' && preg_match('//u', $s) !== 1) {
        $s = substr($s, 0, -1);
    }
    return $s;
}

/* Una sola línea, sin caracteres de control (cierra la puerta a la inyección de cabeceras). */
function una_linea(string $s, int $max): string
{
    $s = preg_replace('/[\x00-\x1F\x7F]+/', ' ', $s) ?? '';
    return trim(cortar(trim($s), $max));
}

/* Texto libre : conserva saltos de línea y tabuladores, quita el resto de caracteres de control. */
function texto_libre(string $s, int $max): string
{
    $s = str_replace(["\r\n", "\r"], "\n", $s);
    $limpio = preg_replace('/[^\P{C}\n\t]/u', '', $s);
    return trim(cortar($limpio ?? '', $max));
}

/* Sin filter_var() : no todas las compilaciones de PHP traen esa extensión. */
function correo_valido(string $e): bool
{
    return $e !== '' && strlen($e) <= 160
        && preg_match('/^[A-Za-z0-9.!#$%&\'*+\/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/D', $e) === 1;
}

/* ------------------------------------------------------------ carpeta de datos (respaldo y límites) */

/* Fuera de la carpeta web : p. ej. /home/cuenta/respaldo-solicitudes. En pruebas, la fija ADOPTAME_RESPALDO. */
function dir_datos(): string
{
    static $d = null;
    if ($d !== null) {
        return $d;
    }
    $fijo = (string) getenv('ADOPTAME_RESPALDO');
    $raiz = (string) ($_SERVER['DOCUMENT_ROOT'] ?? '');
    $candidatos = $fijo !== '' ? [$fijo] : [];
    if ($raiz !== '') {
        $candidatos[] = dirname(rtrim($raiz, '/')) . '/respaldo-solicitudes';
    }
    $candidatos[] = sys_get_temp_dir() . '/adoptame-solicitudes';
    foreach ($candidatos as $ruta) {
        if ((is_dir($ruta) || @mkdir($ruta, 0700, true)) && is_writable($ruta)) {
            return $d = $ruta;
        }
    }
    return $d = '';
}

/* Cuenta una petición en la «ventana» de $segundos ; false si ya se superó $max. */
function permitir(string $clave, int $max, int $segundos): bool
{
    $dir = dir_datos();
    if ($dir === '') {
        return true;                                   // sin dónde contar : no se bloquea a nadie por error
    }
    @mkdir($dir . '/limites', 0700, true);
    $archivo = $dir . '/limites/' . sha1($clave) . '.json';
    $f = @fopen($archivo, 'c+');
    if (!$f) {
        return true;
    }
    flock($f, LOCK_EX);
    $ahora = time();
    $marcas = json_decode((string) stream_get_contents($f), true);
    $marcas = array_values(array_filter(is_array($marcas) ? $marcas : [], static fn($t) => is_int($t) && $t > $ahora - $segundos));
    $ok = count($marcas) < $max;
    if ($ok) {
        $marcas[] = $ahora;
    }
    ftruncate($f, 0);
    rewind($f);
    fwrite($f, json_encode($marcas));
    flock($f, LOCK_UN);
    fclose($f);
    return $ok;
}

/* Olvida el contador de una clave (p. ej. si un envío falló : que se pueda reintentar). */
function olvidar(string $clave): void
{
    $dir = dir_datos();
    if ($dir !== '') {
        @unlink($dir . '/limites/' . sha1($clave) . '.json');
    }
}

/* Copia de respaldo de cada solicitud (30 días) : si el correo se pierde por el camino, no se pierde la solicitud. */
function guardar_respaldo(array $datos): bool
{
    $dir = dir_datos();
    if ($dir === '') {
        return false;
    }
    foreach (glob($dir . '/*.json') ?: [] as $viejo) {                       // limpieza : más de 30 días
        if (@filemtime($viejo) < time() - 30 * 86400) {
            @unlink($viejo);
        }
    }
    $nombre = $dir . '/' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(4)) . '.json';
    $ok = @file_put_contents($nombre, json_encode($datos, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT)) !== false;
    if ($ok) {
        @chmod($nombre, 0600);
    }
    return $ok;
}

/* ------------------------------------------------------------ envío (MIME) */

function asunto_mime(string $s): string
{
    return '=?UTF-8?B?' . base64_encode(cortar(una_linea($s, 200), 140)) . '?=';
}

/* Envía un correo UTF-8 (texto y, si se da, HTML). En pruebas (ADOPTAME_CORREO_PRUEBA=carpeta) lo escribe en un archivo. */
function enviar_correo(string $para, string $asunto, string $texto, ?string $html = null, ?string $responder = null, bool $automatico = false): bool
{
    if (!correo_valido($para)) {
        return false;
    }
    $desde = secreto('correo_desde', 'formularios@adoptameplaya.org');
    $nombre = (string) (sitio_config()['refugio']['nombre'] ?? 'Adopta Me Playa');
    $limite = 'adopta_' . bin2hex(random_bytes(8));
    $b64 = static fn(string $s): string => chunk_split(base64_encode(str_replace("\n", "\r\n", str_replace("\r\n", "\n", $s))), 76, "\r\n");

    $cab = [
        'From: =?UTF-8?B?' . base64_encode($nombre) . '?= <' . $desde . '>',
        'Date: ' . date('r'),
        'Message-ID: <' . bin2hex(random_bytes(12)) . '@adoptameplaya.org>',
        'MIME-Version: 1.0',
    ];
    if ($responder !== null && correo_valido($responder)) {
        $cab[] = 'Reply-To: ' . $responder;
    }
    if ($automatico) {
        $cab[] = 'Auto-Submitted: auto-generated';
    }
    if ($html !== null) {
        $cab[] = 'Content-Type: multipart/alternative; boundary="' . $limite . '"';
        $cuerpo = "--$limite\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . $b64($texto)
                . "--$limite\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . $b64($html)
                . "--$limite--\r\n";
    } else {
        $cab[] = 'Content-Type: text/plain; charset=UTF-8';
        $cab[] = 'Content-Transfer-Encoding: base64';
        $cuerpo = $b64($texto);
    }

    $prueba = (string) getenv('ADOPTAME_CORREO_PRUEBA');
    if ($prueba !== '') {                                                    // pruebas : nada sale de la máquina
        @mkdir($prueba, 0700, true);
        $n = count(glob($prueba . '/*.eml') ?: []) + 1;
        $nombreArchivo = sprintf('%s/%03d-%s.eml', $prueba, $n, preg_replace('/[^a-z0-9@._-]/i', '_', $para));
        return file_put_contents($nombreArchivo, 'To: ' . $para . "\r\nSubject: " . asunto_mime($asunto) . "\r\n" . implode("\r\n", $cab) . "\r\n\r\n" . $cuerpo) !== false;
    }
    return mail($para, asunto_mime($asunto), $cuerpo, implode("\r\n", $cab), '-f' . $desde);
}

/* ------------------------------------------------------------ plantillas */

const COLOR_CREMA = '#FFF7EA';
const COLOR_TINTA = '#241B12';
const COLOR_NARANJA = '#F5A63C';
const FUENTE = 'font-family:Arial,Helvetica,sans-serif;';

function html_boton(string $url, string $texto, bool $principal): string
{
    $fondo = $principal ? COLOR_NARANJA : '#FFFFFF';
    return '<a href="' . esc($url) . '" target="_blank" style="display:inline-block;' . FUENTE . 'font-size:16px;font-weight:700;line-height:20px;'
         . 'color:' . COLOR_TINTA . ';background:' . $fondo . ';text-decoration:none;padding:14px 26px;border:2px solid ' . COLOR_TINTA . ';border-radius:999px;">'
         . esc($texto) . '</a>';
}

/* $c : titulo, parrafos[], botones[[url, texto, principal]], notas[] (HTML ya escapado), copia (texto), firma[] */
function correo_html(string $logo, array $c): string
{
    $fila = static fn(string $estilo, string $contenido): string => '<tr><td align="center" style="' . $estilo . '">' . $contenido . '</td></tr>';
    $tinta = COLOR_TINTA;
    $h = '<!doctype html><html lang="' . esc($c['idioma']) . '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
       . '<body style="margin:0;padding:0;background:' . COLOR_CREMA . ';">'
       . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="' . COLOR_CREMA . '" style="background:' . COLOR_CREMA . ';"><tr><td align="center" style="padding:24px 12px;">'
       . '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#FFFFFF" style="max-width:560px;background:#FFFFFF;border:2px solid ' . $tinta . ';border-radius:22px;">';
    $h .= $fila('padding:34px 28px 6px;', '<img src="' . esc($logo) . '" width="112" height="112" alt="Adopta Me Playa" style="display:block;margin:0 auto;border:0;width:112px;height:112px;">');
    $h .= $fila('padding:14px 28px 4px;' . FUENTE . 'font-size:25px;line-height:31px;font-weight:700;color:' . $tinta . ';', esc($c['titulo']));
    foreach ($c['parrafos'] as $p) {
        $h .= $fila('padding:10px 30px 8px;' . FUENTE . 'font-size:16px;line-height:25px;color:' . $tinta . ';', nl2br(esc($p)));
    }
    foreach ($c['botones'] as $b) {
        $h .= $fila('padding:10px 28px 4px;', html_boton($b[0], $b[1], (bool) $b[2]));
    }
    foreach ($c['notas'] as $n) {
        $h .= $fila('padding:14px 30px 4px;' . FUENTE . 'font-size:15px;line-height:24px;color:' . $tinta . ';', $n);
    }
    if (($c['copia'] ?? '') !== '') {
        $h .= $fila('padding:20px 24px 4px;' . FUENTE . 'font-size:13px;line-height:20px;color:' . $tinta . ';text-align:left;',
            '<div style="font-weight:700;margin-bottom:6px;text-align:center;">' . esc($c['copia_titulo']) . '</div>'
          . '<div style="background:' . COLOR_CREMA . ';border-radius:12px;padding:12px 14px;white-space:pre-wrap;word-break:break-word;">' . esc($c['copia']) . '</div>');
    }
    $h .= $fila('padding:18px 30px 34px;' . FUENTE . 'font-size:15px;line-height:24px;color:' . $tinta . ';', implode('<br>', array_map(static fn($l) => esc($l), $c['firma'])));
    return $h . '</table></td></tr></table></body></html>';
}

function correo_texto(array $c): string
{
    $t = [$c['titulo'], ''];
    foreach ($c['parrafos'] as $p) {
        $t[] = $p;
        $t[] = '';
    }
    foreach ($c['botones'] as $b) {
        $t[] = '→ ' . $b[1] . ':';
        $t[] = $b[0];
        $t[] = '';
    }
    foreach ($c['notas_texto'] as $n) {
        $t[] = $n;
        $t[] = '';
    }
    if (($c['copia'] ?? '') !== '') {
        $t[] = '== ' . $c['copia_titulo'] . ' ==';
        $t[] = $c['copia'];
        $t[] = '';
    }
    return implode("\n", array_merge($t, $c['firma']));
}

/* Correo que recibe la PERSONA que llenó el formulario. $d : tipo, idioma, nombre, especie, animal, texto. */
function correo_solicitante(array $d): array
{
    $en = $d['idioma'] === 'en';
    $base = rtrim(secreto('site_url', 'https://adoptameplaya.org'), '/');      // fijo : nunca la cabecera Host, que viene del cliente
    $cfg = sitio_config();
    $refugio = (string) ($cfg['refugio']['nombre'] ?? 'Adopta Me Playa');
    $ciudad = (string) ($cfg['refugio']['ciudad'] ?? 'Playa del Carmen');
    $wa = 'https://wa.me/' . preg_replace('/\D/', '', (string) ($cfg['contacto']['whatsapp'] ?? ''));
    $nombre = $d['nombre'];
    $logo = $base . '/img/ui/favicon-192.png';
    $firma = $en ? ['Warm regards,', $refugio . ' · ' . $ciudad] : ['Un abrazo,', $refugio . ' · ' . $ciudad];
    $ignora = $en ? 'If you did not fill in this form, you can ignore this message.' : 'Si no fuiste tú quien llenó este formulario, ignora este mensaje.';
    $botones = [];
    $notas = [];
    $notasTxt = [];
    $copia = '';

    if ($d['tipo'] === 'solicitud') {
        $esp = $d['especie'];
        $url = $base . '/cuestionario.html?especie=' . rawurlencode($esp) . '&lang=' . $d['idioma'] . ($d['animal'] !== '' ? '&animal=' . rawurlencode($d['animal']) : '');
        $ruta = (string) ($cfg['solicitud']['formularios'][$esp][$d['idioma']] ?? '');
        $botones[] = [$url, $en ? 'Fill in the form online' : 'Rellenar el formulario en línea', true];
        if ($ruta !== '') {
            $botones[] = [$base . '/' . ltrim($ruta, '/'), $en ? 'Download the form as a PDF' : 'Descargar el formulario en PDF', false];
        }
        $asunto = $en ? 'Your adoption form · Adopta Me Playa' : 'Tu formulario de adopción · Adopta Me Playa';
        $titulo = $en ? 'Thank you for your interest in adopting!' : '¡Gracias por tu interés en adoptar!';
        $parrafos = [$en
            ? "Hi $nombre, we are so glad you want to give one of our furry friends a home. Here is the adoption questionnaire:"
            : "Hola $nombre, nos alegra mucho que quieras darle un hogar a uno de nuestros peludos. Aquí tienes el cuestionario de adopción:"];
        $notas[] = $en
            ? 'The easiest way is online, from your phone or your computer. If you prefer the PDF, fill it in and send it to us on <a href="' . esc($wa) . '" style="color:' . COLOR_TINTA . ';font-weight:700;">WhatsApp</a>: it is the fastest way.'
            : 'Lo más cómodo es en línea, desde el celular o la computadora. Si prefieres el PDF, llénalo y mándanoslo por <a href="' . esc($wa) . '" style="color:' . COLOR_TINTA . ';font-weight:700;">WhatsApp</a>: es la vía más rápida.';
        $notasTxt[] = $en ? "If you prefer the PDF, fill it in and send it to us on WhatsApp: $wa" : "Si prefieres el PDF, llénalo y mándanoslo por WhatsApp: $wa";
        $notas[] = $en ? 'We will review it and get back to you as soon as we can.' : 'Lo revisamos y te contestamos lo antes posible.';
        $notasTxt[] = $en ? 'We will review it and get back to you as soon as we can.' : 'Lo revisamos y te contestamos lo antes posible.';
    } else {
        $esHogar = $d['tipo'] === 'hogar';
        $botones[] = [$wa, $en ? 'Message us on WhatsApp' : 'Escribirnos por WhatsApp', false];
        $copia = $d['texto'];
        if ($esHogar) {
            $asunto = $en ? 'We received your foster home questionnaire' : 'Recibimos tu cuestionario de hogar temporal';
            $titulo = $en ? 'Thank you for wanting to foster!' : '¡Gracias por querer ser hogar temporal!';
            $parrafos = [$en
                ? "Hi $nombre, we have received your foster home questionnaire. Thank you for wanting to open your home to a rescued animal! We will read it carefully and get back to you as soon as we can."
                : "Hola $nombre, recibimos tu cuestionario para ser hogar temporal. ¡Gracias por querer abrir las puertas de tu casa a un animal rescatado! Lo vamos a leer con calma y te contestamos lo antes posible."];
        } else {
            $asunto = $en ? 'We received your adoption questionnaire' : 'Recibimos tu cuestionario de adopción';
            $titulo = $en ? 'Thank you for your questionnaire!' : '¡Gracias por tu cuestionario!';
            $parrafos = [$en
                ? "Hi $nombre, we have received your adoption questionnaire" . ($d['animal'] !== '' ? " for {$d['animal']}" : '') . '. We will read it carefully and get back to you as soon as we can.'
                : "Hola $nombre, recibimos tu cuestionario de adopción" . ($d['animal'] !== '' ? " para {$d['animal']}" : '') . '. Lo vamos a leer con calma y te contestamos lo antes posible.'];
        }
                                                              // (el botón ya trae el enlace de WhatsApp y invita a escribir : no se repite la nota)
    }
    $notas[] = '<span style="font-size:13px;opacity:.75;">' . esc($ignora) . '</span>';
    $notasTxt[] = $ignora;

    $c = [
        'idioma' => $d['idioma'], 'titulo' => $titulo, 'parrafos' => $parrafos, 'botones' => $botones,
        'notas' => $notas, 'notas_texto' => $notasTxt, 'copia' => $copia,
        'copia_titulo' => $en ? 'Copy of your answers' : 'Copia de tus respuestas', 'firma' => $firma,
    ];
    return ['asunto' => $asunto, 'html' => correo_html($logo, $c), 'texto' => correo_texto($c)];
}

/* Correo que recibe la ASOCIACIÓN (texto plano, en español). Se responde directamente a la persona. */
function correo_asociacion(array $d): array
{
    $tipos = ['adopcion' => 'Cuestionario de adopción', 'hogar' => 'Cuestionario de hogar temporal', 'solicitud' => 'Solicitud de formulario de adopción'];
    $completo = trim($d['nombre'] . ' ' . ($d['apellido'] ?? ''));
    $asunto = $tipos[$d['tipo']] . ' — ' . $completo . (($d['tipo'] === 'adopcion' && $d['animal'] !== '') ? ' · ' . $d['animal'] : '');
    $lineas = [
        'Nueva solicitud recibida desde adoptameplaya.org',
        'Tipo: ' . $tipos[$d['tipo']],
        'Idioma de la persona: ' . strtoupper($d['idioma']),
        'Fecha: ' . gmdate('Y-m-d H:i') . ' UTC',
        'Nombre: ' . $completo,
        'Correo: ' . $d['email'] . '   (responde a este mensaje para escribirle)',
    ];
    if ($d['tipo'] !== 'hogar') {
        $lineas[] = 'Especie: ' . ($d['especie'] === 'gato' ? 'gato' : 'perro');
        $lineas[] = 'Animal: ' . ($d['animal'] !== '' ? $d['animal'] : '—');
    }
    if ($d['texto'] !== '') {
        $lineas[] = '';
        $lineas[] = $d['texto'];
    }
    return ['asunto' => $asunto, 'texto' => implode("\n", $lineas)];
}
