-- Pruebas de sp_historial_atleta. Inciso d) - Grupo 7 - Valery Alarcon.
-- Ejecutar despues de crear el procedimiento; cada bloque se corre por separado desde SSMS (seleccionar y F5).
-- Base vigente: 336,418 atletas / 2,986 eventos / 712,020 participaciones / total 1,069,251.

USE OlimpiadasDB;
GO

-- T1. Nombre exacto, un solo atleta, solo medallas. Esperado: Michael Phelps 93113, medallero 23/3/2 = 28, filas_origen 28, grupos_indeterminados 0.
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @solo_medallistas    = 1;
GO

-- T2. El mismo atleta sin filtro de medallas. Esperado: participaciones 30, total_medallas 28, ediciones 5, deportes 1, de 2000 a 2016.
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1;
GO

-- T3. Busqueda ambigua: 'Messi' coincide con 26 atletas. Esperado: 2 result sets (aviso + candidatos), sin el detalle.
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @max_atletas   = 5;
GO

-- T4. Desempate por id. Esperado: solo Lionel Messi 110178, nacido 1987-06-24, 2008 Summer ARG, posicion 1, Gold.
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @id_atleta     = 110178;
GO

-- T5. Insensibilidad a acentos, la razon del COLLATE Latin1_General_CI_AI. Esperado: 182 con la colacion de la base, 223 con la del SP.
SELECT 'colacion base CI_AS' AS variante, COUNT(*) AS atletas
FROM olympics.ATLETA WHERE nombre LIKE N'%Elie%'
UNION ALL
SELECT 'colacion del SP CI_AI', COUNT(*)
FROM olympics.ATLETA WHERE nombre COLLATE Latin1_General_CI_AI LIKE N'%Elie%';
GO

EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Elie, Comte de Lastours',
     @max_atletas   = 10;
GO

-- T5b. El mismo COLLATE en @deporte: Glima es el unico deporte con acento y debe encontrarse sin el. Para @pais no aplica: ningun pais ni NOC de la base lleva acentos.
SELECT 'deportes con caracteres no ASCII' AS dato, nombre FROM olympics.DEPORTE
WHERE nombre COLLATE Latin1_General_BIN2 LIKE N'%[^ -~]%';
GO

EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Sigurjon Petursson',
     @deporte       = N'Glima';
GO

-- T6. Los tres filtros del enunciado: deporte, pais y ano. Esperado: solo Guy Forget 17, porque los homonimos quedaron sin participaciones.
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Guy Forget',
     @deporte       = N'Tennis',
     @pais          = N'FRA',
     @anio          = 1992;
GO

-- T7. Filtro de pais en sus tres formas: codigo NOC, nombre del NOC y nombre de la entidad geografica.
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'USA';
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'United States';
GO

-- T8. Dominio de temporada: son cinco valores, no dos. Esperado: Summer 30, Winter 24, Summer Youth 3, Winter Youth 3, Intercalated Games 1.
SELECT temporada, COUNT(*) AS ediciones, MIN(anio) AS desde, MAX(anio) AS hasta
FROM olympics.EDICION_OLIMPICA GROUP BY temporada ORDER BY COUNT(*) DESC;
GO

-- T9. Sin coincidencias. Esperado: 1 result set con el aviso, sin error.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Zzzzz Noexiste';
GO

-- T10. Filtros que no dejan ninguna fila. Esperado: aviso con los filtros aplicados, distinguible de 'el atleta no existe'.
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio                = 1924;
GO

-- T11. Validaciones de parametros: las cuatro deben lanzar RAISERROR con mensaje claro, no un resultado vacio enganoso.
BEGIN TRY EXEC olympics.sp_historial_atleta @nombre_atleta = N'   '; END TRY
BEGIN CATCH SELECT N'nombre vacio' AS prueba, ERROR_MESSAGE() AS mensaje; END CATCH;
GO

BEGIN TRY EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @medalla=N'Oro'; END TRY
BEGIN CATCH SELECT N'medalla invalida' AS prueba, ERROR_MESSAGE() AS mensaje; END CATCH;
GO

BEGIN TRY EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @temporada=N'Otono'; END TRY
BEGIN CATCH SELECT N'temporada invalida' AS prueba, ERROR_MESSAGE() AS mensaje; END CATCH;
GO

