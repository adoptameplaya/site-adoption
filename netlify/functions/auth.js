/* Démarrage de l'authentification GitHub pour Decap CMS.
   Decap ouvre cette URL dans une fenêtre : on redirige vers GitHub. */
exports.handler = async (event) => {
  const clientId = process.env.GITHUB_CLIENT_ID;
  if (!clientId) {
    return { statusCode: 500, body: "GITHUB_CLIENT_ID no está configurado en Netlify." };
  }

  const host = event.headers['x-forwarded-host'] || event.headers.host;
  const redirect = `https://${host}/api/callback`;
  // état aléatoire : protège contre les requêtes forgées
  const state = Math.random().toString(36).slice(2) + Date.now().toString(36);

  const url = 'https://github.com/login/oauth/authorize'
    + `?client_id=${encodeURIComponent(clientId)}`
    + `&redirect_uri=${encodeURIComponent(redirect)}`
    + '&scope=repo'
    + `&state=${state}`;

  return {
    statusCode: 302,
    headers: {
      Location: url,
      'Set-Cookie': `decap_state=${state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
      'Cache-Control': 'no-store'
    },
    body: ''
  };
};
