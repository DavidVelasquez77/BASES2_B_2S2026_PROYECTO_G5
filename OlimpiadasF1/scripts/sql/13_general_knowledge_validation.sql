/*
  GENERAL_KNOWLEDGE_QUERY_VALIDATION
  Read-only validation for OlimpiadasDB.

  This file intentionally contains only SELECT/CTE statements. It does not
  create objects, change data, load CSVs, reset tables, or execute procedures.
  Run with the database context set to OlimpiadasDB.
*/

-- 1. Current cardinalities.
SELECT 'ENTIDAD_GEOGRAFICA' AS entidad, COUNT_BIG(*) AS filas FROM olympics.ENTIDAD_GEOGRAFICA
UNION ALL SELECT 'POBLACION', COUNT_BIG(*) FROM olympics.POBLACION
UNION ALL SELECT 'NOC', COUNT_BIG(*) FROM olympics.NOC
UNION ALL SELECT 'ATLETA', COUNT_BIG(*) FROM olympics.ATLETA
UNION ALL SELECT 'SEDE', COUNT_BIG(*) FROM olympics.SEDE
UNION ALL SELECT 'EDICION_OLIMPICA', COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA
UNION ALL SELECT 'DEPORTE', COUNT_BIG(*) FROM olympics.DEPORTE
UNION ALL SELECT 'DISCIPLINA', COUNT_BIG(*) FROM olympics.DISCIPLINA
UNION ALL SELECT 'EVENTO', COUNT_BIG(*) FROM olympics.EVENTO
UNION ALL SELECT 'PARTICIPACION', COUNT_BIG(*) FROM olympics.PARTICIPACION;

-- 2. Guatemala: athlete rows and official outcomes.
SELECT 'GUA' AS codigo_noc,
       COUNT(DISTINCT p.id_atleta) AS medallistas_distintos,
       COUNT_BIG(*) AS filas_medalla_atleta,
       COUNT(DISTINCT CONCAT(p.id_edicion, '|', p.id_evento, '|', p.id_noc, '|', p.medalla)) AS resultados_oficiales
FROM olympics.PARTICIPACION p
JOIN olympics.NOC n ON n.id_noc = p.id_noc
WHERE n.codigo_noc = 'GUA' AND p.medalla IS NOT NULL;

-- 3. Justin Gatlin, Athens 2004 men's 100 metres.
SELECT a.nombre, e.anio, ev.nombre AS evento, n.codigo_noc, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
JOIN olympics.NOC n ON n.id_noc = p.id_noc
WHERE a.id_atleta = 104445 AND e.anio = 2004 AND ev.id_evento = 43 AND p.medalla = 'Gold';

-- 4. Michael Phelps medal profile and top-20 athlete ranking.
SELECT p.medalla, COUNT_BIG(*) AS filas
FROM olympics.PARTICIPACION p
WHERE p.id_atleta = 93113 AND p.medalla IS NOT NULL
GROUP BY p.medalla
ORDER BY p.medalla;

WITH MedalCounts AS (
    SELECT p.id_atleta, a.nombre,
           SUM(CASE WHEN p.medalla = 'Gold' THEN 1 ELSE 0 END) AS gold,
           SUM(CASE WHEN p.medalla = 'Silver' THEN 1 ELSE 0 END) AS silver,
           SUM(CASE WHEN p.medalla = 'Bronze' THEN 1 ELSE 0 END) AS bronze
    FROM olympics.PARTICIPACION p
    JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_atleta, a.nombre
)
SELECT TOP (20) id_atleta, nombre, gold, silver, bronze, gold + silver + bronze AS total
FROM MedalCounts
ORDER BY gold DESC, silver DESC, bronze DESC, nombre, id_atleta;

