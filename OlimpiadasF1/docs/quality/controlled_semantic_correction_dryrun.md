# Corrección semántica controlada — DRY-RUN

Estado: **CONTROLLED_FIX_READY**

Esta fase solo construyó `data/semantic_preview/`. No se modificaron `data/processed`, SQL Server ni stored procedures.

## Reglas aplicadas

- Sexo: `M/F` a `Male/Female` en el preview; valores originales permanecen en processed.
- `nombre_completo`: reemplazo de U+2022 por espacio y colapso de espacios; filas afectadas: 145252; colisiones generadas: 3.
- No se aplicaron los 21,501 candidatos de atleta ni los 112,492 candidatos de participación globales.
- Se aplicó únicamente el merge completo explícito `147606 -> 121191`.
- `192591` no se fusionó: su participación `2020/CAN/Men's 10m Platform` queda `REVIEW`.
- Se aplicaron 21 aliases de evento `FINAL_SAFE_ALIAS`.
- Fusiones seguras de participación: 19708 grupos / 19732 filas retiradas, todas en el mapa de trazabilidad.

## Regresiones

- Barrondo: PASS; una plata lógica 2012, 20 km, GUA.
- Guatemala: PASS; tres medallistas lógicos.
- Phelps: PASS; Gold 23, Silver 3, Bronze 2, total 28.
- Phelps participaciones lógicas: PASS; esperado 30.
- Chad le Clos: PASS; Gold 1, Silver 3, Bronze 0 en Summer no Youth.
- Nikolay Andrianov: PASS; Gold 7, Silver 5, Bronze 3.
- Messi: PASS.
- 100 m Athletics 2004 Gold: PASS.
- Edad de oro: 23 conflictos individuales, todos clasificados `CONFLICT_REVIEW` y sin cambios.

## Conteos del preview

- ATLETA: 336419 -> 336418 (merge completo explícito 147606->121191)
- EVENTO: 3007 -> 2986 (aliases FINAL_SAFE_ALIAS materializados)
- PARTICIPACION: 733414 -> 713682 (aliases/reasignaciones y fusiones trazables)

## Integridad

- SHA de processed: 10/10 MATCH.
- SQL Server modificado: **NO**.
- Stored procedures modificados: **NO**.

## Archivos

- `data/semantic_preview/atleta.csv`
- `data/semantic_preview/evento.csv`
- `data/semantic_preview/participacion.csv`
- `docs/quality/controlled_athlete_map.csv`
- `docs/quality/controlled_event_map.csv`
- `docs/quality/controlled_participation_map.csv`
- `docs/quality/barrondo_resolution.csv`
- `docs/quality/phelps_resolution.csv`
- `docs/quality/gold_age_conflicts_review.csv`
- `docs/quality/acceptance_queries_controlled_preview.csv`
- `docs/quality/semantic_preview_counts.csv`
- `docs/quality/controlled_processed_integrity.csv`

Recomendación: **APPLY**. El estado `CONTROLLED_FIX_READY` solo se declara si todas las regresiones críticas pasan y no existe ningún merge de revisión aplicado.
