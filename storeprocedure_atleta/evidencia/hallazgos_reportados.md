# Hallazgos de calidad de datos reportados al equipo

Revisión sobre la base vigente tras la corrección canónica de identidades guatemaltecas: **336,418 atletas · 2,986 eventos · 712,020 participaciones · total 1,069,251**.

Todos los hallazgos son reproducibles con las consultas incluidas.

---

## Lo que quedó resuelto

| Hallazgo anterior | Estado |
|---|---|
| Dominio de `sexo` sin homologar | resuelto — solo `Male` y `Female` |
| Separador `•` en `nombre_completo` | resuelto **en esa columna** — ver hallazgo 5 |
| Identidades guatemaltecas duplicadas | resuelto — 1,232 → **594** participaciones, 802 → **263** atletas |
| Duplicación de medallas en 1,015 pares confirmados | resuelto — Nurmi, Spitz y Bolt quedaron correctos |
| Cristiano Ronaldo ausente del dataset | resuelto — id `102010`, 2004 Summer POR, posición 14 |

Las nueve regresiones de la revisión final pasan contra el dato vigente.

---

## 1. La duplicación de medallas persiste fuera de los 1,015 pares corregidos

El patrón original sigue presente en el resto del dataset:

```sql
SELECT eo.anio, e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
WHERE p.id_atleta = 77795 AND p.medalla = N'Gold'   -- Ray Ewry
ORDER BY eo.anio, e.nombre;
```

Devuelve **20 filas de oro** para sus **10 oros reales**:

```
1900  Standing High Jump, Men (Olympic)      pos=1   edad=-
1900  Athletics Men's Standing High Jump     pos=-   edad=26     <- el mismo salto
```

Jenny Thompson: **24 filas** para **12 medallas** reales.

### Qué se hizo

Por indicación del equipo, **el `sp_historial_atleta` ahora corrige este conteo**.

La clave está en que los nombres de `EVENTO` vienen en dos familias, y son dos orígenes que se fusionaron al construir la base:

| Familia | Forma | Ejemplo | Trae |
|---|---|---|---|
| canónica | con calificador entre paréntesis | `200 metres, Men (Olympic)` | `posicion`, `nombre_competencia` |
| descriptiva | sin paréntesis | `Athletics Men's 200 metres` | `edad`, `equipo` |

**La regla:** dentro de un grupo `(atleta, edición, disciplina, medalla)` se cuentan las filas de la familia canónica; si el grupo solo tiene descriptivas, se cuentan esas. Cuando la descriptiva aporta más eventos que la canónica el grupo se marca en `grupos_indeterminados`, porque ahí puede haber uno legítimo.

`medalla` forma parte de la clave, así que no se colapsan medallas legítimamente distintas. La columna `filas_origen` deja el conteo auditable: si es mayor que el total, ese atleta tenía duplicados.

Validado contra las nueve regresiones del equipo: las nueve dan exacto, y los siete que el ETL ya había corregido quedan con `filas_origen = total`, o sea que **el procedimiento no los toca**. La tabla completa está en `documentacion_d.md` §5.2.

Impacto global: 103,223 filas de medalla → **82,698 reales** (−19.9%), con 14 grupos indeterminados de 78,975.

> **Para el ETL:** la corrección en el SP resuelve la salida, pero el dato de origen sigue duplicado. Cualquier otra consulta que cuente medallas directamente sobre `PARTICIPACION` seguirá dando cifras infladas.

---

## 2. Las participaciones también estaban duplicadas — corregido en el SP

El mismo patrón en filas sin medalla inflaba el conteo de participaciones. El caso más limpio es Guy Forget (`17`) en Barcelona 1992:

```
Doubles, Men (Olympic)    posicion  9    edad  -
Tennis Men's Doubles      posicion  -    edad 27
Singles, Men (Olympic)    posicion 17    edad  -
Tennis Men's Singles      posicion  -    edad 27
```

Jugó **2 eventos** y la base tiene **4 filas**.

### Qué se hizo

Un primer intento falló: la firma `posicion`/`edad` no sirve aquí, porque todas las filas comparten `medalla = NULL` y caen en un solo grupo.

La solución vino de identificar **la causa**. Los nombres de `EVENTO` vienen en dos familias, que son dos orígenes fusionados: la canónica lleva un calificador entre paréntesis (`200 metres, Men (Olympic)`) y la descriptiva no (`Athletics Men's 200 metres`). Dentro de `(atleta, edición, disciplina)` se cuentan las filas canónicas, y solo si no hay ninguna se cuentan las descriptivas.

Verificado contra casos de verdad comprobable: Bolt 12 filas → **10**, Guy Forget 9 → **5**, Ray Ewry 23 → **13**, Phelps 30 → **30** sin cambio.

Global: 712,020 filas → **557,545 participaciones reales** (−21.7%), con 590 grupos indeterminados de 428,251 (0.14%).

> **Para el ETL:** igual que con las medallas, esto corrige la salida del SP. Las filas siguen duplicadas en `PARTICIPACION`.

---

