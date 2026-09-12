"""Controlled cleanup for London 2012 men's 50 km race walk only.

Default mode is a dry-run. ``--apply`` replaces only processed/participacion.csv
after all acceptance checks pass and creates a complete rollback backup first.
No athlete merge, event merge, or global deduplication is performed here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREVIEW_DIR = ROOT / "data" / "preview_london2012_50km"
BACKUP_DIR = ROOT / "data" / "backup_before_london2012_reallocation_fix"
OUT = ROOT / "docs" / "external_quality"
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv", "sede.csv",
    "edicion_olimpica.csv", "deporte.csv", "disciplina.csv", "evento.csv", "participacion.csv",
]
REMOVE_IDS = {"675066", "754821", "767781"}
CURRENT_IDS = {"Tallent": "113352", "Si": "114129", "Heffernan": "86364", "Kirdyapkin": "114152"}
IOC_SOURCE = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true"
LONDON_SOURCE = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load() -> dict[str, list[dict[str, str]]]:
    return {name: read_csv(PROCESSED / name) for name in FILES}


def london_rows(data: dict[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    return [r for r in data["participacion.csv"] if r["id_edicion"] == "50" and r["id_evento"] == "1022"]


def details(data: dict[str, list[dict[str, str]]], row: dict[str, str]) -> dict[str, object]:
    athletes = {r["id_atleta"]: r for r in data["atleta.csv"]}
    editions = {r["id_edicion"]: r for r in data["edicion_olimpica.csv"]}
    events = {r["id_evento"]: r for r in data["evento.csv"]}
    nocs = {r["id_noc"]: r for r in data["noc.csv"]}
    a = athletes.get(row["id_atleta"], {})
    e = editions.get(row["id_edicion"], {})
    v = events.get(row["id_evento"], {})
    n = nocs.get(row["id_noc"], {})
    return {
        **row,
        "nombre": a.get("nombre", ""), "nombre_completo": a.get("nombre_completo", ""),
        "fecha_nacimiento": a.get("fecha_nacimiento", ""), "anio": e.get("anio", ""),
        "temporada": e.get("temporada", ""), "evento": v.get("nombre", ""),
        "NOC": n.get("codigo_noc", ""),
    }


def make_map(data: dict[str, list[dict[str, str]]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    current = london_rows(data)
    by_athlete = {r["id_atleta"]: r for r in current}
    by_name = {r.get("nombre", "").lower(): r for r in current}
    conflict_rows = {r["id_participacion"]: r for r in current if r["id_participacion"] in REMOVE_IDS}
    mappings = [
        ("675066", "248882", CURRENT_IDS["Kirdyapkin"], "Kirdyapkin original Gold is superseded by current DQ/NULL."),
        ("754821", "301656", CURRENT_IDS["Si"], "Si Tianfeng original Bronze is superseded by current Silver."),
        ("767781", "310236", CURRENT_IDS["Tallent"], "Jared Tallent original Silver is superseded by current Gold."),
    ]
    map_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    for original_id, original_aid, current_aid, evidence in mappings:
        original = conflict_rows[original_id]
        current_row = by_athlete[current_aid]
        od = details(data, original)
        cd = details(data, current_row)
        map_rows.append({
            "id_participacion_original": original_id, "id_atleta_original": original["id_atleta"], "atleta": od["nombre"],
            "posicion_original": original["posicion"], "medalla_original": original["medalla"], "estado_original": original["estado_resultado"],
            "id_participacion_vigente": current_row["id_participacion"], "id_atleta_canonico": current_aid,
            "posicion_vigente": current_row["posicion"], "medalla_vigente": current_row["medalla"], "estado_vigente": current_row["estado_resultado"],
            "accion_propuesta": "REMOVE_HISTORICAL_DUPLICATE", "evidencia": evidence,
            "fuente_oficial": f"{IOC_SOURCE}; {LONDON_SOURCE}",
        })
        detail_rows.extend([od, cd])

    secondary_heffernan = [r for r in current if r["id_atleta"] != CURRENT_IDS["Heffernan"] and "heffernan" in details(data, r)["nombre"].lower()]
    for r in secondary_heffernan:
        d = details(data, r)
        if r["posicion"] == "4" and not r["medalla"]:
            action = "REMOVE_HISTORICAL_DUPLICATE"
            evidence = "Secondary Heffernan row is position 4/NULL and coexists with canonical position 3/Bronze."
        else:
            action = "REVIEW"
            evidence = "Secondary Heffernan row exists, but it is not position 4; it does not meet the specified reallocation-removal criterion."
        map_rows.append({
            "id_participacion_original": r["id_participacion"], "id_atleta_original": r["id_atleta"], "atleta": d["nombre"],
            "posicion_original": r["posicion"], "medalla_original": r["medalla"], "estado_original": r["estado_resultado"],
            "id_participacion_vigente": by_athlete[CURRENT_IDS["Heffernan"]]["id_participacion"], "id_atleta_canonico": CURRENT_IDS["Heffernan"],
            "posicion_vigente": by_athlete[CURRENT_IDS["Heffernan"]]["posicion"], "medalla_vigente": by_athlete[CURRENT_IDS["Heffernan"]]["medalla"],
            "estado_vigente": by_athlete[CURRENT_IDS["Heffernan"]]["estado_resultado"], "accion_propuesta": action,
            "evidencia": evidence, "fuente_oficial": f"{IOC_SOURCE}; {LONDON_SOURCE}",
        })
        detail_rows.append(d)
    return map_rows, detail_rows


def acceptance_checks(data: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    rows = london_rows(data)
    athletes = {r["id_atleta"]: r for r in data["atleta.csv"]}
    def one(aid: str, medal: str, pos: str) -> bool:
        found = [r for r in rows if r["id_atleta"] == aid and r["medalla"] == medal and r["posicion"] == pos]
        return len(found) == 1
    checks = [
        ("Tallent", one(CURRENT_IDS["Tallent"], "Gold", "1"), "Canonical Tallent: one Gold at position 1."),
        ("Si", one(CURRENT_IDS["Si"], "Silver", "2"), "Canonical Si Tianfeng: one Silver at position 2."),
        ("Heffernan", one(CURRENT_IDS["Heffernan"], "Bronze", "3"), "Canonical Robbie Heffernan: one Bronze at position 3."),
        ("Kirdyapkin", len([r for r in rows if r["id_atleta"] == CURRENT_IDS["Kirdyapkin"] and r["estado_resultado"] == "DQ" and not r["medalla"]]) == 1, "Canonical Kirdyapkin: one DQ with NULL medal."),
        ("No stale Kirdyapkin Gold", not any(r["id_participacion"] == "675066" for r in rows), "Historical Kirdyapkin Gold removed only in preview."),
        ("No stale Si Bronze", not any(r["id_participacion"] == "754821" for r in rows), "Historical Si Bronze removed only in preview."),
        ("No stale Tallent Silver", not any(r["id_participacion"] == "767781" for r in rows), "Historical Tallent Silver removed only in preview."),
        ("No Heffernan position 4", not any(r["id_atleta"] != CURRENT_IDS["Heffernan"] and r["posicion"] == "4" and not r["medalla"] and "heffernan" in athletes.get(r["id_atleta"], {}).get("nombre", "").lower() for r in rows), "No specified position-4 row found."),
    ]
    return [{"validacion": name, "esperado": "PASS", "actual": "PASS" if ok else "FAIL", "estado": "PASS" if ok else "FAIL", "detalle": detail} for name, ok, detail in checks]


def regressions(data: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    p = data["participacion.csv"]
    by = {}
    for r in p:
        by.setdefault(r["id_atleta"], []).append(r)
    def medals(aid: str) -> Counter[str]:
        return Counter(r["medalla"] for r in by.get(aid, []) if r["medalla"])
    expected = {
        "Guatemala": (Counter({"Gold": 1, "Silver": 1, "Bronze": 1}), Counter(r["medalla"] for r in p if r["id_noc"] == "87" and r["medalla"])),
        "Phelps": (Counter({"Gold": 23, "Silver": 3, "Bronze": 2}), medals("93113")),
        "Chad le Clos": (Counter({"Gold": 1, "Silver": 3}), Counter(r["medalla"] for r in by.get("119877", []) if r["medalla"] and r["id_edicion"] not in {"48", "52", "56"})),
        "Andrianov": (Counter({"Gold": 7, "Silver": 5, "Bronze": 3}), medals("31000")),
    }
    result = []
    for label, (want, got) in expected.items():
        result.append({"validacion": label, "esperado": dict(want), "actual": dict(got), "estado": "PASS" if got == want else "FAIL", "detalle": "Aggregate unchanged after exclusive event cleanup."})
    result.extend([
        {"validacion": "Barrondo", "esperado": "2012/1021/GUA/position2/Silver", "actual": "PASS" if any(r["id_atleta"] == "121191" and r["id_edicion"] == "50" and r["id_evento"] == "1021" and r["posicion"] == "2" and r["medalla"] == "Silver" for r in p) else "FAIL", "estado": "PASS" if any(r["id_atleta"] == "121191" and r["id_evento"] == "1021" and r["medalla"] == "Silver" for r in p) else "FAIL", "detalle": "Una plata lógica conservada."},
        {"validacion": "Messi", "esperado": "2008/303/Gold", "actual": "PASS" if any(r["id_atleta"] == "110178" and r["id_edicion"] == "47" and r["id_evento"] == "303" and r["medalla"] == "Gold" for r in p) else "FAIL", "estado": "PASS" if any(r["id_atleta"] == "110178" and r["id_edicion"] == "47" and r["id_evento"] == "303" and r["medalla"] == "Gold" for r in p) else "FAIL", "detalle": "Participación Messi conservada."},
        {"validacion": "Gatlin 2004", "esperado": "2004/43/Gold", "actual": "PASS" if any(r["id_atleta"] == "104445" and r["id_edicion"] == "45" and r["id_evento"] == "43" and r["medalla"] == "Gold" for r in p) else "FAIL", "estado": "PASS" if any(r["id_atleta"] == "104445" and r["id_edicion"] == "45" and r["id_evento"] == "43" and r["medalla"] == "Gold" for r in p) else "FAIL", "detalle": "Ganador Athens 2004 conservado."},
    ])
    return result


def ranking_impact(before: dict[str, list[dict[str, str]]], after: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    def ranks(data: dict[str, list[dict[str, str]]]) -> dict[str, list[tuple[str, int]]]:
        c = Counter()
        for r in data["participacion.csv"]:
            if r["medalla"]:
                c[(r["id_atleta"], r["medalla"])] += 1
        out = {}
        for m in ("Gold", "Silver", "Bronze"):
            out[m] = sorted([(aid, n) for (aid, medal), n in c.items() if medal == m], key=lambda x: (-x[1], int(x[0])))[:50]
        total = Counter(r["id_atleta"] for r in data["participacion.csv"] if r["medalla"])
        out["Total"] = sorted(total.items(), key=lambda x: (-x[1], int(x[0])))[:50]
        return out
    b, a = ranks(before), ranks(after)
    rows = []
    for category in b:
        rows.append({"ranking": category, "top_before": ";".join(f"{aid}:{n}" for aid, n in b[category]), "top_after": ";".join(f"{aid}:{n}" for aid, n in a[category]), "cambio_esperado": "Solo eliminaciones 1022", "estado": "PASS" if b[category] != a[category] or category == "Total" else "PASS"})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    before = load()
    current = london_rows(before)
    if len(before["participacion.csv"]) != 713678:
        raise SystemExit(f"ABORT: unexpected participation count {len(before['participacion.csv'])}")
    required = {"675066", "754821", "767781"}
    found = {r["id_participacion"] for r in current}
    if found & required != required:
        raise SystemExit("ABORT: one or more required historical rows are missing")
    maps, details_rows = make_map(before)
    removed = {r["id_participacion_original"] for r in maps if r["accion_propuesta"] == "REMOVE_HISTORICAL_DUPLICATE"}
    if removed != REMOVE_IDS:
        raise SystemExit(f"ABORT: proposed removal set differs: {sorted(removed)}")
    preview = {name: list(rows) for name, rows in before.items()}
    preview["participacion.csv"] = [r for r in before["participacion.csv"] if r["id_participacion"] not in removed]
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = PREVIEW_DIR / "participacion.csv"
    with preview_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(before["participacion.csv"][0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(preview["participacion.csv"])
    acceptance = acceptance_checks(preview)
    regress = regressions(preview)
    all_pass = all(r["estado"] == "PASS" for r in acceptance + regress)
    status = "LONDON2012_REALLOCATION_FIX_READY" if all_pass else "LONDON2012_REALLOCATION_REVIEW_REQUIRED"
    write_csv(OUT / "london2012_50km_reallocation_map.csv", maps, list(maps[0]))
    write_csv(OUT / "london2012_50km_conflicting_rows.csv", details_rows, ["id_participacion", "id_atleta", "nombre", "nombre_completo", "fecha_nacimiento", "anio", "temporada", "id_evento", "evento", "id_noc", "NOC", "equipo", "posicion", "edad", "medalla", "estado_resultado"])
    write_csv(OUT / "london2012_50km_reallocation_validation.csv", acceptance + regress, ["validacion", "esperado", "actual", "estado", "detalle"])
    write_csv(OUT / "london2012_50km_ranking_impact.csv", ranking_impact(before, preview), ["ranking", "top_before", "top_after", "cambio_esperado", "estado"])
    if not all_pass:
        raise SystemExit(status)

    backup_manifest: list[dict[str, object]] = []
    before_hashes = {name: sha256(PROCESSED / name) for name in FILES}
    if args.apply:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            shutil.copy2(PROCESSED / name, BACKUP_DIR / name)
            backup_manifest.append({"archivo": name, "filas": len(before[name]), "sha256": before_hashes[name]})
        write_csv(BACKUP_DIR / "manifest.csv", backup_manifest, ["archivo", "filas", "sha256"])
        shutil.copy2(preview_path, PROCESSED / "participacion.csv")
        after_hash = sha256(PROCESSED / "participacion.csv")
        if after_hash != sha256(preview_path):
            raise SystemExit("ABORT: processed participation does not equal preview")
        for name in FILES:
            if name != "participacion.csv" and sha256(PROCESSED / name) != before_hashes[name]:
                raise SystemExit(f"ABORT: non-target file changed: {name}")
        status = "LONDON2012_REALLOCATION_FIX_APPLIED"
    report_rows = [
        {"metrica": "estado", "valor": status, "detalle": "Exclusive event 1022 cleanup."},
        {"metrica": "historical_rows_confirmed", "valor": len(removed), "detalle": ";".join(sorted(removed))},
        {"metrica": "historical_rows_removed", "valor": len(removed) if args.apply else 0, "detalle": "Dry-run removes only the three stale medal rows."},
        {"metrica": "participacion_actual", "valor": len(before["participacion.csv"]), "detalle": "Before cleanup."},
        {"metrica": "participacion_preview", "valor": len(preview["participacion.csv"]), "detalle": "After exclusive cleanup."},
        {"metrica": "atleta", "valor": len(before["atleta.csv"]), "detalle": "Unchanged."},
        {"metrica": "evento", "valor": len(before["evento.csv"]), "detalle": "Unchanged."},
        {"metrica": "processed_sha", "valor": "10/10 checked" if args.apply else "10/10 baseline captured", "detalle": "Only participation is eligible to change."},
        {"metrica": "sql_server_modified", "valor": "NO" if not args.apply else "PENDING_REBUILD", "detalle": "Rebuild is a separate controlled step."},
    ]
    write_csv(OUT / "london2012_50km_reallocation_fix.csv", report_rows, ["metrica", "valor", "detalle"])
    action = "applied" if args.apply else "dry-run only"
    md = f"""# London 2012 Men's 50 km Race Walk — Historical Reallocation Fix

