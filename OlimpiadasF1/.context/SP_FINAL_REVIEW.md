# Revisión final de Stored Procedures

> **Propósito de este documento:** este archivo NO contiene cambios aplicados a los Stored Procedures. Su función es servir únicamente como guía de revisión y recomendaciones para los integrantes encargados de implementar los SP. Toda recomendación debe validarse antes de modificar el contrato de salida o la semántica de los procedimientos.

## Estado actual

Esta revisión es estática y documental. No se ejecutaron `CREATE OR ALTER`, no se recargó la base, no se modificaron CSV y no se modificó ningún Stored Procedure.

La revisión se realizó sobre:

- `sp_historial_atleta.sql`;
- `scripts/sql/14_sp_consultar_pais.sql`.

El estado físico vigente de la base es:

| Entidad | Filas |
|---|---:|
| ENTIDAD_GEOGRAFICA | 282 |
| POBLACION | 17,024 |
| NOC | 236 |
| ATLETA | 336,418 |
| SEDE | 42 |
| EDICION_OLIMPICA | 61 |
| DEPORTE | 65 |
| DISCIPLINA | 117 |
| EVENTO | 2,986 |
| PARTICIPACION | 712,658 |
| **Total** | **1,069,889** |

Validaciones de integridad vigentes:

- `10_final_validation.sql`: 26/26 PASS;
- `11_special_cases_validation.sql`: 8/8 PASS;
- PK duplicadas: 0;
- FK huérfanas: 0;
- DQ con medalla: 0;
- podios incorrectos confirmados: 0.

Los conteos de medallas de atletas se deben interpretar con cuidado cuando la búsqueda por nombre devuelve más de un `id_atleta`. La consulta por identidad seleccionada debe utilizar `@id_atleta` o una búsqueda que no resulte ambigua.

## Hallazgos críticos

| Prioridad | SP | Hallazgo | Acción recomendada |
|---|---|---|---|
| CRITICAL | `sp_historial_atleta` | Mantiene `#grupos`, `#est`, `estimado` y conteos paralelos para compensar duplicaciones antiguas | Retirar la heurística; usar `PARTICIPACION` como fuente canónica y confirmar el tratamiento de columnas estimadas |
| HIGH | `sp_consultar_pais` | El medallero oficial usa `DISTINCT(id_edicion,id_evento,medalla)` sin `id_noc` | Incluir `id_noc` en la clave lógica del medallero |
| HIGH | Ambos | No hay validación completa del dominio de `@temporada` | Rechazar valores fuera de `Summer`, `Winter`, `Summer Youth`, `Winter Youth`, `Intercalated Games` |
| CONTRACT DECISION | `sp_consultar_pais` | `TOP 1` resuelve silenciosamente coincidencias parciales | Elegir entre devolver coincidencias, rechazar ambigüedad o mantener `TOP 1` documentado |
| HIGH | `sp_consultar_pais` | `@top_participaciones` no valida `NULL`, valores negativos ni límites excesivos | Normalizar `NULL`/`<=0` a 50 y establecer un máximo de 500 o 1,000 |
| MEDIUM | `sp_historial_atleta` | Los filtros `@deporte` y `@pais` no escapan todos los comodines | Aplicar una estrategia equivalente a la búsqueda del nombre del atleta |
| MEDIUM | `sp_consultar_pais` | Las búsquedas de país no fuerzan explícitamente una collation sin acentos | Aplicar `Latin1_General_CI_AI` cuando corresponda |
| CONTRACT DECISION | `sp_consultar_pais` | El detalle no devuelve explícitamente `codigo_noc` ni `nombre_noc` | Confirmar compatibilidad antes de agregar columnas al result set |
| LOW | Ambos | Comentarios y documentación todavía describen deduplicaciones históricas como si fueran lógica vigente | Actualizar comentarios y documentación sin cambiar el dato |
| KEEP | `sp_historial_atleta` | Control de ambigüedad mediante `@max_atletas`, `@coincidencia_exacta` y `@id_atleta` | Conservar, con validaciones adicionales |
| KEEP | Ambos | Las relaciones se resuelven mediante las FK del modelo | Mantener joins explícitos y no introducir tablas auxiliares de medallas |
| DESIGN DECISION | `sp_consultar_pais` | Una entidad geográfica puede tener varios NOC históricos | Definir si la consulta es por entidad consolidada o por NOC histórico específico |

