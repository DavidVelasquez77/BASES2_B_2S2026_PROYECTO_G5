/* Inciso d) Stored procedure por atleta - Grupo 7
   Solo lectura. No escribe datos ni altera el modelo. Usa solo el schema olympics.
   Devuelve 3 result sets: ficha, medallero y detalle de participaciones.
   Si la busqueda es ambigua o vacia, devuelve un solo result set informativo.

   Las metricas salen directamente de PARTICIPACION, que es la fuente canonica.
   El SP no deduplica: esa tarea pertenece al ETL y ya fue resuelta ahi.

   Decisiones de diseno explicadas en documentacion_d.md */

USE OlimpiadasDB;
GO

CREATE OR ALTER PROCEDURE olympics.sp_historial_atleta
    /* Parametro 1, obligatorio por enunciado: nombre del atleta.
       Busqueda parcial, sin distinguir mayusculas ni acentos. */
    @nombre_atleta       NVARCHAR(250),

    /* Filtros que menciona el enunciado */
    @deporte             NVARCHAR(150) = NULL,   -- coincidencia parcial
    @pais                NVARCHAR(150) = NULL,   -- codigo NOC, nombre NOC o pais
    @anio                SMALLINT      = NULL,   -- ano exacto

    /* Rango de anos y tipo de medalla */
    @anio_desde          SMALLINT      = NULL,   -- rango inclusivo
    @anio_hasta          SMALLINT      = NULL,
    @medalla             NVARCHAR(20)  = NULL,   -- Gold | Silver | Bronze

    /* Filtros propios */
    @temporada           NVARCHAR(30)  = NULL,   -- uno de los 5 valores validos
    @solo_medallistas    BIT           = 0,      -- 1 = solo filas con medalla
    @coincidencia_exacta BIT           = 0,      -- 1 = nombre exacto
    @id_atleta           BIGINT        = NULL,   -- desempate por id
    @max_atletas         INT           = 25      -- tope antes de declarar ambiguedad
