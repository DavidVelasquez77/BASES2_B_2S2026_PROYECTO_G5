/* ============================================================================
   PRUEBAS DE sp_historial_atleta
   Inciso d) - Grupo 7 - Valery Alarcon

   Ejecutar despues de crear el procedimiento con sp_historial_atleta.sql.
   Cada bloque se corre por separado desde SSMS (seleccionar y F5).

   Los valores esperados corresponden a la base vigente:
   336,418 atletas / 2,986 eventos / 712,658 participaciones.
============================================================================ */

USE OlimpiadasDB;
GO

/* ----------------------------------------------------------------------------
   T1. Caso feliz: nombre exacto, un solo atleta, solo medallas.
   Esperado: Michael Phelps, id 93113, medallero 23 / 3 / 2 = 28.
   Es el caso de regresion que define la revision final del equipo.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @solo_medallistas    = 1;
GO

/* ----------------------------------------------------------------------------
   T2. El mismo atleta sin filtro de medallas.
   Esperado: participaciones 30, total_medallas 28, ediciones 5,
   deportes 1, primer_ano 2000, ultimo_ano 2016.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1;
GO

/* ----------------------------------------------------------------------------
   T3. Busqueda ambigua: "Messi" coincide con 26 atletas distintos
   (se busca tambien en nombre_completo y nombre_usado).
   Esperado: 2 result sets (aviso + lista de candidatos), NO el detalle.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @max_atletas   = 5;
GO

/* ----------------------------------------------------------------------------
   T4. Desempate por id tras una busqueda ambigua.
   Esperado: solo Lionel Messi (110178), nacido 1987-06-24, una participacion
   en 2008 Summer con ARG, posicion 1, Gold.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @id_atleta     = 110178;
GO

/* ----------------------------------------------------------------------------
   T5. Insensibilidad a acentos (la razon del COLLATE Latin1_General_CI_AI).
   La colacion de la base ignora mayusculas pero distingue acentos.
   Esperado: 182 con la colacion de la base, 223 con la del SP.
---------------------------------------------------------------------------- */
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

/* ----------------------------------------------------------------------------
   T5b. El mismo COLLATE aplica al filtro @deporte.
   La revision final pide probar filtros de texto con y sin acentos.

   El unico deporte con acento en la base es Glima (lucha islandesa, 3
   participaciones en 1908 y 1912). Buscarlo SIN acento debe encontrarlo.

   Nota: la prueba equivalente para @pais no se puede hacer porque ningun
   nombre de pais ni de NOC de esta base lleva acentos (estan todos en
   ingles: Germany, Russian Federation). El COLLATE se aplica igual por
   consistencia, pero ahi no hay nada que recuperar.
---------------------------------------------------------------------------- */
SELECT 'deportes con acento' AS dato, nombre FROM olympics.DEPORTE
WHERE nombre COLLATE Latin1_General_CI_AS <> nombre COLLATE Latin1_General_CI_AI;
GO

EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Sigurjon Petursson',
     @deporte       = N'Glima';
GO

/* ----------------------------------------------------------------------------
   T6. Los tres filtros que menciona el enunciado: deporte, pais y ano.
   Esperado: solo Guy Forget id 17 (los otros tres id homonimos quedaron
   sin participaciones tras la consolidacion).
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Guy Forget',
     @deporte       = N'Tennis',
     @pais          = N'FRA',
     @anio          = 1992;
GO

/* ----------------------------------------------------------------------------
   T7. Filtro de pais en sus tres formas aceptadas:
   codigo NOC / nombre del NOC / nombre de la entidad geografica.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'USA';
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'United States';
GO

/* ----------------------------------------------------------------------------
   T8. Dominio de temporada: cinco valores, no dos.
   Esperado: Summer 30, Winter 24, Summer Youth 3, Winter Youth 3,
   Intercalated Games 1.
---------------------------------------------------------------------------- */
SELECT temporada, COUNT(*) AS ediciones, MIN(anio) AS desde, MAX(anio) AS hasta
FROM olympics.EDICION_OLIMPICA GROUP BY temporada ORDER BY COUNT(*) DESC;
GO

/* ----------------------------------------------------------------------------
   T9. Sin coincidencias. Esperado: 1 result set con el aviso, sin error.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Zzzzz Noexiste';
GO

/* ----------------------------------------------------------------------------
   T10. Filtros que no dejan ninguna fila. Esperado: aviso con los filtros
   aplicados, distinguible de "el atleta no existe".
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio                = 1924;
GO

/* ----------------------------------------------------------------------------
   T11. Validaciones de parametros. Las cuatro deben lanzar RAISERROR con
   mensaje claro, no devolver un resultado vacio enganoso.
---------------------------------------------------------------------------- */
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

