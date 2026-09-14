# Hallazgos de calidad de datos reportados al equipo

Revisión hecha sobre la base vigente después de la corrección semántica y la deduplicación de medallas (`336,418` atletas, `2,986` eventos, `712,658` participaciones, total `1,069,889`).

Todos los hallazgos son reproducibles con las consultas incluidas.

---

## Lo que quedó resuelto

Confirmado contra los datos nuevos:

| Hallazgo anterior | Estado |
|---|---|
| Dominio de `sexo` sin homologar (`M`/`Male`, `F`/`Female`) |  resuelto — solo `Male` (241,964) y `Female` (94,454) |
| Separador `•` (U+2022) en `nombre_completo` |  resuelto — 0 filas |
| Conteo de medallas de Michael Phelps |  resuelto — `23/3/2 = 28` leyendo `PARTICIPACION` directamente |
| Medallero de Guatemala |  correcto — `1/1/1 = 3` (Barrondo 2012, Ruano 2024, Brol 2024) |

Con eso, el procedimiento del inciso d ya no necesita normalizar nada en la salida ni estimar conteos. Esa lógica fue retirada.

---

## 1. La duplicación de medallas persiste fuera de los casos corregidos — impacto alto

El caso Phelps quedó bien, pero el patrón original sigue presente en el resto del dataset: la misma medalla registrada dos veces bajo las dos nomenclaturas de evento, con campos complementarios (una fila trae `posicion`, la otra trae `edad`).

```sql
SELECT eo.anio, e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
WHERE a.nombre = N'Ray Ewry' AND p.medalla = N'Gold'
ORDER BY eo.anio, e.nombre;
```

Devuelve **20 filas de oro** para sus **10 oros reales**:

```
1900  Standing High Jump, Men (Olympic)      pos=1   edad=-
1900  Athletics Men's Standing High Jump     pos=-   edad=26     <- el mismo salto
1900  Standing Long Jump, Men (Olympic)      pos=1   edad=-
1900  Athletics Men's Standing Long Jump     pos=-   edad=26     <- el mismo salto
...
```

Jenny Thompson presenta lo mismo: **16 filas de oro** para **8 oros reales**.

### Impacto directo en las consultas de la defensa

Una de las consultas pedidas es *"quién es el atleta con más medallas de oro"*:

```sql
SELECT TOP 5 a.nombre, COUNT(*) AS oros
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
WHERE p.medalla = N'Gold'
GROUP BY a.id_atleta, a.nombre
ORDER BY oros DESC;
```

| Resultado actual | Real |
|---|---|
| Michael Phelps 23 | 23 correcto |
| Ray Ewry 20 | 10 incorrecto |
| Birgit Fischer 16 | 8  incorrecto|
| Jenny Thompson 16 | 8 incorrecto |
| Carl Lewis 16 | 9 incorrecto |

El top queda mal desde el segundo puesto.

### Alcance aproximado

```sql
WITH g AS (
  SELECT p.id_atleta, eo.anio, p.medalla,
         SUM(CASE WHEN e.nombre LIKE '%(Olympic%' OR e.nombre LIKE '%(Intercalated%'
                  THEN 1 ELSE 0 END) AS estilo_a,
         SUM(CASE WHEN e.nombre NOT LIKE '%(Olympic%' AND e.nombre NOT LIKE '%(Intercalated%'
                  THEN 1 ELSE 0 END) AS estilo_b
  FROM olympics.PARTICIPACION p
  JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
  JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
  WHERE p.medalla IS NOT NULL
  GROUP BY p.id_atleta, eo.anio, p.medalla)
SELECT COUNT(*) AS grupos, COUNT(DISTINCT id_atleta) AS atletas
FROM g WHERE estilo_a > 0 AND estilo_b > 0;
```

```
grupos (atleta, año, medalla) con ambas nomenclaturas:  19,690
atletas afectados:                                      14,963
filas de medalla implicadas:                            41,911
```

> **Precisión:** los casos de Ray Ewry y Jenny Thompson están confirmados fila por fila. Las cifras agregadas usan el sufijo `(Olympic` / `(Intercalated` para distinguir nomenclaturas, criterio que **no es un clasificador confiable** (hay nombres de evento que no encajan en ningún patrón). Tómense como orden de magnitud, no como conteo exacto.

