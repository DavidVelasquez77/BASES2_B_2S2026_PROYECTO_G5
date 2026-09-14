# Inciso d — Stored procedure por atleta

**Integrante:** Valery Alarcón
**Grupo:** 7 — Sistemas de Bases de Datos 2, 2do. Semestre 2026
**Objeto creado:** `olympics.sp_historial_atleta`
**Base vigente:** 336,418 atletas · 2,986 eventos · 712,658 participaciones · total 1,069,889

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
| `pruebas.sql` | 21 pruebas ejecutables desde SSMS |
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

1. **Ficha del atleta**: datos biográficos, país de nacimiento, y las métricas oficiales `participaciones`, `total_medallas`, `ediciones`, `deportes`, `primer_ano`, `ultimo_ano`.
2. **Medallero**: oro / plata / bronce / total, más el desglose de resultados sin medalla (`DNF`, `DNS`, `DQ`, posiciones sin premio).
3. **Detalle de participaciones**: año, temporada, sede, deporte, disciplina, evento, NOC, país representado, equipo, edad, posición, empate, estado y medalla.

Todas las métricas salen **directamente de `PARTICIPACION`**, que es la fuente canónica. El procedimiento no deduplica ni estima.

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

### 4.4 Se buscan tres columnas de nombre

`nombre` está siempre poblado, pero `nombre_completo` y `nombre_usado` solo en parte de las filas. El SP busca en las tres, lo que aumenta la cobertura.

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

## 5. Calidad de datos: estado y limitaciones conocidas

Durante la construcción del procedimiento se detectaron varios problemas en el dato de origen y se reportaron al equipo. El detalle reproducible está en `evidencia/hallazgos_reportados.md`.

### 5.1 Resueltos en el ETL

| Hallazgo | Estado |
|---|---|
| Dominio de `sexo` sin homologar (`M`/`Male`, `F`/`Female`) | resuelto — solo `Male` y `Female` |
| Separador `•` (U+2022) en `nombre_completo` | resuelto — 0 filas |
| Conteo de medallas de Michael Phelps |  resuelto — `23/3/2 = 28` |

Por eso el procedimiento ya **no normaliza nada en la salida ni estima conteos**. Esa lógica existió mientras el problema estuvo vigente y fue retirada cuando dejó de serlo.

### 5.2 Pendiente: duplicación de medallas fuera de los casos corregidos

La misma medalla sigue registrada dos veces bajo las dos nomenclaturas de evento, con campos complementarios (una fila trae `posicion`, la otra trae `edad`).

```
1900  Standing High Jump, Men (Olympic)      pos=1   edad=-
1900  Athletics Men's Standing High Jump     pos=-   edad=26     <- el mismo salto
```

Consecuencia en los rankings agregados:

| Consulta | Real |
|---|---|
| Michael Phelps 23 oros | 23  |
| Ray Ewry 20 oros | 10  |
| Jenny Thompson 16 oros | 8  |
| Carl Lewis 16 oros | 9  |

**No es corregible desde una consulta.** Las dos filas tienen `id_evento` distinto, así que ningún `DISTINCT` las junta sin colapsar medallas legítimamente diferentes. Se evaluó filtrar por `posicion IS NOT NULL`, que da el número correcto en varios atletas, pero se descartó: perdería 37,721 filas de medalla legítimas en deportes de equipo y relevos, donde la posición nunca se registró.

Corresponde al ETL, y así fue reportado.

### 5.3 Pendiente: participaciones sin medalla duplicadas

El mismo patrón en filas sin medalla infla el conteo de participaciones. Usain Bolt (`104492`) tiene 12 filas para 10 eventos reales; sus 8 medallas sí están limpias.

### 5.4 Pendiente: atletas homónimos sin fusionar

48,370 nombres repetidos. El SP lo maneja con el control de ambigüedad de §4.2, pero el dato de origen sigue fragmentado.

### 5.5 Pendiente: participaciones imposibles atribuidas a un atleta

El problema inverso al anterior: personas distintas fusionadas en un mismo `id_atleta`. Nikolay Andrianov (`31000`), gimnasta soviético fallecido en 2011, tiene 24 participaciones correctas de 1972 a 1980 **más una fila de kayak femenino por China en 2020**. Aristidis Akratopoulos (`173`), tenista de Atenas 1896, tiene una fila de taekwondo por Etiopía en 2020.

