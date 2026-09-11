# Bloque 4 — fase 2 de reducción de riesgo

Esta fase reclasifica candidatos usando historial completo de participaciones, atributos biográficos, unicidad nominal/contextual y coexistencia de aliases de eventos. No aplica merges y no sobrescribe `data/processed/`.

- Hashes `data/processed/*.csv`: **10/10 MATCH**.
- Candidatos totales: **77391**.
- EXACT_DUPLICATE_IDENTITY: **17253**.
- STRONG_ALIAS: **2299**.
- REVIEW: **57675**.
- CONFLICT: **164**.
- Pares seguros propuestos: **19552**; atletas únicos afectados: **38501**.
- SAFE_ALIAS: **454**.
- REVIEW_ALIAS: **23**.
- CONFLICT_ALIAS: **451**.

## Regresión Messi

El par Lionel Messi / Lionel Andrs Messi Cuccittini queda clasificado como:

**STRONG_ALIAS**

La decisión deriva de la relación de tokens, edición 2008 Summer, NOC ARG, equipo Argentina, alias de evento compatible, Gold, fecha compatible (presente en una fuente y ausente en la otra) y unicidad del candidato. No existe una regla especial por nombre.

## Defecto detectado en `event_signature()`

La firma basada en `set(tokens)` elimina multiplicidad. Por ejemplo, `Football, Men (Olympic)` y `Football Men's Football` terminan con la misma firma aunque el segundo repite `Football`. La fase 2 marca estos casos como `REVIEW_ALIAS` salvo que el token adicional sea el nombre del deporte y no exista coexistencia en una misma fuente/edición. Los aliases no se aplican todavía.

## Falsos positivos de la primera regla

La primera regla sobrevaloraba nombres idénticos o contenidos con una sola coincidencia contextual. En la muestra refinada aparecen homónimos como `Francesco Messina`, `Jean Borotra`, `Patrick Chila` y pares con el mismo nombre pero ediciones/equipos distintos. Se clasifican como `REVIEW` cuando la unicidad no queda demostrada y como `CONFLICT` cuando existe contradicción biográfica fuerte.

## Muestreo reproducible

Se generó `athlete_duplicate_samples_phase2.csv` con semilla 42: hasta 30 casos por clasificación y los 30 STRONG_ALIAS con menor confianza.

## Estado

La fase diagnóstica terminó correctamente. No se regeneró `data/processed/`, no se modificó SQL, no se ejecutaron merges y el Bloque 4 no se declara corregido.
