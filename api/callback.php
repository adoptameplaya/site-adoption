<?php
/* Segundo paso: GitHub vuelve aquí con un código. Se cambia por un token
   (con el secreto, que nunca sale del servidor) y se entrega a la ventana
   del panel mediante postMessage. */
declare(strict_types=1);
require __DIR__ . '/_comun.php';

header('Cache-Control: no-store');

function error_pagina(int $codigo, string $texto)
{
    http_response_code($codigo);
    header('Content-Type: text/plain; charset=utf-8');
    exit($texto);
}

$codigo   = (string) ($_GET['code'] ?? '');
$estado   = (string) ($_GET['state'] ?? '');
$esperado = (string) ($_COOKIE['oauth_state'] ?? '');

if ($codigo === '') {
    error_pagina(400, 'Falta el código de GitHub.');
}
if ($esperado === '' || !hash_equals($esperado, $estado)) {
    error_pagina(400, 'Estado no válido. Cierra esta ventana y vuelve a intentar el acceso.');
}

[$http, $cuerpo] = http('POST', 'https://github.com/login/oauth/access_token', [
    'Content-Type: application/json',
    'Accept: application/json',
    'User-Agent: adopta-me-playa-panel',
], json_encode([
    'client_id'     => secreto('github_client_id'),
    'client_secret' => secreto('github_client_secret'),
    'code'          => $codigo,
]));

$datos = json_decode($cuerpo, true);
if (!is_array($datos) || empty($datos['access_token'])) {
    $motivo = is_array($datos) ? ($datos['error_description'] ?? $datos['error'] ?? 'error desconocido') : 'respuesta vacía';
    error_pagina(401, 'GitHub no devolvió un token: ' . $motivo);
}

$mensaje = 'authorization:github:success:' . json_encode(
    ['token' => $datos['access_token'], 'provider' => 'github']
);
$flags = JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT;

/* Borra la cookie de estado. */
setcookie('oauth_state', '', ['expires' => 1, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Lax']);
header('Content-Type: text/html; charset=utf-8');
?>
<!doctype html>
<meta charset="utf-8">
<title>…</title>
<body style="font:600 15px system-ui;padding:40px;text-align:center">
<p>Conectando…</p>
<script>
(function () {
  var mensaje = <?= json_encode($mensaje, $flags) ?>;
  function enviar(e) {
    if (window.opener) { window.opener.postMessage(mensaje, e.origin || '*'); }
  }
  window.addEventListener('message', enviar, false);
  if (window.opener) { window.opener.postMessage('authorizing:github', '*'); }
  setTimeout(function () { window.close(); }, 1200);
})();
</script>
</body>
