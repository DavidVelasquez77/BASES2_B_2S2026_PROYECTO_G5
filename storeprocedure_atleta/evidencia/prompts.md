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
-- 733,333 de 733,414 en NULL
```

**Decisión:** resolver el país por NOC representado.

### 3.4 `temporada` tiene cinco valores, no dos

Se iba a validar el parámetro contra `Summer`/`Winter`. La consulta mostró también `Summer Youth`, `Winter Youth` e `Intercalated Games`.

**Decisión:** no validar el dominio; filtrar por igualdad y documentar los cinco valores. Una validación restrictiva habría rechazado consultas legítimas.

### 3.5 No inventar una clasificación por fuente

Al detectar la duplicidad de eventos se evaluó etiquetar cada fila según su fuente usando el sufijo `(Olympic`. La muestra mostró que el criterio falla: `Singles, Men (Intercalated)` es estilo fuente 1 y no lleva ese sufijo.

**Decisión:** descartar la columna. Una heurística que clasifica mal es peor que no clasificar.

### 3.6 Deduplicación de medallas: dos intentos descartados y uno medido

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

El procedimiento se ejecutó contra las **23 pruebas** de `pruebas.sql`, todas contra la base cargada. Los resultados están en la sección 6 de `documentacion_d.md`.

(Son 23 aunque la última etiqueta sea `T22`: existe un `T1b`, agregado para verificar la corrección de `participaciones` descrita en §3.8.)

Ninguna afirmación de la documentación se escribió sin ejecutar antes la consulta que la respalda.
