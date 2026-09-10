/*
    Bloque 5 — Validación del modelo físico.
    Solo consulta metadatos y conteos; no crea, modifica ni carga datos.
*/

USE OlimpiadasDB;
GO

DECLARE @expected_tables TABLE (table_name SYSNAME PRIMARY KEY);
INSERT INTO @expected_tables (table_name)
VALUES
    (N'ENTIDAD_GEOGRAFICA'), (N'POBLACION'), (N'NOC'), (N'ATLETA'),
    (N'SEDE'), (N'EDICION_OLIMPICA'), (N'DEPORTE'), (N'DISCIPLINA'),
    (N'EVENTO'), (N'PARTICIPACION');

/* 1. Conteo exacto de tablas finales bajo olympics. */
SELECT
    N'TABLE_COUNT' AS validacion,
    (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = N'olympics') AS tablas_actuales,
    (SELECT COUNT(*) FROM @expected_tables) AS tablas_esperadas,
    CASE WHEN (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id WHERE s.name = N'olympics') = 10
              AND NOT EXISTS (
                  SELECT 1 FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
                  WHERE s.name = N'olympics' AND t.name NOT IN (SELECT table_name FROM @expected_tables)
              )
         THEN N'PASS' ELSE N'FAIL' END AS estado;

/* 2. Tablas esperadas ausentes y tablas extras bajo olympics. */
SELECT N'MISSING_TABLE' AS tipo, e.table_name
FROM @expected_tables e
WHERE OBJECT_ID(N'olympics.' + e.table_name, N'U') IS NULL
UNION ALL
SELECT N'EXTRA_TABLE' AS tipo, t.name
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = N'olympics' AND t.name NOT IN (SELECT table_name FROM @expected_tables);

/* 3. Tablas finales creadas accidentalmente en dbo. */
SELECT N'DBO_FINAL_TABLE' AS tipo, t.name
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = N'dbo' AND t.name IN (SELECT table_name FROM @expected_tables);

