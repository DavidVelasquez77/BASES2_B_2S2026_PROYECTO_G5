"""Genera el reporte final del Bloque 7 desde validaciones SQL de solo lectura."""
from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "final"
OUT.mkdir(parents=True, exist_ok=True)


def read_password() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("MSSQL_SA_PASSWORD="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("No se encontró MSSQL_SA_PASSWORD en .env")


def run_sql(script: Path) -> list[list[str]]:
    env = os.environ.copy()
    env["SQLCMDPASSWORD"] = read_password()
    command = [
        "docker", "exec", "-i", "-e", "SQLCMDPASSWORD", "olimpiadas-sqlserver",
        "/opt/mssql-tools18/bin/sqlcmd", "-S", "localhost", "-U", "sa",
        "-d", "OlimpiadasDB", "-C", "-b", "-f", "65001", "-W", "-h", "-1", "-s", "|",
    ]
    result = subprocess.run(
        command,
        input=script.read_text(encoding="utf-8"),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [
        [part.strip() for part in line.split("|")]
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def validation_rows(script: Path) -> list[list[str]]:
    rows = run_sql(script)
    return [row for row in rows if len(row) == 5 and row[3] in {"PASS", "FAIL"}]


rows = validation_rows(ROOT / "scripts" / "sql" / "10_final_validation.sql")
rows.extend(validation_rows(ROOT / "scripts" / "sql" / "11_special_cases_validation.sql"))

with (OUT / "final_validation_report.csv").open("w", encoding="utf-8", newline="") as handle:
    csv.writer(handle).writerows([
        ["validacion", "esperado", "actual", "estado", "detalle"],
        *rows,
    ])

failures = [row for row in rows if row[3] == "FAIL"]
if failures:
    raise RuntimeError(f"La auditoría final contiene {len(failures)} FAIL")
print(f"Reporte generado: {OUT / 'final_validation_report.csv'} ({len(rows)} validaciones PASS)")