-- 5. Official medal logic: one result is edition + event + NOC + medal.
WITH OfficialOutcomes AS (
    SELECT p.id_edicion, p.id_evento, p.id_noc, p.medalla,
           COUNT(DISTINCT p.id_atleta) AS athlete_rows
    FROM olympics.PARTICIPACION p
    WHERE p.medalla IS NOT NULL
    GROUP BY p.id_edicion, p.id_evento, p.id_noc, p.medalla
)
SELECT COUNT_BIG(*) AS official_outcomes,
       SUM(CASE WHEN athlete_rows > 1 THEN 1 ELSE 0 END) AS team_or_multiathlete_outcomes
FROM OfficialOutcomes;

-- 6. Beijing 2008: athlete Gold count vs official Gold outcome count.
WITH BeijingGold AS (
    SELECT p.*
    FROM olympics.PARTICIPACION p
    JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion = p.id_edicion
    WHERE e.anio = 2008 AND p.medalla = 'Gold'
), OfficialGold AS (
    SELECT id_edicion, id_evento, id_noc, medalla
    FROM BeijingGold
    GROUP BY id_edicion, id_evento, id_noc, medalla
)
SELECT (SELECT COUNT(DISTINCT id_atleta) FROM BeijingGold) AS distinct_gold_athletes,
       (SELECT COUNT_BIG(*) FROM OfficialGold) AS official_gold_outcomes;

-- 7. Required edition years.
SELECT anio, COUNT(*) AS editions
FROM olympics.EDICION_OLIMPICA
WHERE anio IN (1896, 1936, 1968, 1984, 2000, 2004, 2008, 2012, 2016, 2020, 2024)
GROUP BY anio
ORDER BY anio;

-- 8. Youngest raw Gold ages. The result is an observation, not an external claim.
SELECT TOP (10) p.id_atleta, a.nombre, p.edad, a.fecha_nacimiento,
       e.anio, ev.nombre AS evento
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
WHERE p.medalla = 'Gold' AND p.edad IS NOT NULL
ORDER BY p.edad, p.id_atleta;

-- 9. Barrondo, Messi and London 2012 50 km walk.
SELECT a.nombre, e.anio, ev.nombre AS evento, n.codigo_noc,
       p.posicion, p.medalla, p.estado_resultado
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA e ON e.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
JOIN olympics.NOC n ON n.id_noc = p.id_noc
WHERE (p.id_atleta = 121191 AND p.id_edicion = 50 AND p.id_evento = 1021)
   OR (p.id_atleta = 110178 AND p.id_edicion = 47 AND p.id_evento = 303)
   OR (p.id_edicion = 50 AND p.id_evento = 1022 AND (p.medalla IS NOT NULL OR p.estado_resultado = 'DQ'))
ORDER BY p.id_edicion, p.id_evento, CASE WHEN p.posicion IS NULL THEN 99 ELSE p.posicion END;

-- 10. Suspicious candidates: DQ carrying a medal and multiple NOCs on one medal.
SELECT COUNT_BIG(*) AS dq_with_medal
FROM olympics.PARTICIPACION
WHERE estado_resultado = 'DQ' AND medalla IS NOT NULL;

SELECT TOP (200) id_edicion, id_evento, medalla,
       COUNT(DISTINCT id_noc) AS noc_distintos,
       COUNT(DISTINCT id_atleta) AS atletas_distintos
FROM olympics.PARTICIPACION
WHERE medalla IS NOT NULL
GROUP BY id_edicion, id_evento, medalla
HAVING COUNT(DISTINCT id_noc) > 1
ORDER BY COUNT(DISTINCT id_noc) DESC;

-- 11. Candidate semantic duplicates. These are candidates only; no merge is implied.
SELECT LOWER(LTRIM(RTRIM(a.nombre))) AS nombre_normalizado,
       COUNT(DISTINCT a.id_atleta) AS ids_atleta
FROM olympics.ATLETA a
WHERE a.nombre IS NOT NULL
GROUP BY LOWER(LTRIM(RTRIM(a.nombre)))
HAVING COUNT(DISTINCT a.id_atleta) > 1
ORDER BY ids_atleta DESC, nombre_normalizado;