**No se puede corregir desde una consulta.** Las dos filas tienen `id_evento` distinto, así que no hay `DISTINCT` que las junte sin colapsar medallas legítimamente diferentes. Corresponde al ETL.

---

## 2. Las participaciones sin medalla también siguen duplicadas

El mismo patrón aparece en filas sin medalla, y por eso el conteo de participaciones queda inflado.

```sql
SELECT eo.anio, e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
WHERE p.id_atleta = 104492      -- Usain Bolt canónico
ORDER BY eo.anio, e.nombre;
```

Devuelve **12 filas** para sus **10 eventos reales**:

```
2004  200 metres, Men (Olympic)               pos=5   edad=-
2004  Athletics Men's 200 metres              pos=-   edad=17    <- la misma carrera
2008  4 x 100 metres Relay, Men (Olympic)     pos=-   edad=-
2008  Athletics Men's 4 x 100 metres Relay    pos=-   edad=21    <- la misma carrera
```

Sus 8 medallas sí están limpias, una fila cada una. Las dos duplicadas son las que no tienen medalla.

Nota aparte: el relevo 4×100 de 2008 aparece **sin medalla**, lo cual es correcto — ese oro fue retirado en 2017 por el dopaje de Nesta Carter. El dato refleja el registro oficial vigente.

---

## 3. Atletas homónimos sin fusionar

```sql
SELECT a.id_atleta, a.nombre, a.fecha_nacimiento,
       (SELECT COUNT(*) FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta) AS participaciones
FROM olympics.ATLETA a WHERE a.nombre = N'Usain Bolt' ORDER BY a.id_atleta;
```

`Usain Bolt` existe como **10 `id_atleta`**: el `104492` con biografía completa y 8 medallas, más nueve registros vacíos con una participación cada uno. `Paavo Nurmi` tiene 12, `Guy Forget` 4, `Eric Lemming` 23.

En total hay **48,370 nombres repetidos** entre atletas distintos.

Esto convierte cualquier búsqueda por nombre en ambigua, que es exactamente el escenario de la defensa. El `sp_historial_atleta` lo maneja devolviendo la lista de candidatos ordenada y permitiendo desempatar con `@id_atleta`, tal como quedó aprobado en la revisión — pero el dato de origen sigue fragmentado.

---

## 4. Participaciones imposibles atribuidas a un atleta — problema inverso al 3

Los hallazgos 3 y 4 son las dos caras del mismo error de *matching*: en el 3 una persona quedó partida en varios `id_atleta`; en el 4 **personas distintas quedaron fusionadas en un mismo id**.

Se detectó al filtrar a Nikolay Andrianov por su NOC: el SP devolvió 24 participaciones y no 25.

```sql
SELECT eo.anio, n.codigo_noc, e.nombre AS evento
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
LEFT JOIN olympics.NOC n          ON n.id_noc      = p.id_noc
WHERE p.id_atleta = 31000
ORDER BY eo.anio;
```

```
1972-1980   URS   24 filas de gimnasia artistica   <- correctas
2020        CHN   Women's Kayak                    <- imposible
```

Andrianov fue un gimnasta soviético que compitió de 1972 a 1980 y **murió en 2011** — la propia ficha lo muestra (`fecha_fallecimiento = 2011-03-21`). No puede tener una participación en kayak femenino por China en 2020.

Otro caso, más extremo:

```
173  Aristidis Akratopoulos   (tenista griego, Atenas 1896)
       1896   GRE   Singles, Men (Olympic)
       1896   GRE   Doubles, Men (Olympic)
       2020   ETH   Men -58kg               <- taekwondo por Etiopia, 124 anos despues
```

### Alcance

```sql
-- participaciones posteriores a la fecha de fallecimiento del atleta
SELECT COUNT(*) AS filas, COUNT(DISTINCT a.id_atleta) AS atletas
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE a.fecha_fallecimiento IS NOT NULL
  AND eo.anio > YEAR(a.fecha_fallecimiento);
```

| Indicador | Cantidad |
|---|---:|
| Participaciones posteriores al fallecimiento | **786** (783 atletas) |
| Atletas con carrera de más de 44 años | **4,976** |

