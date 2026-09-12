# Inciso d - Stored procedure por atleta

**Objeto creado:** `olympics.sp_historial_atleta`

---

## 1. Qué pide el enunciado

> **d)** Realizar un stored procedure que reciba como primer parámetro el nombre del atleta y que despliegue toda la información relacionada con el mismo, participaciones, resultados, medallas, el formato de salida es a su criterio. Pueden agregar parámetros para mostrar o filtrar información específica, por ejemplo, deporte, país y año.

Dos exigencias literales que condicionan el diseño:

1. El **primer parámetro es el nombre**, no un id. El handoff interno del equipo sugería `@id_atleta BIGINT`; se siguió el enunciado.
2. El formato de salida es libre, y los filtros por **deporte, país y año** están explícitamente habilitados.

---

## 2. Archivos de esta carpeta

| Archivo | Contenido |
|---|---|
| `sp_historial_atleta.sql` | El stored procedure (`CREATE OR ALTER`) |
| `pruebas.sql` | 23 pruebas ejecutables desde SSMS |
| `documentacion_d.md` | Este documento |
| `evidencia/prompts.md` | Evidencia de prompt engineering |
| `evidencia/hallazgos_reportados.md` | Hallazgos de calidad de datos reportados al equipo |
| `evidencia/img/` | Capturas con fecha y hora visibles |

Nada fuera de esta carpeta fue modificado. El procedimiento **no altera el modelo físico** entregado en el inciso c y **no escribe datos**: es de solo lectura y consulta únicamente el schema `olympics`, nunca `stg`.

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
     @temporada           = NULL,     -- ver dominio real abajo
     @solo_medallistas    = 0,        -- 1 = solo filas con medalla
     @coincidencia_exacta = 0,        -- 1 = nombre exacto
     @id_atleta           = NULL,     -- desempate directo
     @max_atletas         = 25;       -- tope antes de declarar ambigüedad
