"""Apply three narrowly scoped, source-reviewed participation corrections.

Changes only participation IDs 459825, 48190 and 48192 in processed data.
Creates an exact pre-change backup and a per-cell audit. All other bytes/rows in
the participation CSV and every other project file are left unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "processed" / "participacion.csv"
BACKUP_PATH = ROOT / "data" / "backup_before_olympedia_exact_corrections" / "participacion.csv"
REPORT_DIR = ROOT / "docs" / "quality"
AUDIT_CSV = REPORT_DIR / "participation_olympedia_corrections.csv"
AUDIT_MD = REPORT_DIR / "participation_olympedia_corrections.md"

IOC_FOOTBALL = (
    "https://library.olympics.com/digitalCollection/"
    "DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117"
    "&skipCopyright=true&skipWatermark=true"
)
IOC_LA1932 = (
    "https://library.olympics.com/digitalCollection/"
    "DigitalCollectionAttachmentDownloadHandler.ashx?documentId=2875488&parentDocumentId=2875401"
    "&skipCopyright=true&skipWatermark=true"
)
OLYMPEDIA_ANTONIA = "https://www.olympedia.org/athletes/920763"

# (participation id, athlete id, edition id, event id, field, previous, corrected)
CHANGES = (
    ("459825", "167002", "12", "2328", "edad", "27", "29"),
    ("48190", "25450", "30", "303", "posicion", "9", "10"),
    ("48190", "25450", "30", "303", "empatado", "True", "False"),
    ("48192", "25451", "36", "303", "posicion", "13", "16"),
    ("48192", "25451", "36", "303", "empatado", "True", "False"),
)
EXPECTED_FIELDS = [
    "id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc",
    "id_pais_nacionalidad", "equipo", "nombre_competencia", "edad",
    "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado",
    "estado_resultado", "medalla",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_rows(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return list(reader.fieldnames or []), list(reader)


def expected_values(after: bool) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for participation_id, athlete_id, edition_id, event_id, field, before, after_value in CHANGES:
        expected = after_value if after else before
        result.setdefault(participation_id, {}).update({
            "id_atleta": athlete_id, "id_edicion": edition_id, "id_evento": event_id,
            field: expected,
        })
    return result


def verify_rows(rows: list[dict[str, str]], after: bool) -> None:
    by_id = {row["id_participacion"]: row for row in rows}
    for participation_id, expected in expected_values(after).items():
        if participation_id not in by_id:
            raise RuntimeError(f"Falta id_participacion={participation_id}.")
        for field, value in expected.items():
            if by_id[participation_id].get(field, "") != value:
                state = "final" if after else "previo"
                raise RuntimeError(
                    f"Valor {state} inesperado en {participation_id}.{field}: "
                    f"{by_id[participation_id].get(field)!r}; esperado {value!r}."
                )


def write_audit(before_hash: str, after_hash: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    audit_rows = []
    for participation_id, athlete_id, edition_id, event_id, field, old, new in CHANGES:
        if participation_id == "459825":
            athlete = "Antonia Matos"
            reason = "Olympedia registra nacimiento 21-11-1902; tenía 29 años durante Los Ángeles 1932."
            source = f"{OLYMPEDIA_ANTONIA}; {IOC_LA1932}"
        else:
            athlete = "Luis Villavicencio" if athlete_id == "25450" else "Allan Wellman"
            year_rank = "1976: puesto 10" if athlete_id == "25450" else "1988: puesto 16"
            reason = f"El informe de fútbol del IOC registra a Guatemala en {year_rank}; puesto final no empatado."
            source = IOC_FOOTBALL
        audit_rows.append({
            "id_participacion": participation_id, "id_atleta": athlete_id,
            "id_edicion": edition_id, "id_evento": event_id, "atleta": athlete,
            "columna": field, "valor_anterior": old, "valor_corregido": new,
            "justificacion": reason, "referencia": source,
            "sha256_participacion_antes": before_hash,
            "sha256_participacion_despues": after_hash,
        })

    with AUDIT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    AUDIT_MD.write_text(
        "# Correcciones puntuales contrastadas con fuentes olímpicas\n\n"
        f"Ejecución: `{timestamp}`. Se corrigieron cinco celdas en tres participaciones; "
        "no se modificaron otras filas ni los demás archivos procesados.\n\n"
        "- **Antonia Matos, Los Ángeles 1932:** edad `27 → 29`. Olympedia registra "
        "nacimiento el 21 de noviembre de 1902; durante los Juegos de julio-agosto de "
        f"1932 tenía 29 años ([perfil]({OLYMPEDIA_ANTONIA})). El informe oficial del "
        f"IOC confirma su mención en la competición artística ([informe 1932]({IOC_LA1932})).\n"
        "- **Luis Villavicencio, Montreal 1976:** puesto `9 → 10`; empatado `True → False`.\n"
        "- **Allan Wellman, Seúl 1988:** puesto `13 → 16`; empatado `True → False`.\n\n"
        f"Los puestos guatemaltecos se contrastaron con el [informe de fútbol del IOC]({IOC_FOOTBALL}). "
        "La modificación se limita a las tres participaciones autorizadas; no se propagó "
        "a los demás integrantes de cada selección. Por eso, otros registros del mismo "
        "evento pueden conservar el puesto previo y requerir una revisión de equipo aparte.\n\n"
        f"SHA-256 antes: `{before_hash}`  \nSHA-256 después: `{after_hash}`\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplica las cinco celdas; sin esto solo valida.")
    args = parser.parse_args()

    original = CSV_PATH.read_bytes()
    fields, rows = read_rows(original)
    if fields != EXPECTED_FIELDS:
        raise RuntimeError("El esquema de columnas no coincide con el revisado.")
    if not original.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("Se esperaba UTF-8-SIG/BOM.")
    by_id = {row["id_participacion"]: row for row in rows}
    already_corrected = all(
        by_id[participation_id].get(field, "") == new
        for participation_id, _, _, _, field, _, new in CHANGES
    )
    before_state = all(
        by_id[participation_id].get(field, "") == old
        for participation_id, _, _, _, field, old, _ in CHANGES
    )

    if already_corrected:
        verify_rows(rows, after=True)
        if not BACKUP_PATH.exists():
            raise RuntimeError("Los valores ya están corregidos, pero falta el respaldo previo.")
        before_hash = digest(BACKUP_PATH.read_bytes())
        write_audit(before_hash, digest(original))
        print(f"ALREADY_APPLIED; cinco celdas correctas; SHA-256={digest(original)}")
        return
    if before_state:
        verify_rows(rows, after=False)
    else:
        raise RuntimeError("Estado parcial o inesperado; no se modificó el archivo.")

    print("DRY-RUN: tres participaciones y cinco valores contrastados; no se cambió el archivo.")
    if not args.apply:
        return

    physical_lines = original.splitlines(keepends=True)
    if any(not line.endswith(b"\r\n") for line in physical_lines):
        raise RuntimeError("Se esperaba CRLF en cada fila; se aborta para preservar formato.")
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP_PATH.exists():
        if BACKUP_PATH.read_bytes() != original:
            raise RuntimeError("El respaldo ya existe y difiere; no se sobrescribirá.")
    else:
        shutil.copy2(CSV_PATH, BACKUP_PATH)

    changed_ids = set()
    changed_cells = 0
    output_lines = [physical_lines[0]]
    wanted: dict[str, dict[str, tuple[str, str]]] = {}
    for participation_id, _, _, _, field, old, new in CHANGES:
        wanted.setdefault(participation_id, {})[field] = (old, new)
    for line in physical_lines[1:]:
        parts = line.rstrip(b"\r\n").decode("utf-8").split(",")
        participation_id = parts[0]
        if participation_id in wanted:
            if b'"' in line or len(parts) != len(EXPECTED_FIELDS):
                raise RuntimeError(f"Formato inesperado en la fila {participation_id}; no se escribió.")
            for field, (old, new) in wanted[participation_id].items():
                field_index = EXPECTED_FIELDS.index(field)
                if parts[field_index] != old:
                    raise RuntimeError(f"Valor inesperado en {participation_id}.{field}; no se escribió.")
                parts[field_index] = new
                changed_cells += 1
            changed_ids.add(participation_id)
            output_lines.append(",".join(parts).encode("utf-8") + b"\r\n")
        else:
            output_lines.append(line)

    expected_changed_ids = set(wanted)
    if changed_ids != expected_changed_ids:
        raise RuntimeError(f"No se cambiaron exactamente los tres IDs esperados: {changed_ids}")
    if changed_cells != len(CHANGES):
        raise RuntimeError(f"Se modificaron {changed_cells} celdas, se esperaban {len(CHANGES)}.")
    updated = b"".join(output_lines)
    _, updated_rows = read_rows(updated)
    verify_rows(updated_rows, after=True)
    if len(updated_rows) != len(rows):
        raise RuntimeError("Cambió la cantidad de filas; se aborta.")

    old_lines = original.splitlines(keepends=True)
    new_lines = updated.splitlines(keepends=True)
    line_changes = {
        old.split(b",", 1)[0].decode("ascii")
        for old, new in zip(old_lines, new_lines)
        if old != new
    }
    if line_changes != expected_changed_ids:
        raise RuntimeError(f"Cambió una fila fuera del alcance: {line_changes}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".participacion-correction-", suffix=".tmp",
            dir=CSV_PATH.parent, delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, CSV_PATH)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    after = CSV_PATH.read_bytes()
    write_audit(digest(original), digest(after))
    print(f"APPLIED; tres participaciones, cinco celdas; SHA-256={digest(after)}")


if __name__ == "__main__":
    main()
