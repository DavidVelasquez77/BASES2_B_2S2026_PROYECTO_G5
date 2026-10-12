#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
compose_file="$script_dir/compose.yaml"
source_dir="$script_dir/../OlimpiadasF1/data/processed"
expected=(atleta.csv deporte.csv disciplina.csv edicion_olimpica.csv entidad_geografica.csv evento.csv noc.csv participacion.csv poblacion.csv sede.csv)

command -v docker >/dev/null 2>&1 || { echo 'Docker no está disponible.' >&2; exit 1; }
[[ -d "$source_dir" ]] || { echo "Falta data/processed: $source_dir" >&2; exit 1; }
shopt -s nullglob
actual=("$source_dir"/*.csv)
[[ ${#actual[@]} -eq ${#expected[@]} ]] || { echo 'Se esperaban exactamente diez CSV procesados.' >&2; exit 1; }
for file in "${expected[@]}"; do
    [[ -f "$source_dir/$file" ]] || { echo "Falta CSV: $file" >&2; exit 1; }
done

compose() { docker compose -f "$compose_file" "$@"; }

echo 'Iniciando MongoDB de Fase 3...'
compose up -d --wait mongo
echo 'Comprobando que OlimpiadasF3 no tenga colecciones existentes...'
compose run --rm mongo-cli --file fase3/scripts/mongodb/00_assert_empty.js

echo 'Creando colecciones...'
compose run --rm mongo-cli --file fase3/scripts/mongodb/01_create_collections.js
echo 'Ejecutando preflight sin escritura...'
compose run --rm mongo-cli --file fase3/scripts/mongodb/02_load_processed.js
echo 'Cargando documentos...'
OLIMPIADAS_MONGO_APPLY=1 compose run --rm mongo-cli --file fase3/scripts/mongodb/02_load_processed.js
echo 'Creando índices...'
compose run --rm mongo-cli --file fase3/scripts/mongodb/03_create_indexes.js
echo 'Validando datos cargados...'
compose run --rm mongo-cli --file fase3/scripts/mongodb/04_validate_import.js
echo 'IMPORTACION_Y_VALIDACION_PASS. La base quedó disponible en localhost:27018.'
