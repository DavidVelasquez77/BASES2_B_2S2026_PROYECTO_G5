/* ===
   PRUEBAS DE sp_historial_atleta
   Inciso d)
=== */

USE OlimpiadasDB;
GO

/* ---
   T1. Caso feliz: nombre exacto, un solo atleta, solo medallas.
   Esperado: 3 result sets. Michael Phelps, id 93113.

   En el medallero (result set 2) se ven las dos cifras lado a lado:
     crudo    : oro 46  plata 6  bronce 4  total 56
     estimado : oro 23  plata 3  bronce 2  total 28
     diagnostico: "duplicado detectado y descontado"

   El estimado coincide con la cifra real de Phelps en los tres desgloses.
   Ver seccion 5.1 de documentacion_d.md.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @solo_medallistas    = 1;
GO

/* ---
   T1b. El mismo atleta SIN filtro de medallas, para ver la correccion de
   `participaciones` en la ficha (result set 1).

   Esperado:
     participaciones           60   ->  participaciones_estimado  30
     total_medallas            56   ->  total_medallas_estimado   28
     ediciones  5      deportes 1      2000 - 2016

   Las 30 participaciones son sus eventos reales: 1 en Sydney 2000 + 8 + 8 + 7 + 6.
   `ediciones` y `deportes` no necesitan correccion porque usan COUNT(DISTINCT).

   El tercer result set devuelve 60 filas: es fiel al dato y no fusiona los
   duplicados. Esa es la frontera del metodo (ver seccion 5.1 de documentacion_d.md).
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1;
GO

/* ---
   T2. Busqueda ambigua: "Messi" coincide con 26 atletas distintos
   (26 y no 23 porque se busca tambien en nombre_completo y nombre_usado).
   Esperado: 2 result sets (aviso + lista de candidatos), NO el detalle.
   Demuestra el control de ambiguedad.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @max_atletas   = 5;
GO

/* ---
   T3. Desempate por id tras una busqueda ambigua.
   Esperado: solo Lionel Messi (id 110178), nacido 1987-06-24,
   una participacion en 2008 Summer con ARG y medalla Gold.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Messi',
     @id_atleta     = 110178;
GO

/* ---
   T4. Insensibilidad a acentos (la razon del COLLATE Latin1_General_CI_AI).
   Se escribe "Elie" sin acento y aun asi encuentra a "Elie, Comte de Lastours".
   Comparacion directa:
     con la colacion de la base (CI_AS): 182 atletas
     con CI_AI (la que usa el SP):       223 atletas
--- */
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

/* ---
   T5. Los tres filtros que pide el enunciado: deporte, pais y ano.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Guy Forget',
     @deporte       = N'Tennis',
     @pais          = N'FRA',
     @anio          = 1992;
GO

/* ---
   T6. Filtro de pais en sus tres formas aceptadas.
   codigo NOC / nombre del NOC / nombre de la entidad geografica.
--- */
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'USA';
EXEC olympics.sp_historial_atleta @nombre_atleta=N'Michael Phelps', @coincidencia_exacta=1, @pais=N'United States';
GO

/* ---
   T7. Filtro por temporada. El dominio real tiene CINCO valores, no dos:
   Summer, Winter, Summer Youth, Winter Youth, Intercalated Games.
--- */
SELECT temporada, COUNT(*) AS ediciones, MIN(anio) AS desde, MAX(anio) AS hasta
FROM olympics.EDICION_OLIMPICA GROUP BY temporada ORDER BY COUNT(*) DESC;
GO

EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Heikki Savolainen',
     @temporada     = N'Summer';
GO

/* ---
   T8. Sin coincidencias. Esperado: 1 result set con el aviso, sin error.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Zzzzz Noexiste';
GO

/* ---
   T9. Filtros que no dejan ninguna fila. Esperado: aviso con los filtros
   aplicados, para distinguirlo de "el atleta no existe".
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio                = 1924;
GO

/* ---
   T10. Parametro obligatorio vacio. Esperado: RAISERROR, no un resultado vacio.
--- */
BEGIN TRY
    EXEC olympics.sp_historial_atleta @nombre_atleta = N'   ';
END TRY
BEGIN CATCH
    SELECT N'Error capturado correctamente' AS prueba, ERROR_MESSAGE() AS mensaje;
END CATCH;
GO

/* ---
   T11. Comodines neutralizados: un '%' escrito por el usuario debe buscarse
   literal y NO devolver la tabla completa. Esperado: sin coincidencias.
--- */
EXEC olympics.sp_historial_atleta @nombre_atleta = N'%';
GO

/* ---
   T12. Atleta sin ninguna participacion registrada (hay 241 en la base).
   Esperado: ficha con participaciones = 0 y detalle vacio, sin error.
--- */
SELECT TOP 3 a.id_atleta, a.nombre
FROM olympics.ATLETA a
WHERE NOT EXISTS (SELECT 1 FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta);
GO

