# Inciso d — Stored procedure por atleta

**Integrante:** Valery Alarcón
**Grupo:** 7 — Sistemas de Bases de Datos 2, 2do. Semestre 2026
**Objeto creado:** `olympics.sp_historial_atleta`
**Base vigente:** 336,418 atletas · 2,986 eventos · 712,020 participaciones · total 1,069,251

---

## 1. Qué pide el enunciado

> **d)** Realizar un stored procedure que reciba como primer parámetro el nombre del atleta y que despliegue toda la información relacionada con el mismo, participaciones, resultados, medallas, el formato de salida es a su criterio. Pueden agregar parámetros para mostrar o filtrar información específica, por ejemplo, deporte, país y año.

Dos exigencias literales que condicionan el diseño:

1. El **primer parámetro es el nombre**, no un id. El handoff interno del equipo sugería `@id_atleta BIGINT`; se siguió el enunciado y el id quedó como filtro opcional de desempate.
2. El formato de salida es libre, y los filtros por **deporte, país y año** están explícitamente habilitados.

---

## 2. Archivos de esta carpeta

| Archivo | Contenido |
|---|---|
| `sp_historial_atleta.sql` | El stored procedure (`CREATE OR ALTER`) |
| `consultas_ejemplo.sql` | Consultas listas para la calificación (Guatemala, futbolistas, rankings, edades) |
| `pruebas.sql` | 28 pruebas ejecutables desde SSMS |
| `documentacion_d.md` | Este documento |
| `evidencia/prompts.md` | Evidencia de prompt engineering |
| `evidencia/hallazgos_reportados.md` | Hallazgos de calidad de datos reportados al equipo |
| `evidencia/img/` | Capturas con fecha y hora visibles |

El procedimiento **no altera el modelo físico** entregado en el inciso c y **no escribe datos**: es de solo lectura y consulta únicamente el schema `olympics`, nunca `stg`.

---

## 3. Firma del procedimiento

```sql
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'...',   -- obligatorio (primer parámetro)
     @deporte             = NULL,     -- coincidencia parcial
     @pais                = NULL,     -- código NOC, nombre NOC o país
     @anio                = NULL,     -- año exacto
     @anio_desde          = NULL,     -- rango inclusivo
     @anio_hasta          = NULL,
     @medalla             = NULL,     -- Gold | Silver | Bronze
     @temporada           = NULL,     -- uno de los 5 valores válidos
     @solo_medallistas    = 0,        -- 1 = solo filas con medalla
     @coincidencia_exacta = 0,        -- 1 = nombre exacto
     @id_atleta           = NULL,     -- desempate directo
     @max_atletas         = 25;       -- tope antes de declarar ambigüedad (máx. 500)
```

### Salida — tres result sets

1. **Ficha del atleta**: datos biográficos, país de nacimiento, y las métricas `participaciones`, `participaciones_filas_origen`, `total_medallas`, `medallas_filas_origen`, `ediciones`, `deportes`, `primer_ano`, `ultimo_ano`.
2. **Medallero**: oro / plata / bronce / total, más `filas_origen`, `grupos_indeterminados` y el desglose de resultados sin medalla (`DNF`, `DNS`, `DQ`, posiciones sin premio).
3. **Detalle de participaciones**: año, temporada, sede, deporte, disciplina, evento, NOC, país representado, equipo, edad, posición, empate, estado, medalla y `posterior_a_fallecimiento`.

El **detalle es fiel a `PARTICIPACION`**: no agrupa ni descarta filas. El **medallero corrige la duplicación de medallas** que persiste en el dato (§5.2); `filas_origen` deja ese conteo auditable.

Cuando la búsqueda es ambigua o no da resultados, devuelve **un solo result set informativo** en lugar de los tres, para que el caso se distinga de una respuesta vacía.

---

## 4. Decisiones de diseño

### 4.1 Búsqueda insensible a acentos

La base tiene colación `SQL_Latin1_General_CP1_CI_AS`: ignora mayúsculas pero **distingue acentos**. Buscar `Elie` no encontraría a `Élie, Comte de Lastours`.

El procedimiento fuerza `Latin1_General_CI_AI` solo en la comparación:

| Colación | Atletas que coinciden con `%Elie%` |
|---|---:|
| `CI_AS` (la de la base) | 182 |
| `CI_AI` (la del SP) | **223** |

