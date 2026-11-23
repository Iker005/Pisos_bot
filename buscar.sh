#!/bin/bash
# Lanza la búsqueda desde el Mac compartiendo la lista de pisos con GitHub.
#   ./buscar.sh --nuevos                     -> solo pisos nuevos
#   ./buscar.sh --una-vez                    -> todos los que encajan + resumen
#   ./buscar.sh --nuevos --perfil vosotros   -> vuestra búsqueda (no la de amigos)

# Búsqueda que se lanza si no pones --perfil: "amigos" o "vosotros"
PERFIL_POR_DEFECTO="amigos"

cd "$(dirname "$0")" || exit 1

ARGS=("$@")
if [[ " $* " != *" --perfil "* ]]; then
    ARGS+=(--perfil "$PERFIL_POR_DEFECTO")
fi
# "--perfil vosotros" = config.py (sin perfil)
LIMPIOS=(); SALTAR=0
for i in "${!ARGS[@]}"; do
    if [ "$SALTAR" = 1 ]; then SALTAR=0; continue; fi
    if [ "${ARGS[$i]}" = "--perfil" ] && [ "${ARGS[$((i+1))]}" = "vosotros" ]; then SALTAR=1; continue; fi
    LIMPIOS+=("${ARGS[$i]}")
done

echo "⬇️  Bajando de GitHub los pisos ya enviados..."
git pull --rebase --autostash -q || echo "⚠️  No pude bajar los cambios de GitHub (sigo igualmente)"

source venv/bin/activate
python bot.py "${LIMPIOS[@]}"

git add vistos*.txt historico*.json 2>/dev/null
if ! git diff --cached --quiet; then
    git commit -q -m "Pisos vistos (desde el Mac)"
    if git pull --rebase -q && git push -q; then
        echo "✅ Lista de pisos sincronizada con GitHub"
    else
        echo "⚠️  No pude subir la lista a GitHub"
    fi
fi
