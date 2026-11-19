#!/bin/bash
# Lanza la búsqueda desde el Mac compartiendo la lista de pisos con GitHub.
#   ./buscar.sh --una-vez                  -> búsqueda semanal (todo + resumen)
#   ./buscar.sh --nuevos                   -> solo pisos nuevos
#   ./buscar.sh --una-vez --perfil amigos  -> la de los amigos
cd "$(dirname "$0")" || exit 1

echo "⬇️  Bajando de GitHub los pisos ya enviados..."
git pull --rebase --autostash -q || echo "⚠️  No pude bajar los cambios de GitHub (sigo igualmente)"

source venv/bin/activate
python bot.py "$@"

git add vistos*.txt historico*.json 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "Pisos vistos (desde el Mac)"
    if git pull --rebase -q && git push -q; then
        echo "✅ Lista de pisos sincronizada con GitHub"
    else
        echo "⚠️  No pude subir la lista a GitHub"
    fi
fi
