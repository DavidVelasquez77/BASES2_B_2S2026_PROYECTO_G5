"""Perfilado diagnóstico de los CSV originales.

Este script no limpia, transforma, homologa, deduplica ni sobrescribe archivos
de data/raw. Todas las operaciones se realizan sobre copias en memoria y los
resultados se escriben únicamente en docs/profiling/.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
DOCS_DIR = ROOT / "docs"
OUTPUT_DIR = DOCS_DIR / "profiling"
MANIFEST_FILE = DOCS_DIR / "source_manifest.csv"

EXPECTED_FILE_COUNT = 10
SAMPLE_LIMIT = 5
RARE_SAMPLE_LIMIT = 5
SPECIAL_SAMPLE_LIMIT = 10

KNOWN_NUMERIC_COLUMNS = {
    "age",
    "height",
    "weight",
    "height_cm",
    "weight_kg",
    "year",
    "id",
    "index",
    "athlete_id",
    "player_id",
}

POTENTIAL_OUTLIER_COLUMNS = {
    "age",
    "height",
    "weight",
    "height_cm",
    "weight_kg",
}

DATE_COLUMNS = {
    "year",
    "born",
    "died",
    "born_date",
    "died_date",
}

POSITION_COLUMNS = {"pos", "place", "position"}

SPECIAL_TOKENS = {
    "na",
    "n/a",
    "nan",
    "null",
    "none",
    "no medal",
    "dns",
    "dnf",
    "dsq",
    "dq",
}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def display_value(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def detect_encoding(path: Path) -> str:
    sample = path.read_bytes()[:2 * 1024 * 1024]
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    return "latin-1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_metadata(path: Path) -> dict[str, str]:
    relative = path.relative_to(RAW_DIR).as_posix()
    parts = relative.split("/")
    return {
        "fuente": parts[0] if parts else "",
        "archivo_relativo": (Path("data") / "raw" / Path(*parts)).as_posix(),
        "nombre_archivo": path.name,
    }


def load_manifest_hashes() -> dict[str, str]:
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"No existe el manifiesto: {MANIFEST_FILE}")

    manifest = pd.read_csv(MANIFEST_FILE, dtype=str, keep_default_na=False)
    required = {"archivo_relativo", "sha256"}
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError(f"Faltan columnas en el manifiesto: {sorted(missing)}")

    return {
        str(row["archivo_relativo"]): str(row["sha256"])
        for _, row in manifest.iterrows()
    }


def current_raw_hashes(paths: list[Path]) -> dict[str, str]:
    return {
        source_metadata(path)["archivo_relativo"]: sha256(path)
        for path in paths
    }


def validate_manifest(paths: list[Path]) -> pd.DataFrame:
    manifest_hashes = load_manifest_hashes()
    current_hashes = current_raw_hashes(paths)
    rows: list[dict[str, str]] = []

    manifest_paths = set(manifest_hashes)
    current_paths = set(current_hashes)
    all_paths = sorted(manifest_paths | current_paths)

    for relative in all_paths:
        expected = manifest_hashes.get(relative, "")
        current = current_hashes.get(relative, "")
        if not expected:
            status = "NOT_IN_MANIFEST"
        elif not current:
            status = "MISSING_FROM_RAW"
        elif expected == current:
            status = "MATCH"
        else:
            status = "MISMATCH"
        rows.append(
            {
                "archivo_relativo": relative,
                "sha256_manifest": expected,
                "sha256_actual": current,
                "estado": status,
            }
        )

    result = pd.DataFrame(rows)
    invalid = result[result["estado"] != "MATCH"]
    if not invalid.empty:
        details = invalid.to_dict(orient="records")
        raise RuntimeError(
            "Validación SHA-256 fallida. No se puede continuar: "
            + json.dumps(details, ensure_ascii=False)
        )

    return result


def read_csv_pair(path: Path, encoding: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    inferred = pd.read_csv(
        path,
        encoding=encoding,
        low_memory=False,
    )
    raw_text = pd.read_csv(
        path,
        encoding=encoding,
        dtype=object,
        keep_default_na=False,
        na_filter=False,
        low_memory=False,
    )
    return inferred, raw_text


def series_as_text(series: pd.Series) -> pd.Series:
    return series.map(lambda value: "" if pd.isna(value) else str(value))


def counter_samples(counter: Counter[str]) -> tuple[list[str], list[str]]:
    frequent = [
        {"valor": display_value(value), "frecuencia": count}
        for value, count in counter.most_common(SAMPLE_LIMIT)
    ]
    rare_values = sorted(counter.items(), key=lambda item: (item[1], item[0]))[
        :RARE_SAMPLE_LIMIT
    ]
    rare = [
        {"valor": display_value(value), "frecuencia": count}
        for value, count in rare_values
    ]
    return frequent, rare


def add_special(
    special_rows: list[dict[str, Any]],
    metadata: dict[str, str],
    column: str,
    detection_type: str,
    detected_value: str,
    frequency: int,
    examples: list[str] | None = None,
) -> None:
    special_rows.append(
        {
            **metadata,
            "columna": column,
            "tipo_deteccion": detection_type,
            "valor_especial_detectado": detected_value,
            "frecuencia": frequency,
            "ejemplos": json_value(examples or [detected_value]),
        }
    )


def profile_column(
    inferred: pd.DataFrame,
    raw_text: pd.DataFrame,
    metadata: dict[str, str],
    column: str,
    special_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    inferred_series = inferred[column]
    raw_series = series_as_text(raw_text[column])
    counts = Counter(raw_series.tolist())
    normalized = normalize_name(column)
    total_rows = len(inferred)
    null_count = int(inferred_series.isna().sum())
    non_null_count = total_rows - null_count
    unique_count = int(inferred_series.nunique(dropna=True))

    frequent, rare = counter_samples(
        Counter(value for value in raw_series.tolist() if value != "")
    )

    lengths = [len(value) for value in raw_series.tolist() if value != ""]
    numeric_values = pd.to_numeric(inferred_series, errors="coerce")
    numeric_applicable = (
        is_numeric_dtype(inferred_series)
        or normalized in KNOWN_NUMERIC_COLUMNS
        or numeric_values.notna().sum() == non_null_count
    )

    minimum_numeric = ""
    maximum_numeric = ""
    if numeric_applicable and numeric_values.notna().any():
        minimum_numeric = numeric_values.min()
        maximum_numeric = numeric_values.max()

    metric = {
        **metadata,
        "columna": column,
        "posicion_columna": int(inferred.columns.get_loc(column)) + 1,
        "tipo_inferido": str(inferred_series.dtype),
        "filas_total": total_rows,
        "no_nulos": non_null_count,
        "nulos": null_count,
        "porcentaje_nulos": round((null_count / total_rows * 100), 4)
        if total_rows
        else 0,
        "valores_unicos": unique_count,
        "porcentaje_cardinalidad": round((unique_count / total_rows * 100), 4)
        if total_rows
        else 0,
        "longitud_min_texto": min(lengths) if lengths else "",
        "longitud_max_texto": max(lengths) if lengths else "",
        "minimo_numerico": minimum_numeric,
        "maximo_numerico": maximum_numeric,
        "ejemplos_frecuentes": json_value(frequent),
        "ejemplos_poco_frecuentes": json_value(rare),
    }

    leading_space_count = 0
    leading_space_examples: list[str] = []
    non_ascii_count = 0
    non_ascii_examples: list[str] = []

    for value, frequency in counts.items():
        token = value.strip().casefold()
        if value == "":
            add_special(
                special_rows,
                metadata,
                column,
                "EMPTY_STRING",
                "<EMPTY_STRING>",
                frequency,
            )
        if value != value.strip():
            leading_space_count += frequency
            if len(leading_space_examples) < SPECIAL_SAMPLE_LIMIT:
                leading_space_examples.append(display_value(value))
        if token in SPECIAL_TOKENS:
            add_special(
                special_rows,
                metadata,
                column,
                "SPECIAL_TOKEN",
                value,
                frequency,
            )
        if any(ord(char) > 127 for char in value):
            non_ascii_count += frequency
            if len(non_ascii_examples) < SPECIAL_SAMPLE_LIMIT:
                non_ascii_examples.append(display_value(value))
        if re.fullmatch(r"=\s*\d+", value.strip()):
            add_special(
                special_rows,
                metadata,
                column,
                "POSITION_EQUALS_PREFIX",
                value,
                frequency,
            )

    if leading_space_count:
        add_special(
            special_rows,
            metadata,
            column,
            "LEADING_OR_TRAILING_SPACE",
            "<LEADING_OR_TRAILING_SPACE>",
            leading_space_count,
            leading_space_examples,
        )

    if non_ascii_count:
        add_special(
            special_rows,
            metadata,
            column,
            "NON_ASCII",
            "<NON_ASCII>",
            non_ascii_count,
            non_ascii_examples,
        )

    if normalized in KNOWN_NUMERIC_COLUMNS:
        non_numeric = [
            value
            for value in counts
            if value.strip()
            and value.strip().casefold() not in SPECIAL_TOKENS
            and pd.isna(pd.to_numeric(value, errors="coerce"))
        ]
        if non_numeric:
            frequency = sum(counts[value] for value in non_numeric)
            add_special(
                special_rows,
                metadata,
                column,
                "NON_NUMERIC_IN_NUMERIC_COLUMN",
                "<NON_NUMERIC_IN_NUMERIC_COLUMN>",
                frequency,
                [display_value(value) for value in non_numeric[:SPECIAL_SAMPLE_LIMIT]],
            )

    if normalized in POTENTIAL_OUTLIER_COLUMNS:
        valid = numeric_values.dropna()
        if len(valid) >= 4:
            q1 = valid.quantile(0.25)
            q3 = valid.quantile(0.75)
            iqr = q3 - q1
            if iqr > 0:
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                outliers = valid[(valid < lower) | (valid > upper)]
                if not outliers.empty:
                    add_special(
                        special_rows,
                        metadata,
                        column,
                        "POTENTIAL_OUTLIER_IQR",
                        "<POTENTIAL_OUTLIER_IQR>",
                        int(outliers.size),
                        [display_value(value) for value in outliers.head(SPECIAL_SAMPLE_LIMIT)],
                    )

    is_medal = "medal" in normalized or "medalla" in normalized
    if is_medal:
        for value, frequency in counts.most_common():
            add_special(
                special_rows,
                metadata,
                column,
                "MEDAL_VALUE",
                "<EMPTY_STRING>" if value == "" else value,
                frequency,
            )

    if normalized in POSITION_COLUMNS:
        numeric_positions = {
            value: frequency
            for value, frequency in counts.items()
            if re.fullmatch(r"\d+(?:\.0+)?", value.strip())
        }
        equals_positions = {
            value: frequency
            for value, frequency in counts.items()
            if re.fullmatch(r"=\s*\d+", value.strip())
        }
        other_positions = {
            value: frequency
            for value, frequency in counts.items()
            if value.strip()
            and value not in numeric_positions
            and value not in equals_positions
        }
        for category, values in (
            ("NUMERIC_POSITION", numeric_positions),
            ("EQUALS_POSITION", equals_positions),
            ("OTHER_POSITION_VALUE", other_positions),
        ):
            if values:
                add_special(
                    special_rows,
                    metadata,
                    column,
                    "POSITION_CATEGORY",
                    category,
                    sum(values.values()),
                    [
                        display_value(value)
                        for value, _ in sorted(
                            values.items(), key=lambda item: (-item[1], item[0])
                        )[:SPECIAL_SAMPLE_LIMIT]
                    ],
                )

    return metric, {
        "column": column,
        "normalized": normalized,
        "raw_values": raw_series,
        "counts": counts,
        "numeric_values": numeric_values,
    }


def analyze_date_column(column_info: dict[str, Any]) -> dict[str, Any] | None:
    normalized = column_info["normalized"]
    if normalized not in DATE_COLUMNS:
        return None

    raw_values = column_info["raw_values"]
    non_empty = raw_values[raw_values.str.strip() != ""]
    if normalized == "year":
        parsed = pd.to_numeric(non_empty, errors="coerce")
        parseable = parsed.dropna()
        minimum = parseable.min() if not parseable.empty else ""
        maximum = parseable.max() if not parseable.empty else ""
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(non_empty, errors="coerce", format="mixed")
        parseable = parsed.dropna()
        minimum = parseable.min().date().isoformat() if not parseable.empty else ""
        maximum = parseable.max().date().isoformat() if not parseable.empty else ""

    return {
        "columna": column_info["column"],
        "valores_no_vacios": int(non_empty.size),
        "parseables": int(parseable.size),
        "no_parseables": int(non_empty.size - parseable.size),
        "minimo": minimum,
        "maximo": maximum,
    }


def analyze_noc_column(column_info: dict[str, Any]) -> dict[str, Any] | None:
    normalized = column_info["normalized"]
    if normalized != "noc":
        return None

    counts = Counter(
        value for value in column_info["raw_values"].tolist() if value.strip()
    )
    values = list(counts)
    code_values = [value for value in values if re.fullmatch(r"[A-Z]{3}", value)]
    descriptive_values = [value for value in values if value not in code_values]
    return {
        "columna": column_info["column"],
        "distintos": len(values),
        "codigos_tres_letras": len(code_values),
        "valores_descriptivos": len(descriptive_values),
        "frecuentes": [
            {"valor": value, "frecuencia": count}
            for value, count in counts.most_common(SAMPLE_LIMIT)
        ],
        "ejemplos_codigos": code_values[:SAMPLE_LIMIT],
        "ejemplos_descriptivos": descriptive_values[:SAMPLE_LIMIT],
    }


def analyze_position_column(column_info: dict[str, Any]) -> dict[str, Any] | None:
    if column_info["normalized"] not in POSITION_COLUMNS:
        return None

    counts = column_info["counts"]
    numeric_values: dict[str, int] = {}
    equals_values: dict[str, int] = {}
    special_values: dict[str, int] = {}
    for value, frequency in counts.items():
        stripped = value.strip()
        if not stripped:
            continue
        if re.fullmatch(r"=\s*\d+", stripped):
            equals_values[value] = frequency
        elif re.fullmatch(r"\d+(?:\.0+)?", stripped):
            numeric_values[value] = frequency
        else:
            special_values[value] = frequency
    return {
        "columna": column_info["column"],
        "numericos": numeric_values,
        "con_prefijo_igual": equals_values,
        "estados_especiales": special_values,
    }


def compact_counter(values: dict[str, int], limit: int = 10) -> str:
    ordered = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return json_value(
        [{"valor": display_value(value), "frecuencia": frequency} for value, frequency in ordered]
    )


def write_summary_markdown(
    file_rows: list[dict[str, Any]],
    date_rows: list[dict[str, Any]],
    noc_rows: list[dict[str, Any]],
    position_rows: list[dict[str, Any]],
    special_rows: list[dict[str, Any]],
    hash_rows: pd.DataFrame,
    pandas_version: str,
) -> None:
    lines: list[str] = [
        "# Profiling diagnóstico de fuentes olímpicas",
        "",
        "> Este informe describe los CSV originales sin limpiarlos, transformarlos, homologarlos, deduplicarlos ni modificar sus valores.",
        "",
        f"- Fecha de ejecución: `{datetime.now().astimezone().isoformat()}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- pandas: `{pandas_version}`",
        f"- Directorio analizado: `{RAW_DIR.as_posix()}`",
        f"- Archivos analizados: **{len(file_rows)}**",
        "",
        "## Validaciones de integridad",
        "",
        f"- Archivos esperados: `{EXPECTED_FILE_COUNT}`.",
        f"- Archivos analizados: `{len(file_rows)}`.",
        f"- SHA-256 contra `docs/source_manifest.csv`: **{(hash_rows['estado'] == 'MATCH').sum()} de {len(hash_rows)} coinciden**.",
        "- Los hashes se compararon antes y después del profiling; el script solo lee `data/raw`.",
        "",
        "## Resumen por archivo",
        "",
        "| Fuente | Archivo | Filas | Columnas | Filas vacías | Columnas vacías | Duplicados exactos | Tamaño (bytes) | Codificación |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for row in file_rows:
        lines.append(
            "| {fuente} | `{archivo_relativo}` | {filas_total} | {columnas_total} | "
            "{filas_completamente_vacias} | {columnas_completamente_vacias} | "
            "{duplicados_exactos} | {tamano_bytes} | `{codificacion}` |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Hallazgos importantes",
            "",
            "Los siguientes hallazgos son señales diagnósticas para revisar en el Bloque 3; no constituyen reglas de limpieza.",
            "",
        ]
    )

    duplicate_files = [row for row in file_rows if int(row["duplicados_exactos"]) > 0]
    empty_columns = [row for row in file_rows if int(row["columnas_completamente_vacias"]) > 0]
    if duplicate_files:
        lines.append(
            "- Hay duplicados exactos en: "
            + ", ".join(f"`{row['nombre_archivo']}` ({row['duplicados_exactos']})" for row in duplicate_files)
            + "."
        )
    else:
        lines.append("- No se detectaron duplicados exactos a nivel de fila.")

    if empty_columns:
        lines.append(
            "- Hay columnas completamente vacías en: "
            + ", ".join(f"`{row['nombre_archivo']}` ({row['columnas_completamente_vacias']})" for row in empty_columns)
            + "."
        )
    else:
        lines.append("- No se detectaron columnas completamente vacías.")

    special_counter = Counter(row["tipo_deteccion"] for row in special_rows)
    lines.append(
        "- Categorías especiales detectadas: "
        + ", ".join(f"`{name}` ({count})" for name, count in special_counter.most_common())
        + "."
    )

    lines.extend(["", "## Fechas y años", ""])
    if date_rows:
        lines.extend(
            [
                "| Archivo | Columna | No vacíos | Parseables | No parseables | Mínimo | Máximo |",
                "|---|---|---:|---:|---:|---|---|",
            ]
        )
        for row in date_rows:
            lines.append(
                f"| `{row['archivo_relativo']}` | `{row['columna']}` | {row['valores_no_vacios']} | "
                f"{row['parseables']} | {row['no_parseables']} | {row['minimo']} | {row['maximo']} |"
            )
    else:
        lines.append("No se encontraron columnas con nombres de fecha o año definidos.")

    lines.extend(["", "## Números", ""])
    lines.append(
        "Se revisaron las columnas `Age`, `Height`, `Weight`, `height_cm` y `weight_kg` "
        "cuando estuvieron presentes. Los mínimos, máximos, nulos, valores no numéricos "
        "y posibles atípicos se encuentran en `summary_columns.csv` y `special_values.csv`."
    )

    lines.extend(["", "## NOC", ""])
    if noc_rows:
        for row in noc_rows:
            lines.append(
                f"- `{row['archivo_relativo']}` / `{row['columna']}`: {row['distintos']} NOC distintos; "
                f"{row['codigos_tres_letras']} valores con patrón de tres letras mayúsculas y "
                f"{row['valores_descriptivos']} valores descriptivos. Frecuentes: "
                f"`{json_value(row['frecuentes'])}`."
            )
    else:
        lines.append("No se encontraron columnas NOC.")

    lines.extend(["", "## Medallas", ""])
    medal_rows = [row for row in special_rows if row["tipo_deteccion"] == "MEDAL_VALUE"]
    if medal_rows:
        for row in medal_rows:
            lines.append(
                f"- `{row['archivo_relativo']}` / `{row['columna']}`: "
                f"`{row['valor_especial_detectado']}` = {row['frecuencia']}."
            )
    else:
        lines.append("No se encontraron columnas de medalla.")

    lines.extend(["", "## Posiciones", ""])
    if position_rows:
        for row in position_rows:
            lines.append(
                f"- `{row['archivo_relativo']}` / `{row['columna']}`: "
                f"distintos numéricos={len(row['numericos'])}, "
                f"distintos con `=`={len(row['con_prefijo_igual'])}, "
                f"distintos estados/otros={len(row['estados_especiales'])}; "
                f"muestras numéricas={compact_counter(row['numericos'])}; "
                f"muestras con `=`={compact_counter(row['con_prefijo_igual'])}; "
                f"muestras de estados/otros={compact_counter(row['estados_especiales'])}."
            )
    else:
        lines.append("No se encontraron columnas de posición.")

    lines.extend(
        [
            "",
            "## Archivos generados",
            "",
            "- `summary_files.csv`: una fila por CSV.",
            "- `summary_columns.csv`: una fila por columna.",
            "- `special_values.csv`: valores especiales y categorías diagnósticas.",
            "- `hash_validation.csv`: comparación de SHA-256 contra el manifiesto.",
            "- `profiling_summary.md`: este informe.",
            "",
            "## Alcance y límites",
            "",
            "No se aplicaron reglas de limpieza, no se transformaron valores, no se homologaron nombres, "
            "no se eliminaron duplicados, no se hizo matching entre atletas y no se escribieron archivos "
            "dentro de `data/raw`. El análisis de calidad y las decisiones de transformación quedan para el Bloque 3.",
            "",
        ]
    )

    (OUTPUT_DIR / "profiling_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not RAW_DIR.exists():
        raise FileNotFoundError(f"No existe el directorio de entrada: {RAW_DIR}")

    paths = sorted(RAW_DIR.rglob("*.csv"), key=lambda path: path.relative_to(RAW_DIR).as_posix())
    if len(paths) != EXPECTED_FILE_COUNT:
        raise RuntimeError(
            f"Se esperaban exactamente {EXPECTED_FILE_COUNT} CSV y se encontraron {len(paths)}."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    hash_validation = validate_manifest(paths)

    file_rows: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []
    special_rows: list[dict[str, Any]] = []
    date_rows: list[dict[str, Any]] = []
    noc_rows: list[dict[str, Any]] = []
    position_rows: list[dict[str, Any]] = []

    for path in paths:
        metadata = source_metadata(path)
        encoding = detect_encoding(path)
        inferred, raw_text = read_csv_pair(path, encoding)

        empty_rows = int(inferred.isna().all(axis=1).sum()) if len(inferred.columns) else len(inferred)
        empty_columns = int(inferred.isna().all(axis=0).sum()) if len(inferred) else len(inferred.columns)
        file_rows.append(
            {
                **metadata,
                "filas_total": len(inferred),
                "columnas_total": len(inferred.columns),
                "nombres_columnas": json_value([str(column) for column in inferred.columns]),
                "filas_completamente_vacias": empty_rows,
                "columnas_completamente_vacias": empty_columns,
                "duplicados_exactos": int(inferred.duplicated(keep="first").sum()),
                "tamano_bytes": path.stat().st_size,
                "codificacion": encoding,
            }
        )

        for column in inferred.columns:
            metric, column_info = profile_column(
                inferred,
                raw_text,
                metadata,
                str(column),
                special_rows,
            )
            column_rows.append(metric)

            date_info = analyze_date_column(column_info)
            if date_info:
                date_rows.append({**metadata, **date_info})

            noc_info = analyze_noc_column(column_info)
            if noc_info:
                noc_rows.append({**metadata, **noc_info})

            position_info = analyze_position_column(column_info)
            if position_info:
                position_rows.append({**metadata, **position_info})

    files_df = pd.DataFrame(file_rows)
    columns_df = pd.DataFrame(column_rows)
    special_df = pd.DataFrame(
        special_rows,
        columns=[
            "fuente",
            "archivo_relativo",
            "nombre_archivo",
            "columna",
            "tipo_deteccion",
            "valor_especial_detectado",
            "frecuencia",
            "ejemplos",
        ],
    )

    files_df.to_csv(OUTPUT_DIR / "summary_files.csv", index=False, encoding="utf-8-sig")
    columns_df.to_csv(OUTPUT_DIR / "summary_columns.csv", index=False, encoding="utf-8-sig")
    special_df.to_csv(OUTPUT_DIR / "special_values.csv", index=False, encoding="utf-8-sig")
    hash_validation.to_csv(OUTPUT_DIR / "hash_validation.csv", index=False, encoding="utf-8-sig")
    write_summary_markdown(
        file_rows,
        date_rows,
        noc_rows,
        position_rows,
        special_rows,
        hash_validation,
        pd.__version__,
    )

    generated = [
        OUTPUT_DIR / "summary_files.csv",
        OUTPUT_DIR / "summary_columns.csv",
        OUTPUT_DIR / "special_values.csv",
        OUTPUT_DIR / "hash_validation.csv",
        OUTPUT_DIR / "profiling_summary.md",
    ]
    missing_reports = [str(path) for path in generated if not path.exists()]
    if missing_reports:
        raise RuntimeError(f"No se generaron todos los reportes: {missing_reports}")

    post_hash_validation = validate_manifest(paths)
    if not (post_hash_validation["estado"] == "MATCH").all():
        raise RuntimeError("Los hashes cambiaron durante el profiling.")

    print(f"Archivos CSV analizados: {len(paths)}")
    print(f"Filas documentadas en summary_files.csv: {len(files_df)}")
    print(f"Columnas documentadas en summary_columns.csv: {len(columns_df)}")
    print(f"Detecciones en special_values.csv: {len(special_df)}")
    print(f"SHA-256 coincidentes: {(post_hash_validation['estado'] == 'MATCH').sum()}/{len(post_hash_validation)}")
    print(f"Raw intacto: {'SI' if (post_hash_validation['estado'] == 'MATCH').all() else 'NO'}")
    print(f"Reportes generados en: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
