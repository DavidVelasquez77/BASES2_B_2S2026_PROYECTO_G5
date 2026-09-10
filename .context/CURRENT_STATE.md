# CURRENT STATE — PROYECTO OLIMPIADAS FASE 1

## Corte del estado

- Fecha y hora de esta revisión: 2026-09-09 20:19:06 -06:00.
- Proyecto: `OlimpiadasF1`.
- Alcance actual: Fase 1, incisos a, b y c.
- Los incisos d y e quedan fuera del alcance de este integrante.

## Estado del Bloque 1

El Bloque 1 está **técnicamente concluido** y su cierre documental fue intentado en esta sesión. El cierre visual completo queda condicionado por una limitación del entorno: Computer Use no expuso aplicaciones nativas locales (`apps: []`), por lo que no fue posible abrir Docker Desktop, SSMS, una aplicación de terminal ni una herramienta local para capturar y guardar imágenes reales.

No se fabricaron ni simularon capturas.

La matriz detallada está en:

- `OlimpiadasF1/docs/Evidence/Evidences.md`

## Hechos establecidos por el handoff y el estado del proyecto

- La base objetivo es SQL Server 2025 Developer Edition ejecutado mediante Docker.
- La base se llama `OlimpiadasDB`.
- Los schemas previstos son `stg` y `olympics`.
- El contenedor previsto es `olimpiadas-sqlserver`.
- El mapeo de puertos previsto es `1434:1433`.
- El montaje previsto es `./data:/var/opt/mssql/import:ro`.
- El volumen persistente previsto es `sqlserver_data:/var/opt/mssql`.
- El manifiesto de fuentes usa SHA-256 y se genera mediante `scripts/python/00_source_manifest.py`.
- El modelo final contiene diez entidades: `ENTIDAD_GEOGRAFICA`, `POBLACION`, `NOC`, `ATLETA`, `SEDE`, `EDICION_OLIMPICA`, `DEPORTE`, `DISCIPLINA`, `EVENTO` y `PARTICIPACION`.
- No se deben crear entidades `FUENTE`, `RESULTADO`, `TIPO_MEDALLA` ni `MEDALLA`.

## Comprobaciones realizadas en esta sesión

- Se encontraron exactamente 10 CSV en `OlimpiadasF1/data/raw`.
- `OlimpiadasF1/docs/source_manifest.csv` contiene 10 registros de archivos además del encabezado.
- Existe una evidencia visual preexistente: `OlimpiadasF1/docs/img/evidence_00_create_database.sql.png`.
- Esa imagen fue inspeccionada y muestra SSMS con `localhost,1434`, `OlimpiadasDB`, el script `00_create_database.sql`, ejecución correcta y fecha/hora visibles.
- El cliente Docker no pudo conectarse al daemon desde esta sesión debido a acceso denegado al pipe `docker_engine`.
- El ejecutable de `.venv` existe, pero no pudo iniciarse por acceso denegado.
- El Python global disponible respondió `3.12.7`; `pip` no está disponible en ese intérprete.

## Evidencias pendientes

No se obtuvieron capturas nuevas para Docker, versión de SQL Server, schemas, persistencia, montaje de datos, entorno Python, código y ejecución del manifiesto ni contenido del CSV. La causa común es la ausencia de aplicaciones locales accesibles mediante Computer Use; el detalle por evidencia está en `Evidences.md`.

## Estado del Bloque 2

El profiling diagnóstico del Bloque 2 fue ejecutado sin modificar `data/raw`.

- Script: `OlimpiadasF1/scripts/python/01_profile_sources.py`.
- CSV analizados: 10.
- Columnas perfiladas: 171.
- Detecciones especiales reportadas: 357.
- SHA-256 coincidentes: 10/10.
- `data/raw` intacto: sí.
- Python: 3.14.7.
- pandas: 3.0.5.
- Reportes: `OlimpiadasF1/docs/profiling/`.
- Documentación: `OlimpiadasF1/docs/Evidence/Evidences_Bloque2.md`.

El Bloque 2 **no está aprobado**. Las evidencias visuales reales quedan pendientes porque Computer Use no expuso aplicaciones nativas locales en esta sesión. No se inventaron capturas.

## Estado del Bloque 3

El Bloque 3 está **ejecutado y pendiente de revisión; no está aprobado**. Se creó el script reproducible:

- `OlimpiadasF1/scripts/python/02_clean_and_standardize.py`