Se recuperan 41 atletas que de otro modo quedaban invisibles (`Éliécer Montes`, `Aurélien Agnan`, entre otros).

### 4.1b Normalización del separador `•` en la búsqueda

El carácter U+2022 quedó dentro de los datos: **145,500 filas en `nombre_usado`** y **30,706 en `nombre_original`**. Solo se limpió de `nombre_completo`.

Eso rompía la búsqueda contra esas columnas:

```
Lionel Messi      →  nombre_usado = 'Lionel•Messi'
Cristiano Ronaldo →  nombre_usado = '•Cristiano Ronaldo'
```

El procedimiento aplica `REPLACE(columna, NCHAR(8226), N' ')` en las cuatro columnas de nombre **antes de comparar**, tanto en la búsqueda exacta como en la parcial. El dato no se modifica.

### 4.2 Control de ambigüedad

Buscar por nombre es ambiguo por naturaleza: hay **48,370 nombres repetidos** entre atletas distintos. `Usain Bolt` existe como 10 `id_atleta`, `Paavo Nurmi` como 12, `Eric Lemming` como 23.

Si la búsqueda supera `@max_atletas`, el SP devuelve la **lista de candidatos** ordenada por medallas y participaciones, en vez de volcar miles de filas. El usuario refina con `@id_atleta`.

La revisión final del equipo marcó esta lógica como `KEEP`, precisamente porque la fragmentación de identidades sigue presente en el dato.

### 4.3 El filtro de país va por NOC

`PARTICIPACION.id_pais_nacionalidad` es nullable y está casi siempre vacío, así que no sirve como filtro. El país se resuelve por el **NOC representado**, aceptando tres formas: código (`FRA`), nombre del NOC (`France`) o nombre de la entidad geográfica.

El detalle expone los tres conceptos por separado, que es la distinción que el modelo exige no confundir. Ejemplo real (prueba T18, Nikolay Andrianov):

```
codigo_noc        = URS                  <- comité olímpico histórico
pais_representado = Russian Federation   <- entidad geográfica actual
equipo            = Soviet Union         <- nombre del equipo de la época
```

Varios NOC históricos conviven apuntando a la misma entidad: `FRG`, `GDR` y `GER` → Germany; `URS` y `EUN` → Russian Federation.

### 4.4 Se buscan cuatro columnas de nombre

`nombre` está siempre poblado; `nombre_completo`, `nombre_usado` y `nombre_original` solo en parte de las filas. El SP busca en las cuatro, lo que aumenta la cobertura.

### 4.5 Comodines neutralizados en los tres filtros parciales

Si el usuario escribe `%`, se busca literalmente y no devuelve la tabla completa. Los caracteres `%`, `_` y `[` se escapan antes de armar el patrón, y esto aplica a `@nombre_atleta`, `@deporte` y `@pais`.

### 4.6 Validación de dominios

- `@medalla` acepta solo `Gold`, `Silver`, `Bronze` o `NULL`.
- `@temporada` acepta solo los cinco valores reales de `EDICION_OLIMPICA`.
- `@anio_desde` no puede ser mayor que `@anio_hasta`.
- `@max_atletas` normaliza `NULL` y valores `<= 0` a 25, y se acota a un máximo de 500.

Un valor fuera de dominio lanza `RAISERROR` con mensaje explícito, en vez de devolver un resultado vacío que parecería *"este atleta no tiene medallas"*.

### 4.7 No se agregó ningún índice

La búsqueda por nombre hace scan de `ATLETA` porque no hay índice por nombre y el `COLLATE` impediría usarlo. Agregar uno habría mejorado la búsqueda, pero implica alterar el modelo físico del inciso c, y el handoff indica que la base debe soportar los procedimientos **sin modificar el modelo**.

El tiempo se mide con la prueba T15 (`DATEDIFF` sobre `SYSDATETIME()`). En la medición anterior dio 51 ms con la tabla en caché, que no justifica tocar el modelo.

### 4.8 Dominio real de `temporada`

Tiene **cinco** valores, no dos:

| Temporada | Ediciones | Rango |
|---|---:|---|
| Summer | 30 | 1896–2024 |
| Winter | 24 | 1924–2022 |
| Summer Youth | 3 | 2010–2018 |
| Winter Youth | 3 | 2012–2020 |
| Intercalated Games | 1 | 1906 |