BEGIN TRY EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @anio_desde=2012, @anio_hasta=2004; END TRY
BEGIN CATCH SELECT N'rango invertido' AS prueba, ERROR_MESSAGE() AS mensaje; END CATCH;
GO

-- T12. Comodines neutralizados: un '%' escrito por el usuario se busca literal. Esperado: los tres sin resultados, nunca la tabla completa.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'%';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1, @deporte = N'%';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1, @pais = N'%';
GO

-- T13. Tope de @max_atletas: nulo o menor o igual a 0 pasa a 25, y el maximo se acota a 500.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi', @max_atletas = 0;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi', @max_atletas = 99999;
GO

-- T14. Atleta sin ninguna participacion, hay 744 en la base. Esperado: ficha con participaciones = 0 y detalle vacio, sin error.
SELECT TOP 3 a.id_atleta, a.nombre
FROM olympics.ATLETA a
WHERE NOT EXISTS (SELECT 1 FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta);
GO

-- T15. Rendimiento: la busqueda por nombre hace scan de ATLETA (336,418 filas) porque no hay indice por nombre y el COLLATE impediria usarlo.
DECLARE @t0 DATETIME2(7) = SYSDATETIME();
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
SELECT DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS ms_total;
GO

-- T16. Juegos Intercalados: 1906 existe como 'Intercalated Games' y no hay un '1906 Summer'. Esperado: todas las filas con anio 1906 y esa temporada.
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Eric Lemming',
     @anio          = 1906;
GO

SELECT anio, temporada FROM olympics.EDICION_OLIMPICA WHERE anio = 1906;
GO

-- T17. Los Juegos de la Juventud son temporadas aparte: Chad le Clos 119877 tiene 8 en Summer Youth y 11 en Summer, porque @temporada usa igualdad exacta.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Chad le Clos', @temporada = N'Summer Youth';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Chad le Clos', @temporada = N'Summer';
GO

-- T18. NOC historico: Andrianov 31000 con @pais='URS' da 24 participaciones y 15 medallas (7/5/3); la fila 25 es un kayak CHN 2020 imposible, hallazgo 4.
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Nikolay Andrianov',
     @pais          = N'URS';
GO

SELECT n.codigo_noc, n.nombre_noc, eg.nombre AS entidad
FROM olympics.NOC n
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
WHERE n.codigo_noc IN (N'URS', N'EUN', N'GDR', N'FRG', N'GER', N'TCH', N'YUG')
ORDER BY eg.nombre, n.codigo_noc;
GO

-- T19. Rango de anos mas tipo de medalla. Esperado para Phelps: 18 filas Gold entre 2004 y 2012 (6 + 8 + 4).
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio_desde          = 2004,
     @anio_hasta          = 2012,
     @medalla             = N'Gold';
GO

-- T20. La correccion en el caso extremo: Ray Ewry tiene 20 filas de oro y 10 oros reales. La primera consulta muestra los pares crudos, la segunda el SP con filas_origen 20.
SELECT eo.anio, e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
WHERE a.nombre = N'Ray Ewry' AND p.medalla = N'Gold'
ORDER BY eo.anio, e.nombre;
GO

EXEC olympics.sp_historial_atleta @nombre_atleta = N'Ray Ewry', @coincidencia_exacta = 1;
GO

-- T21. Las nueve regresiones del equipo: replica la logica del medallero del SP; las nueve deben coincidir con la columna esperado.
DECLARE @ids TABLE (id BIGINT, nombre NVARCHAR(60), esperado NVARCHAR(20));
INSERT INTO @ids VALUES
 (93113,  N'Michael Phelps',    N'23/3/2 = 28'),
 (77795,  N'Ray Ewry',          N'10/0/0 = 10'),
 (50859,  N'Jenny Thompson',    N'8/3/1 = 12'),
 (104492, N'Usain Bolt',        N'8/0/0 = 8'),
 (67218,  N'Paavo Nurmi',       N'9/3/0 = 12'),
 (51214,  N'Mark Spitz',        N'9/1/1 = 11'),
 (31000,  N'Nikolay Andrianov', N'7/5/3 = 15'),
 (100161, N'Marit Bjorgen',     N'8/4/3 = 15'),
 (164169, N'Larysa Latynina',   N'9/5/4 = 18');