## Clasificación de cambios recomendados

### SAFE CHANGE

Cambios que, en principio, no cambian el significado funcional esperado del SP:

- retirar lógica heurística antigua de deduplicación si ya no es necesaria;
- validar el dominio de `@temporada`;
- validar `NULL`, `<=0` y el límite máximo de `@top_participaciones`;
- escapar `%`, `_` y `[` en búsquedas `LIKE`;
- aplicar collation para búsquedas sin sensibilidad a acentos cuando corresponda;
- actualizar comentarios y documentación obsoleta;
- agregar `ORDER BY` determinístico;
- mejorar mensajes de error y validación.

### CONTRACT DECISION

Cambios que requieren acuerdo entre los integrantes porque pueden afectar consumidores existentes:

- eliminar columnas `*_estimado`;
- cambiar el número u orden de result sets;
- agregar columnas nuevas a result sets existentes;
- cambiar nombres de columnas;
- cambiar la estructura de respuesta;
- cambiar la resolución de país/NOC;
- separar `GER`/`FRG`/`GDR` o `RUS`/`URS`/`EUN`;
- cambiar el comportamiento de búsquedas parciales;
- cambiar la selección cuando existen múltiples coincidencias.

**No implementar un `CONTRACT DECISION` sin acordar primero el contrato de salida.**

## `sp_historial_atleta`

### Búsqueda y control de ambigüedad

La lógica actual es adecuada en principio:

- acepta búsqueda parcial o exacta;
- permite seleccionar directamente `@id_atleta`;
- distingue ausencia de coincidencias, ausencia de resultados y búsqueda ambigua;
- limita el número de candidatos con `@max_atletas`.

Debe conservarse porque la existencia de homónimos sigue siendo válida aunque las participaciones confirmadas ya hayan sido consolidadas.

Se recomienda complementar esta lógica con:

- un límite superior para `@max_atletas`;
- validación de `@temporada`;
- escape de comodines en `@deporte`, `@pais` y, si aplica, otros filtros parciales;
- orden determinístico de candidatos incluyendo `id_atleta`.

### Filtro de país

El filtro `@pais` se resuelve mediante:

- `NOC.codigo_noc`;
- `NOC.nombre_noc`;
- `ENTIDAD_GEOGRAFICA.nombre`.

Esta decisión debe conservarse. `PARTICIPACION.id_pais_nacionalidad` es nullable y no debe ser la única fuente para resolver el país representado. El procedimiento correctamente utiliza el NOC de la participación y la entidad asociada.

### Lógica obsoleta de estimación

El procedimiento todavía construye:

- `#grupos`;
- `#est`;
- `participaciones_estimado`;
- `total_medallas_estimado`;
- `oro_estimado`;
- `plata_estimado`;
- `bronce_estimado`;
- `total_estimado`;
- `diagnostico de duplicidad`.

La lógica agrupa por:

```text
id_atleta + anio + id_disciplina + medalla
```

y decide si una fila con posición y otra con edad representan una sola participación. Esto es riesgoso porque no utiliza toda la identidad del hecho, por ejemplo:

- `id_edicion`;
- `id_evento`;
- `id_noc`;
- estado del resultado;
- resultado original.

Dos eventos distintos de la misma disciplina y año podrían quedar artificialmente agrupados. La consulta tampoco debería reconstruir la deduplicación ETL con heurísticas de posición/edad.

