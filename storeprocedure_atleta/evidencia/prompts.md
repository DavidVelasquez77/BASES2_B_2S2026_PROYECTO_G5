# Evidencia de prompt engineering — Inciso d

**Herramienta:** Claude Code (Opus 5)

Este documento registra cómo se usó asistencia de IA para construir `olympics.sp_historial_atleta`, para dejar la evidencia dentro de la carpeta de cada store procedure.

---

## 1. Contexto entregado a la IA

- `.context/CONTEXT_DATA_LIMPIA_INICIO_STORE_PRODUCES_SQL_PURO.md` — handoff técnico del modelo cargado.
- `.context/GUIA_COMPANEROS_RECREAR_OLIMPIADASDB.md` — guía de reconstrucción de la base.
- `Enunciado proyecto 1.pdf` — el enunciado oficial del curso.
- `OlimpiadasF1/scripts/sql/01_create_tables.sql` — DDL real de las tablas.

---

## 2. Principio de trabajo aplicado

**No aceptar el resumen cuando se puede consultar la fuente.**

Cada supuesto del diseño se verificó con una consulta contra la base real antes de escribir el procedimiento. Los casos donde esto cambió el diseño están en la sección 3.

---

## 3. Verificaciones que cambiaron el diseño

### 3.1 El primer parámetro debe ser el nombre, no el id

El handoff interno del equipo proponía `@id_atleta BIGINT` como parámetro principal. Al leer el enunciado original se encontró que pide literalmente *"que reciba como primer parámetro el nombre del atleta"*.

**Decisión:** el enunciado manda. `@nombre_atleta` es el primer parámetro y `@id_atleta` quedó como filtro opcional de desempate.

### 3.2 La colación esconde atletas con acentos

```sql
SELECT 'CI_AS' AS variante, COUNT(*) FROM olympics.ATLETA WHERE nombre LIKE N'%Elie%'
UNION ALL
SELECT 'CI_AI', COUNT(*) FROM olympics.ATLETA
WHERE nombre COLLATE Latin1_General_CI_AI LIKE N'%Elie%';
-- 182  vs  223
```

**Decisión:** forzar `Latin1_General_CI_AI` en las comparaciones de nombre.

### 3.3 El filtro de país no puede ir por nacionalidad

```sql
SELECT SUM(CASE WHEN id_pais_nacionalidad IS NULL THEN 1 ELSE 0 END), COUNT_BIG(*)
FROM olympics.PARTICIPACION;
-- 711,939 de 712,020 en NULL  (99.99%)
```

**Decisión:** resolver el país por NOC representado.

### 3.4 `temporada` tiene cinco valores, no dos

Se iba a validar el parámetro contra `Summer`/`Winter`. La consulta mostró también `Summer Youth`, `Winter Youth` e `Intercalated Games`.

**Decisión inicial:** no validar el dominio, para no rechazar consultas legítimas con los tres valores que no se conocían.

**Corrección posterior:** la revisión final del equipo lo marcó como `HIGH` — un valor fuera de dominio devolvía un resultado vacío indistinguible de "este atleta no compitió". Ahora se valida contra los cinco valores reales y se lanza `RAISERROR` con el mensaje que los enumera. La lección fue que la alternativa a una validación incorrecta no es ninguna validación, sino la validación correcta.

### 3.5 No inventar una clasificación por fuente

Al detectar la duplicidad de eventos se evaluó etiquetar cada fila según su fuente usando el sufijo `(Olympic`. La muestra mostró que el criterio falla: `Singles, Men (Intercalated)` es estilo fuente 1 y no lleva ese sufijo.

**Decisión:** descartar la columna. Una heurística que clasifica mal es peor que no clasificar.

### 3.6 Deduplicación de medallas: dos intentos descartados y uno medido

> **Nota de lectura.** El dataset cambió tres veces durante el desarrollo. Las cifras de §3.6 a §3.8 son del primer estado (733,414 participaciones); las de §3.9 y §3.10 del segundo (712,658). Las vigentes —**712,020 participaciones, total 1,069,251**— están en §3.11 en adelante. Las secciones anteriores se conservan porque documentan cómo se detectó y cuantificó cada problema.

Este fue el punto que más iteración requirió. Se evaluaron tres caminos.

**Intento 1 — `GROUP BY` por atleta/año/deporte/medalla.** Descartado de inmediato: Phelps ganó oro en 100 m y 200 m mariposa el mismo año, así que el agrupamiento fundiría dos medallas reales en una. Subcontaría.

