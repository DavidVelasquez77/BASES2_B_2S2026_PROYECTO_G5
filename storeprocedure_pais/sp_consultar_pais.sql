/*
========================================================================================
Sistemas de Bases de Datos 2 — 2do. Semestre 2026
Proyecto Fase 1: Olimpiadas (1896 - 2024)
Grupo 7

Archivo: sp_consultar_pais.sql
Ruta: storeprocedure_pais/sp_consultar_pais.sql
Propósito: Implementación oficial y optimizada del Stored Procedure para el Inciso e).
           Consulta integral y analítica de información histórica por País / NOC:
           - Perfil geográfico, códigos NOC y población censal más reciente.
           - Condición histórica de SEDE olímpica (ciudades, años y temporadas).
           - Medallero olímpico oficial (calculado con clave única por evento y NOC para
             evitar inflación en deportes de equipo) y total de preseas físicas a atletas.
           - Detalle cronológico de participaciones con trazabilidad de código NOC y país.
           - Control robusto de ambigüedad, validación de dominio y protección de comodines.

Esquema de ejecución: olympics (Solo lectura sobre el modelo físico final).
Idempotencia: CREATE OR ALTER PROCEDURE.
========================================================================================
*/

USE OlimpiadasDB;
GO

SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO

CREATE OR ALTER PROCEDURE olympics.sp_consultar_pais
    @pais_o_noc           NVARCHAR(150),       -- Código NOC (ej. 'GUA', 'FRA', 'USA'), Código ISO (ej. 'GTM') o Nombre del País (ej. 'Guatemala', 'Francia')
    @anio                 SMALLINT      = NULL, -- Filtro opcional por año olímpico (ej. 2024, 2012, 2008)
    @temporada            NVARCHAR(30)  = NULL, -- Filtro opcional por temporada ('Summer', 'Winter', 'Summer Youth', 'Winter Youth', 'Intercalated Games')
    @deporte              NVARCHAR(150) = NULL, -- Filtro opcional por deporte (ej. 'Athletics', 'Shooting', 'Football')
    @top_participaciones  INT           = 50    -- Límite de filas para el detalle (default: 50, máx: 1000)