```

### Salida - tres result sets

1. **Ficha del atleta**: datos biográficos, país de nacimiento, y las cantidades en **dos versiones** - `participaciones` / `total_medallas` crudas y `participaciones_estimado` / `total_medallas_estimado` descontando la duplicación entre fuentes (ver §5.1). `ediciones` y `deportes` no necesitan corrección porque usan `COUNT(DISTINCT)`.
2. **Medallero**: oro / plata / bronce / total, también en crudo y estimado, más una columna `diagnostico` y el desglose de `DNF`, `DNS`, `DQ`.
3. **Detalle de participaciones**: año, temporada, sede, deporte, disciplina, evento, NOC, país, equipo, edad, posición, empate, estado y medalla. **Este result set es fiel al dato y sí muestra las filas duplicadas**, porque fusionarlas requeriría resolver la identidad de los eventos (ver §5.1).

Cuando la búsqueda es ambigua o no da resultados, devuelve **un solo result set informativo** en lugar de los tres, para que el caso se distinga de una respuesta vacía.

---

## 4. Decisiones de diseño

### 4.1 Búsqueda insensible a acentos

La base tiene colación `SQL_Latin1_General_CP1_CI_AS`: ignora mayúsculas pero **distingue acentos**. Buscar `Elie` no encontraría a `Élie, Comte de Lastours`.

El procedimiento fuerza `Latin1_General_CI_AI` solo en la comparación. Medición sobre esta base:

| Colación | Atletas que coinciden con `%Elie%` |
|---|---:|
| `CI_AS` (la de la base) | 182 |
| `CI_AI` (la del SP) | **223** |

Se recuperan 41 atletas que de otro modo quedaban invisibles.

### 4.2 Control de ambigüedad

Buscar por nombre es ambiguo por naturaleza: **49,869 nombres se repiten** entre atletas distintos (`John Jr.` aparece 76 veces). Buscar `Messi` devuelve 26 atletas.

Si la búsqueda supera `@max_atletas`, el SP devuelve la **lista de candidatos** ordenada por medallas y participaciones, en vez de volcar miles de filas. El usuario refina con `@id_atleta`.

### 4.3 El filtro de país va por NOC

`PARTICIPACION.id_pais_nacionalidad` está en **NULL en 733,333 de 733,414 filas** (99.99%). Como filtro sería inservible. El país se resuelve por el **NOC representado**, aceptando tres formas: código (`FRA`), nombre del NOC (`France`) o nombre de la entidad geográfica.

El detalle expone los tres conceptos por separado, que es la distinción que el modelo exige no confundir. Ejemplo real (prueba T20, Nikolay Andrianov):

```
codigo_noc        = URS                  <- comité olímpico histórico
pais_representado = Russian Federation   <- entidad geográfica actual
equipo            = Soviet Union         <- nombre del equipo de la época
```

Y varios NOC históricos conviven apuntando a la misma entidad: `FRG`, `GDR` y `GER` → Germany; `URS` y `EUN` → Russian Federation.

### 4.4 Se buscan tres columnas de nombre

`nombre` está siempre poblado (336,419), pero `nombre_completo` y `nombre_usado` solo en 145,500 filas (43%). El SP busca en las tres, lo que aumenta la cobertura.

### 4.5 Comodines neutralizados

Si el usuario escribe `%`, se busca literalmente y no devuelve la tabla completa. Los caracteres `%`, `_` y `[` se escapan antes de armar el patrón.

### 4.6 No se agregó ningún índice

La búsqueda por nombre hace scan de `ATLETA` (336,419 filas) porque no hay índice por nombre y el `COLLATE` impediría usarlo.

Agregar un índice por `nombre` habría mejorado esa búsqueda, pero implica alterar el modelo físico entregado en el inciso c, y el handoff del equipo indica que la base debe soportar los procedimientos **sin modificar el modelo**. Se optó por no tocarlo.

**Medición real: 51 ms** para el procedimiento completo (búsqueda + los tres result sets), obtenidos con:

```sql
DECLARE @t0 DATETIME2(7) = SYSDATETIME();
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
SELECT DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS ms_total;
```

Medido con la tabla ya en caché (*buffer pool* caliente), así que en frío puede ser mayor. A 51 ms no se justifica alterar el modelo físico por rendimiento.

### 4.7 Rango de años y tipo de medalla

Además del `@anio` exacto, el procedimiento acepta `@anio_desde` / `@anio_hasta` (rango inclusivo) y `@medalla`. Responden en una sola llamada el tipo de pregunta que puede surgir en la defensa - *"sus medallas de oro entre 2004 y 2012"* - sin escribir SQL en el momento.

Ambos se validan: un `@medalla` fuera del dominio `Gold` / `Silver` / `Bronze`, o un rango invertido, lanzan `RAISERROR` con un mensaje claro en vez de devolver un resultado vacío que parecería *"este atleta no tiene medallas"*.

### 4.8 Dominio real de `temporada`

Tiene **cinco** valores, no dos:

| Temporada | Ediciones | Rango |
|---|---:|---|
| Summer | 30 | 1896–2024 |
| Winter | 24 | 1924–2022 |
| Summer Youth | 3 | 2010–2018 |
| Winter Youth | 3 | 2012–2020 |
| Intercalated Games | 1 | 1906 |

`@temporada = 'Summer'` **no** incluye `Summer Youth`: el filtro es de igualdad exacta. La prueba T19 lo demuestra con Chad le Clos, que compitió en ambas.

---

## 5. Hallazgos de calidad de datos

Estos problemas están en la base entregada, **no los introduce este procedimiento**. Se documentan porque afectan la interpretación de la salida.

### 5.1 Duplicidad de eventos entre fuentes (el más importante)

La misma participación quedó registrada bajo dos nomenclaturas distintas, con campos complementarios:

```
100 metres Butterfly, Men (Olympic)     posición=1     edad=NULL    Gold
Swimming Men's 100 metres Butterfly     posición=NULL  edad=19.00   Gold
```

**Consecuencia directa:** el conteo crudo de Michael Phelps en la base es de **56 medallas** (46 oro, 6 plata, 4 bronce). La cifra real es **28** (23 oro, 3 plata, 2 bronce), verificable en olympics.com. El conteo está exactamente duplicado.

Alcance medido sobre los 64,842 medallistas:

| Caso | Atletas |
|---|---:|
| Conteo exactamente duplicado | 15,766 |
| Solo nomenclatura de una fuente | 19,441 |
| Solo nomenclatura de la otra | 28,741 |
| Mezcla desigual | 894 |

O sea, afecta a **~24% de los medallistas**: justo donde las fuentes se traslapan.

#### Cómo lo trata el procedimiento

El SP **no unifica eventos** - eso es trabajo de consolidación (Bloque 4) - pero sí **cuenta bien las medallas**, y muestra ambas cifras lado a lado.

El duplicado tiene una firma estructural aprovechable: las filas de una nomenclatura traen `posicion` y las de la otra traen `edad`, de forma complementaria. Dentro de un grupo (atleta, año, disciplina, medalla), si hay *n* filas con `posicion` y *n* con `edad`, el conteo real es *n*.

Lo que hace viable el método es que permite **contar** sin resolver **qué** evento es el duplicado de cuál: no importa el emparejamiento individual, solo cuántos pares hay.

Cobertura medida sobre los 78,998 grupos con medalla:

| Caso | Grupos | % |
|---|---:|---:|
| Firma de duplicado limpia (*n* y *n*) | 27,416 | 34.70% |
| Una sola nomenclatura, sin duplicar | 23,632 | 29.91% |
| Grupo de una sola fila | 27,799 | 35.19% |
| Indeterminado | 151 | 0.19% |
| **Determinable** | **78,847** | **99.81%** |

Reproducible con la prueba T16 de `pruebas.sql`.

De los 27,416 con firma limpia, **21,791** tienen partición exacta y **5,625** tienen alguna fila con `posicion` *y* `edad` a la vez. Ese segundo caso también cuenta bien: si `a` filas traen ambos campos, `b` solo posición y `b` solo edad, entonces `con_posicion = a+b` y el conteo real es `a+b` - las `a` son registros ya completos y las `2b` restantes forman `b` pares.

El único caso que podría **subcontar** sería un grupo con firma limpia que además tuviera filas sin `posicion` ni `edad`. Verificado contra la base con la prueba **T17**: **0 grupos.**

La corrección se aplica a **las dos cantidades**: medallas y participaciones. Salida real para Phelps:

```
FICHA
  participaciones  60  ->  participaciones_estimado  30
  total_medallas   56  ->  total_medallas_estimado   28

MEDALLERO
  oro 46  plata 6  bronce 4  total 56
  oro_estimado 23  plata_estimado 3  bronce_estimado 2  total_estimado 28
  diagnostico: duplicado detectado y descontado
```

Las **28 medallas** coinciden con la cifra real en los tres desgloses, no solo en el total. Las **30 participaciones** corresponden a sus eventos reales: 1 en Sídney 2000 + 8 + 8 + 7 + 6.

#### Validación en tres atletas independientes

Para descartar que el caso Phelps fuera casualidad, el método se verificó contra atletas de épocas, deportes y países distintos. **Acierta los tres desgloses en los tres casos:**

| Atleta | Época | Deporte | NOC | Crudo | Estimado | Medallas reales |
|---|---|---|---|---|---|---|
| Michael Phelps (`93113`) | 2000–2016 | Natación | USA | 46/6/4 = 56 | **23/3/2 = 28** | 23 oro, 3 plata, 2 bronce |
| Chad le Clos (`119877`) | 2012–2016 | Natación | RSA | 2/6/0 = 8 | **1/3/0 = 4** | 1 oro, 3 plata |
| Nikolay Andrianov (`31000`) | 1972–1980 | Gimnasia | URS | 14/10/6 = 30 | **7/5/3 = 15** | 7 oro, 5 plata, 3 bronce |

Una cuarta comprobación sale de la prueba T21: filtrando los oros de Phelps entre 2004 y 2012, el estimado da **18**, que es exactamente 6 (Atenas) + 8 (Beijing) + 4 (Londres). Sumados los 5 de Río, 23 - su total de carrera.

El caso de Chad le Clos aporta además el contraste: con `@temporada = 'Summer Youth'` el estimado es igual al crudo (`1/3/1 = 5`) y el diagnóstico dice `sin duplicados detectados`, porque los Juegos de la Juventud provienen de una sola fuente. **El método distingue el caso con duplicación del caso sin ella**, en lugar de dividir todo entre dos.

El método no recibe ninguna información externa: solo cuenta pares de `posicion`/`edad`.

La firma aplica igual a las filas **sin medalla**. Caso real de Phelps en Sídney 2000:

```
200 metres Butterfly, Men (Olympic)   posición=5     edad=NULL
Swimming Men's 200 metres Butterfly   posición=NULL  edad=15.00
```

Un solo evento real registrado dos veces. Estimado del grupo: 1.

Tres garantías del diseño:

1. **El conteo crudo nunca se altera.** Se muestra siempre, junto al estimado.
2. **Donde la firma no concluye se reporta el crudo** y se avisa en `diagnostico`. Nunca subcuenta en silencio.
3. **No se modifica ningún dato.** Es aritmética sobre el resultado, no una escritura.

#### Lo que este método NO resuelve

| Se puede | No se puede |
|---|---|
| Contar cuántas medallas y participaciones reales tiene un atleta | Decir qué evento es el duplicado de cuál |
| Mostrar crudo y estimado lado a lado | Fusionar las filas del result set 3 |

El **detalle de participaciones sigue mostrando las filas duplicadas**, porque fusionarlas requeriría resolver la identidad de los eventos. Dos caminos para eso fueron evaluados y descartados con medición; están documentados en `evidencia/prompts.md` §3.6.

### 5.2 Atletas duplicados

`Guy Forget` existe como **cuatro** `id_atleta` distintos: `17` (con biografía completa, 9 participaciones) y `223817`, `223818`, `223819` (sin datos, una participación cada uno).

El caso más extremo encontrado es `Eric Lemming`, con **diez** `id_atleta`: el `75674` (biografía completa, 23 participaciones, 8 medallas) más `257132`–`257140`, todos vacíos y con una participación cada uno.

Por eso el result set 3 incluye la columna `id_atleta`: sin ella, las filas de atletas homónimos distintos parecen duplicados de evento. Con 49,869 nombres repetidos en la base, esa columna no es opcional.

Como contrapeso, la deduplicación biográfica sí funcionó bien en general: solo **1 grupo** de homónimos comparte fecha de nacimiento.

### 5.3 Dominio de `sexo` sin homologar

| Valor | Atletas |
|---|---:|
| `M` | 135,640 |
| `Male` | 106,325 |
| `F` | 55,279 |
| `Female` | 39,175 |

El mismo concepto en dos codificaciones. **Cualquier consulta por sexo debe usar `IN ('F','Female')`** o pierde la mitad de los registros.

El SP **normaliza esto solo en la salida** (`M`→`Male`, `F`→`Female`) y conserva el valor crudo en la columna `sexo_original`. No modifica la tabla.

### 5.4 Separador residual en `nombre_completo`

**145,252 filas** contienen el carácter `•` (U+2022) como separador: `Lionel Andrés•Messi Cuccittini`. El SP lo sustituye por un espacio **solo al mostrar**; el dato original queda intacto.

---

## 6. Casos de prueba verificados

Todas ejecutadas el 2026-09-11 contra la base cargada (1,090,667 filas, `RESULTADO_GLOBAL = PASS`).

| # | Caso | Resultado |
|---|---|---|
| T1 | Nombre exacto + solo medallas (Phelps) | 3 result sets; medallas 56 → 28  |
| T1b | El mismo sin filtro, para ver `participaciones` | 60 → 30 y 56 → 28  |
| T2 | Búsqueda ambigua (`Messi`, 26 atletas) | Aviso + candidatos  |
| T3 | Desempate por `@id_atleta` (Messi, 110178) | 2008 Summer / ARG / Gold  |
| T4 | Insensibilidad a acentos | 182 → 223  |
| T5 | Filtros deporte + país + año | Filtra correctamente  |
| T6 | País por código y por nombre | Ambos funcionan  |
| T7 | Filtro por temporada |  |
| T8 | Sin coincidencias | Aviso, sin error  |
| T9 | Filtros sin resultado | Aviso distinguible de T8  |
| T10 | Parámetro vacío | `RAISERROR`  |
| T11 | Comodín `%` neutralizado | Sin coincidencias  |
| T12 | Atleta sin participaciones (241 en la base) | Ficha en 0, sin error  |
| T13 | Rendimiento | 51 ms (caché caliente)  |
| T14 | Evidencia de duplicidad de eventos | Reproducible  |
| T15 | Firma de duplicado grupo por grupo (Phelps) | `con_posicion = con_edad` en todos; total 28  |
| T16 | Cobertura global del método de estimación | 99.81% determinable  |
| T17 | Solidez del método: los tres subcasos | 21,791 / 5,625 / **0**  |
| T18 | Caso 1906 Intercalated Games (Eric Lemming) | `anio 1906` / `Intercalated Games`  |
| T19 | Caso Youth (Chad le Clos, Youth vs Summer) | conjuntos distintos; Youth sin duplicados  |
| T20 | NOC histórico (Andrianov, `URS` → Russian Federation) | 3 conceptos separados  |
| T21 | Rango de años + tipo de medalla | solo Gold, 2004–2012; 36 → **18**  |
| T22 | Validación de los parámetros nuevos | dos `RAISERROR` con mensaje claro  |

> **Procedencia de las cifras.** Todos los números de este documento provienen de consultas ejecutadas contra `OlimpiadasDB`, salvo tres excepciones que se declaran explícitamente:
>
> 1. Las **medallas reales** usadas para validar el método -Phelps 23/3/2, Chad le Clos 1/3/0, Andrianov 7/5/3- son datos **externos**, verificables en olympics.com, el sitio que el enunciado señala para revisión de calidad. No salen de esta base: son el contraste independiente contra el que se comprobó el estimado.
> 2. Las estadísticas de normalización de nombres de evento de `prompts.md` §3.6 (3,007 eventos, 495 pares limpios) se midieron sobre los CSV de `data/processed`, cuyo SHA-256 coincide 10/10 con lo cargado. Sustentan una alternativa **descartada**, no el método en uso. El desglose **21,791 / 5,625 / 0** de §5.1 sí está verificado contra el motor con la prueba **T17**.
> 3. El tiempo de §4.6 (**51 ms**) se midió con `DATEDIFF` sobre `SYSDATETIME()`, con la tabla en caché.

**Validación contra el caso conocido del equipo:** Lionel Messi (`110178`) - identidad canónica, nacimiento 1987-06-24, una participación exacta en 2008 Summer, ARG, Argentina, posición 1, Gold. Coincide con lo documentado en `post_block4_final_validation.md`.

---

## 7. Evidencia visual

Capturas tomadas en SSMS 21 en una sola sesión, entre el **2026-09-11 23:24** y el **2026-09-12 01:27**, con la hora del sistema visible en cada una. Están en `evidencia/img/`.

| Captura | Hora | Qué acredita |
|---|---|---|
| `00_sp_arbol.png` | 23:24 | El SP existe en `Programmability → Stored Procedures` |
| `01_creacion_sp.png` | 23:44 | Creación exitosa + `Completion time` del servidor + las 20 tablas |
| `02_prueba_messi.png` | 23:48 | Los tres result sets; valida el caso Messi del equipo |
| `03_prueba_ambiguedad.png` | 23:53 | `BUSQUEDA AMBIGUA` con 26 candidatos ordenados |
| `04_prueba_filtros.png` | 23:54 | Deporte + país + año juntos; formato de empate `=9` / `=17` |
| `05_duplicidad_eventos.png` | 23:55 | Las cuatro filas que evidencian el hallazgo de §5.1 |
| `06_medallero_estimado.png` | 01:25 | Las cuatro cantidades: `60 → 30` y `56 → 28`, más `id_atleta` en el detalle |
| `07_noc_historico.png` | 01:26 | `URS` / `Russian Federation` / `Soviet Union`; estimado `7/5/3 = 15` |
| `08_rango_y_medalla.png` | 01:27 | `@anio_desde` + `@anio_hasta` + `@medalla`; `36 → 18` |

La captura `01` incluye `Completion time: 2026-09-11T23:44:09.4289424-06:00`, que es la hora reportada por SQL Server y no solo la del sistema operativo.

---

## 8. Cómo ejecutarlo

```powershell
# 1. Crear el procedimiento
docker cp sp_historial_atleta.sql olimpiadas-sqlserver:/tmp/
docker exec olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB `
  -i /tmp/sp_historial_atleta.sql
```

Desde SSMS (`localhost,1434`, usuario `sa`, *Trust server certificate*):

```sql
USE OlimpiadasDB;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps';
```
