# CONTEXT_DATA_LIMPIA_INICIO_STORE_PRODUCES_SQL_PURO
## Handoff técnico para Stored Procedures y consultas SQL en defensa

> **Propósito**
>
> Este archivo resume el estado final, limpio, homologado, cargado y validado de `OlimpiadasDB`.
>
> Está pensado para que los integrantes responsables de los procedimientos almacenados puedan trabajar directamente sobre el modelo final y, además, prepararse para responder consultas manuales en **T-SQL puro** durante una defensa.
>
> **No forma parte de la entrega académica oficial.**
>
> No volver a limpiar, homologar, cargar o rediseñar los datos.

---

# 1. Punto de partida

La base ya está:

```text
Limpia
Homologada
Consolidada
Cargada
Validada
Indexada
```

No volver a ejecutar:

```text
limpieza
matching
consolidación
BULK INSERT
carga final
reset de tablas
DELETE
TRUNCATE
DROP
```

Los procedimientos y consultas funcionales deben trabajar exclusivamente contra:

```text
olympics
```

El schema:

```text
stg
```

es únicamente infraestructura ETL y **NO debe utilizarse en Stored Procedures ni consultas de negocio**.

---

# 2. Conexión

```text
Base de datos: OlimpiadasDB
Schema final: olympics
Motor: SQL Server 2025 Developer
Contenedor: olimpiadas-sqlserver
Host: localhost
Puerto: 1434
```

La contraseña se obtiene desde:

```text
.env
```

No incluir contraseñas en scripts o documentación.

---

# 3. Magnitudes finales

```text
ENTIDAD_GEOGRAFICA       282
POBLACION             17,024
NOC                      236
ATLETA               338,772
SEDE                      42
EDICION_OLIMPICA          61
DEPORTE                    65
DISCIPLINA                117
EVENTO                  3,106
PARTICIPACION         826,605
```

Total:

```text
1,186,310 filas
```

Integridad:

```text
PK duplicadas:             0
FK huérfanas:              0
DECIMAL con pérdida:       0
Unicode comparado:    26,261
Diferencias Unicode:       0
```

---

# 4. Tablas finales

## ENTIDAD_GEOGRAFICA

```text
id_entidad     INT            PK
nombre         NVARCHAR(150)  NOT NULL
codigo_pais    CHAR(3)        NULL
```

Importante:

```text
codigo_pais != codigo_noc
```

Ejemplo:

```text
Germany
codigo_pais = DEU
codigo_noc  = GER
```

---

## POBLACION

```text
id_entidad     INT       PK/FK
anio           SMALLINT  PK
poblacion      BIGINT    NULL
```

PK:

```text
(id_entidad, anio)
```

---

## NOC

```text
id_noc         INT            PK
codigo_noc     CHAR(3)        NOT NULL
nombre_noc     NVARCHAR(150)  NULL
id_entidad     INT            FK NULL
notas          NVARCHAR(500)  NULL
```

Relación:

```text
NOC.id_entidad
→ ENTIDAD_GEOGRAFICA.id_entidad
```

No asumir:

```text
NOC = ISO3
```

Puede haber varios NOC asociados históricamente a una misma entidad.

---

## ATLETA

```text
id_atleta                  BIGINT           PK
nombre                     NVARCHAR(250)    NOT NULL
nombre_completo            NVARCHAR(300)    NULL
nombre_usado               NVARCHAR(300)    NULL
nombre_original            NVARCHAR(300)    NULL
otros_nombres              NVARCHAR(500)    NULL
apodos                     NVARCHAR(500)    NULL
orden_nombre               NVARCHAR(50)     NULL
sexo                       NVARCHAR(20)     NULL
fecha_nacimiento           DATE             NULL
ciudad_nacimiento          NVARCHAR(150)    NULL
region_nacimiento          NVARCHAR(150)    NULL
id_pais_nacimiento         INT              FK NULL
id_pais_nacionalidad       INT              FK NULL
fecha_fallecimiento        DATE             NULL
ciudad_fallecimiento       NVARCHAR(150)    NULL
region_fallecimiento       NVARCHAR(150)    NULL
id_pais_fallecimiento      INT              FK NULL
altura_cm                  DECIMAL(5,2)     NULL
peso_kg                    DECIMAL(5,2)     NULL
roles                      NVARCHAR(MAX)    NULL
afiliaciones               NVARCHAR(MAX)    NULL
titulos                    NVARCHAR(2000)   NULL
latitud                    DECIMAL(19,16)   NULL
longitud                   DECIMAL(19,16)   NULL
```

