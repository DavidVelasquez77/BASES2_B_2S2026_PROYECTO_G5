"""Validate the applied GUA correction without changing project data."""
from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
BACKUP = ROOT / "data" / "backup_before_gua_canonical_apply"
OUT = ROOT / "docs" / "quality"


def read(name: str, directory: Path = PROCESSED) -> list[dict[str, str]]:
    with (directory / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    processed_files = sorted(PROCESSED.glob("*.csv"))
    before = {p.name: digest(BACKUP / p.name) for p in processed_files}
    after = {p.name: digest(p) for p in processed_files}
    manifest_rows = []
    for path in processed_files:
        manifest_rows.append({
            "archivo": path.name,
            "filas": str(len(read(path.name))),
            "sha256_backup": before[path.name],
            "sha256_after": after[path.name],
            "estado": "MATCH" if before[path.name] == after[path.name] else "CHANGED",
        })
    with (OUT / "gua_canonical_manifest_after.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(manifest_rows)

    nocs = {r["id_noc"]: r["codigo_noc"] for r in read("noc.csv")}
    editions = {r["id_edicion"]: r for r in read("edicion_olimpica.csv")}
    refs = read("gua_olympedia_olympic_roster.csv", OUT)
    expected_by_edition: defaultdict[str, set[str]] = defaultdict(set)
    for row in refs:
        if row.get("contado_en_referencia_263") == "YES":
            expected_by_edition[row["id_edicion_local"]].add(row["olympedia_athlete_id"])

    gua_olympic_rows = []
    gua_youth_rows = []
    for row in read("participacion.csv"):
        if nocs.get(row.get("id_noc", "")) != "GUA":
            continue
        season = editions.get(row.get("id_edicion", ""), {}).get("temporada", "")
        if season in {"Summer", "Winter"}:
            gua_olympic_rows.append(row)
        elif season in {"Summer Youth", "Winter Youth"}:
            gua_youth_rows.append(row)

    actual_by_edition: defaultdict[str, set[str]] = defaultdict(set)
    rows_by_edition: defaultdict[str, int] = defaultdict(int)
    for row in gua_olympic_rows:
        actual_by_edition[row["id_edicion"]].add(row["id_atleta"])
        rows_by_edition[row["id_edicion"]] += 1

    validation = []
    for eid in sorted(expected_by_edition, key=lambda x: int(x)):
        expected = len(expected_by_edition[eid])
        actual = len(actual_by_edition[eid])
        validation.append({
            "validacion": "GUA_ROSTER_EDITION",
            "id_edicion": eid,
            "edicion": f"{editions[eid]['anio']} {editions[eid]['temporada']}",
            "esperado": str(expected),
            "actual": str(actual),
            "detalle": f"filas_participacion={rows_by_edition[eid]}",
            "estado": "PASS" if expected == actual else "FAIL",
        })
    validation.extend([
        {"validacion": "GUA_UNIQUE_OLYMPIC_IDS", "id_edicion": "", "edicion": "Olympic Games", "esperado": "263", "actual": str(len({r['id_atleta'] for r in gua_olympic_rows})), "detalle": "IDs únicos en participaciones GUA no Youth", "estado": "PASS" if len({r['id_atleta'] for r in gua_olympic_rows}) == 263 else "FAIL"},
        {"validacion": "GUA_OLYMPIC_PARTICIPATION_ROWS", "id_edicion": "", "edicion": "Olympic Games", "esperado": "585", "actual": str(len(gua_olympic_rows)), "detalle": "Filas válidas GUA; una persona puede tener varios eventos", "estado": "PASS" if len(gua_olympic_rows) == 585 else "FAIL"},
        {"validacion": "GUA_YOUTH_PRESERVED", "id_edicion": "", "edicion": "Youth Olympic Games", "esperado": "9", "actual": str(len(gua_youth_rows)), "detalle": "Filas fuera del padrón olímpico 263", "estado": "PASS" if len(gua_youth_rows) == 9 else "FAIL"},
        {"validacion": "PROCESSED_PARTICIPATION_ROWS", "id_edicion": "", "edicion": "participacion.csv", "esperado": "712020", "actual": str(len(read('participacion.csv'))), "detalle": "Conteo materializado", "estado": "PASS" if len(read('participacion.csv')) == 712020 else "FAIL"},
    ])
    with (OUT / "gua_canonical_validation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(validation[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(validation)
    print("GUA_CANONICAL_VALIDATION_COMPLETE")
    print(f"processed_files={len(processed_files)}")
    print(f"unchanged_files={sum(r['estado'] == 'MATCH' for r in manifest_rows)}")
    print(f"gua_olympic_ids={len({r['id_atleta'] for r in gua_olympic_rows})}")
    print(f"gua_olympic_rows={len(gua_olympic_rows)}")
    print(f"gua_youth_rows={len(gua_youth_rows)}")
    print(f"validation_failures={sum(r['estado'] == 'FAIL' for r in validation)}")


if __name__ == "__main__":
    main()