Con el estado vigente, `PARTICIPACION` contiene 712,658 filas finales y es la fuente canónica para las métricas de consulta. Por tanto, la recomendación es retirar la heurística de estimación del SP. Si el contrato permite cambiar la salida, pueden retirarse las columnas `*_estimado`; si existen consumidores que requieren compatibilidad temporal, deben conservarse únicamente como columnas `DEPRECATED`, con el mismo valor canónico y una nota explícita. Por ejemplo:

```text
participaciones = 30
participaciones_estimado = 30  -- DEPRECATED; compatibilidad temporal
```

El valor estimado no debe volver a calcularse con agrupaciones heurísticas.

> **Advertencia de alcance:** la deduplicación semántica ya fue realizada durante ETL y consolidación. Los Stored Procedures no deben volver a deduplicar, agrupar heurísticamente, comparar edad o posición para inferir duplicados, eliminar participaciones ni corregir rankings. Su función es consultar el modelo final.

### Recomendación para la ficha del atleta

El tratamiento de las columnas históricas estimadas depende del contrato:

```text
participaciones_estimado
total_medallas_estimado
```

- Si se aprueba un cambio de contrato, eliminarlas de la salida.
- Si se requiere compatibilidad, conservarlas temporalmente como `DEPRECATED` y hacer que reflejen exactamente las métricas canónicas, sin recalcularlas con heurísticas.

En ambos casos, la ficha debe presentar como métricas oficiales:

```text
participaciones
total_medallas
ediciones
deportes
```

También pueden conservarse `primer_ano` y `ultimo_ano` si forman parte del contrato de salida.

### Recomendación para el medallero

El segundo result set debe calcular directamente las métricas de la participación seleccionada:

```sql
SUM(CASE WHEN medalla = N'Gold' THEN 1 ELSE 0 END)
SUM(CASE WHEN medalla = N'Silver' THEN 1 ELSE 0 END)
SUM(CASE WHEN medalla = N'Bronze' THEN 1 ELSE 0 END)
COUNT(CASE WHEN medalla IS NOT NULL THEN 1 END)
```

Para Michael Phelps, utilizando el `id_atleta` canónico, el resultado esperado es:

```text
Gold   = 23
Silver = 3
Bronze = 2
Total  = 28
```

El SP no debe presentar simultáneamente conteos crudos y estimados como si ambos fueran resultados oficiales.

### Detalle de participaciones

El tercer result set contiene los atributos requeridos:

- año;
- temporada;
- sede;
- deporte;
- disciplina;
- evento;
- código y nombre NOC;
- país representado;
- equipo;
- edad;
- posición;
- empate;
- estado del resultado;
- medalla.

Debe mantenerse como detalle fiel de `PARTICIPACION`. No debe aplicar heurísticas, agrupar filas ni eliminar duplicados durante la consulta.

### Comentarios obsoletos

Deben actualizarse comentarios como:

- “la misma participación quedó registrada dos veces”;
- “la base trae la misma participación bajo dos nomenclaturas de evento”;
- “conteo estimado”;
- “duplicado detectado y descontado”.

Pueden conservarse como contexto histórico en documentación, pero no deben describir el comportamiento vigente del procedimiento.

## `sp_consultar_pais`

### Resolución de país y NOC

La prioridad actual es:

1. código NOC;
2. código ISO de `ENTIDAD_GEOGRAFICA`;
3. nombre exacto de entidad;
4. coincidencia parcial en entidad o nombre NOC.

La estrategia es útil, pero el uso de `TOP 1` en la coincidencia parcial puede ocultar ambigüedades. Se recomienda:

- devolver una lista de coincidencias cuando existan varias entidades;
- o rechazar la búsqueda parcial ambigua;
- o conservar `TOP 1` únicamente después de un orden de prioridad documentado y estable.

