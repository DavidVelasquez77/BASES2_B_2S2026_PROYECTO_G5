# Bloque 4 — Fase 3: plan seguro de merges (dry-run)

Esta fase genera únicamente un plan reproducible. No modifica `data/processed`, `data/intermediate`, `data/raw`, SQL Server ni aplica merges.

## Reglas aplicadas

- Los eventos se evalúan como componentes de grafo y solo `SAFE_ALIAS` puede proponer un mapa. Todo conflicto, coexistencia, par ausente o incompatibilidad de dominio deja el componente en revisión.
- Los atletas se reevaluaron usando exclusivamente esos eventos seguros. Se rechaza la aprobación automática ante contradicciones biográficas, ambigüedad, misma fuente o transitividad no demostrada.
- El canónico se elige por completitud biográfica, después por información disponible y finalmente por ID estable; no por mínimo ID como regla primaria.
- Las participaciones solo se agrupan en memoria por atleta/evento canónicos y claves de participación. No se deduplica ningún CSV.

## Métricas reales

- SAFE_EVENT_COMPONENTS: 260
- REVIEW_EVENT_COMPONENTS: 19
- EVENTS_AFFECTED: 653
- ATHLETE_PAIRS_REEVALUATED: 19552
- SAFE_ATHLETE_COMPONENTS: 2245
- REVIEW_ATHLETE_COMPONENTS: 17005
- ATHLETES_IN_SAFE_COMPONENTS: 4490
- SAME_SOURCE_REVIEW: 16797
- ATTRIBUTE_CONFLICT: 229
- PARTICIPATIONS_BEFORE: 826605
- PARTICIPATIONS_SIMULATED_AFTER: 733104
- MERGEABLE_DUPLICATE_EXTRAS: 93501
- CONFLICTING_DUPLICATE_EXTRAS: 140

## Regresión Lionel Messi

id_atleta_origen_a,nombre_a,id_atleta_origen_b,nombre_b,fuentes_atleta_a,fuentes_atleta_b,ids_originales_a,ids_originales_b,contextos_compartidos,biografia_estado,senales_altura_peso,same_source,clasificacion,razon,event_aliases_used,id_atleta_canonico_propuesto
110178,Lionel Messi,167544,Lionel Andrs Messi Cuccittini,fuente1,fuente2,fuente1:111386,fuente2:79053,"[""2008 Summer | ARG | Argentina | 1902 | Gold""]",UNKNOWN/COMPATIBLE,"altura_cm: diferencia=0; señal, no regla de rechazo | peso_kg: diferencia=0; señal, no regla de rechazo",,SAFE_ATHLETE_PAIR,"Contexto compartido, candidato único y sin contradicción biográfica conocida.",SAFE_EVENT_COMPONENT_ONLY,110178

Participación lógica asociada:

grupo_logico,filas,duplicados_mergeables,duplicados_conflictivos,clasificacion,ids_participacion,atletas_originales,eventos_originales,campos_conflictivos,id_atleta_canonico,id_evento_canonico
110178|47|1902|10|Argentina|Gold,2,1,0,MERGEABLE_DUPLICATE_CANDIDATE,240822;464802,110178;167544,1902;303,,110178,1902

## Integridad

CSV procesados antes: 10/10 MATCH. Después: 10/10 MATCH.
Los archivos de salida son planes y reportes diagnósticos; la aprobación y cualquier merge requieren revisión posterior.
