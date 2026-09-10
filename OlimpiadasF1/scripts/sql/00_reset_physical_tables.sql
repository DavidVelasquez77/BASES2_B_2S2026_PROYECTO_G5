/*
    Reset controlado del Bloque 5 para desarrollo vacío.
    Este archivo es deliberadamente separado del DDL principal y elimina
    únicamente las diez tablas explícitas del schema olympics, en orden inverso
    de dependencias. No carga datos ni modifica schemas, RAW o CSV.
*/

USE OlimpiadasDB;
GO

DROP TABLE IF EXISTS olympics.PARTICIPACION;
DROP TABLE IF EXISTS olympics.POBLACION;
DROP TABLE IF EXISTS olympics.EVENTO;
DROP TABLE IF EXISTS olympics.DISCIPLINA;
DROP TABLE IF EXISTS olympics.EDICION_OLIMPICA;
DROP TABLE IF EXISTS olympics.SEDE;
DROP TABLE IF EXISTS olympics.NOC;
DROP TABLE IF EXISTS olympics.ATLETA;
DROP TABLE IF EXISTS olympics.DEPORTE;
DROP TABLE IF EXISTS olympics.ENTIDAD_GEOGRAFICA;
GO

PRINT N'00_reset_physical_tables.sql finalizado. Las diez tablas fueron eliminadas para recreación vacía.';
GO