La resolución de códigos históricos como `GER`/`FRG`/`GDR` o `RUS`/`URS`/`EUN` es una **DESIGN DECISION** y no debe automatizarse en esta revisión. Existen dos interpretaciones válidas que deben ser aprobadas explícitamente:

- **A. Entidad geográfica consolidada:** agrupar NOC históricos con el mismo `id_entidad` para responder por el país/geografía actual.
- **B. NOC histórico específico:** mantener separadas las representaciones `GER`, `FRG`, `GDR`, `RUS`, `URS` y `EUN`.

No se debe escoger A o B por defecto ni fusionar ambos significados silenciosamente.

### Medallero oficial del país

El procedimiento actualmente utiliza:

```sql
SELECT DISTINCT p.id_edicion, p.id_evento, p.medalla
```

Agregar `p.id_noc` es conceptualmente correcto para la definición del medallero oficial, pero debe validarse con los casos de control antes de modificar el SP. No se debe afirmar que esta columna, por sí sola, corrige todos los resultados.

La clave propuesta es:

```sql
SELECT DISTINCT
    p.id_edicion,
    p.id_evento,
    p.id_noc,
    p.medalla
```

La razón es que la unidad oficial debe ser:

```text
edición + evento + NOC + medalla
```

Esto evita contar atletas individuales como medallas adicionales en deportes de equipo y evita colapsar silenciosamente representaciones NOC distintas dentro de una misma entidad histórica.

La salida debe mantener separadas estas métricas:

| Métrica | Definición |
|---|---|
| Medallas oficiales del país | Resultados distintos por edición, evento, NOC y medalla |
| Preseas entregadas a atletas | Filas físicas de `PARTICIPACION` con medalla no nula |

Por ejemplo, un equipo de fútbol puede producir una medalla oficial Gold para el NOC y múltiples filas Gold para los atletas que recibieron la presea.

### Casos de control

La siguiente batería debe verificarse después de aplicar cambios:

```text
GUA                         = Gold 1, Silver 1, Bronze 1, Total 3
CHN + 2008                  = 51 Gold lógicos
ARG + 2008 + Football       = Gold
USA + 2012 + Basketball     = Gold
```

El caso Beijing debe definirse con la métrica lógica documentada. Los aliases físicos de `EVENTO` pueden permanecer como histórico; las participaciones confirmadas redundantes ya fueron consolidadas.

### Detalle de participaciones

El cuarto result set devuelve año, temporada, sede, deporte, disciplina, evento, atleta, equipo, posición, medalla y estado. Agregar explícitamente:

```text
codigo_noc
nombre_noc
pais_representado
```

es una **CONTRACT DECISION**, porque puede romper consumidores que dependan del número, orden o nombres actuales de las columnas. Debe confirmarse la compatibilidad antes de incorporar esos campos.

El filtro `@top_participaciones` debe normalizarse antes del `TOP`:

```text
NULL o <= 0 -> 50
máximo recomendado -> 500 o 1,000
```

No debe aceptar un valor arbitrariamente grande que genere una respuesta difícil de controlar.

## Cambios recomendados

### Prioridad CRITICAL

1. Retirar la deduplicación heurística de `sp_historial_atleta`.
2. Retirar `#grupos` y `#est`; retirar las columnas estimadas solo si el contrato lo permite, o marcarlas `DEPRECATED` con valores canónicos.
3. Hacer que el medallero del atleta consulte directamente las filas canónicas seleccionadas.

La deduplicación pertenece al ETL y al proceso de consolidación, no a la capa de consulta. Mantenerla dentro del SP produce resultados dependientes de heurísticas y hace difícil explicar la diferencia entre la tabla y la salida.

### Prioridad HIGH

1. Validar el dominio de `@temporada`.
2. Validar y limitar `@top_participaciones`.
3. Validar la clave de medallero con `id_noc` contra GUA, CHN 2008, ARG 2008 y USA 2012.
4. Resolver explícitamente las coincidencias parciales múltiples.