Resultados técnicos:

- 10/10 archivos RAW procesados y validados.
- 10 archivos intermedios generados en `OlimpiadasF1/data/intermediate/cleaned/`.
- 0 filas descartadas.
- 10/10 hashes SHA-256 coincidentes antes y después.
- `data/raw` intacto.
- 1,604,828 valores realmente modificados y 9,218,178 operaciones/valores procesados; ambas métricas están separadas.
- 22,647 combinaciones de valores no resueltos documentadas, con frecuencia acumulada de 83,423.
- La matriz explícita de ausencia está en `OlimpiadasF1/docs/cleaning/missing_value_matrix.csv`; no se aplican NA/N/A/null/None globalmente a campos descriptivos.
- Duplicados exactos analizados y conservados: 126 en `clean/results.csv`, 110 en `raw/results.csv` y 1,385 en `athlete_events.csv`.
- No se realizó carga SQL ni Bloque 5.
- Se generaron los reportes en `OlimpiadasF1/docs/cleaning/` y la documentación en `OlimpiadasF1/docs/Evidence/Evidences_Bloque3.md`.
- Una segunda ejecución y comparación SHA-256 se utilizó para verificar que las salidas fueran idempotentes.

## Estado del Bloque 4

El Bloque 4 está **ejecutado y técnicamente aprobado**. Se creó y ejecutó el script reproducible:

- `OlimpiadasF1/scripts/python/03_match_and_consolidate.py`

Resultados técnicos de la ejecución corregida:

- 10 tablas finales regeneradas en `OlimpiadasF1/data/processed/`.
- 338,772 atletas globales.
- Matching externo: 177,741 STRONG, 496 CONTEXTUAL, 2,857 AMBIGUOUS y 190,415 UNMATCHED; fuzzy automático 0.
- 14,545 matches previamente existentes cambiaron en ID global, estado o tipo respecto a la ejecución anterior.
- 832,189 participaciones de entrada y 826,605 retenidas después de deduplicación documentada.
- Se excluyó únicamente de `data/processed/participacion.csv` la fila de Sotirios Versis asociada a `1888-89 Zappas Olympic Games`, conservándola en RAW, intermedios y `docs/consolidation/excluded_non_official_participations.csv`.
- Fuente 4: 100/100 filas con match exacto normalizado contra Fuente 2; las 100 se excluyen de la salida consolidada.
- Fuente 1 RAW/CLEAN: 299,462 matches seguros y 102,995 atributos enriquecidos; la edición histórica incompleta no pudo resolverse.
- ENTIDAD_GEOGRAFICA: 282 filas; se corrigieron 81 duplicados conceptuales y no quedan duplicados normalizados reportados.
- Nacionalidad de participación: 81 filas resueltas; ningún valor presente quedó sin correspondencia.
- NOC: 231 resueltos y 5 no resueltos.
- Deporte-disciplina: 313 mapeos resueltos, que cubren las 832,189 participaciones de entrada, y 0 pendientes de revisión.
- Validaciones de modelo: 56 PASS y 0 FAIL. La participación fuera del alcance oficial fue excluida únicamente de la salida procesada, sin modificar RAW ni intermedios.
- Revisión puntual posterior al Bloque 5: `1956 | Equestrian` (300 participaciones) se homologó a `1956 | Summer` con sede final Melbourne y excepción histórica Stockholm auditada; `1906 | Summer` se homologó a `1906 | Intercalated Games` después de comparar 1,733 filas de Fuente 2, 1,733 de Fuente 3 y 2,300 de Fuente 1. Youth Olympic Games se conservaron.
- Resultado posterior: 61 ediciones, 826,605 participaciones, 0 duplicados nuevos producidos por el remapeo y 56/56 validaciones PASS.
- SHA-256 RAW: 10/10 MATCH; `data/raw` y `data/intermediate/cleaned` permanecen intactos.
- Idempotencia: dos ejecuciones produjeron hashes idénticos para los 10 CSV de `data/processed/`.
- El Bloque 5 fue iniciado únicamente para crear y validar el modelo físico vacío. No se cargaron datos y no se inició el Bloque 6.

La documentación oficial está en `OlimpiadasF1/docs/Evidence/Evidences_Bloque4.md`; los reportes técnicos están en `OlimpiadasF1/docs/consolidation/` y `OlimpiadasF1/data/intermediate/matching/`.

