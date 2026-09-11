# Auditoría posterior a la aplicación del Bloque 4: Bloques 5, 6 y 7

Fecha de auditoría: 2026-09-10.

## Alcance y restricciones

Se revisaron los artefactos de Bloques 5, 6 y 7, además de los scripts SQL/Python, reportes de carga, validaciones, documentación principal y artefactos de consolidación relacionados con los conteos anteriores.

Esta auditoría fue exclusivamente de lectura sobre los artefactos existentes. No se ejecutó SQL, no se modificó SQL Server, no se ejecutaron resets, no se ejecutó `06_load_final.sql`, no se modificó `data/processed/` y no se alteró la lógica ni la documentación operativa del Bloque 4. Los únicos archivos creados son este informe y `post_block4_b5_b7_audit.csv`.

## Estado oficial usado como referencia

Los conteos vigentes posteriores al apply oficial del Bloque 4 son:

| Entidad | Filas vigentes |
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

El total derivado vigente de las diez entidades es **1,090,667**. El total anterior **1,186,310** corresponde a la suma pre-Bloque 4 y no es vigente.

## Resumen de hallazgos

| Clasificación | Cantidad | Tratamiento |
|---|---:|---|
| MUST_UPDATE | 7 | Requieren actualización antes de presentar Bloques 5-7 como estado final vigente. |
| GENERATED_REPORT_RECREATE | 4 | Deben regenerarse a partir de resultados reales posteriores; no se regeneraron en esta auditoría porque eso exigiría ejecutar validaciones/carga SQL. |
| HISTORICAL_KEEP | 9 | Se conservan porque documentan una ejecución, respaldo, proyección o aprobación anterior. No deben interpretarse como conteos vigentes. |
| NO_ACTION | 6 | No contienen hardcodes obsoletos o contienen identificadores/datos que no deben reemplazarse por coincidencia textual. |

El detalle auditable está en `post_block4_b5_b7_audit.csv`.

## Hallazgos MUST_UPDATE

1. `scripts/sql/05_validate_staging.sql` espera 338,772 atletas, 3,106 eventos y 826,605 participaciones. Debe actualizarse a 336,419, 3,007 y 733,414.
2. `scripts/sql/08_validate_loaded_data.sql` mantiene los mismos tres conteos pre-Bloque 4 y debe actualizarse.
3. `scripts/sql/10_final_validation.sql` mantiene esos conteos en la tabla esperada y en comprobaciones explícitas. Debe actualizarse antes de cualquier validación final futura.
4. `scripts/python/09_generate_loading_reports.py` fija esos valores en su lista de expectativas y debe actualizarse sin fabricar métricas históricas.
5. `README.md` presenta los tres conteos antiguos como finales.
6. `docs/Evidence/Evidences_Bloque7.md` presenta el universo anterior como resultado final del Bloque 7.
7. `docs/FINAL_DELIVERY_CHECKLIST.md` no está presente, aunque es referenciado desde `README.md`; requiere resolución documental posterior.

## Reportes que requieren regeneración

`docs/loading/load_counts.csv`, `docs/loading/load_validation.csv`, `docs/schema/physical_model_validation.csv` y `docs/final/final_validation_report.csv` contienen observaciones del universo anterior. Deben regenerarse desde consultas o validaciones reales contra el estado posterior al Bloque 4. En esta auditoría no se regeneraron para respetar la prohibición de ejecutar SQL y no se editaron manualmente.

Las métricas de `docs/loading/load_metrics_run_20260909.csv` no se clasifican como regenerables: son evidencia histórica de una corrida real del 09/09/2026. Sus valores no deben cambiarse por `datetime.now()` ni presentarse como medición del estado vigente.

## Histórico que debe conservarse

Se conservaron conceptualmente como históricos los conteos anteriores presentes en `Evidences_Bloque4.md`, `Evidences_Bloque5.md`, `Evidences_Bloque6.md`, los manifiestos y reportes de `docs/consolidation/`, y los dry-runs de Phase 7. Esos valores explican el cambio oficial `338,772 -> 336,419`, `3,106 -> 3,007` y `826,605 -> 733,414`.

En particular, `docs/consolidation/block4_apply_report.csv` y `processed_backup_manifest_before_apply.csv` deben conservar sus filas/hashes anteriores porque son la evidencia del estado respaldado y de la transformación aplicada. No son fuentes de conteos finales.

## Compatibilidad del modelo físico

La revisión no identificó una incompatibilidad estructural del modelo físico con 336,419 filas de `ATLETA`, 3,007 de `EVENTO` y 733,414 de `PARTICIPACION`. Los valores obsoletos se encontraron en expectativas y reportes materializados, no como una razón para cambiar tablas, columnas, PK, UQ, FK, CHECK o tipos DECIMAL.

La corrección requerida es de expectativas y reportes: actualizar los validadores y regenerar los informes con datos reales. No se autoriza deducir cambios físicos ni ejecutar una recarga como parte de esta auditoría.

## Totales y pruebas revisadas

- Conteos esperados: deben usar el universo vigente indicado arriba.
- Suma anterior: 1,186,310; se mantiene únicamente como histórico.
- Suma vigente derivada: 1,090,667.
- Validaciones de Unicode, FK, consultas especiales y pruebas funcionales: los scripts/reportes deben revisarse nuevamente después de actualizar sus expectativas; la existencia de un reporte histórico no demuestra que sus números sigan correspondiendo al `data/processed/` actual.
- Ocurrencias aisladas de `3106` o `338772` en `docs/consolidation/` pueden ser IDs o datos de auditoría. No deben reemplazarse automáticamente.

## Archivos revisados

Se revisaron `scripts/sql/`, `scripts/python/`, `docs/loading/`, `docs/schema/`, `docs/final/`, `docs/consolidation/`, `docs/Evidence/`, `README.md` y `docs/EXECUTION_ORDER.md`. También se comprobó la referencia a `docs/FINAL_DELIVERY_CHECKLIST.md`, que no está presente.

## Estado de esta auditoría

**AUDIT_ONLY — NO SE EJECUTÓ SQL — NO SE MODIFICÓ SQL SERVER — NO SE ALTERARON CSV PRODUCTIVOS.**

La auditoría queda detenida aquí. Los hallazgos `MUST_UPDATE` y los reportes `GENERATED_REPORT_RECREATE` requieren una tarea posterior explícita antes de considerar vigentes las validaciones documentales de Bloques 5, 6 y 7.
