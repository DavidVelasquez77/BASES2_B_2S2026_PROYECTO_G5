/* Bloque 7 — auditoría global de solo lectura. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
GO

DECLARE @v TABLE
(
    validacion NVARCHAR(160) NOT NULL,
    esperado BIGINT NOT NULL,
    actual BIGINT NOT NULL,
    estado NVARCHAR(10) NOT NULL,
    detalle NVARCHAR(300) NOT NULL
);

DECLARE @tables TABLE (nombre SYSNAME PRIMARY KEY);
INSERT INTO @tables VALUES
(N'ENTIDAD_GEOGRAFICA'),(N'POBLACION'),(N'NOC'),(N'ATLETA'),(N'SEDE'),
(N'EDICION_OLIMPICA'),(N'DEPORTE'),(N'DISCIPLINA'),(N'EVENTO'),(N'PARTICIPACION');

INSERT INTO @v
SELECT N'tablas_finales',10,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=10 THEN N'PASS' ELSE N'FAIL' END,N'Tablas esperadas en olympics'
FROM sys.tables t JOIN @tables x ON x.nombre=t.name WHERE t.schema_id=SCHEMA_ID(N'olympics');

INSERT INTO @v
SELECT N'tablas_logicas_extra',0,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=0 THEN N'PASS' ELSE N'FAIL' END,N'Tablas fuera del modelo lógico final'
FROM sys.tables t WHERE t.schema_id=SCHEMA_ID(N'olympics') AND NOT EXISTS (SELECT 1 FROM @tables x WHERE x.nombre=t.name);

INSERT INTO @v
SELECT N'columnas',66,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=66 THEN N'PASS' ELSE N'FAIL' END,N'Columnas de las diez tablas finales'
FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id JOIN @tables x ON x.nombre=t.name
WHERE t.schema_id=SCHEMA_ID(N'olympics');

DECLARE @expected TABLE (nombre SYSNAME PRIMARY KEY, filas BIGINT NOT NULL);
INSERT INTO @expected VALUES
(N'ENTIDAD_GEOGRAFICA',282),(N'POBLACION',17024),(N'NOC',236),(N'ATLETA',336418),
(N'SEDE',42),(N'EDICION_OLIMPICA',61),(N'DEPORTE',65),(N'DISCIPLINA',117),
(N'EVENTO',2986),(N'PARTICIPACION',713678);

DECLARE @counts TABLE (nombre SYSNAME PRIMARY KEY, filas BIGINT NOT NULL);
INSERT INTO @counts VALUES
(N'ENTIDAD_GEOGRAFICA',(SELECT COUNT_BIG(*) FROM olympics.ENTIDAD_GEOGRAFICA)),
(N'POBLACION',(SELECT COUNT_BIG(*) FROM olympics.POBLACION)),
(N'NOC',(SELECT COUNT_BIG(*) FROM olympics.NOC)),
(N'ATLETA',(SELECT COUNT_BIG(*) FROM olympics.ATLETA)),
(N'SEDE',(SELECT COUNT_BIG(*) FROM olympics.SEDE)),
(N'EDICION_OLIMPICA',(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA)),
(N'DEPORTE',(SELECT COUNT_BIG(*) FROM olympics.DEPORTE)),
(N'DISCIPLINA',(SELECT COUNT_BIG(*) FROM olympics.DISCIPLINA)),
(N'EVENTO',(SELECT COUNT_BIG(*) FROM olympics.EVENTO)),
(N'PARTICIPACION',(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION));

INSERT INTO @v
SELECT N'conteo.'+e.nombre,e.filas,c.filas,CASE WHEN e.filas=c.filas THEN N'PASS' ELSE N'FAIL' END,N'Conteo final exacto'
FROM @expected e JOIN @counts c ON c.nombre=e.nombre;

INSERT INTO @v
SELECT N'pk',10,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=10 THEN N'PASS' ELSE N'FAIL' END,N'Claves primarias activas'
FROM sys.key_constraints k WHERE k.parent_object_id IN (SELECT t.object_id FROM sys.tables t WHERE t.schema_id=SCHEMA_ID(N'olympics')) AND k.type=N'PK';
INSERT INTO @v
SELECT N'unique',6,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=6 THEN N'PASS' ELSE N'FAIL' END,N'Claves UNIQUE activas'
FROM sys.key_constraints k WHERE k.parent_object_id IN (SELECT t.object_id FROM sys.tables t WHERE t.schema_id=SCHEMA_ID(N'olympics')) AND k.type=N'UQ';
INSERT INTO @v
SELECT N'fk',14,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=14 THEN N'PASS' ELSE N'FAIL' END,N'Claves foráneas activas'
FROM sys.foreign_keys f WHERE f.parent_object_id IN (SELECT t.object_id FROM sys.tables t WHERE t.schema_id=SCHEMA_ID(N'olympics'));
INSERT INTO @v
SELECT N'check',3,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=3 THEN N'PASS' ELSE N'FAIL' END,N'Restricciones CHECK activas'
FROM sys.check_constraints c WHERE c.parent_object_id IN (SELECT t.object_id FROM sys.tables t WHERE t.schema_id=SCHEMA_ID(N'olympics'));
INSERT INTO @v
SELECT N'indices_adicionales',8,COUNT_BIG(*),CASE WHEN COUNT_BIG(*)=8 THEN N'PASS' ELSE N'FAIL' END,N'Índices IX_ adicionales'
FROM sys.indexes i WHERE OBJECT_SCHEMA_NAME(i.object_id)=N'olympics' AND i.name IN
(N'IX_PARTICIPACION_id_atleta',N'IX_PARTICIPACION_id_edicion',N'IX_PARTICIPACION_id_evento',N'IX_PARTICIPACION_id_noc',N'IX_PARTICIPACION_id_pais_nacionalidad',N'IX_ATLETA_id_pais_nacionalidad',N'IX_NOC_id_entidad',N'IX_SEDE_id_pais');

DECLARE @pk_duplicates BIGINT=0;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_entidad,COUNT_BIG(*) c FROM olympics.ENTIDAD_GEOGRAFICA GROUP BY id_entidad HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_entidad,anio,COUNT_BIG(*) c FROM olympics.POBLACION GROUP BY id_entidad,anio HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_noc,COUNT_BIG(*) c FROM olympics.NOC GROUP BY id_noc HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_atleta,COUNT_BIG(*) c FROM olympics.ATLETA GROUP BY id_atleta HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_sede,COUNT_BIG(*) c FROM olympics.SEDE GROUP BY id_sede HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_edicion,COUNT_BIG(*) c FROM olympics.EDICION_OLIMPICA GROUP BY id_edicion HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_deporte,COUNT_BIG(*) c FROM olympics.DEPORTE GROUP BY id_deporte HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_disciplina,COUNT_BIG(*) c FROM olympics.DISCIPLINA GROUP BY id_disciplina HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_evento,COUNT_BIG(*) c FROM olympics.EVENTO GROUP BY id_evento HAVING COUNT_BIG(*)>1)d;
SELECT @pk_duplicates=@pk_duplicates+COALESCE(SUM(c-1),0) FROM (SELECT id_participacion,COUNT_BIG(*) c FROM olympics.PARTICIPACION GROUP BY id_participacion HAVING COUNT_BIG(*)>1)d;
INSERT INTO @v VALUES (N'pk_duplicadas',0,@pk_duplicates,CASE WHEN @pk_duplicates=0 THEN N'PASS' ELSE N'FAIL' END,N'Duplicados efectivos de claves primarias');

DECLARE @fk_orphans BIGINT=0;
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.POBLACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_entidad);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.NOC c WHERE c.id_entidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_entidad);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.ATLETA c WHERE (c.id_pais_nacimiento IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacimiento)) OR (c.id_pais_nacionalidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacionalidad)) OR (c.id_pais_fallecimiento IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_fallecimiento));
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.SEDE c WHERE NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA c WHERE c.id_sede IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.SEDE p WHERE p.id_sede=c.id_sede);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.DISCIPLINA c WHERE NOT EXISTS (SELECT 1 FROM olympics.DEPORTE p WHERE p.id_deporte=c.id_deporte);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.EVENTO c WHERE NOT EXISTS (SELECT 1 FROM olympics.DISCIPLINA p WHERE p.id_disciplina=c.id_disciplina);
SELECT @fk_orphans=@fk_orphans+COUNT_BIG(*) FROM olympics.PARTICIPACION c WHERE NOT EXISTS (SELECT 1 FROM olympics.ATLETA p WHERE p.id_atleta=c.id_atleta) OR NOT EXISTS (SELECT 1 FROM olympics.EDICION_OLIMPICA p WHERE p.id_edicion=c.id_edicion) OR NOT EXISTS (SELECT 1 FROM olympics.EVENTO p WHERE p.id_evento=c.id_evento) OR (c.id_noc IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.NOC p WHERE p.id_noc=c.id_noc)) OR (c.id_pais_nacionalidad IS NOT NULL AND NOT EXISTS (SELECT 1 FROM olympics.ENTIDAD_GEOGRAFICA p WHERE p.id_entidad=c.id_pais_nacionalidad));
INSERT INTO @v VALUES (N'fk_huerfanas',0,@fk_orphans,CASE WHEN @fk_orphans=0 THEN N'PASS' ELSE N'FAIL' END,N'Filas sin padre en las 14 FK');

INSERT INTO @v VALUES
(N'valores_invalidos.temporada',0,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth')),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA WHERE temporada NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth'))=0 THEN N'PASS' ELSE N'FAIL' END,N'Dominio final de temporada'),
(N'valores_invalidos.medalla',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL AND medalla NOT IN (N'Gold',N'Silver',N'Bronze')),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE medalla IS NOT NULL AND medalla NOT IN (N'Gold',N'Silver',N'Bronze'))=0 THEN N'PASS' ELSE N'FAIL' END,N'Dominio final de medalla'),
(N'valores_invalidos.posicion',0,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE posicion IS NOT NULL AND posicion<=0),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION WHERE posicion IS NOT NULL AND posicion<=0)=0 THEN N'PASS' ELSE N'FAIL' END,N'Posición positiva'),
(N'ediciones',61,(SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.EDICION_OLIMPICA)=61 THEN N'PASS' ELSE N'FAIL' END,N'Ediciones finales'),
(N'atletas',336418,(SELECT COUNT_BIG(*) FROM olympics.ATLETA),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.ATLETA)=336418 THEN N'PASS' ELSE N'FAIL' END,N'Atletas finales'),
(N'participaciones',713678,(SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION),CASE WHEN (SELECT COUNT_BIG(*) FROM olympics.PARTICIPACION)=713678 THEN N'PASS' ELSE N'FAIL' END,N'Participaciones finales');

SELECT validacion,esperado,actual,estado,detalle FROM @v ORDER BY validacion;
IF EXISTS (SELECT 1 FROM @v WHERE estado=N'FAIL')
BEGIN
    PRINT N'RESULTADO_GLOBAL = FAIL';
    THROW 51070,N'10_final_validation.sql FAIL.',1;
END;
PRINT N'RESULTADO_GLOBAL = PASS';
GO
