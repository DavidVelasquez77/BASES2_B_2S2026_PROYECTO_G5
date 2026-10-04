/* ============================================================================
   Fase 2 - DDL 01: creacion de la base de datos

   Crea una base vacia para uno de los tres tipos de carga y le fija el modelo
   de recuperacion. No crea tablas ni carga datos.

   Parametro:  DB  nombre de la base (OlimpiadasF2_Anio, _Deporte, _Deportista)

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 01_crear_base.sql

   Modelo de recuperacion SIMPLE: la estrategia de esta fase es full +
   diferencial, y ninguna de las dos necesita la cadena de log. Con SIMPLE el
   log se trunca solo y no crece sin control. Si se quisieran respaldos de log
   (point-in-time) habria que cambiarlo a FULL.
============================================================================ */

USE master;
GO

IF DB_ID(N'$(DB)') IS NULL
BEGIN
    PRINT N'Creando la base $(DB)...';
    EXEC(N'CREATE DATABASE [$(DB)]');
END
ELSE
    PRINT N'La base $(DB) ya existe; no se vuelve a crear.';
GO

ALTER DATABASE [$(DB)] SET RECOVERY SIMPLE;
GO

USE [$(DB)];
GO

IF SCHEMA_ID(N'olympics') IS NULL
    EXEC(N'CREATE SCHEMA olympics');
GO

SELECT
    DB_NAME()                                         AS base,
    (SELECT recovery_model_desc
       FROM sys.databases WHERE name = DB_NAME())     AS modelo_recuperacion,
    SYSDATETIME()                                     AS momento;
GO

PRINT N'01_crear_base.sql finalizado.';
GO
