# Auditoría integral final de calidad semántica

Fecha: 2026-09-12.

## Estado

SEMANTIC_AUDIT_COMPLETE

Fase exclusivamente diagnóstica. No se modificaron data/raw, data/intermediate, data/processed, SQL Server, scripts productivos ni stored procedures. No se ejecutaron DML, resets, cargas ni rebuilds.

## Integridad
- SHA-256 de data/processed: 10/10 MATCH.
- Filas actuales en los diez CSV: 1,090,667.
- Se utilizó una base SQLite temporal, eliminada al terminar.

## Comprobación de solo lectura en SQL Server
- `olympics.ATLETA`: 336,419 filas; `olympics.EVENTO`: 3,007; `olympics.PARTICIPACION`: 733,414.
- Sexo observado: `F=55,279`, `Female=39,175`, `M=135,640`, `Male=106,325`.
- `nombre_completo` con U+2022: 145,252 filas, coincidente con el CSV.
- Guatemala (`GUA`) con medalla: 5 filas, coincidente con el CSV.
- Michael Phelps canónico (`id_atleta=93113`): 56 filas con medalla (`Gold=46`, `Silver=6`, `Bronze=4`). La consulta amplia por apellido devuelve 65 porque incluye otros atletas llamados Phelps; por eso la auditoría usa el ID canónico.
- Las consultas ejecutadas fueron exclusivamente `SELECT`; no se modificó SQL Server.

## Resultados
- Sexo M/F normalizable: 190,919 filas.
- U+2022 en nombre_completo: 145,252 filas.
- Atletas: SAFE_MERGE 0, REVIEW 21501, CONFLICT 28536.
- Eventos: SAFE_ALIAS 5, REVIEW_ALIAS 1326, CONFLICT_ALIAS 4; los cruces masculino/femenino se clasifican como conflicto.
- Participaciones: EXACT_DUPLICATE 0 grupos; COMPLEMENTARY_DUPLICATE 112492 grupos candidatos (incluye 21825 con medalla y 90667 sin medalla), exceso candidato 155652; CONFLICTING_DUPLICATE 3108 grupos.

## Barrondo
IDs 121191, 147606, 192591. Participaciones observadas: 9. Detalle: 121191|2012 Summer|GUA|20 kilometres Race Walk, Men (Olympic)|medalla=Silver|pos=2|edad= || 121191|2012 Summer|GUA|50 kilometres Race Walk, Men (Olympic)|medalla=|pos=|edad= || 121191|2016 Summer|GUA|20 kilometres Race Walk, Men (Olympic)|medalla=|pos=50|edad= || 121191|2020 Summer|GUA|50 kilometres Race Walk, Men (Olympic)|medalla=|pos=|edad= || 147606|2012 Summer|GUA|Athletics Men's 20 kilometres Walk|medalla=Silver|pos=|edad=21 || 147606|2012 Summer|GUA|Athletics Men's 50 kilometres Walk|medalla=|pos=|edad=21 || 147606|2016 Summer|GUA|Athletics Men's 20 kilometres Walk|medalla=|pos=|edad=25 || 192591|2012 Summer|GUA|Athletics Men's 20 kilometres Walk|medalla=Silver|pos=|edad= || 192591|2020 Summer|CAN|Men's 10m Platform|medalla=|pos=|edad=. No se aplicó merge.

## Phelps
Crudo: Gold 46, Silver 6, Bronze 4, Total 56. Estimación pos/edad: Gold 23, Silver 3, Bronze 2, Total 28. No se modificó la tabla.

## Guatemala
Filas medallistas actuales asociadas a GUA: 5. El detalle está en guatemala_medal_audit.csv.

## Decisión

REVIEW_REQUIRED / DO_NOT_APPLY

No se recomienda modificar la base en esta fase. Sexo y nombres pueden resolverse en vista/salida conservando valores originales. Eventos y atletas requieren una corrección controlada de matching/consolidación. El estimador del SP no es una corrección persistente. Los candidatos de participación son una señal de revisión, no una orden de deduplicación.

## Archivos

Se generaron todos los reportes solicitados en docs/quality/.

## Siguiente paso

Revisar SAFE_MERGE y SAFE_ALIAS con evidencia de fuentes antes de aplicar cualquier cambio.
