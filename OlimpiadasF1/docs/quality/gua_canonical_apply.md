# Corrección canónica GUA

Estado: **APPLIED_TO_PROCESSED**

La corrección se limita a asociaciones GUA en participacion.csv. atleta.csv no se elimina ni se reescribe; los IDs fuente sin asociaciones GUA válidas permanecen para trazabilidad.

- Referencia Olympedia: **263 IDs únicos** y **339 registros por edición**.
- IDs GUA Olympic finales: **263**.
- Filas de participación antes: **712634**.
- Filas de participación después: **712020**.
- Asociaciones GUA excluidas: **614**.
- Reasignaciones de alias: **8**.
- Duplicados exactos eliminados después de alias: **0**.
- Participaciones Youth conservadas fuera del padrón 263: **9**.
- Asociaciones GUA falsas confirmadas que permanecen: **0**.

## Seguridad

No se modificaron data/raw, data/intermediate, atleta.csv, evento.csv, SQL Server ni stored procedures. Los casos ambiguos están en `docs/quality/gua_ambiguous_cases.csv`.

## Evidencia externa

https://www.olympedia.org/countries/GUA