AS
BEGIN
    SET NOCOUNT ON;

    -- ====================================================================================
    -- PASO 1: VALIDACIÓN DEFENSIVA Y NORMALIZACIÓN DE ENTRADAS
    -- ====================================================================================

    DECLARE @param_limpio NVARCHAR(150) = TRIM(@pais_o_noc);

    -- 1.1 Validación de parámetro obligatorio
    IF @param_limpio IS NULL OR @param_limpio = N''
    BEGIN
        RAISERROR(N'ERROR: El parámetro @pais_o_noc no puede estar vacío o nulo. Proporcione un código NOC (ej. ''GUA''), código ISO (ej. ''GTM'') o nombre de país (ej. ''Guatemala'').', 16, 1);
        RETURN;
    END;

    -- 1.2 Validación estricta del dominio de @temporada (Requisito de Auditoría SP_FINAL_REVIEW)
    IF @temporada IS NOT NULL
    BEGIN
        SET @temporada = TRIM(@temporada);
        IF @temporada NOT IN (N'Summer', N'Winter', N'Summer Youth', N'Winter Youth', N'Intercalated Games')
        BEGIN
            RAISERROR(N'ERROR: La temporada ingresada "%s" no es válida. Valores permitidos: "Summer", "Winter", "Summer Youth", "Winter Youth", "Intercalated Games".', 16, 1, @temporada);
            RETURN;
        END;
    END;

    -- 1.3 Normalización y control de límites en @top_participaciones
    IF @top_participaciones IS NULL OR @top_participaciones <= 0
        SET @top_participaciones = 50;
    ELSE IF @top_participaciones > 1000
        SET @top_participaciones = 1000;

    -- 1.4 Escape seguro de caracteres comodín en filtros con LIKE
    DECLARE @deporte_escapado NVARCHAR(160) = NULL;
    IF @deporte IS NOT NULL AND TRIM(@deporte) <> N''
    BEGIN
        SET @deporte_escapado = REPLACE(REPLACE(REPLACE(TRIM(@deporte), N'[', N'[[]'), N'%', N'[%]'), N'_', N'[_]');
    END;

    DECLARE @param_escapado NVARCHAR(160) = REPLACE(REPLACE(REPLACE(@param_limpio, N'[', N'[[]'), N'%', N'[%]'), N'_', N'[_]');

    -- ====================================================================================
    -- PASO 2: RESOLUCIÓN JERÁRQUICA Y CONTROL DE AMBIGÜEDAD DE LA ENTIDAD GEOGRÁFICA
    -- ====================================================================================
    -- Prioridad de resolución:
    --   1. Código NOC exacto (ej. 'GUA', 'FRA', 'ANZ')
    --   2. Código ISO de país exacto (ej. 'GTM', 'FRA', 'USA')
    --   3. Nombre exacto de entidad geográfica (con insensibilidad a acentos)
    --   4. Coincidencia parcial: si hay 1 país, se resuelve. Si hay más de 1, se reporta
    --      ambigüedad con lista de candidatos para evitar selección arbitraria.
    -- ====================================================================================

    DECLARE @id_entidad INT = NULL;

    -- 2.1 Búsqueda exacta por código NOC
    SELECT TOP 1 @id_entidad = n.id_entidad
    FROM olympics.NOC n
    WHERE n.codigo_noc = UPPER(@param_limpio)
      AND n.id_entidad IS NOT NULL;

    -- 2.2 Búsqueda exacta por código ISO de país
    IF @id_entidad IS NULL
    BEGIN
        SELECT TOP 1 @id_entidad = eg.id_entidad
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        WHERE eg.codigo_pais = UPPER(@param_limpio);
    END;

    -- 2.3 Búsqueda exacta por nombre de entidad geográfica (insensible a acentos)
    IF @id_entidad IS NULL
    BEGIN
        SELECT TOP 1 @id_entidad = eg.id_entidad
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        WHERE eg.nombre = @param_limpio COLLATE Latin1_General_CI_AI;
    END;

    -- 2.4 Búsqueda aproximada y control de ambigüedad
    IF @id_entidad IS NULL
    BEGIN
        -- Tabla temporal en memoria para recolectar candidatos
        DECLARE @candidatos TABLE (
            id_entidad INT PRIMARY KEY,
            nombre NVARCHAR(150),
            codigo_pais CHAR(3),
            codigos_noc NVARCHAR(100)
        );

        INSERT INTO @candidatos (id_entidad, nombre, codigo_pais, codigos_noc)
        SELECT DISTINCT
            eg.id_entidad,
            eg.nombre,
            eg.codigo_pais,
            ISNULL((
                SELECT STRING_AGG(CONVERT(NVARCHAR(10), n2.codigo_noc), N', ')
                FROM olympics.NOC n2
                WHERE n2.id_entidad = eg.id_entidad
            ), N'Sin NOC') AS codigos_noc
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        LEFT JOIN olympics.NOC n ON n.id_entidad = eg.id_entidad
        WHERE eg.nombre LIKE N'%' + @param_escapado + N'%' COLLATE Latin1_General_CI_AI
           OR n.nombre_noc LIKE N'%' + @param_escapado + N'%' COLLATE Latin1_General_CI_AI;

        DECLARE @total_candidatos INT = (SELECT COUNT(*) FROM @candidatos);

        IF @total_candidatos = 0
        BEGIN
            RAISERROR(N'AVISO: No se encontró ningún país o código NOC que coincida con el parámetro ingresado: "%s". Por favor verifique el nombre o código.', 10, 1, @pais_o_noc);
            RETURN;
        END;
        ELSE IF @total_candidatos = 1
        BEGIN
            SELECT @id_entidad = id_entidad FROM @candidatos;
        END;
        ELSE
        BEGIN
            -- Más de una coincidencia: Se declara ambigüedad explícita (Solución a CONTRACT DECISION de SP_FINAL_REVIEW)
            SELECT 
                N'BÚSQUEDA AMBIGUA' AS estado,
                CONCAT(N'Se encontraron ', @total_candidatos, N' entidades que coinciden con "', @pais_o_noc, N'". Por favor refine su búsqueda utilizando el código NOC exacto o el nombre completo.') AS mensaje;

            SELECT 
                id_entidad,
                nombre AS pais,
                ISNULL(codigo_pais, N'N/A') AS codigo_iso,
                codigos_noc AS codigos_noc_asociados
            FROM @candidatos
            ORDER BY nombre ASC;

            RETURN;
        END;
    END;

    -- ====================================================================================
    -- RESULTSET 1: PERFIL GENERAL DEL PAÍS, CÓDIGOS NOC Y POBLACIÓN CENSADA
    -- ====================================================================================
    SELECT 
        eg.id_entidad,
        eg.nombre AS pais,
        ISNULL(eg.codigo_pais, N'N/A') AS codigo_iso_pais,
        ISNULL((
            SELECT STRING_AGG(CONVERT(NVARCHAR(10), n.codigo_noc), N', ')
            FROM olympics.NOC n
            WHERE n.id_entidad = eg.id_entidad
        ), N'Sin NOC asignado') AS codigos_noc_historicos,
        pob.poblacion AS poblacion_mas_reciente,
        pob.anio AS anio_censo_poblacion
    FROM olympics.ENTIDAD_GEOGRAFICA eg
    OUTER APPLY (
        SELECT TOP 1 p.poblacion, p.anio
        FROM olympics.POBLACION p
        WHERE p.id_entidad = eg.id_entidad
        ORDER BY p.anio DESC
    ) pob
    WHERE eg.id_entidad = @id_entidad;

    -- ====================================================================================
    -- RESULTSET 2: CONDICIÓN HISTÓRICA DE SEDE OLÍMPICA
    -- ====================================================================================
    SELECT 
        CASE WHEN COUNT(eo.id_edicion) > 0 THEN N'SÍ' ELSE N'NO' END AS ha_sido_sede,
        COUNT(eo.id_edicion) AS total_ediciones_como_sede,
        ISNULL((
            SELECT STRING_AGG(CONVERT(NVARCHAR(150), ciudades.nombre), N', ')
            FROM (SELECT DISTINCT s2.nombre FROM olympics.SEDE s2 WHERE s2.id_pais = @id_entidad) ciudades
        ), N'Ninguna') AS ciudades_sede,
        ISNULL(
            STRING_AGG(CONVERT(NVARCHAR(300), CONCAT(s.nombre, N' (', eo.anio, N' ', eo.temporada, N')')), N', '),
            N'Este país nunca ha sido sede de Juegos Olímpicos'
        ) AS resumen_ediciones_como_sede
    FROM olympics.SEDE s
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_sede = s.id_sede
    WHERE s.id_pais = @id_entidad;

    -- ====================================================================================
    -- RESULTSET 2.1: DETALLE DE CADA EDICIÓN ORGANIZADA COMO SEDE (Si aplica)
    -- ====================================================================================
    SELECT 
        eo.id_edicion,
        eo.anio,
        eo.temporada,
        s.nombre AS ciudad_sede
    FROM olympics.SEDE s
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_sede = s.id_sede
    WHERE s.id_pais = @id_entidad
    ORDER BY eo.anio ASC, eo.temporada ASC;

    -- ====================================================================================
    -- RESULTSET 3: RESUMEN DE MEDALLERO Y ESTADÍSTICAS GLOBALES
    -- ====================================================================================
    -- CONTROL DE CALIDAD Y MEDALLERO OFICIAL (AUDITORÍA SP_FINAL_REVIEW):
    -- 1. Medallas oficiales del país: La clave lógica única oficial es
    --    (id_edicion + id_evento + id_noc + medalla). Evita inflar oros en deportes de
    --    equipo (ej. 1 oro oficial para el fútbol de Argentina 2008 en vez de 18).
    -- 2. Preseas físicas individuales: Conteo real de medallas entregadas a deportistas.
    -- Ambos indicadores se reportan de forma transparente y cotejada con olympics.com.
    -- ====================================================================================
    SELECT 
        (
            SELECT COUNT(DISTINCT p1.id_participacion)
            FROM olympics.PARTICIPACION p1
            JOIN olympics.NOC n1 ON n1.id_noc = p1.id_noc
            JOIN olympics.EDICION_OLIMPICA eo1 ON eo1.id_edicion = p1.id_edicion
            JOIN olympics.EVENTO ev1 ON ev1.id_evento = p1.id_evento
            JOIN olympics.DISCIPLINA di1 ON di1.id_disciplina = ev1.id_disciplina
            JOIN olympics.DEPORTE dep1 ON dep1.id_deporte = di1.id_deporte
            WHERE n1.id_entidad = @id_entidad
              AND (@anio IS NULL OR eo1.anio = @anio)
              AND (@temporada IS NULL OR eo1.temporada = @temporada)
              AND (@deporte_escapado IS NULL OR dep1.nombre LIKE N'%' + @deporte_escapado + N'%')
        ) AS total_participaciones,
        (
            SELECT COUNT(DISTINCT p2.id_atleta)
            FROM olympics.PARTICIPACION p2
            JOIN olympics.NOC n2 ON n2.id_noc = p2.id_noc
            JOIN olympics.EDICION_OLIMPICA eo2 ON eo2.id_edicion = p2.id_edicion
            JOIN olympics.EVENTO ev2 ON ev2.id_evento = p2.id_evento
            JOIN olympics.DISCIPLINA di2 ON di2.id_disciplina = ev2.id_disciplina
            JOIN olympics.DEPORTE dep2 ON dep2.id_deporte = di2.id_deporte
            WHERE n2.id_entidad = @id_entidad
              AND (@anio IS NULL OR eo2.anio = @anio)
              AND (@temporada IS NULL OR eo2.temporada = @temporada)
              AND (@deporte_escapado IS NULL OR dep2.nombre LIKE N'%' + @deporte_escapado + N'%')
        ) AS total_atletas_distintos,
        ISNULL(SUM(CASE WHEN m.medalla = N'Gold' THEN 1 ELSE 0 END), 0) AS medallas_oro_oficiales,
        ISNULL(SUM(CASE WHEN m.medalla = N'Silver' THEN 1 ELSE 0 END), 0) AS medallas_plata_oficiales,
        ISNULL(SUM(CASE WHEN m.medalla = N'Bronze' THEN 1 ELSE 0 END), 0) AS medallas_bronce_oficiales,
        COUNT(m.medalla) AS total_medallas_oficiales_pais,
        (
            SELECT COUNT(*)
            FROM olympics.PARTICIPACION p3
            JOIN olympics.NOC n3 ON n3.id_noc = p3.id_noc
            JOIN olympics.EDICION_OLIMPICA eo3 ON eo3.id_edicion = p3.id_edicion
            JOIN olympics.EVENTO ev3 ON ev3.id_evento = p3.id_evento
            JOIN olympics.DISCIPLINA di3 ON di3.id_disciplina = ev3.id_disciplina
            JOIN olympics.DEPORTE dep3 ON dep3.id_deporte = di3.id_deporte
            WHERE n3.id_entidad = @id_entidad
              AND p3.medalla IS NOT NULL
              AND (@anio IS NULL OR eo3.anio = @anio)
              AND (@temporada IS NULL OR eo3.temporada = @temporada)
              AND (@deporte_escapado IS NULL OR dep3.nombre LIKE N'%' + @deporte_escapado + N'%')
        ) AS preseas_totales_entregadas_a_atletas
    FROM (
        -- Clave lógica oficial: Edición + Evento + NOC + Medalla
        SELECT DISTINCT p.id_edicion, p.id_evento, p.id_noc, p.medalla
        FROM olympics.PARTICIPACION p
        JOIN olympics.NOC n ON n.id_noc = p.id_noc
        JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
        JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
        JOIN olympics.DISCIPLINA di ON di.id_disciplina = ev.id_disciplina
        JOIN olympics.DEPORTE dep ON dep.id_deporte = di.id_deporte
        WHERE n.id_entidad = @id_entidad
          AND p.medalla IS NOT NULL
          AND (@anio IS NULL OR eo.anio = @anio)
          AND (@temporada IS NULL OR eo.temporada = @temporada)
          AND (@deporte_escapado IS NULL OR dep.nombre LIKE N'%' + @deporte_escapado + N'%')
    ) AS m;

    -- ====================================================================================
    -- RESULTSET 4: DETALLE DE PARTICIPACIONES Y ATLETAS DESTACADOS
    -- ====================================================================================
    -- Detalle fiel de PARTICIPACION que incluye trazabilidad de código NOC y país
    -- representado, ordenado por relevancia de medalla y cronología.
    -- ====================================================================================
    SELECT TOP (@top_participaciones)
        eo.anio,
        eo.temporada,
        ISNULL(s.nombre, N'Sede no especificada') AS ciudad_sede,
        dep.nombre AS deporte,
        di.nombre AS disciplina,
        ev.nombre AS evento,
        a.nombre AS atleta,
        n.codigo_noc,
        n.nombre_noc,
        eg.nombre AS pais_representado,
        ISNULL(p.equipo, N'Individual') AS equipo,
        p.posicion,
        ISNULL(p.medalla, N'Sin Medalla') AS medalla,
        ISNULL(p.estado_resultado, N'Finished') AS estado_resultado
    FROM olympics.PARTICIPACION p
    JOIN olympics.NOC n ON n.id_noc = p.id_noc
    JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad = n.id_entidad
    JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    LEFT JOIN olympics.SEDE s ON s.id_sede = eo.id_sede
    JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
    JOIN olympics.DISCIPLINA di ON di.id_disciplina = ev.id_disciplina
    JOIN olympics.DEPORTE dep ON dep.id_deporte = di.id_deporte
    WHERE n.id_entidad = @id_entidad
      AND (@anio IS NULL OR eo.anio = @anio)
      AND (@temporada IS NULL OR eo.temporada = @temporada)
      AND (@deporte_escapado IS NULL OR dep.nombre LIKE N'%' + @deporte_escapado + N'%')
    ORDER BY 
        CASE p.medalla 
            WHEN N'Gold' THEN 1 
            WHEN N'Silver' THEN 2 
            WHEN N'Bronze' THEN 3 
            ELSE 4 
        END ASC,
        eo.anio DESC,
        dep.nombre ASC,
        ev.nombre ASC,
        a.nombre ASC;

END;
GO

PRINT N'Procedimiento almacenado olympics.sp_consultar_pais creado/actualizado exitosamente.';
GO
