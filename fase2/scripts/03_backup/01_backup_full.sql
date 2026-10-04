/* ============================================================================
   Fase 2 - Backup 01: respaldo completo (FULL)

   Se ejecuta una sola vez por base, inmediatamente despues de la carga inicial
   de catalogos. Es la linea base sobre la que se apoyan los tres diferenciales
   posteriores: un diferencial no se puede restaurar sin su FULL.

   Parametros:
     DB          nombre de la base a respaldar
     COMPRIMIR   1 aplica WITH COMPRESSION, 0 no (por defecto 0)

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v COMPRIMIR="0" -i 01_backup_full.sql

   Archivo generado: /var/opt/mssql/fase2/backups/<DB>_FULL.bak
   Esa ruta vive dentro del volumen persistente sqlserver_data, asi que los
   respaldos sobreviven a que el contenedor se reinicie o se recree.

   INIT sobrescribe el archivo en cada corrida. Sin el, SQL Server anexa un
   juego de respaldo mas al mismo .bak y el archivo crece sin control, lo que
   ademas invalida la comparacion de tamanos del analisis.

   CHECKSUM + STATS: el primero verifica las paginas al escribirlas, el segundo
   imprime el avance para que quede en el log.
============================================================================ */

SET NOCOUNT ON;
GO

DECLARE @db      SYSNAME       = N'$(DB)';
DECLARE @archivo NVARCHAR(400) = N'/var/opt/mssql/fase2/backups/$(DB)_FULL.bak';
DECLARE @inicio  DATETIME2(3)  = SYSDATETIME();
DECLARE @sql     NVARCHAR(MAX);

PRINT N'FULL de ' + @db + N' - inicio ' + CONVERT(NVARCHAR(30), @inicio, 121);

SET @sql = N'BACKUP DATABASE [' + @db + N'] TO DISK = @a WITH INIT, CHECKSUM, STATS = 25, '
         + CASE WHEN N'$(COMPRIMIR)' = N'1' THEN N'COMPRESSION, ' ELSE N'NO_COMPRESSION, ' END
         + N'NAME = ''FULL ' + @db + N'''';

EXEC sp_executesql @sql, N'@a NVARCHAR(400)', @a = @archivo;

DECLARE @fin DATETIME2(3) = SYSDATETIME();

SELECT
    N'FULL'                                        AS tipo_respaldo,
    @db                                            AS base,
    @archivo                                       AS archivo,
    @inicio                                        AS inicio,
    @fin                                           AS fin,
    DATEDIFF(MILLISECOND, @inicio, @fin)           AS duracion_ms;
GO

/* Verificacion inmediata: confirma que el .bak es legible y que su checksum
   cuadra. No restaura nada. Si esto falla, el respaldo no sirve y es mejor
   saberlo ahora que el dia que haya que usarlo. */
RESTORE VERIFYONLY FROM DISK = N'/var/opt/mssql/fase2/backups/$(DB)_FULL.bak' WITH CHECKSUM;
GO

/* Metadatos del respaldo recien creado, para la bitacora del informe. */
SELECT TOP 1
    bs.database_name                                          AS base,
    bs.type                                                   AS tipo,     -- D = full, I = diferencial
    bs.backup_start_date                                      AS inicio,
    bs.backup_finish_date                                     AS fin,
    DATEDIFF(MILLISECOND, bs.backup_start_date, bs.backup_finish_date) AS duracion_ms,
    CAST(bs.backup_size     / 1024.0 / 1024.0 AS DECIMAL(12,2)) AS tamano_mb,
    CAST(bs.compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(12,2)) AS tamano_comprimido_mb,
    bmf.physical_device_name                                  AS archivo
FROM msdb.dbo.backupset bs
JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id
WHERE bs.database_name = N'$(DB)' AND bs.type = 'D'
ORDER BY bs.backup_finish_date DESC;
GO

PRINT N'01_backup_full.sql finalizado.';
GO