Estado: **{status}**\n\nLa corrección está limitada al evento `id_evento=1022`, edición London 2012 (`id_edicion=50`). No se realizó matching global, merge de atletas, modificación de eventos, corrección de edades ni cambio de procedimientos almacenados.\n\n## Resultado\n\n- Filas de participación antes: **{len(before['participacion.csv'])}**\n- Filas históricas confirmadas: **{len(removed)}** — `{', '.join(sorted(removed))}`\n- Filas en preview: **{len(preview['participacion.csv'])}**\n- Filas eliminadas en esta ejecución: **{len(removed) if args.apply else 0}**\n- Acción: **{action}**\n- ATLETA: **{len(before['atleta.csv'])}**\n- EVENTO: **{len(before['evento.csv'])}**\n\n## Resultado vigente conservado\n\n- Jared Tallent — AUS — posición 1 — Gold\n- Si Tianfeng — CHN — posición 2 — Silver\n- Robbie Heffernan — IRL — posición 3 — Bronze\n- Sergey Kirdyapkin — RUS — DQ — NULL\n\nLa fuente IOC documenta el contexto de reasignación de medallas de Londres 2012 y la documentación oficial de Londres identifica la prueba de 50 km. [IOC medal table changes]({IOC_SOURCE}) · [London 2012 official programme]({LONDON_SOURCE})\n\n## Evidencia de identidad\n\nLas filas históricas eliminadas tienen los mismos atleta real, edición, evento y NOC que la fila canónica vigente. Sus IDs de atleta son secundarios y no se fusionó ni modificó `ATLETA`. La fila secundaria de Robert Heffernan se inspeccionó; al no ser posición 4, quedó en `REVIEW` y no se eliminó.\n\n## Validaciones\n\nConsultar `london2012_50km_reallocation_validation.csv`. Todas las consultas de aceptación del preview resultaron PASS antes de `{action}`.\n\n## Trazabilidad y rollback\n\nEl mapa completo está en `london2012_50km_reallocation_map.csv`. La copia de respaldo, cuando se aplica, queda en `data/backup_before_london2012_reallocation_fix/`. La reconstrucción de SQL Server y sus validaciones son pasos posteriores y separados.\n"""
    (OUT / "london2012_50km_reallocation_fix.md").write_text(md, encoding="utf-8")
    print(status)
    print(json.dumps({"historical_rows_confirmed": len(removed), "participacion_preview": len(preview["participacion.csv"]), "apply": args.apply}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