---

## SEDE

```text
id_sede     INT            PK
nombre      NVARCHAR(150)  NOT NULL
id_pais     INT            FK NOT NULL
```

---

## EDICION_OLIMPICA

```text
id_edicion     INT           PK
anio           SMALLINT      NOT NULL
temporada      NVARCHAR(20)  NOT NULL
id_sede        INT           FK NULL
```

Temporadas válidas:

```text
Summer
Winter
Intercalated Games
Summer Youth
Winter Youth
```

Casos:

```text
1906 = Intercalated Games
1956 Equestrian → Summer
Equestrian no existe como temporada final
```

---

## DEPORTE

```text
id_deporte     INT            PK
nombre         NVARCHAR(150)  NOT NULL
```

---

## DISCIPLINA

```text
id_disciplina     INT            PK
id_deporte        INT            FK NOT NULL
nombre            NVARCHAR(150)  NOT NULL
```

---

## EVENTO

```text
id_evento         BIGINT         PK
id_disciplina     INT            FK NOT NULL
nombre            NVARCHAR(300)  NOT NULL
```

---

## PARTICIPACION

```text
id_participacion            BIGINT           PK
id_atleta                   BIGINT           FK NOT NULL
id_edicion                  INT              FK NOT NULL
id_evento                   BIGINT           FK NOT NULL
id_noc                      INT              FK NULL
id_pais_nacionalidad        INT              FK NULL
equipo                      NVARCHAR(250)    NULL
nombre_competencia          NVARCHAR(300)    NULL
edad                        DECIMAL(5,2)     NULL
altura_cm_registrada        DECIMAL(5,2)     NULL
peso_kg_registrado          DECIMAL(16,13)   NULL
posicion                    INT              NULL
empatado                    BIT              NULL
estado_resultado            NVARCHAR(30)     NULL
medalla                     NVARCHAR(20)     NULL
```

---

# 5. Relaciones principales

```text
ATLETA
   |
   | id_atleta
   v
PARTICIPACION
   | \
   |  \ id_noc
   |   v
   |   NOC
   |    |
   |    | id_entidad
   |    v
   |   ENTIDAD_GEOGRAFICA
   |
   | id_edicion
   v
EDICION_OLIMPICA
   |
   | id_sede
   v
SEDE
   |
   | id_pais
   v
ENTIDAD_GEOGRAFICA

PARTICIPACION
   |
   | id_evento
   v
EVENTO
   |
   | id_disciplina
   v
DISCIPLINA
   |
   | id_deporte
   v
DEPORTE
```

Jerarquía deportiva:

```text
DEPORTE
→ DISCIPLINA
→ EVENTO
→ PARTICIPACION
```

---

# 6. Semántica de participación

## Medalla

Valores:

```text
Gold
Silver
Bronze
NULL
```

Advertencia:

```text
COUNT(medalla)
```

cuenta registros de atletas medallistas, no necesariamente medallas oficiales únicas por evento/país.

---

## Posición

```text
posicion INT NULL
```

Puede ser:

```text
1
2
3
...
NULL
```

---

## Empate

```text
empatado BIT
```

```text
1 = posición compartida
0 = no compartida
NULL = no disponible
```

---

## Estado del resultado

Puede contener:

```text
DNF
DNS
DQ
DSQ
```

o:

```text
NULL
```

Importante:

```text
estado_resultado = NULL
```

normalmente significa que no hubo estado especial.

No existe:

```text
FINISHED
```

---

# 7. País, nacionalidad y NOC NO son lo mismo

No confundir:

```text
ATLETA.id_pais_nacionalidad
PARTICIPACION.id_pais_nacionalidad
PARTICIPACION.id_noc
```

## Nacionalidad biográfica

```text
ATLETA.id_pais_nacionalidad
```

## Nacionalidad registrada en participación

```text
PARTICIPACION.id_pais_nacionalidad
```

## NOC representado

```text
PARTICIPACION.id_noc
```

Para resultados olímpicos por país, normalmente la ruta útil es:

```text
ENTIDAD_GEOGRAFICA
→ NOC
→ PARTICIPACION
```

Pero siempre revisar qué significa “país” en la consulta solicitada.

---

# 8. Índices existentes

