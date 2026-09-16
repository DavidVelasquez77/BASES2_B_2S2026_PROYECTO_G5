USE OlimpiadasDB;
GO


/* ============================================================================
   1. ATLETAS FAMOSOS
============================================================================ */

/* 1.1 Lionel Messi.
   Buscar por nombre devuelve 26 coincidencias (hay homonimos y nombres
   completos que contienen "Messi"), asi que se desempata con @id_atleta.
   Verificado: 2008 Summer, Beijing, Football, ARG, posicion 1, Gold. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi';           -- lista de candidatos
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi', @id_atleta = 110178;
GO

/* 1.2 Neymar.
   Verificado: id 122812, plata en Londres 2012 y oro en Rio 2016. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Neymar', @id_atleta = 122812;
GO

/* 1.3 Cristiano Ronaldo.
   Verificado: id 102010, nacido 1985-02-05 en Funchal. Una sola participacion:
   2004 Summer, Athina, Football, POR, posicion 14, sin medalla.
   Portugal no medallo en Atenas 2004, asi que es correcto.

   Su nombre_usado es '<U+2022>Cristiano Ronaldo', con el separador al inicio.
   El SP normaliza ese caracter en la busqueda, por eso la coincidencia
   exacta lo encuentra igual. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Cristiano Ronaldo', @coincidencia_exacta = 1;
GO

/* 1.4 Ronaldo (el brasileno).
   "Ronaldo" devuelve varios atletas distintos. Ronaldo Nazario gano bronce
   en Atlanta 1996 y aparece con mas de un id_atleta por homonimia. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Ronaldo', @max_atletas = 30;
GO

/* 1.5 Quien mas busquen: solo cambiar el nombre.
   Si devuelve "BUSQUEDA AMBIGUA", usar el id_atleta de la lista. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Usain Bolt';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
GO


/* ============================================================================
   2. GUATEMALA
============================================================================ */

/* 2.1 Los medallistas de Guatemala.
   Verificado: exactamente 3 medallas.
     2012 Summer  Erick Barrondo   20 kilometres Race Walk, Men   Silver
     2024 Summer  Adriana Ruano    Trap, Women                    Gold
     2024 Summer  Jean-Pierre Brol Trap, Men                      Bronze */
SELECT eo.anio,
       eo.temporada,
       a.nombre       AS atleta,
       dep.nombre     AS deporte,
       e.nombre       AS evento,
       p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n               ON n.id_noc        = p.id_noc
JOIN olympics.ATLETA a            ON a.id_atleta     = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
WHERE n.codigo_noc = N'GUA'
  AND p.medalla IS NOT NULL
ORDER BY eo.anio, p.medalla;
GO

/* 2.2 Cuanto ha participado Guatemala en total.
   Verificado: 594 participaciones de 263 atletas distintos, en 20 ediciones.
   20 ediciones sobre 19 anios distintos: en 1988 compitio en Winter y Summer.
   Estas cifras son posteriores a la correccion canonica de identidades
   guatemaltecas del ETL; las anteriores (1,232 / 802) ya no son vigentes. */
SELECT COUNT(*)                      AS participaciones,
       COUNT(DISTINCT p.id_atleta)   AS atletas_distintos,
       COUNT(DISTINCT p.id_edicion)  AS ediciones,
       MIN(eo.anio)                  AS primera,
       MAX(eo.anio)                  AS ultima
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n               ON n.id_noc      = p.id_noc
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE n.codigo_noc = N'GUA';
GO

/* 2.3 En que deportes ha competido Guatemala. */
SELECT dep.nombre AS deporte,
       COUNT(*)                    AS participaciones,
       COUNT(DISTINCT p.id_atleta) AS atletas
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n               ON n.id_noc        = p.id_noc
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
WHERE n.codigo_noc = N'GUA'
GROUP BY dep.nombre
ORDER BY participaciones DESC;
GO

/* 2.4 El historial completo de Barrondo, usando el SP. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Barrondo';
GO


/* ============================================================================
   3. QUIEN GANO EL ORO EN UN EVENTO Y ANO
============================================================================ */

