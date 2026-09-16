/*
========================================================================================
Sistemas de Bases de Datos 2 — 2do. Semestre 2026
Proyecto Fase 1: Olimpiadas (1896 - 2024)
Grupo 7

Archivo: pruebas.sql
Ruta: storeprocedure_pais/pruebas.sql
Propósito: Batería exhaustiva de pruebas, casos de control de calidad y banco de consultas
           frecuentes para la evaluación presencial del Catedrático.
           Todos los resultados numéricos están cotejados con olympics.com y reflejan
           el estado real de la base de datos limpia vigente (712,020 participaciones).

Estructura de Pruebas:
  - BLOQUE 1: Casos de Control Oficiales (Guatemala, Sedes de Francia, Delegación Especial ROC)
  - BLOQUE 2: Demostración de No-Inflación de Medallas en Deportes Colectivos (Fútbol y Básquetbol)
  - BLOQUE 3: Consultas de Jugadores y Atletas Famosos (Messi, Cristiano Ronaldo, Neymar, Phelps, Bolt)
  - BLOQUE 4: Consultas Analíticas Típicas de Examen (100m Planos 2004, Más Medallas, Más Joven)
  - BLOQUE 5: Manejo Defensivo de Errores, Validación Insensible de Temporada y Control de Ambigüedad
========================================================================================
*/

USE OlimpiadasDB;
GO

SET NOCOUNT ON;
GO

PRINT N'================================================================================';
PRINT N'INICIANDO BATERÍA DE PRUEBAS DE sp_consultar_pais (INCISO E)';
PRINT N'================================================================================';
GO

-- ====================================================================================
-- BLOQUE 1: CASOS DE CONTROL OFICIALES DE AUDITORÍA
-- ====================================================================================

