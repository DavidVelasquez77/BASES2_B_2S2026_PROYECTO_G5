/* ============================================================================
   Fase 2 - Restauracion 03: aplicar un respaldo diferencial

   Se ejecuta despues de haber restaurado el FULL con MODO=NORECOVERY. Deja la
   base recuperada y lista para consultarse en el estado que tenia justo
   despues de la carga N.

   Parametros:
     DB   nombre de la base
     N    numero de diferencial a aplicar (1, 2 o 3)

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v N="1" -i 03_restaurar_diferencial.sql

   Los diferenciales son acumulativos: el 3 contiene todo lo que cambio desde
   el FULL, no solo lo de la tercera carga. Por eso para llegar al estado N se
   restauran DOS archivos (FULL + diferencial N) y no la cadena completa. Con
   respaldos de log habria que aplicarlos todos en orden.

   El tiempo total de esta estrategia es la suma del RESTORE FULL
   (con NORECOVERY) mas esta operacion. El script de comparacion suma las dos.
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

/* La base tiene que estar en estado "restaurando". Si esta en linea, es que
   el FULL se restauro con RECOVERY y ya no admite diferenciales. */
IF NOT EXISTS (
    SELECT 1 FROM sys.databases
    WHERE name = N'$(DB)' AND state_desc = N'RESTORING'
)
BEGIN
    RAISERROR(N'La base $(DB) no esta en estado RESTORING. Restaure antes el FULL con MODO=NORECOVERY.', 16, 1);
    SET NOEXEC ON;
END;
GO

DECLARE @archivo NVARCHAR(400) = N'/var/opt/mssql/fase2/backups/$(DB)_DIFF_$(N).bak';
DECLARE @inicio  DATETIME2(3);
DECLARE @fin     DATETIME2(3);
DECLARE @sql     NVARCHAR(MAX);

PRINT N'Aplicando DIFERENCIAL $(N) a $(DB) - ' + CONVERT(NVARCHAR(30), SYSDATETIME(), 121);

SET @sql = N'RESTORE DATABASE [$(DB)] FROM DISK = @a WITH RECOVERY, STATS = 25';

SET @inicio = SYSDATETIME();
EXEC sp_executesql @sql, N'@a NVARCHAR(400)', @a = @archivo;
SET @fin = SYSDATETIME();

SELECT
    N'RESTORE DIFERENCIAL $(N)'                  AS operacion,
    N'$(DB)'                                     AS base,
    @archivo                                     AS archivo,
    @inicio                                      AS inicio,
    @fin                                         AS fin,
    DATEDIFF(MILLISECOND, @inicio, @fin)         AS duracion_ms;
GO

SET NOEXEC OFF;
GO

PRINT N'03_restaurar_diferencial.sql finalizado.';
GO