/* 4. Columnas, tipos, longitud y NULL/NOT NULL. */
DECLARE @expected_columns TABLE
(
    table_name SYSNAME,
    column_name SYSNAME,
    type_name SYSNAME,
    max_length INT,
    is_nullable BIT,
    PRIMARY KEY (table_name, column_name)
);
INSERT INTO @expected_columns (table_name, column_name, type_name, max_length, is_nullable)
VALUES
 (N'ENTIDAD_GEOGRAFICA',N'id_entidad',N'int',4,0),(N'ENTIDAD_GEOGRAFICA',N'nombre',N'nvarchar',300,0),(N'ENTIDAD_GEOGRAFICA',N'codigo_pais',N'char',3,1),
 (N'POBLACION',N'id_entidad',N'int',4,0),(N'POBLACION',N'anio',N'smallint',2,0),(N'POBLACION',N'poblacion',N'bigint',8,1),
 (N'NOC',N'id_noc',N'int',4,0),(N'NOC',N'codigo_noc',N'char',3,1),(N'NOC',N'nombre_noc',N'nvarchar',300,1),(N'NOC',N'id_entidad',N'int',4,1),(N'NOC',N'notas',N'nvarchar',1000,1),
 (N'ATLETA',N'id_atleta',N'bigint',8,0),(N'ATLETA',N'nombre',N'nvarchar',500,0),(N'ATLETA',N'nombre_completo',N'nvarchar',600,1),(N'ATLETA',N'nombre_usado',N'nvarchar',600,1),(N'ATLETA',N'nombre_original',N'nvarchar',600,1),(N'ATLETA',N'otros_nombres',N'nvarchar',1000,1),(N'ATLETA',N'apodos',N'nvarchar',1000,1),(N'ATLETA',N'orden_nombre',N'nvarchar',100,1),(N'ATLETA',N'sexo',N'nvarchar',40,1),(N'ATLETA',N'fecha_nacimiento',N'date',NULL,1),(N'ATLETA',N'ciudad_nacimiento',N'nvarchar',300,1),(N'ATLETA',N'region_nacimiento',N'nvarchar',300,1),(N'ATLETA',N'id_pais_nacimiento',N'int',4,1),(N'ATLETA',N'id_pais_nacionalidad',N'int',4,1),(N'ATLETA',N'fecha_fallecimiento',N'date',NULL,1),(N'ATLETA',N'ciudad_fallecimiento',N'nvarchar',300,1),(N'ATLETA',N'region_fallecimiento',N'nvarchar',300,1),(N'ATLETA',N'id_pais_fallecimiento',N'int',4,1),(N'ATLETA',N'altura_cm',N'decimal',NULL,1),(N'ATLETA',N'peso_kg',N'decimal',NULL,1),(N'ATLETA',N'roles',N'nvarchar',-1,1),(N'ATLETA',N'afiliaciones',N'nvarchar',-1,1),(N'ATLETA',N'titulos',N'nvarchar',4000,1),(N'ATLETA',N'latitud',N'decimal',NULL,1),(N'ATLETA',N'longitud',N'decimal',NULL,1),
 (N'SEDE',N'id_sede',N'int',4,0),(N'SEDE',N'nombre',N'nvarchar',300,0),(N'SEDE',N'id_pais',N'int',4,0),
 (N'EDICION_OLIMPICA',N'id_edicion',N'int',4,0),(N'EDICION_OLIMPICA',N'anio',N'smallint',2,0),(N'EDICION_OLIMPICA',N'temporada',N'nvarchar',40,0),(N'EDICION_OLIMPICA',N'id_sede',N'int',4,1),
 (N'DEPORTE',N'id_deporte',N'int',4,0),(N'DEPORTE',N'nombre',N'nvarchar',300,0),
 (N'DISCIPLINA',N'id_disciplina',N'int',4,0),(N'DISCIPLINA',N'id_deporte',N'int',4,0),(N'DISCIPLINA',N'nombre',N'nvarchar',300,0),
 (N'EVENTO',N'id_evento',N'bigint',8,0),(N'EVENTO',N'id_disciplina',N'int',4,0),(N'EVENTO',N'nombre',N'nvarchar',600,0),
 (N'PARTICIPACION',N'id_participacion',N'bigint',8,0),(N'PARTICIPACION',N'id_atleta',N'bigint',8,0),(N'PARTICIPACION',N'id_edicion',N'int',4,0),(N'PARTICIPACION',N'id_evento',N'bigint',8,0),(N'PARTICIPACION',N'id_noc',N'int',4,1),(N'PARTICIPACION',N'id_pais_nacionalidad',N'int',4,1),(N'PARTICIPACION',N'equipo',N'nvarchar',500,1),(N'PARTICIPACION',N'nombre_competencia',N'nvarchar',600,1),(N'PARTICIPACION',N'edad',N'decimal',NULL,1),(N'PARTICIPACION',N'altura_cm_registrada',N'decimal',NULL,1),(N'PARTICIPACION',N'peso_kg_registrado',N'decimal',NULL,1),(N'PARTICIPACION',N'posicion',N'int',4,1),(N'PARTICIPACION',N'empatado',N'bit',1,1),(N'PARTICIPACION',N'estado_resultado',N'nvarchar',60,1),(N'PARTICIPACION',N'medalla',N'nvarchar',40,1);

SELECT e.table_name, e.column_name, e.type_name AS tipo_esperado, ty.name AS tipo_actual,
       e.max_length AS longitud_esperada_bytes, c.max_length AS longitud_actual_bytes,
       e.is_nullable AS nullable_esperado, c.is_nullable AS nullable_actual,
       CASE WHEN c.column_id IS NOT NULL AND ty.name = e.type_name
                  AND (e.max_length IS NULL OR c.max_length = e.max_length)
                  AND c.is_nullable = e.is_nullable THEN N'PASS' ELSE N'FAIL' END AS estado
