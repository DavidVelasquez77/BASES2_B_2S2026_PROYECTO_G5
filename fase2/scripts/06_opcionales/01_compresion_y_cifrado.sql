/* ============================================================================
   Fase 2 - Opcionales 01: compresion y cifrado de los respaldos
   (cubre dos puntos del alcance opcional del enunciado)

   Genera tres versiones del MISMO respaldo completo de una base para poder
   compararlas de forma justa:

     1. sin comprimir            linea base
     2. comprimido               WITH COMPRESSION
     3. comprimido y cifrado     WITH COMPRESSION, ENCRYPTION AES_256

   Al final imprime una tabla con el tamano y la duracion de cada uno, que es
   el insumo del analisis del informe.

   Se usa WITH FORMAT y no solo INIT: un archivo .bak que ya contiene un
   juego de respaldo sin cifrar no admite que se le anexe uno cifrado
   (error 3095). FORMAT rehace el encabezado del medio y hace que el
   script se pueda volver a ejecutar sin borrar archivos a mano.

   Parametro:  DB  nombre de la base

   Uso:
     sqlcmd -S localhost -U sa -P <clave> -C -v DB="OlimpiadasF2_Anio" \
            -i 01_compresion_y_cifrado.sql

   ---------------------------------------------------------------------------
   Sobre el cifrado

   Cifrar un respaldo en SQL Server exige tres cosas en este orden:
     a) una clave maestra en master
     b) un certificado protegido por esa clave
     c) el respaldo hecho WITH ENCRYPTION, apuntando a ese certificado

   Advertencia importante: un respaldo cifrado SOLO se puede restaurar en una
   instancia que tenga el mismo certificado. Si se pierde el certificado, el
   respaldo es irrecuperable. Por eso el script tambien exporta el certificado
   a /var/opt/mssql/fase2/backups/certificado/, que en un entorno real deberia
   guardarse en un lugar distinto al de los respaldos.

   La contrasena de la clave maestra y del certificado se pasan como parametro
   para no dejarlas escritas en el repositorio.
     -v CLAVE_CERT="una-clave-larga"
   ---------------------------------------------------------------------------
============================================================================ */

USE master;
GO

SET NOCOUNT ON;
GO

/* ---------- a) Clave maestra de la instancia ---------- */
IF NOT EXISTS (SELECT 1 FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    EXEC(N'CREATE MASTER KEY ENCRYPTION BY PASSWORD = ''$(CLAVE_CERT)''');
    PRINT N'Clave maestra creada.';
END
ELSE
    PRINT N'La clave maestra ya existe.';
GO

/* ---------- b) Certificado para cifrar respaldos ---------- */
IF NOT EXISTS (SELECT 1 FROM sys.certificates WHERE name = 'CertRespaldosFase2')
BEGIN
    CREATE CERTIFICATE CertRespaldosFase2
        WITH SUBJECT = 'Certificado para cifrar respaldos de la Fase 2',
             EXPIRY_DATE = '2027-12-31';
    PRINT N'Certificado CertRespaldosFase2 creado.';
END
ELSE
    PRINT N'El certificado CertRespaldosFase2 ya existe.';
GO

SELECT name, subject, start_date, expiry_date, pvt_key_encryption_type_desc
FROM sys.certificates WHERE name = 'CertRespaldosFase2';
GO

/* ---------- Los tres respaldos ---------- */
DECLARE @t0 DATETIME2(3), @t1 DATETIME2(3);
DECLARE @ms_plano INT, @ms_comp INT, @ms_cifr INT;

/* 1. sin comprimir */
SET @t0 = SYSDATETIME();
BACKUP DATABASE [$(DB)]
TO DISK = N'/var/opt/mssql/fase2/backups/comparativa_$(DB)_1_plano.bak'
WITH FORMAT, INIT, CHECKSUM, NO_COMPRESSION, NAME = 'Comparativa sin comprimir';
SET @t1 = SYSDATETIME();
SET @ms_plano = DATEDIFF(MILLISECOND, @t0, @t1);

/* 2. comprimido */
SET @t0 = SYSDATETIME();
BACKUP DATABASE [$(DB)]
TO DISK = N'/var/opt/mssql/fase2/backups/comparativa_$(DB)_2_comprimido.bak'
WITH FORMAT, INIT, CHECKSUM, COMPRESSION, NAME = 'Comparativa comprimido';
SET @t1 = SYSDATETIME();
SET @ms_comp = DATEDIFF(MILLISECOND, @t0, @t1);

/* 3. comprimido y cifrado */
SET @t0 = SYSDATETIME();
BACKUP DATABASE [$(DB)]
TO DISK = N'/var/opt/mssql/fase2/backups/comparativa_$(DB)_3_cifrado.bak'
WITH FORMAT, INIT, CHECKSUM, COMPRESSION,
     ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = CertRespaldosFase2),
     NAME = 'Comparativa comprimido y cifrado';