AS
BEGIN
    SET NOCOUNT ON;

    /* ---------- 1. Validacion de parametros ---------- */

    IF @id_atleta IS NULL
       AND (@nombre_atleta IS NULL OR LTRIM(RTRIM(@nombre_atleta)) = N'')
    BEGIN
        RAISERROR(N'Debe indicar el nombre del atleta en el primer parametro, o bien un @id_atleta.',
                  16, 1);
        RETURN;
    END;

    /* @max_atletas se normaliza y se acota por arriba para no devolver
       listas de candidatos inmanejables. */
    IF @max_atletas IS NULL OR @max_atletas < 1
        SET @max_atletas = 25;
    IF @max_atletas > 500
        SET @max_atletas = 500;

    /* Mejor un error claro que un resultado vacio que parezca "no tiene medallas". */
    IF @medalla IS NOT NULL
       AND @medalla COLLATE Latin1_General_CI_AI NOT IN (N'Gold', N'Silver', N'Bronze')
    BEGIN
        RAISERROR(N'@medalla debe ser Gold, Silver o Bronze, o NULL para todas.', 16, 1);
        RETURN;
    END;

    /* EDICION_OLIMPICA.temporada tiene exactamente estos cinco valores. */
    IF @temporada IS NOT NULL
       AND @temporada COLLATE Latin1_General_CI_AI NOT IN
           (N'Summer', N'Winter', N'Summer Youth', N'Winter Youth', N'Intercalated Games')
    BEGIN
        RAISERROR(N'@temporada debe ser Summer, Winter, Summer Youth, Winter Youth o Intercalated Games, o NULL para todas.',
                  16, 1);
        RETURN;
    END;

    IF @anio_desde IS NOT NULL AND @anio_hasta IS NOT NULL
       AND @anio_desde > @anio_hasta
    BEGIN
        RAISERROR(N'@anio_desde no puede ser mayor que @anio_hasta.', 16, 1);
        RETURN;
    END;

    DECLARE @busqueda NVARCHAR(250) = LTRIM(RTRIM(ISNULL(@nombre_atleta, N'')));

    /* Se escapan los comodines en todos los filtros parciales para que el texto
       del usuario se busque literal: un '%' no debe traer la tabla completa. */
    DECLARE @patron NVARCHAR(260) =
        N'%' + REPLACE(REPLACE(REPLACE(@busqueda, N'[', N'[[]'),
                               N'%', N'[%]'),
                       N'_', N'[_]') + N'%';

    DECLARE @patron_deporte NVARCHAR(170) =
        CASE WHEN @deporte IS NULL THEN NULL
             ELSE N'%' + REPLACE(REPLACE(REPLACE(@deporte, N'[', N'[[]'),
                                         N'%', N'[%]'),
                                 N'_', N'[_]') + N'%' END;

    DECLARE @patron_pais NVARCHAR(170) =
        CASE WHEN @pais IS NULL THEN NULL
             ELSE N'%' + REPLACE(REPLACE(REPLACE(@pais, N'[', N'[[]'),
                                         N'%', N'[%]'),
                                 N'_', N'[_]') + N'%' END;

    /* ---------- 2. Atletas que coinciden ----------
       Se fuerza Latin1_General_CI_AI porque la colacion de la base distingue
       acentos: sin esto, "Elie" no encuentra a "Elie" con E acentuada. */

    CREATE TABLE #atletas (id_atleta BIGINT NOT NULL PRIMARY KEY);

    IF @id_atleta IS NOT NULL
    BEGIN
        INSERT INTO #atletas (id_atleta)
        SELECT a.id_atleta
        FROM olympics.ATLETA a
        WHERE a.id_atleta = @id_atleta;
    END
    ELSE IF @coincidencia_exacta = 1
    BEGIN
        INSERT INTO #atletas (id_atleta)
        SELECT a.id_atleta
        FROM olympics.ATLETA a
        WHERE a.nombre          COLLATE Latin1_General_CI_AI = @busqueda
           OR a.nombre_completo COLLATE Latin1_General_CI_AI = @busqueda
           OR a.nombre_usado    COLLATE Latin1_General_CI_AI = @busqueda;
    END
    ELSE
    BEGIN
        INSERT INTO #atletas (id_atleta)
        SELECT a.id_atleta
        FROM olympics.ATLETA a
        WHERE a.nombre          COLLATE Latin1_General_CI_AI LIKE @patron
           OR a.nombre_completo COLLATE Latin1_General_CI_AI LIKE @patron
           OR a.nombre_usado    COLLATE Latin1_General_CI_AI LIKE @patron;
    END;

    IF NOT EXISTS (SELECT 1 FROM #atletas)
    BEGIN
        SELECT N'SIN COINCIDENCIAS'                                        AS resultado,
               @busqueda                                                   AS texto_buscado,
               N'Revise la escritura, o use @coincidencia_exacta = 0 para busqueda parcial.'
                                                                           AS sugerencia;
        RETURN;
    END;

    /* ---------- 3. Participaciones filtradas ----------
       El pais se resuelve por NOC representado porque
       PARTICIPACION.id_pais_nacionalidad es nullable y esta casi siempre vacio. */

    SELECT
        p.id_participacion,
        p.id_atleta,
        eo.anio,
        eo.temporada,
        s.nombre        AS sede,
        dep.nombre      AS deporte,
        dis.nombre      AS disciplina,
        ev.nombre       AS evento,
        n.codigo_noc,
        n.nombre_noc,
        eg.nombre       AS pais_representado,
        p.equipo,
        p.nombre_competencia,
        p.edad,
        p.altura_cm_registrada,
        p.peso_kg_registrado,
        p.posicion,
        p.empatado,
        p.estado_resultado,
        p.medalla
    INTO #part
    FROM olympics.PARTICIPACION p
    INNER JOIN #atletas fa                   ON fa.id_atleta    = p.id_atleta
    INNER JOIN olympics.EDICION_OLIMPICA eo  ON eo.id_edicion   = p.id_edicion
    INNER JOIN olympics.EVENTO ev            ON ev.id_evento    = p.id_evento
    INNER JOIN olympics.DISCIPLINA dis       ON dis.id_disciplina = ev.id_disciplina
    INNER JOIN olympics.DEPORTE dep          ON dep.id_deporte  = dis.id_deporte
    LEFT  JOIN olympics.SEDE s               ON s.id_sede       = eo.id_sede
    LEFT  JOIN olympics.NOC n                ON n.id_noc        = p.id_noc
    LEFT  JOIN olympics.ENTIDAD_GEOGRAFICA eg ON eg.id_entidad  = n.id_entidad
    WHERE (@anio       IS NULL OR eo.anio  = @anio)
      AND (@anio_desde IS NULL OR eo.anio >= @anio_desde)
      AND (@anio_hasta IS NULL OR eo.anio <= @anio_hasta)
      AND (@temporada  IS NULL OR eo.temporada COLLATE Latin1_General_CI_AI = @temporada)
      AND (@deporte    IS NULL OR dep.nombre   COLLATE Latin1_General_CI_AI LIKE @patron_deporte)
      AND (@medalla    IS NULL OR p.medalla    COLLATE Latin1_General_CI_AI = @medalla)
      AND (@pais       IS NULL
           OR n.codigo_noc COLLATE Latin1_General_CI_AI = @pais
           OR n.nombre_noc COLLATE Latin1_General_CI_AI LIKE @patron_pais
           OR eg.nombre    COLLATE Latin1_General_CI_AI LIKE @patron_pais)
      AND (@solo_medallistas = 0 OR p.medalla IS NOT NULL);

    /* Con filtros, se descartan los atletas que no dejaron ninguna fila.
       Sin filtros se conservan todos, incluso los que no tienen participaciones. */
    DECLARE @hay_filtros BIT =
        CASE WHEN @deporte     IS NULL AND @pais       IS NULL AND @anio IS NULL
                  AND @temporada  IS NULL AND @medalla IS NULL
                  AND @anio_desde IS NULL AND @anio_hasta IS NULL
                  AND @solo_medallistas = 0
             THEN 0 ELSE 1 END;

    IF @hay_filtros = 1
        DELETE FROM #atletas
        WHERE id_atleta NOT IN (SELECT id_atleta FROM #part);

    /* Se devuelven los filtros aplicados para distinguir este caso
       de "el atleta no existe". */
    IF NOT EXISTS (SELECT 1 FROM #atletas)
    BEGIN
        SELECT N'SIN RESULTADOS CON LOS FILTROS APLICADOS' AS resultado,
               @busqueda   AS texto_buscado,
               @deporte    AS f_deporte,
               @pais       AS f_pais,
               @anio       AS f_anio,
               @anio_desde AS f_anio_desde,
               @anio_hasta AS f_anio_hasta,
               @temporada  AS f_temporada,
               @medalla    AS f_medalla,
               @solo_medallistas AS f_solo_medallistas;
        RETURN;
    END;

    /* ---------- 4. Control de ambiguedad ----------
       Hay 48,370 nombres repetidos entre atletas distintos. Si la busqueda
       trae demasiados, se devuelve la lista de candidatos en vez del detalle. */

    DECLARE @n_atletas INT = (SELECT COUNT(*) FROM #atletas);

    IF @n_atletas > @max_atletas
    BEGIN
        SELECT N'BUSQUEDA AMBIGUA'                                            AS resultado,
               @busqueda                                                      AS texto_buscado,
               @n_atletas                                                     AS atletas_encontrados,
               @max_atletas                                                   AS tope_actual,
               N'Refine el nombre, use @id_atleta, o suba @max_atletas.'      AS sugerencia;

        SELECT TOP (200)
               a.id_atleta,
               a.nombre,
               CASE WHEN a.sexo IN (N'M', N'Male')   THEN N'Male'
                    WHEN a.sexo IN (N'F', N'Female') THEN N'Female'
                    ELSE a.sexo END                                AS sexo,
               a.fecha_nacimiento,
               (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                 WHERE p.id_atleta = a.id_atleta)                             AS participaciones,
               (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                 WHERE p.id_atleta = a.id_atleta AND p.medalla IS NOT NULL)   AS medallas
        FROM olympics.ATLETA a
        INNER JOIN #atletas fa ON fa.id_atleta = a.id_atleta
        ORDER BY medallas DESC, participaciones DESC, a.nombre, a.id_atleta;

        RETURN;
    END;

    /* ---------- Result set 1: ficha del atleta ---------- */

    SELECT
        a.id_atleta,
        a.nombre,
        /* nombre_completo trae un separador U+2022; se limpia solo al mostrar. */
        LTRIM(RTRIM(REPLACE(a.nombre_completo, NCHAR(8226), N' '))) AS nombre_completo,
        /* sexo convive como M/Male y F/Female; se unifica solo en la salida. */
        CASE WHEN a.sexo IN (N'M', N'Male')   THEN N'Male'
             WHEN a.sexo IN (N'F', N'Female') THEN N'Female'
             ELSE a.sexo END                                AS sexo,
        a.sexo                                              AS sexo_original,
        a.fecha_nacimiento,
        a.ciudad_nacimiento,
        a.region_nacimiento,
        pn.nombre                                   AS pais_nacimiento,
        a.fecha_fallecimiento,
        pf.nombre                                   AS pais_fallecimiento,
        a.altura_cm,
        a.peso_kg,
        COUNT(x.id_participacion)                   AS participaciones,
        SUM(CASE WHEN x.medalla IS NOT NULL THEN 1 ELSE 0 END) AS total_medallas,
        COUNT(DISTINCT x.anio)                      AS ediciones,
        COUNT(DISTINCT x.deporte)                   AS deportes,
        MIN(x.anio)                                 AS primer_ano,
        MAX(x.anio)                                 AS ultimo_ano
    FROM olympics.ATLETA a
    INNER JOIN #atletas fa                    ON fa.id_atleta  = a.id_atleta
    LEFT  JOIN olympics.ENTIDAD_GEOGRAFICA pn ON pn.id_entidad = a.id_pais_nacimiento
    LEFT  JOIN olympics.ENTIDAD_GEOGRAFICA pf ON pf.id_entidad = a.id_pais_fallecimiento
    LEFT  JOIN #part x                        ON x.id_atleta   = a.id_atleta
    GROUP BY
        a.id_atleta, a.nombre, a.nombre_completo, a.sexo, a.fecha_nacimiento,
        a.ciudad_nacimiento, a.region_nacimiento, pn.nombre,
        a.fecha_fallecimiento, pf.nombre, a.altura_cm, a.peso_kg
    ORDER BY total_medallas DESC, participaciones DESC, a.nombre, a.id_atleta;

    /* ---------- Result set 2: medallero ----------
       Conteo directo sobre las participaciones seleccionadas. */

    SELECT
        a.id_atleta,
        a.nombre,
        SUM(CASE WHEN x.medalla = N'Gold'   THEN 1 ELSE 0 END) AS oro,
        SUM(CASE WHEN x.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata,
        SUM(CASE WHEN x.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronce,
        SUM(CASE WHEN x.medalla IS NOT NULL THEN 1 ELSE 0 END) AS total_medallas,
        /* resultados sin medalla, para leer el historial completo */
        SUM(CASE WHEN x.medalla IS NULL
                  AND x.estado_resultado IS NULL
                  AND x.posicion IS NOT NULL THEN 1 ELSE 0 END) AS sin_medalla_con_posicion,
        SUM(CASE WHEN x.estado_resultado = N'DNF' THEN 1 ELSE 0 END) AS dnf,
        SUM(CASE WHEN x.estado_resultado = N'DNS' THEN 1 ELSE 0 END) AS dns,
        SUM(CASE WHEN x.estado_resultado = N'DQ'  THEN 1 ELSE 0 END) AS dq
    FROM olympics.ATLETA a
    INNER JOIN #atletas fa ON fa.id_atleta = a.id_atleta
    LEFT  JOIN #part x     ON x.id_atleta  = a.id_atleta
    GROUP BY a.id_atleta, a.nombre
    ORDER BY total_medallas DESC, a.nombre, a.id_atleta;

    /* ---------- Result set 3: detalle de participaciones ----------
       Detalle fiel de PARTICIPACION: no agrupa ni filtra filas.
       La columna resultado junta medalla / estado_resultado / posicion
       en un solo campo legible ("=17 lugar" para un empate). */

    SELECT
        /* Con nombres repetidos, sin id_atleta el detalle es ilegible. */
        x.id_atleta,
        a.nombre                                    AS atleta,
        x.anio,
        x.temporada,
        x.sede,
        x.deporte,
        x.disciplina,
        x.evento,
        x.codigo_noc,
        x.pais_representado,
        x.equipo,
        x.edad,
        x.posicion,
        x.empatado,
        x.estado_resultado,
        x.medalla,
        CASE
            WHEN x.medalla          IS NOT NULL THEN x.medalla
            WHEN x.estado_resultado IS NOT NULL THEN x.estado_resultado
            WHEN x.posicion         IS NOT NULL THEN
                 CASE WHEN x.empatado = 1 THEN N'=' ELSE N'' END
                 + CAST(x.posicion AS NVARCHAR(10)) + N' lugar'
            ELSE N'(sin dato de resultado)'
        END                                         AS resultado,
        x.nombre_competencia
    FROM #part x
    INNER JOIN olympics.ATLETA a ON a.id_atleta = x.id_atleta
    ORDER BY a.nombre, x.id_atleta, x.anio, x.deporte, x.disciplina, x.evento;

END;
GO

PRINT N'sp_historial_atleta creado/actualizado correctamente.';
GO
