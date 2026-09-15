# Corrección GUA 2020

Estado: **APPLIED_TO_PROCESSED**

Se retiraron únicamente 24 filas de `data/processed/participacion.csv`:
- 23 asociaciones GUA 2020 cuyo atleta no pertenece al roster publicado.
- 1 fila duplicada de Yulisa López.

No se modificaron `data/raw`, `data/intermediate`, los otros nueve CSV, SQL Server ni Stored Procedures.

Participación antes: **712658**.
Participación después: **712634**.

El resto de discrepancias GUA no se fusionó automáticamente: los 263 nombres históricos requieren un mapa biográfico explícito y la tabla recibida contiene inconsistencias de conteo.

Archivos de control:
- `docs\quality\gua_2020_fix_manifest_before.csv`
- `docs\quality\gua_2020_fix_manifest_after.csv`
- `docs\quality\gua_2020_roster_review.csv`
- `data\backup_before_gua_2020_fix`
- `data\preview_gua_2020_fix`
