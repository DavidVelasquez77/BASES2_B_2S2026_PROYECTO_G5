/* Inciso d) Stored procedure por atleta - Grupo 7
   Solo lectura. No escribe datos ni altera el modelo. Usa solo el schema olympics.
   Devuelve 3 result sets: ficha, medallero y detalle de participaciones.
   Si la busqueda es ambigua o vacia, devuelve un solo result set informativo.
   Las decisiones de diseno estan explicadas en documentacion_d.md */

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
    @temporada           NVARCHAR(30)  = NULL,   -- 5 valores, ver documentacion_d.md 4.8
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

    IF @max_atletas IS NULL OR @max_atletas < 1
        SET @max_atletas = 25;

    /* Mejor un error claro que un resultado vacio que parezca "no tiene medallas". */
    IF @medalla IS NOT NULL
       AND @medalla COLLATE Latin1_General_CI_AI NOT IN (N'Gold', N'Silver', N'Bronze')
    BEGIN
        RAISERROR(N'@medalla debe ser Gold, Silver o Bronze, o NULL para todas.', 16, 1);
        RETURN;
    END;

    IF @anio_desde IS NOT NULL AND @anio_hasta IS NOT NULL
       AND @anio_desde > @anio_hasta
    BEGIN
        RAISERROR(N'@anio_desde no puede ser mayor que @anio_hasta.', 16, 1);
        RETURN;
    END;

    DECLARE @busqueda NVARCHAR(250) = LTRIM(RTRIM(ISNULL(@nombre_atleta, N'')));

    /* Se escapan los comodines para que un '%' escrito por el usuario
       se busque literal y no devuelva la tabla completa. */
    DECLARE @patron NVARCHAR(260) =
        N'%' + REPLACE(REPLACE(REPLACE(@busqueda, N'[', N'[[]'),
                               N'%', N'[%]'),
                       N'_', N'[_]') + N'%';

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
       PARTICIPACION.id_pais_nacionalidad esta casi siempre en NULL. */

    SELECT
        p.id_participacion,
        p.id_atleta,
        eo.anio,
        eo.temporada,
        s.nombre        AS sede,
        dep.nombre      AS deporte,
        dis.id_disciplina,
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
      AND (@deporte    IS NULL OR dep.nombre   COLLATE Latin1_General_CI_AI LIKE N'%' + @deporte + N'%')
      AND (@medalla    IS NULL OR p.medalla    COLLATE Latin1_General_CI_AI = @medalla)
      AND (@pais       IS NULL
           OR n.codigo_noc COLLATE Latin1_General_CI_AI = @pais
           OR n.nombre_noc COLLATE Latin1_General_CI_AI LIKE N'%' + @pais + N'%'
           OR eg.nombre    COLLATE Latin1_General_CI_AI LIKE N'%' + @pais + N'%')
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
       Hay 49,869 nombres repetidos entre atletas distintos. Si la busqueda
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
        ORDER BY medallas DESC, participaciones DESC, a.nombre;

        RETURN;
    END;

    /* ---------- 5. Agrupamiento para descontar duplicados ----------
       La base trae la misma participacion bajo dos nomenclaturas de evento:
       una fila con posicion y otra con edad. Si un grupo tiene n filas con
       posicion y n con edad, el conteo real es n. Detalle en documentacion_d.md 5.1.
       Se incluyen las filas sin medalla porque la firma aplica igual. */

    SELECT
        x.id_atleta,
        x.medalla,
        COUNT(*)                                                AS filas,
        SUM(CASE WHEN x.posicion IS NOT NULL THEN 1 ELSE 0 END) AS con_posicion,
        SUM(CASE WHEN x.edad     IS NOT NULL THEN 1 ELSE 0 END) AS con_edad
    INTO #grupos
    FROM #part x
    GROUP BY x.id_atleta, x.anio, x.id_disciplina, x.medalla;

    /* Estimado por grupo. Si la firma no concluye se deja el crudo y se marca. */
    SELECT
        id_atleta,
        medalla,
        filas,
        CASE WHEN con_posicion > 0 AND con_edad > 0 AND con_posicion = con_edad
             THEN con_posicion
             ELSE filas
        END AS estimado,
        CASE WHEN (con_posicion > 0 AND con_edad > 0 AND con_posicion <> con_edad)
               OR (con_posicion = 0 AND con_edad = 0 AND filas > 1)
             THEN 1 ELSE 0
        END AS indeterminado
    INTO #est
    FROM #grupos;

    /* ---------- Result set 1: ficha del atleta ----------
       Las cantidades van en crudo y estimado. ediciones y deportes no
       necesitan correccion porque usan COUNT(DISTINCT). */

    SELECT
        a.id_atleta,
        a.nombre,
        /* nombre_completo trae un separador U+2022; se limpia solo al mostrar. */
        LTRIM(RTRIM(REPLACE(a.nombre_completo, NCHAR(8226), N' '))) AS nombre_completo,
        /* sexo no quedo homologado en la carga: conviven M/Male y F/Female. */
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
        /* crudo */
        COUNT(x.id_participacion)                   AS participaciones,
        SUM(CASE WHEN x.medalla IS NOT NULL THEN 1 ELSE 0 END) AS total_medallas,
        /* estimado */
        ISNULL(r.part_est, 0)                       AS participaciones_estimado,
        ISNULL(r.med_est,  0)                       AS total_medallas_estimado,
        COUNT(DISTINCT x.anio)                      AS ediciones,
        COUNT(DISTINCT x.deporte)                   AS deportes,
        MIN(x.anio)                                 AS primer_ano,
        MAX(x.anio)                                 AS ultimo_ano
    FROM olympics.ATLETA a
    INNER JOIN #atletas fa                    ON fa.id_atleta  = a.id_atleta
    LEFT  JOIN olympics.ENTIDAD_GEOGRAFICA pn ON pn.id_entidad = a.id_pais_nacimiento
    LEFT  JOIN olympics.ENTIDAD_GEOGRAFICA pf ON pf.id_entidad = a.id_pais_fallecimiento
    LEFT  JOIN #part x                        ON x.id_atleta   = a.id_atleta
    LEFT  JOIN
    (
        SELECT
            id_atleta,
            SUM(estimado)                                             AS part_est,
            SUM(CASE WHEN medalla IS NOT NULL THEN estimado ELSE 0 END) AS med_est
        FROM #est
        GROUP BY id_atleta
    ) r                                       ON r.id_atleta   = a.id_atleta
    GROUP BY
        a.id_atleta, a.nombre, a.nombre_completo, a.sexo, a.fecha_nacimiento,
        a.ciudad_nacimiento, a.region_nacimiento, pn.nombre,
        a.fecha_fallecimiento, pf.nombre, a.altura_cm, a.peso_kg,
        r.part_est, r.med_est
    ORDER BY total_medallas DESC, participaciones DESC, a.nombre;

    /* ---------- Result set 2: medallero ----------
       Crudo y estimado lado a lado. El crudo nunca se altera y la columna
       diagnostico dice que se detecto. Cobertura del metodo en documentacion_d.md 5.1. */

    WITH estimado AS
    (
        /* Solo los grupos con medalla. */
        SELECT
            id_atleta,
            SUM(CASE WHEN medalla = N'Gold'   THEN estimado ELSE 0 END) AS oro_est,
            SUM(CASE WHEN medalla = N'Silver' THEN estimado ELSE 0 END) AS plata_est,
            SUM(CASE WHEN medalla = N'Bronze' THEN estimado ELSE 0 END) AS bronce_est,
            SUM(estimado)                                               AS total_est,
            SUM(indeterminado)                                          AS indet
        FROM #est
        WHERE medalla IS NOT NULL
        GROUP BY id_atleta
    )
    SELECT
        a.id_atleta,
        a.nombre,
        /* crudo */
        SUM(CASE WHEN x.medalla = N'Gold'   THEN 1 ELSE 0 END) AS oro,
        SUM(CASE WHEN x.medalla = N'Silver' THEN 1 ELSE 0 END) AS plata,
        SUM(CASE WHEN x.medalla = N'Bronze' THEN 1 ELSE 0 END) AS bronce,
        SUM(CASE WHEN x.medalla IS NOT NULL THEN 1 ELSE 0 END) AS total_medallas,
        /* estimado */
        ISNULL(e.oro_est,    0)                                AS oro_estimado,
        ISNULL(e.plata_est,  0)                                AS plata_estimado,
        ISNULL(e.bronce_est, 0)                                AS bronce_estimado,
        ISNULL(e.total_est,  0)                                AS total_estimado,
        CASE WHEN ISNULL(e.indet, 0) > 0
             THEN N'parcial: ' + CAST(e.indet AS NVARCHAR(10)) + N' grupo(s) indeterminado(s)'
             WHEN ISNULL(e.total_est, 0) = 0                   THEN N'sin medallas'
             WHEN e.total_est < SUM(CASE WHEN x.medalla IS NOT NULL THEN 1 ELSE 0 END)
                                                               THEN N'duplicado detectado y descontado'
             ELSE N'sin duplicados detectados'
        END                                                    AS diagnostico,
        /* otros estados */
        SUM(CASE WHEN x.medalla IS NULL
                  AND x.estado_resultado IS NULL
                  AND x.posicion IS NOT NULL THEN 1 ELSE 0 END) AS sin_medalla_con_posicion,
        SUM(CASE WHEN x.estado_resultado = N'DNF' THEN 1 ELSE 0 END) AS dnf,
        SUM(CASE WHEN x.estado_resultado = N'DNS' THEN 1 ELSE 0 END) AS dns,
        SUM(CASE WHEN x.estado_resultado = N'DQ'  THEN 1 ELSE 0 END) AS dq
    FROM olympics.ATLETA a
    INNER JOIN #atletas fa ON fa.id_atleta = a.id_atleta
    LEFT  JOIN #part x     ON x.id_atleta  = a.id_atleta
    LEFT  JOIN estimado e  ON e.id_atleta  = a.id_atleta
    GROUP BY a.id_atleta, a.nombre,
             e.oro_est, e.plata_est, e.bronce_est, e.total_est, e.indet
    ORDER BY total_medallas DESC, a.nombre;

    /* ---------- Result set 3: detalle de participaciones ----------
       Fiel al dato: no fusiona las filas duplicadas.
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
