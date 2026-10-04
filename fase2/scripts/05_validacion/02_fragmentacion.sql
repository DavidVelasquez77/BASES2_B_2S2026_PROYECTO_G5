/* ============================================================================
   Fase 2 - Validacion 02: nivel de fragmentacion de las tablas

   El enunciado lo pide al final de cada tipo de carga. La fragmentacion
   importa aqui porque las cuatro cargas insertan en lotes sucesivos sobre las
   mismas tablas, y eso desordena las paginas del indice agrupado.

   Parametro:  DB  nombre de la base

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 02_fragmentacion.sql

   Como leer el resultado:
     avg_fragmentation_in_percent  porcentaje de paginas fuera de orden
        < 10 %   aceptable, no se hace nada
       10 - 30 % conviene REORGANIZE
        > 30 %   conviene REBUILD
     page_count   paginas del indice. Por debajo de 1000 paginas el porcentaje
                  es poco representativo y suele ignorarse.

   El modo 'LIMITED' es el que usa menos recursos y basta para este reporte;
   'DETAILED' recorre todas las paginas y bloquea mas tiempo.

   Este script solo mide. No reorganiza ni reconstruye nada, para que la
   comparacion de respaldos se haga sobre el estado real que dejo la carga.
============================================================================ */

USE [$(DB)];
GO

SET NOCOUNT ON;
GO

SELECT
    DB_NAME()      AS base,
    SYSDATETIME()  AS fecha_hora_servidor;
GO

SELECT
    OBJECT_NAME(ips.object_id)                              AS tabla,
    i.name                                                  AS indice,
    i.type_desc                                             AS tipo_indice,
    ips.page_count                                          AS paginas,
    CAST(ips.avg_fragmentation_in_percent AS DECIMAL(5,2))  AS fragmentacion_pct,
    CAST(ips.avg_page_space_used_in_percent AS DECIMAL(5,2)) AS uso_de_pagina_pct,
    CASE
        WHEN ips.page_count < 1000                        THEN 'sin accion (indice pequeno)'
        WHEN ips.avg_fragmentation_in_percent > 30        THEN 'REBUILD recomendado'
        WHEN ips.avg_fragmentation_in_percent >= 10       THEN 'REORGANIZE recomendado'
        ELSE 'sin accion'
    END                                                     AS recomendacion
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') AS ips
JOIN sys.indexes AS i
  ON i.object_id = ips.object_id AND i.index_id = ips.index_id
WHERE OBJECTPROPERTY(ips.object_id, 'IsUserTable') = 1
ORDER BY ips.page_count DESC, tabla;
GO

/* Resumen de una sola linea, util para la tabla comparativa del informe. */
SELECT
    COUNT(*)                                                     AS indices_medidos,
    SUM(ips.page_count)                                          AS paginas_totales,
    CAST(AVG(ips.avg_fragmentation_in_percent) AS DECIMAL(5,2))  AS fragmentacion_promedio_pct,
    CAST(MAX(ips.avg_fragmentation_in_percent) AS DECIMAL(5,2))  AS fragmentacion_maxima_pct
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') AS ips
WHERE OBJECTPROPERTY(ips.object_id, 'IsUserTable') = 1;
GO

PRINT N'02_fragmentacion.sql finalizado.';
GO
