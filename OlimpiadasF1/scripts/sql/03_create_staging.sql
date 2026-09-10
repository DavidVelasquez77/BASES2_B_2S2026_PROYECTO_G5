/* Bloque 6 — staging exclusivo para los diez CSV finales. */
USE OlimpiadasDB;
GO

IF SCHEMA_ID(N'stg') IS NULL
    EXEC(N'CREATE SCHEMA stg');
GO

/* Helpers de conversión segura. Admiten representaciones textuales
   integrales como "280.0" solo cuando no existe parte fraccionaria. */
CREATE OR ALTER FUNCTION stg.CleanValue(@value NVARCHAR(MAX))
RETURNS NVARCHAR(MAX)
AS
BEGIN
    RETURN NULLIF(REPLACE(TRIM(@value), NCHAR(13), N''), N'');
END;
GO

CREATE OR ALTER FUNCTION stg.TryIntValue(@value NVARCHAR(MAX))
RETURNS INT
AS
BEGIN
    DECLARE @n DECIMAL(38,10) = TRY_CONVERT(DECIMAL(38,10), stg.CleanValue(@value));
    RETURN CASE WHEN @n IS NULL OR @n <> FLOOR(@n) THEN NULL ELSE TRY_CONVERT(INT, @n) END;
END;
GO

CREATE OR ALTER FUNCTION stg.TryBigIntValue(@value NVARCHAR(MAX))
RETURNS BIGINT
AS
BEGIN
    DECLARE @n DECIMAL(38,10) = TRY_CONVERT(DECIMAL(38,10), stg.CleanValue(@value));
    RETURN CASE WHEN @n IS NULL OR @n <> FLOOR(@n) THEN NULL ELSE TRY_CONVERT(BIGINT, @n) END;
END;
GO

CREATE OR ALTER FUNCTION stg.TrySmallIntValue(@value NVARCHAR(MAX))
RETURNS SMALLINT
AS
BEGIN
    DECLARE @n DECIMAL(38,10) = TRY_CONVERT(DECIMAL(38,10), stg.CleanValue(@value));
    RETURN CASE WHEN @n IS NULL OR @n <> FLOOR(@n) THEN NULL ELSE TRY_CONVERT(SMALLINT, @n) END;
END;
GO

IF EXISTS (SELECT 1 FROM sys.tables WHERE schema_id = SCHEMA_ID(N'stg'))
    THROW 51000, N'Abortado: ya existen tablas en stg. Revisar y limpiar staging manualmente antes de continuar.', 1;
GO

CREATE TABLE stg.ENTIDAD_GEOGRAFICA
(
    id_entidad NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL,
    codigo_pais NVARCHAR(MAX) NULL
);
CREATE TABLE stg.POBLACION
(
    id_entidad NVARCHAR(MAX) NULL,
    anio NVARCHAR(MAX) NULL,
    poblacion NVARCHAR(MAX) NULL
);
CREATE TABLE stg.NOC
(
    id_noc NVARCHAR(MAX) NULL,
    codigo_noc NVARCHAR(MAX) NULL,
    nombre_noc NVARCHAR(MAX) NULL,
    id_entidad NVARCHAR(MAX) NULL,
    notas NVARCHAR(MAX) NULL
);
CREATE TABLE stg.ATLETA
(
    id_atleta NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL,
    nombre_completo NVARCHAR(MAX) NULL,
    nombre_usado NVARCHAR(MAX) NULL,
    nombre_original NVARCHAR(MAX) NULL,
    otros_nombres NVARCHAR(MAX) NULL,
    apodos NVARCHAR(MAX) NULL,
    orden_nombre NVARCHAR(MAX) NULL,
    sexo NVARCHAR(MAX) NULL,
    fecha_nacimiento NVARCHAR(MAX) NULL,
    ciudad_nacimiento NVARCHAR(MAX) NULL,
    region_nacimiento NVARCHAR(MAX) NULL,
    id_pais_nacimiento NVARCHAR(MAX) NULL,
    id_pais_nacionalidad NVARCHAR(MAX) NULL,
    fecha_fallecimiento NVARCHAR(MAX) NULL,
    ciudad_fallecimiento NVARCHAR(MAX) NULL,
    region_fallecimiento NVARCHAR(MAX) NULL,
    id_pais_fallecimiento NVARCHAR(MAX) NULL,
    altura_cm NVARCHAR(MAX) NULL,
    peso_kg NVARCHAR(MAX) NULL,
    roles NVARCHAR(MAX) NULL,
    afiliaciones NVARCHAR(MAX) NULL,
    titulos NVARCHAR(MAX) NULL,
    latitud NVARCHAR(MAX) NULL,
    longitud NVARCHAR(MAX) NULL
);
CREATE TABLE stg.SEDE
(
    id_sede NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL,
    id_pais NVARCHAR(MAX) NULL
);
CREATE TABLE stg.EDICION_OLIMPICA
(
    id_edicion NVARCHAR(MAX) NULL,
    anio NVARCHAR(MAX) NULL,
    temporada NVARCHAR(MAX) NULL,
    id_sede NVARCHAR(MAX) NULL
);
CREATE TABLE stg.DEPORTE
(
    id_deporte NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL
);
CREATE TABLE stg.DISCIPLINA
(
    id_disciplina NVARCHAR(MAX) NULL,
    id_deporte NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL
);
CREATE TABLE stg.EVENTO
(
    id_evento NVARCHAR(MAX) NULL,
    id_disciplina NVARCHAR(MAX) NULL,
    nombre NVARCHAR(MAX) NULL
);
CREATE TABLE stg.PARTICIPACION
(
    id_participacion NVARCHAR(MAX) NULL,
    id_atleta NVARCHAR(MAX) NULL,
    id_edicion NVARCHAR(MAX) NULL,
    id_evento NVARCHAR(MAX) NULL,
    id_noc NVARCHAR(MAX) NULL,
    id_pais_nacionalidad NVARCHAR(MAX) NULL,
    equipo NVARCHAR(MAX) NULL,
    nombre_competencia NVARCHAR(MAX) NULL,
    edad NVARCHAR(MAX) NULL,
    altura_cm_registrada NVARCHAR(MAX) NULL,
    peso_kg_registrado NVARCHAR(MAX) NULL,
    posicion NVARCHAR(MAX) NULL,
    empatado NVARCHAR(MAX) NULL,
    estado_resultado NVARCHAR(MAX) NULL,
    medalla NVARCHAR(MAX) NULL
);
GO

PRINT N'03_create_staging.sql finalizado. Diez tablas staging creadas; no se cargaron datos.';
GO
