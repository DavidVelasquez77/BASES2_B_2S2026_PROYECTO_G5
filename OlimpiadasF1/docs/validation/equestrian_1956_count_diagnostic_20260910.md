# Diagnóstico controlado: conteo Equestrian 1956

Fecha del diagnóstico: 2026-09-10.

## Resultado

La causa del único fallo restante de `11_special_cases_validation.sql` es:

**EXPECTATION_STALE**

La métrica activa `Equestrian.1956_eventos_finales` esperaba **586** y obtuvo **536**. La reproducción independiente sobre los archivos actuales de `data/processed/` obtiene 536 y la consulta SQL de solo lectura obtiene también 536. La diferencia es, por tanto, **-50** respecto del conteo pre-Bloque 4 y no representa pérdida de datos durante la carga.

## Lógica exacta auditada

En `scripts/sql/11_special_cases_validation.sql:13`, la métrica cuenta filas de `olympics.PARTICIPACION` unidas a `EDICION_OLIMPICA` y `EVENTO`, filtrando:

- `e.anio = 1956`;
- `e.temporada = N'Summer'`;
- `ev.nombre LIKE N'%Equestrian%'`.

La métrica cuenta participaciones, no eventos distintos. En el estado actual produce 536 filas, 396 atletas distintos y 6 eventos distintos.

## Comparación pre/post

| Métrica | Pre-Bloque 4 | `data/processed` actual | SQL actual | Diferencia |
|---|---:|---:|---:|---:|
| Participaciones Equestrian 1956 | 586 | 536 | 536 | -50 |
| Atletas distintos | 396 | 396 | 396 | 0 |
| Eventos distintos | 6 | 6 | 6 | 0 |
| Medalla NULL | 514 | 464 | 464 | -50 |
| Gold | 24 | 24 | 24 | 0 |
| Silver | 24 | 24 | 24 | 0 |
| Bronze | 24 | 24 | 24 | 0 |

La coincidencia CSV → SQL es exacta. Los seis eventos permanecen; el cambio está concentrado en filas sin medalla. La distribución por NOC se conserva con la reducción esperada derivada de las mismas 50 filas duplicadas.

## Explicación de las 50 filas

Se filtró `docs/consolidation/final_participation_merge_plan_phase7.csv` a la clave de edición `20` (1956 Summer) y a los seis IDs de evento ecuestre `1961`, `2196`, `2197`, `2302`, `2283` y `2284`.

El resultado fue:

- 50 claves lógicas afectadas;
- 100 filas de entrada;
- 50 filas eliminadas;
- 50 filas supervivientes;
- clasificación en todos los casos: `PREEXISTING_COMPLEMENTARY_DUPLICATE`;
- causa primaria en todos los casos: `PREEXISTING_DUPLICATE`;
- sin `EVENT_ALIAS`;
- sin `ATHLETE_MERGE`.

Esto explica exactamente `586 - 50 = 536`. Las filas no fueron descartadas por una regla nueva de Equestrian ni por la carga SQL: fueron eliminadas por la deduplicación conservadora ya aprobada para duplicados preexistentes. El plan conserva la trazabilidad de cada clave y el archivo opcional `equestrian_1956_removed_rows_explanation_20260910.csv` lista las 50 claves afectadas.

## Estado conceptual de la edición

- `1956 | Summer` existe en el modelo final con `id_edicion = 20`.
- `Equestrian` no existe como temporada independiente.
- Las participaciones ecuestres contabilizadas están bajo `1956 | Summer`.
- La excepción histórica de Stockholm permanece documentada conceptualmente en los reportes de consolidación; no se inventa una procedencia adicional en la tabla final.

## Decisión recomendada, no aplicada

Actualizar únicamente la expectativa de `Equestrian.1956_eventos_finales` en `scripts/sql/11_special_cases_validation.sql` de 586 a 536, o sustituirla por una expectativa derivada del resultado aprobado vigente. Esta recomendación **no se aplicó** en este diagnóstico.

El registro `Equestrian.1956_eventos_finales,586,586,PASS` presente en `docs/final/final_validation_report.csv` es un reporte generado histórico y no debe interpretarse como el resultado SQL actual. Tampoco se modificó ese archivo en esta fase.

## Integridad y alcance

- SHA-256 de `data/processed`: **10/10 MATCH** contra `processed_manifest_after_block4_apply.csv`.
- SQL Server modificado: **NO**.
- `scripts/sql/11_special_cases_validation.sql` modificado: **NO**.
- `data/raw`, `data/intermediate` y `data/processed` modificados: **NO**.
- `12_functional_queries.sql`, el cierre de Bloque 7 y el reporte final no se ejecutaron después de este fallo.

## Archivos

- `equestrian_1956_count_diagnostic_20260910.csv`: métricas reproducidas y conciliadas.
- `equestrian_1956_removed_rows_explanation_20260910.csv`: detalle de las 50 claves del plan de merge que explican la reducción.
