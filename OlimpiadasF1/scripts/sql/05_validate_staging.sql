/* Bloque 6 — prevalidación staging. Cualquier error real detiene la carga final. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'stg.PARTICIPACION', N'U') IS NULL
    THROW 51002, N'Falta staging. Ejecutar primero 03_create_staging.sql y 04_bulk_load_staging.sql.', 1;
GO

DECLARE @errors TABLE
(
    validacion NVARCHAR(160) NOT NULL,
    filas_invalidas BIGINT NOT NULL,
    detalle NVARCHAR(500) NOT NULL
);

DECLARE @expected TABLE (nombre SYSNAME PRIMARY KEY, filas BIGINT NOT NULL);
INSERT INTO @expected VALUES
 (N'ENTIDAD_GEOGRAFICA',282),(N'POBLACION',17024),(N'NOC',236),(N'ATLETA',336418),
 (N'SEDE',42),(N'EDICION_OLIMPICA',61),(N'DEPORTE',65),(N'DISCIPLINA',117),
 (N'EVENTO',2986),(N'PARTICIPACION',713678);

DECLARE @actual TABLE (nombre SYSNAME PRIMARY KEY, filas BIGINT NOT NULL);
INSERT INTO @actual VALUES
 (N'ENTIDAD_GEOGRAFICA',(SELECT COUNT_BIG(*) FROM stg.ENTIDAD_GEOGRAFICA)),
 (N'POBLACION',(SELECT COUNT_BIG(*) FROM stg.POBLACION)),
 (N'NOC',(SELECT COUNT_BIG(*) FROM stg.NOC)),
 (N'ATLETA',(SELECT COUNT_BIG(*) FROM stg.ATLETA)),
 (N'SEDE',(SELECT COUNT_BIG(*) FROM stg.SEDE)),
 (N'EDICION_OLIMPICA',(SELECT COUNT_BIG(*) FROM stg.EDICION_OLIMPICA)),
 (N'DEPORTE',(SELECT COUNT_BIG(*) FROM stg.DEPORTE)),
 (N'DISCIPLINA',(SELECT COUNT_BIG(*) FROM stg.DISCIPLINA)),
 (N'EVENTO',(SELECT COUNT_BIG(*) FROM stg.EVENTO)),
 (N'PARTICIPACION',(SELECT COUNT_BIG(*) FROM stg.PARTICIPACION));

INSERT INTO @errors
SELECT N'conteo.'+e.nombre, 1, N'Conteo staging distinto al CSV esperado'
FROM @expected e JOIN @actual a ON a.nombre=e.nombre WHERE e.filas<>a.filas;

/* Conversiones numéricas, fechas, BIT y DECIMAL. */
INSERT INTO @errors SELECT N'convert.ENTIDAD_GEOGRAFICA.id_entidad',COUNT_BIG(*),N'INT inválido' FROM stg.ENTIDAD_GEOGRAFICA WHERE NULLIF(TRIM(id_entidad),N'') IS NULL OR TRY_CONVERT(INT,id_entidad) IS NULL;
INSERT INTO @errors SELECT N'convert.POBLACION.id_entidad',COUNT_BIG(*),N'INT inválido' FROM stg.POBLACION WHERE NULLIF(TRIM(id_entidad),N'') IS NULL OR TRY_CONVERT(INT,id_entidad) IS NULL;
INSERT INTO @errors SELECT N'convert.POBLACION.anio',COUNT_BIG(*),N'SMALLINT inválido' FROM stg.POBLACION WHERE NULLIF(TRIM(anio),N'') IS NULL OR TRY_CONVERT(SMALLINT,anio) IS NULL;
INSERT INTO @errors SELECT N'convert.POBLACION.poblacion',COUNT_BIG(*),N'BIGINT inválido' FROM stg.POBLACION WHERE NULLIF(TRIM(poblacion),N'') IS NOT NULL AND TRY_CONVERT(BIGINT,poblacion) IS NULL;
INSERT INTO @errors SELECT N'convert.NOC.id_noc',COUNT_BIG(*),N'INT inválido' FROM stg.NOC WHERE NULLIF(TRIM(id_noc),N'') IS NULL OR TRY_CONVERT(INT,id_noc) IS NULL;
INSERT INTO @errors SELECT N'convert.NOC.id_entidad',COUNT_BIG(*),N'INT inválido' FROM stg.NOC WHERE NULLIF(TRIM(id_entidad),N'') IS NOT NULL AND TRY_CONVERT(INT,id_entidad) IS NULL;
INSERT INTO @errors SELECT N'convert.ATLETA.id_atleta',COUNT_BIG(*),N'BIGINT inválido' FROM stg.ATLETA WHERE NULLIF(TRIM(id_atleta),N'') IS NULL OR TRY_CONVERT(BIGINT,id_atleta) IS NULL;
INSERT INTO @errors SELECT N'convert.ATLETA.country_ids',COUNT_BIG(*),N'INT inválido en país nullable' FROM stg.ATLETA WHERE (NULLIF(TRIM(id_pais_nacimiento),N'') IS NOT NULL AND TRY_CONVERT(INT,id_pais_nacimiento) IS NULL) OR (NULLIF(TRIM(id_pais_nacionalidad),N'') IS NOT NULL AND TRY_CONVERT(INT,id_pais_nacionalidad) IS NULL) OR (NULLIF(TRIM(id_pais_fallecimiento),N'') IS NOT NULL AND TRY_CONVERT(INT,id_pais_fallecimiento) IS NULL);
INSERT INTO @errors SELECT N'convert.ATLETA.dates',COUNT_BIG(*),N'DATE inválida' FROM stg.ATLETA WHERE (NULLIF(TRIM(fecha_nacimiento),N'') IS NOT NULL AND TRY_CONVERT(DATE,fecha_nacimiento) IS NULL) OR (NULLIF(TRIM(fecha_fallecimiento),N'') IS NOT NULL AND TRY_CONVERT(DATE,fecha_fallecimiento) IS NULL);
INSERT INTO @errors SELECT N'convert.ATLETA.decimals',COUNT_BIG(*),N'DECIMAL inválido o fuera de precision/scale' FROM stg.ATLETA WHERE (NULLIF(TRIM(altura_cm),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(5,2),altura_cm) IS NULL) OR (NULLIF(TRIM(peso_kg),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(5,2),peso_kg) IS NULL) OR (NULLIF(TRIM(latitud),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(19,16),latitud) IS NULL) OR (NULLIF(TRIM(longitud),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(19,16),longitud) IS NULL);
INSERT INTO @errors SELECT N'convert.SEDE',COUNT_BIG(*),N'INT inválido' FROM stg.SEDE WHERE NULLIF(TRIM(id_sede),N'') IS NULL OR TRY_CONVERT(INT,id_sede) IS NULL OR NULLIF(TRIM(id_pais),N'') IS NULL OR TRY_CONVERT(INT,id_pais) IS NULL;
INSERT INTO @errors SELECT N'convert.EDICION_OLIMPICA',COUNT_BIG(*),N'INT/SMALLINT inválido' FROM stg.EDICION_OLIMPICA WHERE NULLIF(TRIM(id_edicion),N'') IS NULL OR TRY_CONVERT(INT,id_edicion) IS NULL OR NULLIF(TRIM(anio),N'') IS NULL OR TRY_CONVERT(SMALLINT,anio) IS NULL;
INSERT INTO @errors SELECT N'convert.DEPORTE',COUNT_BIG(*),N'INT inválido' FROM stg.DEPORTE WHERE NULLIF(TRIM(id_deporte),N'') IS NULL OR TRY_CONVERT(INT,id_deporte) IS NULL;
INSERT INTO @errors SELECT N'convert.DISCIPLINA',COUNT_BIG(*),N'INT inválido' FROM stg.DISCIPLINA WHERE NULLIF(TRIM(id_disciplina),N'') IS NULL OR TRY_CONVERT(INT,id_disciplina) IS NULL OR NULLIF(TRIM(id_deporte),N'') IS NULL OR TRY_CONVERT(INT,id_deporte) IS NULL;
INSERT INTO @errors SELECT N'convert.EVENTO',COUNT_BIG(*),N'BIGINT/INT inválido' FROM stg.EVENTO WHERE NULLIF(TRIM(id_evento),N'') IS NULL OR TRY_CONVERT(BIGINT,id_evento) IS NULL OR NULLIF(TRIM(id_disciplina),N'') IS NULL OR TRY_CONVERT(INT,id_disciplina) IS NULL;
INSERT INTO @errors SELECT N'convert.PARTICIPACION.required',COUNT_BIG(*),N'BIGINT/INT requerido inválido' FROM stg.PARTICIPACION WHERE NULLIF(TRIM(id_participacion),N'') IS NULL OR TRY_CONVERT(BIGINT,id_participacion) IS NULL OR NULLIF(TRIM(id_atleta),N'') IS NULL OR TRY_CONVERT(BIGINT,id_atleta) IS NULL OR NULLIF(TRIM(id_edicion),N'') IS NULL OR TRY_CONVERT(INT,id_edicion) IS NULL OR NULLIF(TRIM(id_evento),N'') IS NULL OR TRY_CONVERT(BIGINT,id_evento) IS NULL;
INSERT INTO @errors SELECT N'convert.PARTICIPACION.optional_ids',COUNT_BIG(*),N'INT nullable inválido' FROM stg.PARTICIPACION WHERE (NULLIF(TRIM(id_noc),N'') IS NOT NULL AND TRY_CONVERT(INT,id_noc) IS NULL) OR (NULLIF(TRIM(id_pais_nacionalidad),N'') IS NOT NULL AND TRY_CONVERT(INT,id_pais_nacionalidad) IS NULL);
INSERT INTO @errors SELECT N'convert.PARTICIPACION.decimals',COUNT_BIG(*),N'DECIMAL inválido o fuera de precision/scale' FROM stg.PARTICIPACION WHERE (NULLIF(TRIM(edad),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(5,2),edad) IS NULL) OR (NULLIF(TRIM(altura_cm_registrada),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(5,2),altura_cm_registrada) IS NULL) OR (NULLIF(TRIM(peso_kg_registrado),N'') IS NOT NULL AND TRY_CONVERT(DECIMAL(16,13),peso_kg_registrado) IS NULL) OR (NULLIF(TRIM(posicion),N'') IS NOT NULL AND TRY_CONVERT(INT,posicion) IS NULL);