## 3. Atletas homónimos sin fusionar

**48,370 nombres repetidos.** `Usain Bolt` existe como 10 `id_atleta`, `Paavo Nurmi` como 12, `Eric Lemming` como 23.

**Corrección sobre lo que se había reportado antes:** los fragmentos **no son registros vacíos**. Cada uno carga participaciones propias, que duplican las del registro canónico. Los nueve fragmentos de `Usain Bolt`:

```
197719  2008  100 metres, Men (Olympic)              JAM  Gold
197720  2008  Athletics Men's 200 metres             JAM  Gold
197721  2008  Athletics Men's 4 x 100 metres Relay   JAM  -
197722  2012  100 metres, Men (Olympic)              JAM  Gold
...                                                        (9 filas)
```

Son sus carreras reales, repartidas en nueve atletas distintos. Es una **tercera capa de duplicación**, por encima de las dos de los hallazgos 1 y 2, y a nivel de identidad en vez de a nivel de fila.

Medido: **128,324 registros sin biografía cargan 139,950 filas de participación.**

### Por qué no se puede resolver desde el SP

Se evaluó fusionarlos usando la biografía como discriminador —quedarse con el registro que la tiene— y no funciona:

| Patrón entre nombres repetidos | Nombres | `id_atleta` |
|---|---:|---:|
| 1 canónico con biografía + N sin ella | 29,696 | 96,058 |
| **ninguno con biografía** | **17,629** | **58,866** |
| varios con biografía | 2,544 | 9,737 |

En 17,629 nombres no hay ningún registro con biografía, así que no hay forma de saber cuál es el canónico. Y donde varios la tienen pueden ser personas distintas de verdad. Fusionar desde una consulta sería inventar una identidad que el dato no respalda.

El patrón habitual, donde sí hay biografía, es **un registro canónico más N fragmentos**:

```
Usain Bolt     10 ids  ->  1 con biografía,  9 sin
Eric Lemming   23 ids  ->  1 con biografía, 22 sin
Michael Phelps  1 id   ->  1 con biografía,  0 sin
```

El SP lo maneja con `@max_atletas`, `@coincidencia_exacta` y `@id_atleta`.

---

## 4. Participaciones imposibles atribuidas a un atleta

El problema inverso al 3: personas distintas fusionadas en un mismo `id_atleta`.

```sql
SELECT COUNT(*) AS filas, COUNT(DISTINCT a.id_atleta) AS atletas
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE a.fecha_fallecimiento IS NOT NULL
  AND eo.anio > YEAR(a.fecha_fallecimiento);
```

**784 participaciones posteriores a la fecha de fallecimiento**, en 781 atletas (0.11% de las filas).

```
31000  Nikolay Andrianov   falleció 2011-03-21
         1972-1980  URS  24 filas de gimnasia   <- correctas
         2020       CHN  Women's Kayak          <- imposible

173    Aristidis Akratopoulos   tenista, Atenas 1896
         2020       ETH  Men -58kg              <- taekwondo, 124 años después
```

Se detectó al filtrar a Andrianov por `@pais = 'URS'`: el SP devolvió 24 y la tabla tiene 25.

Verificado que **no es una regresión**: ya existía antes de las correcciones semánticas.

### Qué se hizo

Por indicación del equipo **no se filtran**. Pero el detalle del SP ahora trae la columna `posterior_a_fallecimiento`, que las marca con `1` sin alterar ningún conteo. Señalar no es esconder: la fila sigue ahí y sigue contando, solo deja de pasar desapercibida.

---

## 5. El separador `•` sigue en dos columnas de nombre

```sql
SELECT 'nombre_usado' AS columna, COUNT(*) AS filas
FROM olympics.ATLETA WHERE nombre_usado LIKE N'%' + NCHAR(8226) + N'%'
UNION ALL
SELECT 'nombre_original', COUNT(*)
FROM olympics.ATLETA WHERE nombre_original LIKE N'%' + NCHAR(8226) + N'%';
```

```
nombre_usado      145,500 filas
nombre_original    30,706 filas
nombre_completo         0 filas   <- la única que se limpió
```

Rompía la búsqueda contra esas columnas:

```
Lionel Messi       ->  nombre_usado = 'Lionel•Messi'
Cristiano Ronaldo  ->  nombre_usado = '•Cristiano Ronaldo'
```

**Resuelto en el SP:** aplica `REPLACE(columna, NCHAR(8226), N' ')` antes de comparar, en las cuatro columnas de nombre y tanto en la búsqueda exacta como en la parcial. El dato no se modifica.

---

## 6. Nombres duplicados por pérdida de caracteres

Un patrón distinto al de los homónimos vacíos: el mismo nombre existe dos veces, una con el carácter no-ASCII y otra **sin él**, no reemplazado sino eliminado.

Medido sobre `atleta.csv`: **16,115 nombres no-ASCII tienen un gemelo idéntico ya despojado** de esos caracteres, presente en la base como atleta aparte.