Alcance: **786 participaciones posteriores a la fecha de fallecimiento** del atleta (783 atletas), sobre 712,658 filas — un 0.11%. Verificado que es previo a la corrección semántica, no una regresión.

Se detectó al ejecutar la prueba T18: el SP devolvió 24 participaciones para Andrianov filtrando por `@pais = 'URS'`, y no las 25 que tiene la tabla.

> **Qué significa para la salida del SP.** El procedimiento reporta fielmente lo que la base contiene. Los pendientes 5.2 a 5.4 se manifiestan en su salida porque están en el dato, no porque el procedimiento los produzca. Las consultas acotadas a un evento, año o país —y el historial individual con `@id_atleta`— no están afectadas.

---

## 6. Casos de prueba

Ejecutables desde `pruebas.sql`.

| # | Caso | Esperado |
|---|---|---|
| T1 | Phelps, solo medallas | 23 / 3 / 2 = 28 |
| T2 | Phelps sin filtro | 30 participaciones, 5 ediciones |
| T3 | Búsqueda ambigua (`Messi`) | Aviso + 26 candidatos |
| T4 | Desempate por `@id_atleta` | 2008 Summer / ARG / Gold |
| T5 | Insensibilidad a acentos en el nombre | 182 → 223 |
| T5b | Lo mismo en `@deporte` (`Glima` → `Glíma`) | Encuentra el deporte |
| T6 | Filtros deporte + país + año | Solo Guy Forget `17` |
| T7 | País por código y por nombre | Ambos funcionan |
| T8 | Dominio de temporada | 5 valores |
| T9 | Sin coincidencias | Aviso, sin error |
| T10 | Filtros sin resultado | Aviso distinguible de T9 |
| T11 | Validación de parámetros | 4 `RAISERROR` |
| T12 | Comodines en los 3 filtros | Nunca devuelve la tabla completa |
| T13 | Tope de `@max_atletas` | Normaliza a 25 / acota a 500 |
| T14 | Atleta sin participaciones | 247 en la base; ficha en 0 |
| T15 | Rendimiento | `DATEDIFF` en ms |
| T16 | Caso 1906 Intercalated Games | `anio 1906` / temporada correcta |
| T17 | Caso Youth (Chad le Clos) | 8 Summer Youth vs 11 Summer |
| T18 | NOC histórico (Andrianov) | `URS` / Russian Federation / Soviet Union |
| T19 | Rango de años + medalla | 18 oros de Phelps 2004–2012 |
| T20 | Limitación conocida (Ray Ewry) | 20 filas para 10 oros reales |

**Regresiones de la revisión final del equipo**, verificadas contra la base vigente:

```
Michael Phelps  23 / 3 / 2 = 28     Usain Bolt        8
Paavo Nurmi              12         Lionel Messi      Gold Beijing 2008
Mark Spitz               11         Érick Barrondo    Silver London 2012
```

---

## 7. Evidencia visual

Capturas tomadas en SSMS 21 el **2026-09-13 entre 19:24 y 19:35**, contra la base vigente, con la hora del sistema visible en cada una. Están en `evidencia/img/`.

| Captura | Hora | Qué acredita |
|---|---|---|
| `01_creacion_sp.png` | 19:24 | Creación del SP; se ven los parámetros nuevos y el `Completion time` del servidor |
| `02_phelps.png` | 19:25 | Medallero **23 / 3 / 2 = 28**, sin columnas de estimado — la regresión de la revisión final |
| `03_ambiguedad.png` | 19:25 | `BUSQUEDA AMBIGUA` con 26 candidatos ordenados por medallas |
| `04_guatemala.png` | 19:26 | Los 3 medallistas de Guatemala: Barrondo 2012, Brol y Ruano 2024 |
| `05_filtros.png` | 19:26 | Deporte + país + año juntos; formato de empate `=9 lugar` / `=17 lugar` |
| `06_validaciones.png` | 19:27 | Los 4 `RAISERROR`, incluida la validación nueva de `@temporada` |
| `07_noc_historico.png` | 19:34 | `URS` / `Russian Federation` / `Soviet Union`; medallero 7 / 5 / 3 = 15 |
| `08_rango_y_medalla.png` | 19:35 | `@anio_desde` + `@anio_hasta` + `@medalla`: 18 oros entre 2004 y 2012 |

La captura `01` incluye `Completion time: 2026-09-13T19:23:46`, que es la hora reportada por SQL Server y no solo la del sistema operativo.

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
