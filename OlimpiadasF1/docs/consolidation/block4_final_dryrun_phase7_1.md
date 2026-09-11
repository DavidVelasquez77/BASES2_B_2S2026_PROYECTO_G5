# Fase 7.1 — Cierre del dry-run del Bloque 4

**Fecha de cierre:** 2026-09-10T16:55:30  
**Estado final:** **READY_TO_APPLY**  
**Aplicación:** ninguna. No se modificaron `data/processed`, `data/raw`, `data/intermediate` ni SQL Server.

## Regresiones reales

- PASS: 12
- NOT_APPLICABLE: 3
- FAIL: 0

Los tres casos `NOT_APPLICABLE` permanecen así y no fueron convertidos en `PASS`: no existe un par completo de eventos procesados con el cual evaluarlos sobre datos reales.

## Regresiones sintéticas

- Negativas sintéticas PASS: 3/3
- Negativas sintéticas FAIL: 0
- Football alias positivo: PASS
- Prueba real `303 ↔ 1902`: PASS (`SAFE_EVENT_ALIAS`)

Las claves se calcularon con la misma función `parse_event()` de Fase 5. Las pruebas sintéticas distinguen distancia/secuencia, `Pursuit` y `adult`/`youth`.

## Messi

Resultado: **PASS**. El preview conserva una identidad canónica `110178`, una participación 2008 Football ARG Gold, evento `303`, posición `1`, medalla `Gold` y nacimiento `1987-06-24`.

## Integridad y preview

- ATLETA: 336419 (preview=336419)
- EVENTO: 3007 (preview=3007)
- PARTICIPACION: 733414 (preview=733414)

- Integridad referencial: **PASS**
- Unicode exacto: **PASS**
- SHA-256 processed: **10/10 MATCH**
- Componentes REVIEW aplicados: 0
- SAME_SOURCE_REVIEW aplicados: 0
- Conflictos de atributo en componentes aprobados: 0

## Causas de deduplicación

- ATHLETE_MERGE: 1349
- EVENT_ALIAS: 27048
- EVENT_ALIAS + ATHLETE_MERGE: 1488
- PREEXISTING_DUPLICATE: 63306

## Archivos

- `final_synthetic_regressions_phase7_1.csv`
- `final_readiness_phase7_1.csv`
- `processed_integrity_phase7_1.csv`
- `block4_final_dryrun_phase7_1.md`

Si el estado es `READY_TO_APPLY`, el proceso se detiene aquí. No se sobrescribe `data/processed`, no se modifica SQL Server y no se inicia ningún bloque posterior.
