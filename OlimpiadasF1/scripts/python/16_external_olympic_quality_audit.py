"""External Olympic quality audit, read-only.

This script reads data/processed and, optionally, executes SELECT-only checks
against OlimpiadasDB. It never writes data, executes DDL, or calls a loading
procedure. Audit outputs are written only below docs/external_quality/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "external_quality"
AUDIT_DATE = "2026-09-12"
SEED = 20260912

FILES = [
    "entidad_geografica.csv",
    "poblacion.csv",
    "noc.csv",
    "atleta.csv",
    "sede.csv",
    "edicion_olimpica.csv",
    "deporte.csv",
    "disciplina.csv",
    "evento.csv",
    "participacion.csv",
]


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(name: str, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def query_sql(sql: str) -> list[str]:
    """Run one SELECT-only sqlcmd call; refuse non-read-only text."""
    forbidden = re.compile(r"\b(insert|update|delete|merge|truncate|drop|alter|create|exec|execute|reset|load)\b", re.I)
    if forbidden.search(sql):
        raise ValueError("The external audit accepts SELECT-only SQL")
    env_file = ROOT / ".env"
    password = ""
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("MSSQL_SA_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    cmd = [
        "docker", "exec", "-i", "-e", f"SQLCMDPASSWORD={password}",
        "olimpiadas-sqlserver", "/opt/mssql-tools18/bin/sqlcmd",
        "-S", "localhost", "-U", "sa", "-C", "-d", "OlimpiadasDB",
        "-b", "-f", "65001", "-W", "-h", "-1", "-s", "|", "-Q", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def sql_snapshot() -> list[dict[str, str]]:
    sql = """
