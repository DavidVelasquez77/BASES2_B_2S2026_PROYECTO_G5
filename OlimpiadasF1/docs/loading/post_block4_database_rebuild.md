# Reconstrucción posterior al Bloque 4 — resultado controlado

## Estado

**DB_REBUILD_FAILED**

La reconstrucción se detuvo en la carga de staging. No se ejecutaron `05_validate_staging.sql`, `06_load_final.sql`, `07_create_indexes.sql` ni `08_validate_loaded_data.sql` después del fallo.

## Prechecks aprobados

- Los diez CSV de `data/processed/` coincidieron con `docs/consolidation/processed_manifest_after_block4_apply.csv`: **10/10 MATCH**.
- Los conteos locales coincidieron con el universo oficial y sumaron **1,090,667**.
- El contenedor `olimpiadas-sqlserver` estaba activo con `1434->1433`.
- `OlimpiadasDB` estaba ONLINE.
- SQL Server respondió como versión 2025 RTM-CU8-GDR, `17.0.4085.5`.
- El montaje `/var/opt/mssql/import/processed/` contenía los diez CSV oficiales.
- El estado SQL anterior quedó registrado en `pre_rebuild_sql_counts_20260910.csv`.

## Scripts ejecutados

1. `scripts/sql/00_reset_physical_tables.sql` — PASS.
2. `scripts/sql/01_create_tables.sql` — PASS.
3. `scripts/sql/03_reset_staging.sql` — PASS.
4. `scripts/sql/04_bulk_load_staging.sql` — FAIL.

`03_create_staging.sql` no se ejecutó porque las diez tablas staging ya existían y el propio script aborta deliberadamente en ese caso. Se utilizó el script oficial `03_reset_staging.sql` para vaciar el staging existente, sin DROP manual.

## Incidencia exacta

SQL Server rechazó:

```text
Bulk load failed due to invalid column value in CSV data file
/var/opt/mssql/import/processed/evento.csv in row 2, column 3.
Msg 4879
```

La fila local corresponde a un CSV válido y no fue modificada:

```text
1,96,"Singles, Men (Olympic)"
```

El SHA-256 de `data/processed/evento.csv` continuó siendo `d40e80508e38a07e95d1a829ffc0d390477e92ff66d6f960c49cb985b35044cf`. No se aplicó ningún parche ni conversión manual para forzar la carga.

## Métricas reales

Las duraciones reales de los cuatro pasos ejecutados están en `load_metrics_run_20260910.csv`. El tiempo transcurrido de los pasos ejecutados fue **15.374 segundos**. Los pasos posteriores están marcados `NOT_RUN` y no tienen timestamps inventados.

## Estado posterior

- La carga de staging falló y la transacción de `04_bulk_load_staging.sql` terminó con error.
- No se cargaron tablas finales mediante `06_load_final.sql`.
- No se crearon índices en esta ejecución.
- No se ejecutó la validación integral posterior.
- No se declara `DB_REBUILD_SUCCESS` ni `FINAL_DATABASE_VALIDATION_PASS`.
- Los CSV productivos permanecen intactos: **10/10 SHA-256 MATCH**.

## Próximo paso requerido

Debe revisarse la compatibilidad real del parser CSV de SQL Server con `evento.csv` y `04_bulk_load_staging.sql`. La corrección debe hacerse en la estrategia/script de carga, sin modificar `data/processed/`, y requiere una nueva autorización o una instrucción específica antes de reintentar.
