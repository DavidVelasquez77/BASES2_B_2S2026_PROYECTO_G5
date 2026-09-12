/* FINAL_EXTERNAL_LIVE_QUERY_AUDIT
   SELECT/CTE only. No data, schema, index, procedure or table changes.
*/

-- 1. Guatemala medal table.
SELECT n.codigo_noc, p.medalla, COUNT_BIG(*) AS filas_atleta,
       COUNT(DISTINCT CONCAT(p.id_edicion,'|',p.id_evento,'|',p.id_noc,'|',p.medalla)) AS resultados_oficiales
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n ON n.id_noc=p.id_noc
WHERE n.codigo_noc='GUA' AND p.medalla IS NOT NULL
GROUP BY n.codigo_noc,p.medalla
ORDER BY p.medalla;

-- 2. Event winners by year and event name.
SELECT e.anio, ev.nombre AS evento, a.nombre, n.codigo_noc, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion=p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento
JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
JOIN olympics.NOC n ON n.id_noc=p.id_noc
WHERE p.medalla='Gold'
  AND ((e.anio IN (2004,2008,2012,2016) AND ev.nombre IN ('100 metres, Men (Olympic)','100 metres, Women (Olympic)'))
       OR (e.anio=2008 AND ev.nombre LIKE '200 metres, Men%')
       OR (e.anio=2008 AND ev.nombre LIKE '100 metres Freestyle, Men%')
       OR (e.anio=2008 AND ev.nombre LIKE 'Football%Men%')
       OR (e.anio=2012 AND ev.nombre LIKE 'Basketball%Men%'))
ORDER BY e.anio,ev.nombre,a.nombre;

-- 3. Athlete rankings by total and medal type.
WITH MedalCounts AS (
    SELECT p.id_atleta,a.nombre,
           SUM(CASE WHEN p.medalla='Gold' THEN 1 ELSE 0 END) AS Gold,
           SUM(CASE WHEN p.medalla='Silver' THEN 1 ELSE 0 END) AS Silver,
           SUM(CASE WHEN p.medalla='Bronze' THEN 1 ELSE 0 END) AS Bronze
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta,a.nombre
)
SELECT TOP (20) id_atleta,nombre,Gold,Silver,Bronze,Gold+Silver+Bronze AS Total
FROM MedalCounts ORDER BY Total DESC,Gold DESC,Silver DESC,Bronze DESC,nombre,id_atleta;

WITH MedalCounts AS (
    SELECT p.id_atleta,a.nombre,
           SUM(CASE WHEN p.medalla='Gold' THEN 1 ELSE 0 END) AS Gold,
           SUM(CASE WHEN p.medalla='Silver' THEN 1 ELSE 0 END) AS Silver,
           SUM(CASE WHEN p.medalla='Bronze' THEN 1 ELSE 0 END) AS Bronze
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta,a.nombre
)
SELECT TOP (20) id_atleta,nombre,Gold,Silver,Bronze,Gold+Silver+Bronze AS Total
FROM MedalCounts ORDER BY Gold DESC,Silver DESC,Bronze DESC,nombre,id_atleta;

-- 4. Rankings by sport through PARTICIPACION -> EVENTO -> DISCIPLINA -> DEPORTE.
WITH SportMedals AS (
    SELECT d.nombre AS deporte,p.id_atleta,a.nombre AS atleta,
           COUNT_BIG(*) AS medallas
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
    JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento
    JOIN olympics.DISCIPLINA di ON di.id_disciplina=ev.id_disciplina
    JOIN olympics.DEPORTE d ON d.id_deporte=di.id_deporte
    WHERE p.medalla IS NOT NULL
    GROUP BY d.nombre,p.id_atleta,a.nombre
), RankedSportMedals AS (
    SELECT deporte,id_atleta,atleta,medallas,
           ROW_NUMBER() OVER (PARTITION BY deporte ORDER BY medallas DESC,atleta,id_atleta) AS ranking
    FROM SportMedals
)
SELECT deporte,id_atleta,atleta,medallas,ranking
FROM RankedSportMedals
WHERE deporte IN ('Swimming','Athletics','Gymnastics') AND ranking <= 10;

-- 5. Winter-sport ranking through the edition category and the model hierarchy.
WITH WinterMedals AS (
    SELECT p.id_atleta,a.nombre AS atleta,COUNT_BIG(*) AS medallas
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
    JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion
    JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento
    JOIN olympics.DISCIPLINA di ON di.id_disciplina=ev.id_disciplina
    JOIN olympics.DEPORTE d ON d.id_deporte=di.id_deporte
    WHERE p.medalla IS NOT NULL AND ed.temporada='Winter'
    GROUP BY p.id_atleta,a.nombre
)
SELECT TOP (10) id_atleta,atleta,medallas
FROM WinterMedals ORDER BY medallas DESC,atleta,id_atleta;

-- 6. Famous athlete profiles used by the external review.
SELECT a.id_atleta,a.nombre,COUNT(p.id_participacion) AS participaciones,
       SUM(CASE WHEN p.medalla='Gold' THEN 1 ELSE 0 END) AS Gold,
       SUM(CASE WHEN p.medalla='Silver' THEN 1 ELSE 0 END) AS Silver,
       SUM(CASE WHEN p.medalla='Bronze' THEN 1 ELSE 0 END) AS Bronze,
       COUNT(CASE WHEN p.medalla IS NOT NULL THEN 1 END) AS TotalMedals
FROM olympics.ATLETA a
LEFT JOIN olympics.PARTICIPACION p ON p.id_atleta=a.id_atleta
WHERE a.id_atleta IN (93113,28985,100161,31000,67218,78102,51214,129489,104492,110178)
GROUP BY a.id_atleta,a.nombre
ORDER BY a.nombre;

-- 7. Youngest Gold observations with DOB and edition year.
SELECT TOP (20) p.id_atleta,a.nombre,p.edad,a.fecha_nacimiento,ed.anio,
       ev.nombre AS evento
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta=p.id_atleta
JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento=p.id_evento
WHERE p.medalla='Gold' AND p.edad IS NOT NULL
ORDER BY p.edad,p.id_atleta;

-- 8. Beijing 2008: distinct athlete Gold vs official outcomes.
WITH BG AS (
    SELECT p.* FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA ed ON ed.id_edicion=p.id_edicion
    WHERE ed.anio=2008 AND p.medalla='Gold'
), BO AS (
    SELECT id_edicion,id_evento,id_noc,medalla FROM BG
    GROUP BY id_edicion,id_evento,id_noc,medalla
)
SELECT (SELECT COUNT(DISTINCT id_atleta) FROM BG) AS atletas_distintos_gold,
       (SELECT COUNT_BIG(*) FROM BO) AS resultados_gold_oficiales;

-- 9. Suspicious podium diagnostics; candidates only, never corrections.
SELECT TOP (200) p.id_edicion,p.id_evento,p.medalla,
       COUNT(DISTINCT p.id_noc) AS noc_distintos,
       COUNT(DISTINCT p.id_atleta) AS atletas_distintos
FROM olympics.PARTICIPACION p
WHERE p.medalla IS NOT NULL
GROUP BY p.id_edicion,p.id_evento,p.medalla
HAVING COUNT(DISTINCT p.id_noc)>1
ORDER BY COUNT(DISTINCT p.id_noc) DESC;

SELECT COUNT_BIG(*) AS dq_con_medalla
FROM olympics.PARTICIPACION
WHERE estado_resultado='DQ' AND medalla IS NOT NULL;
