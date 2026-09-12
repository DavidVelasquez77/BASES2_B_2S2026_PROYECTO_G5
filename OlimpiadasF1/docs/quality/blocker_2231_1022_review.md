# BLOCKER RESOLUTION REVIEW — Alias 2231 → 1022

## Resultado

**BLOCKER_2231_1022_RESOLVED**

**Decisión:** `ALIAS_2231_1022_SELECTIVE`  
**Recomendación en esta fase:** `DO_NOT_APPLY`

La decisión resuelve el bloqueo semántico, pero no autoriza todavía la aplicación de ninguna corrección. La regla propuesta es unificar el catálogo de eventos y conservar sin merge automático las participaciones que tengan conflicto de resultado histórico.

## Alcance y protección

La revisión fue de solo lectura. No se modificaron `data/processed/`, `data/semantic_preview/`, SQL Server ni stored procedures. El análisis hipotético de 20 aliases se ejecutó en memoria y no se materializó sobre el preview.

## Identificación de los eventos

| id_evento | nombre | disciplina | deporte | modalidad |
|---:|---|---|---|---|
| 2231 | Athletics Men's 50 kilometres Walk | Athletics | Athletics | Individual, masculino, 50 km |
| 1022 | 50 kilometres Race Walk, Men (Olympic) | Athletics | Athletics | Individual, masculino, 50 km |

Ambos comparten `id_disciplina=10` e `id_deporte=6`. No representan 20 km, una prueba femenina, Youth, Intercalated Games ni una prueba no-medallista diferente. La diferencia es de nomenclatura y de versión histórica del resultado, no de identidad del evento.

## Cobertura y solapamiento

- Ediciones comunes: **19** — 1932 a 2016.
- Solo en 2231: **ninguna**.
- Solo en 1022: **2020**; la fuente 2231 no contiene esa edición.
- Contextos comunes atleta + edición + NOC: **502**.
- Atletas comunes: **332**.
- NOC comunes: **53**.
- Conflictos de NOC: **0**.
- Conflictos de género: **0**.
- Conflictos de edición/temporada: **0**.

El detalle por edición está en `blocker_2231_1022_overlap.csv`.

## Conflictos de resultado

Los **dos conflictos bidireccionales de medalla** que bloquearon el alias son ambos de Londres 2012:

1. **Jared Tallent / AUS:** 2231 registra Silver; 1022 registra Gold y posición 1.
2. **Si Tianfeng / CHN:** 2231 registra Bronze; 1022 registra Silver y posición 2.

También se detectan dos diferencias de estado medalla/NULL que deben conservarse en la auditoría:

- **Robbie Heffernan / IRL:** 2231 lo deja sin medalla, mientras 1022 registra Bronze y posición 3.
- **Sergey Kirdyapkin / RUS:** 2231 registra Gold, mientras 1022 conserva `DQ` y medalla NULL.

Estas cuatro diferencias no son evidencia de dos eventos distintos. Son la coexistencia de dos cortes históricos del mismo resultado: el resultado original de la carrera y el resultado vigente después de la descalificación antidopaje de Kirdyapkin.

## Verificación histórica

La crónica de World Athletics de 2012 describe el resultado original: Kirdyapkin primero, Tallent segundo, Si tercero y Heffernan cuarto. La página de resultados vigente de World Athletics muestra la reasignación: Tallent primero, Si segundo, Heffernan tercero y Kirdyapkin `DQ`. El Australian Olympic Committee documenta la entrega posterior del oro olímpico a Tallent.

Referencias:

- [World Athletics — resultados vigentes de London 2012, 50 km Race Walk](https://worldathletics.org/competitions/olympic-games/the-xxx-olympic-games-6999193/results/men/50-kilometres-race-walk/final/result)
- [World Athletics — crónica original del evento](https://worldathletics.org/news/report/london-2012-event-report-mens-50km-race-w)
- [Australian Olympic Committee — entrega del oro a Jared Tallent](https://www.olympics.com.au/news/golden-smile-as-tallent-finally-receives-olympic-gold/)

Resultado histórico vigente usado para la evaluación:

| atleta | posición vigente | medalla vigente |
|---|---:|---|
| Jared Tallent | 1 | Gold |
| Si Tianfeng | 2 | Silver |
| Robbie Heffernan | 3 | Bronze |
| Sergey Kirdyapkin | DQ | NULL |

El detalle de las cuatro diferencias, con posición, edad, equipo, estado e IDs de participación, está en `blocker_2231_1022_conflicts.csv`.

## Consistencia de posición e información

- Coincidencias exactas de posición entre los contextos comunes: **132/502**.
- Pares complementarios posición/edad: **370**. La fuente 1022 aporta la posición y la fuente 2231 aporta principalmente edad, por lo que la diferencia no se interpreta como otro evento.
- En los dos conflictos bidireccionales, la posición de 1022 respalda la medalla vigente: posición 1 → Gold y posición 2 → Silver.
- No se sobrescribe ninguna fila en esta revisión.

## Equivalencia global

- Coincidencia exacta de medalla/status: **498/502 = 99.20%**.
- Si se separan las dos diferencias medalla/NULL propias de la reasignación histórica, quedan **2 conflictos bidireccionales** de medalla.
- Compatibilidad semántica de evento: **100%**; ambos nombres corresponden a Athletics, 50 km, masculino, individual.

## Evaluación de alternativas

### Opción A — Alias completo

No se aprueba. Un merge automático convertiría dos versiones históricas de medallas en una sola fila sin registrar procedencia ni el cambio de estado de Kirdyapkin.

### Opción B — Alias de evento con merge selectivo

**Seleccionada.** El catálogo puede usar el evento canónico 1022, pero las participaciones que tengan diferencia de medalla o estado deben conservarse como conflicto de fuente y no fusionarse automáticamente. Las filas sin conflicto pueden fusionarse cuando la clave lógica y los campos complementarios sean compatibles.

### Opción C — No alias

No es necesaria para resolver la semántica: mantener ambos eventos en el catálogo representaría como distintos dos nombres del mismo evento. Puede usarse solo como fallback si el Bloque 4 no puede soportar una trazabilidad de participación selectiva.

## Preview hipotético sin el alias 2231 → 1022

Recalculado en memoria, excluyendo exclusivamente ese alias y manteniendo los otros 20:

| entidad | preview actual con 21 aliases | hipotético con 20 aliases |
|---|---:|---:|
| ATLETA | 336418 | 336418 |
| EVENTO | 2986 | 2987 |
| PARTICIPACION | 713682 | 714181 |

Las regresiones permanecen PASS: Guatemala 1/1/1, Barrondo Silver 2012 en 20 km, Phelps 23/3/2, Chad le Clos Summer 1/3/0 con Youth separado, Andrianov 7/5/3, Messi una participación Gold en 2008 y Justin Gatlin Gold en 100 m 2004.

## Integridad

- `data/processed` SHA-256: **10/10 MATCH**.
- `data/semantic_preview` modificado en esta fase: **NO**.
- SQL Server modificado: **NO**.
- Stored procedures modificados: **NO**.

## Cierre

El bloqueo se resuelve como `ALIAS_2231_1022_SELECTIVE`. No se debe aplicar todavía: la siguiente fase, si se autoriza, debe implementar la trazabilidad de los cuatro casos de resultado histórico y comprobar los conteos antes de promover el cambio.
