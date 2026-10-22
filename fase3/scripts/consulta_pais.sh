#!/usr/bin/env bash
# Inciso d: muestra toda la información histórica de un país (participaciones, resultados,
# medallas, años de participación y si ha sido sede en alguna ocasión con sus respectivos años).
#
# Uso:
#   ./fase3/scripts/consulta_pais.sh "Guatemala"
#   ./fase3/scripts/consulta_pais.sh GUA --anio 2012
#   ./fase3/scripts/consulta_pais.sh France --temporada verano --medalla oro
#   ./fase3/scripts/consulta_pais.sh Argentina --deporte Football
#   ./fase3/scripts/consulta_pais.sh GUA --json
#
# Opciones: --deporte, --anio, --temporada, --medalla, --limite, --json,
#           --uri (mongodb://127.0.0.1:27018 para compose, o 27017 nativo),
#           --db (OlimpiadasF3), --contenedor
# Usa mongosh si está instalado; si no, ejecuta mongosh dentro del contenedor MongoDB de
# fase3/compose.yaml (o del indicado en --contenedor).
set -euo pipefail

pais="" deporte="" anio="" temporada="" medalla="" limite="100" formato="texto"
uri="mongodb://127.0.0.1:27018" base="OlimpiadasF3" contenedor=""

while [ $# -gt 0 ]; do
    case "$1" in
        --deporte) deporte="$2"; shift 2 ;;
        --anio) anio="$2"; shift 2 ;;
        --temporada) temporada="$2"; shift 2 ;;
        --medalla) medalla="$2"; shift 2 ;;
        --limite) limite="$2"; shift 2 ;;
        --json) formato="json"; shift ;;
        --uri) uri="$2"; shift 2 ;;
        --db) base="$2"; shift 2 ;;
        --contenedor) contenedor="$2"; shift 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        -*) echo "Opción no reconocida: $1" >&2; exit 1 ;;
        *) pais="$1"; shift ;;
    esac
done

if [ -z "$pais" ]; then
    echo "Indique el país o código NOC/ISO como primer parámetro, por ejemplo: $0 \"Guatemala\" o $0 GUA" >&2
    exit 1
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
script="$script_dir/mongodb/07_consulta_pais.js"
variables=(
    "OLIMPIADAS_PAIS=$pais"
    "OLIMPIADAS_ANIO=$anio"
    "OLIMPIADAS_TEMPORADA=$temporada"
    "OLIMPIADAS_DEPORTE=$deporte"
    "OLIMPIADAS_MEDALLA=$medalla"
    "OLIMPIADAS_LIMITE=$limite"
    "OLIMPIADAS_FORMATO=$formato"
    "OLIMPIADAS_MONGO_DB=$base"
)

if command -v mongosh >/dev/null 2>&1; then
    env "${variables[@]}" mongosh "$uri" --quiet --file "$script"
elif command -v docker >/dev/null 2>&1; then
    if [ -z "$contenedor" ]; then
        contenedor="$(docker compose -f "$script_dir/../compose.yaml" ps -q mongo 2>/dev/null | head -n 1)"
        if [ -z "$contenedor" ]; then
            echo "MongoDB no está en ejecución. Inícielo con ./fase3/run_import.sh o indique --contenedor." >&2
            exit 1
        fi
    fi
    # En Git Bash (Windows) se pasa la ruta en formato Windows y se evita que MSYS
    # convierta las rutas del contenedor.
    if command -v cygpath >/dev/null 2>&1; then
        script="$(cygpath -w "$script")"
        export MSYS_NO_PATHCONV=1
    fi
    docker cp "$script" "$contenedor:/tmp/07_consulta_pais.js" >/dev/null
    argumentos=()
    for variable in "${variables[@]}"; do argumentos+=(-e "$variable"); done
    docker exec "${argumentos[@]}" "$contenedor" mongosh --quiet --file /tmp/07_consulta_pais.js
else
    echo "No se encontró mongosh ni docker." >&2
    exit 1
fi