/* 3.1 Oro en 100 metros planos, 2004.
   Verificado:  Men -> Justin Gatlin     Women -> Yuliya Nestsiarenka
   Los 100 m planos son el evento "100 metres"; "100 metres Hurdles",
   "100 metres Butterfly", etc. son otros eventos. */
SELECT eo.anio, e.nombre AS evento, a.nombre AS atleta,
       n.codigo_noc, eg.nombre AS pais, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
LEFT JOIN olympics.NOC n                 ON n.id_noc      = p.id_noc
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
WHERE p.medalla = N'Gold'
  AND eo.anio   = 2004
  AND e.nombre IN (N'100 metres, Men (Olympic)', N'100 metres, Women (Olympic)')
ORDER BY e.nombre;
GO

/* 3.2 Variante por ano: cambiar el 2004.
   Verificado 2008 y 2016 -> Usain Bolt en Men. */
SELECT eo.anio, e.nombre AS evento, a.nombre AS atleta, n.codigo_noc, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
LEFT JOIN olympics.NOC n          ON n.id_noc      = p.id_noc
WHERE p.medalla = N'Gold'
  AND eo.anio IN (2008, 2012, 2016, 2020, 2024)
  AND e.nombre = N'100 metres, Men (Olympic)'
ORDER BY eo.anio;
GO

/* 3.3 Variante por evento: buscar cualquier disciplina.
   Cambiar el texto del LIKE por el evento que pregunten. */
SELECT eo.anio, e.nombre AS evento, a.nombre AS atleta, n.codigo_noc, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
LEFT JOIN olympics.NOC n          ON n.id_noc      = p.id_noc
WHERE p.medalla = N'Gold'
  AND eo.anio = 2024
  AND e.nombre COLLATE Latin1_General_CI_AI LIKE N'%marathon%'
ORDER BY e.nombre;
GO

/* 3.4 Para encontrar el nombre exacto de un evento antes de filtrarlo. */
SELECT DISTINCT e.nombre AS evento, dep.nombre AS deporte
FROM olympics.EVENTO e
JOIN olympics.DISCIPLINA d ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep  ON dep.id_deporte  = d.id_deporte
WHERE e.nombre COLLATE Latin1_General_CI_AI LIKE N'%100 metres%'
ORDER BY dep.nombre, e.nombre;
GO


/* ============================================================================
   4. RANKINGS DE MEDALLISTAS

   Estas consultas cuentan MEDALLAS REALES, no filas de PARTICIPACION.

   La misma medalla quedo registrada dos veces bajo las dos nomenclaturas de
   evento, con campos complementarios: una fila trae posicion y la otra trae
   edad. Dentro de un grupo (atleta, ano, disciplina, medalla), si hay n filas
   con posicion y n con edad, el numero real es n.

   Sin esta correccion el top sale mal desde el segundo puesto: Ray Ewry
   aparece con 20 oros cuando sus oros reales son 10.

   La misma logica esta dentro de sp_historial_atleta. Detalle en
   documentacion_d.md seccion 5.2.
============================================================================ */

/* Vista auxiliar en linea: medallas reales por atleta y tipo.
   Se repite en cada consulta para que cada bloque sea autonomo. */

/* 4.1 Atletas con mas medallas de oro.
   Verificado el 2026-09-15: Phelps 23, Ray Ewry 10, Latynina 9, Ledecky 9,
   Nurmi 9, Spitz 9, Carl Lewis 9.

   OJO para la defensa: Larysa Latynina aparece DOS VECES, como id 28985 y como
   164169, las dos con 9 oros y 18 medallas. No es un error de esta consulta:
   es el hallazgo 3, dos registros de atleta para la misma persona. El SP no
   puede fusionarlos porque eso es identidad, no conteo de filas. */
