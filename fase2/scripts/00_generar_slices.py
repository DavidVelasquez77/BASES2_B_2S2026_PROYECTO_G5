"""
Fase 2 - Generador de recortes (slices) para la carga masiva.

Lee los CSV limpios de OlimpiadasF1/data/processed/ y produce los archivos que
consume cada carga de la Fase 2. No toca la base de datos ni los CSV de origen.

Estructura que genera:

    fase2/data/slices/
        catalogos/      <- carga inicial, identica para las tres bases
        anio/           <- r1=Rio 2016, r2=Tokio 2020, r3=Paris 2024
        deporte/        <- las mismas ediciones, solo Atletismo
        deportista/     <- Usain Bolt en Atenas 2004, Pekin 2008, Londres 2012
        manifiesto.json <- conteos por archivo, para validar la carga

Los archivos se escriben con terminador de linea LF (0x0a) de forma explicita,
porque BULK INSERT los lee con ROWTERMINATOR = '0x0a'. El .gitattributes de
fase2/ impide que git los convierta a CRLF en un checkout de Windows.

Uso:  python fase2/scripts/00_generar_slices.py
"""

import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "OlimpiadasF1" / "data" / "processed"
DESTINO = RAIZ / "fase2" / "data" / "slices"

# Tablas de catalogo: entran completas en la carga inicial.
# El orden es el de insercion, respetando las llaves foraneas.
CATALOGOS = [
    "entidad_geografica",
    "deporte",
    "noc",
    "sede",
    "edicion_olimpica",
    "disciplina",
    "evento",
    "poblacion",
]

# id_edicion tomados de edicion_olimpica.csv (verificados el 2026-09-29).
EDICIONES = {
    "2004": 45,   # Atenas
    "2008": 47,   # Pekin
    "2012": 50,   # Londres
    "2016": 54,   # Rio de Janeiro
    "2020": 58,   # Tokio
    "2024": 61,   # Paris
}

DEPORTE_OBJETIVO = "Athletics"
ATLETA_OBJETIVO = 104492          # Usain Bolt, id unico tras la deduplicacion

# Cada carga se define como (nombre_de_la_ronda, id_edicion, etiqueta legible).
CARGAS = {
    "anio": [
        ("r1", EDICIONES["2016"], "Rio de Janeiro 2016"),
        ("r2", EDICIONES["2020"], "Tokio 2020"),
        ("r3", EDICIONES["2024"], "Paris 2024"),
    ],
    "deporte": [
        ("r1", EDICIONES["2016"], "Atletismo - Rio de Janeiro 2016"),
        ("r2", EDICIONES["2020"], "Atletismo - Tokio 2020"),
        ("r3", EDICIONES["2024"], "Atletismo - Paris 2024"),
    ],
    "deportista": [
        ("r1", EDICIONES["2004"], "Usain Bolt - Atenas 2004"),
        ("r2", EDICIONES["2008"], "Usain Bolt - Pekin 2008"),
        ("r3", EDICIONES["2012"], "Usain Bolt - Londres 2012"),
    ],
}


# --------------------------------------------------------------------------
# Normalizacion de tipos
#
# Los CSV de origen fueron escritos con pandas: cuando una columna entera tiene
# algun nulo, pandas la convierte a flotante y la escribe como "19.0". BULK
# INSERT no puede convertir "19.0" a INT y rechaza la fila con el error 4864.
# Lo mismo pasa con las columnas BIT, que llegan como "True"/"False".
#
# La Fase 1 resolvia esto cargando primero a tablas de staging de texto y
# transformando despues. Aqui se corrige en el origen, al generar el recorte,
# para que la carga de la Fase 2 sea directa a las tablas finales.
# --------------------------------------------------------------------------

COLUMNAS_ENTERAS = {
    "noc": ["id_noc", "id_entidad"],
    "sede": ["id_sede", "id_pais"],
    "edicion_olimpica": ["id_edicion", "anio", "id_sede"],
    "disciplina": ["id_disciplina", "id_deporte"],
    "evento": ["id_evento", "id_disciplina"],
    "poblacion": ["id_entidad", "anio", "poblacion"],
    "entidad_geografica": ["id_entidad"],
    "deporte": ["id_deporte"],
    "atleta": ["id_atleta", "id_pais_nacimiento", "id_pais_nacionalidad",
               "id_pais_fallecimiento"],
    "participacion": ["id_participacion", "id_atleta", "id_edicion", "id_evento",
                      "id_noc", "id_pais_nacionalidad", "posicion"],
}

COLUMNAS_BIT = {"participacion": ["empatado"]}


