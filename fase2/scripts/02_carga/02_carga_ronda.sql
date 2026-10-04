/* ============================================================================
   Fase 2 - Carga 02: carga incremental de una ronda

   Carga una de las tres rondas de datos que siguen a la carga inicial. Cada
   ejecucion trae los atletas nuevos de la ronda y sus participaciones, y es la
   que despues se respalda con un backup diferencial.

   Parametros:
     DB      nombre de la base destino
     TIPO    anio | deporte | deportista
     RONDA   r1 | r2 | r3

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v TIPO="anio" -v RONDA="r1" -i 02_carga_ronda.sql

   Correspondencia de rondas (ver fase2/data/slices/manifiesto.json):
     anio        r1 Rio 2016      r2 Tokio 2020    r3 Paris 2024
     deporte     r1 Atletismo Rio r2 Atletismo Tok r3 Atletismo Par
     deportista  r1 Bolt Atenas   r2 Bolt Pekin    r3 Bolt Londres

   ATLETA va antes que PARTICIPACION porque la segunda tiene una llave foranea
   hacia la primera. Los atletas ya insertados en una ronda anterior no vienen
   repetidos: el generador de recortes los excluye.
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
PRINT N'Carga $(TIPO)/$(RONDA) en $(DB) - inicio ' + CONVERT(NVARCHAR(30), SYSDATETIME(), 121);
GO

/* Preflight: los catalogos deben estar cargados. Sin ellos las llaves
   foraneas de PARTICIPACION fallarian con un error poco descriptivo. */
IF NOT EXISTS (SELECT 1 FROM olympics.EVENTO)
BEGIN
    RAISERROR(N'Los catalogos estan vacios. Ejecute primero 01_carga_inicial_catalogos.sql.', 16, 1);
    SET NOEXEC ON;
END;
GO

DECLARE @atletas_antes BIGINT = (SELECT COUNT(*) FROM olympics.ATLETA);
DECLARE @part_antes    BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION);

BULK INSERT olympics.ATLETA
FROM '/var/opt/mssql/fase2/slices/$(TIPO)/$(RONDA)_atleta.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.PARTICIPACION
FROM '/var/opt/mssql/fase2/slices/$(TIPO)/$(RONDA)_participacion.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

SELECT
    N'$(TIPO)/$(RONDA)'                                    AS carga,
    @atletas_antes                                         AS atletas_antes,
    (SELECT COUNT(*) FROM olympics.ATLETA)                 AS atletas_despues,
    (SELECT COUNT(*) FROM olympics.ATLETA) - @atletas_antes AS atletas_nuevos,
    @part_antes                                            AS participaciones_antes,
    (SELECT COUNT(*) FROM olympics.PARTICIPACION)          AS participaciones_despues,
    (SELECT COUNT(*) FROM olympics.PARTICIPACION) - @part_antes AS participaciones_nuevas;
GO

SET NOEXEC OFF;
GO

PRINT N'02_carga_ronda.sql finalizado: $(TIPO)/$(RONDA) en $(DB).';
GO
