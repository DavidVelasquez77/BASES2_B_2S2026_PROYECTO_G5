"""Resolve three reviewed duplicate participation rows in processed data.

Only the sparse duplicate row is removed from each reviewed athlete/edition/event
group. The richer row and all its values are preserved. The script keeps a byte-
for-byte backup and emits an audit CSV and Markdown note. It does not alter RAW,
intermediate data, SQL Server, or any other processed CSV.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARTICIPATION = ROOT / "data" / "processed" / "participacion.csv"
BACKUP = ROOT / "data" / "backup_before_exact_participation_dedup" / "participacion.csv"
REPORT_DIR = ROOT / "docs" / "quality"
AUDIT_CSV = REPORT_DIR / "participation_duplicate_resolution.csv"
AUDIT_MD = REPORT_DIR / "participation_duplicate_resolution.md"

CASES = (
    {
        "athlete_id": "167002", "edition_id": "12", "event_id": "2328",
        "keep_id": "459825", "remove_id": "700934",
        "athlete": "Antonia Matos (Matos Aycinena-, -de Massot)",
        "edition": "1932 Summer", "event": "Art Competitions Mixed Painting, Paintings",
        "expected_keep": {"id_noc": "87", "equipo": "Guatemala", "edad": "27"},
        "decision_note": (
            "La fila conservada mantiene edad=27 según la fuente de datos; la fila "
            "escasa no agrega valores distintos. El informe IOC de 1932 confirma a "
            "Antonia Matos en la competición artística con mención honorífica. "
            "Olympedia registra nacimiento el 21-11-1902, lo que implicaría 29 años "
            "durante los Juegos; por tanto, los 27 años de la fuente de datos son un "
            "conflicto no resuelto y no se presentan como edad verificada."
        ),
        "references": "IOC report: https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=2875488&parentDocumentId=2875401&skipCopyright=true&skipWatermark=true; Olympedia: https://www.olympedia.org/athletes/920763",
    },
    {
        "athlete_id": "25450", "edition_id": "30", "event_id": "303",
        "keep_id": "48190", "remove_id": "782134",
        "athlete": "Luis Villavicencio", "edition": "1976 Summer",
        "event": "Football, Men (Olympic)",
        "expected_keep": {"id_noc": "87", "equipo": "Guatemala", "posicion": "9", "empatado": "True"},
        "decision_note": (
            "La fila escasa no agrega valores distintos. Se conserva el puesto 9 que "
            "trae la fuente, pero el informe de fútbol del IOC ubica a Guatemala en "
            "el puesto 10; la discrepancia afecta el resultado del equipo y debe "
            "revisarse para toda la plantilla, no solo para este atleta."
        ),
        "references": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117&skipCopyright=true&skipWatermark=true",
    },
    {
        "athlete_id": "25451", "edition_id": "36", "event_id": "303",
        "keep_id": "48192", "remove_id": "786563",
        "athlete": "Allan Wellman", "edition": "1988 Summer",
        "event": "Football, Men (Olympic)",
        "expected_keep": {
            "id_noc": "87", "equipo": "Guatemala", "edad": "34", "altura_cm_registrada": "167",
            "peso_kg_registrado": "70", "posicion": "13", "empatado": "True",
        },
        "decision_note": (
            "La fila escasa no agrega valores distintos. Se conserva el puesto 13 que "
            "trae la fuente, pero el informe de fútbol del IOC ubica a Guatemala en "
            "el puesto 16; la discrepancia afecta el resultado del equipo y debe "
            "revisarse para toda la plantilla, no solo para este atleta."
        ),
        "references": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117&skipCopyright=true&skipWatermark=true",
    },
)

KEY_FIELDS = ("id_atleta", "id_edicion", "id_evento")
SHARED_ID_FIELDS = (*KEY_FIELDS, "id_noc", "id_pais_nacionalidad", "equipo")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_bytes(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig")
    records = list(csv.DictReader(io.StringIO(text, newline="")))
    if not records:
        raise RuntimeError("participacion.csv no contiene registros.")
    return list(records[0]), records


def duplicate_groups(rows: list[dict[str, str]]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        key = tuple(row[field] for field in KEY_FIELDS)
        groups.setdefault(key, []).append(row)
    return {key: group for key, group in groups.items() if len(group) > 1}


def validate_original(rows: list[dict[str, str]]) -> None:
    expected = {
        (case["athlete_id"], case["edition_id"], case["event_id"]): case
        for case in CASES
    }
    duplicates = duplicate_groups(rows)
    if set(duplicates) != set(expected):
        raise RuntimeError(
            f"Las claves duplicadas actuales no son exactamente las revisadas: "
            f"observadas={sorted(duplicates)}, esperadas={sorted(expected)}"
        )

    by_id = {row["id_participacion"]: row for row in rows}
    for key, case in expected.items():
        group = duplicates[key]
        if {row["id_participacion"] for row in group} != {case["keep_id"], case["remove_id"]}:
            raise RuntimeError(f"Cambió el conjunto de IDs del caso {key}.")
        keep = by_id[case["keep_id"]]
        remove = by_id[case["remove_id"]]
        for field, value in case["expected_keep"].items():
            if keep.get(field, "") != value:
                raise RuntimeError(f"Cambió el valor revisado {field} del ID {case['keep_id']}.")
        for field in SHARED_ID_FIELDS:
            if keep.get(field, "") != remove.get(field, ""):
                raise RuntimeError(f"Conflicto en {field} para el caso {key}.")
        for field, value in remove.items():
            if field == "id_participacion" or field in KEY_FIELDS:
                continue
            if value and keep.get(field, "") != value:
                raise RuntimeError(
                    f"La fila que se pretende retirar aporta un valor exclusivo "
                    f"({field}={value!r}) en el caso {key}."
                )


def validate_applied(rows: list[dict[str, str]]) -> None:
    by_id = {row["id_participacion"]: row for row in rows}
    for case in CASES:
        if case["remove_id"] in by_id or case["keep_id"] not in by_id:
            raise RuntimeError("El CSV no está en el estado ya corregido esperado.")
        keep = by_id[case["keep_id"]]
        key = tuple(keep[field] for field in KEY_FIELDS)
        if key != (case["athlete_id"], case["edition_id"], case["event_id"]):
            raise RuntimeError("Cambió una clave del estado ya corregido.")
        for field, value in case["expected_keep"].items():
            if keep.get(field, "") != value:
                raise RuntimeError(f"Cambió el valor conservado {field} del ID {case['keep_id']}.")
    if duplicate_groups(rows):
        raise RuntimeError("Persisten claves atleta/edición/evento duplicadas.")


def write_reports(before_hash: str, after_hash: str, before_count: int, after_count: int) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    fields = (
        "id_atleta", "atleta", "id_edicion", "edicion", "id_evento", "evento",
        "id_participacion_conservado", "id_participacion_retirado", "decision",
        "nota_verificacion", "referencia_oficial", "sha256_antes", "sha256_despues",
    )
    with AUDIT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for case in CASES:
            writer.writerow({
                "id_atleta": case["athlete_id"], "atleta": case["athlete"],
                "id_edicion": case["edition_id"], "edicion": case["edition"],
                "id_evento": case["event_id"], "evento": case["event"],
                "id_participacion_conservado": case["keep_id"],
                "id_participacion_retirado": case["remove_id"],
                "decision": "CONSOLIDAR_SOLAPAMIENTO; conservar fila con datos y auditar ID retirado",
                "nota_verificacion": case["decision_note"],
                "referencia_oficial": case["references"],
                "sha256_antes": before_hash, "sha256_despues": after_hash,
            })

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    notes = "\n".join(
        f"- **{c['athlete']} — {c['edition']} — {c['event']}:** se conserva "
        f"`{c['keep_id']}` y se retira del CSV la fila redundante `{c['remove_id']}`. "
        f"{c['decision_note']}"
        for c in CASES
    )
    AUDIT_MD.write_text(
        "# Resolución puntual de participaciones duplicadas\n\n"
        f"Ejecución: `{now}`. Se revisaron tres grupos duplicados por "
        "`id_atleta + id_edicion + id_evento` (seis filas). En cada grupo, los valores "
        "no vacíos de la fila escasa coincidían con la fila conservada; no añadían "
        "atributos únicos. Se retiraron exactamente tres filas, sin alterar los otros "
        "CSV ni RAW/intermediate.\n\n"
        f"Conteo de `participacion.csv`: {before_count} → {after_count}.\n\n"
        f"SHA-256 antes: `{before_hash}`  \nSHA-256 después: `{after_hash}`\n\n"
        "## Casos\n\n" + notes + "\n\n"
        "## Verificación de fuentes\n\n"
        "El [informe oficial del IOC para Los Ángeles 1932](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=2875488&parentDocumentId=2875401&skipCopyright=true&skipWatermark=true) "
        "incluye a Antonia Matos en los resultados de arte con mención honorífica; no "
        "confirma por sí solo la edad 27 conservada desde la fuente de datos. "
        "Olympedia registra nacimiento el 21-11-1902, que implicaría 29 años en esos "
        "Juegos; se deja la edad de la fuente sin cambiar, marcada como conflicto no "
        "resuelto y no como dato verificado. El "
        "[informe de fútbol del IOC](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117&skipCopyright=true&skipWatermark=true) "
        "lista a Guatemala en los puestos 10 (Montreal 1976) y 16 (Seúl 1988), mientras "
        "el CSV fuente conserva 9 y 13. Los puestos no se corrigieron aquí porque son "
        "resultados colectivos compartidos por las plantillas completas y cambiar solo "
        "dos atletas dejaría inconsistente el mismo evento; requiere revisión global "
        "de esos dos resultados de equipo.\n\n"
        "Se buscaron las fichas individuales en Olympics.com, pero no se pudieron "
        "consultar directamente durante esta revisión. Se contrastaron las filas de "
        "fuentes y los documentos oficiales del IOC/Olympic Studies Centre.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Aplica la eliminación auditada; por defecto solo valida.")
    args = parser.parse_args()

    original = PARTICIPATION.read_bytes()
    fields, rows = parse_bytes(original)
    expected_fields = [
        "id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc",
        "id_pais_nacionalidad", "equipo", "nombre_competencia", "edad",
        "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado",
        "estado_resultado", "medalla",
    ]
    if fields != expected_fields:
        raise RuntimeError("Cambió el contrato de columnas de participacion.csv.")

    before_hash = sha256(original)
    by_id = {row["id_participacion"]: row for row in rows}
    if all(case["remove_id"] not in by_id and case["keep_id"] in by_id for case in CASES):
        validate_applied(rows)
        if not BACKUP.exists():
            raise RuntimeError("El CSV ya parece corregido, pero falta el backup previo.")
        backup_hash = sha256(BACKUP.read_bytes())
        write_reports(backup_hash, before_hash, len(rows) + len(CASES), len(rows))
        print(f"ALREADY_APPLIED; filas={len(rows)}; SHA-256={before_hash}")
        return

    validate_original(rows)
    print(f"DRY-RUN: {len(rows)} filas; tres grupos y seis filas revisados.")
    for case in CASES:
        print(f"Conservar {case['keep_id']}; retirar {case['remove_id']} — {case['athlete']} / {case['edition']}.")
    if not args.apply:
        return

    if not original.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("Se esperaba UTF-8-SIG/BOM en participacion.csv.")
    physical_lines = original.splitlines(keepends=True)
    if len(physical_lines) != len(rows) + 1 or any(not line.endswith(b"\r\n") for line in physical_lines):
        raise RuntimeError("El archivo ya no es un registro CSV físico por línea con CRLF; se aborta para preservar formato.")

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    if BACKUP.exists():
        if BACKUP.read_bytes() != original:
            raise RuntimeError("Existe un backup previo distinto; no se sobrescribirá.")
    else:
        shutil.copy2(PARTICIPATION, BACKUP)

    removed_ids = {case["remove_id"].encode("ascii") for case in CASES}
    output_lines = [physical_lines[0]]
    removed = set()
    for line in physical_lines[1:]:
        first_field = line.split(b",", 1)[0]
        if first_field in removed_ids:
            removed.add(first_field.decode("ascii"))
            continue
        output_lines.append(line)
    if removed != {case["remove_id"] for case in CASES}:
        raise RuntimeError(f"No se localizaron exactamente las tres filas a retirar: {removed}")

    updated = b"".join(output_lines)
    _, updated_rows = parse_bytes(updated)
    validate_applied(updated_rows)
    if len(updated_rows) != len(rows) - 3:
        raise RuntimeError("El total de filas no disminuyó exactamente en tres.")
    PARTICIPATION.write_bytes(updated)
    after = PARTICIPATION.read_bytes()
    if after != updated:
        raise RuntimeError("La verificación byte a byte posterior a escritura falló.")
    write_reports(before_hash, sha256(after), len(rows), len(updated_rows))
    print(f"APPLIED; filas={len(rows)}->{len(updated_rows)}; SHA-256={sha256(after)}")


if __name__ == "__main__":
    main()