def _a_entero(valor):
    """'19.0' -> '19'.  '' -> ''.  '19' -> '19'."""
    v = (valor or "").strip()
    if not v:
        return ""
    try:
        return str(int(float(v)))
    except ValueError:
        return v          # se deja igual; la carga lo reportara si es invalido


def _a_bit(valor):
    """'True'/'False' -> '1'/'0'. Vacio se conserva vacio (NULL)."""
    v = (valor or "").strip().lower()
    if v in ("true", "1"):
        return "1"
    if v in ("false", "0"):
        return "0"
    return ""


def normalizar(tabla, filas):
    """Aplica las conversiones de tipo a las filas de una tabla."""
    enteras = COLUMNAS_ENTERAS.get(tabla, [])
    bits = COLUMNAS_BIT.get(tabla, [])
    if not enteras and not bits:
        return filas
    for fila in filas:
        for c in enteras:
            if c in fila:
                fila[c] = _a_entero(fila[c])
        for c in bits:
            if c in fila:
                fila[c] = _a_bit(fila[c])
    return filas


def leer(nombre):
    """Devuelve (lista_de_filas_normalizadas, lista_de_columnas) de un CSV de origen."""
    ruta = ORIGEN / f"{nombre}.csv"
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        return normalizar(nombre, list(lector)), lector.fieldnames


def escribir(ruta, columnas, filas):
    """Escribe un CSV en UTF-8 con terminador LF, que es lo que espera BULK INSERT."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    return len(filas)


def main():
    if not ORIGEN.is_dir():
        sys.exit(f"No se encontro el directorio de origen: {ORIGEN}")

    manifiesto = {"catalogos": {}, "cargas": {}}

    # ---------- Carga inicial: catalogos completos ----------
    print("Catalogos (carga inicial)")
    for tabla in CATALOGOS:
        filas, columnas = leer(tabla)
        n = escribir(DESTINO / "catalogos" / f"{tabla}.csv", columnas, filas)
        manifiesto["catalogos"][tabla] = n
        print(f"   {tabla:22} {n:>7,}")

    # ---------- Cargas incrementales ----------
    participaciones, col_part = leer("participacion")
    atletas, col_atl = leer("atleta")
    atleta_por_id = {r["id_atleta"]: r for r in atletas}

    eventos, _ = leer("evento")
    disciplinas, _ = leer("disciplina")
    deportes, _ = leer("deporte")

    id_deporte = next(r["id_deporte"] for r in deportes if r["nombre"] == DEPORTE_OBJETIVO)
    disc_del_deporte = {r["id_disciplina"] for r in disciplinas if r["id_deporte"] == id_deporte}
    eventos_del_deporte = {r["id_evento"] for r in eventos if r["id_disciplina"] in disc_del_deporte}

    def filtro(tipo, id_edicion):
        """Predicado que define que participaciones entran en cada tipo de carga."""
        if tipo == "anio":
            return lambda p: p["id_edicion"] == str(id_edicion)
        if tipo == "deporte":
            return lambda p: (p["id_edicion"] == str(id_edicion)
                              and p["id_evento"] in eventos_del_deporte)
        if tipo == "deportista":
            return lambda p: (p["id_edicion"] == str(id_edicion)
                              and p["id_atleta"] == str(ATLETA_OBJETIVO))
        raise ValueError(tipo)

    for tipo, rondas in CARGAS.items():
        print(f"\nCarga por {tipo}")
        manifiesto["cargas"][tipo] = []
        # Un atleta ya insertado en una ronda anterior no se repite en la siguiente:
        # la llave primaria lo rechazaria.
        ya_insertados = set()

        for ronda, id_edicion, etiqueta in rondas:
            seleccion = [p for p in participaciones if filtro(tipo, id_edicion)(p)]
            ids_nuevos = {p["id_atleta"] for p in seleccion} - ya_insertados
            nuevos = [atleta_por_id[i] for i in sorted(ids_nuevos, key=int)]
            ya_insertados |= ids_nuevos

            base = DESTINO / tipo
            n_atl = escribir(base / f"{ronda}_atleta.csv", col_atl, nuevos)
            n_par = escribir(base / f"{ronda}_participacion.csv", col_part, seleccion)

            manifiesto["cargas"][tipo].append({
                "ronda": ronda,
                "id_edicion": id_edicion,
                "etiqueta": etiqueta,
                "atletas": n_atl,
                "participaciones": n_par,
            })
            print(f"   {ronda}  {etiqueta:34} atletas={n_atl:>6,}  participaciones={n_par:>7,}")

    ruta_manifiesto = DESTINO / "manifiesto.json"
    ruta_manifiesto.write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nManifiesto escrito en {ruta_manifiesto.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
