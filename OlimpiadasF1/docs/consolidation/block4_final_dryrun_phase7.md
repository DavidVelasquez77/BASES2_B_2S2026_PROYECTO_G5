# Fase 7 final del Bloque 4 — dry-run integral

**Fecha de ejecución:** 2026-09-10T16:38:56  
**Estado del dry-run:** **NOT_READY_TO_APPLY**  
**Aplicación real:** no realizada. `data/processed` y SQL Server no fueron modificados.

## Alcance

Se simularon en memoria los alias únicamente de los 99 componentes `SAFE_EVENT_COMPONENT`, los merges de atletas clasificados como `FINAL_SAFE_ATHLETE_COMPONENT`, el enriquecimiento conservador y la deduplicación exacta/complementaria de participaciones. Los componentes en revisión o conflicto no se aplicaron.

## Resultado

- Componentes de eventos seguros: 99; IDs miembros en componentes seguros: 198; IDs no canónicos remapeados: 99.
- Componentes finales de atletas seguros: 2353; atletas remapeados: 2353.
- Atletas: 338772 → 336419.
- Participaciones: 826605 → 733414; eliminadas por deduplicación segura: 93191.
- Unicode exacto `ATLETA.nombre`: 26261 filas comparadas; diferencias: 0; estado: PASS.
- Integridad SHA-256 de processed: 10/10 MATCH.
- Integridad referencial del preview atleta/evento/participación: PASS.

## Causas de filas eliminadas

             causa_primaria  filas_eliminadas
              ATHLETE_MERGE              1349
                EVENT_ALIAS             27048
EVENT_ALIAS + ATHLETE_MERGE              1488
      PREEXISTING_DUPLICATE             63306

## Messi

La prueba por IDs 110178 y 167544 exige una sola identidad canónica 110178, nacimiento 1987-06-24, evento 303, posición 1 y medalla Gold; resultado: **PASS**.

## Bloqueadores

regresiones negativas

## Archivos

Los resultados completos se encuentran en los CSV de Fase 7 y en `data/preview_phase7/`. Este preview no sustituye `data/processed` y no autoriza aplicar cambios.
