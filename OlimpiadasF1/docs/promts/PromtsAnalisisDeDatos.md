# Versionamiento de prompts — Análisis de Datos OlimpiadasF1

## Propósito

Este documento conserva el historial funcional de las solicitudes realizadas para el proyecto OlimpiadasF1. Cada versión identifica el bloque, el objetivo, las restricciones, los entregables y los cambios introducidos respecto de la versión anterior.

Las fechas exactas de los mensajes no están disponibles en el historial consolidado; por ello se utiliza versionamiento secuencial y no se inventan fechas. El nombre de archivo mantiene la grafía solicitada: `PromtsAnalisisDeDatos.md`.

## Convención

- `P00`: contexto y alcance inicial.
- `P01` a `P07`: bloques del proyecto.
- `.0`: solicitud inicial de un bloque.
- `.1`, `.2`, etc.: correcciones o revisiones posteriores del mismo bloque.
- Una revisión de un bloque no autoriza iniciar el siguiente.

## Índice de versiones

| Versión | Bloque | Tipo | Resultado o alcance |
|---|---|---|---|
| P00.1 | Contexto | Inicial | Leer el handoff y confirmar alcance, sin ejecutar cambios. |
| P01.0 | Bloque 1 | Cierre | Crear estado actual y cerrar formalmente el bloque. |
| P02.0 | Bloque 2 | Inicial | Profiling diagnóstico reproducible de 10 CSV. |
| P03.0 | Bloque 3 | Inicial | Limpieza y homologación por fuente. |
| P03.1 | Bloque 3 | Corrección | Ajustar ausencia, fechas, posiciones y métricas. |
| P04.0 | Bloque 4 | Inicial | Matching, deduplicación y consolidación. |
| P04.1 | Bloque 4 | Corrección | Corregir matching por sexo/NOC y contextual. |
| P04.2 | Bloque 4 | Corrección final | Excluir únicamente Zappas fuera del alcance oficial. |
| P05.0 | Bloque 5 | Inicial | Crear y validar modelo físico SQL Server. |
| P04.3 | Bloque 4 | Revisión puntual | Homologar Equestrian 1956 y resolver 1906. |
| P05.1 | Bloque 5 | Reanudación | Actualizar DECIMAL, temporada y validar schema final. |
| P06.0 | Bloque 6 | Inicial | Cargar datos mediante staging e índices. |
| P06.1 | Bloque 6 | Auditoría final | Corregir métricas históricas y validar Unicode exactamente. |
| P07.0 | Bloque 7 | Inicial | Validación global, cierre documental y handoff. |
| P07.1 | Documentación | Solicitud actual | Versionar este historial de prompts. |

---

## P00.1 — Lectura inicial del contexto

### Solicitud

Leer primero `.context/WORK_HANDOFF.md` y todo `.context`, no ejecutar acciones todavía y confirmar:

1. qué se entendió del proyecto;
2. cuál es el alcance del usuario;
3. cuál es el estado actual.

### Restricción

No modificar archivos ni avanzar de bloque hasta confirmar la comprensión del contexto.

---

## P01.0 — Cierre formal del Bloque 1

### Solicitud

Cerrar formalmente el Bloque 1 y crear `.context/CURRENT_STATE.md` con el estado actual.

Obtener evidencias reales de:

- Docker con `olimpiadas-sqlserver` y `1434->1433`;
- versión de SQL Server en SSMS;
- ejecución de `00_create_database.sql`;
- existencia de `OlimpiadasDB`, `stg` y `olympics`;
- persistencia del contenedor;
- montaje de `raw`, `intermediate`, `processed` y los 10 CSV;
- entorno Python;
- código y ejecución de `00_source_manifest.py`;
- salida `Archivos encontrados: 10`;
- contenido de `source_manifest.csv`.

Para cada evidencia se pidió abrir la aplicación correspondiente, mostrar el resultado correcto, incluir fecha y hora del sistema, guardar la captura en `docs/img/`, agregarla a `docs/Evidence/Evidences.md` y documentar qué demuestra.

### Restricciones

- No fabricar ni simular capturas.
- Si una aplicación local no fuese accesible, detenerse únicamente en esa evidencia y reportar la causa.
- No iniciar el Bloque 2.

---

## P02.0 — Bloque 2: Data Profiling

### Preparación obligatoria

Leer completamente `.context`, el modelo ER vigente y revisar `data/raw`. Confirmar exactamente 10 CSV fuente.

### Objetivo

Crear `scripts/python/01_profile_sources.py` para perfilar automáticamente todos los CSV bajo `data/raw`, sin limpiar, transformar, homologar, cambiar valores, eliminar duplicados ni hacer matching.

