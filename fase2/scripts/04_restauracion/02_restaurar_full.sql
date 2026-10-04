/* ============================================================================
   Fase 2 - Restauracion 02: restaurar el respaldo completo

   Parametros:
     DB     nombre de la base a restaurar
     MODO   RECOVERY   deja la base lista para usarse. Es el caso de la
                       restauracion "solo full", que es una de las dos
                       estrategias que se comparan.
            NORECOVERY deja la base en estado de restauracion para poder
                       aplicarle despues un diferencial.

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v MODO="RECOVERY" -i 02_restaurar_full.sql

   Sobre la medicion del tiempo: se toma con SYSDATETIME() justo antes y justo
   despues del RESTORE, en el mismo lote, de modo que no incluya el arranque de
   sqlcmd ni la conexion. Es el tiempo que el motor tarda en la restauracion.

   Una base restaurada WITH NORECOVERY no admite consultas: aparece como
   "Restoring..." hasta que se le aplique el diferencial o se la recupere. Eso
   es esperado, no un error.
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

DECLARE @archivo NVARCHAR(400) = N'/var/opt/mssql/fase2/backups/$(DB)_FULL.bak';
DECLARE @inicio  DATETIME2(3);
DECLARE @fin     DATETIME2(3);
DECLARE @sql     NVARCHAR(MAX);

PRINT N'Restaurando FULL de $(DB) en modo $(MODO) - ' + CONVERT(NVARCHAR(30), SYSDATETIME(), 121);

SET @sql = N'RESTORE DATABASE [$(DB)] FROM DISK = @a WITH REPLACE, $(MODO), STATS = 25';

SET @inicio = SYSDATETIME();
EXEC sp_executesql @sql, N'@a NVARCHAR(400)', @a = @archivo;
SET @fin = SYSDATETIME();

SELECT
    N'RESTORE FULL'                              AS operacion,
    N'$(DB)'                                     AS base,
    N'$(MODO)'                                   AS modo,
    @archivo                                     AS archivo,
    @inicio                                      AS inicio,
    @fin                                         AS fin,
    DATEDIFF(MILLISECOND, @inicio, @fin)         AS duracion_ms;
GO

PRINT N'02_restaurar_full.sql finalizado.';
GO