`@temporada = 'Summer'` **no** incluye `Summer Youth`: el filtro es de igualdad exacta. La prueba T17 lo demuestra con Chad le Clos, que compitió en ambas.

---

## 5. Calidad de datos: estado, corrección aplicada y limitaciones

Durante la construcción del procedimiento se detectaron varios problemas en el dato de origen y se reportaron al equipo. El detalle reproducible está en `evidencia/hallazgos_reportados.md`.

### 5.1 Resueltos en el ETL

| Hallazgo | Estado |
|---|---|
| Dominio de `sexo` sin homologar (`M`/`Male`, `F`/`Female`) | resuelto — solo `Male` y `Female` |
| Separador `•` en `nombre_completo` | resuelto en esa columna — sigue en `nombre_usado` y `nombre_original` (§4.1b) |
| Identidades guatemaltecas duplicadas | resuelto — Guatemala pasó de 1,232 a **594** participaciones y de 802 a **263** atletas |
| Duplicación de medallas en 1,015 pares confirmados | resuelto — Nurmi, Spitz y Bolt quedaron correctos |

### 5.2 Corregido en el procedimiento: medallas y participaciones

El ETL corrigió 1,015 pares confirmados, pero **el patrón persiste en el resto del dataset**: la misma medalla sigue registrada dos veces bajo las dos nomenclaturas de evento, con campos complementarios.

```
1900  Standing High Jump, Men (Olympic)      pos=1   edad=-
1900  Athletics Men's Standing High Jump     pos=-   edad=26     <- el mismo salto
```

Sin corregir, el ranking de medallistas queda mal desde el segundo puesto: Ray Ewry aparece con **20 oros** cuando son **10**, y Jenny Thompson con **24 medallas** cuando son **12**.

#### La causa, no el síntoma

Los nombres de `EVENTO` vienen en dos familias, y son dos orígenes distintos que se fusionaron al construir la base:

| Familia | Forma | Ejemplo | Trae |
|---|---|---|---|
| canónica | calificador entre paréntesis | `200 metres, Men (Olympic)` | `posicion`, `nombre_competencia` |
| descriptiva | sin paréntesis | `Athletics Men's 200 metres` | `edad`, `equipo` |

Identificar la familia por el nombre del evento es lo que permite reconocer la fila repetida, en lugar de inferirla de qué columnas están llenas.

**La regla aplicada:** dentro de un grupo `(atleta, edición, disciplina)` —más `medalla` cuando se cuentan medallas— se cuentan las filas de la familia canónica. Si el grupo solo tiene filas descriptivas, se cuentan esas.

Es una sola regla para los dos conteos. Cuando la familia descriptiva aporta *más* eventos que la canónica el grupo se marca en `grupos_indeterminados`, porque ahí puede haber un evento legítimo que solo existe en ese origen.

**Validación — las nueve regresiones del equipo dan exacto:**

| Atleta | `filas_origen` | Medallero | Real |
|---|---:|---|---|
| Michael Phelps | 28 | 23 / 3 / 2 = 28 | coincide |
| Larysa Latynina | 18 | 9 / 5 / 4 = 18 | coincide |
| Marit Bjørgen | 15 | 8 / 4 / 3 = 15 | coincide |
| Nikolay Andrianov | 15 | 7 / 5 / 3 = 15 | coincide |
| Jenny Thompson | **24** | 8 / 3 / 1 = **12** | corregido |
| Paavo Nurmi | 12 | 9 / 3 / 0 = 12 | coincide |
| Mark Spitz | 11 | 9 / 1 / 1 = 11 | coincide |
| Ray Ewry | **20** | 10 / 0 / 0 = **10** | corregido |
| Usain Bolt | 8 | 8 / 0 / 0 = 8 | coincide |

Los siete que el ETL ya había corregido tienen `filas_origen = total`: el procedimiento **no los toca**.

**Y la misma regla corrige `participaciones`**, contra casos de verdad verificable:

| Atleta | Filas | `participaciones` | Comprobación |
|---|---:|---:|---|
| Usain Bolt | 12 | **10** | 2004 (1) + 2008, 2012 y 2016 (3 cada uno) |
| Guy Forget | 9 | **5** | 1984 (1, exhibición) + 1988 (2) + 1992 (2) |
| Ray Ewry | 23 | **13** | 10 oros + 3 DNS |
| Michael Phelps | 30 | **30** | correcto de origen, no se toca |
| Paavo Nurmi | 15 | **15** | 15 pruebas; sus 12 son medallas, no participaciones |