/* NOT NULL y dominios. */
INSERT INTO @errors SELECT N'notnull.ENTIDAD_GEOGRAFICA',COUNT_BIG(*),N'id_entidad/nombre vacío' FROM stg.ENTIDAD_GEOGRAFICA WHERE NULLIF(TRIM(id_entidad),N'') IS NULL OR NULLIF(TRIM(nombre),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.NOC',COUNT_BIG(*),N'id_noc vacío' FROM stg.NOC WHERE NULLIF(TRIM(id_noc),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.ATLETA',COUNT_BIG(*),N'id_atleta/nombre vacío' FROM stg.ATLETA WHERE NULLIF(TRIM(id_atleta),N'') IS NULL OR NULLIF(TRIM(nombre),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.DEPORTE',COUNT_BIG(*),N'id_deporte/nombre vacío' FROM stg.DEPORTE WHERE NULLIF(TRIM(id_deporte),N'') IS NULL OR NULLIF(TRIM(nombre),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.DISCIPLINA',COUNT_BIG(*),N'id_disciplina/id_deporte/nombre vacío' FROM stg.DISCIPLINA WHERE NULLIF(TRIM(id_disciplina),N'') IS NULL OR NULLIF(TRIM(id_deporte),N'') IS NULL OR NULLIF(TRIM(nombre),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.EVENTO',COUNT_BIG(*),N'id_evento/id_disciplina/nombre vacío' FROM stg.EVENTO WHERE NULLIF(TRIM(id_evento),N'') IS NULL OR NULLIF(TRIM(id_disciplina),N'') IS NULL OR NULLIF(TRIM(nombre),N'') IS NULL;
INSERT INTO @errors SELECT N'notnull.PARTICIPACION',COUNT_BIG(*),N'clave requerida vacía' FROM stg.PARTICIPACION WHERE NULLIF(TRIM(id_participacion),N'') IS NULL OR NULLIF(TRIM(id_atleta),N'') IS NULL OR NULLIF(TRIM(id_edicion),N'') IS NULL OR NULLIF(TRIM(id_evento),N'') IS NULL;
INSERT INTO @errors SELECT N'domain.EDICION_OLIMPICA.temporada',COUNT_BIG(*),N'Temporada fuera del dominio final' FROM stg.EDICION_OLIMPICA WHERE TRIM(temporada) NOT IN (N'Summer',N'Winter',N'Intercalated Games',N'Summer Youth',N'Winter Youth');
INSERT INTO @errors SELECT N'domain.PARTICIPACION.medalla',COUNT_BIG(*),N'Medalla fuera del dominio' FROM stg.PARTICIPACION WHERE NULLIF(TRIM(medalla),N'') IS NOT NULL AND TRIM(medalla) NOT IN (N'Gold',N'Silver',N'Bronze');
INSERT INTO @errors SELECT N'domain.PARTICIPACION.empatado',COUNT_BIG(*),N'BIT fuera del dominio' FROM stg.PARTICIPACION WHERE NULLIF(TRIM(empatado),N'') IS NOT NULL AND LOWER(TRIM(empatado)) NOT IN (N'true',N'false',N'0',N'1');
INSERT INTO @errors SELECT N'domain.PARTICIPACION.posicion',COUNT_BIG(*),N'Posición no positiva' FROM stg.PARTICIPACION WHERE stg.CleanValue(posicion) IS NOT NULL AND stg.TryIntValue(posicion) <= 0;

/* Longitudes máximas del modelo físico. */
INSERT INTO @errors SELECT N'length.NOC',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.NOC WHERE LEN(nombre_noc)>150 OR LEN(notas)>500 OR LEN(codigo_noc)>3;
INSERT INTO @errors SELECT N'length.ATLETA',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.ATLETA WHERE LEN(nombre)>250 OR LEN(nombre_completo)>300 OR LEN(nombre_usado)>300 OR LEN(nombre_original)>300 OR LEN(otros_nombres)>500 OR LEN(apodos)>500 OR LEN(orden_nombre)>50 OR LEN(sexo)>20 OR LEN(ciudad_nacimiento)>150 OR LEN(region_nacimiento)>150 OR LEN(ciudad_fallecimiento)>150 OR LEN(region_fallecimiento)>150 OR LEN(titulos)>2000;
INSERT INTO @errors SELECT N'length.SEDE',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.SEDE WHERE LEN(nombre)>150;
INSERT INTO @errors SELECT N'length.EDICION_OLIMPICA',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.EDICION_OLIMPICA WHERE LEN(temporada)>20;
INSERT INTO @errors SELECT N'length.DEPORTE_DISCIPLINA',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.DEPORTE WHERE LEN(nombre)>150;
INSERT INTO @errors SELECT N'length.DISCIPLINA',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.DISCIPLINA WHERE LEN(nombre)>150;
INSERT INTO @errors SELECT N'length.EVENTO',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.EVENTO WHERE LEN(nombre)>300;
INSERT INTO @errors SELECT N'length.PARTICIPACION',COUNT_BIG(*),N'Longitud mayor al DDL' FROM stg.PARTICIPACION WHERE LEN(equipo)>250 OR LEN(nombre_competencia)>300 OR LEN(estado_resultado)>30 OR LEN(medalla)>20;

/* Duplicados de claves. */
INSERT INTO @errors SELECT N'duplicate.ENTIDAD_GEOGRAFICA',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_entidad),N'') k,COUNT_BIG(*) c FROM stg.ENTIDAD_GEOGRAFICA GROUP BY NULLIF(TRIM(id_entidad),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.POBLACION',COALESCE(SUM(c-1),0),N'PK compuesta duplicada' FROM (SELECT NULLIF(TRIM(id_entidad),N'') a,NULLIF(TRIM(anio),N'') b,COUNT_BIG(*) c FROM stg.POBLACION GROUP BY NULLIF(TRIM(id_entidad),N''),NULLIF(TRIM(anio),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.NOC',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_noc),N'') k,COUNT_BIG(*) c FROM stg.NOC GROUP BY NULLIF(TRIM(id_noc),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.ATLETA',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_atleta),N'') k,COUNT_BIG(*) c FROM stg.ATLETA GROUP BY NULLIF(TRIM(id_atleta),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.EDICION_OLIMPICA',COALESCE(SUM(c-1),0),N'PK o UNIQUE duplicada' FROM (SELECT NULLIF(TRIM(id_edicion),N'') k,COUNT_BIG(*) c FROM stg.EDICION_OLIMPICA GROUP BY NULLIF(TRIM(id_edicion),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.EDICION_OLIMPICA.anio_temporada',COALESCE(SUM(c-1),0),N'UNIQUE duplicada' FROM (SELECT NULLIF(TRIM(anio),N'') a,NULLIF(TRIM(temporada),N'') b,COUNT_BIG(*) c FROM stg.EDICION_OLIMPICA GROUP BY NULLIF(TRIM(anio),N''),NULLIF(TRIM(temporada),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.DEPORTE',COALESCE(SUM(c-1),0),N'PK o UNIQUE duplicada' FROM (SELECT NULLIF(TRIM(id_deporte),N'') k,COUNT_BIG(*) c FROM stg.DEPORTE GROUP BY NULLIF(TRIM(id_deporte),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.DISCIPLINA',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_disciplina),N'') k,COUNT_BIG(*) c FROM stg.DISCIPLINA GROUP BY NULLIF(TRIM(id_disciplina),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.EVENTO',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_evento),N'') k,COUNT_BIG(*) c FROM stg.EVENTO GROUP BY NULLIF(TRIM(id_evento),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'duplicate.PARTICIPACION',COALESCE(SUM(c-1),0),N'PK duplicada' FROM (SELECT NULLIF(TRIM(id_participacion),N'') k,COUNT_BIG(*) c FROM stg.PARTICIPACION GROUP BY NULLIF(TRIM(id_participacion),N'') HAVING COUNT_BIG(*)>1) d;

/* UNIQUE adicionales. */
INSERT INTO @errors SELECT N'unique.NOC.codigo_noc',COALESCE(SUM(c-1),0),N'Código NOC duplicado' FROM (SELECT NULLIF(TRIM(codigo_noc),N'') k,COUNT_BIG(*) c FROM stg.NOC GROUP BY NULLIF(TRIM(codigo_noc),N'') HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'unique.DEPORTE.nombre',COALESCE(SUM(c-1),0),N'Nombre de deporte duplicado' FROM (SELECT TRIM(nombre) k,COUNT_BIG(*) c FROM stg.DEPORTE GROUP BY TRIM(nombre) HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'unique.DISCIPLINA.deporte_nombre',COALESCE(SUM(c-1),0),N'Disciplina duplicada dentro de deporte' FROM (SELECT NULLIF(TRIM(id_deporte),N'') a,TRIM(nombre) b,COUNT_BIG(*) c FROM stg.DISCIPLINA GROUP BY NULLIF(TRIM(id_deporte),N''),TRIM(nombre) HAVING COUNT_BIG(*)>1) d;
INSERT INTO @errors SELECT N'unique.EVENTO.disciplina_nombre',COALESCE(SUM(c-1),0),N'Evento duplicado dentro de disciplina' FROM (SELECT NULLIF(TRIM(id_disciplina),N'') a,TRIM(nombre) b,COUNT_BIG(*) c FROM stg.EVENTO GROUP BY NULLIF(TRIM(id_disciplina),N''),TRIM(nombre) HAVING COUNT_BIG(*)>1) d;

/* FK potenciales inexistentes. */
INSERT INTO @errors SELECT N'fk.POBLACION.entidad',COUNT_BIG(*),N'Entidad inexistente' FROM stg.POBLACION s WHERE NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_entidad));
INSERT INTO @errors SELECT N'fk.NOC.entidad',COUNT_BIG(*),N'Entidad inexistente' FROM stg.NOC s WHERE NULLIF(TRIM(s.id_entidad),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_entidad));
INSERT INTO @errors SELECT N'fk.ATLETA.paises',COUNT_BIG(*),N'País inexistente' FROM stg.ATLETA s WHERE (NULLIF(TRIM(s.id_pais_nacimiento),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_pais_nacimiento))) OR (NULLIF(TRIM(s.id_pais_nacionalidad),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_pais_nacionalidad))) OR (NULLIF(TRIM(s.id_pais_fallecimiento),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_pais_fallecimiento)));
INSERT INTO @errors SELECT N'fk.SEDE.pais',COUNT_BIG(*),N'País inexistente' FROM stg.SEDE s WHERE NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_pais));
INSERT INTO @errors SELECT N'fk.EDICION_OLIMPICA.sede',COUNT_BIG(*),N'Sede inexistente' FROM stg.EDICION_OLIMPICA s WHERE NULLIF(TRIM(s.id_sede),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.SEDE p WHERE TRY_CONVERT(INT,p.id_sede)=TRY_CONVERT(INT,s.id_sede));
INSERT INTO @errors SELECT N'fk.DISCIPLINA.deporte',COUNT_BIG(*),N'Deporte inexistente' FROM stg.DISCIPLINA s WHERE NOT EXISTS (SELECT 1 FROM stg.DEPORTE p WHERE TRY_CONVERT(INT,p.id_deporte)=TRY_CONVERT(INT,s.id_deporte));
INSERT INTO @errors SELECT N'fk.EVENTO.disciplina',COUNT_BIG(*),N'Disciplina inexistente' FROM stg.EVENTO s WHERE NOT EXISTS (SELECT 1 FROM stg.DISCIPLINA p WHERE TRY_CONVERT(INT,p.id_disciplina)=TRY_CONVERT(INT,s.id_disciplina));
INSERT INTO @errors SELECT N'fk.PARTICIPACION.atleta',COUNT_BIG(*),N'Atleta inexistente' FROM stg.PARTICIPACION s WHERE NOT EXISTS (SELECT 1 FROM stg.ATLETA p WHERE TRY_CONVERT(BIGINT,p.id_atleta)=TRY_CONVERT(BIGINT,s.id_atleta));
INSERT INTO @errors SELECT N'fk.PARTICIPACION.edicion',COUNT_BIG(*),N'Edición inexistente' FROM stg.PARTICIPACION s WHERE NOT EXISTS (SELECT 1 FROM stg.EDICION_OLIMPICA p WHERE TRY_CONVERT(INT,p.id_edicion)=TRY_CONVERT(INT,s.id_edicion));
INSERT INTO @errors SELECT N'fk.PARTICIPACION.evento',COUNT_BIG(*),N'Evento inexistente' FROM stg.PARTICIPACION s WHERE NOT EXISTS (SELECT 1 FROM stg.EVENTO p WHERE TRY_CONVERT(BIGINT,p.id_evento)=TRY_CONVERT(BIGINT,s.id_evento));
INSERT INTO @errors SELECT N'fk.PARTICIPACION.noc',COUNT_BIG(*),N'NOC inexistente' FROM stg.PARTICIPACION s WHERE NULLIF(TRIM(s.id_noc),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.NOC p WHERE TRY_CONVERT(INT,p.id_noc)=TRY_CONVERT(INT,s.id_noc));
INSERT INTO @errors SELECT N'fk.PARTICIPACION.nacionalidad',COUNT_BIG(*),N'Entidad inexistente' FROM stg.PARTICIPACION s WHERE NULLIF(TRIM(s.id_pais_nacionalidad),N'') IS NOT NULL AND NOT EXISTS (SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA p WHERE TRY_CONVERT(INT,p.id_entidad)=TRY_CONVERT(INT,s.id_pais_nacionalidad));

/* Resultado auditable completo: incluye PASS y FAIL derivados de los datos. */
SELECT N'conteo.'+e.nombre AS validacion,
       e.filas AS esperado,
       a.filas AS actual,
       CASE WHEN e.filas=a.filas THEN N'PASS' ELSE N'FAIL' END AS estado,
       N'Conteo CSV esperado frente a staging' AS detalle
FROM @expected e
JOIN @actual a ON a.nombre=e.nombre
UNION ALL
SELECT validacion,
       CONVERT(BIGINT,0) AS esperado,
       filas_invalidas AS actual,
       CASE WHEN filas_invalidas=0 THEN N'PASS' ELSE N'FAIL' END AS estado,
       detalle
FROM @errors
ORDER BY validacion;

IF EXISTS (SELECT 1 FROM @errors WHERE filas_invalidas>0)
    THROW 51003, N'Prevalidación staging fallida. No se debe ejecutar 06_load_final.sql.', 1;

PRINT N'05_validate_staging.sql PASS. No hay conversiones, duplicados, truncamientos, dominios o FK potenciales inválidos.';
GO
