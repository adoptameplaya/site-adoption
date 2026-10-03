<?php
/* PLANTILLA. Copia este archivo en el SERVIDOR (cPanel → Administrador de
   archivos) y rellena los valores. Dos sitios posibles:

     RECOMENDADO  /home/TU-CUENTA/secrets-adoptameplaya.php
                  (en tu carpeta personal, FUERA de la carpeta web del dominio:
                  ninguna dirección de internet puede llegar hasta ahí)
     ALTERNATIVA  api/secrets.php  (dentro de la carpeta web, protegido por
                  api/.htaccess)

   No lo pongas en GitHub: el repositorio es público. El despliegue
   automático nunca lo toca ni lo borra. */
return [
    /* Aplicación OAuth de GitHub (Settings → Developer settings → OAuth Apps).
       Callback URL: https://TU-DOMINIO/api/callback */
    'github_client_id'     => '',
    'github_client_secret' => '',

    /* Repositorio del sitio, tal como lo escribe GitHub: cuenta/repositorio */
    'github_repo'          => 'adoptameplaya/site-adoption',

    /* Dirección pública del sitio, sin barra final. */
    'site_url'             => 'https://adoptameplaya.org',

    /* Clave de la API de DeepL (plan gratuito: termina en :fx).
       Si queda vacía, el panel funciona igual pero no traduce solo. */
    'deepl_key'            => '',
];
