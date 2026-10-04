/* ============================================================================
   Fase 2 - Backup 03: inventario de los respaldos de una base

   Lista los cuatro respaldos generados durante el ciclo (1 completo y 3
   diferenciales) con su tipo, fecha y hora, duracion, tamano y archivo.

   Sirve como la evidencia unica de la ejecucion de respaldos que pide el
   criterio 2.2 de la rubrica: "se registran todos los archivos y se documenta
   la fecha/hora". Una sola captura muestra los cuatro, en vez de una captura
   por respaldo; el detalle de cada operacion queda en el log de la ejecucion.

   Parametro:  DB  nombre de la base

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 03_inventario_respaldos.sql

   La columna tipo viene de msdb: D = completo (full), I = diferencial.
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

SELECT
    N'$(DB)'      AS base,
    SYSDATETIME() AS fecha_hora_servidor;
GO

/* msdb guarda el historial de todas las corridas. Se toma el respaldo mas
   reciente de cada archivo, que es el que esta en disco ahora mismo. */
WITH ultimos AS (
    SELECT
        bmf.physical_device_name,
        bs.type,
        bs.backup_start_date,
        bs.backup_finish_date,
        bs.backup_size,
        bs.compressed_backup_size,
        ISNULL(bs.compression_algorithm, 'ninguno') AS compresion,
        ROW_NUMBER() OVER (PARTITION BY bmf.physical_device_name
                           ORDER BY bs.backup_finish_date DESC) AS rn
    FROM msdb.dbo.backupset bs
    JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id
    WHERE bs.database_name = N'$(DB)'
      AND bmf.physical_device_name LIKE '%/fase2/backups/$(DB)[_]%'
)
/* No se muestra una duracion calculada desde msdb: backup_start_date y
   backup_finish_date son DATETIME con precision de segundos, y a este volumen
   los respaldos tardan milisegundos, asi que la resta siempre daria 0. La
   duracion exacta la mide cada script de respaldo con SYSDATETIME() y queda
   en el log de la ejecucion. */
SELECT
    CASE type WHEN 'D' THEN 'completo' WHEN 'I' THEN 'diferencial'
              ELSE type END                                          AS tipo,
    /* Solo el nombre del archivo, sin la ruta: se corta por la ultima barra. */
    REVERSE(LEFT(REVERSE(physical_device_name),
                 CHARINDEX('/', REVERSE(physical_device_name)) - 1))  AS archivo,
    backup_start_date                                                AS fecha_hora,
    CAST(compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(12,2))  AS tamano_mb,
    compresion
FROM ultimos
WHERE rn = 1
ORDER BY type ASC, physical_device_name;   /* D = completo primero, luego los diferenciales */
GO

PRINT N'03_inventario_respaldos.sql finalizado.';
GO
