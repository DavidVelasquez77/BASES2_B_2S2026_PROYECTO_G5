"""Aplica la corrección comprobada del matching GUA 2020.

La fuente de decisión es docs/quality/gua_2020_roster_review.csv, generado
contra la delegación publicada por Olympedia. El script es controlado,
reproducible e idempotente: exige el estado previo esperado y aborta si ya se
aplicó o si el reporte no contiene exactamente las 24 filas problemáticas.

No modifica data/raw, data/intermediate, SQL Server ni Stored Procedures.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
BACKUP = ROOT / "data" / "backup_before_gua_2020_fix"
PREVIEW = ROOT / "data" / "preview_gua_2020_fix"
QUALITY = ROOT / "docs" / "quality"
REVIEW = QUALITY / "gua_2020_roster_review.csv"
MANIFEST_BEFORE = QUALITY / "gua_2020_fix_manifest_before.csv"
MANIFEST_AFTER = QUALITY / "gua_2020_fix_manifest_after.csv"
REPORT = QUALITY / "gua_2020_fix_report.md"

FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]
EXPECTED_COUNTS = {
    "atleta.csv": 336418,
    "evento.csv": 2986,
    "participacion.csv": 712658,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest(directory: Path) -> list[dict[str, str]]:
    return [
        {"archivo": name, "filas": str(count_rows(directory / name)), "sha256": sha256(directory / name)}
        for name in FILES
    ]


def main() -> None:
    if not REVIEW.exists():
        raise RuntimeError(f"Falta el reporte de revisión: {REVIEW}")
    if BACKUP.exists():
        raise RuntimeError(f"El respaldo ya existe; no se sobrescribe: {BACKUP}")

    before_counts = {name: count_rows(PROCESSED / name) for name in FILES}
    for name, expected in EXPECTED_COUNTS.items():
        if before_counts[name] != expected:
            raise RuntimeError(f"Estado previo inesperado: {name}={before_counts[name]} != {expected}")

    review_rows = read_csv(REVIEW)
    remove_ids = {
        row["id_participacion"]
        for row in review_rows
        if row.get("clasificacion") in {"NOT_IN_2020_GUA_ROSTER", "DUPLICATE_ROW_FOR_ROSTER_ATHLETE"}
    }
    if len(remove_ids) != 24:
        raise RuntimeError(f"Se esperaban exactamente 24 filas a retirar; se encontraron {len(remove_ids)}")
    if sum(row.get("clasificacion") == "NOT_IN_2020_GUA_ROSTER" for row in review_rows) != 23:
        raise RuntimeError("El reporte no contiene exactamente 23 asociaciones GUA fuera del roster")
    if sum(row.get("clasificacion") == "DUPLICATE_ROW_FOR_ROSTER_ATHLETE" for row in review_rows) != 1:
        raise RuntimeError("El reporte no contiene exactamente 1 fila duplicada de roster")

    BACKUP.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(PROCESSED / name, BACKUP / name)
    before_manifest = manifest(BACKUP)
    QUALITY.mkdir(parents=True, exist_ok=True)
    write_csv(MANIFEST_BEFORE, before_manifest, ["archivo", "filas", "sha256"])

    original = read_csv(PROCESSED / "participacion.csv")
    fields = list(original[0])
    kept = [row for row in original if row["id_participacion"] not in remove_ids]
    if len(kept) != len(original) - 24:
        raise RuntimeError("La eliminación controlada no coincide con las 24 filas aprobadas")

    PREVIEW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        if name == "participacion.csv":
            write_csv(PREVIEW / name, kept, fields)
        else:
            shutil.copy2(PROCESSED / name, PREVIEW / name)

    shutil.copy2(PREVIEW / "participacion.csv", PROCESSED / "participacion.csv")
    after_manifest = manifest(PROCESSED)
    write_csv(MANIFEST_AFTER, after_manifest, ["archivo", "filas", "sha256"])

    changed = [
        row["archivo"] for row in after_manifest
        if row["sha256"] != next(item["sha256"] for item in before_manifest if item["archivo"] == row["archivo"])
    ]
    if changed != ["participacion.csv"]:
        for name in FILES:
            shutil.copy2(BACKUP / name, PROCESSED / name)
        raise RuntimeError(f"Se modificaron archivos inesperados: {changed}")

    after_counts = {name: count_rows(PROCESSED / name) for name in FILES}
    if after_counts["participacion.csv"] != 712634:
        for name in FILES:
            shutil.copy2(BACKUP / name, PROCESSED / name)
        raise RuntimeError(f"Conteo final inesperado: participacion={after_counts['participacion.csv']}")

    REPORT.write_text(
        "\n".join([
            "# Corrección GUA 2020",
            "",
            "Estado: **APPLIED_TO_PROCESSED**",
            "",
            "Se retiraron únicamente 24 filas de `data/processed/participacion.csv`:",
            "- 23 asociaciones GUA 2020 cuyo atleta no pertenece al roster publicado.",
            "- 1 fila duplicada de Yulisa López.",
            "",
            "No se modificaron `data/raw`, `data/intermediate`, los otros nueve CSV, SQL Server ni Stored Procedures.",
            "",
            f"Participación antes: **{before_counts['participacion.csv']}**.",
            f"Participación después: **{after_counts['participacion.csv']}**.",
            "",
            "El resto de discrepancias GUA no se fusionó automáticamente: los 263 nombres históricos requieren un mapa biográfico explícito y la tabla recibida contiene inconsistencias de conteo.",
            "",
            "Archivos de control:",
            f"- `{MANIFEST_BEFORE.relative_to(ROOT)}`",
            f"- `{MANIFEST_AFTER.relative_to(ROOT)}`",
            f"- `{REVIEW.relative_to(ROOT)}`",
            f"- `{BACKUP.relative_to(ROOT)}`",
            f"- `{PREVIEW.relative_to(ROOT)}`",
        ]) + "\n",
        encoding="utf-8",
    )
    print("GUA_2020_FIX_APPLIED")
    print("removed_rows=24")
    print(f"participacion_before={before_counts['participacion.csv']}")
    print(f"participacion_after={after_counts['participacion.csv']}")
    print("changed=participacion.csv")
    print(f"backup={BACKUP}")


if __name__ == "__main__":
    main()