/* ---
   T13. Medicion de rendimiento. La busqueda por nombre hace scan de
   ATLETA (336,419 filas) porque no existe indice por nombre y el COLLATE
   impide usarlo. Se mide para justificar que no se altera el modelo fisico.
--- */
SET STATISTICS TIME ON;
EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @coincidencia_exacta = 1;
SET STATISTICS TIME OFF;
GO

/* ---
   T14. Evidencia de la duplicidad de eventos (ver documentacion_d.md).
   Misma medalla de Phelps 2004 registrada bajo dos nomenclaturas distintas,
   con campos complementarios: una trae posicion, la otra trae edad.
--- */
SELECT e.nombre AS evento, p.posicion, p.edad, p.medalla, p.nombre_competencia
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e            ON e.id_evento  = p.id_evento
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE p.id_atleta = 93113 AND eo.anio = 2004 AND e.nombre LIKE N'%Butterfly%'
ORDER BY e.nombre;
GO

/* ---
   T15. La firma de duplicado, grupo por grupo, para Phelps.
   Reproduce a mano lo que el SP calcula internamente: dentro de cada grupo
   (ano, disciplina, medalla), n filas con posicion y n con edad => n medallas.
   Esperado: con_posicion = con_edad en todos los grupos, y 28 en el total.
--- */
SELECT
    eo.anio,
    d.nombre AS disciplina,
    p.medalla,
    COUNT(*)                                                AS filas,
    SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END) AS con_posicion,
    SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END) AS con_edad,
    CASE WHEN SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END)
            = SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END)
          AND SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END) > 0
         THEN SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END)
         ELSE COUNT(*)
    END                                                     AS estimado
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion   = p.id_edicion
JOIN olympics.EVENTO e            ON e.id_evento     = p.id_evento
JOIN olympics.DISCIPLINA d        ON d.id_disciplina = e.id_disciplina
WHERE p.id_atleta = 93113 AND p.medalla IS NOT NULL
GROUP BY eo.anio, d.id_disciplina, d.nombre, p.medalla
ORDER BY eo.anio, p.medalla;
GO

/* ---
   T16. Cobertura global del metodo de estimacion sobre toda la base.
   Esperado: determinable 99.81% de los 78,998 grupos con medalla.
--- */
WITH g AS
(
    SELECT
        p.id_atleta, eo.anio, e.id_disciplina, p.medalla,
        COUNT(*)                                                AS filas,
        SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END) AS con_pos,
        SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END) AS con_edad
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, eo.anio, e.id_disciplina, p.medalla
)
SELECT
    CASE
        WHEN con_pos > 0 AND con_edad > 0 AND con_pos =  con_edad THEN N'1. firma de duplicado limpia'
        WHEN con_pos > 0 AND con_edad = 0                         THEN N'2. solo una nomenclatura'
        WHEN con_edad > 0 AND con_pos = 0                         THEN N'2. solo una nomenclatura'
        WHEN con_pos = 0 AND con_edad = 0 AND filas = 1           THEN N'3. grupo de una sola fila'
        ELSE                                                           N'4. indeterminado'
    END                                     AS caso,
    COUNT(*)                                AS grupos,
    CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS DECIMAL(5,2)) AS porcentaje
FROM g
GROUP BY
    CASE
        WHEN con_pos > 0 AND con_edad > 0 AND con_pos =  con_edad THEN N'1. firma de duplicado limpia'
        WHEN con_pos > 0 AND con_edad = 0                         THEN N'2. solo una nomenclatura'
        WHEN con_edad > 0 AND con_pos = 0                         THEN N'2. solo una nomenclatura'
        WHEN con_pos = 0 AND con_edad = 0 AND filas = 1           THEN N'3. grupo de una sola fila'
        ELSE                                                           N'4. indeterminado'
    END
ORDER BY caso;
GO