```text
IX_PARTICIPACION_id_atleta
IX_PARTICIPACION_id_edicion
IX_PARTICIPACION_id_evento
IX_PARTICIPACION_id_noc
IX_PARTICIPACION_id_pais_nacionalidad
IX_ATLETA_id_pais_nacionalidad
IX_NOC_id_entidad
IX_SEDE_id_pais
```

No crear índices duplicados.

---

# 9. Stored Procedure por atleta

## Objetivo

Consultar el historial completo de un atleta.

## Parámetro principal recomendado

```sql
@id_atleta BIGINT
```

## Ruta de JOIN

```text
ATLETA
→ PARTICIPACION
→ EDICION_OLIMPICA
→ EVENTO
→ DISCIPLINA
→ DEPORTE
→ NOC
```

## Consulta base

```sql
SELECT
    a.id_atleta,
    a.nombre AS atleta,
    eo.anio,
    eo.temporada,
    dep.nombre AS deporte,
    d.nombre AS disciplina,
    e.nombre AS evento,
    n.codigo_noc,
    p.equipo,
    p.nombre_competencia,
    p.edad,
    p.altura_cm_registrada,
    p.peso_kg_registrado,
    p.posicion,
    p.empatado,
    p.estado_resultado,
    p.medalla
FROM olympics.ATLETA a
JOIN olympics.PARTICIPACION p
    ON p.id_atleta = a.id_atleta
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
JOIN olympics.DISCIPLINA d
    ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep
    ON dep.id_deporte = d.id_deporte
LEFT JOIN olympics.NOC n
    ON n.id_noc = p.id_noc
WHERE a.id_atleta = @id_atleta
ORDER BY eo.anio, dep.nombre, d.nombre, e.nombre;
```

Caso conocido:

```text
id_atleta = 17
Guy Forget
```

---

# 10. Stored Procedure por país

## Parámetro recomendado

```sql
@id_entidad INT
```

## Ruta principal

```text
ENTIDAD_GEOGRAFICA
→ NOC
→ PARTICIPACION
→ ATLETA
→ EDICION_OLIMPICA
→ EVENTO
→ DISCIPLINA
→ DEPORTE
```

## Consulta base

```sql
SELECT
    eg.id_entidad,
    eg.nombre AS pais,
    n.codigo_noc,
    n.nombre_noc,
    a.id_atleta,
    a.nombre AS atleta,
    eo.anio,
    eo.temporada,
    dep.nombre AS deporte,
    d.nombre AS disciplina,
    e.nombre AS evento,
    p.equipo,
    p.posicion,
    p.estado_resultado,
    p.medalla
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
JOIN olympics.PARTICIPACION p
    ON p.id_noc = n.id_noc
JOIN olympics.ATLETA a
    ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
JOIN olympics.DISCIPLINA d
    ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep
    ON dep.id_deporte = d.id_deporte
WHERE eg.id_entidad = @id_entidad
ORDER BY eo.anio, a.nombre, dep.nombre, e.nombre;
```

Caso conocido:

```text
id_entidad = 268
United States
NOC = USA
```

---

# 11. Buenas prácticas para Stored Procedures

Usar:

```sql
CREATE OR ALTER PROCEDURE
```

Agregar:

```sql
SET NOCOUNT ON;
```

Usar parámetros tipados:

```sql
@id_atleta BIGINT
@id_entidad INT
```

Evitar:

```sql
SELECT *
```

No usar SQL dinámico si no es necesario.

No modificar datos.

No consultar `stg`.

---

# 12. Filtros opcionales útiles

Si la rúbrica permite filtros adicionales:

## Atleta

```text
@id_atleta     BIGINT
@anio_desde    SMALLINT = NULL
@anio_hasta    SMALLINT = NULL
@temporada     NVARCHAR(20) = NULL
@medalla       NVARCHAR(20) = NULL
```

## País

```text
@id_entidad     INT
@anio_desde     SMALLINT = NULL
@anio_hasta     SMALLINT = NULL
@temporada      NVARCHAR(20) = NULL
@deporte        NVARCHAR(150) = NULL
@medalla        NVARCHAR(20) = NULL
```

Ejemplo de patrón:

```sql
AND (@anio_desde IS NULL OR eo.anio >= @anio_desde)
AND (@anio_hasta IS NULL OR eo.anio <= @anio_hasta)
AND (@temporada IS NULL OR eo.temporada = @temporada)
```

---

# 13. SQL puro para defensa