### Métricas requeridas

Por archivo: fuente, ruta relativa, nombre, filas, columnas, nombres de columnas, tipos inferidos, filas/columnas vacías, duplicados exactos, tamaño y codificación.

Por columna: tipo, nulos, porcentaje de nulos, únicos, cardinalidad, longitudes, mínimos/máximos numéricos y muestras razonables.

Detectar sin modificar: vacíos, espacios, `NA`, `N/A`, `nan`, `null`, `None`, `No medal`, `DNS`, `DNF`, `DSQ`, `DQ`, posiciones como `=17`, Unicode y valores numéricos sospechosos.

Analizar específicamente fechas, años, numéricos, identificadores, NOC, medallas y posiciones de Fuente 1.

### Salidas

Crear `docs/profiling/` con:

- `summary_files.csv`;
- `summary_columns.csv`;
- `special_values.csv`;
- `profiling_summary.md`;
- `Evidences_Bloque2.md`.

### Validaciones y límites

- Analizar exactamente 10 CSV.
- Comparar SHA-256 contra `docs/source_manifest.csv`.
- No modificar `data/raw`.
- No iniciar el Bloque 3.
- No declarar aprobado el Bloque 2.

---

## P03.0 — Bloque 3: reglas de limpieza y homologación

### Preparación

Leer `.context`, `docs/profiling/profiling_summary.md`, los cuatro CSV de profiling y el modelo ER vigente. Si existe contradicción con el modelo ER, reportarla antes de decidir.

### Objetivo

Aplicar reglas reproducibles e idempotentes sobre los datos originales, generar archivos por fuente en `data/intermediate/cleaned/` y no modificar `data/raw`.

### Reglas principales

- Validar SHA-256 antes y después.
- Aplicar `strip()` solo a columnas textuales.
- Conservar tildes, Unicode y nombres originales.
- No aplicar `Unidecode` al valor final.
- Normalizar marcadores de ausencia de forma dependiente de archivo/columna.
- Convertir `No medal` a `NULL` solo en columnas de medalla.
- Normalizar medallas a `Gold`, `Silver`, `Bronze` o `NULL`.
- Transformar `Pos` en columnas auxiliares `posicion`, `empatado`, `estado_resultado` y `pos_original`.
- No inventar interpretación para posiciones complejas; reportarlas como no resueltas.
- Validar fechas completas a ISO y analizar por separado fechas parciales y formatos de biografías.
- Homologar año/temporada sin alterar correspondencias.
- Convertir edad, altura y peso cuando sea seguro, conservando atípicos.
- Diferenciar nombre descriptivo de NOC y código de tres letras.
- Conservar agregados de población y convertir `populations.csv` a formato largo.
- Conservar identificadores originales únicamente en intermedios.
- Analizar duplicados sin eliminarlos automáticamente.

### Entregables

Crear `scripts/python/02_clean_and_standardize.py`, `docs/cleaning/` con reglas, resumen, no resueltos, duplicados y documentación, además de `docs/Evidence/Evidences_Bloque3.md`.

### Límites

No realizar matching, deduplicación global, consolidación final, CSV finales, carga SQL ni Bloque 4.

---

## P03.1 — Corrección del Bloque 3

### Motivo

Una revisión externa detectó tres problemas en `02_clean_and_standardize.py`.

### Cambios exigidos

1. `normalize_missing()` no debe convertir `NA`, `N/A`, `null` o `None` globalmente. Implementar una matriz por archivo/columna y conservar esos textos en columnas descriptivas cuando sean valores legítimos.
2. `parse_iso_date()` no debe convertir mes/año en una fecha con día 1. Solo producir ISO cuando día, mes y año estén explícitos; fechas parciales quedan documentadas como no resueltas.
3. `normalize_positions()` debe usar contadores explícitos por fila para posición segura, empate, estado conocido, complejo no resuelto y sin resultado. No usar `len(frame) - len(unresolved)`.
4. `valores_modificados` solo cuenta valores que realmente cambian. Procesamiento y modificación deben ser métricas distintas.

### Reejecución obligatoria

Regenerar los 10 intermedios y reportes, actualizar `Evidences_Bloque3.md`, verificar SHA-256 10/10, idempotencia y que no se inició el Bloque 4.

---

## P04.0 — Bloque 4: matching, deduplicación y consolidación

### Preparación

Leer `.context`, el modelo ER, todos los reportes de profiling y limpieza y los 10 archivos intermedios.

### Objetivo

