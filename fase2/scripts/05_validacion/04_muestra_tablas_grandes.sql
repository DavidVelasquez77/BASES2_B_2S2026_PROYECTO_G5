/* ============================================================================
   Fase 2 - Validacion 04: muestra de las dos tablas de datos

   Complementa a 01_conteos_y_muestra.sql. Aquel recorre las diez tablas y su
   salida no cabe en una sola pantalla: ATLETA tiene 25 columnas y cada fila
   ocupa varias lineas de consola. Este muestra solo ATLETA y PARTICIPACION,
   que son las dos que reciben los datos de cada carga, con pocas columnas y
   pocas filas, para que la captura quepa entera.

   La evidencia queda asi en tres niveles:
     - captura de 01: los COUNT(*) de las diez tablas
     - captura de 04: el contenido real de las dos tablas que cambian
     - log de la ejecucion: la salida completa de SELECT * de las diez

   Parametro:  DB  nombre de la base

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 04_muestra_tablas_grandes.sql
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
GO

SELECT
    DB_NAME()      AS base,
    SYSDATETIME()  AS fecha_hora_servidor,
    (SELECT COUNT(*) FROM olympics.ATLETA)        AS total_atletas,
    (SELECT COUNT(*) FROM olympics.PARTICIPACION) AS total_participaciones;
GO

PRINT N'--- ATLETA: primeras 5 filas (subconjunto legible de las 25 columnas) ---';
SELECT TOP 5
    id_atleta, nombre, sexo, fecha_nacimiento,
    id_pais_nacimiento, altura_cm, peso_kg
FROM olympics.ATLETA
ORDER BY id_atleta;
GO

PRINT N'--- PARTICIPACION: primeras 5 filas ---';
SELECT TOP 5
    id_participacion, id_atleta, id_edicion, id_evento, id_noc,
    edad, posicion, medalla
FROM olympics.PARTICIPACION
ORDER BY id_participacion;
GO

PRINT N'--- PARTICIPACION: ultimas 5 filas (lo que agrego la carga mas reciente) ---';
SELECT TOP 5
    id_participacion, id_atleta, id_edicion, id_evento, id_noc,
    edad, posicion, medalla
FROM olympics.PARTICIPACION
ORDER BY id_participacion DESC;
GO

/* Distribucion por edicion: confirma que estan las tres cargas y cuantas
   filas aporto cada una. Es la comprobacion mas directa de que la carga
   incremental funciono como se esperaba. */
PRINT N'--- Distribucion de las participaciones por edicion olimpica ---';
SELECT
    eo.anio,
    eo.temporada,
    s.nombre                AS sede,
    COUNT(*)                AS participaciones,
    COUNT(DISTINCT p.id_atleta) AS atletas
FROM olympics.PARTICIPACION p
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
LEFT JOIN olympics.SEDE s         ON s.id_sede     = eo.id_sede
GROUP BY eo.anio, eo.temporada, s.nombre
ORDER BY eo.anio;
GO

PRINT N'04_muestra_tablas_grandes.sql finalizado.';
GO
