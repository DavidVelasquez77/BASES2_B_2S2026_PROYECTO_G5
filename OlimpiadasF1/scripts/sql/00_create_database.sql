USE master;
GO

IF DB_ID('OlimpiadasDB') IS NULL
BEGIN
    CREATE DATABASE OlimpiadasDB;
END;
GO

USE OlimpiadasDB;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'stg'
)
BEGIN
    EXEC('CREATE SCHEMA stg');
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'olympics'
)
BEGIN
    EXEC('CREATE SCHEMA olympics');
END;
GO