/* ---
   T17. Solidez del metodo de estimacion: los tres subcasos de la firma limpia.

   Verifica contra la base lo que documentacion_d.md afirma en la seccion 5.1:
     a) particion exacta            esperado 21,791
     b) alguna fila con AMBOS       esperado  5,625
     c) alguna fila con NINGUNO     esperado      0   <- el caso que subcontaria

   El caso (c) es el unico capaz de subcontar: si un grupo tiene firma limpia
   pero ademas filas sin posicion ni edad, esas filas podrian ser medallas
   reales y no duplicados. Debe dar 0.

   a) + b) debe sumar 27,416, que es el total de firma limpia de T16.
--- */
WITH g AS
(
    SELECT
        p.id_atleta, eo.anio, e.id_disciplina, p.medalla,
        COUNT(*)                                                       AS filas,
        SUM(CASE WHEN p.posicion IS NOT NULL THEN 1 ELSE 0 END)        AS con_pos,
        SUM(CASE WHEN p.edad     IS NOT NULL THEN 1 ELSE 0 END)        AS con_edad,
        SUM(CASE WHEN p.posicion IS     NULL AND p.edad IS     NULL
                 THEN 1 ELSE 0 END)                                    AS con_ninguno,
        SUM(CASE WHEN p.posicion IS NOT NULL AND p.edad IS NOT NULL
                 THEN 1 ELSE 0 END)                                    AS con_ambos
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, eo.anio, e.id_disciplina, p.medalla
)
SELECT
    SUM(CASE WHEN firma = 1 AND filas = con_pos + con_edad
             THEN 1 ELSE 0 END) AS a_particion_exacta,
    SUM(CASE WHEN firma = 1 AND con_ambos > 0
             THEN 1 ELSE 0 END) AS b_alguna_fila_con_ambos,
    SUM(CASE WHEN firma = 1 AND con_ninguno > 0 AND con_ambos = 0
             THEN 1 ELSE 0 END) AS c_RIESGO_subconteo,
    SUM(firma)                  AS total_firma_limpia
FROM
(
    SELECT *,
           CASE WHEN con_pos > 0 AND con_edad > 0 AND con_pos = con_edad
                THEN 1 ELSE 0 END AS firma
    FROM g
) q;
GO

/* ---
   T18. Caso 1906 - Juegos Intercalados de Atenas.

   El checklist del equipo pide probarlo porque 1906 es una edicion atipica:
   existe como "Intercalated Games" y NO existe un "1906 Summer".

   Eric Lemming (id 75674) tiene 23 participaciones en esa edicion.
   Esperado: todas las filas con anio 1906 y temporada "Intercalated Games".
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Eric Lemming',
     @anio          = 1906;
GO

/* Comprobacion del dominio: 1906 existe como Intercalated y no como Summer. */
SELECT anio, temporada FROM olympics.EDICION_OLIMPICA WHERE anio = 1906;
GO

/* ---
   T19. Caso Youth - los Juegos Olimpicos de la Juventud se conservaron.

   Chad le Clos (id 119877) compitio en Youth y tambien en Summer, asi que
   sirve para ver que el filtro de temporada los distingue.

   Recordar que @temporada usa igualdad EXACTA: 'Summer' no incluye
   'Summer Youth'.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Chad le Clos',
     @temporada     = N'Summer Youth';
GO

EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Chad le Clos',
     @temporada     = N'Summer';
GO

/* ---
   T20. NOC historico - NOC y pais NO son lo mismo.

   Nikolay Andrianov (id 31000) compitio por la URSS. En el modelo final
   codigo_noc = 'URS' y la entidad geografica asociada es 'Russia'.

   Esperado en el detalle: codigo_noc = URS con pais_representado = Russia.
   Eso demuestra que la relacion NOC -> ENTIDAD_GEOGRAFICA es explicita y que
   no se asumio codigo_pais = codigo_noc.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta = N'Nikolay Andrianov',
     @pais          = N'URS';
GO

/* Los NOC historicos que apuntan a una misma entidad. */
SELECT n.codigo_noc, n.nombre_noc, eg.nombre AS entidad
FROM olympics.NOC n
LEFT JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
WHERE n.codigo_noc IN (N'URS', N'EUN', N'GDR', N'FRG', N'GER', N'TCH', N'YUG')
ORDER BY eg.nombre, n.codigo_noc;
GO

/* ---
   T21. Rango de anos y tipo de medalla.

   Responde de una sola pasada el tipo de pregunta que puede salir en la
   defensa: "sus medallas de oro entre 2004 y 2012".
   Esperado para Phelps: solo filas Gold con anio entre 2004 y 2012.
--- */
EXEC olympics.sp_historial_atleta
     @nombre_atleta       = N'Michael Phelps',
     @coincidencia_exacta = 1,
     @anio_desde          = 2004,
     @anio_hasta          = 2012,
     @medalla             = N'Gold';
GO

/* ---
   T22. Validacion de los parametros nuevos. Ambos deben lanzar RAISERROR
   con un mensaje claro, no devolver un resultado vacio enganoso.
--- */
BEGIN TRY
    EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps', @medalla = N'Oro';
END TRY
BEGIN CATCH
    SELECT N'medalla invalida' AS prueba, ERROR_MESSAGE() AS mensaje;
END CATCH;
GO

BEGIN TRY
    EXEC olympics.sp_historial_atleta @nombre_atleta = N'Michael Phelps',
         @anio_desde = 2012, @anio_hasta = 2004;
END TRY
BEGIN CATCH
    SELECT N'rango invertido' AS prueba, ERROR_MESSAGE() AS mensaje;
END CATCH;
GO