WITH g AS (
    SELECT p.id_atleta, p.medalla, COUNT(*) AS filas,
           /* Misma regla que el SP: se cuentan los eventos de la familia
              canonica (nombre con calificador entre parentesis) y solo si el
              grupo no tiene ninguna se cuentan los de la descriptiva.
              Ver documentacion_d.md seccion 5.2. */
           CASE WHEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END)
                ELSE SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 0 ELSE 1 END)
                END AS reales
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, p.id_edicion, e.id_disciplina, p.medalla
)
SELECT TOP 10
       a.id_atleta, a.nombre,
       SUM(CASE WHEN g.medalla = N'Gold' THEN g.reales ELSE 0 END) AS oro,
       SUM(g.reales)                                               AS total_medallas,
       SUM(g.filas)                                                AS filas_origen
FROM g
JOIN olympics.ATLETA a ON a.id_atleta = g.id_atleta
GROUP BY a.id_atleta, a.nombre
ORDER BY oro DESC, total_medallas DESC, a.nombre;
GO

/* 4.2 Variante por tipo de medalla: cambiar 'Silver' por 'Bronze'. */
WITH g AS (
    SELECT p.id_atleta, p.medalla, COUNT(*) AS filas,
           /* Misma regla que el SP: se cuentan los eventos de la familia
              canonica (nombre con calificador entre parentesis) y solo si el
              grupo no tiene ninguna se cuentan los de la descriptiva.
              Ver documentacion_d.md seccion 5.2. */
           CASE WHEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END)
                ELSE SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 0 ELSE 1 END)
                END AS reales
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, p.id_edicion, e.id_disciplina, p.medalla
)
SELECT TOP 10
       a.id_atleta, a.nombre,
       SUM(CASE WHEN g.medalla = N'Silver' THEN g.reales ELSE 0 END) AS plata,
       SUM(g.reales)                                                 AS total_medallas
FROM g
JOIN olympics.ATLETA a ON a.id_atleta = g.id_atleta
GROUP BY a.id_atleta, a.nombre
ORDER BY plata DESC, total_medallas DESC, a.nombre;
GO

/* 4.3 Variante acotada a un deporte. Cambiar el nombre del deporte. */
WITH g AS (
    SELECT p.id_atleta, p.medalla, dep.nombre AS deporte, COUNT(*) AS filas,
           /* Misma regla que el SP: se cuentan los eventos de la familia
              canonica (nombre con calificador entre parentesis) y solo si el
              grupo no tiene ninguna se cuentan los de la descriptiva.
              Ver documentacion_d.md seccion 5.2. */
           CASE WHEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END)
                ELSE SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 0 ELSE 1 END)
                END AS reales
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
    JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
    JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
    WHERE p.medalla IS NOT NULL
      AND dep.nombre COLLATE Latin1_General_CI_AI = N'Gymnastics'
    GROUP BY p.id_atleta, p.id_edicion, e.id_disciplina, p.medalla, dep.nombre
)
SELECT TOP 10
       a.id_atleta, a.nombre, g.deporte,
       SUM(CASE WHEN g.medalla = N'Gold'   THEN g.reales ELSE 0 END) AS oro,
       SUM(CASE WHEN g.medalla = N'Silver' THEN g.reales ELSE 0 END) AS plata,
       SUM(CASE WHEN g.medalla = N'Bronze' THEN g.reales ELSE 0 END) AS bronce,
       SUM(g.reales)                                                 AS total
FROM g
JOIN olympics.ATLETA a ON a.id_atleta = g.id_atleta
GROUP BY a.id_atleta, a.nombre, g.deporte
ORDER BY oro DESC, total DESC, a.nombre;
GO

/* 4.4 Medallero por pais.
   Ojo: cuenta preseas entregadas a atletas, no medallas oficiales del pais.
   En deportes de equipo cada integrante suma una fila; la medalla oficial del
   pais es una sola. Esa distincion la resuelve el SP del inciso e. */
