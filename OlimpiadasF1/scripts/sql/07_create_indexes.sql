/* Bloque 6 — índices no cluster adicionales, creados después de la carga. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.PARTICIPACION') AND name=N'IX_PARTICIPACION_id_atleta')
    CREATE NONCLUSTERED INDEX IX_PARTICIPACION_id_atleta ON olympics.PARTICIPACION(id_atleta);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.PARTICIPACION') AND name=N'IX_PARTICIPACION_id_edicion')
    CREATE NONCLUSTERED INDEX IX_PARTICIPACION_id_edicion ON olympics.PARTICIPACION(id_edicion);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.PARTICIPACION') AND name=N'IX_PARTICIPACION_id_evento')
    CREATE NONCLUSTERED INDEX IX_PARTICIPACION_id_evento ON olympics.PARTICIPACION(id_evento);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.PARTICIPACION') AND name=N'IX_PARTICIPACION_id_noc')
    CREATE NONCLUSTERED INDEX IX_PARTICIPACION_id_noc ON olympics.PARTICIPACION(id_noc);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.PARTICIPACION') AND name=N'IX_PARTICIPACION_id_pais_nacionalidad')
    CREATE NONCLUSTERED INDEX IX_PARTICIPACION_id_pais_nacionalidad ON olympics.PARTICIPACION(id_pais_nacionalidad);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.ATLETA') AND name=N'IX_ATLETA_id_pais_nacionalidad')
    CREATE NONCLUSTERED INDEX IX_ATLETA_id_pais_nacionalidad ON olympics.ATLETA(id_pais_nacionalidad);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.NOC') AND name=N'IX_NOC_id_entidad')
    CREATE NONCLUSTERED INDEX IX_NOC_id_entidad ON olympics.NOC(id_entidad);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'olympics.SEDE') AND name=N'IX_SEDE_id_pais')
    CREATE NONCLUSTERED INDEX IX_SEDE_id_pais ON olympics.SEDE(id_pais);
GO

PRINT N'07_create_indexes.sql finalizado. Índices adicionales creados de forma idempotente.';
GO