El primer indicador es objetivo: compara contra `fecha_fallecimiento`, que está en la propia tabla. El segundo usa un umbral arbitrario de 44 años y sirve solo para dimensionar.

Entre las filas atípicas, **2020 es el año más frecuente** (1,210 de 4,911, el 25%), pero el problema cruza muchas décadas: también aparecen 1972, 1968, 1960 y 1952 con varios cientos cada una. No es exclusivamente la fuente más reciente mal integrada.

### No es una regresión

Se comparó contra el dataset anterior (commit `efdc312`) para descartar que lo hubiera introducido la corrección semántica:

```
ANTES:   786 post-mortem,   4,983 carreras de mas de 44 anos
AHORA:   786 post-mortem,   4,976 carreras de mas de 44 anos
```

El problema es previo y la corrección semántica incluso redujo levemente el segundo indicador. Viene del *matching* de atletas del Bloque 4.

Son 786 filas de 712,658 (0.11%), así que el impacto es acotado — pero es visible en consultas individuales, que es justo lo que se hace en la defensa.

---

## Qué hace el procedimiento del inciso d frente a esto

Siguiendo la indicación de la revisión final (*"los Stored Procedures no deben volver a deduplicar"*):

- Las métricas salen **directamente de `PARTICIPACION`**, sin heurísticas ni conteos paralelos.
- Se retiraron `#grupos`, `#est`, todas las columnas `*_estimado` y la columna `diagnostico`.
- El detalle de participaciones es fiel: no agrupa ni descarta filas.
- La ambigüedad por homónimos se resuelve con `@max_atletas`, `@coincidencia_exacta` y `@id_atleta`.

Es decir: el SP reporta fielmente lo que la base contiene. Los cuatro hallazgos se manifiestan en su salida porque están en el dato, no porque el procedimiento los produzca.

---

## Sugerencia de prioridad

Quedan seis días para la entrega. El hallazgo **1** es el único que cambia lo que el ingeniero vería en una consulta en vivo.

Y la parte difícil ya está hecha: los candidatos están identificados y los scripts existen.

| Artefacto | Filas |
|---|---:|
| `medal_confirmed_duplicate_map.csv` — pares **aplicados** | 1,015 |
| `medal_semantic_duplicate_candidates.csv` — candidatos identificados | 27,308 |
| `semantic_duplicate_candidates.csv` — candidatos identificados | 49,741 |

Contra las ~41,911 filas de medalla todavía implicadas (unos ~21,000 pares), lo aplicado cubre alrededor del **5%**. Ampliar el mapa de confirmados usando la lista de candidatos que ya existe, con `22_final_medal_dedup_preview_apply.py`, resolvería el top de medallistas.

Los hallazgos **2**, **3** y **4** tienen menor impacto y pueden quedar documentados como limitación conocida si no da el tiempo.

El **4** es el más barato de los tres: la consulta que lo detecta ya está escrita y las 786 filas posteriores al fallecimiento son identificables sin ambigüedad, porque se comparan contra un dato que está en la propia tabla `ATLETA`. Si se decide limpiarlas, no hace falta criterio humano para elegir cuáles.

Resumen de los cuatro:

| # | Hallazgo | Impacto en la defensa | Corregible |
|---|---|---|---|
| 1 | Duplicación de medallas | **Alto** — rompe el top de medallistas | Sí, ampliando el mapa existente |
| 2 | Participaciones sin medalla duplicadas | Medio — infla `participaciones` | Mismo mecanismo que el 1 |
| 3 | Atletas homónimos sin fusionar | Medio — lo absorbe el control de ambigüedad | Requiere criterio caso por caso |
| 4 | Participaciones imposibles | Bajo — 0.11% de las filas | Sí, identificables sin ambigüedad |

---

## Detalle de entorno (no es de datos)

`04_bulk_load_staging.sql` usa `ROWTERMINATOR = '0x0a'` para los diez CSV. En un checkout de Windows con `core.autocrlf = true` los archivos quedan en CRLF, y la carga falla en `disciplina.csv` (21 filas) y `evento.csv` (1,974 filas), que son los que tienen campos entrecomillados al final.

Un `.gitattributes` que fije los finales de línea de `*.csv` haría el script determinista en cualquier máquina:

```
*.csv -text
```