Además de los Stored Procedures, deben saber resolver consultas manuales con:

```text
SELECT
JOIN
LEFT JOIN
WHERE
GROUP BY
HAVING
ORDER BY
COUNT
COUNT_BIG
COUNT DISTINCT
SUM
CASE
TOP
LIKE
```

---

# 14. Buscar un atleta por nombre

```sql
SELECT
    id_atleta,
    nombre
FROM olympics.ATLETA
WHERE nombre LIKE N'%Forget%'
ORDER BY nombre;
```

No memorizar IDs si no es necesario.

Primero buscar el atleta y luego usar el `id_atleta`.

---

# 15. Historial de un atleta

```sql
SELECT
    a.nombre,
    eo.anio,
    eo.temporada,
    dep.nombre AS deporte,
    d.nombre AS disciplina,
    e.nombre AS evento,
    n.codigo_noc,
    p.equipo,
    p.posicion,
    p.estado_resultado,
    p.medalla
FROM olympics.ATLETA a
JOIN olympics.PARTICIPACION p
    ON p.id_atleta = a.id_atleta
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
JOIN olympics.DISCIPLINA d
    ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep
    ON dep.id_deporte = d.id_deporte
LEFT JOIN olympics.NOC n
    ON n.id_noc = p.id_noc
WHERE a.id_atleta = 17
ORDER BY eo.anio;
```

---

# 16. Cuántas participaciones tiene un atleta

```sql
SELECT
    a.id_atleta,
    a.nombre,
    COUNT_BIG(*) AS participaciones
FROM olympics.ATLETA a
JOIN olympics.PARTICIPACION p
    ON p.id_atleta = a.id_atleta
WHERE a.id_atleta = 17
GROUP BY a.id_atleta, a.nombre;
```

---

# 17. Medallas de un atleta

```sql
SELECT
    a.nombre,
    p.medalla,
    COUNT_BIG(*) AS registros
FROM olympics.ATLETA a
JOIN olympics.PARTICIPACION p
    ON p.id_atleta = a.id_atleta
WHERE a.id_atleta = 17
  AND p.medalla IS NOT NULL
GROUP BY a.nombre, p.medalla
ORDER BY p.medalla;
```

---

# 18. Buscar país o entidad

```sql
SELECT
    id_entidad,
    nombre,
    codigo_pais
FROM olympics.ENTIDAD_GEOGRAFICA
WHERE nombre LIKE N'%United%'
ORDER BY nombre;
```

---

# 19. NOC asociados a un país

```sql
SELECT
    eg.nombre AS pais,
    n.codigo_noc,
    n.nombre_noc,
    n.notas
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
WHERE eg.id_entidad = 268
ORDER BY n.codigo_noc;
```

Esto es útil para demostrar que una entidad puede tener múltiples NOC históricos.

---

# 20. Atletas distintos por país/NOC

```sql
SELECT
    eg.nombre AS pais,
    COUNT(DISTINCT p.id_atleta) AS atletas_distintos
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
JOIN olympics.PARTICIPACION p
    ON p.id_noc = n.id_noc
GROUP BY eg.nombre
ORDER BY atletas_distintos DESC;
```

---

# 21. Participaciones por país

```sql
SELECT
    eg.nombre AS pais,
    COUNT_BIG(*) AS participaciones
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
JOIN olympics.PARTICIPACION p
    ON p.id_noc = n.id_noc
GROUP BY eg.nombre
ORDER BY participaciones DESC;
```

---

# 22. Registros de medalla por país

```sql
SELECT
    eg.nombre AS pais,
    SUM(CASE WHEN p.medalla = N'Gold' THEN 1 ELSE 0 END) AS gold,
    SUM(CASE WHEN p.medalla = N'Silver' THEN 1 ELSE 0 END) AS silver,
    SUM(CASE WHEN p.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronze
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
JOIN olympics.PARTICIPACION p
    ON p.id_noc = n.id_noc
GROUP BY eg.nombre
ORDER BY gold DESC;
```

Advertencia:

```text
Esto cuenta registros de atletas con medalla.
No equivale automáticamente a medallas oficiales únicas por evento.
```

---

# 23. Participaciones por año

```sql
SELECT
    eo.anio,
    COUNT_BIG(*) AS participaciones
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
GROUP BY eo.anio
ORDER BY eo.anio;
```

---

# 24. Participaciones por temporada