WITH g AS (
    SELECT p.id_atleta, p.id_noc, p.medalla, COUNT(*) AS filas,
           /* Misma regla que el SP: se cuentan los eventos de la familia
              canonica (nombre con calificador entre parentesis) y solo si el
              grupo no tiene ninguna se cuentan los de la descriptiva.
              Ver documentacion_d.md seccion 5.2. */
           CASE WHEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 1 ELSE 0 END)
                ELSE SUM(CASE WHEN e.nombre LIKE N'%(%)' THEN 0 ELSE 1 END)
                END AS reales
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, p.id_noc, p.id_edicion, e.id_disciplina, p.medalla
)
SELECT TOP 15
       n.codigo_noc, eg.nombre AS pais,
       SUM(CASE WHEN g.medalla = N'Gold'   THEN g.reales ELSE 0 END) AS oro,
       SUM(CASE WHEN g.medalla = N'Silver' THEN g.reales ELSE 0 END) AS plata,
       SUM(CASE WHEN g.medalla = N'Bronze' THEN g.reales ELSE 0 END) AS bronce,
       SUM(g.reales)                                                 AS preseas
FROM g
JOIN olympics.NOC n                      ON n.id_noc      = g.id_noc
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
GROUP BY n.codigo_noc, eg.nombre
ORDER BY oro DESC, plata DESC, bronce DESC;
GO


/* ============================================================================
   5. EL MAS JOVEN EN GANAR ORO   (usa el campo edad)
============================================================================ */

/* 5.1 Los oros mas jovenes registrados.
   Verificado: el minimo es 13 anos, con varios casos.
   Entre ellos Marjorie Gestring (1936, Diving Springboard), que es la
   medallista de oro mas joven de la historia olimpica segun olympics.com.
   edad viene NULL en muchas filas, por eso se filtra. */
SELECT TOP 15
       p.edad,
       a.nombre       AS atleta,
       eo.anio,
       eo.temporada,
       dep.nombre     AS deporte,
       e.nombre       AS evento,
       n.codigo_noc
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta     = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
LEFT JOIN olympics.NOC n          ON n.id_noc        = p.id_noc
WHERE p.medalla = N'Gold'
  AND p.edad IS NOT NULL
ORDER BY p.edad ASC, eo.anio;
GO

/* 5.2 El mas viejo: mismo orden invertido. */
SELECT TOP 10
       p.edad, a.nombre AS atleta, eo.anio, dep.nombre AS deporte, e.nombre AS evento
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta     = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
WHERE p.medalla = N'Gold' AND p.edad IS NOT NULL
ORDER BY p.edad DESC, eo.anio;
GO

/* 5.3 Edad promedio de los medallistas de oro por deporte. */
SELECT TOP 15
       dep.nombre AS deporte,
       COUNT(*)                          AS oros_con_edad,
       CAST(AVG(p.edad) AS DECIMAL(5,2)) AS edad_promedio,
       MIN(p.edad)                       AS mas_joven,
       MAX(p.edad)                       AS mas_viejo
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e     ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep  ON dep.id_deporte  = d.id_deporte
WHERE p.medalla = N'Gold' AND p.edad IS NOT NULL
GROUP BY dep.nombre
HAVING COUNT(*) >= 50
ORDER BY edad_promedio ASC;
GO


/* ============================================================================
   6. GANADORES POR ANO, TEMPORADA Y PAIS
============================================================================ */

/* 6.1 Los cinco valores reales de temporada.
   Verificado: Summer 30, Winter 24, Summer Youth 3, Winter Youth 3,
   Intercalated Games 1. No existe "otono". */
SELECT temporada, COUNT(*) AS ediciones, MIN(anio) AS desde, MAX(anio) AS hasta
FROM olympics.EDICION_OLIMPICA
GROUP BY temporada
ORDER BY ediciones DESC;
GO

/* 6.2 Quienes ganaron oro en un ano, temporada y pais concretos.
   Cambiar los tres valores segun lo que pregunten. */
DECLARE @anio       SMALLINT     = 2024,
        @temporada  NVARCHAR(30) = N'Summer',
        @noc        CHAR(3)      = 'GUA';

SELECT eo.anio, eo.temporada, s.nombre AS sede,
       a.nombre AS atleta, dep.nombre AS deporte, e.nombre AS evento, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
JOIN olympics.ATLETA a            ON a.id_atleta     = p.id_atleta
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
JOIN olympics.NOC n               ON n.id_noc        = p.id_noc
LEFT JOIN olympics.SEDE s         ON s.id_sede       = eo.id_sede
WHERE p.medalla   = N'Gold'
  AND eo.anio     = @anio
  AND eo.temporada = @temporada
  AND n.codigo_noc = @noc