Consolidar las cuatro fuentes en `data/processed/`, resolviendo atletas, NOC, entidades geográficas, deportes, disciplinas, eventos, ediciones, sedes, participaciones y duplicados, sin crear tablas ni cargar SQL Server.

### Matching

- No fusionar por nombre parecido, país, deporte o año aislados.
- Usar IDs originales solo como evidencia dentro de su fuente.
- Nivel A: determinístico fuerte.
- Nivel B: determinístico contextual.
- Nivel C: fuzzy solo como apoyo y nunca con fusión automática por umbral.
- Conservar candidatos, score, criterio y estados `MATCHED`, `UNMATCHED`, `AMBIGUOUS`.
- Mantener nombres originales y claves auxiliares de matching separadas.

### Consolidación

Crear maestro de atletas, correspondencias de matching, entidades, NOC, población larga, sedes, ediciones, deporte-disciplina-evento y participaciones. Respetar la jerarquía `DEPORTE → DISCIPLINA → EVENTO`.

### Deduplicación y Fuente 4

Comparar por clave lógica, clasificar duplicados y eliminar solo equivalencias demostrables. Verificar si `datalab_export.csv` es subconjunto de Fuente 2 y documentar el solapamiento.

### Reportes

Generar conflictos, mappings, deduplicación, conteos, resumen de consolidación, validaciones de PK/FK, hashes RAW e idempotencia. Crear `scripts/python/03_match_and_consolidate.py` y `Evidences_Bloque4.md`.

### Límites

No cargar SQL, no crear tablas o índices SQL, no crear procedimientos y no iniciar Bloque 5.

---

## P04.1 — Corrección del Bloque 4

### Cambios exigidos por revisión externa

- Eliminar obligatoriamente candidatos incompatibles por sexo y NOC aunque el conjunto filtrado quede vacío.
- Implementar matching contextual determinístico usando nombre, sexo, NOC, año/edición, deporte/disciplina y evento; fusionar solo si queda un candidato único.
- No usar fuzzy automático.
- Reportar por separado `STRONG`, `CONTEXTUAL`, `AMBIGUOUS` y `UNMATCHED`.
- Auditar `build_entities()` para no crear entidades solo por diferencia entre `codigo_noc` y `country_code`.
- Documentar equivalencias por nombre normalizado y mappings explícitos.
- Mantener NOC especiales sin entidad cuando corresponda.
- Revisar longitudes y constraints contra los CSV finales.
- Regenerar outputs, reportes, validaciones, hashes e idempotencia.

### Restricciones

No modificar RAW/intermedios, no iniciar Bloque 5 y no forzar ambiguos o no encontrados.

---

## P04.2 — Corrección final del Bloque 4: participación Zappas

### Problema

El único `FAIL` restante correspondía a una participación de Sotirios Versis asociada a `1888-89 Zappas Olympic Games`.

### Decisión obligatoria

- No inventar año, temporada ni `id_edicion`.
- No asignar a Athens 1896.
- Excluir únicamente esa participación de `data/processed/participacion.csv`.
- Conservar RAW e intermedios.
- Registrar fuente, archivo, fila, IDs, atleta, Games original, evento, motivo, criterio y referencia en `excluded_non_official_participations.csv`.
- Usar como referencia que Athens 1896 fueron los primeros Juegos Olímpicos modernos.

### Revalidación

Reconstruir `participacion.csv`, renumerar IDs si corresponde, regenerar deduplicación, conteos y validaciones, verificar SHA-256, intermedios e idempotencia. No modificar los cinco NOC sin entidad solo para conseguir PASS, ni fusionar `AMBIGUOUS` o `UNMATCHED`.

---

## P05.0 — Bloque 5: modelo físico SQL Server

### Objetivo

Crear y validar el modelo físico de SQL Server sin cargar datos.

### Alcance

- Diez tablas bajo `olympics`.
- Schema `stg` solo como infraestructura ETL.
- 66 columnas, 10 PK, 6 UNIQUE, 14 FK y 3 CHECK.
- Crear `01_create_tables.sql`, `02_validate_schema.sql` y opcionalmente `04_validate_physical_model.py`.
- Validar tipos, longitudes, nulos, dominios, precisión decimal, IDs, fechas y coordenadas contra los CSV finales.

### Decisiones físicas iniciales

Usar `NVARCHAR` para Unicode, `BIGINT` cuando corresponda, `DECIMAL(5,2)` para altura/peso/edad, `DECIMAL(9,6)` inicialmente para coordenadas y `NVARCHAR(10)` inicialmente para temporada. Mantener títulos con capacidad suficiente y reportar ajustes respecto al ER.

