/*
========================================================================================
Sistemas de Bases de Datos 2 — 2do. Semestre 2026
Proyecto Fase 1: Olimpiadas (1896 - 2024)
Grupo 7

Archivo: 14_sp_consultar_pais.sql
Propósito: Implementación oficial del Stored Procedure para el Inciso e).
           Consulta integral de información histórica por País / NOC:
           - Perfil geográfico, códigos NOC y población censal más reciente.
           - Condición histórica de SEDE olímpica (ciudades, años y temporadas).
           - Medallero olímpico oficial (calculado por evento para evitar inflación en
             deportes de equipo) y total de preseas entregadas a deportistas.
           - Detalle cronológico de participaciones y atletas destacados con filtros opcionales.

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
    @pais_o_noc           NVARCHAR(150),       -- Código NOC (ej. 'GUA', 'FRA', 'USA') o Nombre del País (ej. 'Guatemala', 'France')
    @anio                 SMALLINT      = NULL, -- Filtro opcional por año olímpico (ej. 2024, 2012)
    @temporada            NVARCHAR(20)  = NULL, -- Filtro opcional por temporada ('Summer', 'Winter', 'Summer Youth', etc.)
    @deporte              NVARCHAR(150) = NULL, -- Filtro opcional por deporte (ej. 'Athletics', 'Shooting')
    @top_participaciones  INT           = 50   -- Límite de filas para el detalle de participaciones (default: 50)
AS
BEGIN
    SET NOCOUNT ON;

    -- ====================================================================================
    -- PASO 1: RESOLUCIÓN FLEXIBLE Y DEFENSIVA DE LA ENTIDAD GEOGRÁFICA
    -- ====================================================================================
    -- Permite que el usuario consulte tanto por código NOC ('GUA'), código ISO ('GTM')
    -- o por el nombre común de la entidad ('Guatemala', 'United States', 'Francia').
    -- ====================================================================================

    DECLARE @id_entidad INT = NULL;
    DECLARE @param_limpio NVARCHAR(150) = TRIM(@pais_o_noc);

    -- Validación defensiva: parámetro vacío o nulo
    IF @param_limpio IS NULL OR @param_limpio = N''
    BEGIN
        RAISERROR(N'AVISO: El parámetro @pais_o_noc no puede estar vacío o nulo. Proporcione un código NOC (ej. ''GUA''), código ISO (ej. ''GTM'') o nombre de país (ej. ''Guatemala'').', 10, 1);
        RETURN;
    END;

    -- 1.1 Búsqueda exacta por código NOC
    SELECT TOP 1 @id_entidad = n.id_entidad
    FROM olympics.NOC n
    WHERE n.codigo_noc = UPPER(@param_limpio)
      AND n.id_entidad IS NOT NULL;

    -- 1.2 Búsqueda exacta por código ISO de país
    IF @id_entidad IS NULL
    BEGIN
        SELECT TOP 1 @id_entidad = eg.id_entidad
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        WHERE eg.codigo_pais = UPPER(@param_limpio);
    END;

    -- 1.3 Búsqueda exacta por nombre de entidad geográfica
    IF @id_entidad IS NULL
    BEGIN
        SELECT TOP 1 @id_entidad = eg.id_entidad
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        WHERE eg.nombre = @param_limpio;
    END;

    -- 1.4 Búsqueda aproximada por coincidencia parcial en nombre de entidad o NOC
    IF @id_entidad IS NULL
    BEGIN
        SELECT TOP 1 @id_entidad = eg.id_entidad
        FROM olympics.ENTIDAD_GEOGRAFICA eg
        LEFT JOIN olympics.NOC n ON n.id_entidad = eg.id_entidad
        WHERE eg.nombre LIKE '%' + @param_limpio + '%'
           OR n.nombre_noc LIKE '%' + @param_limpio + '%'
        ORDER BY 
            CASE WHEN eg.nombre = @param_limpio THEN 1 ELSE 2 END,
            eg.id_entidad ASC;
    END;

    -- Validación de existencia
    IF @id_entidad IS NULL
    BEGIN
        RAISERROR(N'AVISO: No se encontró ningún país o código NOC que coincida con el parámetro ingresado: "%s". Por favor verifique el nombre o código.', 10, 1, @pais_o_noc);
        RETURN;
    END;

    -- ====================================================================================
    -- RESULTSET 1: PERFIL GENERAL DEL PAÍS, CÓDIGOS NOC Y POBLACIÓN CENSADA
    -- ====================================================================================
    -- Conecta ENTIDAD_GEOGRAFICA con NOC (STRING_AGG para múltiples códigos históricos)
    -- y recupera la población censal más reciente disponible en POBLACION.
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
    -- Responde al requerimiento del Inciso e): "¿Ha sido sede y en qué años?".
    -- Conecta ENTIDAD_GEOGRAFICA -> SEDE -> EDICION_OLIMPICA.
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
    -- CONTROL DE CALIDAD DE DATOS (REGLA DE ORO):
    -- En deportes por equipo (ej. Fútbol, Baloncesto, Relevos), múltiples atletas reciben
    -- presea física, generando múltiples filas en PARTICIPACION con medalla.
    -- Para el medallero oficial olímpico del país, cada evento ganado cuenta como 1 medalla.
    -- Aquí se reportan AMBAS métricas de forma transparente:
    --   1. Medallas oficiales del país por evento único (COUNT DISTINCT).
    --   2. Preseas físicas individuales entregadas a los deportistas (COUNT *).
    -- Además, respeta los filtros opcionales (@anio, @temporada, @deporte).
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
              AND (@deporte IS NULL OR dep1.nombre LIKE '%' + @deporte + '%')
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
              AND (@deporte IS NULL OR dep2.nombre LIKE '%' + @deporte + '%')
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
              AND (@deporte IS NULL OR dep3.nombre LIKE '%' + @deporte + '%')
        ) AS preseas_totales_entregadas_a_atletas
    FROM (
        SELECT DISTINCT p.id_edicion, p.id_evento, p.medalla
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
          AND (@deporte IS NULL OR dep.nombre LIKE '%' + @deporte + '%')
    ) AS m;

    -- ====================================================================================
    -- RESULTSET 4: DETALLE DE PARTICIPACIONES Y ATLETAS DESTACADOS
    -- ====================================================================================
    -- Proporciona el historial individual de participaciones, posiciones y preseas.
    -- Prioriza en el orden de salida a los ganadores de medallas (Gold, Silver, Bronze),
    -- seguidos de las ediciones más recientes y nombres de eventos.
    -- Controlado por el parámetro @top_participaciones para un despliegue ágil.
    -- ====================================================================================
    SELECT TOP (@top_participaciones)
        eo.anio,
        eo.temporada,
        ISNULL(s.nombre, N'Sede no especificada') AS ciudad_sede,
        dep.nombre AS deporte,
        di.nombre AS disciplina,
        ev.nombre AS evento,
        a.nombre AS atleta,
        ISNULL(p.equipo, N'Individual') AS equipo,
        p.posicion,
        ISNULL(p.medalla, N'Sin Medalla') AS medalla,
        ISNULL(p.estado_resultado, N'Finished') AS estado_resultado
    FROM olympics.PARTICIPACION p
    JOIN olympics.NOC n ON n.id_noc = p.id_noc
    JOIN olympics.ATLETA a ON a.id_atleta = p.id_atleta
    JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
    LEFT JOIN olympics.SEDE s ON s.id_sede = eo.id_sede
    JOIN olympics.EVENTO ev ON ev.id_evento = p.id_evento
    JOIN olympics.DISCIPLINA di ON di.id_disciplina = ev.id_disciplina
    JOIN olympics.DEPORTE dep ON dep.id_deporte = di.id_deporte
    WHERE n.id_entidad = @id_entidad
      AND (@anio IS NULL OR eo.anio = @anio)
      AND (@temporada IS NULL OR eo.temporada = @temporada)
      AND (@deporte IS NULL OR dep.nombre LIKE '%' + @deporte + '%')
    ORDER BY 
        CASE p.medalla 
            WHEN N'Gold' THEN 1 
            WHEN N'Silver' THEN 2 
            WHEN N'Bronze' THEN 3 
            ELSE 4 
        END ASC,
        eo.anio DESC,
        dep.nombre ASC,
        ev.nombre ASC;

END;
GO

PRINT N'Procedimiento almacenado olympics.sp_consultar_pais creado/actualizado exitosamente.';
GO
