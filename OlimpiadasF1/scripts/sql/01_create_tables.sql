/*
    Bloque 5 — Modelo físico SQL Server
    Crea únicamente las diez tablas finales bajo olympics.
    No carga datos. No elimina tablas existentes.

    Ejecutar previamente scripts/sql/00_create_database.sql en un entorno limpio.
    Si una tabla ya existe, se conserva y se informa; la validación se realiza con
    scripts/sql/02_validate_schema.sql.
*/

USE OlimpiadasDB;
GO

IF SCHEMA_ID(N'olympics') IS NULL
    EXEC(N'CREATE SCHEMA olympics');
GO

IF OBJECT_ID(N'olympics.ENTIDAD_GEOGRAFICA', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.ENTIDAD_GEOGRAFICA
    (
        id_entidad INT NOT NULL,
        nombre NVARCHAR(150) NOT NULL,
        codigo_pais CHAR(3) NULL,
        CONSTRAINT PK_ENTIDAD_GEOGRAFICA PRIMARY KEY (id_entidad)
    );
END;
GO

IF OBJECT_ID(N'olympics.DEPORTE', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.DEPORTE
    (
        id_deporte INT NOT NULL,
        nombre NVARCHAR(150) NOT NULL,
        CONSTRAINT PK_DEPORTE PRIMARY KEY (id_deporte),
        CONSTRAINT UQ_DEPORTE_nombre UNIQUE (nombre)
    );
END;
GO

IF OBJECT_ID(N'olympics.NOC', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.NOC
    (
        id_noc INT NOT NULL,
        codigo_noc CHAR(3) NULL,
        nombre_noc NVARCHAR(150) NULL,
        id_entidad INT NULL,
        notas NVARCHAR(500) NULL,
        CONSTRAINT PK_NOC PRIMARY KEY (id_noc),
        CONSTRAINT UQ_NOC_codigo_noc UNIQUE (codigo_noc),
        CONSTRAINT FK_NOC_ENTIDAD_GEOGRAFICA FOREIGN KEY (id_entidad)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad)
    );
END;
GO

IF OBJECT_ID(N'olympics.ATLETA', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.ATLETA
    (
        id_atleta BIGINT NOT NULL,
        nombre NVARCHAR(250) NOT NULL,
        nombre_completo NVARCHAR(300) NULL,
        nombre_usado NVARCHAR(300) NULL,
        nombre_original NVARCHAR(300) NULL,
        otros_nombres NVARCHAR(500) NULL,
        apodos NVARCHAR(500) NULL,
        orden_nombre NVARCHAR(50) NULL,
        sexo NVARCHAR(20) NULL,
        fecha_nacimiento DATE NULL,
        ciudad_nacimiento NVARCHAR(150) NULL,
        region_nacimiento NVARCHAR(150) NULL,
        id_pais_nacimiento INT NULL,
        id_pais_nacionalidad INT NULL,
        fecha_fallecimiento DATE NULL,
        ciudad_fallecimiento NVARCHAR(150) NULL,
        region_fallecimiento NVARCHAR(150) NULL,
        id_pais_fallecimiento INT NULL,
        altura_cm DECIMAL(5,2) NULL,
        peso_kg DECIMAL(5,2) NULL,
        roles NVARCHAR(MAX) NULL,
        afiliaciones NVARCHAR(MAX) NULL,
        /* Ajuste físico: el máximo real del CSV es 1,518 caracteres. */
        titulos NVARCHAR(2000) NULL,
        latitud DECIMAL(19,16) NULL,
        longitud DECIMAL(19,16) NULL,
        CONSTRAINT PK_ATLETA PRIMARY KEY (id_atleta),
        CONSTRAINT FK_ATLETA_PAIS_NACIMIENTO FOREIGN KEY (id_pais_nacimiento)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad),
        CONSTRAINT FK_ATLETA_PAIS_NACIONALIDAD FOREIGN KEY (id_pais_nacionalidad)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad),
        CONSTRAINT FK_ATLETA_PAIS_FALLECIMIENTO FOREIGN KEY (id_pais_fallecimiento)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad)
    );
END;
GO

IF OBJECT_ID(N'olympics.SEDE', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.SEDE
    (
        id_sede INT NOT NULL,
        nombre NVARCHAR(150) NOT NULL,
        id_pais INT NOT NULL,
        CONSTRAINT PK_SEDE PRIMARY KEY (id_sede),
        CONSTRAINT UQ_SEDE_nombre_id_pais UNIQUE (nombre, id_pais),
        CONSTRAINT FK_SEDE_ENTIDAD_GEOGRAFICA FOREIGN KEY (id_pais)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad)
    );
END;
GO