**Intento 2 — normalizar los nombres de evento y emparejar los dos estilos.** Se implementó y se midió contra los 3,007 eventos reales:

```
estilo A reconocido        1,383
estilo B reconocido          627
no encajan en ningun patron  997   (33%)
pares limpios 1 a 1          495
grupos ambiguos              103
```

Descartado. Los 997 sin clasificar son nombres pelados (`Tennis`, `Polo`, `Athletics`), y los grupos ambiguos son peligrosos:

```
clave 'singles' / Men:
   Singles, Men (Olympic)
   Singles, Men (Intercalated)            <- Juegos Intercalados 1906
   Singles, Men (Olympic (non-medal))     <- evento SIN medalla
   Tennis Men's Singles
```

Fusionarlos mezclaría un evento con medalla, uno de 1906 y uno sin medalla. Habría corrompido el dato de forma más difícil de detectar que el problema original.

**Intento 3 — firma estructural, el que se adoptó.** Se observó que las filas duplicadas son complementarias: una nomenclatura trae `posicion` y la otra trae `edad`. Dentro de un grupo (atleta, año, disciplina, medalla), si hay *n* filas con `posicion` y *n* con `edad`, el conteo real es *n*.

La clave es que esto permite **contar** correctamente sin resolver **qué** evento es el duplicado de cuál: no importa el emparejamiento individual, solo cuántos pares hay.

Cobertura medida sobre los 78,998 grupos con medalla:

| Caso | Grupos | % |
|---|---:|---:|
| Firma de duplicado limpia (*n* y *n*) | 27,416 | 34.70% |
| Una sola nomenclatura, sin duplicar | 23,632 | 29.91% |
| Grupo de una sola fila | 27,799 | 35.19% |
| Indeterminado | 151 | 0.19% |

**Determinable: 78,847 de 78,998 = 99.81%.**

Validación independiente en **tres atletas distintos** —distintas décadas, deportes y países— todos exactos en los tres desgloses:

| Atleta | Época / deporte / NOC | Crudo | Estimado | Real |
|---|---|---|---|---|
| Michael Phelps (93113) | 2000–2016 · natación · USA | 46/6/4 = 56 | **23/3/2 = 28** | 23 oro, 3 plata, 2 bronce |
| Chad le Clos (119877) | 2012–2016 · natación · RSA | 2/6/0 = 8 | **1/3/0 = 4** | 1 oro, 3 plata |
| Nikolay Andrianov (31000) | 1972–1980 · gimnasia · URS | 14/10/6 = 30 | **7/5/3 = 15** | 7 oro, 5 plata, 3 bronce |

Además, Chad le Clos con `@temporada = 'Summer Youth'` da estimado igual al crudo (`1/3/1 = 5`) y diagnóstico `sin duplicados detectados`: el Youth viene de una sola fuente. El método distingue el caso con duplicación del caso sin ella.

El método no recibió ninguna información sobre medallas reales: solo cuenta pares de `posicion`/`edad`.

**Decisión:** mostrar ambas cifras lado a lado. El conteo crudo nunca se altera; el estimado se presenta junto a una columna `diagnostico`. Donde la firma no concluye se reporta el crudo, para no subcontar nunca en silencio.

Unificar los eventos sigue siendo trabajo del Bloque 4. Lo que hace el SP es contar bien y decir cómo lo hizo.

### 3.7 Error detectado al validar las cifras contra la base

El desglose anterior se calculó primero con un script de Python sobre los CSV, y dio `21,791 / 27.6%` para la firma limpia. Al ejecutar la prueba T16 contra la base, SQL Server devolvió `27,416 / 34.70%`.

La discrepancia se detectó porque **las categorías de la base suman 78,998 y las del script sumaban 73,373**. El script tenía una condición extra (que el total de filas fuera igual a `con_posicion + con_edad`) que no está en la lógica del procedimiento, y eso dejó 5,625 grupos fuera de toda categoría: la partición no era exhaustiva.

La cifra de cobertura (99.81%) no estaba afectada, porque se había calculado sin esa condición extra.

Al investigar esos 5,625 grupos se verificó además que el estimado sigue siendo correcto en ellos, y que el único caso capaz de subcontar —filas sin `posicion` ni `edad` dentro de un grupo con firma limpia— **no existe en esta base (0 grupos)**.

