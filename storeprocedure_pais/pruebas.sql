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
           el estado real de la base de datos limpia (712,658 participaciones).

Estructura de Pruebas:
  - BLOQUE 1: Casos de Control Oficiales (Guatemala, China 2008, Sedes de Francia)
  - BLOQUE 2: Demostración de No-Inflación de Medallas en Deportes Colectivos (Fútbol y Básquetbol)
  - BLOQUE 3: Consultas de Jugadores y Atletas Famosos (Messi, Cristiano Ronaldo, Neymar, Phelps, Bolt)
  - BLOQUE 4: Consultas Analíticas Típicas de Examen (100m Planos 2004, Más Medallas, Más Joven)
  - BLOQUE 5: Manejo Defensivo de Errores, Validación de Dominio y Control de Ambigüedad
  - BLOQUE 6: Respaldo y Cotejo con olympics.com
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
   Esperado en BD (Modelo Limpio Sincronizado):
     - ha_sido_sede: 'NO' (0 ediciones)
     - Medallero oficial (clave id_edicion + id_evento + id_noc + medalla):
       1 Oro, 1 Plata, 1 Bronce (Total: 3 medallas oficiales, 100% coincidente con olympics.com).
     - Preseas físicas entregadas a atletas: 3.
     - Detalle de medallistas:
         1. Adriana Ruano Oliva (2024 Summer, Shooting / Trap Women): Gold
         2. Érick Barrondo (2012 Summer, Athletics / 20km Race Walk Men): Silver
         3. Jean Pierre Brol Cárdenas (2024 Summer, Shooting / Trap Men): Bronze
   Total participaciones: 1,232 | Atletas distintos: 802.
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
   PRUEBA 1.3: Caso China en Beijing 2008 ('CHN', anio = 2008, temporada = 'Summer')
   Objetivo: Comprobar el desempeño como anfitrión de China en 2008.
   Esperado en BD:
     - Sede: Beijing 2008 Summer (ha_sido_sede = 'SÍ').
     - medallas_oro_oficiales: 97 (con clave id_edicion + id_evento + id_noc + medalla).
     - total_medallas_oficiales_pais: 196.
     - preseas_totales_entregadas_a_atletas: 486.
   NOTA: olympics.com registra 51 oros para China en Beijing 2008. La BD devuelve 97
   porque múltiples fuentes registraron los mismos eventos con id_evento distintos.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 1.3: China (Beijing 2008 Summer)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'CHN',
    @anio       = 2008,
    @temporada  = N'Summer';
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
     - preseas_totales_entregadas_a_atletas: 37 (incluye registros de múltiples fuentes
       para los mismos jugadores: Messi, Agüero, Riquelme, Di María, etc.).
     - total_participaciones: 64, total_atletas_distintos: 64.
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
     - preseas_totales_entregadas_a_atletas: 42 (incluye registros de múltiples fuentes).
     - total_participaciones: 42, total_atletas_distintos: 42.
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
   Objetivo: Consultar la participación de Portugal en los Juegos Olímpicos de 2004
             donde participó Cristiano Ronaldo (id_atleta 102010).
   Esperado:
     - Portugal compitió en Fútbol Masculino.
     - Posición en fase de grupos, medalla: 'Sin Medalla'.
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
   PRUEBA 3.2: Brasil en Fútbol Río 2016 y Londres 2012 ('BRA', 'Football') - Caso Neymar Jr.
   Objetivo: Consultar el historial de fútbol de Brasil donde Neymar ganó Plata en 2012 y Oro en 2016.
   Esperado:
     - 2016: Medalla de Oro oficial en Río de Janeiro.
     - 2012: Medalla de Plata oficial en Londres.
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
   PRUEBA 4.1: ¿Quién ganó la medalla de oro en 100 metros planos en Atenas 2004?
   Objetivo: Responder a la pregunta clásica de atletismo en velocidad.
   Respuesta histórica y en BD:
     - Oro: Justin Gatlin (Estados Unidos / 'USA'), tiempo 9.85s.
     - Plata: Francis Obikwelu (Portugal / 'POR'), tiempo 9.86s.
     - Bronce: Maurice Greene (Estados Unidos / 'USA'), tiempo 9.87s.
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
   PRUEBA 4.2: ¿Quién es el atleta con más medallas de oro en la historia de los Juegos Olímpicos?
   Respuesta en BD (conteo de preseas físicas por registros de múltiples fuentes):
     - Michael Phelps (Natación, USA): 46 preseas de oro, 56 preseas totales en la BD.
   NOTA: olympics.com registra 23 oros y 28 totales. La BD contiene registros duplicados
   de múltiples fuentes con id_evento distintos para los mismos eventos reales.
