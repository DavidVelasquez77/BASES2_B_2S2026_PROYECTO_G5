# FINAL PRE-APPLY REVIEW — Corrección semántica controlada

Resultado: **PRE_APPLY_REVIEW_REQUIRED**

Revisión independiente de `data/processed`, `data/semantic_preview`, mapas y reportes. No se modificaron archivos de datos, preview, SQL Server ni stored procedures.

## Aliases

- `VERIFIED_SAFE_ALIAS`: **20/21**.
- `REVIEW_ALIAS`: **1**; rechazados: **0**.
- Se comprobaron género, distancia, modalidad, categoría, temporada/edición, medallas, posiciones, atletas y NOC.

## Aceptación

- Guatemala: **PASS** — Gold 1, Silver 1, Bronze 1.
- Barrondo: **PASS** — 2012 Summer, GUA, evento 1021, posición 2; edad preservada.
- `147606`: único atleta eliminado; trazado a `121191`.
- `192591/CAN/2020/Men's 10m Platform`: queda separado.
- Phelps: **PASS** — 23/3/2, 30 participaciones.
- Chad le Clos: **PASS** — Summer Youth separado.
- Nikolay Andrianov: **PASS** — 7/5/3.
- Messi: **PASS**.
- 100 m 2004: **PASS** — Justin Gatlin / USA / Gold.

## Participaciones eliminadas

- Fusionadas: **19732**.
- Muestra reproducible: **105** filas distribuida entre 21 aliases.
- Destinos existentes: **PASS**.
- Eliminadas sin mapa: **PASS**.
- Nuevas sin origen: **PASS**.
- Pérdidas en campos útiles de todas las filas fusionadas: **0**.

## Colisiones de nombres

No se fusionaron identidades por estas colisiones:
- `Mohamed El-Sayed Hafez`: variantes=["Mohamed El-Sayed•Hafez", "Mohamed•El-Sayed Hafez"]; ids=105308,55136
- `Rashid Salih Hamad Al-Athba`: variantes=["Rashid Salih Hamad•Al-Athba", "Rashid Salih•Hamad Al-Athba"]; ids=103803,115969
- `Win Maung`: variantes=["Win Maung", "Win•Maung"]; ids=26435,4654,55982

## Edad y rankings

Edad mínima confiable: **13**. Los **23** conflictos edad/DOB siguen como `CONFLICT_REVIEW`.

Los TOP 20 globales y TOP 10 por Swimming, Athletics y Gymnastics están en `pre_apply_acceptance_results.csv`. Se marcaron `REVIEW` para evitar aprobación automática y se revisaron Phelps, Andrianov y conteos anómalos.

## Conteos e integridad

- ATLETA: `336419 -> 336418`.
- EVENTO: `3007 -> 2986`.
- PARTICIPACION: `733414 -> 713682`.
- FK huérfanas: **0**.
- IDs eliminados: **147606**.
- SHA processed: **10/10 MATCH**.
- SQL Server modificado: **NO**.
- Stored procedures modificados: **NO**.
- Preview modificado durante esta revisión: **NO**.

No se aplica todavía; la promoción requiere una fase posterior controlada.


## Hallazgo bloqueante

El alias `2231 -> 1022` (50 km marcha) conserva dos conflictos de medalla para el mismo atleta, edición y NOC. Se mantiene como `REVIEW_ALIAS`; no puede promoverse en esta fase.

Recomendación: **DO_NOT_APPLY** hasta resolver el alias `2231 -> 1022`.

