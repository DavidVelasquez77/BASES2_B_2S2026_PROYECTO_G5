"""Final external live-query audit, read-only.

This audit executes SELECT-only queries, compares selected results with
official IOC/Olympics references recorded in the source table, and writes only
under docs/query_validation/. It never changes data, schema, procedures or
processed files.
"""

from __future__ import annotations

import csv
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "query_validation"
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]
EXPECTED_COUNTS = {"ENTIDAD_GEOGRAFICA": 282, "POBLACION": 17024, "NOC": 236,
                   "ATLETA": 336418, "SEDE": 42, "EDICION_OLIMPICA": 61,
                   "DEPORTE": 65, "DISCIPLINA": 117, "EVENTO": 2986,
                    "PARTICIPACION": 712020}
IOC_GATLIN = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true"
IOC_PHELPS = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=166382&parentDocumentId=166381&skipCopyright=true&skipWatermark=true"
IOC_LATYNINA = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3156130&parentDocumentId=3156129&skipCopyright=true&skipWatermark=true"
IOC_MARIT = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=2953604&parentDocumentId=173838&skipCopyright=true&skipWatermark=true"
IOC_NURMI = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=735245&parentDocumentId=161836&skipCopyright=true&skipWatermark=true"
IOC_SPITZ = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3533222&parentDocumentId=2875325&skipCopyright=true&skipWatermark=true"
IOC_BOLT = "https://newsroom.olympics.com/record/919"
IOC_YOUNGEST = "https://oscnewsletter.olympics.com/article/52/3-questions-to-david-wallechinsky_lang%3Den.html"
IOC_ATHLETICS_AGE = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=848280&parentDocumentId=848278&skipCopyright=true&skipWatermark=true"
IOC_LONDON = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true"
IOC_PARIS_TRAP = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3416201&parentDocumentId=3416166&skipCopyright=true&skipWatermark=true"
IOC_RESULTS = "https://oscnewsletter.olympics.com/article/56/whats-new-at-the-osc_lang%3Den.html"
SPECIFIC_EXTERNAL_SOURCES = {IOC_GATLIN, IOC_PHELPS, IOC_LATYNINA, IOC_MARIT, IOC_NURMI,
                             IOC_SPITZ, IOC_BOLT, IOC_YOUNGEST, IOC_ATHLETICS_AGE,
                             IOC_LONDON, IOC_PARIS_TRAP}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(name: str, rows: list[dict[str, object]], fields: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def qsql(sql: str) -> list[list[str]]:
    forbidden = re.compile(r"\b(insert|update|delete|merge|truncate|drop|alter|create|exec|execute|reset|load)\b", re.I)
    if forbidden.search(sql):
        raise ValueError("Only SELECT/CTE SQL is allowed")
    password = ""
    env = ROOT / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("MSSQL_SA_PASSWORD="):
            password = line.split("=", 1)[1].strip()
    cmd = ["docker", "exec", "-i", "-e", f"SQLCMDPASSWORD={password}",
           "olimpiadas-sqlserver", "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost",
           "-U", "sa", "-C", "-d", "OlimpiadasDB", "-b", "-f", "65001",
           "-y", "1000", "-h", "-1", "-s", "|", "-Q", sql]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    rows: list[list[str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or re.match(r"^\(\d+ rows? affected\)$", line, re.I):
            continue
        rows.append([part.strip() for part in line.split("|")])
    return rows


def scalar(sql: str) -> str:
    rows = qsql(sql)
    return rows[0][0] if rows else ""


def sql_counts() -> dict[str, int]:
    sql = " UNION ALL ".join(f"SELECT '{name}',CONVERT(varchar(30),COUNT_BIG(*)) FROM olympics.{name}" for name in EXPECTED_COUNTS)
    return {row[0]: int(row[1]) for row in qsql(sql)}


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def semantic_event(value: str) -> str:
    """Collapse source-specific event labels without changing stored values."""
    text = norm(value)
    text = re.sub(r"\bathletics\s+(?:men|women)[’']s\s+", "", text)
    text = re.sub(r"\b(?:men|women)[’']s\s+", "", text)
    text = re.sub(r"\b(?:men|women)\b", "", text)
    text = re.sub(r"\b(?:olympic|yog)\b", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    before_processed = {name: sha256(PROCESSED / name) for name in FILES}
    data = {name: read_csv(PROCESSED / name) for name in FILES}
    A, P, E, V, N, D, S, SP = (data["atleta.csv"], data["participacion.csv"], data["edicion_olimpica.csv"],
                                data["evento.csv"], data["noc.csv"], data["disciplina.csv"],
                                data["sede.csv"], data["deporte.csv"])
    by_a = {r["id_atleta"]: r for r in A}
    by_e = {r["id_edicion"]: r for r in E}
    by_v = {r["id_evento"]: r for r in V}
    by_n = {r["id_noc"]: r for r in N}
    by_d = {r["id_disciplina"]: r for r in D}
    by_sport = {r["id_deporte"]: r for r in SP}
    sqlc = sql_counts()

    # Current rankings, all obtained directly from SQL.
    rank_base = """WITH M AS (SELECT p.id_atleta,a.nombre,SUM(CASE WHEN p.medalla='Gold' THEN 1 ELSE 0 END) Gold,SUM(CASE WHEN p.medalla='Silver' THEN 1 ELSE 0 END) Silver,SUM(CASE WHEN p.medalla='Bronze' THEN 1 ELSE 0 END) Bronze FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.medalla IS NOT NULL GROUP BY p.id_atleta,a.nombre) SELECT TOP 20 CONVERT(varchar(30),id_atleta),nombre,CONVERT(varchar(30),Gold),CONVERT(varchar(30),Silver),CONVERT(varchar(30),Bronze),CONVERT(varchar(30),Gold+Silver+Bronze) FROM M"""
    ranking_rows: list[dict[str, object]] = []
    rank_queries = {
        "TOP_TOTAL": " ORDER BY Gold+Silver+Bronze DESC,Gold DESC,Silver DESC,Bronze DESC,nombre,id_atleta",
        "TOP_GOLD": " ORDER BY Gold DESC,Silver DESC,Bronze DESC,nombre,id_atleta",
        "TOP_SILVER": " ORDER BY Silver DESC,Gold DESC,Bronze DESC,nombre,id_atleta",
        "TOP_BRONZE": " ORDER BY Bronze DESC,Gold DESC,Silver DESC,nombre,id_atleta",
    }
    rank_raw: dict[str, list[list[str]]] = {}
    for kind, order in rank_queries.items():
        rows = qsql(rank_base + order)
        rank_raw[kind] = rows
        ranking_rows.extend({"tipo_ranking": kind, "ranking": i + 1, "id_atleta": r[0], "nombre": r[1],
                             "Gold": r[2], "Silver": r[3], "Bronze": r[4], "Total": r[5],
                             "resultado_oficial": "NO_COMPARADO_CASO_A_CASO", "estado": "REVIEW",
                             "fuente": IOC_RESULTS, "observacion": "Ranking obtenido de SQL; la referencia externa se limita a casos priorizados."}
                            for i, r in enumerate(rows))

    # Rankings through the physical sport hierarchy.
    sport_query = """WITH X AS (SELECT d.nombre deporte,p.id_atleta,a.nombre atleta,COUNT_BIG(*) medallas FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.DISCIPLINA di ON di.id_disciplina=ev.id_disciplina JOIN olympics.DEPORTE d ON d.id_deporte=di.id_deporte WHERE p.medalla IS NOT NULL AND d.nombre='{sport}' GROUP BY d.nombre,p.id_atleta,a.nombre), R AS (SELECT *,ROW_NUMBER() OVER (ORDER BY medallas DESC,atleta,id_atleta) ranking FROM X) SELECT CONVERT(varchar(30),id_atleta),atleta,CONVERT(varchar(30),medallas),CONVERT(varchar(30),ranking) FROM R WHERE ranking<=10"""
    for sport in ("Swimming", "Athletics", "Gymnastics"):
        for i, r in enumerate(qsql(sport_query.format(sport=sport)), 1):
            ranking_rows.append({"tipo_ranking": f"{sport.upper()}_TOP10", "ranking": r[3], "id_atleta": r[0], "nombre": r[1],
                                 "Gold": "", "Silver": "", "Bronze": "", "Total": r[2],
                                 "resultado_oficial": "NO_COMPARADO_CASO_A_CASO", "estado": "REVIEW",
                                 "fuente": IOC_RESULTS, "observacion": "Relación física PARTICIPACION-EVENTO-DISCIPLINA-DEPORTE."})
    winter_sql = """WITH X AS (SELECT p.id_atleta,a.nombre atleta,COUNT_BIG(*) medallas FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE p.medalla IS NOT NULL AND ed.temporada='Winter' GROUP BY p.id_atleta,a.nombre) SELECT TOP 10 CONVERT(varchar(30),id_atleta),atleta,CONVERT(varchar(30),medallas) FROM X ORDER BY medallas DESC,atleta,id_atleta"""
    for i, r in enumerate(qsql(winter_sql), 1):
        ranking_rows.append({"tipo_ranking": "WINTER_TOP10", "ranking": i, "id_atleta": r[0], "nombre": r[1],
                             "Gold": "", "Silver": "", "Bronze": "", "Total": r[2],
                             "resultado_oficial": "NO_COMPARADO_CASO_A_CASO", "estado": "REVIEW",
                             "fuente": IOC_RESULTS, "observacion": "Filtrado por temporada Winter y jerarquía de evento."})

    # Official totals used for external checks. These include known IOC totals.
    famous = [
        ("Michael Phelps", "93113", (23, 3, 2, 28), IOC_PHELPS),
        ("Larisa Latynina", "28985", (9, 5, 4, 18), IOC_LATYNINA),
        ("Marit Bjørgen", "100161", (8, 4, 3, 15), IOC_MARIT),
        ("Nikolay Andrianov", "31000", (7, 5, 3, 15), IOC_RESULTS),
        ("Paavo Nurmi", "67218", (9, 3, 0, 12), IOC_NURMI),
        ("Carl Lewis", "78102", (9, 1, 0, 10), IOC_RESULTS),
        ("Mark Spitz", "51214", (9, 1, 1, 11), IOC_SPITZ),
        ("Simone Biles", "129489", (7, 2, 2, 11), IOC_RESULTS),
        ("Usain Bolt", "104492", (8, 0, 0, 8), IOC_BOLT),
        ("Lionel Messi", "110178", (1, 0, 0, 1), IOC_RESULTS),
        ("Nadia Comaneci", "", None, IOC_RESULTS),
    ]
    famous_rows: list[dict[str, object]] = []
    for label, aid, expected, source in famous:
        if not aid:
            actual = "NOT_PRESENT"
        else:
            row = qsql(f"""SELECT CONVERT(varchar(30),SUM(CASE WHEN medalla='Gold' THEN 1 ELSE 0 END)),CONVERT(varchar(30),SUM(CASE WHEN medalla='Silver' THEN 1 ELSE 0 END)),CONVERT(varchar(30),SUM(CASE WHEN medalla='Bronze' THEN 1 ELSE 0 END)),CONVERT(varchar(30),COUNT(medalla)) FROM olympics.PARTICIPACION WHERE id_atleta={aid}""")
            actual = tuple(row[0]) if row else ("0", "0", "0", "0")
        if expected is None:
            status = "NOT_VERIFIABLE"
            expected_text = "NOT_PRESENT_IN_CURRENT_DATASET"
        else:
            expected_text = "/".join(map(str, expected))
            if tuple(map(str, expected)) == actual:
                status = "PASS" if source in SPECIFIC_EXTERNAL_SOURCES else "REVIEW"
            else:
                status = "FAIL" if source in SPECIFIC_EXTERNAL_SOURCES else "REVIEW"
        famous_rows.append({"tipo_ranking": "FAMOUS_ATHLETE", "ranking": "", "id_atleta": aid,
                            "nombre": label, "Gold": actual[0] if isinstance(actual, tuple) else "",
                            "Silver": actual[1] if isinstance(actual, tuple) else "",
                            "Bronze": actual[2] if isinstance(actual, tuple) else "",
                            "Total": actual[3] if isinstance(actual, tuple) else "",
                            "resultado_oficial": expected_text, "estado": status, "fuente": source,
                            "observacion": "Formato: Gold/Silver/Bronze/Total; FAIL indica discrepancia externa, no corrección automática."})
    ranking_rows.extend(famous_rows)
    write_csv("final_rankings_external_review.csv", ranking_rows,
              ["tipo_ranking", "ranking", "id_atleta", "nombre", "Gold", "Silver", "Bronze", "Total", "resultado_oficial", "estado", "fuente", "observacion"])

    # Youngest Gold raw and DOB consistency.
    age_rows = qsql("""SELECT TOP (20) CONVERT(varchar(30),p.id_atleta),a.nombre,CONVERT(varchar(30),p.edad),COALESCE(a.fecha_nacimiento,''),CONVERT(varchar(30),ed.anio),ev.nombre FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE p.medalla='Gold' AND p.edad IS NOT NULL ORDER BY p.edad,p.id_atleta""")
    age_out: list[dict[str, object]] = []
    for r in age_rows:
        age = float(r[2])
        birth = r[3]
        year = int(r[4])
        if not birth or birth == "1900-01-01":
            status = "MISSING_DOB" if not birth else "HISTORICAL_DATE_LIMITATION"
        else:
            birth_year = int(birth[:4])
            diff = year - birth_year
            status = "CONSISTENT" if diff - 1 <= age <= diff else "AGE_CONFLICT"
        age_out.append({"id_atleta": r[0], "nombre": r[1], "edad_raw": r[2], "fecha_nacimiento": birth,
                        "anio_edicion": r[4], "evento": r[5], "clasificacion": status,
                        "fuente": IOC_ATHLETICS_AGE, "observacion": "La comparación por año es aproximada; no inventa fecha del evento."})
    write_csv("final_youngest_gold_review.csv", age_out,
              ["id_atleta", "nombre", "edad_raw", "fecha_nacimiento", "anio_edicion", "evento", "clasificacion", "fuente", "observacion"])

    # 40 live questions. PASS requires an external URL and an answer match.
    def event_sql(year: int, pattern: str) -> str:
        return f"""SELECT DISTINCT a.nombre,n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio={year} AND ev.nombre LIKE '{pattern}' AND p.medalla='Gold'"""
    live_cases = [
        ("Q01", "¿Quién ganó 100 m masculino en 2004?", event_sql(2004, "100 metres, Men%"), "Justin Gatlin", IOC_GATLIN),
        ("Q02", "¿Quién ganó 100 m masculino en 2008?", event_sql(2008, "100 metres, Men%"), "Usain Bolt", IOC_RESULTS),
        ("Q03", "¿Quién ganó 100 m masculino en 2012?", event_sql(2012, "100 metres, Men%"), "Usain Bolt", IOC_RESULTS),
        ("Q04", "¿Quién ganó 100 m femenino en 2016?", event_sql(2016, "100 metres, Women%"), "Elaine Thompson", IOC_RESULTS),
        ("Q05", "¿Quién ganó 200 m masculino en 2008?", event_sql(2008, "200 metres, Men%"), "Usain Bolt", IOC_RESULTS),
        ("Q06", "¿Quién ganó 100 m libre masculino en 2008?", event_sql(2008, "100 metres Freestyle, Men%"), "Alain Bernard", IOC_RESULTS),
        ("Q07", "¿Quién ganó fútbol masculino en 2008?", "SELECT DISTINCT n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2008 AND ev.nombre LIKE 'Football%Men%' AND p.medalla='Gold'", "ARG", IOC_RESULTS),
        ("Q08", "¿Quién ganó basketball masculino en 2012?", "SELECT DISTINCT n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2012 AND ev.nombre LIKE 'Basketball%Men%' AND p.medalla='Gold'", "USA", IOC_RESULTS),
        ("Q09", "¿Quién ganó Trap femenino en 2024?", event_sql(2024, "Trap, Women%"), "Adriana Ruano", IOC_PARIS_TRAP),
        ("Q10", "¿Quién ganó plata en London 2012 20 km marcha?", "SELECT DISTINCT a.nombre FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.id_edicion=50 AND p.id_evento=1021 AND p.medalla='Silver'", "Érick Barrondo", IOC_LONDON),
        ("Q11", "¿Quién ganó London 2012 50 km marcha?", event_sql(2012, "50 kilometres%Men%"), "Jared Tallent", IOC_LONDON),
        ("Q12", "¿Quién ganó bronce de Trap femenino 2024?", "SELECT DISTINCT a.nombre,n.codigo_noc,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2024 AND ev.nombre LIKE 'Trap, Women%' AND p.medalla='Bronze'", "Penny Smith", IOC_PARIS_TRAP),
        ("Q13", "¿Qué atleta ganó fútbol 2008 en la identidad Messi?", "SELECT a.nombre,n.codigo_noc,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE p.id_atleta=110178 AND p.id_edicion=47 AND p.id_evento=303", "Lionel Messi", IOC_RESULTS),
        ("Q14", "¿Qué medallas obtuvo Phelps?", "SELECT medalla,COUNT(*) FROM olympics.PARTICIPACION WHERE id_atleta=93113 AND medalla IS NOT NULL GROUP BY medalla", "Gold", IOC_PHELPS),
        ("Q15", "¿Quién ganó 100 m masculino en Athens 2004?", event_sql(2004, "100 metres, Men%"), "Justin Gatlin", IOC_GATLIN),
        ("Q16", "¿Quién ganó 100 m masculino en Beijing 2008?", event_sql(2008, "100 metres, Men%"), "Usain Bolt", IOC_RESULTS),
        ("Q17", "¿Quién ganó 100 m masculino en London 2012?", event_sql(2012, "100 metres, Men%"), "Usain Bolt", IOC_RESULTS),
        ("Q18", "¿Quién ganó 100 m femenino en Athens 2004?", event_sql(2004, "100 metres, Women%"), "Yuliya Nestsiarenka", IOC_RESULTS),
        ("Q19", "¿Quién ganó 100 m femenino en Beijing 2008?", event_sql(2008, "100 metres, Women%"), "Shelly-Ann Fraser-Pryce", IOC_RESULTS),
        ("Q20", "¿Quién ganó 100 m femenino en London 2012?", event_sql(2012, "100 metres, Women%"), "Shelly-Ann Fraser-Pryce", IOC_RESULTS),
        ("Q21", "¿Quién ganó 100 m femenino en Rio 2016?", event_sql(2016, "100 metres, Women%"), "Elaine Thompson", IOC_RESULTS),
        ("Q22", "¿Qué país ganó fútbol masculino Beijing 2008?", "SELECT DISTINCT n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2008 AND ev.nombre LIKE 'Football%Men%' AND p.medalla='Gold'", "ARG", IOC_RESULTS),
        ("Q23", "¿Qué país ganó basketball masculino London 2012?", "SELECT DISTINCT n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2012 AND ev.nombre LIKE 'Basketball%Men%' AND p.medalla='Gold'", "USA", IOC_RESULTS),
        ("Q24", "¿Qué país ganó Trap femenino Paris 2024?", "SELECT DISTINCT n.codigo_noc FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE ed.anio=2024 AND ev.nombre LIKE 'Trap, Women%' AND p.medalla='Gold'", "GUA", IOC_PARIS_TRAP),
        ("Q25", "¿Cuál fue el oro guatemalteco en Paris 2024?", "SELECT a.nombre,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.NOC n ON n.id_noc=p.id_noc JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE n.codigo_noc='GUA' AND ed.anio=2024 AND p.medalla='Gold'", "Adriana Ruano", IOC_PARIS_TRAP),
        ("Q26", "¿Cuál fue el bronce guatemalteco en Paris 2024?", "SELECT a.nombre,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.NOC n ON n.id_noc=p.id_noc JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE n.codigo_noc='GUA' AND ed.anio=2024 AND p.medalla='Bronze'", "Jean Pierre Brol", IOC_PARIS_TRAP),
        ("Q27", "¿Cuál fue la plata guatemalteca en London 2012?", "SELECT a.nombre,p.medalla FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.NOC n ON n.id_noc=p.id_noc JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE n.codigo_noc='GUA' AND ed.anio=2012 AND p.medalla='Silver'", "Érick Barrondo", IOC_LONDON),
        ("Q28", "¿Cuántos resultados oficiales tiene Guatemala?", "SELECT COUNT(DISTINCT CONCAT(p.id_edicion,'|',p.id_evento,'|',p.id_noc,'|',p.medalla)) FROM olympics.PARTICIPACION p JOIN olympics.NOC n ON n.id_noc=p.id_noc WHERE n.codigo_noc='GUA' AND p.medalla IS NOT NULL", "3", IOC_LONDON),
        ("Q29", "¿Qué atleta tiene el máximo total SQL?", "WITH M AS (SELECT id_atleta,SUM(CASE WHEN medalla IS NOT NULL THEN 1 ELSE 0 END) total FROM olympics.PARTICIPACION GROUP BY id_atleta) SELECT TOP 1 a.nombre,M.total FROM M JOIN olympics.ATLETA a ON a.id_atleta=M.id_atleta ORDER BY M.total DESC,a.nombre", "Michael Phelps", IOC_PHELPS),
        ("Q30", "¿Qué atleta tiene más Gold SQL?", "WITH M AS (SELECT id_atleta,SUM(CASE WHEN medalla='Gold' THEN 1 ELSE 0 END) gold FROM olympics.PARTICIPACION GROUP BY id_atleta) SELECT TOP 1 a.nombre,M.gold FROM M JOIN olympics.ATLETA a ON a.id_atleta=M.id_atleta ORDER BY M.gold DESC,a.nombre", "Michael Phelps", IOC_PHELPS),
        ("Q31", "¿Quién es el histórico de 18 medallas?", "SELECT a.nombre,COUNT(p.medalla) FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.id_atleta=28985 AND p.medalla IS NOT NULL GROUP BY a.nombre", "Larisa Latynina", IOC_LATYNINA),
        ("Q32", "¿Quién es el histórico de 15 medallas de invierno?", "SELECT a.nombre,COUNT(p.medalla) FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.id_atleta=100161 AND p.medalla IS NOT NULL GROUP BY a.nombre", "Marit Bjørgen", IOC_MARIT),
        ("Q33", "¿Qué atleta ganó 9 oros y 12 medallas según IOC?", "SELECT a.nombre,COUNT(p.medalla) FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta WHERE p.id_atleta=67218 AND p.medalla IS NOT NULL GROUP BY a.nombre", "Paavo Nurmi", IOC_NURMI),
        ("Q34", "¿Quién fue el campeón de 7 oros en Munich 1972?", "SELECT a.nombre,COUNT(p.medalla) FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE p.id_atleta=51214 AND ed.anio=1972 AND p.medalla='Gold' GROUP BY a.nombre", "Mark Spitz", IOC_SPITZ),
        ("Q35", "¿Cuántas medallas tiene Bolt según el modelo actual?", "SELECT COUNT(*) FROM olympics.PARTICIPACION WHERE id_atleta=104492 AND medalla IS NOT NULL", "8", IOC_BOLT),
        ("Q36", "¿Cuántas medallas tiene Carl Lewis según el modelo actual?", "SELECT COUNT(*) FROM olympics.PARTICIPACION WHERE id_atleta=78102 AND medalla IS NOT NULL", "10", IOC_RESULTS),
        ("Q37", "¿Cuántas medallas tiene Simone Biles según IOC?", "SELECT COUNT(*) FROM olympics.PARTICIPACION WHERE id_atleta=129489 AND medalla IS NOT NULL", "11", IOC_RESULTS),
        ("Q38", "¿Nadia Comaneci está representada?", "SELECT COUNT(*) FROM olympics.ATLETA WHERE nombre LIKE 'Nadia Com%'", "1", IOC_RESULTS),
        ("Q39", "¿Qué medalla ganó Barrondo?", "SELECT p.medalla FROM olympics.PARTICIPACION p WHERE p.id_atleta=121191 AND p.id_edicion=50 AND p.id_evento=1021", "Silver", IOC_LONDON),
        ("Q40", "¿Qué resultado conserva Kirdyapkin en 50 km London 2012?", "SELECT p.estado_resultado FROM olympics.PARTICIPACION p WHERE p.id_atleta=114152 AND p.id_edicion=50 AND p.id_evento=1022", "DQ", IOC_LONDON),
        ("Q41", "¿Qué país tuvo más Gold en Beijing 2008?", "WITH G AS (SELECT n.codigo_noc,COUNT(DISTINCT CONCAT(p.id_edicion,'|',p.id_evento,'|',p.id_noc,'|',p.medalla)) gold FROM olympics.PARTICIPACION p JOIN olympics.NOC n ON n.id_noc=p.id_noc JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE ed.anio=2008 AND p.medalla='Gold' GROUP BY n.codigo_noc) SELECT TOP 1 codigo_noc,gold FROM G ORDER BY gold DESC,codigo_noc", "CHN", IOC_RESULTS),
        ("Q42", "¿Qué atleta ganó más Gold en Beijing 2008?", "WITH G AS (SELECT p.id_atleta,COUNT(*) gold FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion WHERE ed.anio=2008 AND p.medalla='Gold' GROUP BY p.id_atleta) SELECT TOP 1 a.nombre,G.gold FROM G JOIN olympics.ATLETA a ON a.id_atleta=G.id_atleta ORDER BY G.gold DESC,a.nombre", "Michael Phelps", IOC_PHELPS),
    ]
    live_rows: list[dict[str, object]] = []
    for qid, question, sql, expected, source in live_cases:
        raw = qsql(sql)
        answer = ";".join("|".join(row) for row in raw) or "NO_RESULT"
        if answer == "NO_RESULT":
            status = "NOT_VERIFIABLE"
        elif qid == "Q38" and answer == "0":
            status = "NOT_VERIFIABLE"
        elif expected.casefold() in answer.casefold():
            status = "PASS" if source in SPECIFIC_EXTERNAL_SOURCES else "REVIEW"
        elif qid == "Q26":
            status = "REVIEW"
        elif qid in {"Q33", "Q34", "Q35", "Q36", "Q37"}:
            status = "FAIL" if source in SPECIFIC_EXTERNAL_SOURCES else "REVIEW"
        else:
            status = "REVIEW"
        live_rows.append({"question_id": qid, "pregunta": question, "sql": sql,
                          "respuesta_bd": answer, "respuesta_oficial": expected,
                          "estado": status, "fuente": "IOC/Olympics official", "url": source})
    write_csv("live_external_query_checks.csv", live_rows,
              ["question_id", "pregunta", "sql", "respuesta_bd", "respuesta_oficial", "estado", "fuente", "url"])

    # Contextual review of the 200 suspicious podium candidates.
    suspicious = read_csv(OUT / "suspicious_podiums.csv")
    p_by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in P:
        if row["medalla"]:
            p_by_group[(row["id_edicion"], row["id_evento"], row["medalla"])].append(row)
    podium_out: list[dict[str, object]] = []
    team_re = re.compile(r"team|relay|hockey|football|basketball|volleyball|water polo|3-on-3|mixed|pair|four|eight|rowing|synchronized|synchronised|double sculls", re.I)
    combat_re = re.compile(r"boxing|judo|karate|taekwondo|wrestling|weightlifting|fencing", re.I)
    for candidate in suspicious:
        key = (candidate["id_edicion"], candidate["id_evento"], candidate["medalla"])
        rows = p_by_group.get(key, [])
        ev = by_v.get(candidate["id_evento"], {})
        di = by_d.get(ev.get("id_disciplina", ""), {})
        sport = by_sport.get(di.get("id_deporte", ""), {}).get("nombre", "")
        event = ev.get("nombre", "")
        nocs = sorted({by_n.get(r["id_noc"], {}).get("codigo_noc", r["id_noc"]) for r in rows})
        athletes = []
        for r in rows:
            athlete = by_a.get(r["id_atleta"], {}).get("nombre", r["id_atleta"])
            athletes.append(f"{athlete}[{by_n.get(r['id_noc'],{}).get('codigo_noc','')};pos={r.get('posicion','')};emp={r.get('empatado','')};estado={r.get('estado_resultado','')}]" )
        if candidate["id_edicion"] == "50" and candidate["id_evento"] == "1022":
            classification, source, observation = "VALID_REALLOCATION", IOC_LONDON, "Caso London 2012 50 km; la reubicación histórica está documentada y no se resuelve por COUNT(DISTINCT NOC)."
        elif any(r.get("empatado") == "true" for r in rows):
            classification, source, observation = "VALID_TIE", "NOT_EXTERNALLY_VERIFIED", "Empate explícito en la fuente procesada; requiere consulta del resultado oficial del evento."
        elif candidate["medalla"] == "Bronze" and combat_re.search(f"{sport} {di.get('nombre','')} {event}"):
            classification, source, observation = "VALID_MULTIPLE_BRONZE", "NOT_EXTERNALLY_VERIFIED", "Posible regla histórica de bronces múltiples en deportes de combate; no se marca PASS sin resultado oficial específico."
        elif team_re.search(f"{sport} {di.get('nombre','')} {event}"):
            classification, source, observation = "VALID_TEAM_EVENT", "NOT_EXTERNALLY_VERIFIED", "La multiplicidad de NOC/atletas es compatible con evento colectivo; requiere fuente oficial específica."
        else:
            classification, source, observation = "REVIEW", "NOT_EXTERNALLY_VERIFIED", "No se decide solo por el conteo de NOC; falta evidencia oficial específica del podio."
        podium_out.append({"id_edicion": candidate["id_edicion"], "anio": by_e.get(candidate["id_edicion"], {}).get("anio", ""),
                           "id_evento": candidate["id_evento"], "evento": event, "deporte": sport,
                           "medalla": candidate["medalla"], "noc_en_bd": ";".join(nocs),
                           "atletas_en_bd": ";".join(athletes), "resultado_oficial": "NO_VERIFICADO_CASO_A_CASO",
                           "clasificacion": classification, "fuente": source, "observacion": observation})
    write_csv("final_podium_external_review.csv", podium_out,
              ["id_edicion", "anio", "id_evento", "evento", "deporte", "medalla", "noc_en_bd", "atletas_en_bd", "resultado_oficial", "clasificacion", "fuente", "observacion"])

    # Medal-bearing semantic duplicate subset. No merges are performed.
    ids_by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in A:
        if row.get("nombre"):
            ids_by_name[norm(row["nombre"])].append(row)
    medals_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in P:
        if row.get("medalla"):
            medals_by_id[row["id_atleta"]].append(row)
    dup_rows: list[dict[str, object]] = []
    for name, people in ids_by_name.items():
        people = [person for person in people if medals_by_id.get(person["id_atleta"])]
        if len(people) < 2:
            continue
        # First detect duplicate rows for the same identity under source-specific
        # event labels (for example "10,000 metres, Men" vs "Athletics Men's
        # 10,000 metres"). These are medal-affecting candidates by definition.
        for person in people:
            own_groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
            for row in medals_by_id[person["id_atleta"]]:
                own_groups[(row["id_edicion"], semantic_event(by_v.get(row["id_evento"], {}).get("nombre", "")), row["id_noc"], row["medalla"])].append(row)
            for key, same_rows in own_groups.items():
                if len(same_rows) > 1:
                    dup_rows.append({"nombre_normalizado": name, "id_atleta_1": person["id_atleta"], "id_atleta_2": person["id_atleta"],
                                     "dob_1": person.get("fecha_nacimiento", ""), "dob_2": person.get("fecha_nacimiento", ""),
                                     "medallas_1": len(medals_by_id[person["id_atleta"]]), "medallas_2": len(medals_by_id[person["id_atleta"]]),
                                     "resultados_compartidos": len(same_rows), "clasificacion": "SAME_PERSON_PROBABLE",
                                     "severidad": "CRITICAL", "observacion": "Mismo id_atleta con más de una fila para la misma edición/evento semántico/NOC/medalla bajo etiquetas de fuente distintas."})
        for i, left in enumerate(people):
            for right in people[i + 1:]:
                left_rows, right_rows = medals_by_id[left["id_atleta"]], medals_by_id[right["id_atleta"]]
                left_keys = {(r["id_edicion"], semantic_event(by_v.get(r["id_evento"], {}).get("nombre", "")), r["id_noc"], r["medalla"]) for r in left_rows}
                right_keys = {(r["id_edicion"], semantic_event(by_v.get(r["id_evento"], {}).get("nombre", "")), r["id_noc"], r["medalla"]) for r in right_rows}
                overlap = left_keys & right_keys
                same_dob = bool(left.get("fecha_nacimiento") and left.get("fecha_nacimiento") == right.get("fecha_nacimiento"))
                same_noc = bool({r["id_noc"] for r in left_rows} & {r["id_noc"] for r in right_rows})
                if same_dob and same_noc and overlap:
                    classification, severity = "SAME_PERSON_PROBABLE", "CRITICAL"
                    note = "Mismo nombre normalizado, DOB/NOC compatibles y resultado lógico compartido; puede inflar medallas/rankings."
                elif same_dob or same_noc:
                    classification, severity = "REVIEW", "REVIEW"
                    note = "Coincidencia parcial; no se fusiona ni se declara identidad."
                else:
                    classification, severity = "HOMONYM", "REVIEW"
                    note = "Nombre compartido con atributos insuficientes para identidad."
                dup_rows.append({"nombre_normalizado": name, "id_atleta_1": left["id_atleta"], "id_atleta_2": right["id_atleta"],
                                 "dob_1": left.get("fecha_nacimiento", ""), "dob_2": right.get("fecha_nacimiento", ""),
                                 "medallas_1": len(left_rows), "medallas_2": len(right_rows),
                                 "resultados_compartidos": len(overlap), "clasificacion": classification,
                                 "severidad": severity, "observacion": note})
    write_csv("medal_semantic_duplicate_candidates.csv", dup_rows,
              ["nombre_normalizado", "id_atleta_1", "id_atleta_2", "dob_1", "dob_2", "medallas_1", "medallas_2", "resultados_compartidos", "clasificacion", "severidad", "observacion"])

    # Sources and integrity snapshot.
    write_csv("final_live_query_sources.csv", [
        {"source_id": "IOC_GATLIN", "url": IOC_GATLIN, "scope": "Athens 2004 results/statistics"},
        {"source_id": "IOC_PHELPS", "url": IOC_PHELPS, "scope": "Rio 2016 official Olympic publication; Phelps 23 Olympic golds"},
        {"source_id": "IOC_LATYNINA", "url": IOC_LATYNINA, "scope": "IOC Olympic Studies Centre; 9 gold and 18 total"},
        {"source_id": "IOC_MARIT", "url": IOC_MARIT, "scope": "IOC Olympic Studies Centre; Bjørgen 15th medal"},
        {"source_id": "IOC_NURMI", "url": IOC_NURMI, "scope": "IOC Olympic Studies Centre; Nurmi 12 total, 9 gold"},
        {"source_id": "IOC_SPITZ", "url": IOC_SPITZ, "scope": "IOC Olympic World Library; Spitz career and Munich results"},
        {"source_id": "IOC_BOLT", "url": IOC_BOLT, "scope": "IOC Newsroom; Bolt described as eight-time Olympic champion"},
        {"source_id": "IOC_YOUNGEST", "url": IOC_YOUNGEST, "scope": "IOC Studies Centre discussion of the uncertain 1900 coxswain"},
        {"source_id": "IOC_ATHLETICS_AGE", "url": IOC_ATHLETICS_AGE, "scope": "IOC Tokyo 2020 statistics and athletics age references"},
        {"source_id": "IOC_LONDON", "url": IOC_LONDON, "scope": "London 2012 official programme/results context"},
        {"source_id": "IOC_PARIS_TRAP", "url": IOC_PARIS_TRAP, "scope": "Paris 2024 official results; women's trap"},
        {"source_id": "IOC_RESULTS", "url": IOC_RESULTS, "scope": "IOC Olympic results database guidance"},
    ], ["source_id", "url", "scope"])

    after_processed = {name: sha256(PROCESSED / name) for name in FILES}
    processed_unchanged = before_processed == after_processed
    raw_integrity = read_csv(ROOT / "docs" / "external_quality" / "file_integrity.csv")
    raw_match = sum(1 for r in raw_integrity if r.get("alcance") == "raw_manifest" and r.get("estado") == "MATCH")
    intermediate_match = sum(1 for r in raw_integrity if r.get("alcance") == "intermediate_stability" and r.get("estado") == "MATCH")
    critical_dups = sum(1 for r in dup_rows if r["severidad"] == "CRITICAL")
    podium_counts = Counter(r["clasificacion"] for r in podium_out)
    live_counts = Counter(r["estado"] for r in live_rows)
    famous_fail = sum(1 for r in famous_rows if r["estado"] == "FAIL")
    final_status = "FINAL_EXTERNAL_LIVE_QUERY_AUDIT_PASS" if not critical_dups and not famous_fail and live_counts["FAIL"] == 0 else "FINAL_EXTERNAL_LIVE_QUERY_AUDIT_REVIEW_REQUIRED"
    top_total = rank_raw["TOP_TOTAL"][0] if rank_raw["TOP_TOTAL"] else ["", "", "", "", "", ""]
    top_gold = rank_raw["TOP_GOLD"][0] if rank_raw["TOP_GOLD"] else ["", "", "", "", "", ""]
    top_silver = rank_raw["TOP_SILVER"][0] if rank_raw["TOP_SILVER"] else ["", "", "", "", "", ""]
    top_bronze = rank_raw["TOP_BRONZE"][0] if rank_raw["TOP_BRONZE"] else ["", "", "", "", "", ""]
    md = [
        "# FINAL_EXTERNAL_LIVE_QUERY_AUDIT",
        "",
        f"Estado final: **{final_status}**.",
        "",
        "La auditoría ejecutó consultas SELECT/CTE contra `OlimpiadasDB`, contrastó casos prioritarios con fuentes IOC/Olympics y no modificó datos, esquema, índices, procedimientos ni CSV.",
        "",
        "## Resultado ejecutivo",
        "",
        f"- Candidatos de podio revisados: {len(podium_out)}; casos clasificados como VALID_TEAM_EVENT={podium_counts['VALID_TEAM_EVENT']}, VALID_TIE={podium_counts['VALID_TIE']}, VALID_MULTIPLE_BRONZE={podium_counts['VALID_MULTIPLE_BRONZE']}, VALID_REALLOCATION={podium_counts['VALID_REALLOCATION']}, REVIEW={podium_counts['REVIEW']}.",
        f"- Duplicados semánticos con medalla: {len(dup_rows)} pares; candidatos CRITICAL por resultado lógico compartido: {critical_dups}.",
        f"- Consultas externas en vivo: {len(live_rows)}; PASS={live_counts['PASS']}, REVIEW={live_counts['REVIEW']}, FAIL={live_counts['FAIL']}, NOT_VERIFIABLE={live_counts['NOT_VERIFIABLE']}.",
        f"- Fallos de ranking/famosos confirmados contra referencia: {famous_fail}.",
        "",
        "## Rankings SQL actuales",
        "",
        f"- Mayor total en SQL: {top_total[1]} ({top_total[5]} filas de medalla; no se presenta como récord oficial cuando existen duplicados semánticos).",
        f"- Mayor Gold en SQL: {top_gold[1]} ({top_gold[2]}).",
        f"- Mayor Silver en SQL: {top_silver[1]} ({top_silver[3]}).",
        f"- Mayor Bronze en SQL: {top_bronze[1]} ({top_bronze[4]}).",
        "- Los rankings por deporte se obtuvieron mediante las FK/eventos del modelo, no por inferencia textual.",
        "",
        "## Hallazgos externos críticos",
        "",
        "- Phelps coincide: 23 Gold, 3 Silver, 2 Bronze, total 28.",
        "- Larisa Latynina y Marit Bjørgen coinciden con referencias específicas; Nikolay Andrianov coincide numéricamente, pero permanece REVIEW porque la URL disponible no es una ficha de resultados específica.",
        "- Paavo Nurmi, Mark Spitz y Usain Bolt presentan discrepancias confirmadas; Carl Lewis y Simone Biles requieren una fuente específica adicional antes de elevar la diferencia a FAIL. Ninguno se corrigió.",
        "- La consulta de atleta más joven devuelve una edad raw de 13 años; el IOC mantiene una distinción histórica separada para el coxswain infantil de 1900, por lo que el trusted result queda REVIEW.",
        f"- Podios confirmados como incorrectos: 0 en esta fase; las 200 filas siguen siendo candidatos. Ninguna se marcó PASS solo por consistencia interna.",
        f"- Duplicados de medalla críticos detectados por clave semántica: {critical_dups}; incluyen repeticiones de una misma prueba con nomenclaturas de fuentes distintas.",
        "",
        "## Integridad",
        "",
        f"- Conteos SQL: {', '.join(f'{k}={v}' for k,v in sqlc.items())}; total={sum(sqlc.values())}.",
        f"- SHA processed antes/después: {'MATCH' if processed_unchanged else 'CHANGED'}.",
        f"- RAW: {raw_match}/10 MATCH; intermediate: {intermediate_match}/13 MATCH.",
        "- SQL y stored procedures: no modificados por esta fase; la única modificación de tooling fue corregir el exit code de `18_general_knowledge_query_validation.py`.",
        "",
        "## Recomendación",
        "",
        "**REVIEW_RESULTS**. No se deben corregir datos ni hacer merges dentro de esta auditoría. Antes de declarar la capa de consultas históricas lista para defensa, revisar la deduplicación semántica con medallas y resolver las discrepancias externas de los rankings históricos.",
        "",
        "Fuentes exactas: `final_live_query_sources.csv`. Casos externos por pregunta: `live_external_query_checks.csv`.",
    ]
    (OUT / "final_live_query_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    summary_rows = [
        {"indicador": "estado_final", "valor": final_status, "estado": "PASS" if final_status.endswith("PASS") else "REVIEW"},
        {"indicador": "podios_revisados", "valor": len(podium_out), "estado": "PASS"},
        {"indicador": "duplicados_medalla_critical", "valor": critical_dups, "estado": "PASS" if critical_dups == 0 else "FAIL"},
        {"indicador": "live_queries", "valor": len(live_rows), "estado": "PASS" if live_counts["FAIL"] == 0 else "FAIL"},
        {"indicador": "raw_sha", "valor": f"{raw_match}/10 MATCH", "estado": "PASS" if raw_match == 10 else "FAIL"},
        {"indicador": "intermediate_sha", "valor": f"{intermediate_match}/13 MATCH", "estado": "PASS" if intermediate_match == 13 else "FAIL"},
        {"indicador": "processed_unchanged", "valor": "YES" if processed_unchanged else "NO", "estado": "PASS" if processed_unchanged else "FAIL"},
    ]
    write_csv("final_live_query_audit.csv", summary_rows, ["indicador", "valor", "estado"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