### Restricciones

No ejecutar `BULK INSERT`, cargas, inserts masivos, Python de carga ni staging de datos. Las tablas deben quedar vacías. No iniciar Bloque 6 ni declarar aprobación.

---

## P04.3 — Revisión puntual del Bloque 4 motivada por Bloque 5

### Youth

Conservar `Summer Youth` y `Winter Youth`. Documentar que `temporada` funciona como categoría/tipo de edición, no solo como estación.

### Equestrian 1956

Investigar las 300 participaciones `1956 | Equestrian`, homologarlas a `1956 | Summer`, mantener Melbourne como sede principal y documentar Stockholm como excepción histórica sin crear una segunda edición.

Generar `docs/consolidation/edition_special_cases.csv`.

### 1906

Comparar todas las participaciones de `1906 | Summer` y `1906 | Intercalated Games` por atleta, evento, NOC/equipo y resultado. Si son equivalentes, conservar solo `Intercalated Games`; si no, documentar la diferencia.

### Límites

Mantener matching aprobado, ambiguos y no encontrados, Fuente 4, NOC nullable, jerarquía deportiva, exclusión Zappas y deduplicación conservadora. No cambiar precisión física ni DDL en esta revisión.

---

## P05.1 — Reanudación del Bloque 5

### Cambios físicos

Actualizar:

```text
ATLETA.latitud DECIMAL(19,16)
ATLETA.longitud DECIMAL(19,16)
PARTICIPACION.peso_kg_registrado DECIMAL(16,13)
```

Mantener `DECIMAL(5,2)` para altura, peso, edad y altura registrada; mantener `titulos NVARCHAR(2000)` y `temporada NVARCHAR(20)`.

### Validaciones

- Validación física exacta 66/66.
- Validación de precision/scale en Python y `sys.columns`.
- CHECK de temporada solo con `Summer`, `Winter`, `Intercalated Games`, `Summer Youth` y `Winter Youth`.
- Crear/recrear tablas vacías de desarrollo sin cargar datos.
- Confirmar 10 tablas, 10 PK, 6 UNIQUE, 14 FK, 3 CHECK, cero tablas en `dbo`, 10 tablas vacías.
- Confirmar 61 ediciones y 826,605 participaciones en los CSV, sin modificar `data/processed`.

No declarar aprobado el Bloque 5 ni iniciar Bloque 6.

---

## P06.0 — Bloque 6: carga de datos e índices

### Objetivo

Cargar exactamente los 10 CSV de `data/processed/` en SQL Server mediante staging reproducible, auditable, compatible con UTF-8, respetando NULL, constraints, precisión y conteos.

### Estrategia obligatoria

- Verificar `/var/opt/mssql/import/processed/` antes de cargar.
- Crear staging bajo `stg`.
- Probar `BULK INSERT` con `FORMAT='CSV'`, `FIELDQUOTE='"'`, `FIRSTROW=2`, `CODEPAGE='65001'` y terminador `\n`.
- Convertir explícitamente staging → final con `TRY_CONVERT`/`TRY_CAST` durante prevalidación.
- Validar nulos obligatorios, duplicados PK, FK potenciales, dominios, longitudes y DECIMAL.
- Detener la carga si existe cualquier error real.

### Orden y seguridad

Cargar en orden de dependencias: entidad, deporte, NOC, atleta, sede, edición, disciplina, evento, población y participación.

Usar transacciones, `SET XACT_ABORT ON` y abortar si alguna tabla final ya contiene datos. No ejecutar automáticamente DELETE, TRUNCATE o DROP.

### Resultados requeridos

Comparar CSV vs staging vs SQL final, validar 10/10 entidades, PK/FK/CHECK, Unicode, siete DECIMAL, índices justificados, métricas de tiempo e integridad RAW/intermedios/processed.

Crear scripts SQL de staging, validación, carga, índices y validación final; reportes de carga y `Evidences_Bloque6.md`. No iniciar Bloque 7 ni declarar aprobación.

---

## P06.1 — Auditoría final del Bloque 6

### Correcciones exigidas

1. `09_generate_loading_reports.py` no debe fabricar timestamps ni duraciones. Conservarlos como evidencia histórica de la corrida del 09/09/2026 y no regenerarlos con `datetime.now()`.
2. No hardcodear `staging_prevalidacion`, conversiones inválidas, truncamientos ni not-null. `05_validate_staging.sql` debe emitir `validacion`, `esperado`, `actual`, `estado` y `detalle`; Python debe consultar esos resultados.
3. Comparar exactamente `data/processed/atleta.csv` contra `olympics.ATLETA` por `id_atleta` para nombres no ASCII. Resultado esperado: 26,261 comparados y 0 diferencias. Crear `unicode_validation.csv`.
4. Mantener conteos, PK/FK/CHECK, siete DECIMAL y ocho índices ya validados.
5. Actualizar `Evidences_Bloque6.md` distinguiendo SQL directo, tiempos históricos y comparación Unicode exacta.

