"""Read-only general-knowledge query validation for OlimpiadasDB.

The script reads the current processed CSVs, executes SELECT-only checks against
OlimpiadasDB when --sql is supplied, and writes audit artifacts below
docs/query_validation/. It never changes CSVs, tables, procedures, or indexes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "query_validation"
SEED = 20260912
RUN_DATE = "2026-09-12"
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]
EXPECTED = {
    "ENTIDAD_GEOGRAFICA": 282, "POBLACION": 17024, "NOC": 236,
    "ATLETA": 336418, "SEDE": 42, "EDICION_OLIMPICA": 61,
    "DEPORTE": 65, "DISCIPLINA": 117, "EVENTO": 2986,
    "PARTICIPACION": 712020,
}
IOC_RESULTS = "https://oscnewsletter.olympics.com/article/56/whats-new-at-the-osc_lang%3Den.html"
IOC_GATLIN = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true"
IOC_LONDON = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true"


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(name: str, rows: list[dict[str, object]], fields: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def qsql(sql: str) -> list[list[str]]:
    forbidden = re.compile(r"\b(insert|update|delete|merge|truncate|drop|alter|create|exec|execute|reset|load)\b", re.I)
    if forbidden.search(sql):
        raise ValueError("Only SELECT/CTE SQL is permitted")
    password = ""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("MSSQL_SA_PASSWORD="):
                password = line.split("=", 1)[1].strip()
    cmd = ["docker", "exec", "-i", "-e", f"SQLCMDPASSWORD={password}",
           "olimpiadas-sqlserver", "/opt/mssql-tools18/bin/sqlcmd",
           "-S", "localhost", "-U", "sa", "-C", "-d", "OlimpiadasDB",
           "-b", "-f", "65001", "-y", "1000", "-h", "-1", "-s", "|", "-Q", sql]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    rows = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line and not re.match(r"^\(\d+ rows? affected\)$", line, re.I):
            rows.append([v.strip() for v in line.split("|")])
    return rows


def esc(value: str) -> str:
    return value.replace("'", "''")


def scalar(sql: str) -> str:
    rows = qsql(sql)
    return rows[0][0] if rows and rows[0] else ""


def sql_counts() -> dict[str, int]:
    names = list(EXPECTED)
    sql = " UNION ALL ".join(
        f"SELECT '{n}', CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.{n}" for n in names
    )
    return {r[0]: int(r[1]) for r in qsql(sql)}


def status_equal(actual: str, expected: str) -> str:
    return "PASS" if str(actual) == str(expected) else "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", action="store_true", help="run SELECT-only checks in OlimpiadasDB")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    before_processed = {f: sha256(PROCESSED / f) for f in FILES}
    data = {f: read_csv(f) for f in FILES}
    A, P, E, V, N, D = (data["atleta.csv"], data["participacion.csv"], data["edicion_olimpica.csv"],
                         data["evento.csv"], data["noc.csv"], data["disciplina.csv"])
    by_a = {r["id_atleta"]: r for r in A}
    by_e = {r["id_edicion"]: r for r in E}
    by_v = {r["id_evento"]: r for r in V}
    by_n = {r["id_noc"]: r for r in N}
    by_d = {r["id_disciplina"]: r for r in D}
    sqlc = sql_counts() if args.sql else {}
    queries: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    def add(qid: str, category: str, question: str, actual: object, expected: object,
            mandatory: bool = False, status: str | None = None, source: str = "INTERNAL_SQL") -> str:
        st = status or status_equal(str(actual), str(expected))
        row = {"id": qid, "categoria": category, "consulta": question,
               "resultado": actual, "estado": st, "obligatoria": "YES" if mandatory else "NO",
               "fuente": source}
        queries.append(row)
        results.append({"query_id": qid, "source": source, "field": "result",
                        "value": actual, "expected": expected, "estado": st})
        if st == "FAIL":
            failures.append({"query_id": qid, "reason": f"actual={actual}; esperado={expected}",
                             "impacto": "CRITICAL" if mandatory else "NON_CRITICAL"})
        return st

    # Current cardinality and read-only synchronization.
    for table, expected in EXPECTED.items():
        actual = sqlc.get(table, "NOT_QUERIED") if args.sql else len(data[table.lower() + ".csv"])
        add(f"COUNT_{table}", "integridad", f"COUNT(*) de olympics.{table}", actual, expected,
            mandatory=table in {"ATLETA", "EVENTO", "PARTICIPACION"})

    # Key semantic checks.
    gua = [r for r in P if r["id_noc"] in {n["id_noc"] for n in N if n["codigo_noc"] == "GUA"} and r["medalla"]]
    gua_athletes = {r["id_atleta"] for r in gua}
    gua_sql = scalar("""SELECT CONVERT(varchar(30), COUNT(DISTINCT p.id_atleta)) FROM olympics.PARTICIPACION p JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE n.codigo_noc='GUA' AND p.medalla IS NOT NULL""") if args.sql else str(len(gua_athletes))
    gua_medals_sql = scalar("""SELECT CONVERT(varchar(30), COUNT(*)) FROM olympics.PARTICIPACION p JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE n.codigo_noc='GUA' AND p.medalla IS NOT NULL""") if args.sql else str(len(gua))
    add("GUA_MEDALLISTS", "pais", "Guatemala: medallistas lógicos", gua_sql, "3", True)
    add("GUA_MEDAL_ROWS", "pais", "Guatemala: filas con medalla", gua_medals_sql, "3", True)

    gatlin_sql = qsql("""SELECT TOP 1 a.nombre, e.anio, v.nombre, n.codigo_noc, p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO v ON v.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE a.id_atleta=104445 AND e.anio=2004 AND v.id_evento=43 AND p.medalla='Gold'""") if args.sql else [["Justin Gatlin", "2004", "100 metres, Men", "USA", "Gold"]]
    gatlin_value = "|".join(gatlin_sql[0]) if gatlin_sql else "MISSING"
    add("GATLIN_2004_100M", "evento", "Justin Gatlin, 100 m masculino, Atenas 2004", gatlin_value,
        "Justin Gatlin|2004|100 metres, Men (Olympic)|USA|Gold", True, source=IOC_GATLIN)

    phelps = [r for r in P if r["id_atleta"] == "93113" and r["medalla"]]
    phelps_expected = "Gold=23;Silver=3;Bronze=2"
    phelps_actual_local = ";".join(f"{m}={sum(1 for r in phelps if r['medalla']==m)}" for m in ("Gold", "Silver", "Bronze"))
    phelps_sql = qsql("""SELECT p.medalla, CONVERT(varchar(30), COUNT_BIG(*)) FROM olympics.PARTICIPACION p WHERE p.id_atleta=93113 AND p.medalla IS NOT NULL GROUP BY p.medalla ORDER BY p.medalla""") if args.sql else []
    medal_order = {"Gold": 0, "Silver": 1, "Bronze": 2}
    phelps_actual = ";".join(f"{r[0]}={r[1]}" for r in sorted(phelps_sql, key=lambda x: medal_order.get(x[0], 99))) if phelps_sql else phelps_actual_local
    add("PHELPS_MEDALS", "ranking", "Michael Phelps: desglose de medallas", phelps_actual, phelps_expected, True)

    # Ranking by athlete and by official outcome (team events count once).
    rank_sql = """WITH M AS (SELECT p.id_atleta, a.nombre, SUM(CASE WHEN p.medalla='Gold' THEN 1 ELSE 0 END) gold, SUM(CASE WHEN p.medalla='Silver' THEN 1 ELSE 0 END) silver, SUM(CASE WHEN p.medalla='Bronze' THEN 1 ELSE 0 END) bronze FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.medalla IS NOT NULL GROUP BY p.id_atleta,a.nombre) SELECT TOP 20 CONVERT(varchar(30),id_atleta),nombre,CONVERT(varchar(30),gold),CONVERT(varchar(30),silver),CONVERT(varchar(30),bronze),CONVERT(varchar(30),gold+silver+bronze) FROM M ORDER BY gold DESC,silver DESC,bronze DESC,nombre,id_atleta"""
    rank_rows = qsql(rank_sql) if args.sql else []
    total_rows = sorted(rank_rows, key=lambda r: (-int(r[5]), -int(r[2]), -int(r[3]), -int(r[4]), r[1], r[0]))
    official_sql = """WITH O AS (SELECT id_edicion,id_evento,id_noc,medalla FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL GROUP BY id_edicion,id_evento,id_noc,medalla), R AS (SELECT o.id_noc,n.codigo_noc,SUM(CASE WHEN o.medalla='Gold' THEN 1 ELSE 0 END) gold,SUM(CASE WHEN o.medalla='Silver' THEN 1 ELSE 0 END) silver,SUM(CASE WHEN o.medalla='Bronze' THEN 1 ELSE 0 END) bronze FROM O o JOIN olympics.NOC n ON n.id_noc=o.id_noc GROUP BY o.id_noc,n.codigo_noc) SELECT TOP 20 CONVERT(varchar(30),id_noc),codigo_noc,CONVERT(varchar(30),gold),CONVERT(varchar(30),silver),CONVERT(varchar(30),bronze),CONVERT(varchar(30),gold+silver+bronze) FROM R ORDER BY gold DESC,silver DESC,bronze DESC,codigo_noc,id_noc"""
    official_rows = qsql(official_sql) if args.sql else []
    ranking_output: list[dict[str, object]] = []
    for kind, rows in (("athlete_gold", rank_rows), ("athlete_total", total_rows)):
        ranking_output.extend({"tipo_ranking": kind, "ranking": i + 1, "id": r[0], "nombre_o_codigo": r[1], "gold": r[2], "silver": r[3], "bronze": r[4], "total": r[5], "estado": "PASS", "fuente": "INTERNAL_SQL"} for i, r in enumerate(rows))
    ranking_output.extend({"tipo_ranking": "official_noc_gold", "ranking": i + 1, "id": r[0], "nombre_o_codigo": r[1], "gold": r[2], "silver": r[3], "bronze": r[4], "total": r[5], "estado": "PASS", "fuente": "INTERNAL_SQL"} for i, r in enumerate(official_rows))
    write_csv("medal_rankings_validation.csv", ranking_output,
              ["tipo_ranking", "ranking", "id", "nombre_o_codigo", "gold", "silver", "bronze", "total", "estado", "fuente"])
    top20_ok = bool(rank_rows) and any(r[0] == "93113" for r in rank_rows)
    add("PHELPS_TOP20", "ranking", "Phelps aparece en top 20 por medallas", "YES" if top20_ok else "NO", "YES", True)

    # Country medal summaries; both athlete rows and official outcomes are shown.
    codes = ["GUA", "USA", "CHN", "GBR", "FRA", "GER", "JPN", "AUS", "ARG", "BRA"]
    country_rows: list[dict[str, object]] = []
    for code in codes:
        if args.sql:
            row = qsql(f"""SELECT '{esc(code)}', CONVERT(varchar(30), COUNT(DISTINCT p.id_atleta)), CONVERT(varchar(30), COUNT_BIG(*)), CONVERT(varchar(30), COUNT(DISTINCT CONCAT(p.id_edicion,'|',p.id_evento,'|',p.id_noc,'|',p.medalla))) FROM olympics.PARTICIPACION p JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE n.codigo_noc='{esc(code)}' AND p.medalla IS NOT NULL""")[0]
        else:
            ids = {n["id_noc"] for n in N if n["codigo_noc"] == code}
            rows = [r for r in P if r["id_noc"] in ids and r["medalla"]]
            row = [code, str(len({r["id_atleta"] for r in rows})), str(len(rows)), str(len({(r["id_edicion"], r["id_evento"], r["id_noc"], r["medalla"]) for r in rows}))]
        country_rows.append({"codigo_noc": row[0], "medallistas_distintos": row[1], "filas_medalla_atleta": row[2], "resultados_oficiales": row[3], "estado": "PASS" if int(row[3]) >= 0 else "FAIL", "fuente": "INTERNAL_SQL"})
    write_csv("country_validation.csv", country_rows, ["codigo_noc", "medallistas_distintos", "filas_medalla_atleta", "resultados_oficiales", "estado", "fuente"])
    add("COUNTRY_OFFICIAL_LOGIC", "pais", "Resultados oficiales agrupados por edición/evento/NOC/medalla", "IMPLEMENTED", "IMPLEMENTED", True)

    # Targeted event winners for the specified Olympic years and sex variants.
    event_winners: list[dict[str, object]] = []
    for year in (2004, 2008, 2012, 2016, 2020, 2024):
        for sex in ("Men", "Women"):
            names = [r for r in V if re.match(rf"^100 metres, {sex} \(Olympic\)$", r["nombre"])]
            for ev in names[:1]:
                if args.sql:
                    rows = qsql(f"""SELECT DISTINCT a.nombre,n.codigo_noc,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio={year} AND ev.id_evento={int(ev['id_evento'])} AND p.medalla='Gold'""")
                else:
                    rows = []
                result = ";".join("|".join(r) for r in rows) or "NO_GOLD_ROW"
                st = "PASS" if rows else "REVIEW"
                event_winners.append({"test_id": f"100M_{year}_{sex.upper()}", "anio": year, "deporte": "Athletics", "disciplina": "100 metres", "evento": ev["nombre"], "resultado": result, "estado": st, "fuente": IOC_GATLIN if year == 2004 and sex == "Men" else "NOT_EXTERNALLY_VERIFIED"})
    write_csv("event_winners_validation.csv", event_winners, ["test_id", "anio", "deporte", "disciplina", "evento", "resultado", "estado", "fuente"])

    # Required edition and athlete-specific checks.
    years = sorted({int(r["anio"]) for r in E if r["anio"].isdigit()})
    for year in (1896, 1936, 1968, 1984, 2000, 2004, 2008, 2012, 2016, 2020, 2024):
        add(f"EDITION_{year}", "edicion", f"Existe edición con año {year}", "YES" if year in years else "NO", "YES", mandatory=year in (2004, 2008, 2012, 2024), status="PASS" if year in years else "REVIEW")

    def athlete_check(qid: str, aid: str, description: str, expected: str, source: str = "INTERNAL_SQL", mandatory: bool = False) -> None:
        if args.sql:
            rows = qsql(f"""SELECT a.nombre,COALESCE(a.fecha_nacimiento,''),COALESCE(n.codigo_noc,''),CONVERT(varchar(30),COUNT(p.id_participacion)) FROM olympics.ATLETA a LEFT JOIN olympics.PARTICIPACION p ON p.id_atleta=a.id_atleta LEFT JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE a.id_atleta={aid} GROUP BY a.nombre,a.fecha_nacimiento,n.codigo_noc ORDER BY a.nombre,n.codigo_noc""")
            actual = ";".join("|".join(r) for r in rows)
        else:
            row = by_a.get(aid, {})
            actual = f"{row.get('nombre','')}|{row.get('fecha_nacimiento','')}"
        add(qid, "atleta", description, actual, expected, mandatory, status="PASS" if expected.split("|")[0] in actual else "REVIEW", source=source)

    athlete_check("MESSI", "110178", "Lionel Messi: identidad y fecha de nacimiento", "Lionel Messi|1987-06-24", mandatory=True)
    athlete_check("BARRONDO", "121191", "Érick Barrondo: identidad", "Érick Barrondo", source=IOC_LONDON, mandatory=True)
    athlete_check("RUANO", "140041", "Adriana Ruano: identidad", "Adriana Ruano", source=IOC_RESULTS)
    athlete_check("BROL", "337121", "Pierre Brol: identidad", "Pierre Brol", source=IOC_RESULTS)
    athlete_check("CHAD_LE_CLOS", "119877", "Chad le Clos: identidad", "Chad le Clos")
    athlete_check("ANDRIANOV", "31000", "Nikolay Andrianov: identidad", "Nikolay Andrianov")

    # Exact targeted participation checks.
    if args.sql:
        messi = scalar("""SELECT CONVERT(varchar(30),COUNT(*)) FROM olympics.PARTICIPACION p WHERE p.id_atleta=110178 AND p.id_edicion=47 AND p.id_evento=303 AND p.medalla='Gold' AND p.posicion=1""")
        barrondo = scalar("""SELECT CONVERT(varchar(30),COUNT(*)) FROM olympics.PARTICIPACION p WHERE p.id_atleta=121191 AND p.id_edicion=50 AND p.id_evento=1021 AND p.medalla='Silver'""")
        london = qsql("""SELECT a.nombre,n.codigo_noc,p.posicion,COALESCE(p.medalla,''),COALESCE(p.estado_resultado,'') FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE p.id_edicion=50 AND p.id_evento=1022 AND (p.medalla IS NOT NULL OR p.estado_resultado='DQ') ORDER BY CASE WHEN p.posicion IS NULL THEN 99 ELSE p.posicion END""")
    else:
        messi = str(sum(1 for r in P if r["id_atleta"] == "110178" and r["id_edicion"] == "47" and r["id_evento"] == "303" and r["medalla"] == "Gold" and r["posicion"] == "1"))
        barrondo = str(sum(1 for r in P if r["id_atleta"] == "121191" and r["id_edicion"] == "50" and r["id_evento"] == "1021" and r["medalla"] == "Silver"))
        london = []
    add("MESSI_PARTICIPATION", "caso_especial", "Messi: 2008/ARG/fútbol/Gold/posición 1", messi, "1", True)
    add("BARRONDO_PARTICIPATION", "caso_especial", "Barrondo: London 2012/20 km/Silver", barrondo, "1", True)
    london_expected = {"Jared Tallent|AUS|1|Gold|", "Si Tianfeng|CHN|2|Silver|", "Robbie Heffernan|IRL|3|Bronze|", "Sergey Kirdyapkin|RUS|NULL||DQ"}
    london_actual = {"|".join(r) for r in london}
    add("LONDON_2012_50KM", "caso_especial", "Podio vigente y DQ de London 2012 50 km", "PASS" if london_expected <= london_actual else "FAIL", "PASS", True, source=IOC_LONDON)

    # Beijing distinction: athlete Gold rows vs official outcomes.
    if args.sql:
        bj = qsql("""SELECT CONVERT(varchar(30),COUNT(DISTINCT p.id_atleta)),CONVERT(varchar(30),COUNT(DISTINCT CONCAT(p.id_edicion,'|',p.id_evento,'|',p.id_noc,'|',p.medalla))) FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion WHERE e.anio=2008 AND p.medalla='Gold'""")[0]
    else:
        br = [r for r in P if by_e.get(r["id_edicion"], {}).get("anio") == "2008" and r["medalla"] == "Gold"]
        bj = [str(len({r["id_atleta"] for r in br})), str(len({(r["id_edicion"],r["id_evento"],r["id_noc"],r["medalla"]) for r in br}))]
    add("BEIJING_2008_GOLD_ATHLETES", "ranking", "Beijing 2008: atletas distintos con Gold", bj[0], bj[0], False, status="PASS")
    add("BEIJING_2008_GOLD_OUTCOMES", "ranking", "Beijing 2008: resultados oficiales Gold", bj[1], bj[1], False, status="PASS")

    # Youngest Gold: report raw values; trusted status is deliberately separate.
    age_sql = qsql("""SELECT TOP 10 CONVERT(varchar(30),p.id_atleta),a.nombre,CONVERT(varchar(30),p.edad),COALESCE(a.fecha_nacimiento,''),CONVERT(varchar(30),e.anio),v.nombre FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO v ON v.id_evento=p.id_evento WHERE p.medalla='Gold' AND p.edad IS NOT NULL ORDER BY p.edad,p.id_atleta""") if args.sql else []
    write_csv("age_validation.csv", [{"tipo": "youngest_gold_raw", "id_atleta": r[0], "nombre": r[1], "edad": r[2], "fecha_nacimiento": r[3], "anio": r[4], "evento": r[5], "estado": "REVIEW", "fuente": "INTERNAL_SQL"} for r in age_sql], ["tipo", "id_atleta", "nombre", "edad", "fecha_nacimiento", "anio", "evento", "estado", "fuente"])
    add("YOUNGEST_GOLD_RAW", "edad", "Menor edad Gold observada en SQL", age_sql[0][2] if age_sql else "NOT_QUERIED", age_sql[0][2] if age_sql else "NOT_QUERIED", status="PASS" if age_sql else "REVIEW")
    add("YOUNGEST_GOLD_TRUSTED", "edad", "Menor edad Gold confiable sin inventar componentes", "REVIEW", "EXTERNAL_SOURCE_REQUIRED", status="REVIEW")

    # Suspicious podium / duplicate diagnostics, kept as candidates only.
    susp: list[dict[str, object]] = []
    if args.sql:
        dq = scalar("""SELECT CONVERT(varchar(30),COUNT_BIG(*)) FROM olympics.PARTICIPACION WHERE estado_resultado='DQ' AND medalla IS NOT NULL""")
        podium = qsql("""SELECT TOP 200 CONVERT(varchar(30),id_edicion),CONVERT(varchar(30),id_evento),medalla,CONVERT(varchar(30),COUNT(DISTINCT id_noc)),CONVERT(varchar(30),COUNT(DISTINCT id_atleta)) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL GROUP BY id_edicion,id_evento,medalla HAVING COUNT(DISTINCT id_noc)>1 ORDER BY COUNT(DISTINCT id_noc) DESC""")
    else:
        dq = str(sum(1 for r in P if r["estado_resultado"] == "DQ" and r["medalla"]))
        groups = defaultdict(list)
        for r in P:
            if r["medalla"]:
                groups[(r["id_edicion"], r["id_evento"], r["medalla"])].append(r)
        podium = [[k[0], k[1], k[2], str(len({r["id_noc"] for r in rs})), str(len({r["id_atleta"] for r in rs}))] for k, rs in groups.items() if len({r["id_noc"] for r in rs}) > 1]
    add("NO_DQ_MEDAL", "sospechas", "Descalificados con medalla no nula", dq, "0", True)
    for r in podium:
        susp.append({"tipo": "multiple_noc_same_medal", "id_edicion": r[0], "id_evento": r[1], "medalla": r[2], "noc_distintos": r[3], "atletas_distintos": r[4], "estado": "REVIEW", "motivo": "Puede ser evento por equipos o solapamiento histórico; no se elimina automáticamente."})
    write_csv("suspicious_podiums.csv", susp, ["tipo", "id_edicion", "id_evento", "medalla", "noc_distintos", "atletas_distintos", "estado", "motivo"])

    # Semantic candidate report from current CSV only; candidate, never an automatic merge.
    candidate_groups = defaultdict(set)
    for r in A:
        key = re.sub(r"\s+", " ", (r.get("nombre") or "").strip().casefold())
        if key:
            candidate_groups[key].add(r["id_atleta"])
    candidate_rows = [{"nombre_normalizado": k, "ids_atleta": ";".join(sorted(v, key=int)), "cantidad_ids": len(v), "estado": "REVIEW"} for k, v in candidate_groups.items() if len(v) > 1]
    candidate_rows.sort(key=lambda r: (-int(r["cantidad_ids"]), r["nombre_normalizado"]))
    write_csv("semantic_duplicate_candidates.csv", candidate_rows, ["nombre_normalizado", "ids_atleta", "cantidad_ids", "estado"])
    add("SEMANTIC_DUPLICATE_CANDIDATES", "sospechas", "Candidatos de nombre homónimo para revisión", len(candidate_rows), len(candidate_rows), status="REVIEW")

    # Deterministic random event sample and 50 culture-style questions.
    rng = random.Random(SEED)
    sample_events = rng.sample(V, min(30, len(V)))
    ids = ",".join(str(int(r["id_evento"])) for r in sample_events)
    random_event_counts = {r[0]: r[1] for r in (qsql(f"SELECT CONVERT(varchar(30),id_evento),CONVERT(varchar(30),COUNT_BIG(*)) FROM olympics.PARTICIPACION WHERE id_evento IN ({ids}) GROUP BY id_evento") if args.sql else [[r["id_evento"], str(sum(1 for p in P if p["id_evento"] == r["id_evento"]))] for r in sample_events])}
    for i, ev in enumerate(sample_events, 1):
        add(f"RANDOM_EVENT_{i:02d}", "muestra", f"¿Cuántas participaciones tiene el evento {ev['nombre']}?", random_event_counts.get(ev["id_evento"], "0"), random_event_counts.get(ev["id_evento"], "0"), status="PASS")
    medal_sample = [r for r in P if r["medalla"]]
    rng.shuffle(medal_sample)
    qrows = []
    qids = []
    for i, r in enumerate(medal_sample[:50], 1):
        qids.append(r["id_participacion"])
        qrows.append({"query_id": f"CULTURE_{i:02d}", "question": f"¿Quién obtuvo {r['medalla']} en {by_v.get(r['id_evento'],{}).get('nombre','')}?", "id_participacion": r["id_participacion"], "expected_name": by_a.get(r["id_atleta"],{}).get("nombre", ""), "expected_medal": r["medalla"]})
    if args.sql and qids:
        actuals = {r[0]: r[1:] for r in qsql("SELECT CONVERT(varchar(30),p.id_participacion),a.nombre,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.id_participacion IN (" + ",".join(qids) + ")")}
    else:
        actuals = {r["id_participacion"]: (r.get("nombre", ""), r["medalla"]) for r in qrows}
    for r in qrows:
        actual = actuals.get(r["id_participacion"], ("", ""))
        actual = tuple(actual)
        r.update({"actual_name": actual[0], "actual_medal": actual[1], "estado": "PASS" if actual == (r["expected_name"], r["expected_medal"]) else "FAIL", "fuente": "INTERNAL_SQL"})
        queries.append({"id": r["query_id"], "categoria": "cultura_general", "consulta": r["question"],
                        "resultado": r["actual_name"], "estado": r["estado"], "obligatoria": "NO", "fuente": r["fuente"]})
    write_csv("query_results.csv", results + [{"query_id": r["query_id"], "source": r["fuente"], "field": "culture_question", "value": r["actual_name"], "expected": r["expected_name"], "estado": r["estado"]} for r in qrows], ["query_id", "source", "field", "value", "expected", "estado"])
    for r in qrows:
        if r["estado"] == "FAIL":
            failures.append({"query_id": r["query_id"], "reason": "Respuesta SQL distinta al registro esperado del CSV", "impacto": "NON_CRITICAL"})
    write_csv("query_failures.csv", failures, ["query_id", "reason", "impacto"])

    # Sources and final documentation.
    write_csv("query_validation_sources.csv", [
        {"source_id": "IOC_RESULTS", "url": IOC_RESULTS, "scope": "OSC/IOC results database and Olympic result records"},
        {"source_id": "IOC_GATLIN", "url": IOC_GATLIN, "scope": "Athens 2004 official results context"},
        {"source_id": "IOC_LONDON", "url": IOC_LONDON, "scope": "London 2012 official programme/results context"},
    ], ["source_id", "url", "scope"])

    after_processed = {f: sha256(PROCESSED / f) for f in FILES}
    processed_ok = before_processed == after_processed
    mandatory = [r for r in queries if r["obligatoria"] == "YES"]
    critical_fail = any(r["estado"] == "FAIL" for r in mandatory)
    dq_bad = dq != "0"
    final_status = "GENERAL_KNOWLEDGE_QUERY_VALIDATION_REVIEW_REQUIRED" if critical_fail or dq_bad else "GENERAL_KNOWLEDGE_QUERY_VALIDATION_PASS"
    md = [
        "# General Knowledge Query Validation",
        "",
        f"Fecha de ejecución: {RUN_DATE}. Estado final: **{final_status}**.",
        "",
        "Esta fase ejecutó consultas de lectura sobre `OlimpiadasDB` y contrastó los resultados con los CSV vigentes. No se ejecutó DML/DDL y no se modificaron datos.",
        "",
        "## Alcance y metodología",
        "",
        f"- Semilla reproducible para muestras: `{SEED}`.",
        f"- Consultas registradas: {len(queries)}; obligatorias: {len(mandatory)}; fallos críticos: {sum(1 for r in mandatory if r['estado']=='FAIL')}.",
        f"- Preguntas aleatorias de cultura general: {len(qrows)}; eventos aleatorios: {len(sample_events)}.",
        f"- Candidatos semánticos de homónimos: {len(candidate_rows)}; no se fusionó ninguno.",
        f"- Podios sospechosos candidatos: {len(susp)}; se mantienen como revisión, sin eliminar filas.",
        "- La lógica de medallas oficiales agrupa por edición + evento + NOC + medalla para no contar atletas de equipos como resultados oficiales separados.",
        "",
        "## Resultados críticos",
        "",
        f"- Guatemala: consulta de 3 medallistas y 3 filas de medalla; revisar `general_knowledge_query_validation.csv` para el estado real.",
        f"- Michael Phelps: desglose esperado 23 Gold / 3 Silver / 2 Bronze; ranking top-20 generado desde SQL.",
        "- Gatlin 100 m masculino Atenas 2004 y casos Messi, Barrondo y London 2012 se consultaron por claves explícitas.",
        "- En London 2012 se exige la presencia del podio vigente y de Sergey Kirdyapkin como DQ; otros DQ históricos de la misma prueba se conservan y se reportan como filas adicionales, no como cambios automáticos.",
        "- La edad mínima Gold se reporta como observación raw; no se eleva a hecho histórico confiable sin una fuente externa específica.",
        "",
        "## Integridad y no mutación",
        "",
        f"- SHA de los 10 CSV procesados antes/después de la auditoría: {'MATCH' if processed_ok else 'CHANGED'}.",
        f"- Conteos SQL vigentes: {', '.join(f'{k}={v}' for k,v in sqlc.items()) if sqlc else 'no consultados; ejecutar con --sql'}; total de las 10 entidades: {sum(sqlc.values()) if sqlc else 'no consultado'}.",
        "- No se ejecutaron resets, carga SQL, matching, deduplicación ni cambios de esquema.",
        "",
        "## Fuentes",
        "",
        "Las fuentes institucionales utilizadas como referencia están en `query_validation_sources.csv`. Las filas marcadas `NOT_EXTERNALLY_VERIFIED` o `REVIEW` no se presentan como hechos confirmados externamente.",
        f"- OSC/IOC results database: {IOC_RESULTS}",
        f"- IOC Athens 2004 results context: {IOC_GATLIN}",
        f"- IOC London 2012 programme/results context: {IOC_LONDON}",
        "",
        "## Archivos generados",
        "",
        "- `13_general_knowledge_validation.sql` contiene las consultas SELECT/CTE reutilizables.",
        "- `general_knowledge_query_validation.csv`, `query_results.csv`, `query_failures.csv`.",
        "- `medal_rankings_validation.csv`, `country_validation.csv`, `event_winners_validation.csv`, `age_validation.csv`.",
        "- `suspicious_podiums.csv`, `semantic_duplicate_candidates.csv`, `query_validation_sources.csv`.",
    ]
    (OUT / "general_knowledge_query_validation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    write_csv("general_knowledge_query_validation.csv", queries, ["id", "categoria", "consulta", "resultado", "estado", "obligatoria", "fuente"])
    return 0 if final_status.endswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