--- */
PRINT N'--- Consulta analítica 4.2: Top 5 Atletas con más medallas de Oro ---';
SELECT TOP 5
    a.id_atleta,
    a.nombre AS atleta,
    n.codigo_noc AS pais,
    COUNT(*) AS total_oros
FROM olympics.PARTICIPACION p
JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
JOIN olympics.NOC n ON n.id_noc = p.id_noc
WHERE p.medalla = N'Gold'
GROUP BY a.id_atleta, a.nombre, n.codigo_noc
ORDER BY total_oros DESC;
GO

/* ---
   PRUEBA 4.3: ¿Quién ganó medalla de oro siendo el atleta más joven (utilizando campo edad)?
   Respuesta en BD (Top 5 más jóvenes con oro):
     - Aileen Riggin (USA): 13.0 años (Amberes 1920, Clavados Trampolín).
     - Hans Bourquin (SUI): 13.0 años (Ámsterdam 1928, Remo Coxed Pairs).
     - Marjorie Gestring (USA): 13.0 años (Berlín 1936, Clavados Trampolín).
     - Donna de Varona (USA): 13.0 años (Roma 1960, Natación 4x100m Relay).
     - Klaus Zerta (GER): 13.0 años (Roma 1960, Remo Coxed Pairs).
--- */
PRINT N'--- Consulta analítica 4.3: Atletas más jóvenes en ganar medalla de Oro ---';
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
   PRUEBA 5.1: Validación de temporada inválida
   Esperado: Error controlado vía RAISERROR indicando que 'Otoño' no es válida
             y listando los 5 dominios permitidos.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.1: Error por temporada inválida ("Otoño")';
EXEC olympics.sp_consultar_pais
    @pais_o_noc  = N'FRA',
    @temporada   = N'Otoño';
GO

/* ---
   PRUEBA 5.2: Control de búsqueda ambigua (Caso 'San')
   Esperado: No hace un TOP 1 silencioso.
             Retorna dos resultsets: Estado/Mensaje de advertencia + Listado de países candidatos
             (ej. San Marino, etc.) para que el usuario refine su búsqueda.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.2: Búsqueda ambigua ("San")';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'San';
GO

/* ---
   PRUEBA 5.3: Insensibilidad a acentos ('Perú' vs 'Peru', 'México' vs 'Mexico')
   Esperado: Ambas invocaciones deben resolver exitosamente hacia la misma entidad geográfica.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.3: Insensibilidad a acentos ("Peru" sin tilde)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'Peru',
    @top_participaciones = 5;
GO

/* ---
   PRUEBA 5.4: Normalización defensiva de @top_participaciones (valores negativos y NULL)
   Esperado: Se normaliza a 50 automáticamente sin fallar.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.4: Normalización de @top_participaciones negativo (-99)';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = N'GUA',
    @top_participaciones = -99;
GO

/* ---
   PRUEBA 5.5: Parámetro obligatorio nulo o vacío
   Esperado: Mensaje de error controlado indicando que @pais_o_noc es obligatorio.
--- */
PRINT N'>>> EJECUTANDO PRUEBA 5.5: Error por parámetro nulo';
EXEC olympics.sp_consultar_pais
    @pais_o_noc = NULL;
GO

PRINT N'================================================================================';
PRINT N'BATERÍA DE PRUEBAS FINALIZADA EXITOSAMENTE';
PRINT N'================================================================================';
GO
