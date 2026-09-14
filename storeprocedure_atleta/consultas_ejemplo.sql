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

/* 1.3 Ronaldo.
   "Ronaldo" devuelve varios atletas distintos. El Ronaldo brasileno
   (Ronaldo Nazario) gano bronce en Atlanta 1996; aparece con mas de un
   id_atleta por la duplicacion de homonimos.
   Cristiano Ronaldo NO esta en el dataset. */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Ronaldo', @max_atletas = 30;
GO

/* 1.4 Quien mas busquen: solo cambiar el nombre.
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
     2024 Summer  Pierre Brol      Trap, Men                      Bronze */
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
   Verificado: 1,232 participaciones de 802 atletas distintos. */
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

   LEER LA SECCION 7 ANTES DE USAR ESTAS CONSULTAS EN VIVO.
   Los conteos estan inflados para la mayoria de atletas por duplicacion
   pendiente en el dato de origen.
============================================================================ */

/* 4.1 Atletas con mas medallas de oro. */
SELECT TOP 10
       a.id_atleta, a.nombre,
       SUM(CASE WHEN p.medalla = N'Gold' THEN 1 ELSE 0 END) AS oro
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
WHERE p.medalla IS NOT NULL
GROUP BY a.id_atleta, a.nombre
ORDER BY oro DESC, a.nombre;
GO

/* 4.2 Variante por tipo de medalla: cambiar 'Silver' o 'Bronze'. */
SELECT TOP 10
       a.id_atleta, a.nombre,
       SUM(CASE WHEN p.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
WHERE p.medalla IS NOT NULL
GROUP BY a.id_atleta, a.nombre
ORDER BY plata DESC, a.nombre;
GO

/* 4.3 Variante acotada a un deporte. Al restringir el deporte, el ranking
   es mas manejable y facil de cotejar con olympics.com. */
SELECT TOP 10
       a.id_atleta, a.nombre, dep.nombre AS deporte,
       SUM(CASE WHEN p.medalla = N'Gold'   THEN 1 ELSE 0 END) AS oro,
       SUM(CASE WHEN p.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata,
       SUM(CASE WHEN p.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronce,
       COUNT(*)                                               AS total
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta     = p.id_atleta
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
JOIN olympics.DEPORTE dep         ON dep.id_deporte  = d.id_deporte
WHERE p.medalla IS NOT NULL
  AND dep.nombre COLLATE Latin1_General_CI_AI = N'Gymnastics'
GROUP BY a.id_atleta, a.nombre, dep.nombre
ORDER BY oro DESC, total DESC;
GO

/* 4.4 Medallero por pais. Ojo: cuenta preseas entregadas a atletas, no
   medallas oficiales del pais (en deportes de equipo cada integrante
   suma una fila). */
SELECT TOP 15
       n.codigo_noc, eg.nombre AS pais,
       SUM(CASE WHEN p.medalla = N'Gold'   THEN 1 ELSE 0 END) AS oro,
       SUM(CASE WHEN p.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata,
       SUM(CASE WHEN p.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronce,
       COUNT(*)                                               AS preseas
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n                      ON n.id_noc      = p.id_noc
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
WHERE p.medalla IS NOT NULL
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
   7. NOTAS DE CALIDAD DEL DATO   (leer antes de usar la seccion 4)

   Los conteos de medallas por atleta estan inflados para la mayoria de los
   casos. La misma medalla quedo registrada dos veces bajo las dos
   nomenclaturas de evento: una fila trae posicion y la otra trae edad.

   Ejemplo verificado: Ray Ewry aparece con 20 oros y los reales son 10.

     Michael Phelps  23 oros  -> correcto (fue uno de los casos corregidos)
     Ray Ewry        20 oros  -> reales 10
     Jenny Thompson  16 oros  -> reales 8
     Carl Lewis      16 oros  -> reales 9

   Alcance aproximado: unos 14,963 atletas afectados.

   NO se puede corregir desde la consulta: las dos filas tienen id_evento
   distinto, asi que ningun DISTINCT las junta sin colapsar medallas
   legitimamente diferentes. Se evaluo filtrar por "posicion IS NOT NULL",
   que da el numero correcto en varios atletas, pero se descarto: perderia
   37,721 filas de medalla legitimas en deportes de equipo y relevos, donde
   la posicion nunca se registro.

   Corresponde al ETL. Reportado en evidencia/hallazgos_reportados.md.

   Lo que SI es confiable:
     - el medallero de Guatemala (3 medallas, verificado);
     - los ganadores de un evento y ano concretos (secciones 3 y 6);
     - el historial individual consultado con @id_atleta;
     - Michael Phelps y el resto de los casos corregidos.

   Recomendacion para la defensa: preferir consultas acotadas a un evento,
   ano o pais, que no dependen del conteo agregado por atleta.
============================================================================ */