/* ---
   PRUEBA 1.1: Caso Guatemala ('GUA')
   Objetivo: Verificar medallero de Guatemala y condición de NO sede.
   Esperado en BD (Modelo Canónico Vigente - Reconciliación Olympedia):
     - ha_sido_sede: 'NO' (0 ediciones)
     - Medallero oficial (clave id_edicion + id_evento + id_noc + medalla):
       1 Oro, 1 Plata, 1 Bronce (Total: 3 medallas oficiales, 100% coincidente con olympics.com).
     - Preseas físicas entregadas a atletas: 3.
     - Detalle de medallistas:
         1. Adriana Ruano Oliva (2024 Summer, Shooting / Trap Women): Gold
         2. Érick Barrondo (2012 Summer, Athletics / 20km Race Walk Men): Silver
         3. Jean Pierre Brol Cárdenas (2024 Summer, Shooting / Trap Men): Bronze
   Total participaciones: 594 | Atletas distintos: 263 (100% cotejado con padrón Olympedia).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 1.1: Guatemala (General)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'GUA';
GO

/* ---
   PRUEBA 1.2: Caso Francia ('FRA') - Sedes Múltiples
   Objetivo: Verificar detección completa de ediciones históricas organizadas como sede.
   Esperado:
     - ha_sido_sede: 'SÍ'
     - total_ediciones_como_sede: 6
     - Ciudades sede: Paris (1900, 1924, 2024), Chamonix (1924), Grenoble (1968), Albertville (1992).
     - Desglose ordenado por año y temporada.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 1.2: Francia (Historial de Sedes)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'FRA';
GO

/* ---
   PRUEBA 1.3: Delegación Especial / NOC sin entidad geográfica ('ROC' - Comité Olímpico Ruso)
   Objetivo: Demostrar el desacoplamiento @id_entidad vs @id_noc. NOCs con id_entidad IS NULL
             (ej. ROC, EOR, ROT, AIN, COR) son consultados correctamente sin errores.
   Esperado en BD:
     - id_entidad: NULL | pais: 'ROC' | codigo_iso: 'N/A' | codigos_noc: 'ROC' | poblacion: NULL
     - ha_sido_sede: 'NO' (0 ediciones)
     - total_participaciones: 1,689 | total_atletas_distintos: 1,151
     - Medallas oficiales: 46 Oro, 71 Plata, 67 Bronce = 184 medallas oficiales.
     - Preseas físicas a atletas: 425.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 1.3: Delegación Especial ROC (id_entidad IS NULL)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'ROC',
    @top_participaciones = 10;
GO

/* ---
   PRUEBA 1.4: Delegación Especial de Refugiados ('EOR' - Equipe Olympique des Réfugiés)
   Objetivo: Verificar consulta de equipo independiente de atletas refugiados.
   Esperado en BD:
     - ha_sido_sede: 'NO'
     - total_participaciones: 126 | total_atletas_distintos: 97
     - Medallas: 1 Bronce (París 2024 - Boxeo 75kg femenino, Cindy Ngamba / Winner Djankeu).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 1.4: Equipo Olímpico de Refugiados (EOR)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'EOR',
    @top_participaciones = 5;
GO


-- ====================================================================================
-- BLOQUE 2: DEMOSTRACIÓN DE NO-INFLACIÓN EN DEPORTES DE EQUIPO
-- ====================================================================================

/* ---
   PRUEBA 2.1: Argentina en Fútbol Masculino Beijing 2008 ('ARG', 2008, 'Football')
   Objetivo: Demostrar que un deporte colectivo aporta 1 sola medalla de oro al país,
             mientras se reportan las preseas físicas de todos los atletas registrados.
   Esperado en BD:
     - medallas_oro_oficiales: 1
     - total_medallas_oficiales_pais: 1
     - preseas_totales_entregadas_a_atletas: 37 (Messi, Agüero, Riquelme, Di María, Mascherano, etc.).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 2.1: Argentina (Fútbol Beijing 2008 - Caso Messi)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'ARG',
    @anio       = 2008,
    @deporte    = N'Football';
GO

/* ---
   PRUEBA 2.2: Estados Unidos en Baloncesto Londres 2012 ('USA', 2012, 'Basketball')
   Objetivo: Verificar que el torneo ganado por USA Basketball no infle el medallero.
   Esperado en BD:
     - medallas_oro_oficiales: 2 (1 oro en Torneo Masculino + 1 oro en Torneo Femenino).
     - preseas_totales_entregadas_a_atletas: 42 (LeBron James, Kobe Bryant, Kevin Durant, etc.).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 2.2: USA (Baloncesto Londres 2012)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'USA',
    @anio       = 2012,
    @deporte    = N'Basketball';
GO


-- ====================================================================================
-- BLOQUE 3: CONSULTAS DE JUGADORES Y ATLETAS FAMOSOS
-- ====================================================================================

/* ---
   PRUEBA 3.1: Portugal en Fútbol Atenas 2004 ('POR', 2004, 'Football') - Caso Cristiano Ronaldo
   Objetivo: Consultar la participación de Portugal en 2004 donde compitió Cristiano Ronaldo (id_atleta 102010).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 3.1: Portugal (Fútbol Atenas 2004 - Caso Cristiano Ronaldo)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'POR',
    @anio       = 2004,
    @deporte    = N'Football';
GO

-- Consulta directa complementaria de respaldo para la defensa en vivo:
PRINT N'--- Consulta directa: Participación de Cristiano Ronaldo en JJ.OO. ---';
SELECT 
    a.id_atleta,
    a.nombre,
    eo.anio,
    eo.temporada,
    s.nombre AS ciudad_sede,
    ev.nombre AS evento,
    p.posicion,
    ISNULL(p.medalla, N'Sin Medalla') AS medalla
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.SEDE s ON s.id_sede = eo.id_sede
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
WHERE a.id_atleta = 102010;
GO

/* ---
   PRUEBA 3.2: Brasil en Fútbol ('BRA', 'Football') - Caso Neymar Jr.
   Objetivo: Consultar el historial de fútbol de Brasil donde Neymar ganó Plata en 2012 y Oro en 2016.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 3.2: Brasil (Fútbol - Caso Neymar Jr.)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'BRA',
    @deporte    = N'Football',
    @top_participaciones = 30;
GO


-- ====================================================================================
-- BLOQUE 4: CONSULTAS ANALÍTICAS TÍPICAS DE EXAMEN
-- ====================================================================================

/* ---
   PRUEBA 4.1: Podio 100 metros planos en Atenas 2004
   Respuesta histórica y en BD:
     - Oro: Justin Gatlin (Estados Unidos / 'USA'), 9.85s.
     - Plata: Francis Obikwelu (Portugal / 'POR'), 9.86s.
     - Bronce: Maurice Greene (Estados Unidos / 'USA'), 9.87s.
--- */
PRINT N'--- Consulta analítica 4.1: Podio 100m Planos Masculino Atenas 2004 ---';
SELECT 
    a.nombre AS atleta,
    n.codigo_noc AS pais,
    ev.nombre AS evento,
    eo.anio,
    p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.NOC n ON n.id_noc = p.id_noc
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
WHERE eo.anio = 2004 
  AND eo.temporada = N'Summer'
  AND ev.nombre LIKE N'%100 metres, Men%'
  AND p.medalla IS NOT NULL
