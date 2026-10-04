/* ============================================================================
   Fase 2 - Restauracion 01: eliminar la base

   El enunciado exige borrar la base completa antes de restaurar, para que la
   prueba de recuperabilidad sea real y no una restauracion sobre datos que ya
   estaban ahi.

   Parametro:  DB  nombre de la base a eliminar

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 01_eliminar_base.sql

   SINGLE_USER WITH ROLLBACK IMMEDIATE cierra cualquier conexion abierta contra
   la base; sin eso el DROP se queda esperando indefinidamente si quedo una
   sesion de SSMS conectada.

   Los archivos .bak NO se tocan: viven fuera de la base, en
   /var/opt/mssql/fase2/backups/. Eliminar la base y conservar los respaldos es
   justamente lo que hace valida la prueba.
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

IF DB_ID(N'$(DB)') IS NULL
BEGIN
    PRINT N'La base $(DB) no existe; no hay nada que eliminar.';
END
ELSE
BEGIN
    DECLARE @filas_antes NVARCHAR(200);
    DECLARE @sql NVARCHAR(MAX);

    /* Se deja constancia de cuantas filas habia antes de borrar, para poder
       compararlo contra lo que devuelva la restauracion.
       La consulta se arma en una variable: sp_executesql no admite una
       concatenacion como primer argumento, solo una variable o un literal. */
    SET @sql = N'SELECT @salida = CONCAT(''atletas='',
                     (SELECT COUNT(*) FROM [$(DB)].olympics.ATLETA),
                     '' participaciones='',
                     (SELECT COUNT(*) FROM [$(DB)].olympics.PARTICIPACION))';

    EXEC sp_executesql @sql, N'@salida NVARCHAR(200) OUTPUT', @salida = @filas_antes OUTPUT;

    PRINT N'Estado antes de eliminar: ' + ISNULL(@filas_antes, N'(sin datos)');

    ALTER DATABASE [$(DB)] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE [$(DB)];

    PRINT N'Base $(DB) eliminada a las ' + CONVERT(NVARCHAR(30), SYSDATETIME(), 121);
END;
GO

/* Comprobacion: la base ya no debe aparecer en el catalogo del servidor. */
SELECT
    N'$(DB)'                                          AS base,
    CASE WHEN DB_ID(N'$(DB)') IS NULL
         THEN N'ELIMINADA' ELSE N'TODAVIA EXISTE' END AS estado,
    SYSDATETIME()                                     AS momento;
GO

PRINT N'01_eliminar_base.sql finalizado.';
GO
