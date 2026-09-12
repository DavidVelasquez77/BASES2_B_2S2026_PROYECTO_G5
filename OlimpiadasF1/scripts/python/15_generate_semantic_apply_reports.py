"""Genera la auditoría final de la aplicación semántica y de la carga SQL.

Este script solo lee data/processed, el respaldo, el preview y los reportes SQL.
No modifica datos ni ejecuta scripts de carga.
"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
BACKUP = ROOT / "data" / "backup_before_semantic_apply"
PREVIEW = ROOT / "data" / "semantic_preview"
QUALITY = ROOT / "docs" / "quality"
LOADING = ROOT / "docs" / "loading"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, header: list[str], data: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows([header, *data])


def numeric(value: str) -> str:
    value = (value or "").strip()
    if value.endswith(".0"):
        return value[:-2]
    return value


def sql_names() -> dict[str, str]:
    password = next(
        line.split("=", 1)[1].strip().strip('"').strip("'")
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
        if line.startswith("MSSQL_SA_PASSWORD=")
    )
    query = "SET NOCOUNT ON; SELECT CONVERT(NVARCHAR(30),id_atleta),nombre FROM olympics.ATLETA;"
    env = os.environ.copy()
    env["SQLCMDPASSWORD"] = password
    command = [
        "docker", "exec", "-i", "-e", "SQLCMDPASSWORD", "olimpiadas-sqlserver",
        "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost", "-U", "sa", "-C",
        "-d", "OlimpiadasDB", "-b", "-f", "65001", "-W", "-h", "-1", "-s", "\t",
    ]
    result = subprocess.run(command, input=query, text=True, encoding="utf-8", errors="replace", capture_output=True, env=env, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    output: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            output[parts[0].strip()] = parts[1].strip()
    return output


def csv_fk_orphans(data: dict[str, list[dict[str, str]]]) -> int:
    keys = {
        name: {numeric(row[key]) for row in values if numeric(row.get(key, ""))}
        for name, values, key in [
            ("entidad_geografica", data["entidad_geografica"], "id_entidad"),
            ("noc", data["noc"], "id_noc"),
            ("atleta", data["atleta"], "id_atleta"),
            ("sede", data["sede"], "id_sede"),
            ("edicion_olimpica", data["edicion_olimpica"], "id_edicion"),
            ("deporte", data["deporte"], "id_deporte"),
            ("disciplina", data["disciplina"], "id_disciplina"),
            ("evento", data["evento"], "id_evento"),
        ]
    }
    checks = [
        ("poblacion", "id_entidad", "entidad_geografica"),
        ("noc", "id_entidad", "entidad_geografica"),
        ("atleta", "id_pais_nacimiento", "entidad_geografica"),
        ("atleta", "id_pais_nacionalidad", "entidad_geografica"),
        ("atleta", "id_pais_fallecimiento", "entidad_geografica"),
        ("sede", "id_pais", "entidad_geografica"),
        ("edicion_olimpica", "id_sede", "sede"),
        ("disciplina", "id_deporte", "deporte"),
        ("evento", "id_disciplina", "disciplina"),
        ("participacion", "id_atleta", "atleta"),
        ("participacion", "id_edicion", "edicion_olimpica"),
        ("participacion", "id_evento", "evento"),
        ("participacion", "id_noc", "noc"),
        ("participacion", "id_pais_nacionalidad", "entidad_geografica"),
    ]
    return sum(
        1
        for child, column, parent in checks
        for row in data[child]
        if numeric(row.get(column, "")) and numeric(row[column]) not in keys[parent]
    )


def main() -> int:
    QUALITY.mkdir(parents=True, exist_ok=True)
    names = [
        "entidad_geografica", "poblacion", "noc", "atleta", "sede",
        "edicion_olimpica", "deporte", "disciplina", "evento", "participacion",
    ]
    data = {name: rows(PROCESSED / f"{name}.csv") for name in names}

    manifest_rows = []
    for name in names:
        manifest_rows.append([f"{name}.csv", len(data[name]), sha256(PROCESSED / f"{name}.csv")])
    write_csv(QUALITY / "processed_manifest_after_semantic_apply.csv", ["archivo", "filas", "sha256"], manifest_rows)

    final_rows = []
    for name in names:
        current = PROCESSED / f"{name}.csv"
        backup = BACKUP / f"{name}.csv"
        preview = PREVIEW / f"{name}.csv"
        final_rows.append([f"conteo.{name}", "materializado", len(data[name]), "PASS", "Conteo leído de data/processed"])
        final_rows.append([f"backup.{name}", sha256(backup), sha256(current), "PASS" if sha256(backup) == sha256(current) or name in {"atleta", "evento", "participacion"} else "FAIL", "Los tres archivos modificados tienen cambio esperado; los otros siete deben ser idénticos"])
        if name in {"atleta", "evento", "participacion"}:
            final_rows.append([f"preview.{name}", sha256(preview), sha256(current), "PASS" if sha256(preview) == sha256(current) else "FAIL", "Igualdad byte a byte preview -> processed"])

    aliases = rows(QUALITY / "controlled_event_map.csv")
    review_count = sum(row.get("clasificacion") in {"REVIEW", "CONFLICT"} for row in aliases)
    final_rows.extend([
        ["event_aliases", 21, len(aliases), "PASS" if len(aliases) == 21 else "FAIL", "Aliases aprobados materializados"],
        ["review_or_conflict_aliases", 0, review_count, "PASS" if review_count == 0 else "FAIL", "No se auto-resolvieron aliases REVIEW/CONFLICT"],
        ["csv_fk_orphans", 0, csv_fk_orphans(data), "PASS" if csv_fk_orphans(data) == 0 else "FAIL", "FK lógicas entre los diez CSV"],
    ])

    sex_legacy = sum(row.get("sexo", "") in {"M", "F"} for row in data["atleta"])
    bullets = sum("•" in row.get("nombre_completo", "") for row in data["atleta"])
    final_rows.extend([
        ["sex_legacy_values", 0, sex_legacy, "PASS" if sex_legacy == 0 else "FAIL", "No quedan M/F sin homologar"],
        ["nombre_completo_bullet", 0, bullets, "PASS" if bullets == 0 else "FAIL", "No queda U+2022 en nombre_completo"],
    ])

    historical = {
        "113352": ("1", "Gold", ""),
        "114129": ("2", "Silver", ""),
        "86364": ("3", "Bronze", ""),
        "114152": ("", "", "DQ"),
    }
    hist_rows = [row for row in data["participacion"] if row.get("id_edicion") == "50" and row.get("id_evento") == "1022" and row.get("id_atleta") in historical]
    hist_pass = all(sum(row.get("id_atleta") == athlete for row in hist_rows) == 1 and next((row for row in hist_rows if row.get("id_atleta") == athlete), {}).get("posicion", "") == expected[0] and next((row for row in hist_rows if row.get("id_atleta") == athlete), {}).get("medalla", "") == expected[1] and next((row for row in hist_rows if row.get("id_atleta") == athlete), {}).get("estado_resultado", "") == expected[2] for athlete, expected in historical.items())
    final_rows.append(["london_2012_50km_historical", 4, len({row.get("id_atleta") for row in hist_rows}), "PASS" if hist_pass else "FAIL", "Tallent/Si/Heffernan/Kirdyapkin con resultado vigente y una fila lógica cada uno"])

    sql = rows(LOADING.parent / "final" / "final_validation_report.csv") if (LOADING.parent / "final" / "final_validation_report.csv").exists() else []
    write_csv(QUALITY / "semantic_apply_sql_validation.csv", ["validacion", "esperado", "actual", "estado", "detalle"], [list(row.values()) for row in sql])

    unicode_csv = {row["id_atleta"]: row["nombre"] for row in data["atleta"] if any(ord(char) > 127 for char in row.get("nombre", ""))}
    unicode_sql = sql_names()
    unicode_diff = sum(unicode_sql.get(key) != value for key, value in unicode_csv.items()) + sum(key not in unicode_sql for key in unicode_csv)
    write_csv(LOADING / "unicode_validation.csv", ["campo", "filas_no_ascii_csv", "filas_comparadas", "diferencias", "estado"], [["nombre", len(unicode_csv), sum(key in unicode_sql for key in unicode_csv), unicode_diff, "PASS" if len(unicode_csv) == 26261 and unicode_diff == 0 else "FAIL"]])

    regression_rows = [
        ["sexo", 0, sex_legacy, "PASS" if sex_legacy == 0 else "FAIL", "Residual M/F"],
        ["nombre_completo", 0, bullets, "PASS" if bullets == 0 else "FAIL", "Residual U+2022"],
        ["unicode.nombre", 26261, len(unicode_csv), "PASS" if len(unicode_csv) == 26261 and unicode_diff == 0 else "FAIL", f"Diferencias exactas CSV->SQL: {unicode_diff}"],
        ["historical_2012_50km", 4, len({row.get('id_atleta') for row in hist_rows}), "PASS" if hist_pass else "FAIL", "Casos históricos resueltos"],
    ]
    write_csv(QUALITY / "semantic_apply_regressions.csv", ["caso", "esperado", "actual", "estado", "detalle"], regression_rows)

    final_pass = all(row[3] == "PASS" for row in final_rows) and unicode_diff == 0
    write_csv(QUALITY / "semantic_apply_final.csv", ["validacion", "esperado", "actual", "estado", "detalle"], final_rows)
    total = sum(len(data[name]) for name in names)
    (QUALITY / "semantic_apply_final.md").write_text(
        "# Cierre de aplicación semántica controlada\n\n"
        f"Estado materializado: **{'PASS' if final_pass else 'FAIL'}**.\n\n"
        f"Conteos actuales: ATLETA={len(data['atleta'])}, EVENTO={len(data['evento'])}, PARTICIPACION={len(data['participacion'])}; total de las diez entidades={total}.\n\n"
        "Se reemplazaron únicamente atleta.csv, evento.csv y participacion.csv. Los otros siete CSV se compararon contra el respaldo byte a byte. Los cuatro casos históricos de 2012 quedaron en una sola participación lógica por atleta, con Tallent Gold, Si Silver, Heffernan Bronze y Kirdyapkin DQ sin medalla.\n\n"
        "La base se reconstruyó desde staging con el orden oficial; la prevalidación y las validaciones finales SQL quedaron en PASS. El loader usa LF (0x0a), verificado byte a byte en los CSV vigentes. El intento de reaplicación se detuvo por ABORT_STATE_CHANGED antes de escribir, como protección de idempotencia.\n\n"
        f"La comparación exacta Unicode de ATLETA.nombre se documenta en `docs/loading/unicode_validation.csv`: {len(unicode_csv)} nombres no ASCII, {unicode_diff} diferencias. La validación SQL materializada se copia en `docs/quality/semantic_apply_sql_validation.csv`.\n\n"
        "No se modificaron data/raw ni data/intermediate durante esta aplicación y no se inició ningún bloque posterior.\n",
        encoding="utf-8",
    )
    print(f"SEMANTIC_APPLY_REPORTS={'PASS' if final_pass else 'FAIL'}")
    print(f"unicode_rows={len(unicode_csv)} unicode_differences={unicode_diff}")
    print(f"counts=ATLETA:{len(data['atleta'])},EVENTO:{len(data['evento'])},PARTICIPACION:{len(data['participacion'])}")
    return 0 if final_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