Impacto global:

| Conteo | Filas | Reales | Indeterminados |
|---|---:|---:|---:|
| Medallas | 103,223 | **82,698** (−19.9%) | 14 de 78,975 |
| Participaciones | 712,020 | **557,545** (−21.7%) | 590 de 428,251 |

Las dos columnas `participaciones_filas_origen` y `medallas_filas_origen` dejan el conteo auditable: si superan al total, ese atleta tenía filas repetidas.

#### Verificación contra fuentes externas

Las cifras "reales" de arriba no salen de la base: son el patrón con el que se la contrasta. Se verificaron el **2026-09-15** contra Olympedia, que es la fuente de la que deriva este dataset.

| Atleta | El SP dice | La fuente dice | |
|---|---|---|---|
| Paavo Nurmi | 15 participaciones, 12 medallas, `dns = 3` | 15 entradas: 9 oros, 3 platas y 3 DNS (1500 m y steeplechase en 1920, 800 m en 1924) | coincide |
| Guy Forget | 5 participaciones | 1984 singles (exhibición), 1988 y 1992 singles y dobles | coincide |
| Usain Bolt | 10 participaciones | 200 m en 2004; 100 m, 200 m y relevo en 2008, 2012 y 2016 | coincide |
| Ray Ewry | 10 oros | 8 olímpicos más 2 en los Juegos Intercalados de 1906 | coincide |

El caso de Nurmi es el que más dice. Una fuente secundaria afirma que compitió en 12 pruebas, porque cuenta solo las que largó; Olympedia registra 15 entradas con 3 DNS. El SP devuelve `participaciones = 15` **y** `dns = 3`, así que reproduce las dos lecturas sin contradecirse.

