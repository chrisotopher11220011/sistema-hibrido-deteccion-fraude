#!/bin/sh
# Arranque de n8n para el prototipo (docs/decisions/0004).
#
# Verificado en la documentacion de n8n el 2026-11-16, con la version 2.47.7:
#   - `import:workflow` deja sin publicar todo lo que importa y sobrescribe el
#     flujo que tenga el mismo id. Por eso cada flujo lleva un id fijo.
#   - `publish:workflow --id=<ID>` publica un flujo; no existe `--all`.
#   - Con n8n detenido, la publicacion se aplica al arrancar.
set -eu

FLUJOS=/arranque/flujos

echo "[arranque] Importando los flujos de ${FLUJOS}..."
n8n import:workflow --separate --input="${FLUJOS}"

for archivo in "${FLUJOS}"/*.json; do
    id=$(node -e 'process.stdout.write(String(require(process.argv[1]).id))' "${archivo}")
    echo "[arranque] Publicando el flujo ${id} ($(basename "${archivo}"))..."
    n8n publish:workflow --id="${id}"
done

echo "[arranque] Flujos listos. Arrancando n8n..."
exec n8n start
