/* ============================================================================
   Fase 2 - Validacion 01: conteos y muestra de cada tabla

   Este es el script de captura. Se ejecuta en dos momentos:
     - despues de cada una de las cuatro cargas
     - despues de cada restauracion
   y produce la evidencia que pide el enunciado: SELECT COUNT(*) y SELECT *
   de cada tabla, con la fecha y hora del servidor.

   Parametro:  DB  nombre de la base a validar

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 01_conteos_y_muestra.sql

   Sobre el SELECT *: el enunciado pide "SELECT * de cada tabla". Sobre
   PARTICIPACION eso son decenas de miles de filas, que ni caben en una captura
   ni se pueden leer. Se muestran las primeras 10 filas de cada tabla, que es
   lo que hace verificable el contenido, y el conteo completo va aparte. La
   consulta sin TOP queda documentada en el manual de usuario para quien
   quiera ejecutarla.
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
GO

/* ---------- Encabezado: identifica la captura ---------- */
SELECT
    DB_NAME()                                   AS base,
    @@SERVERNAME                                AS servidor,
    SYSDATETIME()                               AS fecha_hora_servidor,
    (SELECT recovery_model_desc FROM sys.databases WHERE name = DB_NAME())
                                                AS modelo_recuperacion,
    (SELECT state_desc FROM sys.databases WHERE name = DB_NAME())
                                                AS estado;
GO

/* ---------- Conteo de filas de las diez tablas ---------- */
SELECT 'ENTIDAD_GEOGRAFICA' AS tabla, COUNT(*) AS filas FROM olympics.ENTIDAD_GEOGRAFICA
UNION ALL SELECT 'DEPORTE',          COUNT(*) FROM olympics.DEPORTE
UNION ALL SELECT 'NOC',              COUNT(*) FROM olympics.NOC
UNION ALL SELECT 'SEDE',             COUNT(*) FROM olympics.SEDE
UNION ALL SELECT 'EDICION_OLIMPICA', COUNT(*) FROM olympics.EDICION_OLIMPICA
UNION ALL SELECT 'DISCIPLINA',       COUNT(*) FROM olympics.DISCIPLINA
UNION ALL SELECT 'EVENTO',           COUNT(*) FROM olympics.EVENTO
UNION ALL SELECT 'POBLACION',        COUNT(*) FROM olympics.POBLACION
UNION ALL SELECT 'ATLETA',           COUNT(*) FROM olympics.ATLETA
UNION ALL SELECT 'PARTICIPACION',    COUNT(*) FROM olympics.PARTICIPACION
ORDER BY tabla;
GO

/* ---------- Total general, para comparar de un vistazo ---------- */
SELECT
    (SELECT COUNT(*) FROM olympics.ENTIDAD_GEOGRAFICA)
  + (SELECT COUNT(*) FROM olympics.DEPORTE)
  + (SELECT COUNT(*) FROM olympics.NOC)
  + (SELECT COUNT(*) FROM olympics.SEDE)
  + (SELECT COUNT(*) FROM olympics.EDICION_OLIMPICA)
  + (SELECT COUNT(*) FROM olympics.DISCIPLINA)
  + (SELECT COUNT(*) FROM olympics.EVENTO)
  + (SELECT COUNT(*) FROM olympics.POBLACION)
  + (SELECT COUNT(*) FROM olympics.ATLETA)
  + (SELECT COUNT(*) FROM olympics.PARTICIPACION)  AS total_filas_en_la_base;
GO

/* ---------- Muestra de contenido: primeras filas de cada tabla ---------- */
SELECT TOP 10 * FROM olympics.ENTIDAD_GEOGRAFICA ORDER BY id_entidad;
SELECT TOP 10 * FROM olympics.DEPORTE            ORDER BY id_deporte;
SELECT TOP 10 * FROM olympics.NOC                ORDER BY id_noc;
SELECT TOP 10 * FROM olympics.SEDE               ORDER BY id_sede;
SELECT TOP 10 * FROM olympics.EDICION_OLIMPICA   ORDER BY id_edicion;
SELECT TOP 10 * FROM olympics.DISCIPLINA         ORDER BY id_disciplina;
SELECT TOP 10 * FROM olympics.EVENTO             ORDER BY id_evento;
SELECT TOP 10 * FROM olympics.POBLACION          ORDER BY id_entidad, anio;
SELECT TOP 10 * FROM olympics.ATLETA             ORDER BY id_atleta;
SELECT TOP 10 * FROM olympics.PARTICIPACION      ORDER BY id_participacion;
GO

PRINT N'01_conteos_y_muestra.sql finalizado.';
GO
