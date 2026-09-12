# BEIJING2008_CHN_GOLD_RESIDUAL_AUDIT

Estado: **BEIJING2008_CHN_GOLD_RESIDUAL_RESOLVED**.

Investigación read-only sobre el preview hipotético generado por el dry-run de medallas. No se aplicó ninguna corrección, no se modificó `data/processed` y no se ejecutó SQL de escritura.

## Resultado

El estado previo tenía 89 resultados Gold CHN por la métrica de eventos actuales. Después del dry-run previo quedaron 53 resultados lógicos bajo la clave estricta. La referencia oficial del Comité Olímpico Chino reporta 51 Gold; al unificar únicamente los dos pares de alias de trampolín quedan 51 resultados canónicos.

## Residuales identificados

- `Individual, Men (Olympic)` ↔ `Trampolining Men's Individual`: Lu Chunlong, CHN, Gold; misma edición, disciplina 27 y prueba individual masculina de trampolín.
- `Individual, Women (Olympic)` ↔ `Trampolining Women's Individual`: He Wenna, CHN, Gold; misma edición, disciplina 27 y prueba individual femenina de trampolín.

Ambos son `CONFIRMED_DUPLICATE` por `EVENT_ALIAS`. No son dos resultados olímpicos legítimos, no son cambios históricos de medalla y no son conteo de integrantes de equipo.

## Equipos

El conteo usa una medalla lógica por combinación edición/NOC/medalla/clave semántica. Los integrantes aparecen juntos en `atletas_asociados`; no se cuentan como Gold adicionales. Esto aplica a relevos, equipos, basketball y equipos de gimnasia.

## Controles
- Michael Phelps: 28 frente a 28 — PASS.
- Paavo Nurmi: 12 frente a 12 — PASS.
- Mark Spitz: 11 frente a 11 — PASS.
- Usain Bolt: 8 frente a 8 — PASS.
- USA: 40 → 40 — PASS.
- RUS: 31 → 31 — PASS.
- GBR: 21 → 21 — PASS.
- GER: 21 → 21 — PASS.
- AUS: 14 → 14 — PASS.
- Guatemala: PASS; London 2012 50 km: PASS, conservados por el dry-run anterior.

## Integridad

Processed SHA: MATCH; RAW: 10/10 MATCH; intermediate: 13/13 MATCH; SQL modificado: NO.

Fuentes: [tabla oficial del Comité Olímpico Chino](https://en.olympic.cn/2008/2008-10-25/467661.html), [resumen oficial Beijing 2008](https://en.olympic.cn/games/summer/2008-09-17/466319.html), [IOC Olympic Medal Table Changes](https://library.olympics.com/fiba/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3156828&parentDocumentId=848890&skipCopyright=true&skipWatermark=true).

Esta fase solo deja evidencia para una futura aplicación controlada. No modifica el mapa previo de 1,015 duplicados ni aplica los dos aliases adicionales.
