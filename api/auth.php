<?php
/* Primer paso del inicio de sesión con GitHub.
   El panel abre esta dirección en una ventana: aquí se redirige a GitHub. */
declare(strict_types=1);
require __DIR__ . '/_comun.php';

$cliente = secreto('github_client_id');
if ($cliente === '') {
    http_response_code(500);
    exit('Falta github_client_id: crea el archivo de secretos (ver api/secrets.example.php).');
}

/* Estado aleatorio: impide que alguien fabrique una respuesta de GitHub. */
$estado = bin2hex(random_bytes(16));
setcookie('oauth_state', $estado, [
    'expires'  => time() + 600,
    'path'     => '/',
    'secure'   => true,
    'httponly' => true,
    'samesite' => 'Lax',
]);

$url = 'https://github.com/login/oauth/authorize?' . http_build_query([
    'client_id'    => $cliente,
    'redirect_uri' => origen() . '/api/callback',
    /* Dar de alta fichas solo necesita escribir en un repositorio público. */
    'scope'        => secreto('github_scope', 'public_repo'),
    'state'        => $estado,
]);

header('Cache-Control: no-store');
header('Location: ' . $url, true, 302);
