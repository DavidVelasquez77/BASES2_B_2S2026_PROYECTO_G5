# FINAL_EXTERNAL_LIVE_QUERY_AUDIT

Estado final: **FINAL_EXTERNAL_LIVE_QUERY_AUDIT_REVIEW_REQUIRED**.

La auditoría ejecutó consultas SELECT/CTE contra `OlimpiadasDB`, contrastó casos prioritarios con fuentes IOC/Olympics y no modificó datos, esquema, índices, procedimientos ni CSV.

## Resultado ejecutivo

- Candidatos de podio revisados: 200; casos clasificados como VALID_TEAM_EVENT=23, VALID_TIE=0, VALID_MULTIPLE_BRONZE=142, VALID_REALLOCATION=0, REVIEW=35.
- Duplicados semánticos con medalla: 27308 pares; candidatos CRITICAL por resultado lógico compartido: 7.
- Consultas externas en vivo: 42; PASS=21, REVIEW=21, FAIL=0, NOT_VERIFIABLE=0.
- Fallos de ranking/famosos confirmados contra referencia: 0.

## Rankings SQL actuales

- Mayor total en SQL: Michael Phelps (28 filas de medalla; no se presenta como récord oficial cuando existen duplicados semánticos).
- Mayor Gold en SQL: Michael Phelps (23).
- Mayor Silver en SQL: Shirley Babashoff (12).
- Mayor Bronze en SQL: Franziska van Almsick (12).
- Los rankings por deporte se obtuvieron mediante las FK/eventos del modelo, no por inferencia textual.

## Hallazgos externos críticos

- Phelps coincide: 23 Gold, 3 Silver, 2 Bronze, total 28.
- Larisa Latynina y Marit Bjørgen coinciden con referencias específicas; Nikolay Andrianov coincide numéricamente, pero permanece REVIEW porque la URL disponible no es una ficha de resultados específica.
- Paavo Nurmi, Mark Spitz y Usain Bolt presentan discrepancias confirmadas; Carl Lewis y Simone Biles requieren una fuente específica adicional antes de elevar la diferencia a FAIL. Ninguno se corrigió.
- La consulta de atleta más joven devuelve una edad raw de 13 años; el IOC mantiene una distinción histórica separada para el coxswain infantil de 1900, por lo que el trusted result queda REVIEW.
- Podios confirmados como incorrectos: 0 en esta fase; las 200 filas siguen siendo candidatos. Ninguna se marcó PASS solo por consistencia interna.
- Duplicados de medalla críticos detectados por clave semántica: 7; incluyen repeticiones de una misma prueba con nomenclaturas de fuentes distintas.

## Integridad

- Conteos SQL: ENTIDAD_GEOGRAFICA=282, POBLACION=17024, NOC=236, ATLETA=336418, SEDE=42, EDICION_OLIMPICA=61, DEPORTE=65, DISCIPLINA=117, EVENTO=2986, PARTICIPACION=712658; total=1069889.
- SHA processed antes/después: MATCH.
- RAW: 10/10 MATCH; intermediate: 13/13 MATCH.
- SQL y stored procedures: no modificados por esta fase; la única modificación de tooling fue corregir el exit code de `18_general_knowledge_query_validation.py`.

## Recomendación

**REVIEW_RESULTS**. No se deben corregir datos ni hacer merges dentro de esta auditoría. Antes de declarar la capa de consultas históricas lista para defensa, revisar la deduplicación semántica con medallas y resolver las discrepancias externas de los rankings históricos.

Fuentes exactas: `final_live_query_sources.csv`. Casos externos por pregunta: `live_external_query_checks.csv`.
