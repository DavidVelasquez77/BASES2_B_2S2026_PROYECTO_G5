/* Bloque 6 — carga explícita staging -> modelo final. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF EXISTS
(
    SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA UNION ALL SELECT 1 FROM olympics.POBLACION
    UNION ALL SELECT 1 FROM olympics.NOC UNION ALL SELECT 1 FROM olympics.ATLETA
    UNION ALL SELECT 1 FROM olympics.SEDE UNION ALL SELECT 1 FROM olympics.EDICION_OLIMPICA
    UNION ALL SELECT 1 FROM olympics.DEPORTE UNION ALL SELECT 1 FROM olympics.DISCIPLINA
    UNION ALL SELECT 1 FROM olympics.EVENTO UNION ALL SELECT 1 FROM olympics.PARTICIPACION
)
    THROW 51010, N'Abortado: al menos una tabla olympics ya contiene datos. No se ejecuta DELETE, TRUNCATE ni DROP automáticamente.', 1;
GO

IF OBJECT_ID(N'stg.PARTICIPACION',N'U') IS NULL OR NOT EXISTS (SELECT 1 FROM stg.PARTICIPACION)
    THROW 51011, N'Abortado: staging no está cargado. Ejecutar 03_create_staging.sql, 04_bulk_load_staging.sql y 05_validate_staging.sql.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO olympics.ENTIDAD_GEOGRAFICA (id_entidad,nombre,codigo_pais)
    SELECT TRY_CONVERT(INT,TRIM(id_entidad)),CONVERT(NVARCHAR(150),TRIM(nombre)),CONVERT(NVARCHAR(20),NULLIF(TRIM(codigo_pais),N''))
    FROM stg.ENTIDAD_GEOGRAFICA;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.DEPORTE (id_deporte,nombre)
    SELECT TRY_CONVERT(INT,TRIM(id_deporte)),CONVERT(NVARCHAR(150),TRIM(nombre)) FROM stg.DEPORTE;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.NOC (id_noc,codigo_noc,nombre_noc,id_entidad,notas)
    SELECT TRY_CONVERT(INT,TRIM(id_noc)),CONVERT(NVARCHAR(3),NULLIF(TRIM(codigo_noc),N'')),CONVERT(NVARCHAR(150),NULLIF(TRIM(nombre_noc),N'')),TRY_CONVERT(INT,NULLIF(TRIM(id_entidad),N'')),CONVERT(NVARCHAR(500),NULLIF(TRIM(notas),N''))
    FROM stg.NOC;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.ATLETA
    (id_atleta,nombre,nombre_completo,nombre_usado,nombre_original,otros_nombres,apodos,orden_nombre,sexo,fecha_nacimiento,ciudad_nacimiento,region_nacimiento,id_pais_nacimiento,id_pais_nacionalidad,fecha_fallecimiento,ciudad_fallecimiento,region_fallecimiento,id_pais_fallecimiento,altura_cm,peso_kg,roles,afiliaciones,titulos,latitud,longitud)
    SELECT TRY_CONVERT(BIGINT,TRIM(id_atleta)),CONVERT(NVARCHAR(250),TRIM(nombre)),CONVERT(NVARCHAR(300),NULLIF(TRIM(nombre_completo),N'')),CONVERT(NVARCHAR(300),NULLIF(TRIM(nombre_usado),N'')),CONVERT(NVARCHAR(300),NULLIF(TRIM(nombre_original),N'')),CONVERT(NVARCHAR(500),NULLIF(TRIM(otros_nombres),N'')),CONVERT(NVARCHAR(500),NULLIF(TRIM(apodos),N'')),CONVERT(NVARCHAR(50),NULLIF(TRIM(orden_nombre),N'')),CONVERT(NVARCHAR(20),NULLIF(TRIM(sexo),N'')),TRY_CONVERT(DATE,NULLIF(TRIM(fecha_nacimiento),N'')),CONVERT(NVARCHAR(150),NULLIF(TRIM(ciudad_nacimiento),N'')),CONVERT(NVARCHAR(150),NULLIF(TRIM(region_nacimiento),N'')),TRY_CONVERT(INT,NULLIF(TRIM(id_pais_nacimiento),N'')),TRY_CONVERT(INT,NULLIF(TRIM(id_pais_nacionalidad),N'')),TRY_CONVERT(DATE,NULLIF(TRIM(fecha_fallecimiento),N'')),CONVERT(NVARCHAR(150),NULLIF(TRIM(ciudad_fallecimiento),N'')),CONVERT(NVARCHAR(150),NULLIF(TRIM(region_fallecimiento),N'')),TRY_CONVERT(INT,NULLIF(TRIM(id_pais_fallecimiento),N'')),TRY_CONVERT(DECIMAL(5,2),NULLIF(TRIM(altura_cm),N'')),TRY_CONVERT(DECIMAL(5,2),NULLIF(TRIM(peso_kg),N'')),NULLIF(TRIM(roles),N''),NULLIF(TRIM(afiliaciones),N''),CONVERT(NVARCHAR(2000),NULLIF(TRIM(titulos),N'')),TRY_CONVERT(DECIMAL(19,16),NULLIF(TRIM(latitud),N'')),TRY_CONVERT(DECIMAL(19,16),NULLIF(TRIM(longitud),N''))
    FROM stg.ATLETA;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.SEDE (id_sede,nombre,id_pais)
    SELECT TRY_CONVERT(INT,TRIM(id_sede)),CONVERT(NVARCHAR(150),TRIM(nombre)),TRY_CONVERT(INT,TRIM(id_pais)) FROM stg.SEDE;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.EDICION_OLIMPICA (id_edicion,anio,temporada,id_sede)
    SELECT TRY_CONVERT(INT,TRIM(id_edicion)),TRY_CONVERT(SMALLINT,TRIM(anio)),CONVERT(NVARCHAR(20),TRIM(temporada)),TRY_CONVERT(INT,NULLIF(TRIM(id_sede),N'')) FROM stg.EDICION_OLIMPICA;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.DISCIPLINA (id_disciplina,id_deporte,nombre)
    SELECT TRY_CONVERT(INT,TRIM(id_disciplina)),TRY_CONVERT(INT,TRIM(id_deporte)),CONVERT(NVARCHAR(150),TRIM(nombre)) FROM stg.DISCIPLINA;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.EVENTO (id_evento,id_disciplina,nombre)
    SELECT TRY_CONVERT(BIGINT,TRIM(id_evento)),TRY_CONVERT(INT,TRIM(id_disciplina)),CONVERT(NVARCHAR(300),TRIM(nombre)) FROM stg.EVENTO;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.POBLACION (id_entidad,anio,poblacion)
    SELECT TRY_CONVERT(INT,TRIM(id_entidad)),TRY_CONVERT(SMALLINT,TRIM(anio)),TRY_CONVERT(BIGINT,NULLIF(TRIM(poblacion),N'')) FROM stg.POBLACION;
    COMMIT TRANSACTION;

    BEGIN TRANSACTION;
    INSERT INTO olympics.PARTICIPACION
    (id_participacion,id_atleta,id_edicion,id_evento,id_noc,id_pais_nacionalidad,equipo,nombre_competencia,edad,altura_cm_registrada,peso_kg_registrado,posicion,empatado,estado_resultado,medalla)
    SELECT TRY_CONVERT(BIGINT,TRIM(id_participacion)),TRY_CONVERT(BIGINT,TRIM(id_atleta)),TRY_CONVERT(INT,TRIM(id_edicion)),TRY_CONVERT(BIGINT,TRIM(id_evento)),TRY_CONVERT(INT,NULLIF(TRIM(id_noc),N'')),TRY_CONVERT(INT,NULLIF(TRIM(id_pais_nacionalidad),N'')),CONVERT(NVARCHAR(250),NULLIF(TRIM(equipo),N'')),CONVERT(NVARCHAR(300),NULLIF(TRIM(nombre_competencia),N'')),TRY_CONVERT(DECIMAL(5,2),NULLIF(TRIM(edad),N'')),TRY_CONVERT(DECIMAL(5,2),NULLIF(TRIM(altura_cm_registrada),N'')),TRY_CONVERT(DECIMAL(16,13),NULLIF(TRIM(peso_kg_registrado),N'')),TRY_CONVERT(INT,NULLIF(TRIM(posicion),N'')),CASE LOWER(NULLIF(TRIM(empatado),N'')) WHEN N'true' THEN CONVERT(BIT,1) WHEN N'1' THEN CONVERT(BIT,1) WHEN N'false' THEN CONVERT(BIT,0) WHEN N'0' THEN CONVERT(BIT,0) ELSE NULL END,CONVERT(NVARCHAR(30),NULLIF(TRIM(estado_resultado),N'')),CONVERT(NVARCHAR(20),NULLIF(TRIM(medalla),N''))
    FROM stg.PARTICIPACION;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

PRINT N'06_load_final.sql finalizado. Diez tablas olympics cargadas desde staging.';
GO
