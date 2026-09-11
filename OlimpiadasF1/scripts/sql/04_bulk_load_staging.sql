/* Bloque 6 — carga UTF-8 de los diez CSV finales al staging. */
USE OlimpiadasDB;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF EXISTS
(
    SELECT 1 FROM stg.ENTIDAD_GEOGRAFICA UNION ALL SELECT 1 FROM stg.POBLACION
    UNION ALL SELECT 1 FROM stg.NOC UNION ALL SELECT 1 FROM stg.ATLETA
    UNION ALL SELECT 1 FROM stg.SEDE UNION ALL SELECT 1 FROM stg.EDICION_OLIMPICA
    UNION ALL SELECT 1 FROM stg.DEPORTE UNION ALL SELECT 1 FROM stg.DISCIPLINA
    UNION ALL SELECT 1 FROM stg.EVENTO UNION ALL SELECT 1 FROM stg.PARTICIPACION
)
    THROW 51001, N'Abortado: staging ya contiene filas. No se duplicará la carga.', 1;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    BULK INSERT stg.ENTIDAD_GEOGRAFICA
    FROM '/var/opt/mssql/import/processed/entidad_geografica.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.POBLACION
    FROM '/var/opt/mssql/import/processed/poblacion.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.NOC
    FROM '/var/opt/mssql/import/processed/noc.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.ATLETA
    FROM '/var/opt/mssql/import/processed/atleta.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0d0a', TABLOCK);
    BULK INSERT stg.SEDE
    FROM '/var/opt/mssql/import/processed/sede.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.EDICION_OLIMPICA
    FROM '/var/opt/mssql/import/processed/edicion_olimpica.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0d0a', TABLOCK);
    BULK INSERT stg.DEPORTE
    FROM '/var/opt/mssql/import/processed/deporte.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.DISCIPLINA
    FROM '/var/opt/mssql/import/processed/disciplina.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0a', TABLOCK);
    BULK INSERT stg.EVENTO
    FROM '/var/opt/mssql/import/processed/evento.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0d0a', TABLOCK);
    BULK INSERT stg.PARTICIPACION
    FROM '/var/opt/mssql/import/processed/participacion.csv'
    WITH (FORMAT = 'CSV', FIELDQUOTE = '"', FIRSTROW = 2, ROWTERMINATOR = '0x0d0a', TABLOCK);

    /* Los archivos fueron generados con CRLF; SQL Server Linux usa 0x0a como
       terminador y deja CR en el último campo. Se elimina únicamente ese
       carácter de transporte dentro de staging, nunca en data/processed. */
    UPDATE stg.ENTIDAD_GEOGRAFICA SET codigo_pais=REPLACE(codigo_pais,NCHAR(13),N'');
    UPDATE stg.POBLACION SET poblacion=REPLACE(poblacion,NCHAR(13),N'');
    UPDATE stg.NOC SET notas=REPLACE(notas,NCHAR(13),N'');
    UPDATE stg.ATLETA SET longitud=REPLACE(longitud,NCHAR(13),N'');
    UPDATE stg.SEDE SET id_pais=REPLACE(id_pais,NCHAR(13),N'');
    UPDATE stg.EDICION_OLIMPICA SET id_sede=REPLACE(id_sede,NCHAR(13),N'');
    UPDATE stg.DEPORTE SET nombre=REPLACE(nombre,NCHAR(13),N'');
    UPDATE stg.DISCIPLINA SET nombre=REPLACE(nombre,NCHAR(13),N'');
    UPDATE stg.EVENTO SET nombre=REPLACE(nombre,NCHAR(13),N'');
    UPDATE stg.PARTICIPACION SET medalla=REPLACE(medalla,NCHAR(13),N'');

    /* Algunas columnas ID fueron serializadas como texto integral con .0.
       Se normaliza solo ese sufijo en staging; una fracción distinta no se
       modifica y será rechazada por 05_validate_staging.sql. */
    UPDATE stg.ENTIDAD_GEOGRAFICA SET id_entidad=LEFT(id_entidad,LEN(id_entidad)-2) WHERE RIGHT(id_entidad,2)=N'.0';
    UPDATE stg.POBLACION SET id_entidad=CASE WHEN RIGHT(id_entidad,2)=N'.0' THEN LEFT(id_entidad,LEN(id_entidad)-2) ELSE id_entidad END, anio=CASE WHEN RIGHT(anio,2)=N'.0' THEN LEFT(anio,LEN(anio)-2) ELSE anio END WHERE RIGHT(id_entidad,2)=N'.0' OR RIGHT(anio,2)=N'.0';
    UPDATE stg.NOC SET id_noc=CASE WHEN RIGHT(id_noc,2)=N'.0' THEN LEFT(id_noc,LEN(id_noc)-2) ELSE id_noc END, id_entidad=CASE WHEN RIGHT(id_entidad,2)=N'.0' THEN LEFT(id_entidad,LEN(id_entidad)-2) ELSE id_entidad END WHERE RIGHT(id_noc,2)=N'.0' OR RIGHT(id_entidad,2)=N'.0';
    UPDATE stg.ATLETA SET id_atleta=CASE WHEN RIGHT(id_atleta,2)=N'.0' THEN LEFT(id_atleta,LEN(id_atleta)-2) ELSE id_atleta END, id_pais_nacimiento=CASE WHEN RIGHT(id_pais_nacimiento,2)=N'.0' THEN LEFT(id_pais_nacimiento,LEN(id_pais_nacimiento)-2) ELSE id_pais_nacimiento END, id_pais_nacionalidad=CASE WHEN RIGHT(id_pais_nacionalidad,2)=N'.0' THEN LEFT(id_pais_nacionalidad,LEN(id_pais_nacionalidad)-2) ELSE id_pais_nacionalidad END, id_pais_fallecimiento=CASE WHEN RIGHT(id_pais_fallecimiento,2)=N'.0' THEN LEFT(id_pais_fallecimiento,LEN(id_pais_fallecimiento)-2) ELSE id_pais_fallecimiento END WHERE RIGHT(id_atleta,2)=N'.0' OR RIGHT(id_pais_nacimiento,2)=N'.0' OR RIGHT(id_pais_nacionalidad,2)=N'.0' OR RIGHT(id_pais_fallecimiento,2)=N'.0';
    UPDATE stg.SEDE SET id_sede=CASE WHEN RIGHT(id_sede,2)=N'.0' THEN LEFT(id_sede,LEN(id_sede)-2) ELSE id_sede END, id_pais=CASE WHEN RIGHT(id_pais,2)=N'.0' THEN LEFT(id_pais,LEN(id_pais)-2) ELSE id_pais END WHERE RIGHT(id_sede,2)=N'.0' OR RIGHT(id_pais,2)=N'.0';
    UPDATE stg.EDICION_OLIMPICA SET id_edicion=CASE WHEN RIGHT(id_edicion,2)=N'.0' THEN LEFT(id_edicion,LEN(id_edicion)-2) ELSE id_edicion END, anio=CASE WHEN RIGHT(anio,2)=N'.0' THEN LEFT(anio,LEN(anio)-2) ELSE anio END, id_sede=CASE WHEN RIGHT(id_sede,2)=N'.0' THEN LEFT(id_sede,LEN(id_sede)-2) ELSE id_sede END WHERE RIGHT(id_edicion,2)=N'.0' OR RIGHT(anio,2)=N'.0' OR RIGHT(id_sede,2)=N'.0';
    UPDATE stg.DEPORTE SET id_deporte=CASE WHEN RIGHT(id_deporte,2)=N'.0' THEN LEFT(id_deporte,LEN(id_deporte)-2) ELSE id_deporte END WHERE RIGHT(id_deporte,2)=N'.0';
    UPDATE stg.DISCIPLINA SET id_disciplina=CASE WHEN RIGHT(id_disciplina,2)=N'.0' THEN LEFT(id_disciplina,LEN(id_disciplina)-2) ELSE id_disciplina END, id_deporte=CASE WHEN RIGHT(id_deporte,2)=N'.0' THEN LEFT(id_deporte,LEN(id_deporte)-2) ELSE id_deporte END WHERE RIGHT(id_disciplina,2)=N'.0' OR RIGHT(id_deporte,2)=N'.0';
    UPDATE stg.EVENTO SET id_evento=CASE WHEN RIGHT(id_evento,2)=N'.0' THEN LEFT(id_evento,LEN(id_evento)-2) ELSE id_evento END, id_disciplina=CASE WHEN RIGHT(id_disciplina,2)=N'.0' THEN LEFT(id_disciplina,LEN(id_disciplina)-2) ELSE id_disciplina END WHERE RIGHT(id_evento,2)=N'.0' OR RIGHT(id_disciplina,2)=N'.0';
    UPDATE stg.PARTICIPACION SET id_participacion=CASE WHEN RIGHT(id_participacion,2)=N'.0' THEN LEFT(id_participacion,LEN(id_participacion)-2) ELSE id_participacion END, id_atleta=CASE WHEN RIGHT(id_atleta,2)=N'.0' THEN LEFT(id_atleta,LEN(id_atleta)-2) ELSE id_atleta END, id_edicion=CASE WHEN RIGHT(id_edicion,2)=N'.0' THEN LEFT(id_edicion,LEN(id_edicion)-2) ELSE id_edicion END, id_evento=CASE WHEN RIGHT(id_evento,2)=N'.0' THEN LEFT(id_evento,LEN(id_evento)-2) ELSE id_evento END, id_noc=CASE WHEN RIGHT(id_noc,2)=N'.0' THEN LEFT(id_noc,LEN(id_noc)-2) ELSE id_noc END, id_pais_nacionalidad=CASE WHEN RIGHT(id_pais_nacionalidad,2)=N'.0' THEN LEFT(id_pais_nacionalidad,LEN(id_pais_nacionalidad)-2) ELSE id_pais_nacionalidad END, posicion=CASE WHEN RIGHT(posicion,2)=N'.0' THEN LEFT(posicion,LEN(posicion)-2) ELSE posicion END WHERE RIGHT(id_participacion,2)=N'.0' OR RIGHT(id_atleta,2)=N'.0' OR RIGHT(id_edicion,2)=N'.0' OR RIGHT(id_evento,2)=N'.0' OR RIGHT(id_noc,2)=N'.0' OR RIGHT(id_pais_nacionalidad,2)=N'.0' OR RIGHT(posicion,2)=N'.0';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

PRINT N'04_bulk_load_staging.sql finalizado. Se cargaron los diez CSV en stg; no se insertó en olympics.';
GO
