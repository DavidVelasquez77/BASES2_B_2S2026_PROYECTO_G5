/* ============================================================================
   Fase 2 - Validacion 03: alerta de integridad posterior a la restauracion
   (cubre el alcance opcional "crear alertas de validacion de integridad")

   Una restauracion que termina sin error no garantiza que los datos esten
   completos y coherentes. Este script comprueba tres cosas distintas y, si
   alguna falla, corta con RAISERROR de severidad 16 para que la falla sea
   visible y detenga un script encadenado en vez de pasar inadvertida.

     1. Conteos   comparados contra el valor esperado que se pasa por
                  parametro (el que se registro antes de eliminar la base).
     2. Huerfanos revisa que ninguna fila de PARTICIPACION apunte a un atleta,
                  edicion, evento o NOC que no exista. Una restauracion
                  parcial rompe esto aunque los conteos parezcan altos.
     3. DBCC      CHECKDB verifica la consistencia fisica y logica de las
                  paginas de la base.

   Parametros:
     DB           nombre de la base
     ESP_ATLETAS  cantidad esperada de filas en ATLETA
     ESP_PART     cantidad esperada de filas en PARTICIPACION

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -v ESP_ATLETAS="26621" -v ESP_PART="43547" \
            -i 03_alerta_integridad.sql

   El codigo de salida de sqlcmd es distinto de cero si se dispara la alerta,
   asi que sirve igual dentro de un script automatizado.
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
GO

DECLARE @atletas      BIGINT = (SELECT COUNT(*) FROM olympics.ATLETA);
DECLARE @part         BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION);
DECLARE @esp_atletas  BIGINT = CAST(N'$(ESP_ATLETAS)' AS BIGINT);
DECLARE @esp_part     BIGINT = CAST(N'$(ESP_PART)'    AS BIGINT);

/* ---------- 1. Conteos contra lo esperado ---------- */
SELECT
    N'ATLETA'                                                  AS tabla,
    @atletas                                                   AS filas_encontradas,
    @esp_atletas                                               AS filas_esperadas,
    CASE WHEN @atletas = @esp_atletas THEN N'OK' ELSE N'ALERTA' END AS resultado
UNION ALL
SELECT
    N'PARTICIPACION', @part, @esp_part,
    CASE WHEN @part = @esp_part THEN N'OK' ELSE N'ALERTA' END;

/* ---------- 2. Integridad referencial ---------- */
DECLARE @h_atleta  BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                             WHERE NOT EXISTS (SELECT 1 FROM olympics.ATLETA a
                                               WHERE a.id_atleta = p.id_atleta));
DECLARE @h_edicion BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                             WHERE NOT EXISTS (SELECT 1 FROM olympics.EDICION_OLIMPICA e
                                               WHERE e.id_edicion = p.id_edicion));
DECLARE @h_evento  BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                             WHERE NOT EXISTS (SELECT 1 FROM olympics.EVENTO v
                                               WHERE v.id_evento = p.id_evento));
DECLARE @h_noc     BIGINT = (SELECT COUNT(*) FROM olympics.PARTICIPACION p
                             WHERE p.id_noc IS NOT NULL
                               AND NOT EXISTS (SELECT 1 FROM olympics.NOC n
                                               WHERE n.id_noc = p.id_noc));

SELECT
    @h_atleta   AS huerfanos_atleta,
    @h_edicion  AS huerfanos_edicion,
    @h_evento   AS huerfanos_evento,
    @h_noc      AS huerfanos_noc,
    CASE WHEN @h_atleta + @h_edicion + @h_evento + @h_noc = 0
         THEN N'OK' ELSE N'ALERTA' END AS resultado;

/* ---------- Veredicto ---------- */
DECLARE @fallas INT =
      CASE WHEN @atletas <> @esp_atletas THEN 1 ELSE 0 END
    + CASE WHEN @part    <> @esp_part    THEN 1 ELSE 0 END
    + CASE WHEN @h_atleta + @h_edicion + @h_evento + @h_noc > 0 THEN 1 ELSE 0 END;

IF @fallas > 0
BEGIN
    DECLARE @msg NVARCHAR(500) = CONCAT(
        N'ALERTA DE INTEGRIDAD en $(DB): ', @fallas, N' comprobacion(es) fallaron. ',
        N'Atletas ', @atletas, N'/', @esp_atletas,
        N', participaciones ', @part, N'/', @esp_part,
        N', huerfanos ', @h_atleta + @h_edicion + @h_evento + @h_noc, N'.');
    RAISERROR(@msg, 16, 1);
END
ELSE
    PRINT N'Integridad verificada en $(DB): conteos y referencias correctos a las '
        + CONVERT(NVARCHAR(30), SYSDATETIME(), 121);
GO

/* ---------- 3. Consistencia fisica de la base ---------- */
DBCC CHECKDB ([$(DB)]) WITH NO_INFOMSGS, ALL_ERRORMSGS;
GO

PRINT N'03_alerta_integridad.sql finalizado.';
GO