### Prohibiciones

No recargar, no ejecutar `06_load_final.sql`, no borrar, truncar, eliminar ni iniciar Bloque 7.

---

## P07.0 — Bloque 7: validación final y preparación de entrega

### Restricciones

Los Bloques 1–6 se consideran ejecutados/aprobados técnicamente. No modificar datos, no ejecutar limpieza, matching, consolidación, carga, resets, DELETE, TRUNCATE o DROP. No recrear la base ni implementar procedimientos almacenados de atleta/país.

### Validación global

Crear `scripts/sql/10_final_validation.sql` para validar 10 tablas, 66 columnas, conteos exactos, 10 PK, 6 UNIQUE, 14 FK, 3 CHECK, 8 índices, 0 PK duplicadas, 0 FK huérfanas, dominios válidos y magnitudes principales. Emitir `RESULTADO_GLOBAL = PASS` solo si todo pasa.

### Casos especiales

Crear `11_special_cases_validation.sql` para verificar:

- 1906 como `Intercalated Games` y ausencia de `1906 Summer`;
- ausencia de edición `Equestrian`;
- participación ecuestre de 1956 bajo `1956 Summer`;
- ausencia final de la participación Zappas;
- tres ediciones `Summer Youth` y tres `Winter Youth`.

### Consultas funcionales

Crear `12_functional_queries.sql` sin procedimientos almacenados. Demostrar JOIN de atleta por toda la jerarquía, relación por país/NOC, Unicode, medallas, ausencia de medalla, DNF, DNS, DQ, empate, NOC histórico, Summer, Winter, Youth y 1906.

### Documentación y entrega

- Revisar consistencia ER/CSV/SQL.
- Crear `docs/EXECUTION_ORDER.md`.
- Crear o actualizar `README.md` sin exponer secretos.
- Revisar documentos históricos sin borrar decisiones útiles.
- Crear `.context/CONTEXT_DATA_LIMPIA_INICIO_STORE_PRODUCES.md`.
- Revisar `.gitignore` y evitar secretos, `.env`, `.venv`, caches y temporales.
- Crear `docs/FINAL_DELIVERY_CHECKLIST.md`.
- Crear `docs/Evidence/Evidences_Bloque7.md` con espacios para capturas reales.
- Crear `docs/final/final_validation_report.csv` derivado de consultas reales, sin escribir PASS manualmente.

### Resultado exigido

Reportar validación global, casos especiales, atleta y país usados, consultas funcionales, inconsistencias documentales, README, handoff, `.gitignore`, checklist, archivos y evidencias pendientes. No declarar el proyecto totalmente terminado hasta revisión externa.

---

## P07.1 — Versionamiento de prompts

### Solicitud actual

Crear este archivo en:

```text
OlimpiadasF1/docs/promts/PromtsAnalisisDeDatos.md
```

El archivo debe conservar una versión organizada de los prompts entregados hasta el momento. Esta versión documenta la evolución del alcance desde la lectura inicial del contexto hasta el cierre del Bloque 7, incluyendo correcciones, restricciones, entregables y prohibiciones de avance.

---

## Reglas transversales conservadas

1. Trabajar únicamente en el bloque solicitado.
2. No iniciar el bloque siguiente sin autorización explícita.
3. No inventar datos, correspondencias, fechas, sedes, capturas ni resultados.
4. Mantener `data/raw/` intacto y verificar SHA-256 cuando corresponda.
5. Mantener trazabilidad de decisiones, conflictos, ambiguos, no encontrados y exclusiones.
6. Preferir procesos reproducibles e idempotentes.
7. No ocultar errores con valores fijos, estados PASS manuales o transformaciones silenciosas.
8. No exponer contraseñas ni archivos `.env` en la documentación.
9. No declarar un bloque aprobado hasta la revisión externa solicitada.

## Estado al momento de este versionamiento

- Bloques 1–6: ejecutados técnicamente; sus aprobaciones formales quedan sujetas al registro histórico y revisión externa correspondiente.
- Bloque 7: validación global ejecutada con PASS, documentación creada y pendiente de revisión externa.
- Bloque 8: no iniciado.
- Datos: no modificados durante el cierre del Bloque 7.