/* ----------------------------------------------------------------------------
   T12. Comodines neutralizados en los tres filtros parciales.
   Un '%' escrito por el usuario debe buscarse literal y no devolver todo.
   Esperado: los tres sin coincidencias o sin resultados, nunca la tabla completa.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'%';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1, @deporte = N'%';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1, @pais = N'%';
GO

/* ----------------------------------------------------------------------------
   T13. Tope de @max_atletas. Valores nulos o <= 0 pasan a 25 y el maximo
   se acota a 500, para no devolver listas de candidatos inmanejables.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi', @max_atletas = 0;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Messi', @max_atletas = 99999;
GO

/* ----------------------------------------------------------------------------
   T14. Atleta sin ninguna participacion registrada (hay 247 en la base).
   Esperado: ficha con participaciones = 0 y detalle vacio, sin error.
---------------------------------------------------------------------------- */
SELECT TOP 3 a.id_atleta, a.nombre
FROM olympics.ATLETA a
WHERE NOT EXISTS (SELECT 1 FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta);
GO

/* ----------------------------------------------------------------------------
   T15. Rendimiento. La busqueda por nombre hace scan de ATLETA (336,418
   filas) porque no hay indice por nombre y el COLLATE impediria usarlo.
   Se mide para justificar que no se altera el modelo fisico del inciso c.
---------------------------------------------------------------------------- */
DECLARE @t0 DATETIME2(7) = SYSDATETIME();
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
SELECT DATEDIFF(MILLISECOND, @t0, SYSDATETIME()) AS ms_total;
GO

/* ----------------------------------------------------------------------------
   T16. Caso 1906 - Juegos Intercalados de Atenas.
   1906 existe como "Intercalated Games" y NO existe un "1906 Summer".
   Esperado: todas las filas con anio 1906 y esa temporada.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Eric Lemming',
     @anio          = 1906;
GO

SELECT anio, temporada FROM olympics.EDICION_OLIMPICA WHERE anio = 1906;
GO

/* ----------------------------------------------------------------------------
   T17. Caso Youth - los Juegos de la Juventud se conservaron y son
   temporadas distintas.
   Chad le Clos (119877) tiene 8 participaciones en Summer Youth y 11 en
   Summer. @temporada usa igualdad exacta: 'Summer' no incluye 'Summer Youth'.
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Chad le Clos', @temporada = N'Summer Youth';
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Chad le Clos', @temporada = N'Summer';
GO

/* ----------------------------------------------------------------------------
   T18. NOC historico - NOC y pais no son lo mismo.
   Nikolay Andrianov (31000) compitio por la URSS. Con @pais = 'URS' el SP
   devuelve 24 participaciones y 15 medallas (7/5/3). En el detalle debe verse
   codigo_noc = URS con pais_representado = Russian Federation y
   equipo = Soviet Union.

   Nota: la tabla tiene 25 filas para este id, no 24. La fila 25 es una
   participacion de kayak femenino por CHN en 2020, imposible para un
   gimnasta sovietico fallecido en 2011. El filtro por NOC la deja fuera.
   Es el hallazgo 4 de evidencia/hallazgos_reportados.md.
---------------------------------------------------------------------------- */
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

/* ----------------------------------------------------------------------------
   T19. Rango de anos y tipo de medalla.
   Responde de una pasada el tipo de pregunta que puede salir en la defensa:
   "sus medallas de oro entre 2004 y 2012".
   Esperado para Phelps: 18 filas Gold (6 + 8 + 4).
---------------------------------------------------------------------------- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio_desde          = 2004,
     @anio_hasta          = 2012,
     @medalla             = N'Gold';
GO

/* ----------------------------------------------------------------------------
   T20. Limitacion conocida: duplicacion de medallas pendiente en el dato.
   El SP reporta fielmente PARTICIPACION, asi que refleja el problema.
   Ray Ewry aparece con 20 filas de oro cuando sus oros reales son 10.
   Detalle en evidencia/hallazgos_reportados.md.
---------------------------------------------------------------------------- */
SELECT eo.anio, e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.ATLETA a            ON a.id_atleta   = p.id_atleta
WHERE a.nombre = N'Ray Ewry' AND p.medalla = N'Gold'
ORDER BY eo.anio, e.nombre;
GO
