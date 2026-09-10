/* Bloque 7 — consultas funcionales, solo lectura. No crea procedimientos. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
GO

DECLARE @id_atleta BIGINT;
SELECT TOP (1) @id_atleta=p.id_atleta
FROM olympics.PARTICIPACION p
GROUP BY p.id_atleta
HAVING COUNT_BIG(*) BETWEEN 3 AND 10
ORDER BY COUNT_BIG(*) DESC,p.id_atleta;

PRINT N'CONSULTA_ATLETA — atleta seleccionado dinámicamente';
SELECT p.id_atleta,a.nombre AS atleta,e.anio,e.temporada,d.nombre AS deporte,di.nombre AS disciplina,ev.nombre AS evento,n.codigo_noc AS noc,p.equipo,p.posicion,p.estado_resultado,p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento
JOIN olympics.DISCIPLINA di ON di.id_disciplina=ev.id_disciplina
JOIN olympics.DEPORTE d ON d.id_deporte=di.id_deporte
LEFT JOIN olympics.NOC n ON n.id_noc=p.id_noc
WHERE p.id_atleta=@id_atleta
ORDER BY e.anio,e.temporada,ev.nombre;

DECLARE @id_entidad INT;
SELECT TOP (1) @id_entidad=n.id_entidad
FROM olympics.NOC n
JOIN olympics.PARTICIPACION p ON p.id_noc=n.id_noc
WHERE n.id_entidad IS NOT NULL
GROUP BY n.id_entidad
ORDER BY COUNT_BIG(*) DESC,n.id_entidad;

PRINT N'CONSULTA_PAIS — entidad seleccionada dinámicamente';
SELECT TOP (20) eg.id_entidad,eg.nombre AS entidad,n.codigo_noc,n.nombre_noc,p.id_atleta,a.nombre AS atleta,e.anio,e.temporada
FROM olympics.ENTIDAD_GEOGRAFICA eg
JOIN olympics.NOC n ON n.id_entidad=eg.id_entidad
JOIN olympics.PARTICIPACION p ON p.id_noc=n.id_noc
JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion
WHERE eg.id_entidad=@id_entidad
ORDER BY e.anio,e.temporada,a.nombre;

PRINT N'CASOS_REPRESENTATIVOS — Unicode';
SELECT TOP (1) id_atleta,nombre,nombre_original FROM olympics.ATLETA WHERE nombre COLLATE Latin1_General_100_BIN2 LIKE N'%[^ -~]%' ORDER BY id_atleta;

PRINT N'CASOS_REPRESENTATIVOS — medalla y sin medalla';
SELECT TOP (1) N'medalla' AS caso,p.id_participacion,a.nombre,p.medalla,e.anio,e.temporada FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion WHERE p.medalla IS NOT NULL ORDER BY p.id_participacion;
SELECT TOP (1) N'sin_medalla' AS caso,p.id_participacion,a.nombre,p.medalla,e.anio,e.temporada FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion WHERE p.medalla IS NULL ORDER BY p.id_participacion;

PRINT N'CASOS_REPRESENTATIVOS — estados especiales';
;WITH s AS
(
    SELECT p.id_participacion,a.nombre,p.estado_resultado,p.posicion,p.empatado,e.anio,e.temporada,
           ROW_NUMBER() OVER (PARTITION BY p.estado_resultado ORDER BY p.id_participacion) AS rn
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
    JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion
    WHERE p.estado_resultado IN (N'DNF',N'DNS',N'DQ',N'DSQ')
)
SELECT id_participacion,nombre,estado_resultado,posicion,empatado,anio,temporada FROM s WHERE rn=1 ORDER BY estado_resultado;

PRINT N'CASOS_REPRESENTATIVOS — empate';
SELECT TOP (1) p.id_participacion,a.nombre,p.posicion,p.empatado,e.anio,e.temporada FROM olympics.PARTICIPACION p JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion WHERE p.empatado=1 ORDER BY p.id_participacion;

PRINT N'CASOS_REPRESENTATIVOS — NOC histórico';
SELECT TOP (1) n.id_noc,n.codigo_noc,n.nombre_noc,n.notas FROM olympics.NOC n WHERE n.notas IS NOT NULL ORDER BY n.id_noc;

PRINT N'CASOS_REPRESENTATIVOS — temporadas y edición 1906';
SELECT TOP (1) N'Summer' AS caso,e.id_edicion,e.anio,e.temporada,s.nombre AS sede FROM olympics.EDICION_OLIMPICA e LEFT JOIN olympics.SEDE s ON s.id_sede=e.id_sede WHERE e.temporada=N'Summer' ORDER BY e.anio;
SELECT TOP (1) N'Winter' AS caso,e.id_edicion,e.anio,e.temporada,s.nombre AS sede FROM olympics.EDICION_OLIMPICA e LEFT JOIN olympics.SEDE s ON s.id_sede=e.id_sede WHERE e.temporada=N'Winter' ORDER BY e.anio;
SELECT TOP (1) N'Summer Youth' AS caso,e.id_edicion,e.anio,e.temporada,s.nombre AS sede FROM olympics.EDICION_OLIMPICA e LEFT JOIN olympics.SEDE s ON s.id_sede=e.id_sede WHERE e.temporada=N'Summer Youth' ORDER BY e.anio;
SELECT TOP (1) N'Winter Youth' AS caso,e.id_edicion,e.anio,e.temporada,s.nombre AS sede FROM olympics.EDICION_OLIMPICA e LEFT JOIN olympics.SEDE s ON s.id_sede=e.id_sede WHERE e.temporada=N'Winter Youth' ORDER BY e.anio;
SELECT e.id_edicion,e.anio,e.temporada,s.nombre AS sede FROM olympics.EDICION_OLIMPICA e LEFT JOIN olympics.SEDE s ON s.id_sede=e.id_sede WHERE e.anio=1906;
GO
