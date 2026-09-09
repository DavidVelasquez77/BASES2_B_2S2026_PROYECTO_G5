"""Limpieza y homologación por fuente para el Bloque 3.

El script lee exclusivamente data/raw y escribe archivos intermedios por
fuente en data/intermediate/cleaned, además de reportes en docs/cleaning.
No realiza matching, deduplicación global, consolidación ni carga SQL.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
INTERMEDIATE_DIR = ROOT / "data" / "intermediate" / "cleaned"
CLEANING_DIR = ROOT / "docs" / "cleaning"
MANIFEST_FILE = ROOT / "docs" / "source_manifest.csv"

EXPECTED_FILES = [
    "fuente1/clean/bios.csv",
    "fuente1/clean/bios_locs.csv",
    "fuente1/clean/noc_regions.csv",
    "fuente1/clean/populations.csv",
    "fuente1/clean/results.csv",
    "fuente1/raw/bios.csv",
    "fuente1/raw/results.csv",
    "fuente2/athlete_events.csv",
    "fuente3/olympics_dataset.csv",
    "fuente4/datalab_export.csv",
]

OUTPUT_NAMES = {
    "fuente1/clean/bios.csv": "fuente1_clean_bios.csv",
    "fuente1/clean/bios_locs.csv": "fuente1_clean_bios_locs.csv",
    "fuente1/clean/noc_regions.csv": "fuente1_clean_noc_regions.csv",
    "fuente1/clean/populations.csv": "fuente1_clean_populations_long.csv",
    "fuente1/clean/results.csv": "fuente1_clean_results.csv",
    "fuente1/raw/bios.csv": "fuente1_raw_bios.csv",
    "fuente1/raw/results.csv": "fuente1_raw_results.csv",
    "fuente2/athlete_events.csv": "fuente2_athlete_events.csv",
    "fuente3/olympics_dataset.csv": "fuente3_olympics_dataset.csv",
    "fuente4/datalab_export.csv": "fuente4_datalab_export.csv",
}

SEMANTIC_MISSING_MARKERS = {"na", "n/a", "null", "none"}
MEDAL_VALUES = {"gold": "Gold", "silver": "Silver", "bronze": "Bronze"}
KNOWN_STATUSES = {"DNS", "DNF", "DQ", "DSQ"}
DATE_CACHE: dict[str, str | None] = {}

# Los marcadores semánticos no se aplican por defecto. El vacío se trata como
# ausencia después de strip(); los marcadores NA/N/A/null/None solo se
# aceptan en estas columnas estructurales o de medición. Los campos
# descriptivos quedan fuera deliberadamente.
MISSING_SEMANTIC_COLUMNS: dict[str, set[str]] = {
    "fuente1/clean/bios.csv": {
        "athlete_id", "born_date", "height_cm", "weight_kg", "died_date",
    },
    "fuente1/clean/bios_locs.csv": {
        "athlete_id", "born_date", "height_cm", "weight_kg", "died_date", "lat", "long",
    },
    "fuente1/clean/noc_regions.csv": {"NOC"},
    "fuente1/clean/populations.csv": {"Country Code"},
    "fuente1/clean/results.csv": {"year", "athlete_id", "place", "tied", "medal"},
    "fuente1/raw/bios.csv": {"athlete_id", "Born", "Died", "Measurements"},
    "fuente1/raw/results.csv": {"Games", "Pos", "Medal", "athlete_id"},
    "fuente2/athlete_events.csv": {"ID", "Age", "Height", "Weight", "Games", "Year", "Season", "Medal"},
    "fuente3/olympics_dataset.csv": {"player_id", "Year", "Season", "Medal"},
    "fuente4/datalab_export.csv": {"id", "age", "height", "weight", "games", "year", "season", "medal"},
}


def is_null_value(value: Any) -> bool:
    """Detect Python/pandas/numpy scalar nulls without treating text as null."""
    if value is None or value is pd.NA:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    if type(result).__name__ == "bool_":
        return bool(result)
    return False


def relative_raw(path: Path) -> str:
    return path.relative_to(RAW_DIR).as_posix()


def source_of(relative: str) -> str:
    return relative.split("/", 1)[0]


def display(value: Any, limit: int = 240) -> str:
    if is_null_value(value):
        return ""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def detect_encoding(path: Path) -> str:
    sample = path.read_bytes()[:2 * 1024 * 1024]
    if sample.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            pass
    return "latin-1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_paths() -> list[Path]:
    found = sorted(RAW_DIR.rglob("*.csv"), key=relative_raw)
    expected = set(EXPECTED_FILES)
    actual = {relative_raw(path) for path in found}
    if actual != expected:
        raise RuntimeError(
            "El conjunto de CSV no coincide con el esperado. "
            f"Faltantes={sorted(expected - actual)}; adicionales={sorted(actual - expected)}"
        )
    return found


def manifest_hashes() -> dict[str, str]:
    manifest = pd.read_csv(MANIFEST_FILE, dtype=str, keep_default_na=False)
    required = {"archivo_relativo", "sha256"}
    if not required.issubset(manifest.columns):
        raise RuntimeError("source_manifest.csv no contiene archivo_relativo y sha256")
    return {
        str(row["archivo_relativo"]): str(row["sha256"])
        for _, row in manifest.iterrows()
    }


def validate_raw_hashes(paths: list[Path]) -> pd.DataFrame:
    expected = manifest_hashes()
    rows: list[dict[str, str]] = []
    for path in paths:
        relative = f"data/raw/{relative_raw(path)}"
        actual = sha256(path)
        manifest_value = expected.get(relative, "")
        status = "MATCH" if manifest_value and manifest_value == actual else "MISMATCH"
        rows.append(
            {
                "archivo_relativo": relative,
                "sha256_manifest": manifest_value,
                "sha256_actual": actual,
                "estado": status,
            }
        )
    result = pd.DataFrame(rows)
    if not (result["estado"] == "MATCH").all():
        raise RuntimeError(
            "Hash SHA-256 no coincide; el proceso se detiene: "
            + json_compact(result[result["estado"] != "MATCH"].to_dict(orient="records"))
        )
    return result


def read_raw(path: Path) -> tuple[pd.DataFrame, str]:
    encoding = detect_encoding(path)
    frame = pd.read_csv(
        path,
        encoding=encoding,
        dtype=object,
        keep_default_na=False,
        na_filter=False,
        low_memory=False,
    )
    return frame, encoding


def is_missing_marker(
    value: Any,
    allow_semantic: bool = False,
    medal: bool = False,
    include_no_medal: bool = True,
) -> bool:
    if is_null_value(value):
        return True
    text = str(value).strip()
    if not text:
        return True
    if allow_semantic and text.casefold() in SEMANTIC_MISSING_MARKERS:
        return True
    return include_no_medal and medal and text.casefold() == "no medal"


def null_like_count(frame: pd.DataFrame, file_key: str) -> int:
    count = 0
    for column in frame.columns:
        medal = "medal" in str(column).casefold()
        allow_semantic = column in MISSING_SEMANTIC_COLUMNS.get(file_key, set())
        count += sum(
            is_missing_marker(value, allow_semantic=allow_semantic, medal=medal)
            for value in frame[column].tolist()
        )
    return int(count)


def actual_null_count(frame: pd.DataFrame) -> int:
    return int(sum(is_null_value(value) for column in frame.columns for value in frame[column].tolist()))


def strip_text(frame: pd.DataFrame, audit: "Audit", file_key: str) -> int:
    changed = 0
    processed = 0
    for column in frame.columns:
        values = []
        for value in frame[column].tolist():
            if isinstance(value, str):
                stripped = value.strip()
                changed += int(stripped != value)
                values.append(stripped)
            else:
                values.append(value)
        frame[column] = values
    audit.rule(
        file_key,
        "*",
        "espacios en texto",
        "Aplicar strip() a columnas textuales sin eliminar tildes ni Unicode.",
        "Evitar diferencias artificiales por espacios y conservar el contenido original.",
        changed,
    )
    return changed


def normalize_missing(frame: pd.DataFrame, audit: "Audit", file_key: str) -> int:
    total = 0
    for column in frame.columns:
        medal = "medal" in str(column).casefold()
        allow_semantic = column in MISSING_SEMANTIC_COLUMNS.get(file_key, set())
        changed = 0
        processed = 0
        values: list[Any] = []
        for value in frame[column].tolist():
            if is_missing_marker(
                value,
                allow_semantic=allow_semantic,
                medal=medal,
                include_no_medal=False,
            ):
                if not is_null_value(value):
                    processed += 1
                # Empty text is already serialized as an empty CSV field;
                # converting it internally to NULL is not a value change.
                if not is_null_value(value) and str(value).strip():
                    changed += 1
                values.append(pd.NA)
            else:
                values.append(value)
        frame[column] = values
        if changed or processed:
            total += changed
            audit.rule(
                file_key,
                str(column),
                "marcadores de ausencia",
                "Normalizar vacío a NULL y aceptar NA/N/A/null/None solo en la matriz explícita por columna.",
                "Evitar sustituciones globales; No medal se procesa exclusivamente por la regla de medallas.",
                changed,
                processed,
            )
    return total


def numeric_value(value: Any) -> Any:
    if is_null_value(value):
        return pd.NA
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return value
    if float(parsed).is_integer():
        return int(parsed)
    return float(parsed)


def convert_numeric(
    frame: pd.DataFrame,
    column: str,
    audit: "Audit",
    file_key: str,
    unresolved_reason: str,
) -> int:
    if column not in frame.columns:
        return 0
    modified = 0
    processed = 0
    values: list[Any] = []
    invalid = Counter()
    for value in frame[column].tolist():
        if is_null_value(value):
            values.append(pd.NA)
            continue
        parsed = pd.to_numeric(value, errors="coerce")
        if pd.isna(parsed):
            values.append(value)
            invalid[display(value)] += 1
        else:
            normalized = numeric_value(value)
            values.append(normalized)
            processed += 1
            modified += int(str(value).strip() != str(normalized))
    frame[column] = values
    if processed:
        audit.rule(
            file_key,
            column,
            "valor numérico representado como texto",
            "Convertir a número cuando la conversión sea segura.",
            "Permitir rangos y consultas numéricas sin borrar valores no convertibles.",
            modified,
            processed,
        )
    for value, frequency in invalid.items():
        audit.unresolved(file_key, column, value, frequency, unresolved_reason)
    return modified


MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)


def partial_date_reason(value: Any) -> str | None:
    if is_null_value(value):
        return None
    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text):
        return "Fecha parcial: solo contiene año; se conserva sin inventar día ni mes."
    if re.fullmatch(rf"(?:{MONTH_NAMES})\s+\d{{4}}", text, flags=re.IGNORECASE):
        return "Fecha parcial: contiene mes y año, pero no día; se conserva sin inventar el día."
    return None


def parse_iso_date(value: Any) -> str | None:
    if is_null_value(value) or not str(value).strip():
        return None
    text = str(value).strip()
    if text in DATE_CACHE:
        return DATE_CACHE[text]

    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %B %Y",
        "%d %b %Y",
    )
    for date_format in formats:
        try:
            parsed = datetime.strptime(text, date_format)
            result = parsed.date().isoformat()
            DATE_CACHE[text] = result
            return result
        except ValueError:
            continue

    DATE_CACHE[text] = None
    return None


def normalize_date_column(
    frame: pd.DataFrame,
    column: str,
    audit: "Audit",
    file_key: str,
) -> int:
    if column not in frame.columns:
        return 0
    modified = 0
    processed = 0
    values: list[Any] = []
    for value in frame[column].tolist():
        if is_null_value(value) or not str(value).strip():
            values.append(pd.NA)
            continue
        parsed = parse_iso_date(value)
        if parsed is None:
            values.append(value)
            audit.unresolved(
                file_key,
                column,
                display(value),
                1,
                partial_date_reason(value)
                or "Fecha no parseable con seguridad; se conserva el valor original.",
            )
        else:
            values.append(parsed)
            processed += 1
            modified += int(str(value).strip() != parsed)
    frame[column] = values
    if processed:
        audit.rule(
            file_key,
            column,
            "fecha no ISO o fecha validable",
            "Normalizar fechas interpretables a YYYY-MM-DD.",
            "Alinear las fechas con el tipo DATE previsto en el modelo ER.",
            modified,
            processed,
        )
    return modified


def normalize_medal(frame: pd.DataFrame, column: str, audit: "Audit", file_key: str) -> int:
    if column not in frame.columns:
        return 0
    changed = 0
    processed = 0
    values: list[Any] = []
    unexpected = Counter()
    for value in frame[column].tolist():
        if is_null_value(value) or not str(value).strip():
            values.append(pd.NA)
            continue
        text = str(value).strip()
        processed += 1
        if text.casefold() in SEMANTIC_MISSING_MARKERS or text.casefold() == "no medal":
            values.append(pd.NA)
            changed += 1
        elif text.casefold() in MEDAL_VALUES:
            canonical = MEDAL_VALUES[text.casefold()]
            values.append(canonical)
            changed += int(canonical != text)
        else:
            values.append(text)
            unexpected[text] += 1
    frame[column] = values
    if processed:
        audit.rule(
            file_key,
            column,
            "medalla con representación heterogénea",
            "Normalizar a Gold, Silver, Bronze o NULL.",
            "Coincidir con PARTICIPACION.medalla sin crear una entidad de medallas.",
            changed,
            processed,
        )
    for value, frequency in unexpected.items():
        audit.unresolved(file_key, column, value, frequency, "Valor de medalla no reconocido; se conserva.")
    return changed


def normalize_boolean(
    frame: pd.DataFrame,
    column: str,
    output_column: str,
    audit: "Audit",
    file_key: str,
) -> int:
    if column not in frame.columns:
        return 0
    true_values = {"true", "1", "yes", "y"}
    false_values = {"false", "0", "no", "n"}
    changed = 0
    processed = 0
    values: list[Any] = []
    for value in frame[column].tolist():
        if is_null_value(value) or not str(value).strip():
            values.append(pd.NA)
            continue
        text = str(value).strip()
        if text.casefold() in true_values:
            values.append(True)
            processed += 1
            changed += int(text.casefold() != "true")
        elif text.casefold() in false_values:
            values.append(False)
            processed += 1
            changed += int(text.casefold() != "false")
        else:
            values.append(value)
            audit.unresolved(file_key, column, text, 1, "Booleano no reconocible; se conserva.")
    frame[output_column] = values
    if output_column != column:
        frame.drop(columns=[column], inplace=True)
    if processed:
        audit.rule(
            file_key,
            column,
            "indicador booleano",
            "Homologar valores booleanos reconocibles a True/False.",
            "Representar empatado como atributo booleano del resultado.",
            changed,
            processed,
        )
    return changed


def parse_games(value: Any) -> tuple[Any, Any] | None:
    if is_null_value(value) or not str(value).strip():
        return None
    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})\s+(.+?)(?:\s+Olympics)?", text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), match.group(2).strip()


def split_games(
    frame: pd.DataFrame,
    games_column: str,
    audit: "Audit",
    file_key: str,
    year_column: str | None = None,
    season_column: str | None = None,
) -> tuple[list[Any], list[Any], int]:
    years: list[Any] = []
    seasons: list[Any] = []
    parsed_count = 0
    for index, value in enumerate(frame[games_column].tolist()):
        parsed = parse_games(value)
        if parsed is None:
            years.append(pd.NA)
            seasons.append(pd.NA)
            if not is_null_value(value) and str(value).strip():
                audit.unresolved(file_key, games_column, display(value), 1, "Games no parseable con seguridad.")
            continue
        games_year, games_season = parsed
        parsed_count += 1
        if year_column and season_column:
            source_year = frame.iloc[index][year_column]
            source_season = frame.iloc[index][season_column]
            if str(source_year).strip() and str(source_year).strip() != str(games_year):
                audit.unresolved(
                    file_key,
                    games_column,
                    display(value),
                    1,
                    f"Inconsistencia Games/year: Games={games_year}, year={display(source_year)}.",
                )
            if str(source_season).strip().casefold() != str(games_season).strip().casefold():
                audit.unresolved(
                    file_key,
                    games_column,
                    display(value),
                    1,
                    f"Inconsistencia Games/season: Games={display(games_season)}, season={display(source_season)}.",
                )
            years.append(source_year)
            seasons.append(source_season)
        else:
            years.append(games_year)
            seasons.append(games_season)
    audit.rule(
        file_key,
        games_column,
        "Games compuesto",
        "Separar Games en year y season y conservar games_original para trazabilidad intermedia.",
        "El modelo final representa año y temporada por separado.",
        0,
        parsed_count,
    )
    return years, seasons, parsed_count


def parse_location_date(value: Any) -> dict[str, Any]:
    result = {
        "date": pd.NA,
        "city": pd.NA,
        "region": pd.NA,
        "country": pd.NA,
        "reason": None,
    }
    if is_null_value(value) or not str(value).strip():
        return result

    text = str(value).strip()
    location_text = text
    country_match = re.search(r"\(([^()]*)\)\s*$", text)
    if country_match:
        result["country"] = country_match.group(1).strip() or pd.NA
        location_text = text[: country_match.start()].strip()

    if re.search(r"\s+in\s+", location_text, flags=re.IGNORECASE):
        date_text, place_text = re.split(r"\s+in\s+", location_text, maxsplit=1, flags=re.IGNORECASE)
    else:
        date_text, place_text = location_text, ""

    full_date_match = re.search(
        r"\b\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}\b",
        date_text,
        flags=re.IGNORECASE,
    )
    if full_date_match:
        parsed = parse_iso_date(full_date_match.group(0))
        if parsed:
            result["date"] = parsed
        else:
            result["reason"] = "Fecha textual no parseable."
    elif partial_date_reason(date_text):
        result["reason"] = partial_date_reason(date_text)
    else:
        result["reason"] = "No se identificó una fecha completa."

    if place_text:
        parts = [part.strip() for part in place_text.split(",") if part.strip()]
        if parts:
            result["city"] = parts[0]
            if len(parts) > 1:
                result["region"] = ", ".join(parts[1:])
        else:
            result["reason"] = result["reason"] or "Lugar vacío después de la fecha."
    elif result["reason"] is None:
        result["reason"] = "Fecha extraída sin ciudad/región explícita."

    return result


def extract_location_columns(
    frame: pd.DataFrame,
    source_column: str,
    prefix: str,
    audit: "Audit",
    file_key: str,
) -> int:
    if source_column not in frame.columns:
        return 0
    date_values: list[Any] = []
    city_values: list[Any] = []
    region_values: list[Any] = []
    country_values: list[Any] = []
    unresolved = Counter()
    parsed_count = 0
    for value in frame[source_column].tolist():
        parsed = parse_location_date(value)
        date_values.append(parsed["date"])
        city_values.append(parsed["city"])
        region_values.append(parsed["region"])
        country_values.append(parsed["country"])
        if not is_null_value(parsed["date"]):
            parsed_count += 1
        if parsed["reason"] and not is_null_value(value):
            unresolved[display(value) + " || " + parsed["reason"]] += 1
    frame[f"{prefix}_date"] = date_values
    frame[f"{prefix}_city"] = city_values
    frame[f"{prefix}_region"] = region_values
    frame[f"{prefix}_country"] = country_values
    for key, frequency in unresolved.items():
        original, reason = key.split(" || ", 1)
        audit.unresolved(file_key, source_column, original, frequency, reason)
    audit.rule(
        file_key,
        source_column,
        "fecha y lugar biográfico compuesto",
        "Extraer fecha completa, ciudad, región y país cuando sean identificables; conservar la columna original.",
        "El modelo ER separa fecha y componentes geográficos, pero no permite inventar partes ausentes.",
        0,
        parsed_count,
    )
    return 0


def extract_measurements(
    frame: pd.DataFrame,
    source_column: str,
    audit: "Audit",
    file_key: str,
) -> int:
    if source_column not in frame.columns:
        return 0
    heights: list[Any] = []
    weights: list[Any] = []
    unresolved = Counter()
    parsed_count = 0
    for value in frame[source_column].tolist():
        if is_null_value(value) or not str(value).strip():
            heights.append(pd.NA)
            weights.append(pd.NA)
            continue
        text = str(value).strip()
        height_match = re.search(r"(\d+(?:\.\d+)?)\s*cm\b", text, flags=re.IGNORECASE)
        weight_match = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", text, flags=re.IGNORECASE)
        heights.append(numeric_value(height_match.group(1)) if height_match else pd.NA)
        weights.append(numeric_value(weight_match.group(1)) if weight_match else pd.NA)
        if height_match or weight_match:
            parsed_count += 1
        if not height_match and not weight_match:
            unresolved[text] += 1
    frame["height_cm"] = heights
    frame["weight_kg"] = weights
    for value, frequency in unresolved.items():
        audit.unresolved(file_key, source_column, value, frequency, "Measurements no contiene cm/kg interpretables.")
    audit.rule(
        file_key,
        source_column,
        "Measurements compuesto",
        "Extraer height_cm y weight_kg cuando existan unidades cm/kg; conservar measurements_original.",
        "Separar atributos que el modelo ER almacena como altura y peso.",
        0,
        parsed_count,
    )
    return 0


def normalize_positions(
    frame: pd.DataFrame,
    source_column: str,
    audit: "Audit",
    file_key: str,
) -> int:
    if source_column not in frame.columns:
        return 0
    positions: list[Any] = []
    tied: list[Any] = []
    statuses: list[Any] = []
    originals: list[Any] = []
    classifications: list[str] = []
    unresolved = Counter()
    counts = Counter()
    for value in frame[source_column].tolist():
        original = pd.NA if is_null_value(value) else str(value).strip()
        originals.append(original)
        if is_null_value(original) or not str(original).strip():
            positions.append(pd.NA)
            tied.append(pd.NA)
            statuses.append(pd.NA)
            classifications.append("sin_resultado")
            counts["sin_resultado"] += 1
            continue
        text = str(original)
        if re.fullmatch(r"\d+(?:\.0+)?", text):
            positions.append(int(float(text)))
            tied.append(False)
            statuses.append(pd.NA)
            classifications.append("posicion_numerica")
            counts["posicion_numerica"] += 1
        elif re.fullmatch(r"=\s*\d+", text):
            positions.append(int(re.search(r"\d+", text).group(0)))
            tied.append(True)
            statuses.append(pd.NA)
            classifications.append("empate")
            counts["empate"] += 1
        elif text.upper() in KNOWN_STATUSES:
            positions.append(pd.NA)
            tied.append(False)
            statuses.append(text.upper())
            classifications.append("estado_resultado")
            counts["estado_resultado"] += 1
        else:
            positions.append(pd.NA)
            tied.append(pd.NA)
            statuses.append(pd.NA)
            classifications.append("complejo_no_resuelto")
            unresolved[text] += 1
            counts["complejo_no_resuelto"] += 1
    frame["pos_original"] = originals
    frame["posicion"] = positions
    frame["empatado"] = tied
    frame["estado_resultado"] = statuses
    frame["pos_clasificacion"] = classifications
    for value, frequency in unresolved.items():
        audit.unresolved(
            file_key,
            source_column,
            value,
            frequency,
            "Valor de Pos complejo; no se inventó una interpretación.",
        )
    audit.rule(
        file_key,
        source_column,
        "posición, empate y estado mezclados",
        "Separar posicion, empatado, estado_resultado, pos_original y pos_clasificacion.",
        "Alinear resultados con PARTICIPACION y conservar casos no resolubles para revisión.",
        0,
        len(frame),
    )
    for classification, frequency in counts.items():
        audit.rule(
            file_key,
            source_column,
            f"Pos clasificación: {classification}",
            "Clasificar sin borrar pos_original.",
            "Permitir transformar solo patrones seguros.",
            frequency,
        )
    # Las cantidades por clasificación son frecuencias de filas reales. No
    # se usa len(unresolved), que solo representa valores distintos.
    return 0


def rename_existing(frame: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return frame.rename(columns={key: value for key, value in mapping.items() if key in frame.columns})


def reorder(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    present = [column for column in columns if column in frame.columns]
    remaining = [column for column in frame.columns if column not in present]
    return frame[present + remaining]


class Audit:
    def __init__(self) -> None:
        self.rules: list[dict[str, Any]] = []
        self.unresolved_counts: defaultdict[tuple[str, str, str, str], int] = defaultdict(int)
        self.duplicates: list[dict[str, Any]] = []
        self.summaries: list[dict[str, Any]] = []
        self.processed_by_file: defaultdict[str, int] = defaultdict(int)

    def rule(
        self,
        file_key: str,
        column: str,
        problem: str,
        rule: str,
        justification: str,
        affected: int,
        processed: int | None = None,
    ) -> None:
        if processed is None:
            processed = affected
        if affected or processed:
            self.processed_by_file[file_key] += int(processed)
            self.rules.append(
                {
                    "fuente": source_of(file_key),
                    "archivo": f"data/raw/{file_key}",
                    "columna": column,
                    "problema_detectado": problem,
                    "regla_aplicada": rule,
                    "justificacion": justification,
                    "valores_afectados": int(affected),
                    "operaciones_procesadas": int(processed),
                }
            )

    def unresolved(
        self,
        file_key: str,
        column: str,
        value: str,
        frequency: int,
        reason: str,
    ) -> None:
        key = (file_key, column, value, reason)
        self.unresolved_counts[key] += int(frequency)

    def summary(
        self,
        file_key: str,
        rows_in: int,
        rows_out: int,
        cols_in: int,
        cols_out: int,
        nulls_before: int,
        nulls_after: int,
        modified: int,
        processed: int,
        discarded: int = 0,
        discard_reason: str = "",
    ) -> None:
        self.summaries.append(
            {
                "fuente": source_of(file_key),
                "archivo": f"data/raw/{file_key}",
                "filas_entrada": rows_in,
                "filas_salida": rows_out,
                "columnas_entrada": cols_in,
                "columnas_salida": cols_out,
                "nulos_antes": nulls_before,
                "nulos_despues": nulls_after,
                "valores_modificados": modified,
                "operaciones_procesadas": processed,
                "registros_descartados": discarded,
                "motivo_descartes": discard_reason,
            }
        )


def prepare(frame: pd.DataFrame, audit: Audit, file_key: str) -> int:
    return strip_text(frame, audit, file_key) + normalize_missing(frame, audit, file_key)


def clean_bios_clean(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    for column in ("born_date", "died_date"):
        modified += normalize_date_column(frame, column, audit, file_key)
    for column in ("height_cm", "weight_kg", "lat", "long"):
        modified += convert_numeric(frame, column, audit, file_key, "Valor no numérico en columna numérica; se conserva.")
    frame = rename_existing(
        frame,
        {
            "NOC": "noc_nombre",
        },
    )
    return reorder(
        frame,
        [
            "athlete_id",
            "name",
            "born_date",
            "born_city",
            "born_region",
            "born_country",
            "noc_nombre",
            "height_cm",
            "weight_kg",
            "died_date",
            "lat",
            "long",
        ],
    ), modified


def clean_noc_regions(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    frame = rename_existing(frame, {"NOC": "noc_codigo"})
    return reorder(frame, ["noc_codigo", "region", "notes"]), modified


def clean_populations(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    id_columns = ["Country Name", "Country Code"]
    year_columns = [column for column in frame.columns if str(column).isdigit()]
    for column in year_columns:
        modified += convert_numeric(frame, column, audit, file_key, "Población no numérica; se conserva.")
    frame = frame.rename(columns={"Country Name": "country_name", "Country Code": "country_code"})
    long_frame = frame.melt(
        id_vars=["country_name", "country_code"],
        value_vars=year_columns,
        var_name="year",
        value_name="population",
    )
    long_frame["year"] = [numeric_value(value) for value in long_frame["year"].tolist()]
    modified += convert_numeric(long_frame, "population", audit, file_key, "Población no numérica después de pasar a formato largo.")
    audit.rule(
        file_key,
        "1960-2023",
        "población en formato ancho",
        "Convertir columnas anuales a country_name, country_code, year y population.",
        "Preparar la relación 1:N de POBLACION sin eliminar agregados.",
        0,
        len(long_frame),
    )
    return long_frame[["country_name", "country_code", "year", "population"]], modified


def clean_clean_results(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    modified += convert_numeric(frame, "year", audit, file_key, "Año no numérico; se conserva.")
    modified += convert_numeric(frame, "place", audit, file_key, "Posición no numérica; se conserva.")
    modified += normalize_boolean(frame, "tied", "empatado", audit, file_key)
    modified += normalize_medal(frame, "medal", audit, file_key)
    frame = rename_existing(
        frame,
        {
            "type": "season",
            "discipline": "discipline",
            "event": "event",
            "as": "nombre_competencia",
            "noc": "noc_codigo",
            "team": "equipo",
            "place": "posicion",
            "medal": "medalla",
        },
    )
    return reorder(
        frame,
        [
            "year",
            "season",
            "discipline",
            "event",
            "nombre_competencia",
            "athlete_id",
            "noc_codigo",
            "equipo",
            "posicion",
            "empatado",
            "medalla",
        ],
    ), modified


def clean_raw_bios(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    modified += extract_location_columns(frame, "Born", "born", audit, file_key)
    modified += extract_location_columns(frame, "Died", "died", audit, file_key)
    modified += extract_measurements(frame, "Measurements", audit, file_key)
    frame = frame.rename(
        columns={
            "Born": "born_original",
            "Died": "died_original",
            "Measurements": "measurements_original",
            "Roles": "roles",
            "Sex": "sex",
            "NOC": "noc_nombre",
            "Full name": "full_name",
            "Used name": "used_name",
            "Nick/petnames": "nick_petnames",
            "Title(s)": "titles",
            "Other names": "other_names",
            "Affiliations": "affiliations",
            "Nationality": "nationality",
            "Original name": "original_name",
            "Name order": "name_order",
        }
    )
    return reorder(
        frame,
        [
            "roles",
            "sex",
            "full_name",
            "used_name",
            "born_original",
            "died_original",
            "born_date",
            "born_city",
            "born_region",
            "born_country",
            "died_date",
            "died_city",
            "died_region",
            "died_country",
            "noc_nombre",
            "athlete_id",
            "measurements_original",
            "height_cm",
            "weight_kg",
            "affiliations",
            "nick_petnames",
            "titles",
            "other_names",
            "nationality",
            "original_name",
            "name_order",
        ],
    ), modified


def clean_raw_results(frame: pd.DataFrame, audit: Audit, file_key: str) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    years, seasons, _games_processed = split_games(frame, "Games", audit, file_key)
    frame["year"] = years
    frame["season"] = seasons
    modified += normalize_medal(frame, "Medal", audit, file_key)
    normalize_positions(frame, "Pos", audit, file_key)
    if "Unnamed: 7" in frame.columns:
        frame.drop(columns=["Unnamed: 7"], inplace=True)
        audit.rule(
            file_key,
            "Unnamed: 7",
            "columna técnica completamente vacía",
            "Excluir del archivo intermedio limpio.",
            "El modelo no conserva columnas accidentales y la fuente no aporta información.",
            0,
            len(frame),
        )
    if "Pos" in frame.columns:
        frame.drop(columns=["Pos"], inplace=True)
        audit.rule(
            file_key,
            "Pos",
            "posición compuesta desglosada",
            "Sustituir Pos por pos_original, posicion, empatado, estado_resultado y pos_clasificacion.",
            "Evitar duplicar el mismo dato y conservar el valor original en pos_original.",
            0,
            len(frame),
        )
    frame = frame.rename(
        columns={
            "Games": "games_original",
            "Event": "event",
            "Team": "equipo",
            "Medal": "medalla",
            "As": "nombre_competencia",
            "NOC": "noc_codigo",
            "Discipline": "discipline",
            "Nationality": "nationality",
        }
    )
    return reorder(
        frame,
        [
            "year",
            "season",
            "games_original",
            "event",
            "discipline",
            "nombre_competencia",
            "athlete_id",
            "noc_codigo",
            "nationality",
            "equipo",
            "pos_original",
            "posicion",
            "empatado",
            "estado_resultado",
            "pos_clasificacion",
            "medalla",
        ],
    ), modified


def clean_participation_source(
    frame: pd.DataFrame,
    audit: Audit,
    file_key: str,
    source_kind: str,
) -> tuple[pd.DataFrame, int]:
    modified = prepare(frame, audit, file_key)
    year_column = "Year" if "Year" in frame.columns else "year"
    season_column = "Season" if "Season" in frame.columns else "season"
    if "Games" in frame.columns:
        games_years, games_seasons, _games_processed = split_games(
            frame,
            "Games",
            audit,
            file_key,
            year_column,
            season_column,
        )
        frame["games_year_diagnostic"] = games_years
        frame["games_season_diagnostic"] = games_seasons
    modified += convert_numeric(frame, year_column, audit, file_key, "Año no numérico; se conserva.")
    for column in ("Age", "Height", "Weight", "age", "height", "weight"):
        modified += convert_numeric(frame, column, audit, file_key, "Medición no numérica; se conserva.")
    medal_column = "Medal" if "Medal" in frame.columns else "medal"
    modified += normalize_medal(frame, medal_column, audit, file_key)
    mapping = {
        "ID": "ID",
        "player_id": "player_id",
        "id": "id",
        "Name": "name",
        "Sex": "sex",
        "Age": "age",
        "Height": "height",
        "Weight": "weight",
        "Team": "equipo",
        "NOC": "noc_codigo",
        "Games": "games_original",
        "Year": "year",
        "Season": "season",
        "City": "city",
        "Sport": "sport",
        "Event": "event",
        "Medal": "medalla",
        "name": "name",
        "sex": "sex",
        "age": "age",
        "height": "height",
        "weight": "weight",
        "team": "equipo",
        "noc": "noc_codigo",
        "games": "games_original",
        "year": "year",
        "season": "season",
        "city": "city",
        "sport": "sport",
        "event": "event",
        "medal": "medalla",
    }
    frame = rename_existing(frame, mapping)
    for diagnostic in ("games_year_diagnostic", "games_season_diagnostic"):
        if diagnostic in frame.columns:
            frame.drop(columns=[diagnostic], inplace=True)
    if source_kind == "fuente4" and "index" in frame.columns:
        frame.drop(columns=["index"], inplace=True)
        audit.rule(
            file_key,
            "index",
            "índice técnico de exportación",
            "Excluir index del archivo intermedio.",
            "El modelo no conserva índices técnicos; se mantiene id como identificador original temporal.",
            0,
            len(frame),
        )
    identifier = {"fuente2": "ID", "fuente3": "player_id", "fuente4": "id"}[source_kind]
    return reorder(
        frame,
        [
            identifier,
            "name",
            "sex",
            "age",
            "height",
            "weight",
            "equipo",
            "noc_codigo",
            "games_original",
            "year",
            "season",
            "city",
            "sport",
            "event",
            "medalla",
        ],
    ), modified


def clean_one(path: Path, audit: Audit) -> tuple[Path, str]:
    file_key = relative_raw(path)
    frame, encoding = read_raw(path)
    rows_in = len(frame)
    cols_in = len(frame.columns)
    nulls_before = null_like_count(frame, file_key)

    if file_key == "fuente1/clean/bios.csv":
        cleaned, modified = clean_bios_clean(frame, audit, file_key)
    elif file_key == "fuente1/clean/bios_locs.csv":
        cleaned, modified = clean_bios_clean(frame, audit, file_key)
    elif file_key == "fuente1/clean/noc_regions.csv":
        cleaned, modified = clean_noc_regions(frame, audit, file_key)
    elif file_key == "fuente1/clean/populations.csv":
        cleaned, modified = clean_populations(frame, audit, file_key)
    elif file_key == "fuente1/clean/results.csv":
        cleaned, modified = clean_clean_results(frame, audit, file_key)
    elif file_key == "fuente1/raw/bios.csv":
        cleaned, modified = clean_raw_bios(frame, audit, file_key)
    elif file_key == "fuente1/raw/results.csv":
        cleaned, modified = clean_raw_results(frame, audit, file_key)
    elif file_key == "fuente2/athlete_events.csv":
        cleaned, modified = clean_participation_source(frame, audit, file_key, "fuente2")
    elif file_key == "fuente3/olympics_dataset.csv":
        cleaned, modified = clean_participation_source(frame, audit, file_key, "fuente3")
    elif file_key == "fuente4/datalab_export.csv":
        cleaned, modified = clean_participation_source(frame, audit, file_key, "fuente4")
    else:
        raise RuntimeError(f"No existe función de limpieza para {file_key}")

    output = INTERMEDIATE_DIR / OUTPUT_NAMES[file_key]
    cleaned.to_csv(output, index=False, encoding="utf-8-sig", lineterminator="\n")
    audit.summary(
        file_key,
        rows_in,
        len(cleaned),
        cols_in,
        len(cleaned.columns),
        nulls_before,
        actual_null_count(cleaned),
        modified,
        audit.processed_by_file[file_key],
        0,
        "",
    )
    return output, encoding


def analyze_duplicates(paths: list[Path], audit: Audit) -> None:
    for path in paths:
        file_key = relative_raw(path)
        frame, _ = read_raw(path)
        duplicate_mask = frame.duplicated(keep="first")
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_count == 0:
            continue
        duplicate_rows = frame[frame.duplicated(keep=False)].head(3).to_dict(orient="records")
        audit.duplicates.append(
            {
                "archivo": f"data/raw/{file_key}",
                "cantidad_duplicados": duplicate_count,
                "columnas_involucradas": json_compact([str(column) for column in frame.columns]),
                "muestra_casos": json_compact(duplicate_rows),
                "accion": "No eliminados; quedan para análisis posterior.",
            }
        )


def missing_matrix() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_key in EXPECTED_FILES:
        rows.append(
            {
                "fuente": source_of(file_key),
                "archivo": f"data/raw/{file_key}",
                "columna": "*",
                "vacio_a_null": "SI",
                "marcadores_semanticos": "NO",
                "no_medal_a_null": "NO",
                "justificacion": "El vacío se interpreta como ausencia después de strip(); los marcadores semánticos no son globales.",
            }
        )
        for column in sorted(MISSING_SEMANTIC_COLUMNS.get(file_key, set())):
            rows.append(
                {
                    "fuente": source_of(file_key),
                    "archivo": f"data/raw/{file_key}",
                    "columna": column,
                    "vacio_a_null": "SI",
                    "marcadores_semanticos": "SI",
                    "no_medal_a_null": "SI" if "medal" in column.casefold() else "NO",
                    "justificacion": "Columna estructural, de medición, identificador o de medalla donde NA/N/A/null/None representa ausencia.",
                }
            )
    return pd.DataFrame(rows)


def write_reports(audit: Audit, hash_validation: pd.DataFrame) -> None:
    CLEANING_DIR.mkdir(parents=True, exist_ok=True)
    rules = pd.DataFrame(
        audit.rules,
        columns=[
            "fuente",
            "archivo",
            "columna",
            "problema_detectado",
            "regla_aplicada",
            "justificacion",
            "valores_afectados",
            "operaciones_procesadas",
        ],
    ).sort_values(["archivo", "columna", "problema_detectado"], kind="stable")
    summaries = pd.DataFrame(
        audit.summaries,
        columns=[
            "fuente",
            "archivo",
            "filas_entrada",
            "filas_salida",
            "columnas_entrada",
            "columnas_salida",
            "nulos_antes",
            "nulos_despues",
            "valores_modificados",
            "operaciones_procesadas",
            "registros_descartados",
            "motivo_descartes",
        ],
    ).sort_values("archivo", kind="stable")
    unresolved_rows = [
        {
            "fuente": source_of(file_key),
            "archivo": f"data/raw/{file_key}",
            "columna": column,
            "valor_original": value,
            "frecuencia": frequency,
            "motivo": reason,
        }
        for (file_key, column, value, reason), frequency in sorted(audit.unresolved_counts.items())
    ]
    unresolved = pd.DataFrame(
        unresolved_rows,
        columns=["fuente", "archivo", "columna", "valor_original", "frecuencia", "motivo"],
    )
    duplicates = pd.DataFrame(
        audit.duplicates,
        columns=["archivo", "cantidad_duplicados", "columnas_involucradas", "muestra_casos", "accion"],
    ).sort_values("archivo", kind="stable")

    for frame, name in (
        (rules, "cleaning_rules.csv"),
        (summaries, "cleaning_summary.csv"),
        (unresolved, "unresolved_values.csv"),
        (duplicates, "duplicate_analysis.csv"),
        (hash_validation, "hash_validation.csv"),
        (missing_matrix(), "missing_value_matrix.csv"),
    ):
        frame.to_csv(CLEANING_DIR / name, index=False, encoding="utf-8-sig", lineterminator="\n")

    write_summary_markdown(audit, summaries, unresolved, duplicates, hash_validation)


def write_summary_markdown(
    audit: Audit,
    summaries: pd.DataFrame,
    unresolved: pd.DataFrame,
    duplicates: pd.DataFrame,
    hash_validation: pd.DataFrame,
) -> None:
    output_files = [OUTPUT_NAMES[key] for key in EXPECTED_FILES]
    total_modified = int(summaries["valores_modificados"].sum())
    total_processed = int(summaries["operaciones_procesadas"].sum())
    total_unresolved = int(unresolved["frecuencia"].sum()) if not unresolved.empty else 0
    lines = [
        "# Cleaning y homologación por fuente — Bloque 3",
        "",
        "Este informe documenta transformaciones reproducibles por fuente. No realiza matching entre atletas, deduplicación global, consolidación final ni carga a SQL Server.",
        "",
        "## Alcance ejecutado",
        "",
        f"- Archivos RAW validados y procesados: **{len(EXPECTED_FILES)}**.",
        f"- Archivos intermedios generados: **{len(output_files)}**.",
        f"- Valores realmente modificados: **{total_modified}**.",
        f"- Operaciones/valores procesados: **{total_processed}**; esta métrica no equivale a modificaciones.",
        f"- Frecuencia acumulada de casos no resueltos: **{total_unresolved}**.",
        f"- Hashes SHA-256 coincidentes: **{int((hash_validation['estado'] == 'MATCH').sum())}/{len(hash_validation)}**.",
        "- Registros descartados: **0**.",
        "- Duplicados exactos: analizados y conservados.",
        "",
        "## Reglas aplicadas",
        "",
        "- `strip()` únicamente sobre valores textuales; se conservaron tildes, Unicode y caracteres no ASCII.",
        "- Marcadores de ausencia normalizados de forma dependiente de la columna. `Nan`, `DNS`, `DNF`, `DQ` y `DSQ` no se convirtieron globalmente a NULL.",
        "- Medallas normalizadas exclusivamente a `Gold`, `Silver`, `Bronze` o NULL.",
        "- Posiciones RAW separadas en `posicion`, `empatado`, `estado_resultado`, `pos_original` y `pos_clasificacion`.",
        "- Fechas limpias normalizadas a ISO; Born/Died RAW se conservaron y se descompusieron solo cuando fue seguro.",
        "- Games separado en `year` y `season`, con `games_original` temporal para trazabilidad.",
        "- Mediciones convertidas a números cuando fue posible; no se eliminaron posibles atípicos.",
        "- NOC descriptivo y código NOC se conservaron en columnas diferenciadas; no se asumió equivalencia con Country Code.",
        "- populations.csv pasó a formato largo sin eliminar agregados.",
        "- La matriz de ausencia por archivo y columna está en `missing_value_matrix.csv`; los campos descriptivos no reciben NA/N/A/null/None de forma global.",
        "",
        "## Archivos intermedios",
        "",
    ]
    lines.extend(f"- `data/intermediate/cleaned/{name}`" for name in output_files)
    lines.extend(
        [
            "",
            "## Matriz de ausencia",
            "",
            "`missing_value_matrix.csv` documenta cuándo el vacío, los marcadores semánticos y `No medal` se convierten a NULL. El vacío se normaliza después de `strip()`; los marcadores semánticos no se aplican a nombres, apodos, títulos, equipos, eventos, afiliaciones ni otros campos descriptivos.",
        ]
    )
    lines.extend(
        [
            "",
            "## Resumen por archivo",
            "",
            "| Archivo | Filas entrada | Filas salida | Columnas entrada | Columnas salida | Nulos antes | Nulos después | Modificados | Procesados | Descartados |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in summaries.iterrows():
        lines.append(
            f"| `{row['archivo']}` | {row['filas_entrada']} | {row['filas_salida']} | {row['columnas_entrada']} | "
            f"{row['columnas_salida']} | {row['nulos_antes']} | {row['nulos_despues']} | {row['valores_modificados']} | "
            f"{row['operaciones_procesadas']} | {row['registros_descartados']} |"
        )

    lines.extend(
        [
            "",
            "## Ejemplos antes/después",
            "",
            "| Archivo/campo | Antes | Después |",
            "|---|---|---|",
            "| `fuente1/raw/results.csv` / `Pos` | `=17` | `pos_original='=17'`, `posicion=17`, `empatado=True`, `estado_resultado=NULL` |",
            "| `fuente1/raw/results.csv` / `Pos` | `DNS` | `pos_original='DNS'`, `posicion=NULL`, `empatado=False`, `estado_resultado='DNS'` |",
            "| `fuente2/athlete_events.csv` / `Medal` | `NA` | `medalla=NULL` |",
            "| `fuente3/olympics_dataset.csv` / `Medal` | `No medal` | `medalla=NULL` |",
            "| `fuente4/datalab_export.csv` / `index` | índice técnico | columna excluida; `id` se conserva |",
            "| `fuente1/clean/populations.csv` / `1960` | formato ancho | fila(s) `country_name`, `country_code`, `year`, `population` |",
            "",
            "## Duplicados",
            "",
            "Los duplicados exactos de `clean/results.csv`, `raw/results.csv` y `athlete_events.csv` están en `duplicate_analysis.csv`. No se eliminó ningún registro; la muestra y las columnas involucradas quedan disponibles para la revisión del Bloque 4.",
            "",
            "## Casos no resueltos",
            "",
            "Los casos no resueltos se conservaron en los intermedios y se detallan en `unresolved_values.csv`. Incluyen posiciones complejas como `AC`, formatos de rondas y valores de Born/Died que no permiten extraer una fecha completa o una interpretación segura.",
            "",
            "## Integridad",
            "",
            "La validación SHA-256 se ejecutó antes y después del proceso. Todos los archivos coinciden con `docs/source_manifest.csv`; ningún archivo de `data/raw` fue escrito.",
            "",
            "## Pendiente para revisión",
            "",
            "- Revisar la semántica de posiciones complejas antes del matching.",
            "- Revisar las inconsistencias Games/year/season registradas, si existen.",
            "- Revisar duplicados exactos antes de cualquier deduplicación global.",
            "- Confirmar la estrategia de matching para NOC descriptivo, NOC codificado y Country Code.",
            "- No iniciar el Bloque 4 hasta aprobar este bloque.",
        ]
    )
    (CLEANING_DIR / "cleaning_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    paths = raw_paths()
    INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    CLEANING_DIR.mkdir(parents=True, exist_ok=True)

    before_hashes = validate_raw_hashes(paths)
    audit = Audit()
    analyze_duplicates(paths, audit)
    encodings: dict[str, str] = {}
    generated: list[Path] = []
    for path in paths:
        output, encoding = clean_one(path, audit)
        generated.append(output)
        encodings[relative_raw(path)] = encoding

    after_hashes = validate_raw_hashes(paths)
    if not (before_hashes["sha256_actual"] == after_hashes["sha256_actual"]).all():
        raise RuntimeError("Los hashes cambiaron durante la limpieza; proceso detenido.")

    write_reports(audit, after_hashes)
    expected_reports = [
        CLEANING_DIR / "cleaning_rules.csv",
        CLEANING_DIR / "cleaning_summary.csv",
        CLEANING_DIR / "unresolved_values.csv",
        CLEANING_DIR / "duplicate_analysis.csv",
        CLEANING_DIR / "hash_validation.csv",
        CLEANING_DIR / "missing_value_matrix.csv",
        CLEANING_DIR / "cleaning_summary.md",
    ]
    missing = [str(path) for path in expected_reports + generated if not path.exists()]
    if missing:
        raise RuntimeError(f"Faltan salidas esperadas: {missing}")

    unresolved_rows = sum(audit.unresolved_counts.values())
    print(f"Archivos RAW validados: {len(paths)}")
    print(f"Archivos intermedios generados: {len(generated)}")
    print(f"Reglas registradas: {len(audit.rules)}")
    print(f"Valores realmente modificados: {sum(row['valores_modificados'] for row in audit.summaries)}")
    print(f"Operaciones/valores procesados: {sum(row['operaciones_procesadas'] for row in audit.summaries)}")
    print(f"Casos no resueltos acumulados: {unresolved_rows}")
    print(f"Duplicados analizados: {len(audit.duplicates)} archivos")
    print(f"SHA-256 coincidentes: {(after_hashes['estado'] == 'MATCH').sum()}/{len(after_hashes)}")
    print("RAW intacto: SI")
    print(f"Reportes generados en: {CLEANING_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