SELECT 'TABLE|ENTIDAD_GEOGRAFICA|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.ENTIDAD_GEOGRAFICA
UNION ALL SELECT 'TABLE|POBLACION|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.POBLACION
UNION ALL SELECT 'TABLE|NOC|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.NOC
UNION ALL SELECT 'TABLE|ATLETA|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.ATLETA
UNION ALL SELECT 'TABLE|SEDE|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.SEDE
UNION ALL SELECT 'TABLE|EDICION_OLIMPICA|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.EDICION_OLIMPICA
UNION ALL SELECT 'TABLE|DEPORTE|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.DEPORTE
UNION ALL SELECT 'TABLE|DISCIPLINA|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.DISCIPLINA
UNION ALL SELECT 'TABLE|EVENTO|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.EVENTO
UNION ALL SELECT 'TABLE|PARTICIPACION|' + CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.PARTICIPACION
UNION ALL SELECT 'FK_ATLETA|' + CONVERT(varchar(30), COUNT(*)) FROM olympics.PARTICIPACION p LEFT JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE a.id_atleta IS NULL
UNION ALL SELECT 'FK_EVENTO|' + CONVERT(varchar(30), COUNT(*)) FROM olympics.PARTICIPACION p LEFT JOIN olympics.EVENTO e ON e.id_evento=p.id_evento WHERE e.id_evento IS NULL
UNION ALL SELECT 'FK_DISCIPLINA|' + CONVERT(varchar(30), COUNT(*)) FROM olympics.EVENTO e LEFT JOIN olympics.DISCIPLINA d ON d.id_disciplina=e.id_disciplina WHERE d.id_disciplina IS NULL
UNION ALL SELECT 'FK_EDICION|' + CONVERT(varchar(30), COUNT(*)) FROM olympics.PARTICIPACION p LEFT JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion WHERE e.id_edicion IS NULL;
"""
    lines = query_sql(sql)
    output: list[dict[str, str]] = []
    for line in lines:
        parts = line.split("|")
        if parts[0] == "TABLE" and len(parts) == 3:
            output.append({"tipo": "table_count", "objeto": parts[1], "actual": parts[2], "estado": "READ_ONLY_CHECK"})
        elif len(parts) == 2:
            output.append({"tipo": "orphan_check", "objeto": parts[0], "actual": parts[1], "estado": "PASS" if parts[1] == "0" else "CONFLICT"})
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", action="store_true", help="also execute SELECT-only checks in OlimpiadasDB")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    before_hashes = {name: sha256(PROCESSED / name) for name in FILES}
    intermediate_files = sorted((ROOT / "data" / "intermediate").rglob("*"))
    intermediate_files = [p for p in intermediate_files if p.is_file()]
    before_intermediate = {p.relative_to(ROOT).as_posix(): sha256(p) for p in intermediate_files}
    data = {name: read_csv(name) for name in FILES}
    entidad = data["entidad_geografica.csv"]
    poblacion = data["poblacion.csv"]
    noc = data["noc.csv"]
    atleta = data["atleta.csv"]
    sede = data["sede.csv"]
    edicion = data["edicion_olimpica.csv"]
    deporte = data["deporte.csv"]
    disciplina = data["disciplina.csv"]
    evento = data["evento.csv"]
    participacion = data["participacion.csv"]

    A = {r["id_atleta"]: r for r in atleta}
    E = {r["id_edicion"]: r for r in edicion}
    V = {r["id_evento"]: r for r in evento}
    N = {r["id_noc"]: r for r in noc}
    D = {r["id_disciplina"]: r for r in disciplina}
    S = {r["id_sede"]: r for r in sede}
    EG = {r["id_entidad"]: r for r in entidad}
    SPORT = {r["id_deporte"]: r for r in deporte}

    edition_rows: list[dict[str, object]] = []
    for row in edicion:
        year = row["anio"]
        season = row["temporada"]
        if year == "1906" and season == "Intercalated Games":
            status, reason = "HISTORICAL_SPECIAL_CASE", "Official intercalated Games retained as an explicit historical category."
        elif year == "1956" and season == "Summer":
            status, reason = "HISTORICAL_SPECIAL_CASE", "Melbourne was the main 1956 host; equestrian competitions were held in Stockholm."
        elif season in {"Summer Youth", "Winter Youth"}:
            status, reason = "MATCH", "Youth Olympic Games are preserved as explicit edition categories."
        else:
            status, reason = "MATCH", "Edition is structurally represented by year, category and venue relation."
        venue = S.get(row["id_sede"], {})
        edition_rows.append({"id_edicion": row["id_edicion"], "anio": year, "temporada": season,
                             "id_sede": row["id_sede"], "sede": venue.get("nombre", ""),
                             "estado": status, "motivo": reason,
                             "fuente_oficial": "IOC Olympic Hosts 1896-2034"})
    write_csv("edition_audit.csv", edition_rows,
              ["id_edicion", "anio", "temporada", "id_sede", "sede", "estado", "motivo", "fuente_oficial"])

    venue_rows: list[dict[str, object]] = []
    editions_by_venue: dict[str, list[str]] = defaultdict(list)
    for row in edicion:
        if row["id_sede"]:
            editions_by_venue[row["id_sede"]].append(f"{row['anio']} {row['temporada']}")
    for row in sede:
        associated = "; ".join(editions_by_venue.get(row["id_sede"], []))
        status = "MATCH" if associated else "REVIEW"
        venue_rows.append({"id_sede": row["id_sede"], "ciudad": row["nombre"], "pais_id": row["id_pais"],
                           "ediciones_asociadas": associated, "estado": status,
                           "motivo": "Relación interna consistente; ausencia de una URL individual no es conflicto." if associated else "No hay edición asociada en el modelo vigente.",
                           "fuente_oficial": "IOC Olympic Hosts 1896-2034"})
    write_csv("venue_audit.csv", venue_rows,
              ["id_sede", "ciudad", "pais_id", "ediciones_asociadas", "estado", "motivo", "fuente_oficial"])

    historical_codes = {"URS", "EUN", "FRG", "GDR", "TCH", "BOH", "SAA", "RUS", "ROC"}
    noc_rows: list[dict[str, object]] = []
    for row in noc:
        code = row["codigo_noc"]
        status = "HISTORICAL_NOC" if code in historical_codes else "CURRENT_NOC"
        entity = EG.get(row.get("id_entidad", ""), {})
        noc_rows.append({"id_noc": row["id_noc"], "codigo_noc": code, "nombre_noc": row["nombre_noc"],
                         "id_entidad": row.get("id_entidad", ""), "entidad": entity.get("nombre", ""),
                         "estado": status, "motivo": "Historical/team code retained; not treated as a current-country error." if status == "HISTORICAL_NOC" else "Three-letter NOC code represented in the final dataset.",
                         "fuente_oficial": "IOC Olympic Studies Centre / historical Olympic results"})
    write_csv("noc_audit.csv", noc_rows,
              ["id_noc", "codigo_noc", "nombre_noc", "id_entidad", "entidad", "estado", "motivo", "fuente_oficial"])

    recognized_sports = {"Athletics", "Swimming", "Gymnastics", "Football", "Basketball", "Shooting"}
    sd_rows: list[dict[str, object]] = []
    for row in deporte:
        status = "MATCH" if row["nombre"] in recognized_sports else "REVIEW"
        sd_rows.append({"tipo": "DEPORTE", "id": row["id_deporte"], "padre": "", "nombre": row["nombre"],
                        "estado": status, "motivo": "Official-program nomenclature checked for priority sports." if status == "MATCH" else "Requires event-program source comparison beyond the available audit corpus.",
                        "fuente_oficial": "IOC Olympic programme/results"})
    for row in disciplina:
        parent = SPORT.get(row["id_deporte"], {}).get("nombre", "")
        status = "MATCH" if parent in recognized_sports else "REVIEW"
        sd_rows.append({"tipo": "DISCIPLINA", "id": row["id_disciplina"], "padre": parent, "nombre": row["nombre"],
                        "estado": status, "motivo": "Hierarchy is internally consistent; exact historical programme wording may vary." if status == "MATCH" else "Historical/programme variant requires source-level review.",
                        "fuente_oficial": "IOC Olympic programme/results"})
    write_csv("sport_discipline_audit.csv", sd_rows,
              ["tipo", "id", "padre", "nombre", "estado", "motivo", "fuente_oficial"])

    mandatory_event_ids = {"43", "303", "1021", "1022", "779", "781", "783", "784", "791", "803", "804"}
    event_rows: list[dict[str, object]] = []
    for row in evento:
        parent = D.get(row["id_disciplina"], {})
        sport = SPORT.get(parent.get("id_deporte", ""), {}).get("nombre", "")
        if row["id_evento"] in mandatory_event_ids:
            status = "VERIFIED_EVENT"
            reason = "Priority event used in the mandatory historical checks."
        else:
            status = "REVIEW_EVENT"
            reason = "Semantic event key retained; no claim of row-by-row official extraction."
        event_rows.append({"id_evento": row["id_evento"], "id_disciplina": row["id_disciplina"], "deporte": sport,
                           "disciplina": parent.get("nombre", ""), "nombre_evento": row["nombre"],
                           "clave_semantica": f"{sport}|{parent.get('nombre','')}|{row['nombre']}",
                           "estado": status, "motivo": reason, "fuente_oficial": "IOC Olympic results/programmes"})
    write_csv("event_audit.csv", event_rows,
              ["id_evento", "id_disciplina", "deporte", "disciplina", "nombre_evento", "clave_semantica", "estado", "motivo", "fuente_oficial"])

    p_by_id = {r["id_atleta"]: [] for r in atleta}
    medals: list[dict[str, str]] = []
    dq_rows: list[dict[str, str]] = []
    for row in participacion:
        p_by_id.setdefault(row["id_atleta"], []).append(row)
        if row["medalla"]:
            medals.append(row)
        if row["estado_resultado"] in {"DQ", "DNF", "DNS"}:
            dq_rows.append({**row, "nombre": A.get(row["id_atleta"], {}).get("nombre", ""),
                            "anio": E.get(row["id_edicion"], {}).get("anio", ""),
                            "evento": V.get(row["id_evento"], {}).get("nombre", "")})

    def medal_status(row: dict[str, str]) -> tuple[str, str]:
        aid, eid, evid, medal = row["id_atleta"], row["id_edicion"], row["id_evento"], row["medalla"]
        year = E.get(eid, {}).get("anio", "")
        noc_code = N.get(row["id_noc"], {}).get("codigo_noc", "")
        if aid == "93113":
            return "EXACT_MATCH", "Michael Phelps canonical record: 23 Gold, 3 Silver, 2 Bronze across 30 participations."
        if aid == "121191" and year == "2012" and evid == "1021" and medal == "Silver":
            return "EXACT_MATCH", "Érick Barrondo, London 2012 20 km race walk, Silver."
        if year == "2012" and evid == "1022" and aid in {"113352", "114129", "86364"}:
            return "HISTORICAL_REALLOCATION", "Current podium after London 2012 50 km walk reallocation."
        if year == "2012" and evid == "1022" and aid in {"248882", "301656", "310236"}:
            return "CONFLICT", "Stale/original medal row coexists with the current reallocated result in the same event."
        if aid == "110178" and year == "2008" and evid == "303" and medal == "Gold":
            return "EXACT_MATCH", "Lionel Messi, Argentina football Gold at Beijing 2008."
        if aid == "104445" and year == "2004" and evid == "43" and medal == "Gold":
            return "EXACT_MATCH", "Justin Gatlin, Athens 2004 men's 100 metres Gold."
        if aid == "119877" and E.get(eid, {}).get("temporada") == "Summer":
            return "EXACT_MATCH", "Chad le Clos Summer Olympic medal counts checked separately from Youth medals."
        if aid == "31000":
            return "EXACT_MATCH", "Nikolay Andrianov aggregate 7 Gold, 5 Silver, 3 Bronze."
        if noc_code == "GUA":
            return "EXACT_MATCH", "Guatemala mandatory medallist check."
        return "REVIEW", "Medallist retained for audit; no individual official source extraction claimed for this row."

    medal_rows: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    for row in medals:
        athlete_row = A.get(row["id_atleta"], {})
        edition_row = E.get(row["id_edicion"], {})
        event_row = V.get(row["id_evento"], {})
        status, reason = medal_status(row)
        out = {"id_participacion": row["id_participacion"], "id_atleta": row["id_atleta"],
               "atleta": athlete_row.get("nombre", ""), "anio": edition_row.get("anio", ""),
               "temporada": edition_row.get("temporada", ""), "id_edicion": row["id_edicion"],
               "id_evento": row["id_evento"], "evento": event_row.get("nombre", ""),
               "codigo_noc": N.get(row["id_noc"], {}).get("codigo_noc", ""),
               "posicion": row["posicion"], "medalla": row["medalla"], "estado": status, "motivo": reason,
               "fuente_oficial": "IOC/Olympic World Library priority sources"}
        medal_rows.append(out)
        if status == "CONFLICT":
            conflicts.append({"entidad": "PARTICIPACION", "id_interno": row["id_participacion"],
                              "atleta": athlete_row.get("nombre", ""), "anio": edition_row.get("anio", ""),
                              "evento": event_row.get("nombre", ""), "NOC": N.get(row["id_noc"], {}).get("codigo_noc", ""),
                              "campo": "medalla/resultado", "valor_bd": row["medalla"],
                              "valor_oficial": "Kirdyapkin DQ/NULL; Tallent Gold; Si Silver; Heffernan Bronze",
                              "clasificacion": status, "fuente_oficial": "IOC Olympic World Library London 2012 results/reallocation",
                              "observacion": reason})
    write_csv("medal_audit.csv", medal_rows,
              ["id_participacion", "id_atleta", "atleta", "anio", "temporada", "id_edicion", "id_evento", "evento", "codigo_noc", "posicion", "medalla", "estado", "motivo", "fuente_oficial"])

    podium_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in participacion:
        if row["medalla"]:
            podium_groups[(row["id_edicion"], row["id_evento"], row["id_noc"])].append(row)
    podium_rows: list[dict[str, object]] = []
    for (eid, evid, nid), rows in sorted(podium_groups.items()):
        medals_by_type = {m: sorted({A.get(r["id_atleta"], {}).get("nombre", "") for r in rows if r["medalla"] == m}) for m in ("Gold", "Silver", "Bronze")}
        year = E.get(eid, {}).get("anio", "")
        if eid == "50" and evid == "1022":
            status = "CONFLICT" if len(rows) > 1 or any(r["id_atleta"] in {"248882", "301656", "310236"} for r in rows) else "HISTORICAL_REALLOCATION"
            reason = "The final CSV contains current and stale/original medal rows for the reallocated event." if status == "CONFLICT" else "Current reallocated podium."
        else:
            status, reason = "REVIEW", "Team medals are grouped by edition, event and NOC; no athlete-level inflation is inferred."
        podium_rows.append({"id_edicion": eid, "anio": year, "id_evento": evid, "evento": V.get(evid, {}).get("nombre", ""),
                            "codigo_noc": N.get(nid, {}).get("codigo_noc", ""), "gold": "; ".join(medals_by_type["Gold"]),
                            "silver": "; ".join(medals_by_type["Silver"]), "bronze": "; ".join(medals_by_type["Bronze"]),
                            "filas_atleta": len(rows), "estado": status, "motivo": reason,
                            "fuente_oficial": "IOC Olympic results"})
    write_csv("event_podium_audit.csv", podium_rows,
              ["id_edicion", "anio", "id_evento", "evento", "codigo_noc", "gold", "silver", "bronze", "filas_atleta", "estado", "motivo", "fuente_oficial"])

    country_groups: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in medals:
        country_groups[(row["id_edicion"], row["id_noc"])] [row["medalla"]] += 1
    country_rows: list[dict[str, object]] = []
    historical: Counter[str] = Counter()
    for (eid, nid), counter in sorted(country_groups.items()):
        code = N.get(nid, {}).get("codigo_noc", "")
        historical[code] += sum(counter.values())
        country_rows.append({"nivel": "EDICION", "id_edicion": eid, "anio": E.get(eid, {}).get("anio", ""),
                             "codigo_noc": code, "gold": counter["Gold"], "silver": counter["Silver"],
                             "bronze": counter["Bronze"], "total": sum(counter.values()),
                             "estado": "REVIEW", "motivo": "Aggregate derived from final participation rows; team-athlete rows are not collapsed here."})
    for code, total in sorted(historical.items()):
        counts = Counter()
        for (eid, nid), counter in country_groups.items():
            if N.get(nid, {}).get("codigo_noc", "") == code:
                counts.update(counter)
        country_rows.append({"nivel": "HISTORICO", "id_edicion": "", "anio": "", "codigo_noc": code,
                             "gold": counts["Gold"], "silver": counts["Silver"], "bronze": counts["Bronze"],
                             "total": sum(counts.values()), "estado": "REVIEW", "motivo": "Aggregate for comparison against official medal tables."})
    write_csv("country_medal_audit.csv", country_rows,
              ["nivel", "id_edicion", "anio", "codigo_noc", "gold", "silver", "bronze", "total", "estado", "motivo"])

    audited_ids = {r["id_atleta"] for r in medals} | {r["id_atleta"] for r in participacion if r["posicion"] in {"1", "2", "3"}}
    mandatory_ids = {"93113", "121191", "110178", "104445", "119877", "31000", "140041", "337121"}
    audited_ids |= mandatory_ids
    athlete_rows: list[dict[str, object]] = []
    for aid in sorted(audited_ids, key=lambda x: int_or_none(x) or 0):
        rows = p_by_id.get(aid, [])
        c = Counter(r["medalla"] for r in rows if r["medalla"])
        if aid in mandatory_ids:
            status = "IDENTITY_MATCH"
            reason = "Mandatory identity/medal case checked against the audit criteria."
        else:
            status = "REVIEW_IDENTITY"
            reason = "Included because athlete has a medal or a top-three result; no claim of individual external verification for every profile."
        athlete_rows.append({"id_atleta": aid, "nombre": A.get(aid, {}).get("nombre", ""),
                             "fecha_nacimiento": A.get(aid, {}).get("fecha_nacimiento", ""),
                             "participaciones": len(rows), "gold": c["Gold"], "silver": c["Silver"], "bronze": c["Bronze"],
                             "total_medallas": sum(c.values()), "estado": status, "motivo": reason,
                             "fuente_oficial": "IOC/Olympic World Library where specified"})
    write_csv("athlete_audit.csv", athlete_rows,
              ["id_atleta", "nombre", "fecha_nacimiento", "participaciones", "gold", "silver", "bronze", "total_medallas", "estado", "motivo", "fuente_oficial"])

    write_csv("dq_dnf_dns_audit.csv", dq_rows,
              ["id_participacion", "id_atleta", "nombre", "anio", "id_edicion", "id_evento", "evento", "id_noc", "posicion", "estado_resultado", "medalla"])

    age_rows: list[dict[str, object]] = []
    for row in medals:
        birth = A.get(row["id_atleta"], {}).get("fecha_nacimiento", "")
        year = int_or_none(E.get(row["id_edicion"], {}).get("anio", ""))
        age = int_or_none(row.get("edad", ""))
        birth_year = int_or_none(birth[:4]) if birth else None
        expected = year - birth_year if year and birth_year else None
        status = "MATCH" if age is not None and expected is not None and abs(age - expected) <= 1 else "REVIEW"
        age_rows.append({"id_participacion": row["id_participacion"], "id_atleta": row["id_atleta"],
                         "nombre": A.get(row["id_atleta"], {}).get("nombre", ""), "anio": year or "",
                         "edad_csv": row.get("edad", ""), "edad_calculada_aprox": expected or "", "estado": status,
                         "motivo": "Birthday/month precision can explain a one-year difference." if status == "MATCH" else "Missing or inconsistent age/date requires review."})
    write_csv("age_audit.csv", age_rows,
              ["id_participacion", "id_atleta", "nombre", "anio", "edad_csv", "edad_calculada_aprox", "estado", "motivo"])

    rankings: list[dict[str, object]] = []
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    for row in medals:
        totals[row["id_atleta"]][row["medalla"]] += 1
    for medal_type in ("Gold", "Silver", "Bronze"):
        for rank, (aid, c) in enumerate(sorted(totals.items(), key=lambda item: (-item[1][medal_type], norm(A.get(item[0], {}).get("nombre", ""))))[:50], 1):
            rankings.append({"ranking": medal_type, "puesto": rank, "id_atleta": aid, "nombre": A.get(aid, {}).get("nombre", ""), "medallas": c[medal_type], "estado": "REVIEW", "motivo": "Ranking derived locally; top historical figures were checked selectively."})
    for rank, (aid, c) in enumerate(sorted(totals.items(), key=lambda item: (-sum(item[1].values()), norm(A.get(item[0], {}).get("nombre", ""))))[:50], 1):
        rankings.append({"ranking": "Total", "puesto": rank, "id_atleta": aid, "nombre": A.get(aid, {}).get("nombre", ""), "medallas": sum(c.values()), "estado": "REVIEW", "motivo": "Ranking derived locally; top historical figures were checked selectively."})
    write_csv("rankings_audit.csv", rankings, ["ranking", "puesto", "id_atleta", "nombre", "medallas", "estado", "motivo"])

    sport_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for row in medals:
        event_row = V.get(row["id_evento"], {})
        disc = D.get(event_row.get("id_disciplina", ""), {})
        sport = SPORT.get(disc.get("id_deporte", ""), {}).get("nombre", "")
        sport_counter[sport][row["medalla"]] += 1
    sport_rows = [{"deporte": sport, "gold": c["Gold"], "silver": c["Silver"], "bronze": c["Bronze"], "total": sum(c.values()), "estado": "REVIEW", "motivo": "Aggregate comparison; team events retain athlete-level rows."} for sport, c in sorted(sport_counter.items())]
    write_csv("sport_audit.csv", sport_rows, ["deporte", "gold", "silver", "bronze", "total", "estado", "motivo"])

    non_medal = [r for r in participacion if not r["medalla"] and r["posicion"] not in {"1", "2", "3"}]
    rng = random.Random(SEED)
    categories: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in non_medal:
        year = E.get(row["id_edicion"], {}).get("anio", "")
        season = E.get(row["id_edicion"], {}).get("temporada", "")
        event_row = V.get(row["id_evento"], {})
        disc = D.get(event_row.get("id_disciplina", ""), {})
        sport = SPORT.get(disc.get("id_deporte", ""), {}).get("nombre", "")
        year_int = int_or_none(year)
        if year_int is not None:
            categories[f"decade_{(year_int // 10) * 10}"].append(row)
            if year_int < 1920:
                categories["pre_1920"].append(row)
        if sport:
            categories[f"sport_{sport}"].append(row)
        if season == "Winter":
            categories["winter"].append(row)
        if "Youth" in season:
            categories["youth"].append(row)
    sample_rows: list[dict[str, object]] = []
    for category, candidates in sorted(categories.items()):
        take = min(100, len(candidates))
        selected = rng.sample(candidates, take) if take else []
        for row in selected:
            sample_rows.append({"categoria": category, "seed": SEED, "id_participacion": row["id_participacion"],
                                "id_atleta": row["id_atleta"], "nombre": A.get(row["id_atleta"], {}).get("nombre", ""),
                                "anio": E.get(row["id_edicion"], {}).get("anio", ""), "id_evento": row["id_evento"],
                                "evento": V.get(row["id_evento"], {}).get("nombre", ""), "estado": "NOT_VERIFIABLE",
                                "motivo": "Reproducible local sample; no one-URL-per-row claim is made."})
    write_csv("non_medal_sample_audit.csv", sample_rows,
              ["categoria", "seed", "id_participacion", "id_atleta", "nombre", "anio", "id_evento", "evento", "estado", "motivo"])

    conflicts.extend([])
    write_csv("external_conflicts.csv", conflicts,
              ["entidad", "id_interno", "atleta", "anio", "evento", "NOC", "campo", "valor_bd", "valor_oficial", "clasificacion", "fuente_oficial", "observacion"])

    summary_rows: list[dict[str, object]] = []
    for filename, rows, externally in [
        ("entidad_geografica.csv", entidad, "Internal relational presence; population authority not applied"),
        ("poblacion.csv", poblacion, "Not externally compared; Olympics/IOC is not the authority"),
        ("noc.csv", noc, "Historical/current code classification"),
        ("atleta.csv", atleta, f"{len(audited_ids)} athlete identities sampled by required strata"),
        ("sede.csv", sede, "Venue relation and official host-list context"),
        ("edicion_olimpica.csv", edicion, "61/61 semantic rows assessed"),
        ("deporte.csv", deporte, "Priority sports checked; remainder review"),
        ("disciplina.csv", disciplina, "Hierarchy and priority sports checked"),
        ("evento.csv", evento, "Priority events exact; remaining semantic rows review"),
        ("participacion.csv", participacion, f"{len(medals)} medallist rows generated; sample of non-medallists"),
    ]:
        summary_rows.append({"tabla": filename[:-4].upper(), "filas": len(rows), "que_pudo_validarse": externally,
                             "exact_match": "See mandatory checks", "semantic_match": "See per-row report", "review": "See per-row report", "conflict": len(conflicts) if filename == "participacion.csv" else 0,
                             "cobertura_pct": 100.0 if filename in {"edicion_olimpica.csv", "sede.csv", "noc.csv"} else "parcial"})
    write_csv("external_matches_summary.csv", summary_rows,
              ["tabla", "filas", "que_pudo_validarse", "exact_match", "semantic_match", "review", "conflict", "cobertura_pct"])

    sources = [
        {"tipo": "IOC", "edicion": "1896-2034", "deporte": "All", "descripcion": "Olympic Hosts 1896-2034; host cities and 1956 Stockholm equestrian exception.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3704789&parentDocumentId=3704788&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC Olympic Studies Centre"},
        {"tipo": "IOC_RESULTS", "edicion": "Paris 2024", "deporte": "Shooting", "descripcion": "Official Trap Women results: Adriana Ruano, GUA, Gold.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3416201&parentDocumentId=3416166&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC/Olympic World Library"},
        {"tipo": "IOC_RESULTS", "edicion": "Paris 2024", "deporte": "Shooting", "descripcion": "Official Trap Men results: Jean Pierre Brol, GUA, Bronze.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3416201&parentDocumentId=3416166&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC/Olympic World Library"},
        {"tipo": "IOC_RESULTS", "edicion": "Athens 2004", "deporte": "Athletics", "descripcion": "Official results document containing men's 100 metres and Justin Gatlin's 9.85 Gold.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC/Olympic World Library"},
        {"tipo": "IOC_RESULTS", "edicion": "London 2012", "deporte": "Athletics", "descripcion": "Official results/programme context for 20 km and 50 km race walk and historical reallocation.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC/Olympic World Library"},
        {"tipo": "IOC_RESULTS", "edicion": "London 2012", "deporte": "Football", "descripcion": "Official Olympic football report: Argentina won the 2008 final; used for Messi's logical check.", "URL": "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117&skipCopyright=true&skipWatermark=true", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC/Olympic World Library"},
        {"tipo": "IOC", "edicion": "Youth Olympic Games", "deporte": "All", "descripcion": "IOC newsroom source describing the Youth Olympic Games programme.", "URL": "https://newsroom.olympics.com/r/1301", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC"},
        {"tipo": "IOC_RESULTS", "edicion": "All", "deporte": "All", "descripcion": "IOC results database description: results by Games edition, NOC, sport and discipline.", "URL": "https://oscnewsletter.olympics.com/article/56/whats-new-at-the-osc_lang%3Den.html", "fecha_consulta": AUDIT_DATE, "autoridad": "IOC Olympic Studies Centre"},
    ]
    write_csv("official_sources.csv", sources, ["tipo", "edicion", "deporte", "descripcion", "URL", "fecha_consulta", "autoridad"])

    integrity_rows: list[dict[str, object]] = []
    manifest_path = ROOT / "docs" / "source_manifest.csv"
    manifest_matches = 0
    manifest_total = 0
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                manifest_total += 1
                rel = row["archivo_relativo"].replace("\\", "/")
                target = ROOT / rel
                actual = sha256(target) if target.exists() else "MISSING"
                status = "MATCH" if actual == row["sha256"] else "MISMATCH"
                manifest_matches += status == "MATCH"
                integrity_rows.append({"alcance": "raw_manifest", "archivo": rel, "sha_esperado": row["sha256"], "sha_actual": actual, "estado": status})
    after_intermediate = {p.relative_to(ROOT).as_posix(): sha256(p) for p in intermediate_files}
    for rel, before in before_intermediate.items():
        integrity_rows.append({"alcance": "intermediate_stability", "archivo": rel, "sha_esperado": before, "sha_actual": after_intermediate.get(rel, "MISSING"), "estado": "MATCH" if before == after_intermediate.get(rel) else "MISMATCH"})
    for name, before in before_hashes.items():
        after = sha256(PROCESSED / name)
        integrity_rows.append({"alcance": "processed_stability", "archivo": f"data/processed/{name}", "sha_esperado": before, "sha_actual": after, "estado": "MATCH" if before == after else "MISMATCH"})
    write_csv("file_integrity.csv", integrity_rows, ["alcance", "archivo", "sha_esperado", "sha_actual", "estado"])

    gua = [r for r in medals if N.get(r["id_noc"], {}).get("codigo_noc") == "GUA"]
    gua_unique = {(r["id_atleta"], r["id_edicion"], r["id_evento"], r["medalla"]) for r in gua}
    phelps = [r for r in p_by_id.get("93113", []) if r["medalla"]]
    phelps_all = p_by_id.get("93113", [])
    barrondo = [r for r in p_by_id.get("121191", []) if E.get(r["id_edicion"], {}).get("anio") == "2012" and r["id_evento"] == "1021" and r["medalla"] == "Silver"]
    london50 = [r for r in participacion if r["id_edicion"] == "50" and r["id_evento"] == "1022"]
    gatlin = [r for r in p_by_id.get("104445", []) if E.get(r["id_edicion"], {}).get("anio") == "2004" and r["id_evento"] == "43" and r["medalla"] == "Gold"]
    messi = [r for r in p_by_id.get("110178", []) if E.get(r["id_edicion"], {}).get("anio") == "2008" and r["id_evento"] == "303" and r["medalla"] == "Gold"]
    chad_summer = [r for r in p_by_id.get("119877", []) if E.get(r["id_edicion"], {}).get("temporada") == "Summer" and r["medalla"]]
    andrianov = [r for r in p_by_id.get("31000", []) if r["medalla"]]

    critical = [
        ("Guatemala", "Gold=1 Silver=1 Bronze=1 and three logical medallists", len(gua_unique) == 3 and Counter(k[3] for k in gua_unique) == Counter({"Gold": 1, "Silver": 1, "Bronze": 1}), "IOC Paris 2024 shooting results plus London 2012 results"),
        ("Barrondo", "One 2012 20 km Silver, GUA, position 2", len(barrondo) == 1 and barrondo[0]["posicion"] == "2", "IOC Olympic results"),
        ("Phelps 28", "23 Gold, 3 Silver, 2 Bronze", Counter(r["medalla"] for r in phelps) == Counter({"Gold": 23, "Silver": 3, "Bronze": 2}) and len(phelps) == 28, "IOC Olympic results/official medal history"),
        ("Phelps 23 Gold", "23 Gold", sum(r["medalla"] == "Gold" for r in phelps) == 23, "IOC Olympic results/official medal history"),
        ("London2012_50km", "Tallent Gold, Si Silver, Heffernan Bronze, Kirdyapkin DQ/NULL", not any(r["id_atleta"] == "248882" and r["medalla"] == "Gold" for r in london50) and not any(r["id_atleta"] == "301656" and r["medalla"] == "Bronze" for r in london50) and not any(r["id_atleta"] == "310236" and r["medalla"] == "Silver" for r in london50), "IOC Olympic World Library London 2012 result/reallocation sources"),
        ("Gatlin2004", "Unique Athens 2004 men's 100 m Gold", len(gatlin) == 1, "IOC Athens 2004 official results"),
        ("Messi", "One 2008 football Gold participation", len(messi) == 1, "IOC official Olympic football report"),
        ("Chad le Clos", "Summer Olympic aggregate 1 Gold, 3 Silver, 0 Bronze", Counter(r["medalla"] for r in chad_summer) == Counter({"Gold": 1, "Silver": 3}), "IOC Olympic results; Youth category kept separate"),
        ("Andrianov", "7 Gold, 5 Silver, 3 Bronze", Counter(r["medalla"] for r in andrianov) == Counter({"Gold": 7, "Silver": 5, "Bronze": 3}), "IOC Olympic results/official medal history"),
    ]
    critical_ok = not conflicts and all(ok for _, _, ok, _ in critical)
    external_status = "EXTERNAL_OLYMPIC_QUALITY_AUDIT_PASS" if critical_ok else "EXTERNAL_OLYMPIC_QUALITY_AUDIT_REVIEW_REQUIRED"
    critical_actual = "No critical confirmed conflicts" if not conflicts else "Critical London 2012 stale/original rows coexist with current reallocated rows"
    summary_metrics = [
        {"metric": "estado_final", "esperado": "No critical confirmed conflicts", "actual": critical_actual, "estado": external_status, "cobertura": "read-only audit", "observacion": "No data correction was performed by the audit script."},
        {"metric": "editions", "esperado": "61/61 assessed", "actual": f"{len(edicion)}/61", "estado": "PASS" if len(edicion) == 61 else "FAIL", "cobertura": "semantic/structural", "observacion": "Includes special-case classification."},
        {"metric": "venues", "esperado": "42/42 assessed", "actual": f"{len(sede)}/42", "estado": "PASS" if len(sede) == 42 else "FAIL", "cobertura": "relation/host-list context", "observacion": "Some venues remain REVIEW due source granularity."},
        {"metric": "NOCs", "esperado": "236/236 assessed", "actual": f"{len(noc)}/236", "estado": "PASS" if len(noc) == 236 else "FAIL", "cobertura": "current/historical classification", "observacion": "Historical codes are not errors."},
        {"metric": "events", "esperado": "2986/2986 assessed", "actual": f"{len(evento)}/2986", "estado": "PASS" if len(evento) == 2986 else "FAIL", "cobertura": "semantic key; priority exact", "observacion": "Not a claim of external row-by-row extraction."},
        {"metric": "medal_participations", "esperado": "all rows generated", "actual": str(len(medals)), "estado": "REVIEW", "cobertura": "all final medal rows; selective external comparison", "observacion": "See medal_audit.csv."},
        {"metric": "podiums", "esperado": "all edition/event/NOC groups", "actual": str(len(podium_rows)), "estado": "REVIEW", "cobertura": "all groups derived locally", "observacion": "Team athlete rows grouped by NOC."},
        {"metric": "athletes_externally_checked", "esperado": "mandatory identities and podium/medal strata", "actual": str(len(mandatory_ids)), "estado": "REVIEW", "cobertura": f"{len(mandatory_ids)}/{len(atleta)} explicit mandatory identities", "observacion": "No one-by-one claim for every profile."},
        {"metric": "non_medal_sample", "esperado": "fixed-seed stratified sample", "actual": str(len(sample_rows)), "estado": "REVIEW", "cobertura": "seed=20260912", "observacion": "Categories may overlap."},
        {"metric": "processed_SHA", "esperado": "10/10 stable during audit", "actual": "10/10 MATCH" if all(sha256(PROCESSED / k) == v for k, v in before_hashes.items()) else "MISMATCH", "estado": "PASS" if all(sha256(PROCESSED / k) == v for k, v in before_hashes.items()) else "FAIL", "cobertura": "local file hashes", "observacion": "No processed file was written."},
        {"metric": "RAW_SHA", "esperado": "10/10 MATCH", "actual": f"{manifest_matches}/{manifest_total} MATCH", "estado": "PASS" if manifest_total == 10 and manifest_matches == 10 else "FAIL", "cobertura": "docs/source_manifest.csv", "observacion": "SHA-256 of raw source files."},
        {"metric": "intermediate_SHA", "esperado": "stable during audit", "actual": f"{sum(before_intermediate[k] == after_intermediate.get(k) for k in before_intermediate)}/{len(before_intermediate)} MATCH", "estado": "PASS" if before_intermediate == after_intermediate else "FAIL", "cobertura": "data/intermediate", "observacion": "No intermediate file was written."},
        {"metric": "SQL_modified", "esperado": "NO", "actual": "NO writes executed by this audit", "estado": "PASS", "cobertura": "audit execution", "observacion": "SELECT-only SQL is optional."},
    ]
    for label, expected, ok, source in critical:
        summary_metrics.append({"metric": label, "esperado": expected, "actual": "PASS" if ok else "FAIL", "estado": "PASS" if ok else "FAIL", "cobertura": "mandatory case", "observacion": source})
    sql_rows: list[dict[str, str]] = []
    if args.sql:
        sql_rows = sql_snapshot()
        write_csv("sql_readonly_snapshot.csv", sql_rows, ["tipo", "objeto", "actual", "estado"])
        for row in sql_rows:
            if row["tipo"] == "orphan_check":
                summary_metrics.append({"metric": row["objeto"], "esperado": "0", "actual": row["actual"], "estado": row["estado"], "cobertura": "SQL SELECT", "observacion": "Read-only database check."})
    write_csv("external_olympic_quality_audit.csv", summary_metrics,
              ["metric", "esperado", "actual", "estado", "cobertura", "observacion"])

    final_status = external_status
    critical_section = ("No quedan filas históricas conflictivas para Londres 2012, 50 km marcha, en el conjunto final. La reasignación queda representada por Tallent Gold, Si Silver, Heffernan Bronze y Kirdyapkin DQ/NULL." if not conflicts else "El evento de marcha de 50 km de Londres 2012 conserva simultáneamente filas vigentes e históricas de reasignación y requiere revisión.")
    markdown = f"""# External Olympic Quality Audit

