/* ============================================================================
   Fase 2 - Carga 01: carga inicial (catalogos)

   Es la primera de las cuatro cargas de cada base y la que precede al FULL
   backup. Trae las ocho tablas de catalogo completas: son las dimensiones del
   modelo y no dependen del recorte (ano, deporte o deportista) que se cargue
   despues.

   Los atletas y las participaciones NO entran aqui: llegan en las tres cargas
   siguientes, que son las que generan los respaldos diferenciales. Si los
   atletas se cargaran de una vez en este paso, los tres diferenciales tendrian
   practicamente el mismo tamano y el analisis comparativo no mostraria nada.

   Parametro:  DB  nombre de la base destino

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 01_carga_inicial_catalogos.sql

   Origen: /var/opt/mssql/fase2/slices/catalogos/<tabla>.csv
   Los CSV se generan con fase2/scripts/00_generar_slices.py y se copian al
   contenedor con fase2/scripts/copiar_slices.ps1.

   CODEPAGE no se especifica: SQL Server sobre Linux no lo admite (Msg 16202).
   Los CSV son UTF-8 y las columnas son NVARCHAR, asi que se leen bien sin el.

   ROWTERMINATOR = '0x0a': los recortes se escriben con terminador LF. El
   .gitattributes de fase2/ evita que un checkout de Windows los pase a CRLF,
   que es lo que rompia la carga de la Fase 1.
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
DECLARE @inicio DATETIME2(3) = SYSDATETIME();
PRINT N'Carga inicial de catalogos en $(DB) - inicio ' + CONVERT(NVARCHAR(30), @inicio, 121);
GO

/* Preflight: la carga inicial solo corre sobre catalogos vacios. Evita
   duplicar filas si el script se ejecuta dos veces por error. */
IF EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA)
BEGIN
    RAISERROR(N'Los catalogos ya tienen datos. Elimine la base y vuelva a crearla antes de recargar.', 16, 1);
    SET NOEXEC ON;
END;
GO

/* El orden respeta las llaves foraneas: primero las tablas referenciadas. */

BULK INSERT olympics.ENTIDAD_GEOGRAFICA
FROM '/var/opt/mssql/fase2/slices/catalogos/entidad_geografica.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.DEPORTE
FROM '/var/opt/mssql/fase2/slices/catalogos/deporte.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.NOC
FROM '/var/opt/mssql/fase2/slices/catalogos/noc.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.SEDE
FROM '/var/opt/mssql/fase2/slices/catalogos/sede.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.EDICION_OLIMPICA
FROM '/var/opt/mssql/fase2/slices/catalogos/edicion_olimpica.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.DISCIPLINA
FROM '/var/opt/mssql/fase2/slices/catalogos/disciplina.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.EVENTO
FROM '/var/opt/mssql/fase2/slices/catalogos/evento.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);

BULK INSERT olympics.POBLACION
FROM '/var/opt/mssql/fase2/slices/catalogos/poblacion.csv'
WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
GO

SET NOEXEC OFF;
GO

/* Conteo inmediato, para que quede en el log junto a la hora de ejecucion. */
SELECT 'ENTIDAD_GEOGRAFICA' AS tabla, COUNT(*) AS filas FROM olympics.ENTIDAD_GEOGRAFICA
UNION ALL SELECT 'DEPORTE',          COUNT(*) FROM olympics.DEPORTE
UNION ALL SELECT 'NOC',              COUNT(*) FROM olympics.NOC
UNION ALL SELECT 'SEDE',             COUNT(*) FROM olympics.SEDE
UNION ALL SELECT 'EDICION_OLIMPICA', COUNT(*) FROM olympics.EDICION_OLIMPICA
UNION ALL SELECT 'DISCIPLINA',       COUNT(*) FROM olympics.DISCIPLINA
UNION ALL SELECT 'EVENTO',           COUNT(*) FROM olympics.EVENTO
UNION ALL SELECT 'POBLACION',        COUNT(*) FROM olympics.POBLACION;
GO

PRINT N'01_carga_inicial_catalogos.sql finalizado en $(DB).';
GO
