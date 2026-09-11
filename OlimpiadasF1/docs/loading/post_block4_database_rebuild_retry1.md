# Reconstrucción posterior al Bloque 4 — retry 1

## Estado

**DB_REBUILD_SUCCESS**

La base `OlimpiadasDB` fue reconstruida y cargada usando los CSV oficiales actuales de `data/processed/`. El único cambio funcional aplicado fue la selección de `ROWTERMINATOR` por archivo en `scripts/sql/04_bulk_load_staging.sql`.

Esta ejecución no declara el cierre integral del Bloque 7.

## Corrección aplicada

Los CSV actuales mezclan terminadores:

- CRLF: `atleta.csv`, `edicion_olimpica.csv`, `evento.csv`, `participacion.csv`.
- LF: `entidad_geografica.csv`, `poblacion.csv`, `noc.csv`, `sede.csv`, `deporte.csv`, `disciplina.csv`.

Se aplicó `0x0d0a` a los cuatro archivos CRLF y se mantuvo `0x0a` en los seis archivos LF. Se conservaron `FORMAT='CSV'`, `FIELDQUOTE='"'` y `FIRSTROW=2`. No se modificaron CSV, schema staging, tablas, columnas, tipos, PK, FK, UQ, CHECK ni lógica de consolidación.

Detalle: `processed_line_endings_20260910.csv` y `bulk_load_rowterminator_fix_20260910.md`.

## Prechecks

- SHA-256 de processed: **10/10 MATCH**.
- Conteos locales: **10/10 correctos**.
- Total local: **1,090,667**.
- Contenedor: `olimpiadas-sqlserver`, `1434->1433`.
- Base: `OlimpiadasDB`.
- Montaje de processed: verificado.

## Flujo ejecutado

1. `00_reset_physical_tables.sql` — PASS.
2. `01_create_tables.sql` — PASS.
3. `03_reset_staging.sql` — PASS. Se usó porque las tablas staging ya existían; `03_create_staging.sql` tiene un guard que aborta cuando detecta tablas existentes.
4. `04_bulk_load_staging.sql` — PASS.
5. Conteos staging — PASS.
6. `05_validate_staging.sql` — PASS.
7. `06_load_final.sql` — PASS.
8. `07_create_indexes.sql` — PASS.
9. `08_validate_loaded_data.sql` — PASS.
10. `09_generate_loading_reports.py` — PASS.
11. `04_validate_physical_model.py` con `.venv` — PASS, 66/66.

## Conteos staging y finales

| Entidad | Staging | Final |
|---|---:|---:|
| ENTIDAD_GEOGRAFICA | 282 | 282 |
| POBLACION | 17,024 | 17,024 |
| NOC | 236 | 236 |
| ATLETA | 336,419 | 336,419 |
| SEDE | 42 | 42 |
| EDICION_OLIMPICA | 61 | 61 |
| DEPORTE | 65 | 65 |
| DISCIPLINA | 117 | 117 |
| EVENTO | 3,007 | 3,007 |
| PARTICIPACION | 733,414 | 733,414 |
| **Total** | **1,090,667** | **1,090,667** |

## Modelo físico e integridad

- Tablas: **10**.
- Columnas: **66**.
- PK: **10**.
- UNIQUE: **6**.
- FK: **14**.
- CHECK: **3**.
- Índices adicionales `IX_`: **8**.
- PK duplicadas: **0**.
- FK huérfanas: **0**.
- Los siete campos DECIMAL: **0 diferencias y 0 redondeos**.

Los ocho índices creados y su justificación están en `docs/loading/indexes_created.csv`.

## Validaciones funcionales

- Unicode CSV → SQL: **26,261 nombres no ASCII comparados; 0 diferencias; PASS**.
- Messi: `id_atleta=110178`, fecha `1987-06-24`; `id_atleta=167544` no aparece como identidad Messi.
- Participación Messi: una sola fila lógica para `2008 Summer`, `ARG`, Argentina, evento `303`, posición `1`, medalla `Gold`.
- `1906 Intercalated Games`: presente; `1906 Summer`: ausente.
- `1956 Summer`: presente; `Equestrian`: 0.
- `Summer Youth`: 3; `Winter Youth`: 3.
- Zappas: exclusión auditada conservada en `excluded_non_official_participations.csv`.
- NOC históricos: se conservaron 5 registros con `id_entidad NULL`.

## Métricas

Las duraciones reales están en `load_metrics_run_20260910_retry1.csv`. La suma de las duraciones de los diez pasos ejecutados fue **272.669 segundos**. El intervalo de reloj entre el primer reset y el fin de la validación física fue aproximadamente **404.734 segundos**, incluyendo consultas de gate y pausas entre etapas.

El intento fallido anterior `load_metrics_run_20260910.csv` se mantuvo intacto. También se mantuvo `load_metrics_run_20260909.csv` como evidencia histórica.

## Reportes regenerados

- `docs/loading/load_counts.csv`.
- `docs/loading/load_validation.csv`.
- `docs/loading/unicode_validation.csv`.
- `docs/loading/indexes_created.csv`.
- `docs/schema/physical_model_validation.csv`.
- `docs/schema/edition_season_analysis.csv`.
- `docs/loading/load_metrics_run_20260910_retry1.csv`.

## Archivos creados o modificados en esta retry

- `scripts/sql/04_bulk_load_staging.sql`.
- `docs/loading/processed_line_endings_20260910.csv`.
- `docs/loading/bulk_load_rowterminator_fix_20260910.md`.
- `docs/loading/load_metrics_run_20260910_retry1.csv`.
- `docs/loading/post_block4_database_rebuild_retry1.csv`.
- `docs/loading/post_block4_database_rebuild_retry1.md`.
- Reportes regenerados de carga y validación física indicados arriba.

Los CSV oficiales de `data/processed/` conservaron sus hashes; no se ejecutó el cierre integral del Bloque 7.
