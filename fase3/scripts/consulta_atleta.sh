#!/usr/bin/env bash
# Inciso c: muestra toda la información de un atleta (participaciones, resultados y medallas).
#
# Uso:
#   ./fase3/scripts/consulta_atleta.sh "Usain Bolt"
#   ./fase3/scripts/consulta_atleta.sh "Michael Phelps" --anio 2008 --medalla oro
#   ./fase3/scripts/consulta_atleta.sh "Luis López" --pais MEX
#   ./fase3/scripts/consulta_atleta.sh --id 104492 --json
#
# Opciones: --deporte, --pais, --anio, --temporada, --medalla, --id, --json,
#           --uri (mongodb://127.0.0.1:27017; la instancia de fase3/compose.yaml usa 27018),
#           --db (OlimpiadasF3), --contenedor
# Usa mongosh si está instalado; si no, ejecuta mongosh dentro del contenedor MongoDB de
# fase3/compose.yaml (o del indicado en --contenedor).
set -euo pipefail

nombre="" deporte="" pais="" anio="" temporada="" medalla="" id="" formato="texto"
uri="mongodb://127.0.0.1:27017" base="OlimpiadasF3" contenedor=""

while [ $# -gt 0 ]; do
    case "$1" in
        --deporte) deporte="$2"; shift 2 ;;
        --pais) pais="$2"; shift 2 ;;
        --anio) anio="$2"; shift 2 ;;
        --temporada) temporada="$2"; shift 2 ;;
        --medalla) medalla="$2"; shift 2 ;;
        --id) id="$2"; shift 2 ;;
        --json) formato="json"; shift ;;
        --uri) uri="$2"; shift 2 ;;
        --db) base="$2"; shift 2 ;;
        --contenedor) contenedor="$2"; shift 2 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        -*) echo "Opción no reconocida: $1" >&2; exit 1 ;;
        *) nombre="$1"; shift ;;
    esac
done

if [ -z "$nombre" ] && [ -z "$id" ]; then
    echo "Indique el nombre del atleta como primer parámetro, por ejemplo: $0 \"Usain Bolt\"" >&2
    exit 1
fi

script_dir="$(cd "$(dirname "$0")" && pwd)"
script="$script_dir/mongodb/06_consulta_atleta.js"
variables=(
    "OLIMPIADAS_ATLETA=$nombre"
    "OLIMPIADAS_ATLETA_ID=$id"
    "OLIMPIADAS_DEPORTE=$deporte"
    "OLIMPIADAS_PAIS=$pais"
    "OLIMPIADAS_ANIO=$anio"
    "OLIMPIADAS_TEMPORADA=$temporada"
    "OLIMPIADAS_MEDALLA=$medalla"
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
    docker cp "$script" "$contenedor:/tmp/06_consulta_atleta.js" >/dev/null
    argumentos=()
    for variable in "${variables[@]}"; do argumentos+=(-e "$variable"); done
    docker exec "${argumentos[@]}" "$contenedor" mongosh --quiet --file /tmp/06_consulta_atleta.js
else
    echo "No se encontró mongosh ni docker." >&2
    exit 1
fi
