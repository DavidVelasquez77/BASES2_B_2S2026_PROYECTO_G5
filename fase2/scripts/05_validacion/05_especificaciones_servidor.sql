/* ============================================================================
   Fase 2 - Validacion 05: especificaciones tecnicas del servidor

   La Documentacion Tecnica que pide el enunciado debe incluir las
   "especificaciones tecnicas del servidor". Este script las reune todas en una
   sola salida, para capturarlas de una vez y no tener que buscarlas despues.

   Reporta: version y edicion del motor, modelo de licencia, sistema operativo,
   CPU y memoria asignadas al contenedor, configuracion de memoria del motor,
   espacio en disco del volumen de datos, y el tamano de cada base de la Fase 2.

   No recibe parametros.

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -i 05_especificaciones_servidor.sql

   Nota: los valores de CPU y memoria son los que ve SQL Server dentro del
   contenedor, es decir los que Docker Desktop le asigno, no necesariamente los
   de la maquina fisica completa.
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

PRINT N'--- Motor de base de datos ---';
SELECT
    SERVERPROPERTY('ProductVersion')                      AS version,
    SERVERPROPERTY('ProductLevel')                        AS nivel,
    SERVERPROPERTY('Edition')                             AS edicion,
    SERVERPROPERTY('EngineEdition')                       AS tipo_motor,
    SERVERPROPERTY('Collation')                           AS colacion,
    SERVERPROPERTY('MachineName')                         AS maquina,
    SYSDATETIME()                                         AS fecha_hora_servidor;
GO

PRINT N'--- Sistema operativo y recursos asignados ---';
SELECT
    host_platform                                         AS plataforma,
    host_distribution                                     AS distribucion,
    host_release                                          AS version_so,
    host_architecture                                     AS arquitectura
FROM sys.dm_os_host_info;
GO

SELECT
    cpu_count                                             AS cpus_visibles,
    scheduler_count                                       AS planificadores,
    CAST(physical_memory_kb / 1024.0 AS DECIMAL(10,0))    AS memoria_fisica_mb,
    CAST(committed_target_kb / 1024.0 AS DECIMAL(10,0))   AS memoria_objetivo_mb,
    sqlserver_start_time                                  AS motor_iniciado
FROM sys.dm_os_sys_info;
GO

PRINT N'--- Espacio en disco del volumen de datos ---';
SELECT DISTINCT
    vs.volume_mount_point                                        AS volumen,
    vs.file_system_type                                          AS sistema_archivos,
    CAST(vs.total_bytes     / 1073741824.0 AS DECIMAL(10,2))     AS total_gb,
    CAST(vs.available_bytes / 1073741824.0 AS DECIMAL(10,2))     AS disponible_gb
FROM sys.master_files AS mf
CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) AS vs;
GO

PRINT N'--- Tamano de las bases de la Fase 2 ---';
SELECT
    DB_NAME(mf.database_id)                                      AS base,
    mf.type_desc                                                 AS tipo_archivo,
    CAST(mf.size * 8.0 / 1024 AS DECIMAL(10,2))                  AS tamano_mb,
    (SELECT recovery_model_desc FROM sys.databases d
      WHERE d.database_id = mf.database_id)                      AS modelo_recuperacion
FROM sys.master_files mf
WHERE DB_NAME(mf.database_id) LIKE 'OlimpiadasF2%'
ORDER BY base, mf.type_desc DESC;
GO

PRINT N'05_especificaciones_servidor.sql finalizado.';
GO