## Estado del Bloque 5

El Bloque 5 está **ejecutado técnicamente y aprobado como prerequisito del Bloque 6**.

- Se crearon exactamente diez tablas bajo `OlimpiadasDB.olympics`.
- No se crearon tablas finales en `dbo` ni tablas lógicas adicionales.
- Las diez tablas están vacías.
- Validación física de CSV: cobertura completa 66/66 columnas; 66 PASS y 0 FAIL.
- La validación física calcula precisión/escala observadas, capacidad entera y redondeo potencial. El DDL definitivo usa `DECIMAL(19,16)` para latitud/longitud y `DECIMAL(16,13)` para peso registrado, sin redondeo.
- Validación del schema SQL: 10 tablas, 66 columnas, 10 PK, 6 UNIQUE, 14 FK y 3 CHECK inspeccionados correctamente; además, `sys.columns.precision` y `sys.columns.scale` coinciden con el contrato definitivo de las siete columnas DECIMAL.
- Análisis de temporadas: 61 ediciones agrupadas en Summer (30), Winter (24), Intercalated Games (1), Summer Youth (3) y Winter Youth (3), sin `Equestrian`, documentado en `OlimpiadasF1/docs/schema/edition_season_analysis.csv`.
- `EDICION_OLIMPICA.temporada` admite únicamente `Summer`, `Winter`, `Intercalated Games`, `Summer Youth` y `Winter Youth`.
- El reset controlado de desarrollo se ejecutó sobre las diez tablas vacías y luego se recreó el schema físico sin cargar datos.
- No se modificaron `data/processed`, `data/raw` ni `data/intermediate/cleaned`.
- Se documentaron dos ajustes de capacidad: `temporada NVARCHAR(20)` y `titulos NVARCHAR(2000)`.
- El schema quedó preparado para la carga y no se modificaron los CSV.

La documentación está en `OlimpiadasF1/docs/Evidence/Evidences_Bloque5.md`; los scripts están en `OlimpiadasF1/scripts/sql/` y `OlimpiadasF1/scripts/python/04_validate_physical_model.py`.

## Estado del Bloque 6

El Bloque 6 está **ejecutado técnicamente y pendiente de revisión externa; no está aprobado**.

- Se crearon diez tablas staging bajo `OlimpiadasDB.stg` y se cargaron exactamente los diez CSV de `data/processed` desde `/var/opt/mssql/import/processed/`.
- Las diez tablas `OlimpiadasDB.olympics` se cargaron mediante INSERT explícito por columna y transacciones por entidad.
- Conteos finales: ENTIDAD_GEOGRAFICA 282, POBLACION 17,024, NOC 236, ATLETA 338,772, SEDE 42, EDICION_OLIMPICA 61, DEPORTE 65, DISCIPLINA 117, EVENTO 3,106 y PARTICIPACION 826,605.
- Validaciones: 0 duplicados de PK, 0 FK huérfanas, 0 conversiones inválidas, 0 truncamientos, 0 redondeos, 0 dominios inválidos; 10 PK, 6 UNIQUE, 14 FK y 3 CHECK activos.
- Se crearon ocho índices no cluster justificados después de la carga.
- La auditoría Unicode compara exactamente `data/processed/atleta.csv` contra `olympics.ATLETA` por `id_atleta`: 26,261 nombres no ASCII, 26,261 comparados y 0 diferencias.
- Los tiempos se conservan como evidencia histórica en `OlimpiadasF1/docs/loading/load_metrics_run_20260909.csv`; el generador no los vuelve a fabricar.
- `05_validate_staging.sql` produce ahora una auditoría completa con `validacion`, `esperado`, `actual`, `estado` y `detalle`, y el reporte Python consulta esa salida real.
- La reejecución segura fue probada: el preflight abortó con mensaje claro y `PARTICIPACION` permaneció en 826,605 filas.
- RAW SHA-256: 10/10 MATCH. `data/raw`, `data/intermediate/cleaned` y `data/processed` permanecen intactos.
- Reportes: `OlimpiadasF1/docs/loading/`; documentación: `OlimpiadasF1/docs/Evidence/Evidences_Bloque6.md`.
- No se inició el Bloque 7.

## Próximo paso autorizado

Revisar externamente la estrategia de staging, las validaciones de carga, los índices adicionales y las evidencias visuales del Bloque 6 antes de aprobarlo o iniciar el Bloque 7.