```
Marit Bjørgen          15 medallas
Marit Bjrgen           10 medallas    <- la ø desapareció

Ole Einar Bjørndalen   13 medallas
Ole Einar Bjrndalen    13 medallas

Zoltán Halmay           9 medallas
Zoltn Halmay            1 medalla
```

En los dos primeros casos **las medallas están duplicadas entre ambos registros**, no repartidas: el atleta real no tiene 28 ni 26, tiene las de uno solo.

**Lo que el SP sí resuelve:** buscar `Bjorgen` encuentra a `Marit Bjørgen`, porque la colación `Latin1_General_CI_AI` pliega la `ø` a `o`. Se verificó una por una: `ø æ å ð þ ł ß đ ı` se pliegan todas.

```sql
SELECT id_atleta, nombre FROM olympics.ATLETA
WHERE nombre COLLATE Latin1_General_CI_AI LIKE N'%Bjorgen%';
-- 100161  Marit Bjørgen
```

**Lo que no:** `Marit Bjrgen` (`148654`) es un atleta aparte, con la letra eliminada y no reemplazada. Ninguna colación lo alcanza, porque no es un problema de comparación sino de identidad — el mismo caso del hallazgo 3.

> Nota para quien venga de la versión anterior de este documento: ahí se decía que `ø` no se pliega. Eso es cierto de la normalización Unicode **NFD**, que fue como se midió al principio desde Python, pero no de la colación `CI_AI` de SQL Server, que es la que usa el SP.

---

## 7. El conteo de medallas de `sp_consultar_pais` queda inflado por el hallazgo 1

Consecuencia directa del hallazgo 1, detectada al revisar si la duplicación afectaba a otras consultas del proyecto. **No es un error de lógica de ese procedimiento**: su regla es razonable y falla solo por cómo quedó el dato.

`sp_consultar_pais` cuenta las medallas oficiales del país así:

```sql
SELECT DISTINCT p.id_edicion, p.id_evento, p.id_noc, p.medalla
```

La clave incluye `id_evento`, y **las filas duplicadas tienen `id_evento` distinto**: la base guarda dos registros de `EVENTO` para la misma prueba, uno por cada nomenclatura. El `DISTINCT` no los colapsa.

```sql
SELECT ev.id_evento, ev.nombre, COUNT(*) AS filas_oro_USA
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO ev          ON ev.id_evento = p.id_evento
JOIN olympics.NOC n              ON n.id_noc     = p.id_noc
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion = p.id_edicion
WHERE n.codigo_noc = N'USA' AND e.anio = 1900 AND p.medalla = N'Gold'
  AND ev.nombre LIKE N'%Standing%'
GROUP BY ev.id_evento, ev.nombre;
```

```
2216  Athletics Men's Standing High Jump        <- misma prueba
1049  Standing High Jump, Men (Olympic)         <- misma prueba
2217  Athletics Men's Standing Long Jump
561   Standing Long Jump, Men (Olympic)
2535  Athletics Men's Standing Triple Jump
1063  Standing Triple Jump, Men (Olympic)
```

Seis `id_evento` para **tres eventos reales**, así que el procedimiento reporta 6 oros donde hubo 3.

Aplicando la regla del hallazgo 1 sobre esa misma métrica, medido en toda la base:

| | |
|---|---:|
| Medallas oficiales que reporta hoy | 40,182 |
| Estimado real | 26,173 |
| Inflación | **14,009 (~35%)** |
| Grupos donde la firma no concluye | 567 |

**Donde el ETL ya fusionó los pares, el conteo sale bien.** Esas filas traen `posicion` y `edad` juntas (7,581 en total) y el `DISTINCT` las trata como una sola. Guatemala, por ejemplo, devuelve **3** correctamente.

No hay nada que corregir del lado del inciso d. Se reporta porque el conteo de país se defiende igual que el de atleta y conviene que la cifra sea consistente entre ambos.

---

## Resumen

| # | Hallazgo | Estado |
|---|---|---|
| 1 | Duplicación de medallas | **Corregido en el SP**; pendiente en el dato |
| 2 | Participaciones duplicadas | **Corregido en el SP**; pendiente en el dato |
| 3 | Atletas homónimos (3.ª capa de duplicación) | Pendiente — no resoluble desde consulta |
| 4 | Participaciones imposibles | **Señaladas en el SP**; pendiente en el dato |
| 5 | Separador `•` en dos columnas | **Resuelto en el SP** |
| 6 | Nombres con caracteres perdidos | Parcial — la búsqueda los alcanza, la identidad no |
| 7 | Medallero de `sp_consultar_pais` inflado | Pendiente — consecuencia del 1, ~35% |

---

## Detalle de entorno (no es de datos)

`04_bulk_load_staging.sql` usa `ROWTERMINATOR = '0x0a'` para los diez CSV. En un checkout de Windows con `core.autocrlf = true` los archivos quedan en CRLF y la carga falla en `disciplina.csv` y `evento.csv`, que son los que tienen campos entrecomillados al final.

Un `.gitattributes` con `*.csv -text` haría el script determinista en cualquier máquina. Queda a criterio del responsable del inciso c.
