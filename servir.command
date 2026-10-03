#!/bin/zsh
# Doble clic para ver el sitio en local.
cd "$(dirname "$0")"
PUERTO=8123
echo "→ http://localhost:$PUERTO"
( sleep 1; open "http://localhost:$PUERTO" ) &
python3 -m http.server $PUERTO