```sql
SELECT
    eo.temporada,
    COUNT_BIG(*) AS participaciones
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
GROUP BY eo.temporada
ORDER BY participaciones DESC;
```

---

# 25. Deportes con más participaciones

```sql
SELECT TOP (10)
    dep.nombre AS deporte,
    COUNT_BIG(*) AS participaciones
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
JOIN olympics.DISCIPLINA d
    ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep
    ON dep.id_deporte = d.id_deporte
GROUP BY dep.nombre
ORDER BY participaciones DESC;
```

---

# 26. Eventos de un deporte

```sql
SELECT
    dep.nombre AS deporte,
    d.nombre AS disciplina,
    e.nombre AS evento
FROM olympics.DEPORTE dep
JOIN olympics.DISCIPLINA d
    ON d.id_deporte = dep.id_deporte
JOIN olympics.EVENTO e
    ON e.id_disciplina = d.id_disciplina
WHERE dep.nombre LIKE N'%Athletics%'
ORDER BY d.nombre, e.nombre;
```

---

# 27. Atletas con DNF

```sql
SELECT TOP (50)
    a.nombre,
    eo.anio,
    eo.temporada,
    e.nombre AS evento,
    p.estado_resultado
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a
    ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
WHERE p.estado_resultado = N'DNF'
ORDER BY eo.anio DESC;
```

---

# 28. DNS / DQ / DSQ

```sql
SELECT
    p.estado_resultado,
    COUNT_BIG(*) AS cantidad
FROM olympics.PARTICIPACION p
WHERE p.estado_resultado IS NOT NULL
GROUP BY p.estado_resultado
ORDER BY cantidad DESC;
```

---

# 29. Posiciones empatadas

```sql
SELECT TOP (50)
    a.nombre,
    eo.anio,
    e.nombre AS evento,
    p.posicion,
    p.empatado
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a
    ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e
    ON e.id_evento = p.id_evento
WHERE p.empatado = 1
ORDER BY eo.anio DESC;
```

---

# 30. Ediciones Olímpicas

```sql
SELECT
    eo.id_edicion,
    eo.anio,
    eo.temporada,
    s.nombre AS sede,
    eg.nombre AS pais_sede
FROM olympics.EDICION_OLIMPICA eo
LEFT JOIN olympics.SEDE s
    ON s.id_sede = eo.id_sede
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg
    ON eg.id_entidad = s.id_pais
ORDER BY eo.anio, eo.temporada;
```

---

# 31. Caso 1906

```sql
SELECT
    *
FROM olympics.EDICION_OLIMPICA
WHERE anio = 1906;
```

Esperado:

```text
Intercalated Games
```

No debe existir:

```text
1906 Summer
```

---

# 32. Caso Equestrian

```sql
SELECT
    COUNT_BIG(*) AS ediciones_equestrian
FROM olympics.EDICION_OLIMPICA
WHERE temporada = N'Equestrian';
```

Esperado:

```text
0
```

---

# 33. Youth

```sql
SELECT
    temporada,
    COUNT(*) AS ediciones
FROM olympics.EDICION_OLIMPICA
WHERE temporada IN (N'Summer Youth', N'Winter Youth')
GROUP BY temporada;
```

Esperado:

```text
Summer Youth = 3
Winter Youth = 3
```

---

# 34. Atletas Unicode

```sql
SELECT TOP (50)
    id_atleta,
    nombre
FROM olympics.ATLETA
WHERE nombre COLLATE Latin1_General_100_BIN2 LIKE N'%[^ -~]%'
ORDER BY nombre;
```

Caso conocido:

```text
Jean-François Blanchy
```

---

# 35. Top atletas con más participaciones

```sql
SELECT TOP (10)
    a.id_atleta,
    a.nombre,
    COUNT_BIG(*) AS participaciones
FROM olympics.ATLETA a
JOIN olympics.PARTICIPACION p
    ON p.id_atleta = a.id_atleta
GROUP BY a.id_atleta, a.nombre
ORDER BY participaciones DESC;
```

---

# 36. Atletas por edición

```sql
SELECT
    eo.anio,
    eo.temporada,
    COUNT(DISTINCT p.id_atleta) AS atletas
FROM olympics.EDICION_OLIMPICA eo
JOIN olympics.PARTICIPACION p
    ON p.id_edicion = eo.id_edicion
GROUP BY eo.anio, eo.temporada
ORDER BY eo.anio;
```

---

# 37. Participaciones con medalla por año