ORDER BY dep.nombre, e.nombre;
GO

/* 6.3 Medallero de una edicion completa (todos los paises de un ano). */
SELECT TOP 20
       n.codigo_noc, eg.nombre AS pais,
       SUM(CASE WHEN p.medalla = N'Gold'   THEN 1 ELSE 0 END) AS oro,
       SUM(CASE WHEN p.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata,
       SUM(CASE WHEN p.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronce
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo        ON eo.id_edicion = p.id_edicion
JOIN olympics.NOC n                      ON n.id_noc      = p.id_noc
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
WHERE p.medalla IS NOT NULL
  AND eo.anio = 2024 AND eo.temporada = N'Summer'
GROUP BY n.codigo_noc, eg.nombre
ORDER BY oro DESC, plata DESC, bronce DESC;
GO

/* 6.4 Las sedes: que ciudades han organizado y en que anos. */
SELECT s.nombre AS sede, eg.nombre AS pais,
       COUNT(*) AS veces,
       STRING_AGG(CAST(eo.anio AS NVARCHAR(4)) + N' ' + eo.temporada, N', ')
           WITHIN GROUP (ORDER BY eo.anio) AS ediciones
FROM olympics.EDICION_OLIMPICA eo
JOIN olympics.SEDE s                     ON s.id_sede     = eo.id_sede
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = s.id_pais
GROUP BY s.nombre, eg.nombre
HAVING COUNT(*) > 1
ORDER BY veces DESC, s.nombre;
GO


/* ============================================================================
   7. NOTAS DE CALIDAD DEL DATO

   1. CONTEO DE MEDALLAS -- corregido en las consultas de la seccion 4 y
      dentro de sp_historial_atleta.

      La misma medalla quedo registrada dos veces bajo las dos nomenclaturas
      de evento. El ETL corrigio 1,015 pares confirmados, pero el patron
      persiste en el resto. Sin correccion, Ray Ewry sale con 20 oros cuando
      son 10, y Jenny Thompson con 24 medallas cuando son 12.

      La regla usada cuenta pares de posicion/edad dentro de un grupo
      (atleta, ano, disciplina, medalla). Validada contra las nueve
      regresiones del equipo: Phelps 23/3/2=28, Latynina 9/5/4=18,
      Bjorgen 8/4/3=15, Andrianov 7/5/3=15, Thompson 8/3/1=12, Nurmi
      9/3/0=12, Spitz 9/1/1=11, Ewry 10/0/0=10, Bolt 8/0/0=8.
      Las nueve dan exacto.

      La columna filas_origen deja el conteo auditable: si es mayor que el
      total, ese atleta tenia duplicados.

   2. CONTEO DE PARTICIPACIONES -- sigue inflado, sin corregir.

      La misma regla NO se puede aplicar aqui. En las filas sin medalla todas
      tienen medalla = NULL, asi que un atleta con varios eventos distintos en
      el mismo ano y disciplina cae en un solo grupo y contar pares deja de
      significar algo. Medido: Bolt daria 11 cuando son 10, Nurmi 15 cuando
      son 12.

      Corresponde al ETL. Reportado en evidencia/hallazgos_reportados.md.

   3. ATLETAS HOMONIMOS -- 48,370 nombres repetidos entre atletas distintos.
      Usain Bolt existe como 10 id_atleta, Eric Lemming como 23. Por eso el
      SP devuelve lista de candidatos y permite desempatar con @id_atleta.

   4. PARTICIPACIONES IMPOSIBLES -- 784 filas posteriores a la fecha de
      fallecimiento del atleta, en 781 atletas. Andrianov, muerto en 2011,
      tiene una fila de kayak femenino por CHN en 2020. No se filtran
      automaticamente: la decision corresponde al ETL.

   Lo que SI es plenamente confiable:
     - el medallero de Guatemala (3 medallas, verificado);
     - los ganadores de un evento y ano concretos (secciones 3 y 6);
     - el historial individual consultado con @id_atleta;
     - los rankings de la seccion 4, ya corregidos.
============================================================================ */
