"""Rebuild the applied GUA exclusion report from the immutable backup."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "data" / "backup_before_gua_canonical_apply" / "participacion.csv"
FINAL = ROOT / "data" / "processed" / "participacion.csv"
ATLETA = ROOT / "data" / "processed" / "atleta.csv"
OUT = ROOT / "docs" / "quality" / "gua_removed_associations.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    final_ids = {row["id_participacion"] for row in rows(FINAL)}
    athlete_by_id = {row["id_atleta"]: row for row in rows(ATLETA)}
    removed = []
    for row in rows(BACKUP):
        if row["id_participacion"] in final_ids:
            continue
        athlete = athlete_by_id.get(row["id_atleta"], {})
        removed.append({
            "id_participacion": row["id_participacion"],
            "id_edicion": row["id_edicion"],
            "id_atleta": row["id_atleta"],
            "nombre": athlete.get("nombre", ""),
            "accion": "EXCLUDE_GUA_ASSOCIATION",
            "motivo": "La asociación GUA no está en el roster de referencia de su edición; se excluye del conjunto GUA procesado y se conserva en el backup para trazabilidad.",
            "estado": "REMOVED_FROM_GUA_ASSOCIATION",
        })
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(removed[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(removed)
    print(f"removed_report_rows={len(removed)}")


if __name__ == "__main__":
    main()