```sql
SELECT
    eo.anio,
    COUNT_BIG(*) AS registros_con_medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo
    ON eo.id_edicion = p.id_edicion
WHERE p.medalla IS NOT NULL
GROUP BY eo.anio
ORDER BY eo.anio;
```

---

# 38. Consultas por nacionalidad registrada

Si el ingeniero pregunta explícitamente por **nacionalidad** y no por NOC:

```sql
SELECT
    eg.nombre AS nacionalidad,
    COUNT_BIG(*) AS participaciones
FROM olympics.PARTICIPACION p
JOIN olympics.ENTIDAD_GEOGRAFICA eg
    ON eg.id_entidad = p.id_pais_nacionalidad
GROUP BY eg.nombre
ORDER BY participaciones DESC;
```

No usar esta consulta como sustituto automático de una consulta por NOC.

---

# 39. Consultas por nacionalidad biográfica

```sql
SELECT
    eg.nombre AS nacionalidad,
    COUNT_BIG(*) AS atletas
FROM olympics.ATLETA a
JOIN olympics.ENTIDAD_GEOGRAFICA eg
    ON eg.id_entidad = a.id_pais_nacionalidad
GROUP BY eg.nombre
ORDER BY atletas DESC;
```

De nuevo:

```text
ATLETA.id_pais_nacionalidad
!= PARTICIPACION.id_pais_nacionalidad
!= PARTICIPACION.id_noc
```

---

# 40. Población por entidad

```sql
SELECT
    eg.nombre,
    p.anio,
    p.poblacion
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.POBLACION p
    ON p.id_entidad = eg.id_entidad
WHERE eg.nombre = N'Guatemala'
ORDER BY p.anio;
```

---

# 41. Plantillas mentales para defensa

## Buscar atleta

```text
ATLETA
→ PARTICIPACION
→ EDICION
→ EVENTO
→ DISCIPLINA
→ DEPORTE
```

## Buscar país por representación olímpica

```text
ENTIDAD_GEOGRAFICA
→ NOC
→ PARTICIPACION
```

## Buscar nacionalidad registrada

```text
PARTICIPACION.id_pais_nacionalidad
→ ENTIDAD_GEOGRAFICA
```

## Buscar nacionalidad biográfica

```text
ATLETA.id_pais_nacionalidad
→ ENTIDAD_GEOGRAFICA
```

## Buscar sede

```text
EDICION_OLIMPICA
→ SEDE
→ ENTIDAD_GEOGRAFICA
```

## Buscar deporte

```text
PARTICIPACION
→ EVENTO
→ DISCIPLINA
→ DEPORTE
```

---

# 42. Patrones SQL útiles

## Filtrar por año

```sql
WHERE eo.anio = 2012
```

## Rango de años

```sql
WHERE eo.anio BETWEEN 2000 AND 2024
```

## Filtrar temporada

```sql
WHERE eo.temporada = N'Summer'
```

## Filtrar medalla

```sql
WHERE p.medalla = N'Gold'
```

## Solo medallistas

```sql
WHERE p.medalla IS NOT NULL
```

## Sin medalla

```sql
WHERE p.medalla IS NULL
```

## Estado especial

```sql
WHERE p.estado_resultado IS NOT NULL
```

## Buscar texto

```sql
WHERE a.nombre LIKE N'%Bolt%'
```

---

# 43. GROUP BY mental rápido

Si seleccionas:

```sql
eg.nombre,
COUNT(*)
```

debes agrupar:

```sql
GROUP BY eg.nombre
```

Si seleccionas:

```sql
eo.anio,
eo.temporada,
COUNT(*)
```

debes usar:

```sql
GROUP BY eo.anio, eo.temporada
```

---

# 44. HAVING

Ejemplo: países con más de 10,000 participaciones.

```sql
SELECT
    eg.nombre,
    COUNT_BIG(*) AS participaciones
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n
    ON n.id_entidad = eg.id_entidad
JOIN olympics.PARTICIPACION p
    ON p.id_noc = n.id_noc
GROUP BY eg.nombre
HAVING COUNT_BIG(*) > 10000
ORDER BY participaciones DESC;
```

---

# 45. DISTINCT

Usar cuando el concepto realmente necesita unicidad.

Ejemplo:

```sql
COUNT(DISTINCT p.id_atleta)
```

para contar atletas distintos.

No poner `DISTINCT` indiscriminadamente para esconder duplicados causados por un JOIN incorrecto.

---