**Lección aplicada:** validar toda partición comprobando que las categorías sumen el total, y tomar la base como fuente de verdad por encima de cualquier cálculo auxiliar.

### 3.8 La corrección se extendió a `participaciones`

Una revisión posterior detectó que se había limpiado solo **una** de las dos cantidades que importan. La ficha seguía mostrando `participaciones = 60` para Phelps, inflado por los mismos duplicados: sus eventos reales son **30**.

Se verificó que la firma aplica igual a las filas **sin medalla**. Caso real, Sídney 2000:

```
200 metres Butterfly, Men (Olympic)   posición=5     edad=NULL
Swimming Men's 200 metres Butterfly   posición=NULL  edad=15.00
```

Un solo evento registrado dos veces, con la misma estructura complementaria.

**Cambio aplicado:** el agrupamiento pasó a incluir las filas con `medalla IS NULL`, y la ficha ganó `participaciones_estimado` y `total_medallas_estimado`. Resultado para Phelps: `60 → 30` y `56 → 28`.

Se comprobó además que `ediciones` y `deportes` **no** requieren corrección: usan `COUNT(DISTINCT)`, así que los duplicados no los afectan. El único conteo afectado era el `COUNT(*)` de participaciones.

---

### 3.9 La heurística cumplió su función y se retiró

Este es el cierre del arco de §3.6 a §3.8.

La estimación se construyó porque la base tenía las medallas duplicadas y no había forma de responder correctamente *"¿cuántas medallas tiene este atleta?"*. Sirvió para **detectar el problema, cuantificarlo y validarlo** contra tres atletas independientes, y ese resultado se reportó al equipo.

El responsable del ETL aplicó la corrección en el origen. Con los datos nuevos, `PARTICIPACION` devuelve `23/3/2 = 28` para Phelps **sin ninguna heurística**, que es exactamente lo que la estimación había predicho.

La revisión final del equipo marcó entonces la lógica como `CRITICAL` para retirar, con el argumento correcto: *"la deduplicación pertenece al ETL y al proceso de consolidación, no a la capa de consulta"*.

**Se retiraron** `#grupos`, `#est`, las columnas `participaciones_estimado`, `total_medallas_estimado`, `oro_estimado`, `plata_estimado`, `bronce_estimado`, `total_estimado` y la columna `diagnostico`. Las métricas salen ahora directamente de `PARTICIPACION`.

La lección: una heurística de consulta puede ser la herramienta correcta para *diagnosticar* un problema de datos, y la herramienta equivocada para *convivir* con él. Una vez corregido el origen, mantenerla habría producido dos números donde debe haber uno.

### 3.10 Un atajo tentador que se descartó con medición

Al verificar los datos nuevos se encontró que la duplicación de medallas persiste fuera de los casos corregidos: Ray Ewry aparece con 20 oros cuando sus oros reales son 10.

Se evaluó un atajo: contar solo las filas con `posicion IS NOT NULL`, porque de cada par duplicado una fila trae `posicion` y la otra trae `edad`. El resultado parecía perfecto en siete atletas de prueba:

```
Phelps          23 -> 23   real 23        Carl Lewis      16 -> 9   real 9
Ray Ewry        20 -> 10   real 10        Birgit Fischer  16 -> 8   real 8
Jenny Thompson  16 -> 8    real 8         Usain Bolt      16 -> 8   real 8
                                          Paavo Nurmi     18 -> 9   real 9
```

Siete de siete. Pero antes de adoptarlo se midió el riesgo opuesto — perder medallas legítimas sin `posicion`:

```
filas con medalla:                                 103,223
  con posicion:                                     44,072  (42.7%)
grupos sin ninguna fila con posicion:               37,117
filas legítimas que el filtro perdería:             37,721
```

Se caen los deportes de equipo y varios relevos (Hockey, Football, Curling, el 4×400 femenino), donde la posición nunca se registró. **Descartado.**

La lección es la misma de §3.7: siete casos que confirman una hipótesis no la validan; hay que buscar activamente el caso que la rompe.

### 3.11 La heurística volvió, y esta vez como el número oficial

En §3.9 se retiró la estimación porque el ETL había corregido el problema. Al revisar los datos del 14 de septiembre se encontró que la corrección fue **parcial**: el ETL aplicó 1,015 pares confirmados y verificó siete atletas concretos, pero el patrón persistía en el resto.

