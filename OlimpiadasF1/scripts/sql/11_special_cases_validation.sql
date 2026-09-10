/* Bloque 7 — validación de casos especiales, solo lectura. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
GO

DECLARE @v TABLE (validacion NVARCHAR(160), esperado BIGINT, actual BIGINT, estado NVARCHAR(10), detalle NVARCHAR(300));

INSERT INTO @v VALUES
(N'1906.Intercalated_Games',1,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE anio=1906 AND temporada=N'Intercalated Games'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE anio=1906 AND temporada=N'Intercalated Games')=1 THEN N'PASS' ELSE N'FAIL' END,N'Debe existir una edición 1906 Intercalated Games'),
(N'1906.Summer_ausente',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE anio=1906 AND temporada=N'Summer'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE anio=1906 AND temporada=N'Summer')=0 THEN N'PASS' ELSE N'FAIL' END,N'No debe existir 1906 Summer'),
(N'Equestrian.ediciones',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Equestrian'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Equestrian')=0 THEN N'PASS' ELSE N'FAIL' END,N'Equestrian no es temporada final'),
(N'Equestrian.1956_eventos_finales',586,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE e.anio=1956 AND e.temporada=N'Summer' AND ev.nombre LIKE N'%Equestrian%'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE e.anio=1956 AND e.temporada=N'Summer' AND ev.nombre LIKE N'%Equestrian%')=586 THEN N'PASS' ELSE N'FAIL' END,N'Conteo final por nombre de evento. Las 300 filas de la fuente auditadas no son recuperables como subconjunto de procedencia en la tabla final.'),
(N'Equestrian.1956_fuera_de_summer',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE e.anio=1956 AND ev.nombre LIKE N'%Equestrian%' AND e.temporada<>N'Summer'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE e.anio=1956 AND ev.nombre LIKE N'%Equestrian%' AND e.temporada<>N'Summer')=0 THEN N'PASS' ELSE N'FAIL' END,N'Todas las filas ecuestres identificables de 1956 están asociadas a 1956 Summer.'),
(N'Zappas.participaciones_finales',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p LEFT JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE ev.nombre LIKE N'%Zappas%' OR p.equipo LIKE N'%Zappas%' OR p.nombre_competencia LIKE N'%Zappas%'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION p LEFT JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento WHERE ev.nombre LIKE N'%Zappas%' OR p.equipo LIKE N'%Zappas%' OR p.nombre_competencia LIKE N'%Zappas%')=0 THEN N'PASS' ELSE N'FAIL' END,N'No quedan atributos Zappas en la participación final; el modelo final no conserva Games original/procedencia de fila.'),
(N'Summer_Youth.ediciones',3,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Summer Youth'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Summer Youth')=3 THEN N'PASS' ELSE N'FAIL' END,N'Youth conservado'),
(N'Winter_Youth.ediciones',3,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Winter Youth'),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada=N'Winter Youth')=3 THEN N'PASS' ELSE N'FAIL' END,N'Youth conservado');

SELECT validacion,esperado,actual,estado,detalle FROM @v ORDER BY validacion;
IF EXISTS (SELECT 1 FROM @v WHERE estado=N'FAIL')
BEGIN
    PRINT N'RESULTADO_CASOS_ESPECIALES = FAIL';
    THROW 51071,N'11_special_cases_validation.sql FAIL.',1;
END;
PRINT N'RESULTADO_CASOS_ESPECIALES = PASS';
GO
