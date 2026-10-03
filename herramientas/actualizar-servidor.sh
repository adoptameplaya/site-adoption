#!/bin/sh
# =========================================================
# Actualiza el sitio del refugio en O2switch.
#
# Se ejecuta EN EL SERVIDOR, desde una tarea cron cada 2 minutos. GitHub
# construye el sitio y lo deja en la rama «despliegue»; este script va a
# buscarla y la copia a la carpeta web del dominio. Ninguna contraseña viaja
# por internet: el repositorio es público y solo se lee.
#
#   cPanel → Tareas cron →  */2 * * * *  /bin/sh /home/CUENTA/actualizar-adoptameplaya.sh
#
# Se puede ejecutar a mano las veces que se quiera: si no hay nada nuevo, no hace nada.
# =========================================================

# ---- ajustes (cámbialos por variables de entorno solo para pruebas) ----
URL_REPO="${URL_REPO:-https://github.com/adoptameplaya/site-adoption.git}"
RAMA="${RAMA:-despliegue}"
REPO="${REPO:-$HOME/adoptameplaya-sitio}"        # copia de trabajo de la rama (fuera de la web)
DEST="${DEST:-$HOME/adoptameplaya.org}"          # carpeta web del dominio (la «Racine du document»)
REGISTRO="${REGISTRO:-$HOME/actualizar-adoptameplaya.log}"
MARCA=".sitio-adoptameplaya"                     # «esta carpeta la gestiona este script»

registrar() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$REGISTRO"; }
fallar()    { registrar "ERROR: $1"; echo "ERROR: $1" >&2; exit 1; }

# ---- seguridad: nunca tocar otro sitio de la misma cuenta ----
[ -n "$HOME" ] && [ -d "$HOME" ] || fallar "HOME no está definido"
[ -d "$DEST" ] || fallar "la carpeta web $DEST no existe"
case "$DEST" in
  */public_html|*/public_html/*|"$HOME"|"$HOME"/) fallar "DEST ($DEST) apunta a public_html o a la carpeta personal: se niega a continuar" ;;
esac
command -v git   >/dev/null 2>&1 || fallar "git no está disponible en este servidor"
command -v rsync >/dev/null 2>&1 || fallar "rsync no está disponible en este servidor"

# ---- primera vez: clonar la rama ----
if [ ! -d "$REPO/.git" ]; then
  git clone -q --branch "$RAMA" --single-branch --depth 1 "$URL_REPO" "$REPO" 2>>"$REGISTRO" \
    || fallar "no se pudo clonar $URL_REPO (rama $RAMA). ¿Ya terminó la primera construcción en GitHub?"
  registrar "clonado $URL_REPO ($RAMA)"
  NUEVO=1
fi

cd "$REPO" || fallar "no se puede entrar en $REPO"

# ---- ¿hay algo nuevo? ----
git fetch -q --depth 1 origin "$RAMA" 2>>"$REGISTRO" || fallar "git fetch falló (¿sin conexión con GitHub?)"
ACTUAL="$(git rev-parse HEAD 2>/dev/null)"
REMOTO="$(git rev-parse FETCH_HEAD 2>/dev/null)"
if [ -z "$NUEVO" ] && [ "$ACTUAL" = "$REMOTO" ] && [ -f "$DEST/$MARCA" ]; then
  exit 0                                          # nada que hacer
fi

git reset -q --hard FETCH_HEAD 2>>"$REGISTRO" || fallar "git reset falló"

# ---- primera publicación: si la carpeta ya contiene OTRO sitio, parar ----
if [ ! -f "$DEST/$MARCA" ]; then
  for f in index.php wp-config.php wp-content wp-admin; do
    [ -e "$DEST/$f" ] && fallar "$DEST ya contiene un sitio ($f) y nunca lo ha desplegado este script. No se ha modificado nada."
  done
  # un index.html que no es el nuestro también se respeta
  if [ -f "$DEST/index.html" ] && ! cmp -s "$DEST/index.html" "$REPO/index.html"; then
    fallar "$DEST ya contiene un index.html ajeno. No se ha modificado nada."
  fi
fi

# ---- copiar. --checksum compara el contenido (no las fechas); --delete retira lo que ya no existe;
#      se protege lo que pone cPanel o el refugio ----
rsync -a --checksum --delete \
  --exclude='.git' \
  --exclude='.well-known' \
  --exclude='cgi-bin' \
  --exclude='error_log' \
  --exclude='api/secrets.php' \
  --exclude="$MARCA" \
  "$REPO"/ "$DEST"/ 2>>"$REGISTRO" || fallar "rsync falló"

date '+%Y-%m-%d %H:%M:%S' > "$DEST/$MARCA"
registrar "publicado $(git rev-parse --short HEAD)"
exit 0
