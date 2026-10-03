/* Retour de GitHub : on échange le code contre un jeton, puis on le renvoie
   à la fenêtre Decap par postMessage. Le secret ne quitte jamais le serveur. */
function pagina(mensaje) {
  return `<!doctype html><meta charset="utf-8"><title>…</title>
<body style="font:600 15px system-ui;padding:40px;text-align:center">
<p>Conectando…</p>
<script>
(function () {
  function enviar(e) {
    window.opener && window.opener.postMessage(${JSON.stringify(mensaje)}, e.origin || '*');
  }
  window.addEventListener('message', enviar, false);
  window.opener && window.opener.postMessage('authorizing:github', '*');
  setTimeout(function () { window.close(); }, 1200);
})();
</script></body>`;
}

exports.handler = async (event) => {
  const { code, state } = event.queryStringParameters || {};
  const cookie = event.headers.cookie || '';
  const esperado = (cookie.match(/decap_state=([^;]+)/) || [])[1];

  if (!code) return { statusCode: 400, body: "Falta el código de GitHub." };
  if (!esperado || state !== esperado) {
    return { statusCode: 400, body: "Estado inválido. Vuelve a intentar el acceso." };
  }

  try {
    const r = await fetch('https://github.com/login/oauth/access_token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        client_id: process.env.GITHUB_CLIENT_ID,
        client_secret: process.env.GITHUB_CLIENT_SECRET,
        code
      })
    });
    const datos = await r.json();
    if (!datos.access_token) {
      return { statusCode: 401, body: `GitHub no devolvió un token: ${datos.error_description || datos.error || 'error desconocido'}` };
    }

    const mensaje = `authorization:github:success:${JSON.stringify({
      token: datos.access_token, provider: 'github'
    })}`;

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Set-Cookie': 'decap_state=; Path=/; Max-Age=0',
        'Cache-Control': 'no-store'
      },
      body: pagina(mensaje)
    };
  } catch (err) {
    return { statusCode: 500, body: `Error al contactar GitHub: ${err.message}` };
  }
};