```
Ray Ewry        20 oros   reales 10
Jenny Thompson  24 medallas   reales 12
```

El coordinador indicó resolverlo desde el SP, revirtiendo explícitamente la instrucción `CRITICAL` de su propia revisión.

**Antes de implementarlo se verificó que la regla no rompiera lo ya corregido.** Ese era el riesgo real: si el ETL había cambiado la estructura, la firma podía descalibrarse y subcontar.

| Atleta | crudo | con la regla | real | |
|---|---|---|---|---|
| Michael Phelps | 23/3/2 | 23/3/2 | 23/3/2 | sin cambio |
| Ray Ewry | 20/0/0 | **10/0/0** | 10/0/0 | corregido |
| Jenny Thompson | 16/6/2 | **8/3/1** | 8/3/1 | corregido |
| Usain Bolt | 8/0/0 | 8/0/0 | 8/0/0 | sin cambio |
| Paavo Nurmi | 9/3/0 | 9/3/0 | 9/3/0 | sin cambio |
| Mark Spitz | 9/1/1 | 9/1/1 | 9/1/1 | sin cambio |
| Nikolay Andrianov | 7/5/3 | 7/5/3 | 7/5/3 | sin cambio |
| Marit Bjørgen | 8/4/3 | 8/4/3 | 8/4/3 | sin cambio |
| Larysa Latynina | 9/5/4 | 9/5/4 | 9/5/4 | sin cambio |

**Nueve de nueve.** Arregla lo roto y no toca lo que el ETL ya había resuelto.

**Diferencia de diseño respecto a §3.6:** antes se mostraban dos cifras lado a lado, crudo y estimado. La revisión del equipo objetó eso —*"el SP no debe presentar simultáneamente conteos crudos y estimados como si ambos fueran resultados oficiales"*— y tenía razón. Ahora hay **un solo número oficial**, el corregido, más una columna `filas_origen` que deja el conteo auditable sin competir con él.

### 3.12 La misma regla se probó en `participaciones` y se descartó

Por consistencia se evaluó corregir también el conteo de participaciones. **Se midió y no funciona:**

```
                crudo  ->  con la regla    real
Michael Phelps    30        30             30    OK
Usain Bolt        12        11             10    NO
Paavo Nurmi       15        15             12    NO
Ray Ewry          23        13             10    NO
grupos indeterminados: 6,924  (contra 196 en medallas)
```

La razón es estructural: en el medallero el valor de `medalla` forma parte de la clave de agrupación, así que los grupos quedan finos. En las filas sin medalla **todas tienen `medalla = NULL`**, así que un atleta con varios eventos distintos en el mismo año y disciplina cae en un solo grupo y contar pares deja de significar algo.

**Decisión:** aplicar la corrección solo al medallero. `participaciones` se reporta crudo, documentado como limitación.

La lección se repite: una regla que funciona en un contexto no se traslada a otro sin volver a medirla.

### 3.13 Una búsqueda que fallaba sin dar señal

El coordinador señaló que el separador `•` podía romper la búsqueda. Se verificó y era cierto:

```
nombre_completo    0 filas con el caracter   <- la unica que se limpio
nombre_usado     145,500
nombre_original   30,706
```

`Lionel Messi` tiene `nombre_usado = 'Lionel•Messi'` y Cristiano Ronaldo `'•Cristiano Ronaldo'`. El SP limpiaba el carácter **en la salida** pero comparaba contra el valor crudo, así que la búsqueda exacta no alcanzaba esas dos columnas.

Es el tipo de falla que no se nota: no da error, solo deja de encontrar cosas.

**Corregido:** `REPLACE(columna, NCHAR(8226), N' ')` antes de comparar, en las cuatro columnas de nombre.

### 3.14 Un error propio al buscar a Marit Bjørgen

Al validar las regresiones, el script de verificación reportó que **Marit Bjørgen no existía en la base**. Era falso: está, con id `100161` y 15 medallas.

El script normalizaba acentos con Unicode NFD, que descompone `é` en `e` + diacrítico pero **no descompone `ø`**, porque no es una vocal acentuada sino una letra distinta del alfabeto nórdico.

Detectado al contrastar contra el ranking de medallistas noruegos, donde aparecía en segundo lugar.

**Lección:** "quitar acentos" y "normalizar caracteres no-ASCII" no son lo mismo. Antes de afirmar que un dato no existe, conviene buscarlo por otra vía.

