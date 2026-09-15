"""Compara las filas GUA de Tokio 2020 con la delegación publicada por Olympedia.

Es una revisión no destructiva. No modifica CSV, SQL Server ni Stored Procedures.
"""
from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "quality"
OUT_CSV = OUT / "gua_2020_roster_review.csv"
OUT_MD = OUT / "gua_2020_roster_review.md"
REFERENCE = "https://www.olympedia.org/countries/GUA/editions/61"

OFFICIAL_NAMES = [
    "Luis Grijalva", "José Oswaldo Calel", "José Ortiz", "José Alejandro Barrondo",
    "Bernardo Barrondo", "Luis Ángel Sánchez", "Érick Barrondo", "Mirna Ortiz",
    "Mayra Herrera", "Kevin Cordón", "Nikté Sotomayor", "Manuel Rodas",
    "José Ramos", "Charles Fernández", "Yulisa López", "Jennieffer Zúñiga",
    "Juan Ignacio Maegli", "Isabella Maegli", "Juan Ramón Schaeffer",
    "Ana Waleska Soto", "Adriana Ruano", "Luis Martínez", "Gaby Santis",
    "Scarleth Ucelo",
]


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("�", "")
    return re.sub(r"[^a-z0-9]+", "", text)


def best_official_name(value: str) -> tuple[str, float]:
    candidate = normalize(value)
    scored = [(difflib.SequenceMatcher(None, candidate, normalize(name)).ratio(), name) for name in OFFICIAL_NAMES]
    score, name = max(scored)
    return name, score


def is_roster_match(value: str, official_name: str, score: float) -> bool:
    """Accept exact normalization or a tiny encoding-only difference.

    A partial name such as ``Angel Sanchez`` must not match ``Luis Angel
    Sanchez`` merely because its similarity score is high.
    """
    local = normalize(value)
    official = normalize(official_name)
    return local == official or (score >= 0.93 and abs(len(local) - len(official)) <= 2)


def main() -> None:
    athletes = read_csv("atleta.csv")
    participations = read_csv("participacion.csv")
    nocs = read_csv("noc.csv")
    editions = read_csv("edicion_olimpica.csv")
    athlete_by_id = {row["id_atleta"]: row for row in athletes}
    noc_by_id = {row["id_noc"]: row for row in nocs}
    edition_by_id = {row["id_edicion"]: row for row in editions}
    rows = [
        row for row in participations
        if noc_by_id.get(row.get("id_noc", ""), {}).get("codigo_noc") == "GUA"
        and edition_by_id.get(row.get("id_edicion", ""), {}).get("anio") == "2020"
    ]
    by_athlete: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_athlete[row["id_atleta"]].append(row)

    output: list[dict[str, str]] = []
    for row in rows:
        athlete = athlete_by_id.get(row["id_atleta"], {})
        name = athlete.get("nombre", "")
        official_name, score = best_official_name(name)
        in_roster = is_roster_match(name, official_name, score)
        same_athlete_rows = sorted(by_athlete[row["id_atleta"]], key=lambda item: int(item["id_participacion"]))
        duplicate_rank = next(index for index, item in enumerate(same_athlete_rows) if item["id_participacion"] == row["id_participacion"])
        if not in_roster:
            classification = "NOT_IN_2020_GUA_ROSTER"
            action = "REVIEW_MATCHING; probable_asociacion_incorrecta"
        elif duplicate_rank > 0:
            classification = "DUPLICATE_ROW_FOR_ROSTER_ATHLETE"
            action = "REVIEW_EVENT_MATCHING; no eliminar sin mapa de evento"
        else:
            classification = "ROSTER_MATCH"
            action = "NO_ACTION"
        output.append({
            "id_participacion": row["id_participacion"],
            "id_atleta": row["id_atleta"],
            "nombre_local": name,
            "nombre_referencia_mas_cercano": official_name if in_roster else "",
            "similitud": f"{score:.3f}",
            "id_evento": row["id_evento"],
            "posicion": row.get("posicion", ""),
            "clasificacion": classification,
            "accion": action,
            "referencia": REFERENCE,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(output[0]) if output else [
        "id_participacion", "id_atleta", "nombre_local", "nombre_referencia_mas_cercano",
        "similitud", "id_evento", "posicion", "clasificacion", "accion", "referencia",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    counts = Counter(row["clasificacion"] for row in output)
    unique_ids = len({row["id_atleta"] for row in rows})
    summary = [
        "# Revisión de la delegación GUA — 2020",
        "",
        "Estado: **DIAGNOSTIC_ONLY**",
        "",
        f"Referencia de contraste: [{REFERENCE}]({REFERENCE})",
        "",
        "## Resultado",
        "",
        f"- Filas GUA en el CSV: **{len(rows)}**.",
        f"- IDs de atleta GUA: **{unique_ids}**.",
        "- Delegación de referencia: **24 atletas**.",
        f"- Coincidencias de roster: **{counts['ROSTER_MATCH']}**.",
        f"- Filas duplicadas de un atleta que sí aparece en el roster: **{counts['DUPLICATE_ROW_FOR_ROSTER_ATHLETE']}**.",
        f"- Filas con nombre fuera del roster 2020: **{counts['NOT_IN_2020_GUA_ROSTER']}**.",
        "",
        "## Interpretación",
        "",
        "La comparación confirma una contaminación de matching en las filas GUA de 2020. El reporte no elimina ni reasigna filas: solo identifica las que requieren un mapa de corrección aprobado.",
        "",
        "## Archivo generado",
        "",
        f"- `{OUT_CSV.relative_to(ROOT)}`",
        "- Comando: `python scripts/python/25_review_gua_2020_roster.py`",
    ]
    OUT_MD.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("GUA_2020_ROSTER_REVIEW_COMPLETE")
    print(f"rows={len(rows)}")
    print(f"unique_ids={unique_ids}")
    print(dict(counts))
    print(f"output={OUT_CSV}")


if __name__ == "__main__":
    main()