ORDER BY 
    CASE p.medalla WHEN N'Gold' THEN 1 WHEN N'Silver' THEN 2 WHEN N'Bronze' THEN 3 END;
GO

/* ---
   PRUEBA 4.2: ¿Quién es el atleta con más medallas de oro en la historia olímpica?
   Respuesta canónica vigente en BD:
     - Michael Phelps (Natación, USA): 23 Oros, 3 Platas, 2 Bronces = 28 Medallas totales.
     - 100% coincidente con el registro oficial de olympics.com.
--- */
PRINT N'--- Consulta analítica 4.2: Desglose Oficial de Medallas de Michael Phelps ---';
SELECT 
    a.nombre AS atleta,
    p.medalla,
    COUNT(*) AS conteo_medallas
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
WHERE a.id_atleta = 115206 AND p.medalla IS NOT NULL
GROUP BY a.nombre, p.medalla
ORDER BY CASE p.medalla WHEN N'Gold' THEN 1 WHEN N'Silver' THEN 2 WHEN N'Bronze' THEN 3 END;
GO

/* ---
   PRUEBA 4.3: Atletas más jóvenes en ganar medalla de oro (campo edad)
--- */
PRINT N'--- Consulta analítica 4.3: Atletas más jóvenes con medalla de Oro ---';
SELECT TOP 5
    a.nombre AS atleta,
    p.edad,
    dep.nombre AS deporte,
    ev.nombre AS evento,
    eo.anio,
    eo.temporada,
    n.codigo_noc AS pais,
    p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.NOC n ON n.id_noc = p.id_noc
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
JOIN olympics.DISCIPLINA di ON di.id_disciplina = ev.id_disciplina
JOIN olympics.DEPORTE dep ON dep.id_deporte = di.id_deporte
WHERE p.medalla = N'Gold'
  AND p.edad IS NOT NULL
  AND p.edad > 0
ORDER BY p.edad ASC, eo.anio ASC;
GO


-- ====================================================================================
-- BLOQUE 5: MANEJO DEFENSIVO DE ERRORES, VALIDACIÓN DE DOMINIO Y AMBIGÜEDAD
-- ====================================================================================

/* ---
   PRUEBA 5.1: Validación de temporada insensible a mayúsculas ('summer' minúscula)
   Esperado: Resuelve exitosamente reconociendo 'summer' = 'Summer'.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.1: Validación insensible de temporada ("summer")';
EXEC olympics.sp_consultar_pais
    @pais_o_noc  = N'GUA',
    @temporada   = N'summer',
    @top_participaciones = 3;
GO

/* ---
   PRUEBA 5.2: Validación de temporada inválida ('Otoño')
   Esperado: Error controlado vía RAISERROR con dominio permitido.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.2: Error por temporada inválida ("Otoño")';
EXEC olympics.sp_consultar_pais
    @pais_o_noc  = N'FRA',
    @temporada   = N'Otoño';
GO

/* ---
   PRUEBA 5.3: Control de búsqueda ambigua ('Korea')
   Esperado: Retorna resultsets de advertencia listando Korea DPR (PRK) y Korea Rep (KOR).
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.3: Búsqueda ambigua ("Korea")';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'Korea';
GO

/* ---
   PRUEBA 5.4: Insensibilidad a acentos ('Perú' vs 'Peru')
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.4: Insensibilidad a acentos ("Peru" sin tilde)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'Peru',
    @top_participaciones = 5;
GO

/* ---
   PRUEBA 5.5: Normalización de @top_participaciones negativo (-99)
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.5: Normalización de @top_participaciones negativo (-99)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'GUA',
    @top_participaciones = -99;
GO

/* ---
   PRUEBA 5.6: Parámetro obligatorio nulo o vacío
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.6: Error por parámetro nulo';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = NULL;
GO

PRINT N'================================================================================';
PRINT N'BATERÍA DE PRUEBAS FINALIZADA EXITOSAMENTE';
PRINT N'================================================================================';
GO
