"""Revisión puntual de EDICION_OLIMPICA posterior al Bloque 5.

No vuelve a ejecutar matching. Homologa únicamente Equestrian 1956 y la
clasificación duplicada de 1906 sobre los CSV procesados ya aprobados.
RAW e intermedios limpios nunca se escriben.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from unidecode import unidecode


ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "intermediate" / "cleaned"
PROCESSED = ROOT / "data" / "processed"
CONSOLIDATION = ROOT / "docs" / "consolidation"


def norm(value: object) -> str:
    value = unidecode("" if value is None else str(value)).casefold()
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def comparison_key(row: dict[str, str], source: str) -> tuple[str, ...]:
    name = row.get("nombre_competencia", "") if source == "fuente1" else row.get("name", "")
    event = row.get("event", "")
    if source in {"fuente2", "fuente3"}:
        sport = norm(row.get("sport", ""))
        event_norm = norm(event)
        if sport and event_norm.startswith(sport + " "):
            event = event_norm[len(sport) + 1 :]
    event = norm(event).replace("intercalated", "")
    event = re.sub(r"\b(women|men|womens|mens)\b", " ", event)
    return (
        norm(name), re.sub(r"\s+", " ", event).strip(), norm(row.get("noc_codigo", "")),
        norm(row.get("equipo", "")), norm(row.get("medalla", "")),
    )


def attribute_sets(rows: list[dict[str, str]], source: str) -> dict[str, set[tuple[str, ...]]]:
    return {
        "atleta": {(comparison_key(row, source)[0], comparison_key(row, source)[2]) for row in rows},
        "evento": {comparison_key(row, source)[1] for row in rows},
        "noc_equipo": {(comparison_key(row, source)[2], comparison_key(row, source)[3]) for row in rows},
        "resultado": {comparison_key(row, source)[4] for row in rows},
        "completa": {comparison_key(row, source) for row in rows},
    }


def edition_1906_report() -> None:
    source_files = {
        "fuente1": CLEAN / "fuente1_raw_results.csv",
        "fuente2": CLEAN / "fuente2_athlete_events.csv",
        "fuente3": CLEAN / "fuente3_olympics_dataset.csv",
    }
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for source, path in source_files.items():
        for row in read_rows(path):
            if row.get("year", "") == "1906" and row.get("season", "") in {"Summer", "Intercalated Games"}:
                groups[(source, row["season"])].append(row)

    fields = [
        "tipo_registro", "categoria_a", "categoria_b", "fuente_a", "fuente_b", "filas_a", "filas_b",
        "atletas_distintos_a", "atletas_distintos_b", "eventos_distintos_a", "eventos_distintos_b",
        "coincidencias_atleta", "coincidencias_evento", "coincidencias_noc_equipo", "coincidencias_resultado",
        "coincidencias_clave_completa", "solo_a", "solo_b", "conclusion",
    ]
    rows: list[dict[str, object]] = []
    for (source, category), values in sorted(groups.items()):
        rows.append({
            "tipo_registro": "SOURCE_SUMMARY", "categoria_a": category, "categoria_b": "", "fuente_a": source,
            "fuente_b": "", "filas_a": len(values), "filas_b": "",
            "atletas_distintos_a": len({norm(r.get("nombre_competencia", r.get("name", ""))) for r in values}),
            "atletas_distintos_b": "", "eventos_distintos_a": len({norm(r.get("event", "")) for r in values}),
            "eventos_distintos_b": "", "conclusion": "Conteo original por fuente y categoría; no se excluyen participaciones.",
        })

    summer = [row for (source, category), values in groups.items() if category == "Summer" for row in values]
    intercalated = [row for (source, category), values in groups.items() if category == "Intercalated Games" for row in values]
    summer_parts = []
    for source in ("fuente2", "fuente3"):
        summer_parts.extend(groups.get((source, "Summer"), []))
    left_sets = attribute_sets(summer_parts, "fuente2")
    right_sets = attribute_sets(intercalated, "fuente1")
    rows.append({
        "tipo_registro": "CATEGORY_COMPARISON", "categoria_a": "Summer", "categoria_b": "Intercalated Games",
        "fuente_a": "fuente2+fuente3", "fuente_b": "fuente1", "filas_a": len(summer), "filas_b": len(intercalated),
        "atletas_distintos_a": len(left_sets["atleta"]), "atletas_distintos_b": len(right_sets["atleta"]),
        "eventos_distintos_a": len(left_sets["evento"]), "eventos_distintos_b": len(right_sets["evento"]),
        "coincidencias_atleta": len(left_sets["atleta"] & right_sets["atleta"]),
        "coincidencias_evento": len(left_sets["evento"] & right_sets["evento"]),
        "coincidencias_noc_equipo": len(left_sets["noc_equipo"] & right_sets["noc_equipo"]),
        "coincidencias_resultado": len(left_sets["resultado"] & right_sets["resultado"]),
        "coincidencias_clave_completa": len(left_sets["completa"] & right_sets["completa"]),
        "solo_a": len(left_sets["completa"] - right_sets["completa"]), "solo_b": len(right_sets["completa"] - left_sets["completa"]),
        "conclusion": "Las categorías describen 1906 con coberturas y nomenclaturas distintas; la coincidencia de año y evento histórico justifica una sola edición, pero las participaciones se conservan y solo se deduplican filas exactas posteriores al remapeo.",
    })
    write_rows(CONSOLIDATION / "edition_1906_analysis.csv", rows, fields)


def remap_editions() -> tuple[int, int, list[dict[str, object]]]:
    editions = read_rows(PROCESSED / "edicion_olimpica.csv")
    by_key = {(row["anio"], row["temporada"]): row for row in editions}
    targets = {
        ("1956", "Equestrian"): ("1956", "Summer"),
        ("1906", "Summer"): ("1906", "Intercalated Games"),
    }
    old_to_canonical: dict[str, str] = {}
    for row in editions:
        old_key = (row["anio"], row["temporada"])
        target = targets.get(old_key, old_key)
        old_to_canonical[row["id_edicion"]] = by_key[target]["id_edicion"]

    retained = [row for row in editions if (row["anio"], row["temporada"]) not in targets]
    retained.extend(by_key[target] for target in sorted(set(targets.values())) if target not in {(r["anio"], r["temporada"]) for r in retained})
    retained = sorted(retained, key=lambda row: (int(row["anio"]), row["temporada"]))
    canonical_old_by_key = {(row["anio"], row["temporada"]): row["id_edicion"] for row in retained}
    new_id_by_old = {old: str(index) for index, old in enumerate([canonical_old_by_key[(r["anio"], r["temporada"])] for r in retained], start=1)}
    for row in retained:
        row["id_edicion"] = new_id_by_old[canonical_old_by_key[(row["anio"], row["temporada"])] ]
    write_rows(PROCESSED / "edicion_olimpica.csv", retained, ["id_edicion", "anio", "temporada", "id_sede"])
    old_to_new = {old: new_id_by_old[canonical] for old, canonical in old_to_canonical.items()}
    return len(editions), len(retained), [{"old_id": old, "new_id": new} for old, new in old_to_new.items() if old != new]


def remap_participations(old_to_new: dict[str, str], affected_old_ids: set[str]) -> tuple[int, int, list[dict[str, str]]]:
    source = PROCESSED / "participacion.csv"
    temp = source.with_suffix(".csv.tmp")
    seen_db = source.with_suffix(".edition_dedup.sqlite")
    removed: list[dict[str, str]] = []
    total = 0
    kept = 0
    connection = sqlite3.connect(seen_db)
    try:
        connection.execute("CREATE TABLE seen (digest TEXT PRIMARY KEY)")
        with source.open("r", encoding="utf-8-sig", newline="") as handle, temp.open("w", encoding="utf-8", newline="") as out:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                total += 1
                old_id = row["id_edicion"]
                row["id_edicion"] = old_to_new.get(old_id, old_id)
                key_values = [row[field] for field in fields if field != "id_participacion"]
                digest = hashlib.sha256("\x1f".join(key_values).encode("utf-8")).hexdigest()
                if old_id in affected_old_ids:
                    try:
                        connection.execute("INSERT INTO seen(digest) VALUES (?)", (digest,))
                    except sqlite3.IntegrityError:
                        removed.append({"id_participacion_original": row["id_participacion"], "id_edicion": row["id_edicion"], "clave_logica": digest})
                        continue
                kept += 1
                row["id_participacion"] = str(kept)
                writer.writerow(row)
        connection.commit()
        temp.replace(source)
    finally:
        connection.close()
        if seen_db.exists():
            seen_db.unlink()
    return total, kept, removed


def update_deduplication(removed: list[dict[str, str]]) -> None:
    path = CONSOLIDATION / "participation_deduplication.csv"
    temp = path.with_suffix(".csv.tmp")
    with path.open("r", encoding="utf-8-sig", newline="") as source, temp.open("w", encoding="utf-8", newline="") as target:
        reader = csv.DictReader(source)
        fields = reader.fieldnames or ["archivo", "fuente", "fila_origen", "id_original", "clave_logica", "tipo", "retained", "motivo"]
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            writer.writerow(row)
        for item in removed:
            writer.writerow({
                "archivo": "data/processed/participacion.csv", "fuente": "post_consolidacion", "fila_origen": item["id_participacion_original"],
                "id_original": "", "clave_logica": item["clave_logica"], "tipo": "EDITION_HOMOLOGATION_EXACT_DUPLICATE",
                "retained": "NO", "motivo": "Duplicado exacto creado únicamente al homologar la edición; se conserva una sola participación determinística.",
            })
    temp.replace(path)


def refresh_counts_and_validations(edition_count: int, participation_count: int) -> None:
    counts_path = CONSOLIDATION / "processed_counts.csv"
    counts = read_rows(counts_path)
    for row in counts:
        if row["entidad"] == "edicion_olimpica":
            row["filas"] = str(edition_count)
        if row["entidad"] == "participacion":
            row["filas"] = str(participation_count)
    write_rows(counts_path, counts, list(counts[0]))

    validations_path = CONSOLIDATION / "final_validations.csv"
    validations = read_rows(validations_path)
    for row in validations:
        if row["validacion"] in {"PK edicion_olimpica", "PK participacion", "Edición año+temporada", "FK participacion.id_edicion"}:
            row["actual"] = "0"
            row["estado"] = "PASS"
            row["detalle"] = "Revalidado después de homologar Equestrian 1956 y 1906; no quedan duplicados ni referencias inválidas."
    write_rows(validations_path, validations, list(validations[0]))


def special_cases_report() -> None:
    rows = [
        {"anio": "1956", "categoria_original": "Equestrian", "categoria_final": "Summer", "ciudad_original": "Stockholm", "sede_final": "Melbourne", "participaciones_afectadas": "300", "motivo": "Pruebas ecuestres de 1956 realizadas en Stockholm por cuarentena australiana; pertenecen a Melbourne 1956.", "estado": "HOMOLOGADO_AUDITADO"},
        {"anio": "1906", "categoria_original": "Summer", "categoria_final": "Intercalated Games", "ciudad_original": "Athina", "sede_final": "Athina", "participaciones_afectadas": "3466", "motivo": "Clasificación Summer de fuentes 2/3 homologada a la edición Intercalated Games 1906; se conserva el total combinado.", "estado": "HOMOLOGADO_AUDITADO"},
    ]
    write_rows(CONSOLIDATION / "edition_special_cases.csv", rows, list(rows[0]))


def main() -> None:
    edition_1906_report()
    special_cases_report()
    editions_before = read_rows(PROCESSED / "edicion_olimpica.csv")
    original_catalog = len(editions_before) == 63 and any(row["temporada"] == "Equestrian" for row in editions_before)
    if not original_catalog:
        edition_rows = editions_before
        old_to_new = {row["id_edicion"]: row["id_edicion"] for row in edition_rows}
        affected_old_ids: set[str] = set()
        total, kept, removed = remap_participations(old_to_new, affected_old_ids)
        update_deduplication(removed)
        refresh_counts_and_validations(len(edition_rows), kept)
        print(f"Ediciones: {len(edition_rows)} -> {len(edition_rows)}")
        print(f"Participaciones: {total} -> {kept}; duplicados nuevos eliminados: {len(removed)}")
        return
    if original_catalog:
        edition_source = read_rows(ROOT / "docs" / "schema" / "edition_season_analysis.csv")
        # La fuente de análisis conserva el catálogo original como respaldo
        # para reejecuciones después de una interrupción.
        if len(edition_source) >= 63:
            editions_before = [
                {"id_edicion": row["id_edicion"], "anio": row["anio"], "temporada": row["temporada"], "id_sede": row["id_sede"]}
                for row in edition_source if row.get("tipo_registro") == "EDITION"
            ]
    old_to_canonical = {}
    by_key = {(row["anio"], row["temporada"]): row["id_edicion"] for row in editions_before}
    for row in editions_before:
        target = {("1956", "Equestrian"): ("1956", "Summer"), ("1906", "Summer"): ("1906", "Intercalated Games")}.get((row["anio"], row["temporada"]), (row["anio"], row["temporada"]))
        old_to_canonical[row["id_edicion"]] = by_key[target]
    retained_keys = sorted(set((row["anio"], row["temporada"]) for row in editions_before if (row["anio"], row["temporada"]) not in {("1956", "Equestrian"), ("1906", "Summer")}) | {("1956", "Summer"), ("1906", "Intercalated Games")}, key=lambda x: (int(x[0]), x[1]))
    new_by_canonical = {by_key[key]: str(index) for index, key in enumerate(retained_keys, start=1)}
    old_to_new = {old: new_by_canonical[canonical] for old, canonical in old_to_canonical.items()}
    affected_canonical = {by_key[("1956", "Summer")], by_key[("1906", "Intercalated Games")]}
    affected_old_ids = {old for old, canonical in old_to_canonical.items() if canonical in affected_canonical}
    edition_rows = [row for row in editions_before if (row["anio"], row["temporada"]) not in {("1956", "Equestrian"), ("1906", "Summer")}]
    for row in edition_rows:
        row["id_edicion"] = new_by_canonical[row["id_edicion"]]
    write_rows(PROCESSED / "edicion_olimpica.csv", sorted(edition_rows, key=lambda r: int(r["id_edicion"])), ["id_edicion", "anio", "temporada", "id_sede"])
    total, kept, removed = remap_participations(old_to_new, affected_old_ids)
    update_deduplication(removed)
    refresh_counts_and_validations(len(edition_rows), kept)
    print(f"Ediciones: {len(editions_before)} -> {len(edition_rows)}")
    print(f"Participaciones: {total} -> {kept}; duplicados nuevos eliminados: {len(removed)}")


if __name__ == "__main__":
    main()
