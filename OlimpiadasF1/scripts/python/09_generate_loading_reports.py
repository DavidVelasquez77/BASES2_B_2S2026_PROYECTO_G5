"""Genera auditoría del Bloque 6 a partir de consultas y archivos existentes.

No recarga tablas, no fabrica métricas históricas y no escribe PASS/FAIL de forma
manual para las validaciones: los estados SQL provienen de las consultas.
"""
from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "loading"
OUT.mkdir(parents=True, exist_ok=True)
HISTORICAL_METRICS = OUT / "load_metrics_run_20260909.csv"


def read_env_password() -> str:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values["MSSQL_SA_PASSWORD"]


def sqlcmd(text: str) -> list[list[str]]:
    env = os.environ.copy()
    env["SQLCMDPASSWORD"] = read_env_password()
    command = [
        "docker", "exec", "-i", "-e", "SQLCMDPASSWORD", "olimpiadas-sqlserver",
        "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost", "-U", "sa", "-C",
        "-d", "OlimpiadasDB", "-b", "-f", "65001", "-W", "-h", "-1", "-s", "|",
    ]
    result = subprocess.run(command, input=text, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    rows = []
    for line in result.stdout.splitlines():
        if line.strip():
            rows.append([part.strip() for part in line.split("|")])
    return rows


def audit_rows_from_staging() -> list[list[str]]:
    rows = sqlcmd((ROOT / "scripts" / "sql" / "05_validate_staging.sql").read_text(encoding="utf-8"))
    return [row for row in rows if len(row) == 5 and row[3] in {"PASS", "FAIL"}]


def write_csv(name: str, header: list[str], rows: list[list[object]]) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([header, *rows])


entities = [
    ("ENTIDAD_GEOGRAFICA", 282), ("POBLACION", 17024), ("NOC", 236),
    ("ATLETA", 336419), ("SEDE", 42), ("EDICION_OLIMPICA", 61),
    ("DEPORTE", 65), ("DISCIPLINA", 117), ("EVENTO", 3007),
    ("PARTICIPACION", 733414),
]
count_sql = "SET NOCOUNT ON;\n" + "\nUNION ALL\n".join(
    f"SELECT N'{name}',{expected},(SELECT COUNT_BIG(*) FROM stg.{name}),(SELECT COUNT_BIG(*) FROM olympics.{name}),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.{name})={expected} AND (SELECT COUNT_BIG(*) FROM olympics.{name})={expected} THEN N'PASS' ELSE N'FAIL' END"
    for name, expected in entities
) + ";\n"
count_rows = sqlcmd(count_sql)
write_csv("load_counts.csv", ["entidad", "esperado_csv", "staging", "final_sql", "estado"], count_rows)


staging_validation = audit_rows_from_staging()

final_validation_sql = r"""
SET NOCOUNT ON;
SELECT N'final_pk_duplicadas',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_participacion,COUNT_BIG(*) c FROM olympics.PARTICIPACION GROUP BY id_participacion HAVING COUNT_BIG(*)>1)d),CASE WHEN (SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_participacion,COUNT_BIG(*) c FROM olympics.PARTICIPACION GROUP BY id_participacion HAVING COUNT_BIG(*)>1)d)=0 THEN N'PASS' ELSE N'FAIL' END,N'PK PARTICIPACION';
SELECT N'final_fk_huerfanas',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p WHERE NOT EXISTS (SELECT 1 FROM olympics.ATLETA a WHERE a.id_atleta=p.id_atleta) OR NOT EXISTS (SELECT 1 FROM olympics.EDICION_OLIMPICA e WHERE e.id_edicion=p.id_edicion) OR NOT EXISTS (SELECT 1 FROM olympics.EVENTO e WHERE e.id_evento=p.id_evento)),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p WHERE NOT EXISTS (SELECT 1 FROM olympics.ATLETA a WHERE a.id_atleta=p.id_atleta) OR NOT EXISTS (SELECT 1 FROM olympics.EDICION_OLIMPICA e WHERE e.id_edicion=p.id_edicion) OR NOT EXISTS (SELECT 1 FROM olympics.EVENTO e WHERE e.id_evento=p.id_evento))=0 THEN N'PASS' ELSE N'FAIL' END,N'FK principales PARTICIPACION';
SELECT N'final_check_medalla',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL AND medalla NOT IN (N'Gold',N'Silver',N'Bronze')),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL AND medalla NOT IN (N'Gold',N'Silver',N'Bronze'))=0 THEN N'PASS' ELSE N'FAIL' END,N'Dominio medalla';
SELECT N'final_check_temporada',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth')),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth'))=0 THEN N'PASS' ELSE N'FAIL' END,N'Dominio temporada';
SELECT N'final_constraints',33,(SELECT COUNT_BIG(*) FROM sys.key_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')))+(SELECT COUNT_BIG(*) FROM sys.foreign_keys WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')))+(SELECT COUNT_BIG(*) FROM sys.check_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics'))),CASE WHEN (SELECT COUNT_BIG(*) FROM sys.key_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')))+(SELECT COUNT_BIG(*) FROM sys.foreign_keys WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')))+(SELECT COUNT_BIG(*) FROM sys.check_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')))=33 THEN N'PASS' ELSE N'FAIL' END,N'10 PK + 6 UNIQUE + 14 FK + 3 CHECK';
SELECT N'final_indices_adicionales',8,(SELECT COUNT_BIG(*) FROM sys.indexes WHERE OBJECT_SCHEMA_NAME(object_id)=N'olympics' AND name LIKE N'IX_%'),CASE WHEN (SELECT COUNT_BIG(*) FROM sys.indexes WHERE OBJECT_SCHEMA_NAME(object_id)=N'olympics' AND name LIKE N'IX_%')=8 THEN N'PASS' ELSE N'FAIL' END,N'Índices no cluster justificados';
SELECT N'decimal.ATLETA.altura_cm',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.ATLETA.peso_kg',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.ATLETA.latitud',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.latitud),N''))<>CONVERT(DECIMAL(38,20),f.latitud)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.latitud),N''))<>CONVERT(DECIMAL(38,20),f.latitud))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.ATLETA.longitud',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.longitud),N''))<>CONVERT(DECIMAL(38,20),f.longitud)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.longitud),N''))<>CONVERT(DECIMAL(38,20),f.longitud))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.PARTICIPACION.edad',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.edad),N''))<>CONVERT(DECIMAL(38,20),f.edad)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.edad),N''))<>CONVERT(DECIMAL(38,20),f.edad))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.PARTICIPACION.altura_cm_registrada',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm_registrada),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm_registrada)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm_registrada),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm_registrada))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
SELECT N'decimal.PARTICIPACION.peso_kg_registrado',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg_registrado),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg_registrado)),CASE WHEN (SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg_registrado),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg_registrado))=0 THEN N'PASS' ELSE N'FAIL' END,N'Comparación staging/final sin redondeo';
"""
final_validation = [row for row in sqlcmd(final_validation_sql) if len(row) == 5 and row[3] in {"PASS", "FAIL"}]


def normalized_id(value: str) -> str:
    value = value.strip()
    if value.endswith(".0"):
        try:
            return str(int(float(value)))
        except ValueError:
            pass
    return value


def validate_unicode() -> list[object]:
    with (ROOT / "data" / "processed" / "atleta.csv").open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    selected = {
        normalized_id(row["id_atleta"]): row["nombre"]
        for row in source_rows
        if any(ord(char) > 127 for char in row["nombre"])
    }
    sql_rows = sqlcmd("SET NOCOUNT ON; SELECT CONVERT(NVARCHAR(50),id_atleta),nombre FROM olympics.ATLETA;\n")
    sql_names = {row[0]: row[1] for row in sql_rows if len(row) == 2}
    compared = sum(identifier in sql_names for identifier in selected)
    differences = sum(
        1 for identifier, source_name in selected.items()
        if identifier not in sql_names or sql_names[identifier] != source_name
    )
    state = "PASS" if len(selected) == 26261 and compared == len(selected) and differences == 0 else "FAIL"
    write_csv(
        "unicode_validation.csv",
        ["campo", "filas_no_ascii_csv", "filas_comparadas", "diferencias", "estado"],
        [["nombre", len(selected), compared, differences, state]],
    )
    return ["unicode.ATLETA.nombre", 0, differences, state, "Comparación exacta CSV -> SQL por id_atleta"]


unicode_result = validate_unicode()
write_csv("load_validation.csv", ["validacion", "esperado", "actual", "estado", "detalle"], staging_validation + final_validation + [unicode_result])

reasons = {
    "IX_PARTICIPACION_id_atleta": "Búsqueda de participaciones por atleta.",
    "IX_PARTICIPACION_id_edicion": "Joins y filtros por edición olímpica.",
    "IX_PARTICIPACION_id_evento": "Joins y filtros por evento.",
    "IX_PARTICIPACION_id_noc": "Consultas por NOC/equipo.",
    "IX_PARTICIPACION_id_pais_nacionalidad": "Consultas por país de nacionalidad.",
    "IX_ATLETA_id_pais_nacionalidad": "Búsqueda de atletas por país.",
    "IX_NOC_id_entidad": "Join NOC a entidad geográfica.",
    "IX_SEDE_id_pais": "Join sede a entidad geográfica.",
}
index_sql = """
SET NOCOUNT ON;
SELECT i.name,OBJECT_NAME(i.object_id),STRING_AGG(c.name,N',') WITHIN GROUP (ORDER BY ic.key_ordinal)
FROM sys.indexes i
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE OBJECT_SCHEMA_NAME(i.object_id)=N'olympics' AND i.name LIKE N'IX_%'
GROUP BY i.name,i.object_id;
"""
index_rows = []
for row in sqlcmd(index_sql):
    if len(row) == 3 and row[0] in reasons:
        index_rows.append([row[0], row[1], row[2], reasons[row[0]]])
write_csv("indexes_created.csv", ["indice", "tabla", "columnas", "motivo"], index_rows)

if not HISTORICAL_METRICS.exists():
    raise FileNotFoundError(f"Falta el registro histórico {HISTORICAL_METRICS}")

print(f"Auditoría regenerada en {OUT}; métricas históricas conservadas en {HISTORICAL_METRICS.name}.")
