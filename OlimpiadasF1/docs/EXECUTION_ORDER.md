# Orden de ejecución

Este orden separa creación, staging, carga, índices y auditoría. Los scripts de validación final son de solo lectura.

1. `scripts/sql/00_create_database.sql`
2. `scripts/sql/01_create_tables.sql`
3. `scripts/sql/03_create_staging.sql`
4. `scripts/sql/04_bulk_load_staging.sql`
5. `scripts/sql/05_validate_staging.sql`
6. `scripts/sql/06_load_final.sql`
7. `scripts/sql/07_create_indexes.sql`
8. `scripts/sql/08_validate_loaded_data.sql`
9. `scripts/python/09_generate_loading_reports.py` para auditar la carga ya realizada.
10. `scripts/sql/10_final_validation.sql`
11. `scripts/sql/11_special_cases_validation.sql`
12. `scripts/sql/12_functional_queries.sql`
13. `scripts/python/13_generate_final_validation_report.py`

Los CSV procesados se montan en el contenedor bajo `/var/opt/mssql/import/processed/`. El servicio publica SQL Server en `localhost,1434`; la autenticación local usa el secreto de `.env` sin documentarlo.

`scripts/sql/03_reset_staging.sql` y `scripts/sql/00_reset_physical_tables.sql` son herramientas manuales de desarrollo. No forman parte del flujo normal, no se ejecutan automáticamente y no deben usarse durante la auditoría final.

`06_load_final.sql` contiene un preflight que aborta si las tablas finales ya tienen datos. No se ejecuta de nuevo en una base cargada.