Fuentes: [Olympedia – Paavo Nurmi](https://www.olympedia.org/athletes/67728), [Olympedia – Guy Forget](https://www.olympedia.org/athletes/17), [Olympedia – Ray Ewry](https://www.olympedia.org/athletes/78385), [Usain Bolt en olympics.com](https://www.olympics.com/en/athletes/usain-bolt).

#### Los 10 oros de Ray Ewry, y por qué las fuentes dicen 8

Es previsible que alguien objete la cifra, porque el COI acredita a Ray Ewry con **8** oros. Las dos cifras son compatibles y el dataset permite demostrarlo:

| Año | Temporada en la base | Oros |
|---|---|---:|
| 1900 | Summer | 3 |
| 1904 | Summer | 3 |
| **1906** | **Intercalated Games** | **2** |
| 1908 | Summer | 2 |

Los Juegos Intercalados de Atenas 1906 **no son reconocidos por el COI**. El dataset sí los incluye, y los marca con su propia `temporada`, así que el 10 es el número correcto *para esta base* y el 8 se obtiene sin tocar nada:

```sql
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Ray Ewry', @temporada = N'Summer';   -- 8 / 0 / 0
```

`Intercalated Games` es uno de los cinco valores que acepta `@temporada` (§4.8), precisamente porque existe en `EDICION_OLIMPICA` como una edición más.

### 5.3 Una regla anterior que se descartó

La primera versión contaba por una firma estadística: dentro de `(atleta, año, disciplina, medalla)`, si había *n* filas con `posicion` y *n* con `edad`, el real era *n*. Daba bien las nueve regresiones, pero tenía dos problemas.

No servía para `participaciones`: ahí todas las filas comparten `medalla = NULL`, así que un atleta con varios eventos en el mismo año y disciplina caía en un solo grupo y contar pares dejaba de significar algo. Medido entonces: Bolt daba **11** cuando son **10**.

Y dejaba **196** grupos de medallas indeterminados, contra **14** de la regla por familia de evento. La diferencia es que aquella inferría el duplicado de qué columnas venían llenas, y ésta lo identifica por su causa.

### 5.4 Pendiente: atletas homónimos sin fusionar

**48,370 nombres repetidos.** `Usain Bolt` existe como 10 `id_atleta`, `Eric Lemming` como 23. El SP lo maneja con el control de ambigüedad de §4.2.

Un dato que acota el problema: entre los atletas **con fecha de nacimiento** hay un solo par duplicado en toda la base. Toda la fragmentación está en los registros sin datos biográficos, que son los que no se pudieron emparejar.

### 5.5 Señalado en el procedimiento: participaciones imposibles

Personas distintas fusionadas en un mismo `id_atleta`. Nikolay Andrianov (`31000`), gimnasta soviético fallecido en 2011, tiene 24 participaciones correctas de 1972 a 1980 **más una fila de kayak femenino por China en 2020**. Aristidis Akratopoulos (`173`), tenista de Atenas 1896, tiene una fila de taekwondo por Etiopía en 2020.

Alcance: **784 participaciones posteriores a la fecha de fallecimiento** del atleta, en 781 atletas — un 0.11% de las filas. Verificado que es previo a las correcciones del ETL, no una regresión.

Por indicación expresa del equipo, **no se filtran**. Filtrarlas sería esconder dato de origen.

Pero señalarlas no es filtrarlas. El detalle trae la columna **`posterior_a_fallecimiento`**, que marca con `1` las filas cuyo año es posterior a la muerte del atleta:

```
1980  Artistic Gymnastics  Rings, Men (Olympic)   URS   posterior_a_fallecimiento = 0
2020  Canoe Slalom         Women's Kayak          CHN   posterior_a_fallecimiento = 1
```

Sin la marca, la fila de 2020 sale mezclada con la gimnasia soviética sin ninguna señal de que es imposible. Con ella, quien lea el detalle la identifica sin tener que conocer la fecha de fallecimiento de memoria. El conteo no cambia: la fila sigue contando.

---

## 6. Casos de prueba

Ejecutables desde `pruebas.sql` (28 pruebas).

| # | Caso | Esperado |
|---|---|---|
| T1 | Phelps, solo medallas | 23 / 3 / 2 = 28, `filas_origen` 28 |
| T2 | Phelps sin filtro | 30 participaciones, 5 ediciones |
| T3 | Búsqueda ambigua (`Messi`) | Aviso + 26 candidatos |
| T4 | Desempate por `@id_atleta` | 2008 Summer / ARG / Gold |
| T5 | Insensibilidad a acentos | 182 → 223 |
| T5b | Lo mismo en `@deporte` (`Glima` → `Glíma`) | Encuentra el deporte |
| T6 | Filtros deporte + país + año | Solo Guy Forget `17` |
| T7 | País por código y por nombre | Ambos funcionan |
| T8 | Dominio de temporada | 5 valores |
| T9 | Sin coincidencias | Aviso, sin error |
| T10 | Filtros sin resultado | Aviso distinguible de T9 |
| T11 | Validación de parámetros | 4 `RAISERROR` |
| T12 | Comodines en los 3 filtros | Nunca devuelve la tabla completa |
| T13 | Tope de `@max_atletas` | Normaliza a 25 / acota a 500 |
| T14 | Atleta sin participaciones | 744 en la base; ficha en 0 |
| T15 | Rendimiento | `DATEDIFF` en ms |
| T16 | Caso 1906 Intercalated Games | `anio 1906` / temporada correcta |
| T17 | Caso Youth (Chad le Clos) | Summer Youth ≠ Summer |
| T18 | NOC histórico (Andrianov) | `URS` / Russian Federation / Soviet Union |
| T19 | Rango de años + medalla | Oros de Phelps 2004–2012 |
| T20 | La corrección en el caso extremo (Ray Ewry) | 20 filas → **10** medallas |
| T21 | **Las nueve regresiones del equipo** | Las nueve exactas |
| T22 | Normalización del `•` en la búsqueda | Cristiano y Messi, un atleta cada uno |
| T23 | Guatemala tras la corrección canónica | 594 / 263 / 20 |
| T24 | Ray Ewry por temporada: 10 de la base vs. 8 del COI | 10 sin filtro, **8** con `Summer` |
| T25 | La corrección de `participaciones` | Bolt **10**, Forget **5**, Ewry **13**, Phelps 30 |
| T26 | Las dos familias de nombre de evento | Bolt 2004 aparece en las dos |
| T27 | La marca `posterior_a_fallecimiento` | Andrianov: 1980 en `0`, kayak 2020 en `1` |

**Las nueve regresiones que exige la revisión del equipo**, verificadas contra la base vigente:

```
Michael Phelps    23/3/2 = 28      Jenny Thompson    8/3/1 = 12
Larysa Latynina    9/5/4 = 18      Paavo Nurmi       9/3/0 = 12
Marit Bjørgen      8/4/3 = 15      Mark Spitz        9/1/1 = 11
Nikolay Andrianov  7/5/3 = 15      Ray Ewry         10/0/0 = 10
                                   Usain Bolt        8/0/0 =  8
```

---

## 7. Evidencia visual

Capturas tomadas en SSMS 21 el **2026-09-15**, contra la base vigente y con la hora del sistema visible en cada una. Están en `evidencia/img/`. Las de las 20:13 en adelante se retomaron después de aplicar la regla por familia de evento (§5.2).

| Captura | Hora | Qué acredita |
|---|---|---|
| `01_creacion_sp.png` | 19:12 | Creación del SP; `Completion time` reportado por el servidor |
| `02_phelps.png` | 20:13 | `30 / 30` y `28 / 28`: el caso que la corrección **no** toca |
| `03_regresiones.png` | 19:14 | Las nueve regresiones del equipo, todas iguales a su valor esperado |
| `04_ray_ewry.png` | 20:13 | Las dos correcciones juntas: `participaciones 13 (origen 23)`, `medallas 10 (origen 20)` |
| `05_busqueda_bullet.png` | 19:16 | Cristiano Ronaldo (`102010`) y Lionel Messi (`110178`): el `•` normalizado |
| `06_guatemala.png` | 19:17 | **594 / 263 / 20**, y los 3 medallistas: Barrondo 2012, Brol y Ruano 2024 |
| `07_ambiguedad.png` | 19:17 | `BUSQUEDA AMBIGUA` con 26 candidatos y `@max_atletas = 5` |
| `08_participaciones.png` | 20:14 | Guy Forget 1992: `participaciones 2 (origen 4)`, con los dos pares en el detalle |
| `09_validaciones.png` | 19:19 | Las 4 validaciones de dominio capturadas por `TRY/CATCH` |
| `10_marca_fallecimiento.png` | 20:18 | `posterior_a_fallecimiento`: el kayak CHN 2020 en `1`, la gimnasia URS 1980 en `0` |

Cuatro valen como prueba más allá del formato:

- **`04_ray_ewry`** es la evidencia central del §5.2. El detalle muestra, lado a lado, `Athletics Men's Standing High Jump` (edad 26, sin posición) y `Standing High Jump, Men (Olympic)` (posición 1, sin edad), ambas `Gold` y del mismo año: el mismo salto contado dos veces. Las dos columnas `filas_origen` dejan ver el 23 y el 20 de origen.
- **`08_participaciones`** prueba que la regla también corrige el conteo de participaciones. Guy Forget jugó **2** eventos en Barcelona 1992 —singles y dobles— y la base tiene **4** filas, cada evento partido en una con posición y otra con edad.
- **`02_phelps`** prueba lo contrario, que es igual de importante: donde no hay duplicación el procedimiento no interviene. Las dos `filas_origen` coinciden con sus totales.
- **`10_marca_fallecimiento`** muestra la fila 25 de 25, un kayak femenino por China en 2020 atribuido a un gimnasta soviético fallecido en 2011, marcada con `1` y con las filas legítimas de 1980 en `0` justo encima. No se filtra: se señala.

La captura `01` incluye el `Completion time` reportado por SQL Server, no solo la hora del sistema operativo.

---

## 8. Cómo ejecutarlo

Desde SSMS, conectando a `localhost,1434` con `sa` y *Trust server certificate* marcado, con `OlimpiadasDB` como base:

```sql
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps';
```

O desde la terminal:

```powershell
docker cp .\storeprocedure_atleta\sp_historial_atleta.sql olimpiadas-sqlserver:/tmp/sp.sql
docker exec olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB -i /tmp/sp.sql
```

> **Nota sobre la carga en Windows.** Los scripts se pasan al contenedor con `docker cp` y se ejecutan con `sqlcmd -i`, no por *pipe* de PowerShell: Windows PowerShell 5.1 inyecta un BOM al canalizar hacia `docker exec` y `sqlcmd` falla con `Incorrect syntax near '﻿'`.
>
> Además, `04_bulk_load_staging.sql` usa `ROWTERMINATOR = '0x0a'`, pero en un checkout de Windows con `core.autocrlf = true` los CSV quedan en CRLF y la carga falla en `disciplina.csv` y `evento.csv`, que son los que tienen campos entrecomillados al final. Para recargar en Windows hay que ejecutar una copia del script con `0x0d0a`, sin modificar el archivo del repositorio.
