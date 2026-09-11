# Corrección de `ROWTERMINATOR` — 2026-09-10

## Causa

El diagnóstico aisló el fallo Msg 4879 en el terminador de línea usado por `scripts/sql/04_bulk_load_staging.sql`. El script usaba `0x0a` para todos los CSV, pero los archivos oficiales actuales mezclan LF y CRLF.

`evento.csv` es UTF-8 válido, tiene 3,007 filas válidas, `stg.EVENTO` es compatible 3/3 y contiene correctamente el campo quoted `"Singles, Men (Olympic)`. Con `ROWTERMINATOR='0x0a'` falló; con `ROWTERMINATOR='0x0d0a'` cargó 3,007 filas.

## Cambio aplicado

Archivo modificado: `scripts/sql/04_bulk_load_staging.sql`.

El único cambio funcional fue `ROWTERMINATOR`:

- CRLF → `0x0d0a`: `atleta.csv`, `edicion_olimpica.csv`, `evento.csv`, `participacion.csv`.
- LF → `0x0a`: `entidad_geografica.csv`, `poblacion.csv`, `noc.csv`, `sede.csv`, `deporte.csv`, `disciplina.csv`.

Se conservaron `FORMAT='CSV'`, `FIELDQUOTE='"'`, `FIRSTROW=2`, el schema staging, el modelo físico, las conversiones y todos los constraints.

## Evidencia

La distribución completa está en `processed_line_endings_20260910.csv`. La prueba de `evento.csv` con CRLF cargó 3,007/3,007 filas en una tabla temporal. La reconstrucción retry1 cargó los diez staging y pasó `05_validate_staging.sql`.

Los CSV oficiales no fueron modificados ni reescritos.