El límite era del script, no del procedimiento: se verificó después que la colación `Latin1_General_CI_AI` del SP **sí** pliega la `ø`, y buscar `Bjorgen` devuelve a `Marit Bjørgen`. Se probaron una por una `ø æ å ð þ ł ß đ ı` y se pliegan todas.

### 3.15 Un conteo mal contado que apareció al revisar las capturas

Al revisar `06_guatemala.png` el resultado en pantalla decía **20 ediciones**, pero `pruebas.sql` y `consultas_ejemplo.sql` afirmaban 19. El número escrito venía de una medición propia sobre los CSV, y estaba mal: se habían contado **años distintos**, no ediciones.

```
id_edicion distintos : 20
anios distintos      : 19
1988 -> ['Winter', 'Summer']
```

Guatemala compitió en los Juegos de Invierno **y** de Verano de 1988, que son dos ediciones del mismo año. El 20 de la consulta es correcto; se corrigieron los dos archivos y la tabla de pruebas.

Vale la pena dejarlo escrito porque el error no estaba en la consulta sino en el valor esperado, que es el caso en que una prueba puede "fallar" estando bien.

---

### 3.16 Una prueba que nunca habia corrido

Al colapsar los comentarios de `pruebas.sql` a una linea se ejecutó el archivo completo para comprobar que nada se hubiera roto, y apareció un error que **ya estaba en `main`**:

```
Msg 468: Cannot resolve the collation conflict between
"Latin1_General_CI_AI" and "Latin1_General_CI_AS" in the not equal to operation.
```

La consulta de T5b comparaba la columna consigo misma bajo dos colaciones explícitas distintas:

```sql
WHERE nombre COLLATE Latin1_General_CI_AS <> nombre COLLATE Latin1_General_CI_AI
```

SQL Server no puede resolver eso: cuando los dos lados traen `COLLATE` explícito y no coinciden, no hay regla de precedencia que aplicar. La idea de fondo tampoco funcionaba, porque `COLLATE` cambia cómo se compara un texto, **no lo transforma**: no existe una colación que devuelva la cadena sin acentos.

Se reemplazó por una detección directa de caracteres fuera de ASCII imprimible, con colación binaria para que el rango del `LIKE` no dependa de la colación de la base:

```sql
WHERE nombre COLLATE Latin1_General_BIN2 LIKE N'%[^ -~]%'
```

Devuelve `Glíma`, que es el único deporte con un carácter no ASCII. El resto de T5b —buscarlo sin acento con `@deporte = N'Glima'`— sí funcionaba, porque ahí solo un lado lleva `COLLATE`.

Lo que deja como lección: el archivo de pruebas se había revisado leyéndolo, no ejecutándolo de corrido. Un error de ese tipo solo aparece al correrlo entero.

---

### 3.17 La causa, después de dos intentos por el síntoma

La corrección de medallas funcionaba, pero `participaciones` seguía inflado y en §3.12 se había concluido que no tenía arreglo. La conclusión era correcta **para la regla que se estaba usando**, no para el problema.

El giro vino de mirar la salida cruda de Usain Bolt:

```
2004  200 metres, Men (Olympic)            posicion 5     edad -
2004  Athletics Men's 200 metres           posicion -     edad 17
```

Los nombres de `EVENTO` vienen en **dos familias**: la canónica lleva un calificador entre paréntesis y la descriptiva no. No son dos formas de escribir lo mismo por descuido: son **dos orígenes que se fusionaron** al construir la base, y cada uno llena columnas distintas —la canónica `posicion` y `nombre_competencia`, la descriptiva `edad` y `equipo`.

Las dos reglas anteriores inferían el duplicado de *qué columnas estaban llenas*, que es el síntoma. Identificar la familia por el nombre del evento ataca la causa.

Se comprobó que `EVENTO` no tiene ninguna columna que relacione ambos registros —solo `id_evento`, `id_disciplina` y `nombre`—, así que la familia hay que leerla del nombre.

**La regla:** dentro de `(atleta, edición, disciplina)` —más `medalla` para el medallero— se cuentan las filas canónicas; si no hay ninguna, las descriptivas.

Antes de aplicarla se validó contra verdades comprobables fuera de la base:

| Atleta | Filas | Regla | Verdad |
|---|---:|---:|---|
| Usain Bolt | 12 | 10 | 1 en 2004 + 3 en 2008, 2012 y 2016 |
| Guy Forget | 9 | 5 | 1984 exhibición + 2 en 1988 + 2 en 1992 |
| Ray Ewry | 23 | 13 | 10 oros + 3 DNS |
| Michael Phelps | 30 | 30 | correcto de origen |

