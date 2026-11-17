<?php
/* Traducción ES → EN para el panel del refugio, con la API de DeepL.
   La clave vive en api/secrets.php; el navegador nunca la ve.

   Solo responde a quien tenga permiso de escritura en el repositorio:
   se comprueba el token de GitHub que manda el panel. Así nadie de fuera
   puede gastar la cuota de traducción. */
declare(strict_types=1);
require __DIR__ . '/_comun.php';

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    json_salida(405, ['ok' => false, 'error' => 'Método no permitido.']);
}

/* 1. ¿Quién llama? */
$token = trim((string) ($_SERVER['HTTP_X_TOKEN_GITHUB'] ?? ''));
if ($token === '' || strlen($token) > 255) {
    json_salida(401, ['ok' => false, 'error' => 'Sesión no válida.']);
}
$repo = secreto('github_repo', 'adoptameplaya/site-adoption');
[$http, $cuerpo] = http('GET', 'https://api.github.com/repos/' . $repo, [
    'Authorization: Bearer ' . $token,
    'Accept: application/vnd.github+json',
    'User-Agent: adopta-me-playa-panel',
]);
$info = json_decode($cuerpo, true);
if ($http !== 200 || !is_array($info) || empty($info['permissions']['push'])) {
    json_salida(403, ['ok' => false, 'error' => 'Esta cuenta no puede modificar el sitio.']);
}

/* 2. ¿Qué piden? */
$pedido = json_decode((string) file_get_contents('php://input'), true);
$textos = is_array($pedido) ? ($pedido['textos'] ?? null) : null;
if (!is_array($textos) || !$textos || count($textos) > 20) {
    json_salida(400, ['ok' => false, 'error' => 'Petición no válida.']);
}
$total = 0;
foreach ($textos as $t) {
    if (!is_string($t) || $t === '') {
        json_salida(400, ['ok' => false, 'error' => 'Petición no válida.']);
    }
    $total += strlen($t);
}
if ($total > 12000) {
    json_salida(413, ['ok' => false, 'error' => 'Demasiado texto de una vez.']);
}

/* 3. DeepL. Las claves del plan gratuito terminan en «:fx» y usan otro servidor. */
$clave = secreto('deepl_key');
if ($clave === '') {
    json_salida(503, ['ok' => false, 'error' => 'La traducción automática aún no está configurada.']);
}
$servidor = substr($clave, -3) === ':fx' ? 'https://api-free.deepl.com' : 'https://api.deepl.com';

[$http, $cuerpo] = http('POST', $servidor . '/v2/translate', [
    'Authorization: DeepL-Auth-Key ' . $clave,
    'Content-Type: application/json',
    'User-Agent: adopta-me-playa-panel',
], json_encode([
    'text'        => array_values($textos),
    'source_lang' => 'ES',
    'target_lang' => 'EN-US',
], JSON_UNESCAPED_UNICODE), 25);

$r = json_decode($cuerpo, true);
if ($http === 456) {
    json_salida(429, ['ok' => false, 'error' => 'Se agotó la cuota mensual de traducción.']);
}
if ($http !== 200 || !is_array($r) || !isset($r['translations']) || count($r['translations']) !== count($textos)) {
    json_salida(502, ['ok' => false, 'error' => 'DeepL respondió con un error (' . $http . ').']);
}

json_salida(200, [
    'ok'     => true,
    'textos' => array_map(static fn($t) => (string) ($t['text'] ?? ''), $r['translations']),
]);
