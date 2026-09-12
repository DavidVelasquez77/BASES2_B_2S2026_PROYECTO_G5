# General Knowledge Query Validation

Fecha de ejecución: 2026-09-12. Estado final: **GENERAL_KNOWLEDGE_QUERY_VALIDATION_PASS**.

Esta fase ejecutó consultas de lectura sobre `OlimpiadasDB` y contrastó los resultados con los CSV vigentes. No se ejecutó DML/DDL y no se modificaron datos.

## Alcance y metodología

- Semilla reproducible para muestras: `20260912`.
- Consultas registradas: 122; obligatorias: 19; fallos críticos: 0.
- Preguntas aleatorias de cultura general: 50; eventos aleatorios: 30.
- Candidatos semánticos de homónimos: 49741; no se fusionó ninguno.
- Podios sospechosos candidatos: 200; se mantienen como revisión, sin eliminar filas.
- La lógica de medallas oficiales agrupa por edición + evento + NOC + medalla para no contar atletas de equipos como resultados oficiales separados.

## Resultados críticos

- Guatemala: consulta de 3 medallistas y 3 filas de medalla; revisar `general_knowledge_query_validation.csv` para el estado real.
- Michael Phelps: desglose esperado 23 Gold / 3 Silver / 2 Bronze; ranking top-20 generado desde SQL.
- Gatlin 100 m masculino Atenas 2004 y casos Messi, Barrondo y London 2012 se consultaron por claves explícitas.
- En London 2012 se exige la presencia del podio vigente y de Sergey Kirdyapkin como DQ; otros DQ históricos de la misma prueba se conservan y se reportan como filas adicionales, no como cambios automáticos.
- La edad mínima Gold se reporta como observación raw; no se eleva a hecho histórico confiable sin una fuente externa específica.

## Integridad y no mutación

- SHA de los 10 CSV procesados antes/después de la auditoría: MATCH.
- Conteos SQL vigentes: ENTIDAD_GEOGRAFICA=282, POBLACION=17024, NOC=236, ATLETA=336418, SEDE=42, EDICION_OLIMPICA=61, DEPORTE=65, DISCIPLINA=117, EVENTO=2986, PARTICIPACION=712658; total de las 10 entidades: 1069889.
- No se ejecutaron resets, carga SQL, matching, deduplicación ni cambios de esquema.

## Fuentes

Las fuentes institucionales utilizadas como referencia están en `query_validation_sources.csv`. Las filas marcadas `NOT_EXTERNALLY_VERIFIED` o `REVIEW` no se presentan como hechos confirmados externamente.
- OSC/IOC results database: https://oscnewsletter.olympics.com/article/56/whats-new-at-the-osc_lang%3Den.html
- IOC Athens 2004 results context: https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true
- IOC London 2012 programme/results context: https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true

## Archivos generados

- `13_general_knowledge_validation.sql` contiene las consultas SELECT/CTE reutilizables.
- `general_knowledge_query_validation.csv`, `query_results.csv`, `query_failures.csv`.
- `medal_rankings_validation.csv`, `country_validation.csv`, `event_winners_validation.csv`, `age_validation.csv`.
- `suspicious_podiums.csv`, `semantic_duplicate_candidates.csv`, `query_validation_sources.csv`.