FROM @expected_columns e
LEFT JOIN sys.tables t ON t.name = e.table_name AND t.schema_id = SCHEMA_ID(N'olympics')
LEFT JOIN sys.columns c ON c.object_id = t.object_id AND c.name = e.column_name
LEFT JOIN sys.types ty ON ty.user_type_id = c.user_type_id;

/* 4b. Precision y scale exactas para todas las columnas DECIMAL. */
DECLARE @expected_decimals TABLE
(
    table_name SYSNAME,
    column_name SYSNAME,
    precision_value TINYINT,
    scale_value TINYINT,
    PRIMARY KEY (table_name, column_name)
);
INSERT INTO @expected_decimals (table_name, column_name, precision_value, scale_value)
VALUES
    (N'ATLETA', N'altura_cm', 5, 2),
    (N'ATLETA', N'peso_kg', 5, 2),
    (N'ATLETA', N'latitud', 19, 16),
    (N'ATLETA', N'longitud', 19, 16),
    (N'PARTICIPACION', N'edad', 5, 2),
    (N'PARTICIPACION', N'altura_cm_registrada', 5, 2),
    (N'PARTICIPACION', N'peso_kg_registrado', 16, 13);

SELECT e.table_name, e.column_name,
       e.precision_value AS precision_esperada, c.precision AS precision_actual,
       e.scale_value AS scale_esperada, c.scale AS scale_actual,
       CASE WHEN c.column_id IS NOT NULL AND ty.name = N'decimal'
                  AND c.precision = e.precision_value AND c.scale = e.scale_value
            THEN N'PASS' ELSE N'FAIL' END AS estado
FROM @expected_decimals e
LEFT JOIN sys.tables t ON t.name = e.table_name AND t.schema_id = SCHEMA_ID(N'olympics')
LEFT JOIN sys.columns c ON c.object_id = t.object_id AND c.name = e.column_name
LEFT JOIN sys.types ty ON ty.user_type_id = c.user_type_id;

/* 5. PK, UNIQUE, FK y CHECK definidos en olympics. */
SELECT N'PRIMARY_KEY_OR_UNIQUE' AS tipo, kc.name AS constraint_name, t.name AS table_name,
       kc.type_desc AS constraint_type, i.is_unique, i.is_primary_key,
       STRING_AGG(c.name, N', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns_list
FROM sys.key_constraints kc
JOIN sys.tables t ON t.object_id = kc.parent_object_id
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.indexes i ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE s.name = N'olympics'
GROUP BY kc.name, t.name, kc.type_desc, i.is_unique, i.is_primary_key;

SELECT N'FOREIGN_KEY' AS tipo, fk.name AS constraint_name,
       OBJECT_SCHEMA_NAME(fk.parent_object_id) + N'.' + OBJECT_NAME(fk.parent_object_id) AS source_table,
       COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS source_column,
       OBJECT_SCHEMA_NAME(fk.referenced_object_id) + N'.' + OBJECT_NAME(fk.referenced_object_id) AS target_table,
       COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS target_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = N'olympics';

SELECT N'CHECK' AS tipo, cc.name AS constraint_name, OBJECT_NAME(cc.parent_object_id) AS table_name, cc.definition
FROM sys.check_constraints cc
WHERE OBJECT_SCHEMA_NAME(cc.parent_object_id) = N'olympics';

/* 6. Las diez tablas deben quedar vacías en este bloque. */
SELECT t.name AS table_name, SUM(p.rows) AS row_count,
       CASE WHEN SUM(p.rows) = 0 THEN N'PASS' ELSE N'FAIL' END AS estado
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1)
WHERE s.name = N'olympics' AND t.name IN (SELECT table_name FROM @expected_tables)
GROUP BY t.name
ORDER BY t.name;
GO
