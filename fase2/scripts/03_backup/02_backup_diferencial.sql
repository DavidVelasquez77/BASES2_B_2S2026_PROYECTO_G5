/* ============================================================================
   Fase 2 - Backup 02: respaldo diferencial

   Se ejecuta despues de cada una de las tres cargas que siguen a la inicial.
   Un diferencial guarda todo lo que cambio desde el ultimo FULL, no desde el
   diferencial anterior: por eso son acumulativos y cada uno es algo mas grande
   que el anterior.

   Por que diferencial y no incremental:
   SQL Server no tiene respaldo incremental. Sus tres tipos son FULL,
   DIFFERENTIAL y LOG. El incremental en el sentido de "solo lo que cambio
   desde el respaldo anterior" se aproxima con la cadena de respaldos de log,
   que exige modelo de recuperacion FULL y restaurar la cadena completa en
   orden. El enunciado permite elegir entre incremental y diferencial segun las
   limitaciones del motor, y aqui la limitacion es del motor.

   Consecuencia practica para la restauracion: recuperar el estado de la carga
   N necesita exactamente dos archivos, el FULL y el diferencial N. No hace
   falta aplicar los diferenciales intermedios.

   Parametros:
     DB          nombre de la base
     N           numero de diferencial (1, 2 o 3)
     COMPRIMIR   1 aplica WITH COMPRESSION, 0 no

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v N="1" -v COMPRIMIR="0" -i 02_backup_diferencial.sql

   Archivo generado: /var/opt/mssql/fase2/backups/<DB>_DIFF_<N>.bak
============================================================================ */

SET NOCOUNT ON;
GO

/* Un diferencial sin FULL previo no se puede crear. SQL Server lo rechazaria
   con un mensaje poco claro, asi que se valida antes. */
IF NOT EXISTS (
    SELECT 1 FROM msdb.dbo.backupset
    WHERE database_name = N'$(DB)' AND type = 'D'
)
BEGIN
    RAISERROR(N'No existe un respaldo FULL de $(DB). Ejecute antes 01_backup_full.sql.', 16, 1);
    SET NOEXEC ON;
END;
GO

DECLARE @db      SYSNAME       = N'$(DB)';
DECLARE @archivo NVARCHAR(400) = N'/var/opt/mssql/fase2/backups/$(DB)_DIFF_$(N).bak';
DECLARE @inicio  DATETIME2(3)  = SYSDATETIME();
DECLARE @sql     NVARCHAR(MAX);

PRINT N'DIFERENCIAL $(N) de ' + @db + N' - inicio ' + CONVERT(NVARCHAR(30), @inicio, 121);

SET @sql = N'BACKUP DATABASE [' + @db + N'] TO DISK = @a WITH DIFFERENTIAL, INIT, CHECKSUM, STATS = 25, '
         + CASE WHEN N'$(COMPRIMIR)' = N'1' THEN N'COMPRESSION, ' ELSE N'NO_COMPRESSION, ' END
         + N'NAME = ''DIFF $(N) ' + @db + N'''';

EXEC sp_executesql @sql, N'@a NVARCHAR(400)', @a = @archivo;

DECLARE @fin DATETIME2(3) = SYSDATETIME();

SELECT
    N'DIFERENCIAL $(N)'                            AS tipo_respaldo,
    @db                                            AS base,
    @archivo                                       AS archivo,
    @inicio                                        AS inicio,
    @fin                                           AS fin,
    DATEDIFF(MILLISECOND, @inicio, @fin)           AS duracion_ms;
GO

RESTORE VERIFYONLY FROM DISK = N'/var/opt/mssql/fase2/backups/$(DB)_DIFF_$(N).bak' WITH CHECKSUM;
GO

SET NOEXEC OFF;
GO

PRINT N'02_backup_diferencial.sql finalizado: diferencial $(N) de $(DB).';
GO