SELECT i.nombre, i.esperado,
       SUM(CASE WHEN g.medalla = 'Gold'   THEN g.reales ELSE 0 END) AS oro,
       SUM(CASE WHEN g.medalla = 'Silver' THEN g.reales ELSE 0 END) AS plata,
       SUM(CASE WHEN g.medalla = 'Bronze' THEN g.reales ELSE 0 END) AS bronce,
       SUM(g.reales) AS total,
       SUM(g.filas)  AS filas_origen
FROM @ids i
JOIN (
    SELECT p.id_atleta, p.medalla, COUNT(*) AS filas,
           CASE WHEN SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END) > 0
                 AND SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END) > 0
                 AND SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END)
                   = SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END)
                THEN SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END)
                ELSE COUNT(*) END AS reales
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, eo.anio, e.id_disciplina, p.medalla
) g ON g.id_atleta = i.id
GROUP BY i.nombre, i.esperado
ORDER BY total DESC;
GO

-- T22. Normalizacion del separador U+2022, presente en 145,500 filas de nombre_usado y 30,706 de nombre_original. Esperado: Cristiano 102010 y Messi 110178, un atleta cada uno.
SELECT 'nombre_usado'    AS columna, COUNT(*) AS filas_con_separador
FROM olympics.ATLETA WHERE nombre_usado    LIKE N'%' + NCHAR(8226) + N'%'
UNION ALL
SELECT 'nombre_original', COUNT(*)
FROM olympics.ATLETA WHERE nombre_original LIKE N'%' + NCHAR(8226) + N'%';
GO

EXEC olympics.sp_historial_atleta @nombre_atleta = N'Cristiano Ronaldo', @coincidencia_exacta = 1;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Lionel Messi',      @coincidencia_exacta = 1;
GO

-- T23. Guatemala tras la correccion canonica. Esperado: 594 participaciones, 263 atletas, 20 ediciones; son 20 en 19 anios porque 1988 cuenta Winter y Summer.
SELECT COUNT(*)                     AS participaciones,
       COUNT(DISTINCT p.id_atleta)  AS atletas,
       COUNT(DISTINCT p.id_edicion) AS ediciones
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n ON n.id_noc = p.id_noc
WHERE n.codigo_noc = N'GUA';
GO

-- T24. Ray Ewry: 10 oros en la base contra los 8 que acredita el COI, porque Atenas 1906 esta como 'Intercalated Games'. Esperado: sin filtro 10/0/0 y filas_origen 20; con @temporada='Summer' 8/0/0 y filas_origen 16.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Ray Ewry';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Ray Ewry', @temporada = N'Summer';
GO

-- T25. La correccion de participaciones, contra casos de verdad comprobable. Esperado: Bolt 12 filas -> 10, Guy Forget 9 -> 5, Ray Ewry 23 -> 13, Phelps 30 -> 30 sin cambio.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Usain Bolt',     @id_atleta = 104492;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Guy Forget',     @id_atleta = 17;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
GO

-- T26. Las dos familias de nombre de evento, que son la base de la regla. Esperado: Bolt 2004 aparece dos veces, como '200 metres, Men (Olympic)' con posicion y como 'Athletics Men''s 200 metres' con edad.
SELECT eo.anio, ev.nombre AS evento,
       CASE WHEN ev.nombre LIKE N'%(%)' THEN N'canonica' ELSE N'descriptiva' END AS familia,
       p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev           ON ev.id_evento  = p.id_evento
WHERE p.id_atleta = 104492
ORDER BY eo.anio, ev.nombre;
GO

-- T27. La marca de participaciones imposibles. Esperado: Andrianov con 8 filas de gimnasia URS 1980 en posterior_a_fallecimiento = 0 y la fila de kayak CHN 2020 en 1; fallecio en 2011. No se filtra ninguna.
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Nikolay Andrianov', @id_atleta = 31000;
GO

SELECT COUNT(*) AS filas_imposibles, COUNT(DISTINCT p.id_atleta) AS atletas
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE a.fecha_fallecimiento IS NOT NULL
  AND eo.anio > YEAR(a.fecha_fallecimiento);
GO
