"""Diagnóstico reproducible de identidades asociadas al NOC GUA.

Este script es deliberadamente no destructivo. Genera candidatos de revisión;
no fusiona atletas, no elimina participaciones y no modifica SQL Server.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "quality"
OUT_CSV = OUT / "gua_identity_reconciliation_candidates.csv"
OUT_MD = OUT / "gua_identity_reconciliation.md"


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("�", "")
    return re.sub(r"[^a-z0-9]+", "", text)


def clean(value: str) -> str:
    return (value or "").strip()


def completeness(row: dict[str, str]) -> int:
    fields = (
        "nombre_completo", "nombre_usado", "nombre_original", "fecha_nacimiento",
        "ciudad_nacimiento", "region_nacimiento", "altura_cm", "peso_kg",
        "titulos", "roles", "afiliaciones",
    )
    return sum(bool(clean(row.get(field, ""))) for field in fields)


def main() -> None:
    athletes = read_csv("atleta.csv")
    participations = read_csv("participacion.csv")
    nocs = read_csv("noc.csv")

    noc_by_id = {row["id_noc"]: row for row in nocs}
    athlete_by_id = {row["id_atleta"]: row for row in athletes}
    participation_by_athlete: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in participations:
        participation_by_athlete[row["id_atleta"]].append(row)

    gua_rows = [
        row for row in participations
        if noc_by_id.get(row.get("id_noc", ""), {}).get("codigo_noc") == "GUA"
    ]
    gua_ids = sorted({row["id_atleta"] for row in gua_rows}, key=int)

    groups: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for athlete_id in gua_ids:
        athlete = athlete_by_id[athlete_id]
        key = (normalize_name(athlete.get("nombre", "")), clean(athlete.get("sexo", "")))
        if key[0]:
            groups[key].append(athlete_id)

    candidate_rows: list[dict[str, str]] = []
    group_count = 0
    excess_count = 0
    for (normalized, sex), ids in sorted(groups.items(), key=lambda item: item[0]):
        if len(ids) < 2:
            continue
        group_count += 1
        excess_count += len(ids) - 1
        rows = [athlete_by_id[athlete_id] for athlete_id in ids]
        dates = sorted({clean(row.get("fecha_nacimiento", "")) for row in rows if clean(row.get("fecha_nacimiento", ""))})
        nocs_seen = sorted({
            noc_by_id.get(participation.get("id_noc", ""), {}).get("codigo_noc", "")
            for athlete_id in ids
            for participation in participation_by_athlete[athlete_id]
            if noc_by_id.get(participation.get("id_noc", ""), {}).get("codigo_noc", "")
        })
        editions = sorted({
            participation.get("id_edicion", "")
            for athlete_id in ids
            for participation in participation_by_athlete[athlete_id]
        }, key=lambda value: int(value) if value.isdigit() else value)
        candidate_rows.append({
            "grupo": f"{normalized}|{sex}",
            "nombre_normalizado": normalized,
            "sexo": sex,
            "ids_atleta": ";".join(ids),
            "cantidad_ids": str(len(ids)),
            "exceso_potencial": str(len(ids) - 1),
            "nombres_observados": " || ".join(sorted({clean(row.get("nombre", "")) for row in rows})),
            "fechas_nacimiento_observadas": ";".join(dates),
            "nocs_observados": ";".join(nocs_seen),
            "ediciones_observadas": ";".join(editions),
            "participaciones_grupo": str(sum(len(participation_by_athlete[athlete_id]) for athlete_id in ids)),
            "completitud_por_id": ";".join(f"{row['id_atleta']}:{completeness(row)}" for row in rows),
            "clasificacion": "REVIEW_NAME_ONLY",
            "accion": "NO_FUSIONAR_SIN_EVIDENCIA_BIOGRAFICA",
            "motivo": "Coincidencia de nombre normalizado y sexo; las fechas son faltantes o no permiten demostrar identidad única.",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(candidate_rows[0]) if candidate_rows else [
        "grupo", "nombre_normalizado", "sexo", "ids_atleta", "cantidad_ids",
        "exceso_potencial", "nombres_observados", "fechas_nacimiento_observadas",
        "nocs_observados", "ediciones_observadas", "participaciones_grupo",
        "completitud_por_id", "clasificacion", "accion", "motivo",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidate_rows)

    exact_date_groups = sum(
        1 for row in candidate_rows
        if len([value for value in row["fechas_nacimiento_observadas"].split(";") if value]) == 1
    )
    summary = [
        "# Reconciliación de identidades GUA",
        "",
        "Estado: **DIAGNOSTIC_ONLY**",
        "",
        "El reporte es no destructivo: no fusiona atletas, no elimina participaciones y no modifica SQL Server.",
        "",
        "## Resultado",
        "",
        f"- Filas de participación con NOC GUA: **{len(gua_rows)}**.",
        f"- IDs de atleta asociados: **{len(gua_ids)}**.",
        f"- Nombres visibles distintos: **{len({clean(athlete_by_id[athlete_id].get('nombre', '')) for athlete_id in gua_ids})}**.",
        f"- Grupos con nombre normalizado y sexo repetidos: **{group_count}**.",
        f"- Exceso potencial dentro de esos grupos: **{excess_count}** IDs.",
        f"- Grupos con una única fecha observada: **{exact_date_groups}**; no se consideran automáticamente confirmados porque la fecha puede faltar en los demás registros.",
        "",
        "## Decisión",
        "",
        "Todos los candidatos quedan en `REVIEW_NAME_ONLY`. El proyecto no fusiona homónimos únicamente por nombre: para aplicar un merge se requiere evidencia biográfica y contextual suficiente, sin conflicto de NOC, fechas o historial.",
        "",
        "## Archivos",
        "",
        f"- `{OUT_CSV.relative_to(ROOT)}` contiene el detalle reproducible por grupo.",
        f"- Comando: `python scripts/python/24_gua_identity_reconciliation.py`.",
    ]
    OUT_MD.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("GUA_IDENTITY_DIAGNOSTIC_COMPLETE")
    print(f"gua_rows={len(gua_rows)}")
    print(f"gua_ids={len(gua_ids)}")
    print(f"candidate_groups={group_count}")
    print(f"potential_excess_ids={excess_count}")
    print(f"output={OUT_CSV}")


if __name__ == "__main__":
    main()
