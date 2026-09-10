"""Valida tipos físicos propuestos contra data/processed sin modificar los CSV."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
REPORT = ROOT / "docs" / "schema" / "physical_model_validation.csv"
SEASON_REPORT = ROOT / "docs" / "schema" / "edition_season_analysis.csv"


SPECS = {
    "entidad_geografica.csv": {
        "id_entidad": ("INT", None), "nombre": ("NVARCHAR(150)", 150), "codigo_pais": ("CHAR(3)", 3),
    },
    "poblacion.csv": {"id_entidad": ("INT", None), "anio": ("SMALLINT", None), "poblacion": ("BIGINT", None)},
    "noc.csv": {"id_noc": ("INT", None), "codigo_noc": ("CHAR(3)", 3), "nombre_noc": ("NVARCHAR(150)", 150), "id_entidad": ("INT", None), "notas": ("NVARCHAR(500)", 500)},
    "atleta.csv": {
        "id_atleta": ("BIGINT", None), "nombre": ("NVARCHAR(250)", 250), "nombre_completo": ("NVARCHAR(300)", 300),
        "nombre_usado": ("NVARCHAR(300)", 300), "nombre_original": ("NVARCHAR(300)", 300), "otros_nombres": ("NVARCHAR(500)", 500),
        "apodos": ("NVARCHAR(500)", 500), "orden_nombre": ("NVARCHAR(50)", 50), "sexo": ("NVARCHAR(20)", 20),
        "ciudad_nacimiento": ("NVARCHAR(150)", 150), "region_nacimiento": ("NVARCHAR(150)", 150),
        "ciudad_fallecimiento": ("NVARCHAR(150)", 150), "region_fallecimiento": ("NVARCHAR(150)", 150),
        "id_pais_nacimiento": ("INT", None), "id_pais_nacionalidad": ("INT", None),
        "id_pais_fallecimiento": ("INT", None),
        "titulos": ("NVARCHAR(2000)", 2000),
        "fecha_nacimiento": ("DATE", None), "fecha_fallecimiento": ("DATE", None),
        "altura_cm": ("DECIMAL(5,2)", None), "peso_kg": ("DECIMAL(5,2)", None),
        "latitud": ("DECIMAL(9,6)", None), "longitud": ("DECIMAL(9,6)", None),
        "roles": ("NVARCHAR(MAX)", None), "afiliaciones": ("NVARCHAR(MAX)", None),
    },
    "sede.csv": {"id_sede": ("INT", None), "nombre": ("NVARCHAR(150)", 150), "id_pais": ("INT", None)},
    "edicion_olimpica.csv": {"id_edicion": ("INT", None), "anio": ("SMALLINT", None), "temporada": ("NVARCHAR(20)", 20), "id_sede": ("INT", None)},
    "deporte.csv": {"id_deporte": ("INT", None), "nombre": ("NVARCHAR(150)", 150)},
    "disciplina.csv": {"id_disciplina": ("INT", None), "id_deporte": ("INT", None), "nombre": ("NVARCHAR(150)", 150)},
    "evento.csv": {"id_evento": ("BIGINT", None), "id_disciplina": ("INT", None), "nombre": ("NVARCHAR(300)", 300)},
    "participacion.csv": {
        "id_participacion": ("BIGINT", None), "id_atleta": ("BIGINT", None), "id_edicion": ("INT", None),
        "id_evento": ("BIGINT", None), "id_noc": ("INT", None), "id_pais_nacionalidad": ("INT", None),
        "equipo": ("NVARCHAR(250)", 250), "nombre_competencia": ("NVARCHAR(300)", 300),
        "edad": ("DECIMAL(5,2)", None), "altura_cm_registrada": ("DECIMAL(5,2)", None),
        "peso_kg_registrado": ("DECIMAL(5,2)", None), "posicion": ("INT", None), "empatado": ("BIT", None),
        "estado_resultado": ("NVARCHAR(30)", 30), "medalla": ("NVARCHAR(20)", 20),
    },
}


def numeric_check(frame: pd.DataFrame, column: str, sql_type: str) -> tuple[str, str]:
    if sql_type == "NVARCHAR(MAX)":
        return "PASS", "NVARCHAR(MAX) sin límite fijo de caracteres"
    if sql_type == "DATE":
        parsed = pd.to_datetime(frame[column].replace("", pd.NA), errors="coerce")
        invalid = int(((frame[column] != "") & parsed.isna()).sum())
        return ("PASS" if invalid == 0 else "FAIL", "fechas ISO compatibles" if invalid == 0 else f"{invalid} fechas no interpretables")
    values = pd.to_numeric(frame[column], errors="coerce")
    if sql_type == "SMALLINT":
        ok = values.dropna().between(-32768, 32767).all()
    elif sql_type == "INT":
        ok = values.dropna().between(-2147483648, 2147483647).all()
    elif sql_type == "BIGINT":
        ok = values.dropna().between(-9223372036854775808, 9223372036854775807).all()
    elif sql_type == "BIT":
        normalized = frame[column].replace({"": pd.NA, "True": 1, "False": 0})
        parsed = pd.to_numeric(normalized, errors="coerce")
        ok = parsed.dropna().isin([0, 1]).all()
    elif column == "latitud":
        ok = values.dropna().between(-90, 90).all()
    elif column == "longitud":
        ok = values.dropna().between(-180, 180).all()
    elif sql_type.startswith("DECIMAL"):
        ok = values.dropna().notna().all()
        detail = "rango numérico compatible; revisar redondeo si hay más precisión decimal que la declarada"
        return ("PASS" if ok else "FAIL", detail if ok else "valor no numérico")
    else:
        ok = True
    return ("PASS" if ok else "FAIL", "rango compatible" if ok else "rango fuera del tipo SQL")


def decimal_check(frame: pd.DataFrame, column: str, sql_type: str) -> tuple[str, str, dict[str, object]]:
    match = re.fullmatch(r"DECIMAL\((\d+),(\d+)\)", sql_type)
    if not match:
        raise ValueError(f"Tipo DECIMAL no reconocido: {sql_type}")
    precision, scale = int(match.group(1)), int(match.group(2))
    max_integer_digits = 0
    max_decimal_digits = 0
    invalid = 0
    rounding = 0
    for raw in frame[column].astype(str):
        if not raw:
            continue
        try:
            value = Decimal(raw)
        except InvalidOperation:
            invalid += 1
            continue
        digits = value.as_tuple().digits
        exponent = value.as_tuple().exponent
        decimal_digits = max(0, -exponent)
        integer_digits = max(0, len(digits) - decimal_digits)
        max_integer_digits = max(max_integer_digits, integer_digits)
        max_decimal_digits = max(max_decimal_digits, decimal_digits)
        if decimal_digits > scale:
            extra_digits = digits[-(decimal_digits - scale):]
            if any(extra_digits):
                rounding += 1
    integer_capacity = precision - scale
    fits = max_integer_digits <= integer_capacity
    requires_rounding = rounding > 0
    state = "PASS" if invalid == 0 and fits and not requires_rounding else "FAIL"
    detail = (
        f"DECIMAL({precision},{scale}); enteros observados {max_integer_digits}/{integer_capacity}; "
        f"decimales observados {max_decimal_digits}/{scale}; valores con redondeo {rounding}; inválidos {invalid}"
    )
    return state, detail, {
        "precision_sql": precision,
        "scale_sql": scale,
        "max_digitos_enteros_observados": max_integer_digits,
        "max_decimales_observados": max_decimal_digits,
        "requiere_redondeo": "YES" if requires_rounding else "NO",
    }


def edition_season_analysis() -> pd.DataFrame:
    editions = pd.read_csv(PROCESSED / "edicion_olimpica.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    venues = pd.read_csv(PROCESSED / "sede.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    participation = pd.read_csv(PROCESSED / "participacion.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig", usecols=["id_edicion"])
    venue_names = venues.set_index("id_sede")["nombre"].to_dict()
    participation_counts = participation.groupby("id_edicion").size().to_dict()
    observations = {
        "Equestrian": "1956; eventos ecuestres asociados a los Juegos de Melbourne 1956, celebrados en Stockholm por cuarentena; no parece una edición independiente.",
        "Intercalated Games": "1906; edición histórica intercalada de Atenas, no equivalente a una edición ordinaria de la Olympiad.",
        "Summer Youth": "2010, 2014 y 2018; Juegos Olímpicos de la Juventud de verano, sin sede conservada en el CSV final.",
        "Winter Youth": "2012, 2016 y 2020; Juegos Olímpicos de la Juventud de invierno, sin sede conservada en el CSV final.",
    }
    rows = []
    for record in editions.to_dict(orient="records"):
        season = record["temporada"]
        rows.append({
            "tipo_registro": "EDITION", "id_edicion": record["id_edicion"], "anio": record["anio"],
            "temporada": season, "id_sede": record["id_sede"], "sede": venue_names.get(record["id_sede"], ""),
            "cantidad_participaciones": int(participation_counts.get(record["id_edicion"], 0)),
            "cantidad_ediciones": 1, "anios": record["anio"], "sedes": venue_names.get(record["id_sede"], ""),
            "observacion": observations.get(season, "Edición ordinaria de verano o invierno."),
        })
    edition_frame = pd.DataFrame(rows)
    for season, group in edition_frame.groupby("temporada", sort=True):
        rows.append({
            "tipo_registro": "SEASON_SUMMARY", "id_edicion": "", "anio": "", "temporada": season,
            "id_sede": "", "sede": "", "cantidad_participaciones": int(group["cantidad_participaciones"].sum()),
            "cantidad_ediciones": len(group), "anios": "|".join(group["anio"].astype(str)),
            "sedes": "|".join(sorted({str(value) for value in group["sede"] if value})),
            "observacion": observations.get(season, "Resumen de ediciones observadas."),
        })
    return pd.DataFrame(rows, columns=["tipo_registro", "id_edicion", "anio", "temporada", "id_sede", "sede", "cantidad_participaciones", "cantidad_ediciones", "anios", "sedes", "observacion"])


def main() -> int:
    rows: list[dict[str, object]] = []
    for file_name, columns in SPECS.items():
        frame = pd.read_csv(PROCESSED / file_name, dtype=str, keep_default_na=False, encoding="utf-8-sig", low_memory=False)
        for column, (sql_type, max_chars) in columns.items():
            values = frame[column].astype(str)
            nonempty = values[values != ""]
            max_observed = int(nonempty.map(len).max()) if len(nonempty) else 0
            nulls = int((values == "").sum())
            metadata: dict[str, object] = {"precision_sql": "", "scale_sql": "", "max_digitos_enteros_observados": "", "max_decimales_observados": "", "requiere_redondeo": "NO"}
            if max_chars is not None:
                state = "PASS" if max_observed <= max_chars else "FAIL"
                detail = f"máximo observado {max_observed}; capacidad {max_chars} caracteres"
            elif sql_type.startswith("DECIMAL"):
                state, detail, metadata = decimal_check(frame, column, sql_type)
            else:
                state, detail = numeric_check(frame, column, sql_type)
            rows.append({"archivo": file_name, "columna": column, "tipo_sql": sql_type,
                         "filas": len(frame), "nulos_o_vacios": nulls,
                         "maximo_observado": max_observed, "capacidad_caracteres": max_chars or "",
                         **metadata, "estado": state, "detalle": detail})

    frame = pd.DataFrame(rows)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(REPORT, index=False, encoding="utf-8-sig", lineterminator="\n")
    season_frame = edition_season_analysis()
    season_frame.to_csv(SEASON_REPORT, index=False, encoding="utf-8-sig", lineterminator="\n")
    print(f"Columnas validadas: {len(frame)}")
    print(f"PASS/FAIL: {(frame['estado'] == 'PASS').sum()}/{(frame['estado'] == 'FAIL').sum()}")
    print(f"Registros de análisis de temporadas: {len(season_frame)}")
    return 0 if (frame["estado"] == "PASS").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