SET @t1 = SYSDATETIME();
SET @ms_cifr = DATEDIFF(MILLISECOND, @t0, @t1);

SELECT N'1. sin comprimir' AS variante, @ms_plano AS duracion_ms
UNION ALL SELECT N'2. comprimido',            @ms_comp
UNION ALL SELECT N'3. comprimido y cifrado',  @ms_cifr;
GO

/* ---------- Comparacion de tamanos y verificacion ---------- */
/* No se usa una columna is_compressed porque no existe en esta version;
   la compresion se deduce de compression_algorithm y del tamano resultante. */
/* msdb conserva el historial de todas las corridas anteriores. Se toma solo
   el respaldo mas reciente de cada archivo para que la tabla del informe
   muestre tres filas y no una por cada vez que se ejecuto el script. */
WITH ultimos AS (
    SELECT
        bmf.physical_device_name,
        bs.compression_algorithm,
        bs.key_algorithm,
        bs.backup_size,
        bs.compressed_backup_size,
        ROW_NUMBER() OVER (PARTITION BY bmf.physical_device_name
                           ORDER BY bs.backup_finish_date DESC) AS rn
    FROM msdb.dbo.backupset bs
    JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id = bs.media_set_id
    WHERE bmf.physical_device_name LIKE '%comparativa_$(DB)%'
)
SELECT
    /* Solo el nombre del archivo, sin la ruta: se corta por la ultima barra. */
    REVERSE(LEFT(REVERSE(physical_device_name),
                 CHARINDEX('/', REVERSE(physical_device_name)) - 1)) AS archivo,
    ISNULL(compression_algorithm, 'ninguno')                         AS compresion,
    ISNULL(key_algorithm, 'no')                                      AS cifrado,
    CAST(backup_size            / 1024.0 / 1024.0 AS DECIMAL(12,2))  AS tamano_datos_mb,
    CAST(compressed_backup_size / 1024.0 / 1024.0 AS DECIMAL(12,2))  AS tamano_archivo_mb,
    CAST(100.0 * (1 - compressed_backup_size * 1.0 / backup_size)
         AS DECIMAL(5,2))                                            AS ahorro_pct
FROM ultimos
WHERE rn = 1
ORDER BY physical_device_name;
GO

/* Los tres deben poder verificarse. El cifrado se verifica solo porque el
   certificado esta presente en esta instancia. */
RESTORE VERIFYONLY FROM DISK = N'/var/opt/mssql/fase2/backups/comparativa_$(DB)_2_comprimido.bak' WITH CHECKSUM;
RESTORE VERIFYONLY FROM DISK = N'/var/opt/mssql/fase2/backups/comparativa_$(DB)_3_cifrado.bak'    WITH CHECKSUM;
GO

/* ---------- Respaldo del certificado ---------- */
/* Sin esto, los respaldos cifrados no se pueden restaurar en otra instancia
   ni despues de recrear el contenedor. */
IF NOT EXISTS (SELECT 1 FROM sys.certificates WHERE name = 'CertRespaldosFase2' AND pvt_key_last_backup_date IS NOT NULL)
BEGIN
    BACKUP CERTIFICATE CertRespaldosFase2
    TO FILE = N'/var/opt/mssql/fase2/backups/certificado/CertRespaldosFase2.cer'
    WITH PRIVATE KEY (
        FILE = N'/var/opt/mssql/fase2/backups/certificado/CertRespaldosFase2.pvk',
        ENCRYPTION BY PASSWORD = '$(CLAVE_CERT)'
    );
    PRINT N'Certificado exportado a /var/opt/mssql/fase2/backups/certificado/';
END
ELSE
    PRINT N'El certificado ya tenia respaldo previo.';
GO

PRINT N'01_compresion_y_cifrado.sql finalizado.';
GO