### Prioridad MEDIUM

1. Aplicar collation `Latin1_General_CI_AI` en búsquedas de país y filtros textuales cuando corresponda.
2. Escapar `%`, `_` y `[` en filtros `LIKE`.
3. Agregar `ORDER BY` determinístico en resultados y candidatos.

### Prioridad LOW

1. Actualizar comentarios históricos.
2. Actualizar documentación de aliases de eventos.
3. Mejorar los mensajes de salida para distinguir parámetro inválido, ausencia de coincidencias y ausencia de resultados.

### CONTRACT DECISION

1. Eliminar o conservar como `DEPRECATED` las columnas `*_estimado`.
2. Cambiar el número u orden de result sets.
3. Agregar `codigo_noc`, `nombre_noc` y `pais_representado` al detalle.
4. Cambiar nombres de columnas o estructura de respuesta.
5. Definir el comportamiento de búsquedas parciales y múltiples coincidencias.
6. Definir la resolución de país/NOC cuando existan aliases o NOC históricos.

### DESIGN DECISION

1. Definir si `GER`/`FRG`/`GDR` y `RUS`/`URS`/`EUN` se consultan como una entidad geográfica consolidada o como NOC históricos independientes.

### KEEP

1. Mantener `@id_atleta`, `@max_atletas` y `@coincidencia_exacta` para controlar homónimos.
2. Mantener las FK y los joins explícitos del modelo.
3. Mantener separadas las medallas oficiales del país y las preseas físicas de atletas.

## Cambios que NO deben hacerse

- No modificar `data/raw`.
- No modificar `data/intermediate`.
- No modificar `data/processed` como parte de la actualización de los SP.
- No volver a deduplicar participaciones dentro de los Stored Procedures.
- No agrupar participaciones por heurísticas de edad, posición, año o disciplina.
- No eliminar participaciones ni corregir rankings desde un Stored Procedure.
- No fusionar homónimos por nombre.
- No fusionar automáticamente NOC históricos.
- No eliminar eventos aliases sin evidencia específica.
- No convertir preseas de atletas en medallas oficiales del país.
- No eliminar los casos `REVIEW` sin una nueva decisión de consolidación.

## Pruebas de regresión

### `sp_historial_atleta`

Ejecutar después de modificar el procedimiento:

```text
Michael Phelps -> Gold 23, Silver 3, Bronze 2, Total 28
Paavo Nurmi    -> Total 12
Mark Spitz     -> Total 11
Usain Bolt     -> Total 8
Lionel Messi   -> Gold en Beijing 2008
Érick Barrondo -> Silver en London 2012
Chad le Clos   -> temporada Summer separada de Youth
```

También probar:

- búsqueda ambigua por nombre repetido;
- búsqueda mediante `@id_atleta`;
- `@medalla` inválida;
- rango de años invertido;
- temporada inválida;
- filtro de país con y sin acentos;
- texto de búsqueda que contiene `%`, `_` o `[`. 

### `sp_consultar_pais`

Ejecutar después de modificar el procedimiento:

```text
GUA                         -> Gold 1, Silver 1, Bronze 1, Total 3
CHN + 2008                  -> 51 Gold lógicos
ARG + 2008 + Football       -> Gold
USA + 2012 + Basketball     -> Gold
GER                         -> revisar GER/FRG/GDR
RUS                         -> revisar RUS/URS/EUN
```

También probar:

- país inexistente;
- parámetro vacío;
- coincidencia parcial ambigua;
- temporada inválida;
- `@top_participaciones = NULL`;
- `@top_participaciones <= 0`;
- valor superior al máximo permitido;
- filtro de deporte con comodines.

## Casos globales de consistencia del dataset

Este caso no pertenece a la batería específica de resolución de país de `sp_consultar_pais`, pero puede verificarse como consulta global de consistencia:

```text
Trap Women Paris 2024 -> Penny Smith, AUS, Bronze
```

La prueba debe distinguir entre el resultado del Stored Procedure y la consistencia general del modelo cargado.

## Contrato que los desarrolladores deben confirmar antes de modificar SP

Antes de implementar cualquier recomendación, confirmar explícitamente:

- ¿El cambio modifica el número de result sets?
- ¿Se eliminarán columnas?
- ¿Se agregarán columnas?
- ¿Existen consumidores frontend/backend de la salida?
- ¿Importa el orden de las columnas?
- ¿Los nombres de las columnas forman parte del contrato?
- ¿`GER` incluye `FRG`/`GDR`?
- ¿`RUS` incluye `URS`/`EUN`?
- ¿Una búsqueda parcial ambigua devuelve error o una lista?
- ¿Debe mantenerse compatibilidad hacia atrás con `*_estimado`?

Las respuestas deben quedar aprobadas por el equipo antes de aplicar cualquier `CONTRACT DECISION` o `DESIGN DECISION`.

## Documentación que debe actualizarse

Debe buscarse y actualizarse cualquier artefacto que todavía use estos valores obsoletos:

```text
ATLETA        = 336419
EVENTO        = 3007
PARTICIPACION = 733414
TOTAL         = 1090667
```

Los valores vigentes son:

```text
ATLETA        = 336418
EVENTO        = 2986
PARTICIPACION = 712658
TOTAL         = 1069889
```

La documentación también debe distinguir claramente:

- aliases históricos de `EVENTO`;
- consolidación física de participaciones confirmadas;
- medalla oficial del país;
- presea física entregada a un atleta;
- casos conservados como `REVIEW`.

## Orden recomendado de implementación

1. Leer y confirmar el contrato de salida actual.
2. Ejecutar los casos actuales y guardar sus resultados de referencia.
3. Aplicar únicamente los `SAFE CHANGE`.
4. Ejecutar las regresiones de identidad, medallero, filtros y ambigüedad.
5. Discutir y aprobar las `CONTRACT DECISION`.
6. Resolver las `DESIGN DECISION` sobre país/NOC históricos.
7. Aplicar cambios de contrato únicamente después de su aprobación.
8. Reejecutar Phelps, Nurmi, Spitz, Bolt, GUA, CHN 2008, Messi y Barrondo.
9. Documentar el resultado, las diferencias y cualquier caso `REVIEW`.

## Checklist final

- [ ] Ningún SP contiene deduplicación heurística de participaciones.
- [ ] `sp_historial_atleta` usa directamente `PARTICIPACION` para sus métricas finales.
- [ ] Las columnas de salida estimadas se eliminaron o permanecen como `DEPRECATED` según un contrato aprobado.
- [ ] El medallero de país usa `id_edicion + id_evento + id_noc + medalla`.
- [ ] Medallas oficiales y preseas físicas permanecen separadas.
- [ ] `@temporada` acepta solo los cinco valores finales.
- [ ] `@top_participaciones` tiene valores por defecto y máximo controlado.
- [ ] Las coincidencias parciales ambiguas no se resuelven silenciosamente.
- [ ] Los filtros `LIKE` escapan comodines cuando corresponde.
- [ ] Las búsquedas toleran acentos de forma documentada.
- [ ] Los NOC históricos tienen una decisión explícita de alcance.
- [ ] Las `CONTRACT DECISION` y `DESIGN DECISION` fueron aprobadas antes de aplicarse.
- [ ] Se ejecutaron los casos de Phelps, Nurmi, Spitz, Bolt, Latynina, Bjørgen y Andrianov.
- [ ] Se ejecutaron GUA, CHN 2008, ARG 2008, USA 2012, GER y RUS.
- [ ] Los conteos vigentes son 336,418 atletas, 2,986 eventos y 712,658 participaciones.
- [ ] No se modificaron datos durante la actualización de los SP.