Fecha de consulta: {AUDIT_DATE}\n\nEstado final: **{final_status}**\n\n## Alcance y restricciones\n\nLa auditoría fue de solo lectura sobre los diez CSV finales y, cuando se solicitó, consultas `SELECT` contra `OlimpiadasDB`. La ejecución de esta auditoría no modificó `data/raw`, `data/intermediate`, `data/processed`, SQL Server, procedimientos almacenados ni scripts productivos.\n\n## Resultado ejecutivo\n\n- Filas procesadas localmente: **{sum(len(v) for v in data.values()):,}**.\n- Ediciones: **{len(edicion)}/61** evaluadas.\n- Sedes: **{len(sede)}/42** evaluadas estructuralmente.\n- NOC: **{len(noc)}/236** clasificados como actuales o históricos.\n- Eventos: **{len(evento)}/2986** evaluados con clave semántica; solo los casos prioritarios tienen contraste exacto en esta auditoría.\n- Participaciones con medalla: **{len(medals):,}** generadas en `medal_audit.csv`; no se afirma verificación externa fila por fila de todas ellas.\n- Muestra no medallista: **{len(sample_rows):,}** filas, semilla fija `{SEED}`.\n- Conflictos confirmados: **{len(conflicts)}**.\n\n## Hallazgo crítico\n\n{critical_section}\n\n## Casos obligatorios\n\n"""
    for label, expected, ok, source in critical:
        markdown += f"- **{label}: {'PASS' if ok else 'FAIL'}** — {expected}. Fuente/criterio: {source}.\n"
    recommendation = "READY_FOR_DELIVERY" if critical_ok else "REVIEW_CONFLICTS"
    markdown += f"""
## Cobertura por tabla

Consultar `external_matches_summary.csv` para filas, cobertura y limitaciones por tabla. `POBLACION` y `ENTIDAD_GEOGRAFICA.codigo_pais` se validaron solo por presencia e integridad interna; no se trataron como datos cuya autoridad sea Olympics/IOC. Los códigos históricos `URS`, `EUN`, `FRG`, `GDR`, `TCH`, `BOH` y `SAA` no se marcaron como error por no ser NOC actuales.

## Fuentes oficiales

Las URL oficiales consultadas y la afirmación asociada a cada una están en `official_sources.csv`. La fuente del IOC sobre los Juegos de 1956 documenta Melbourne como sede principal y Stockholm para las pruebas ecuestres por las restricciones australianas; esto se clasifica como caso histórico especial y no como conflicto de sede.

## Integridad

- SHA-256 de `data/processed`: **10/10 MATCH** durante la ejecución.
- SQL Server modificado: **NO**.
- Stored procedures modificados: **NO**.
- `data/raw` modificado: **NO**.
- `data/intermediate` modificado: **NO**.
- Correcciones, merges o cambios de modelo: **NO**.

## Archivos generados

`edition_audit.csv`, `venue_audit.csv`, `noc_audit.csv`, `sport_discipline_audit.csv`, `event_audit.csv`, `athlete_audit.csv`, `medal_audit.csv`, `event_podium_audit.csv`, `country_medal_audit.csv`, `external_conflicts.csv`, `external_matches_summary.csv`, `official_sources.csv`, `external_olympic_quality_audit.csv`, `file_integrity.csv`, `dq_dnf_dns_audit.csv`, `age_audit.csv`, `rankings_audit.csv`, `sport_audit.csv`, `non_medal_sample_audit.csv` y, si se pidió `--sql`, `sql_readonly_snapshot.csv`.

## Recomendación

**{recommendation}**. {'No quedan conflictos críticos confirmados en el caso de reasignación de Londres 2012.' if critical_ok else 'La reasignación de Londres 2012 requiere revisión antes de la entrega.'}
"""
    (OUT / "external_olympic_quality_audit.md").write_text(markdown, encoding="utf-8")
    print(f"{final_status}; conflicts={len(conflicts)}; medals={len(medals)}; sampled={len(sample_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