Y **reprodujo las nueve regresiones de medalla exactas**, que era la condición para poder reemplazar la regla anterior sin romper lo ya validado.

Dos cosas que mejoraron de paso: el SP quedó con **una sola regla** para los dos conteos en vez de dos heurísticas distintas, y los grupos indeterminados de medallas bajaron de **196 a 14**.

Se midió el riesgo antes de aplicar: 590 grupos de 428,251 (0.14%) donde la familia descriptiva aporta más eventos que la canónica. Esos quedan marcados en `grupos_indeterminados`, no silenciados.

Lo que deja como lección: "no se puede corregir" suele significar "no se puede con la regla que estoy usando". Vale la pena separar las dos afirmaciones antes de darlo por cerrado.

---

### 3.18 La verificación externa, que faltaba desde el principio

Todo lo demás se había contrastado contra la base. Pero las cifras "reales" —Bolt 10, Forget 5, Nurmi 15, Ewry 10 oros— eran el patrón contra el que se medía, y no salían de ninguna consulta: venían de razonar sobre el dato. Se verificaron contra Olympedia el 2026-09-15.

Las cuatro coinciden. La interesante es Nurmi: una fuente secundaria dice que compitió en **12** pruebas y el SP decía **15**. Olympedia resolvió la aparente contradicción — son 15 entradas, de las cuales 3 son DNS, y 12 con medalla. La fuente secundaria contaba solo las que largó.

El SP devuelve `participaciones = 15` y `dns = 3` en el mismo result set, así que sostiene las dos lecturas a la vez.

**Lección:** una cifra propia que coincide con el dato propio no está verificada, solo es consistente. Y cuando dos fuentes discrepan, conviene buscar la primaria antes de suponer que una está mal: acá ninguna lo estaba, contaban cosas distintas.

---

## 4. Consultas de exploración ejecutadas

| Objetivo | Hallazgo |
|---|---|
| Nombres duplicados | 49,869 nombres repetidos; `John Jr.` ×76 |
| Dominio de `medalla` | `Gold`, `Silver`, `Bronze`, `NULL` |
| Dominio de `estado_resultado` | `DNS` 8,831 · `DNF` 7,941 · `DQ` 1,563 |
| Cobertura de columnas de nombre | `nombre` 336,419 · `nombre_completo` 145,500 |
| Índices disponibles | No hay índice por `ATLETA.nombre` |
| Atletas sin participación | 241 |
| Dominio de `sexo` | `M`/`Male` y `F`/`Female` sin homologar |
| Separador en `nombre_completo` | 145,252 filas con `•` (U+2022) |
| Duplicidad de eventos | 15,766 medallistas con conteo duplicado |

---

## 5. Problema de entorno resuelto

Al ejecutar los scripts con el *pipe* de la guía:

```powershell
Get-Content script.sql -Raw | docker exec -i ... sqlcmd ...
```

se obtuvo `Msg 102: Incorrect syntax near '﻿'`. Se comprobó que **ningún `.sql` tiene BOM en disco**: lo inyecta Windows PowerShell 5.1 al canalizar hacia un ejecutable nativo.

**Solución adoptada:** `docker cp` + `sqlcmd -i -f 65001`, que además evita corromper los acentos de los 13 scripts con UTF-8.

Se detectó también que `disciplina.csv` falla con `ROWTERMINATOR = '0x0a'` en cualquier checkout de Windows con `core.autocrlf=true`, por ser el único de los seis archivos configurados como LF que tiene campos entrecomillados (21 filas como `53,31,"20 kilometres, Men"`). Se resolvió ejecutando una copia corregida dentro del contenedor, **sin modificar el script del repositorio**.

---

## 6. Verificación final

El procedimiento se ejecutó contra las **28 pruebas** de `pruebas.sql`, todas contra la base vigente. Los resultados están en la sección 6 de `documentacion_d.md`.

Además se verificaron las regresiones que exige la revisión final del equipo: Phelps `23/3/2 = 28`, Nurmi 12, Spitz 11, Bolt 8, Messi oro en Beijing 2008 y Barrondo plata en Londres 2012. Las seis coinciden.

Ninguna afirmación de la documentación se escribió sin ejecutar antes la consulta que la respalda.
