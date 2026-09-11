# Reporte de actualización documental y de validación: Bloques 5, 6 y 7

## Estado

**B5_B7_UPDATE_SUCCESS**

La actualización se realizó sin ejecutar SQL Server, sin resets, sin `06_load_final.sql`, sin staging, sin bulk load, sin creación de índices y sin modificar `data/processed/`. Tampoco se modificó la lógica del Bloque 4.

## Conteos oficiales vigentes

| Entidad | Filas |
|---|---:|
| ENTIDAD_GEOGRAFICA | 282 |
| POBLACION | 17,024 |
| NOC | 236 |
| ATLETA | 336,419 |
| SEDE | 42 |
| EDICION_OLIMPICA | 61 |
| DEPORTE | 65 |
| DISCIPLINA | 117 |
| EVENTO | 3,007 |
| PARTICIPACION | 733,414 |
| **Total derivado** | **1,090,667** |

Los valores 338,772, 3,106, 826,605 y 1,186,310 se conservaron únicamente cuando documentan una ejecución anterior, respaldo, auditoría o dry-run pre-Bloque 4.

## Correcciones aplicadas

Se resolvieron los 7 hallazgos `MUST_UPDATE`:

1. `scripts/sql/05_validate_staging.sql` ahora espera 336,419 atletas, 3,007 eventos y 733,414 participaciones.
2. `scripts/sql/08_validate_loaded_data.sql` usa los conteos vigentes para las tablas finales.
3. `scripts/sql/10_final_validation.sql` usa los conteos vigentes en `@expected` y en sus comprobaciones finales.
4. `scripts/python/09_generate_loading_reports.py` usa los conteos vigentes y no fabrica ni reemplaza métricas históricas.
5. `README.md` presenta el estado vigente y conserva el estado pre-Bloque 4 como histórico.
6. `docs/Evidence/Evidences_Bloque7.md` separa expectativas vigentes de la corrida SQL histórica y ya no declara aprobación post-Bloque 4 sin nueva ejecución.
7. Se creó `docs/FINAL_DELIVERY_CHECKLIST.md` con las validaciones SQL aún sin marcar.

## Reportes pendientes

Siguen pendientes, deliberadamente, los cuatro artefactos `GENERATED_REPORT_RECREATE`:

- `docs/loading/load_counts.csv`
- `docs/loading/load_validation.csv`
- `docs/schema/physical_model_validation.csv`
- `docs/final/final_validation_report.csv`

No fueron editados manualmente ni regenerados porque la solicitud prohíbe ejecutar SQL y exige resultados reales. Las métricas históricas de `docs/loading/load_metrics_run_20260909.csv` se preservaron sin recalcular.

## Integridad de `data/processed`

Se comparó cada CSV contra `docs/consolidation/processed_manifest_after_block4_apply.csv`:

**10/10 MATCH.**

No se modificó ningún CSV productivo.

## Ocurrencias obsoletas

La búsqueda posterior confirmó **0 ocurrencias obsoletas usadas como `EXPECTED CURRENT VALUE`** en los validadores y documentos vigentes corregidos.

Las ocurrencias restantes se limitan a:

- reportes generados pendientes de regeneración;
- métricas históricas de la ejecución del 09/09/2026;
- respaldos y manifiestos previos al apply;
- dry-runs y auditorías del Bloque 4;
- identificadores o datos cuyo valor numérico coincide accidentalmente con un conteo anterior.

No se reemplazaron indiscriminadamente esos valores.

## Archivos modificados o creados

- `scripts/sql/05_validate_staging.sql`
- `scripts/sql/08_validate_loaded_data.sql`
- `scripts/sql/10_final_validation.sql`
- `scripts/python/09_generate_loading_reports.py`
- `README.md`
- `docs/Evidence/Evidences_Bloque7.md`
- `docs/FINAL_DELIVERY_CHECKLIST.md`
- `docs/validation/post_block4_b5_b7_update_report.csv`
- `docs/validation/post_block4_b5_b7_update_report.md`

## Estado de cierre

- MUST_UPDATE resueltos: **7/7**.
- GENERATED_REPORT_RECREATE pendientes: **4**.
- Históricos preservados: **sí**.
- `data/processed` SHA-256: **10/10 MATCH**.
- Total vigente: **1,090,667**.
- SQL ejecutado: **no**.
- Reconstrucción de `OlimpiadasDB`: **no iniciada**.

La tarea se detiene aquí. No se declara aprobado el cierre técnico de Bloques 5, 6 y 7 hasta regenerar y revisar los cuatro reportes pendientes con resultados reales.