# 46. INNER JOIN vs LEFT JOIN

Usar `JOIN` cuando la relación debe existir.

Ejemplo:

```text
PARTICIPACION → ATLETA
PARTICIPACION → EDICION
PARTICIPACION → EVENTO
```

Usar `LEFT JOIN` cuando una relación puede ser `NULL`.

Ejemplo:

```text
PARTICIPACION.id_noc
EDICION_OLIMPICA.id_sede
```

---

# 47. Qué NO hacer en defensa

```text
NO usar SELECT * si no hace falta
NO hacer joins por nombre si existe FK
NO asumir NOC = ISO3
NO contar medallas oficiales sin definir granularidad
NO olvidar DISCIPLINA entre EVENTO y DEPORTE
NO eliminar NULL válidos
NO usar stg
NO escribir UPDATE/DELETE
NO memorizar IDs si se pueden buscar
```

---

# 48. Ejemplos de preguntas que pueden resolver rápido

```text
¿Cuántos atletas participaron en 2012?
¿Qué país tiene más participaciones?
¿Qué atleta tiene más participaciones?
¿Qué deportes tienen más registros?
¿Cuántos atletas distintos representaron a USA?
¿Qué medallas tiene un atleta?
¿Qué atletas tuvieron DNF?
¿Qué ediciones Youth existen?
¿Qué pasó con 1906?
¿Existe Equestrian como temporada?
¿Qué NOC históricos tiene un país?
¿Cuántos atletas son de determinada nacionalidad?
¿Qué sede tuvo una edición?
```

---

# 49. Stored Procedures y SQL manual no se contradicen

Ambos son T-SQL.

Stored Procedure:

```sql
EXEC olympics.sp_consultar_atleta @id_atleta = 17;
```

Consulta manual:

```sql
SELECT ...
FROM ...
JOIN ...
WHERE ...
```

La diferencia es que el Stored Procedure ya dejó encapsulada una consulta reutilizable.

Durante la defensa pueden pedir que escriban una consulta manual sin utilizar el SP.

Por eso deben dominar ambas formas.

---

# 50. Checklist antes de implementar SP

```text
[ ] Revisar enunciado exacto
[ ] Revisar hoja de calificación
[ ] Definir semántica de “país”
[ ] Definir parámetros
[ ] Usar tipos correctos
[ ] Usar olympics.*
[ ] No consultar stg
[ ] No usar SELECT *
[ ] Probar caso existente
[ ] Probar caso inexistente
[ ] Probar NULL
[ ] Probar 1906
[ ] Probar Youth
[ ] Verificar NOC histórico
[ ] Revisar plan/índices si la consulta es pesada
```

---

# 51. Checklist para defensa SQL

```text
[ ] Sé buscar un atleta
[ ] Sé buscar un país
[ ] Sé recorrer NOC
[ ] Sé llegar de participación a deporte
[ ] Sé filtrar por año
[ ] Sé filtrar por temporada
[ ] Sé filtrar por medalla
[ ] Sé contar atletas distintos
[ ] Sé usar GROUP BY
[ ] Sé usar HAVING
[ ] Sé interpretar NULL
[ ] Sé explicar NOC vs país
[ ] Sé explicar medalla individual vs oficial
[ ] Sé explicar 1906
[ ] Sé explicar 1956 Equestrian
[ ] Sé explicar Youth
```

---

# 52. Instrucción recomendada para una IA

> Trabaja sobre `OlimpiadasDB` utilizando exclusivamente el schema final `olympics`. Los datos ya están limpios, homologados, cargados e indexados. Implementa únicamente los Stored Procedures solicitados en el enunciado usando T-SQL y prepara también consultas SQL manuales para una defensa en vivo. No modifiques datos, no uses `stg`, no alteres el modelo, no inventes equivalencias entre NOC, país y nacionalidad, y no cuentes medallas oficiales sin definir correctamente su granularidad. Prioriza procedimientos parametrizados, joins por claves y consultas simples que puedan adaptarse rápidamente durante la defensa.

---

# 53. Regla final

```text
LOS DATOS YA ESTÁN LIMPIOS, HOMOLOGADOS, CARGADOS Y VALIDADOS.
```

El trabajo siguiente consiste en:

```text
1. Consultar correctamente la base
2. Implementar los Stored Procedures requeridos
3. Prepararse para consultas T-SQL manuales durante la defensa
```

No rediseñar ni volver a transformar los datos.
