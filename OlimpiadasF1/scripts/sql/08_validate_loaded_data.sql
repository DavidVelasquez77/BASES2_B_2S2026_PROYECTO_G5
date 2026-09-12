/* Bloque 6 — validación posterior a la carga y a la creación de índices. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

DECLARE @v TABLE
(
    validacion NVARCHAR(180) NOT NULL,
    esperado BIGINT NULL,
    actual BIGINT NULL,
    estado NVARCHAR(10) NOT NULL,
    detalle NVARCHAR(500) NOT NULL
);

INSERT INTO @v VALUES
(N'conteo.ENTIDAD_GEOGRAFICA',282,(SELECT COUNT_BIG(*) FROM olympics.ENTIDAD_GEOGRAFICA),N'PENDIENTE',N'Conteo final'),
(N'conteo.POBLACION',17024,(SELECT COUNT_BIG(*) FROM olympics.POBLACION),N'PENDIENTE',N'Conteo final'),
(N'conteo.NOC',236,(SELECT COUNT_BIG(*) FROM olympics.NOC),N'PENDIENTE',N'Conteo final'),
(N'conteo.ATLETA',336418,(SELECT COUNT_BIG(*) FROM olympics.ATLETA),N'PENDIENTE',N'Conteo final'),
(N'conteo.SEDE',42,(SELECT COUNT_BIG(*) FROM olympics.SEDE),N'PENDIENTE',N'Conteo final'),
(N'conteo.EDICION_OLIMPICA',61,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA),N'PENDIENTE',N'Conteo final'),
(N'conteo.DEPORTE',65,(SELECT COUNT_BIG(*) FROM olympics.DEPORTE),N'PENDIENTE',N'Conteo final'),
(N'conteo.DISCIPLINA',117,(SELECT COUNT_BIG(*) FROM olympics.DISCIPLINA),N'PENDIENTE',N'Conteo final'),
(N'conteo.EVENTO',2986,(SELECT COUNT_BIG(*) FROM olympics.EVENTO),N'PENDIENTE',N'Conteo final'),
(N'conteo.PARTICIPACION',713678,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION),N'PENDIENTE',N'Conteo final');

UPDATE @v SET estado=CASE WHEN esperado=actual THEN N'PASS' ELSE N'FAIL' END;

INSERT INTO @v VALUES
(N'pk.ENTIDAD_GEOGRAFICA',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_entidad,COUNT_BIG(*) c FROM olympics.ENTIDAD_GEOGRAFICA GROUP BY id_entidad HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.POBLACION',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_entidad,anio,COUNT_BIG(*) c FROM olympics.POBLACION GROUP BY id_entidad,anio HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.NOC',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_noc,COUNT_BIG(*) c FROM olympics.NOC GROUP BY id_noc HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.ATLETA',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_atleta,COUNT_BIG(*) c FROM olympics.ATLETA GROUP BY id_atleta HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.SEDE',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_sede,COUNT_BIG(*) c FROM olympics.SEDE GROUP BY id_sede HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.EDICION_OLIMPICA',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_edicion,COUNT_BIG(*) c FROM olympics.EDICION_OLIMPICA GROUP BY id_edicion HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.DEPORTE',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_deporte,COUNT_BIG(*) c FROM olympics.DEPORTE GROUP BY id_deporte HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.DISCIPLINA',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_disciplina,COUNT_BIG(*) c FROM olympics.DISCIPLINA GROUP BY id_disciplina HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.EVENTO',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_evento,COUNT_BIG(*) c FROM olympics.EVENTO GROUP BY id_evento HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK'),
(N'pk.PARTICIPACION',0,(SELECT COALESCE(SUM(c-1),0) FROM (SELECT id_participacion,COUNT_BIG(*) c FROM olympics.PARTICIPACION GROUP BY id_participacion HAVING COUNT_BIG(*)>1)d),N'PENDIENTE',N'Duplicados de PK');

UPDATE @v SET estado=CASE WHEN esperado=actual THEN N'PASS' ELSE N'FAIL' END WHERE validacion LIKE N'pk.%';

INSERT INTO @v VALUES
(N'fk.POBLACION_ENTIDAD',0,(SELECT COUNT_BIG(*) FROM olympics.POBLACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_entidad)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.NOC_ENTIDAD',0,(SELECT COUNT_BIG(*) FROM olympics.NOC c WHERE c.id_entidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_entidad)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.ATLETA_PAIS_NACIMIENTO',0,(SELECT COUNT_BIG(*) FROM olympics.ATLETA c WHERE c.id_pais_nacimiento IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacimiento)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.ATLETA_PAIS_NACIONALIDAD',0,(SELECT COUNT_BIG(*) FROM olympics.ATLETA c WHERE c.id_pais_nacionalidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacionalidad)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.ATLETA_PAIS_FALLECIMIENTO',0,(SELECT COUNT_BIG(*) FROM olympics.ATLETA c WHERE c.id_pais_fallecimiento IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_fallecimiento)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.SEDE_PAIS',0,(SELECT COUNT_BIG(*) FROM olympics.SEDE c WHERE NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.EDICION_SEDE',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA c WHERE c.id_sede IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.SEDE p WHERE p.id_sede=c.id_sede)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.DISCIPLINA_DEPORTE',0,(SELECT COUNT_BIG(*) FROM olympics.DISCIPLINA c WHERE NOT EXISTS (SELECT 1 FROM olympics.DEPORTE p WHERE p.id_deporte=c.id_deporte)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.EVENTO_DISCIPLINA',0,(SELECT COUNT_BIG(*) FROM olympics.EVENTO c WHERE NOT EXISTS (SELECT 1 FROM olympics.DISCIPLINA p WHERE p.id_disciplina=c.id_disciplina)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.PARTICIPACION_ATLETA',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.ATLETA p WHERE p.id_atleta=c.id_atleta)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.PARTICIPACION_EDICION',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.EDICION_OLIMPICA p WHERE p.id_edicion=c.id_edicion)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.PARTICIPACION_EVENTO',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.EVENTO p WHERE p.id_evento=c.id_evento)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.PARTICIPACION_NOC',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE c.id_noc IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.NOC p WHERE p.id_noc=c.id_noc)),N'PENDIENTE',N'Filas huérfanas'),
(N'fk.PARTICIPACION_PAIS_NACIONALIDAD',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE c.id_pais_nacionalidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacionalidad)),N'PENDIENTE',N'Filas huérfanas');

UPDATE @v SET estado=CASE WHEN esperado=actual THEN N'PASS' ELSE N'FAIL' END WHERE validacion LIKE N'fk.%';

INSERT INTO @v VALUES
(N'check.PARTICIPACION.medalla',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL AND medalla NOT IN (N'Gold',N'Silver',N'Bronze')),N'PENDIENTE',N'Dominio de medalla'),
(N'check.EDICION_OLIMPICA.temporada',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth')),N'PENDIENTE',N'Dominio final de temporada'),
(N'check.PARTICIPACION.posicion',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE posicion IS NOT NULL AND posicion<=0),N'PENDIENTE',N'Posición positiva'),
(N'unicode.ATLETA.nombre',1,(SELECT COUNT_BIG(*) FROM olympics.ATLETA WHERE nombre COLLATE Latin1_General_100_BIN2 LIKE N'%[^ -~]%'),N'PENDIENTE',N'El resultado debe conservar nombres no ASCII'),
(N'constraints.PK',10,(SELECT COUNT_BIG(*) FROM sys.key_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')) AND type=N'PK'),N'PENDIENTE',N'PK activas'),
(N'constraints.UNIQUE',6,(SELECT COUNT_BIG(*) FROM sys.key_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics')) AND type=N'UQ'),N'PENDIENTE',N'UNIQUE activas'),
(N'constraints.FK',14,(SELECT COUNT_BIG(*) FROM sys.foreign_keys WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics'))),N'PENDIENTE',N'FK activas'),
(N'constraints.CHECK',3,(SELECT COUNT_BIG(*) FROM sys.check_constraints WHERE parent_object_id IN (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'olympics'))),N'PENDIENTE',N'CHECK activas'),
(N'indexes.additional',8,(SELECT COUNT_BIG(*) FROM sys.indexes WHERE OBJECT_SCHEMA_NAME(object_id)=N'olympics' AND name IN (N'IX_PARTICIPACION_id_atleta',N'IX_PARTICIPACION_id_edicion',N'IX_PARTICIPACION_id_evento',N'IX_PARTICIPACION_id_noc',N'IX_PARTICIPACION_id_pais_nacionalidad',N'IX_ATLETA_id_pais_nacionalidad',N'IX_NOC_id_entidad',N'IX_SEDE_id_pais')),N'PENDIENTE',N'Índices adicionales justificados');

INSERT INTO @v VALUES
(N'precision.ATLETA.altura_cm',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE (NULLIF(TRIM(s.altura_cm),N'') IS NULL AND f.altura_cm IS NOT NULL) OR (NULLIF(TRIM(s.altura_cm),N'') IS NOT NULL AND f.altura_cm IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.ATLETA.peso_kg',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE (NULLIF(TRIM(s.peso_kg),N'') IS NULL AND f.peso_kg IS NOT NULL) OR (NULLIF(TRIM(s.peso_kg),N'') IS NOT NULL AND f.peso_kg IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.ATLETA.latitud',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE (NULLIF(TRIM(s.latitud),N'') IS NULL AND f.latitud IS NOT NULL) OR (NULLIF(TRIM(s.latitud),N'') IS NOT NULL AND f.latitud IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.latitud),N''))<>CONVERT(DECIMAL(38,20),f.latitud)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.ATLETA.longitud',0,(SELECT COUNT_BIG(*) FROM stg.ATLETA s JOIN olympics.ATLETA f ON f.id_atleta=TRY_CONVERT(BIGINT,s.id_atleta) WHERE (NULLIF(TRIM(s.longitud),N'') IS NULL AND f.longitud IS NOT NULL) OR (NULLIF(TRIM(s.longitud),N'') IS NOT NULL AND f.longitud IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.longitud),N''))<>CONVERT(DECIMAL(38,20),f.longitud)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.PARTICIPACION.edad',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE (NULLIF(TRIM(s.edad),N'') IS NULL AND f.edad IS NOT NULL) OR (NULLIF(TRIM(s.edad),N'') IS NOT NULL AND f.edad IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.edad),N''))<>CONVERT(DECIMAL(38,20),f.edad)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.PARTICIPACION.altura_cm_registrada',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE (NULLIF(TRIM(s.altura_cm_registrada),N'') IS NULL AND f.altura_cm_registrada IS NOT NULL) OR (NULLIF(TRIM(s.altura_cm_registrada),N'') IS NOT NULL AND f.altura_cm_registrada IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.altura_cm_registrada),N''))<>CONVERT(DECIMAL(38,20),f.altura_cm_registrada)),N'PENDIENTE',N'Comparación staging/final sin redondeo'),
(N'precision.PARTICIPACION.peso_kg_registrado',0,(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION s JOIN olympics.PARTICIPACION f ON f.id_participacion=TRY_CONVERT(BIGINT,s.id_participacion) WHERE (NULLIF(TRIM(s.peso_kg_registrado),N'') IS NULL AND f.peso_kg_registrado IS NOT NULL) OR (NULLIF(TRIM(s.peso_kg_registrado),N'') IS NOT NULL AND f.peso_kg_registrado IS NULL) OR TRY_CONVERT(DECIMAL(38,20),NULLIF(TRIM(s.peso_kg_registrado),N''))<>CONVERT(DECIMAL(38,20),f.peso_kg_registrado)),N'PENDIENTE',N'Comparación staging/final sin redondeo');

UPDATE @v SET estado=CASE WHEN esperado=actual OR (validacion=N'unicode.ATLETA.nombre' AND actual>=esperado) THEN N'PASS' ELSE N'FAIL' END WHERE estado=N'PENDIENTE';

SELECT validacion,esperado,actual,estado,detalle FROM @v ORDER BY validacion;

IF EXISTS (SELECT 1 FROM @v WHERE estado=N'FAIL')
    THROW 51020, N'08_validate_loaded_data.sql FAIL. Revisar antes de continuar.', 1;

PRINT N'08_validate_loaded_data.sql PASS. Conteos, PK, FK, CHECK, Unicode e índices validados.';
GO