IF OBJECT_ID(N'olympics.EDICION_OLIMPICA', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.EDICION_OLIMPICA
    (
        id_edicion INT NOT NULL,
        anio SMALLINT NOT NULL,
        /* Ajuste físico: el máximo real de temporada es 18 caracteres. */
        temporada NVARCHAR(20) NOT NULL,
        id_sede INT NULL,
        CONSTRAINT PK_EDICION_OLIMPICA PRIMARY KEY (id_edicion),
        CONSTRAINT UQ_EDICION_OLIMPICA_anio_temporada UNIQUE (anio, temporada),
        CONSTRAINT CK_EDICION_OLIMPICA_temporada CHECK
            (temporada IN (N'Summer', N'Winter', N'Intercalated Games', N'Summer Youth', N'Winter Youth')),
        CONSTRAINT FK_EDICION_OLIMPICA_SEDE FOREIGN KEY (id_sede)
            REFERENCES olympics.SEDE (id_sede)
    );
END;
GO

IF OBJECT_ID(N'olympics.DISCIPLINA', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.DISCIPLINA
    (
        id_disciplina INT NOT NULL,
        id_deporte INT NOT NULL,
        nombre NVARCHAR(150) NOT NULL,
        CONSTRAINT PK_DISCIPLINA PRIMARY KEY (id_disciplina),
        CONSTRAINT UQ_DISCIPLINA_deporte_nombre UNIQUE (id_deporte, nombre),
        CONSTRAINT FK_DISCIPLINA_DEPORTE FOREIGN KEY (id_deporte)
            REFERENCES olympics.DEPORTE (id_deporte)
    );
END;
GO

IF OBJECT_ID(N'olympics.EVENTO', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.EVENTO
    (
        id_evento BIGINT NOT NULL,
        id_disciplina INT NOT NULL,
        nombre NVARCHAR(300) NOT NULL,
        CONSTRAINT PK_EVENTO PRIMARY KEY (id_evento),
        CONSTRAINT UQ_EVENTO_disciplina_nombre UNIQUE (id_disciplina, nombre),
        CONSTRAINT FK_EVENTO_DISCIPLINA FOREIGN KEY (id_disciplina)
            REFERENCES olympics.DISCIPLINA (id_disciplina)
    );
END;
GO

IF OBJECT_ID(N'olympics.POBLACION', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.POBLACION
    (
        id_entidad INT NOT NULL,
        anio SMALLINT NOT NULL,
        poblacion BIGINT NULL,
        CONSTRAINT PK_POBLACION PRIMARY KEY (id_entidad, anio),
        CONSTRAINT FK_POBLACION_ENTIDAD_GEOGRAFICA FOREIGN KEY (id_entidad)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad)
    );
END;
GO

IF OBJECT_ID(N'olympics.PARTICIPACION', N'U') IS NULL
BEGIN
    CREATE TABLE olympics.PARTICIPACION
    (
        id_participacion BIGINT NOT NULL,
        id_atleta BIGINT NOT NULL,
        id_edicion INT NOT NULL,
        id_evento BIGINT NOT NULL,
        id_noc INT NULL,
        id_pais_nacionalidad INT NULL,
        equipo NVARCHAR(250) NULL,
        nombre_competencia NVARCHAR(300) NULL,
        edad DECIMAL(5,2) NULL,
        altura_cm_registrada DECIMAL(5,2) NULL,
        peso_kg_registrado DECIMAL(16,13) NULL,
        posicion INT NULL,
        empatado BIT NULL,
        estado_resultado NVARCHAR(30) NULL,
        medalla NVARCHAR(20) NULL,
        CONSTRAINT PK_PARTICIPACION PRIMARY KEY (id_participacion),
        CONSTRAINT CK_PARTICIPACION_medalla CHECK
            (medalla IN (N'Gold', N'Silver', N'Bronze') OR medalla IS NULL),
        CONSTRAINT CK_PARTICIPACION_posicion CHECK
            (posicion > 0 OR posicion IS NULL),
        CONSTRAINT FK_PARTICIPACION_ATLETA FOREIGN KEY (id_atleta)
            REFERENCES olympics.ATLETA (id_atleta),
        CONSTRAINT FK_PARTICIPACION_EDICION FOREIGN KEY (id_edicion)
            REFERENCES olympics.EDICION_OLIMPICA (id_edicion),
        CONSTRAINT FK_PARTICIPACION_EVENTO FOREIGN KEY (id_evento)
            REFERENCES olympics.EVENTO (id_evento),
        CONSTRAINT FK_PARTICIPACION_NOC FOREIGN KEY (id_noc)
            REFERENCES olympics.NOC (id_noc),
        CONSTRAINT FK_PARTICIPACION_PAIS_NACIONALIDAD FOREIGN KEY (id_pais_nacionalidad)
            REFERENCES olympics.ENTIDAD_GEOGRAFICA (id_entidad)
    );
END;
GO

PRINT N'01_create_tables.sql finalizado. No se cargaron datos.';
GO
