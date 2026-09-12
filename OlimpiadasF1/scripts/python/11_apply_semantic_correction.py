"""Aplica la corrección semántica controlada después de la revisión del blocker.

El script genera primero un preview reproducible en data/semantic_preview.
Solo si el preview pasa las validaciones permitidas reemplaza atleta.csv,
evento.csv y participacion.csv. Los otros siete CSV deben permanecer byte a
byte idénticos. Ante cualquier error posterior al reemplazo restaura el backup.
No ejecuta SQL Server.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREVIEW = ROOT / "data" / "semantic_preview"
BACKUP = ROOT / "data" / "backup_before_semantic_apply"
QUALITY = ROOT / "docs" / "quality"

FILES = [
    "atleta.csv", "deporte.csv", "disciplina.csv", "edicion_olimpica.csv",
    "entidad_geografica.csv", "evento.csv", "noc.csv", "participacion.csv",
    "poblacion.csv", "sede.csv",
]
APPLIED = {"atleta.csv", "evento.csv", "participacion.csv"}
FIELDS_TO_PRESERVE = ("edad", "posicion", "empatado", "estado_resultado", "medalla", "equipo", "nombre_competencia")
HISTORICAL = {
    ("113352", "14"): ("1", "Gold", ""),       # Jared Tallent / AUS
    ("114129", "43"): ("2", "Silver", ""),     # Si Tianfeng / CHN
    ("86364", "99"): ("3", "Bronze", ""),      # Robbie Heffernan / IRL
    ("114152", "177"): ("", "", "DQ"),         # Sergey Kirdyapkin / RUS
}


def load_dryrun_module():
    path = ROOT / "scripts" / "python" / "10_controlled_semantic_correction_dryrun.py"
    spec = importlib.util.spec_from_file_location("semantic_dryrun", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se pudo cargar la definición aprobada de aliases")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DRY = load_dryrun_module()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def int_value(value: object) -> int:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return 10**18


def normalize_sex(value: str) -> str:
    return {"M": "Male", "Male": "Male", "F": "Female", "Female": "Female"}.get(clean(value), clean(value))


def normalize_full_name(value: str) -> str:
    return " ".join(clean(value).replace("•", " ").split())


TEAM_LABELS = {
    "china": "CHN", "peoples republic of china": "CHN", "people s republic of china": "CHN",
    "germany": "GER", "unified team of germany": "GER",
    "republic of korea": "KOR", "south korea": "KOR",
    "democratic peoples republic of korea": "PRK", "democratic people s republic of korea": "PRK", "north korea": "PRK",
    "russia": "RUS", "russian federation": "RUS",
    "chinese taipei": "TPE", "taiwan": "TPE",
    "united states": "USA", "usa": "USA",
    "great britain": "GBR", "united kingdom": "GBR",
}


def team_comparison_key(value: str) -> str:
    text = clean(value).lower().replace("�", "a")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def equivalent_team_values(values: list[str]) -> bool:
    keys = {team_comparison_key(value) for value in values}
    if len(keys) <= 1:
        return True
    labels = {TEAM_LABELS.get(key, key) for key in keys}
    if len(labels) == 1:
        return True
    # One source may have a historical country label while the other has the
    # same club/team label with only a transcription accent difference.
    return any(key.replace("vorwrts", "vorwarts") == other.replace("vorwrts", "vorwarts") for key in keys for other in keys if key != other)


def merge_value(rows: list[dict[str, str]], field: str) -> str:
    for row in sorted(rows, key=lambda item: int_value(item.get("id_participacion", ""))):
        if clean(row.get(field)):
            return row[field]
    return ""


def canonical_aliases() -> list[dict[str, str]]:
    aliases = DRY.event_alias_definitions()
    if len(aliases) != 21:
        raise RuntimeError(f"Se esperaban 21 aliases aprobados; se encontraron {len(aliases)}")
    return aliases


def state_hashes(directory: Path) -> dict[str, str]:
    return {name: sha256(directory / name) for name in FILES}


def row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def historical_update(row: dict[str, str], original_event: str, edition: dict[str, str]) -> bool:
    if original_event not in {"1022", "2231"} or edition.get("anio") != "2012":
        return False
    key = (row["id_atleta"], row["id_noc"])
    if key not in HISTORICAL:
        return False
    position, medal, result = HISTORICAL[key]
    row["posicion"] = position
    row["medalla"] = medal
    row["estado_resultado"] = result
    return True


def build_preview() -> tuple[dict[str, list[dict[str, str]]], dict[str, object]]:
    athletes = read_rows(PROCESSED / "atleta.csv")
    events = read_rows(PROCESSED / "evento.csv")
    parts = read_rows(PROCESSED / "participacion.csv")
    editions = {r["id_edicion"]: r for r in read_rows(PROCESSED / "edicion_olimpica.csv")}
    event_by_id = {r["id_evento"]: r for r in events}
    part_by_id = {r["id_participacion"]: r for r in parts}

    normalized_athletes: list[dict[str, str]] = []
    sex_rows = 0
    bullet_rows = 0
    for original in athletes:
        row = original.copy()
        if clean(row.get("sexo")) in {"M", "F"}:
            sex_rows += 1
        if row.get("nombre_completo", "") != normalize_full_name(row.get("nombre_completo", "")):
            bullet_rows += 1
        row["sexo"] = normalize_sex(row.get("sexo", ""))
        row["nombre_completo"] = normalize_full_name(row.get("nombre_completo", ""))
        normalized_athletes.append(row)

    by_id = {r["id_atleta"]: r for r in normalized_athletes}
    source_merge = by_id.get("147606")
    target_merge = by_id.get("121191")
    if source_merge is None or target_merge is None:
        raise RuntimeError("No se encontró el merge aprobado 147606 -> 121191")
    for field, value in source_merge.items():
        if field != "id_atleta" and not clean(target_merge.get(field)) and clean(value):
            target_merge[field] = value
    preview_athletes = [r for r in normalized_athletes if r["id_atleta"] != "147606"]

    aliases = canonical_aliases()
    alias = {r["origen"]: r["destino_canonico"] for r in aliases}
    preview_events = [r.copy() for r in events if r["id_evento"] not in alias]

    reassigned: list[dict[str, str]] = []
    historical_rows = []
    for original in parts:
        row = original.copy()
        original_athlete = row["id_atleta"]
        original_event = row["id_evento"]
        if original_athlete == "147606":
            row["id_atleta"] = "121191"
        elif original_athlete in {"223817", "223818", "223819"}:
            row["id_atleta"] = "17"
        elif original_athlete == "192591" and editions[row["id_edicion"]].get("anio") == "2012" and row["id_noc"] == "87" and original_event == "2218":
            row["id_atleta"] = "121191"
        elif original_athlete.isdigit() and 187982 <= int(original_athlete) <= 188004:
            event_name = event_by_id.get(original_event, {}).get("nombre", "")
            if editions[row["id_edicion"]].get("anio") in {"1972", "1976", "1980"} and event_name.startswith("Gymnastics Men's"):
                row["id_atleta"] = "31000"
        row["id_evento"] = alias.get(original_event, original_event)
        if historical_update(row, original_event, editions[row["id_edicion"]]):
            historical_rows.append({"original": original, "final": row.copy()})
        reassigned.append(row)

    safe_event_scope = set(alias) | set(alias.values())
    targeted_ids = {"121191", "17", "31000", "93113", "119877"}
    groups: defaultdict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in reassigned:
        original = part_by_id[row["id_participacion"]]
        event_touched = original["id_evento"] in safe_event_scope
        identity_touched = row["id_atleta"] != original["id_atleta"]
        if event_touched or identity_touched or row["id_atleta"] in targeted_ids:
            key = (row["id_atleta"], row["id_edicion"], row["id_evento"], row["id_noc"], row["medalla"])
            groups[key].append(row)

    dropped: set[str] = set()
    updates: dict[str, dict[str, str]] = {}
    incompatible: list[dict[str, str]] = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        explicit_historical = key[1] == "50" and key[2] == "1022" and key[0] in {"86364", "113352", "114129", "114152"}
        for field in FIELDS_TO_PRESERVE:
            values = sorted({clean(r.get(field)) for r in group if clean(r.get(field))})
            if field == "equipo" and equivalent_team_values(values):
                continue
            if len(values) > 1 and not explicit_historical:
                incompatible.append({"clave": "|".join(key), "campo": field, "valores": " || ".join(values)})
        ordered = sorted(group, key=lambda item: int_value(item["id_participacion"]))
        winner = ordered[0].copy()
        for field in winner:
            if not clean(winner.get(field)):
                winner[field] = merge_value(ordered, field)
        updates[winner["id_participacion"]] = winner
        for duplicate in ordered[1:]:
            dropped.add(duplicate["id_participacion"])

    if incompatible:
        sample = "; ".join(f"{r['clave']} {r['campo']}={r['valores']}" for r in incompatible)
        raise RuntimeError(f"ABORT_CONFLICT: valores no vacíos incompatibles: {sample}")

    preview_parts: list[dict[str, str]] = []
    for row in reassigned:
        updated = updates.get(row["id_participacion"], row)
        if updated["id_participacion"] not in dropped:
            preview_parts.append(updated)

    historical_report = []
    for item in historical_rows:
        original = item["original"]
        final = item["final"]
        athlete = by_id[final["id_atleta"]]
        historical_report.append({
            "atleta": athlete.get("nombre", ""),
            "edicion": "2012 Summer",
            "evento_original": original["id_evento"],
            "evento_canonico": final["id_evento"],
            "posicion_original": original.get("posicion", ""),
            "medalla_original": original.get("medalla", ""),
            "posicion_final": final.get("posicion", ""),
            "medalla_final": final.get("medalla", ""),
            "estado_final": final.get("estado_resultado", ""),
            "razon": "Resultado vigente posterior a la descalificación de Sergey Kirdyapkin; se conserva una sola participación lógica y la trazabilidad de la fuente.",
            "referencia": "World Athletics London 2012 results; Australian Olympic Committee for Tallent gold.",
        })

    fields = {
        "atleta.csv": list(athletes[0]),
        "evento.csv": list(events[0]),
        "participacion.csv": list(parts[0]),
    }
    data = {"atleta.csv": preview_athletes, "evento.csv": preview_events, "participacion.csv": preview_parts}
    metrics = {
        "sexo_normalizado": sex_rows,
        "nombre_completo_bullet_normalizado": bullet_rows,
        "athlete_full_merge": "147606->121191",
        "event_aliases": len(aliases),
        "participation_merges": len(dropped),
        "historical_source_rows": len(historical_rows),
        "historical_logical_cases": 4,
        "historical_report": historical_report,
    }
    return {name: (data[name], fields[name]) for name in data}, metrics


def main() -> None:
    before_hashes = state_hashes(PROCESSED)
    before_counts = {name: row_count(PROCESSED / name) for name in FILES}
    expected_before = {"atleta.csv": 336419, "evento.csv": 3007, "participacion.csv": 733414}
    for name, expected in expected_before.items():
        if before_counts[name] != expected:
            raise RuntimeError(f"ABORT_STATE_CHANGED: {name}={before_counts[name]} != {expected}")

    backup_files = sorted(p.name for p in BACKUP.glob("*.csv"))
    if backup_files != sorted(FILES):
        raise RuntimeError("ABORT: backup_before_semantic_apply no contiene exactamente los 10 CSV")
    if state_hashes(BACKUP) != before_hashes:
        raise RuntimeError("ABORT: hashes del backup no coinciden con data/processed")

    data, metrics = build_preview()
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name, (rows, fields) in data.items():
        write_rows(PREVIEW / name, rows, fields)

    preview_counts = {name: row_count(PREVIEW / name) for name in APPLIED}
    expected_preview = {"atleta.csv": 336418, "evento.csv": 2986, "participacion.csv": 713678}
    if preview_counts != expected_preview:
        raise RuntimeError(f"ABORT_PREVIEW_COUNTS: {preview_counts} != {expected_preview}")

    write_rows(QUALITY / "semantic_apply_historical_result_resolution.csv", metrics["historical_report"], [
        "atleta", "edicion", "evento_original", "evento_canonico", "posicion_original", "medalla_original",
        "posicion_final", "medalla_final", "estado_final", "razon", "referencia",
    ])
    write_rows(QUALITY / "semantic_apply_preview_validation.csv", [
        {"validacion": "sexo_normalizado", "esperado": "190919", "actual": str(metrics["sexo_normalizado"]), "estado": "PASS" if metrics["sexo_normalizado"] == 190919 else "FAIL"},
        {"validacion": "nombre_completo_bullet_normalizado", "esperado": "145252", "actual": str(metrics["nombre_completo_bullet_normalizado"]), "estado": "PASS" if metrics["nombre_completo_bullet_normalizado"] == 145252 else "FAIL"},
        {"validacion": "athlete_full_merge", "esperado": "147606->121191", "actual": metrics["athlete_full_merge"], "estado": "PASS"},
        {"validacion": "event_aliases", "esperado": "21", "actual": str(metrics["event_aliases"]), "estado": "PASS" if metrics["event_aliases"] == 21 else "FAIL"},
        {"validacion": "historical_logical_cases", "esperado": "4", "actual": str(metrics["historical_logical_cases"]), "estado": "PASS"},
        {"validacion": "participation_merges", "esperado": "reproducible", "actual": str(metrics["participation_merges"]), "estado": "PASS"},
    ], ["validacion", "esperado", "actual", "estado"])

    applied = False
    try:
        for name in APPLIED:
            shutil.copy2(PREVIEW / name, PROCESSED / name)
        applied = True
        after_hashes = state_hashes(PROCESSED)
        after_counts = {name: row_count(PROCESSED / name) for name in FILES}
        manifest = []
        for name in FILES:
            modified = before_hashes[name] != after_hashes[name]
            if (name in APPLIED) != modified:
                raise RuntimeError(f"APPLY_INTEGRITY: modificación inesperada en {name}")
            manifest.append({"archivo": name, "filas_antes": before_counts[name], "filas_despues": after_counts[name], "sha_antes": before_hashes[name], "sha_despues": after_hashes[name], "modificado": "SI" if modified else "NO"})
        write_rows(QUALITY / "semantic_apply_manifest.csv", manifest, ["archivo", "filas_antes", "filas_despues", "sha_antes", "sha_despues", "modificado"])
    except Exception:
        if applied:
            for name in FILES:
                shutil.copy2(BACKUP / name, PROCESSED / name)
        raise

    print("SEMANTIC_APPLY_CSV_SUCCESS")
    print(f"preview_counts={preview_counts}")
    print(f"participation_merges={metrics['participation_merges']}")
    print(f"historical_rows={metrics['historical_source_rows']}")
    print("modified=atleta.csv,event.csv,participacion.csv")
    print("intact=deporte.csv,disciplina.csv,edicion_olimpica.csv,entidad_geografica.csv,noc.csv,poblacion.csv,sede.csv")


if __name__ == "__main__":
    main()
