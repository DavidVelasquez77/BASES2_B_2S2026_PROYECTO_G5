/*
========================================================================================
Sistemas de Bases de Datos 2 — 2do. Semestre 2026
Proyecto Fase 1: Olimpiadas (1896 - 2024)
Grupo 7 — Inciso e) Stored Procedure de País

Archivo: consultas_ejemplo.sql
Ruta: storeprocedure_pais/consultas_ejemplo.sql
Propósito: Banco de consultas de ejemplo preparadas para la calificación presencial
           e interactiva con el Catedrático.
           Incluye los casos de interés del Ingeniero:
           - Medallistas de Guatemala (Ruano, Barrondo, Brol)
           - Futbolistas famosos (Messi en ARG 2008, Cristiano Ronaldo en POR 2004, Neymar en BRA 2012/2016)
           - Atletas legendarios (Michael Phelps en USA, Usain Bolt en JAM)
           - Delegaciones especiales (ROC, EOR)
           - Manejo defensivo y resolución de ambigüedad
========================================================================================
*/

USE OlimpiadasDB;
GO

SET NOCOUNT ON;
GO


/* ============================================================================
   1. GUATEMALA (GUA) — MEDALLISTAS HISTÓRICOS Y DESEMPEÑO
============================================================================ */

-- 1.1 Consulta general de Guatemala (594 participaciones, 263 atletas, 3 medallas oficiales)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'GUA';
GO

-- 1.2 Guatemala filtrado por temporada de Verano (demuestra insensibilidad a mayúsculas)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'GUA', @temporada = N'summer';
GO

-- 1.3 Guatemala en Tiro Deportivo (Oro de Adriana Ruano y Bronce de Pierre Brol en París 2024)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'GUA', @deporte = N'Shooting';
GO

-- 1.4 Guatemala en Atletismo (Plata histórica de Érick Barrondo en Londres 2012)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'GUA', @deporte = N'Athletics', @anio = 2012;
GO


/* ============================================================================
   2. ATLETAS Y PAÍSES FAMOSOS DE INTERÉS DEL CATEDRÁTICO
============================================================================ */

-- 2.1 ARGENTINA — Lionel Messi (Fútbol Masculino Beijing 2008, Medalla de Oro)
-- Demuestra la regla anti-inflación: 1 solo Oro oficial para el país, 37 preseas físicas.
EXEC olympics.sp_consultar_pais @pais_o_noc = N'ARG', @anio = 2008, @deporte = N'Football';
GO

-- 2.2 PORTUGAL — Cristiano Ronaldo (Fútbol Masculino Atenas 2004, id_atleta 102010)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'POR', @anio = 2004, @deporte = N'Football';
GO

-- 2.3 BRASIL — Neymar Jr. (Fútbol Masculino Londres 2012 Plata y Río 2016 Oro)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'BRA', @deporte = N'Football', @top_participaciones = 30;
GO

-- 2.4 ESTADOS UNIDOS — Michael Phelps (Natación Beijing 2008 / Londres 2012 / Río 2016)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'USA', @deporte = N'Aquatics', @anio = 2008;
GO

-- 2.5 ESTADOS UNIDOS — Baloncesto Londres 2012 (LeBron James, Kobe Bryant, Kevin Durant)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'USA', @anio = 2012, @deporte = N'Basketball';
GO

-- 2.6 JAMAICA — Usain Bolt (Atletismo Beijing 2008 / Londres 2012 / Río 2016)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'JAM', @deporte = N'Athletics', @anio = 2012;
GO


/* ============================================================================
   3. PAÍSES ANFITRIONES Y SEDES OLÍMPICAS MÚLTIPLES
============================================================================ */

-- 3.1 FRANCIA — 6 ediciones olímpicas albergadas (París 1900, 1924, 2024; Chamonix, Grenoble, Albertville)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'France';
GO

-- 3.2 ESTADOS UNIDOS — 8 ediciones olímpicas organizadas como sede
EXEC olympics.sp_consultar_pais @pais_o_noc = N'USA', @top_participaciones = 10;
GO

-- 3.3 JAPÓN — Historial de Tokio 1964, Sapporo 1972, Nagano 1998 y Tokio 2020
EXEC olympics.sp_consultar_pais @pais_o_noc = N'JPN';
GO


/* ============================================================================
   4. DELEGACIONES ESPECIALES (NOCs con id_entidad IS NULL)
============================================================================ */

-- 4.1 ROC — Comité Olímpico Ruso (Tokio 2020 y Beijing 2022: 184 medallas oficiales)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'ROC', @top_participaciones = 15;
GO

-- 4.2 EOR — Equipo Olímpico de Refugiados (Medalla histórica de Bronce en París 2024)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'EOR';
GO

-- 4.3 AIN — Atletas Neutrales Individuales (París 2024)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'AIN';
GO


/* ============================================================================
   5. CONTROL DEFENSIVO DE ERRORES Y AMBIGÜEDAD
============================================================================ */

-- 5.1 Búsqueda ambigua: 'Korea' (despliega opciones entre PRK y KOR sin hacer TOP 1 ciego)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'Korea';
GO

-- 5.2 Búsqueda ambigua: 'San' (despliega lista de candidatos)
EXEC olympics.sp_consultar_pais @pais_o_noc = N'San';
GO

-- 5.3 Búsqueda insensible a acentos: 'Peru' sin tilde resuelve a 'Perú'
EXEC olympics.sp_consultar_pais @pais_o_noc = N'Peru', @top_participaciones = 5;
GO

-- 5.4 Temporada inválida: Mensaje descriptivo con lista cerrada de dominios válidos
EXEC olympics.sp_consultar_pais @pais_o_noc = N'GUA', @temporada = N'Primavera';
GO

-- 5.5 País inexistente: Manejo limpio sin excepciones no controladas
EXEC olympics.sp_consultar_pais @pais_o_noc = N'Atlantis';
GO
