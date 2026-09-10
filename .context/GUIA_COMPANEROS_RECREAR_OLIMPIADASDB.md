# Guía rápida para compañeros — Recrear `OlimpiadasDB` sin backup

Esta guía explica cómo levantar la base final del proyecto **desde cero**, usando Docker, los CSV procesados y los scripts ya preparados.

No hace falta usar un `.bak`.

---

# 1. Qué necesitan tener

Antes de empezar, cada compañero debe tener:

- Docker Desktop
- SQL Server Management Studio (SSMS)
- el proyecto completo `OlimpiadasF1`
- los 10 CSV dentro de:

```text
data/processed/
```

- los scripts SQL dentro de:

```text
scripts/sql/
```

- un archivo `.env` en la raíz del proyecto

---

# 2. Crear el archivo `.env`

En la raíz del proyecto crear:

```text
.env
```

con:

```text
MSSQL_SA_PASSWORD=TuPasswordSeguro123!
```

Debe cumplir los requisitos de contraseña de SQL Server.

No subir `.env` a Git.

---

# 3. Levantar SQL Server con Docker

Abrir PowerShell en la raíz del proyecto:

```powershell
docker compose up -d
```

Verificar:

```powershell
docker ps
```

Debe aparecer un contenedor llamado:

```text
olimpiadas-sqlserver
```

---

# 4. Esperar a que SQL Server esté listo

Ejecutar:

```powershell
docker logs olimpiadas-sqlserver
```

Buscar un mensaje equivalente a:

```text
SQL Server is now ready for client connections
```

No continuar hasta que SQL Server esté listo.

---

# 5. Cargar la contraseña en PowerShell

Antes de ejecutar scripts:

```powershell
$env:MSSQL_SA_PASSWORD = (Get-Content .\.env | Where-Object { $_ -match '^MSSQL_SA_PASSWORD=' }) -replace '^MSSQL_SA_PASSWORD=', ''
```

---

# 6. Crear la base

Ejecutar:

```powershell
Get-Content .\scripts\sql\00_create_database.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C
```

Debe crear:

```text
OlimpiadasDB
```

---

# 7. Crear las tablas finales

Ejecutar:

```powershell
Get-Content .\scripts\sql\01_create_tables.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Esto crea las 10 tablas bajo:

```text
olympics
```

---

# 8. Crear las tablas staging

Ejecutar:

```powershell
Get-Content .\scripts\sql\03_create_staging.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Esto crea las 10 tablas bajo:

```text
stg
```

---

# 9. Verificar que los CSV estén visibles dentro del contenedor

Ejecutar:

```powershell
docker exec -it olimpiadas-sqlserver bash -lc "ls -lah /var/opt/mssql/import/processed/"
```

Deben aparecer estos 10 archivos:

```text
entidad_geografica.csv
poblacion.csv
noc.csv
atleta.csv
sede.csv
edicion_olimpica.csv
deporte.csv
disciplina.csv
evento.csv
participacion.csv
```

Si no aparecen, no continuar.

---

# 10. Cargar los CSV a staging

Ejecutar:

```powershell
Get-Content .\scripts\sql\04_bulk_load_staging.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Esto carga los 10 CSV en `stg`.

---

# 11. Validar staging antes de cargar la base final

Ejecutar:

```powershell
Get-Content .\scripts\sql\05_validate_staging.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Debe mostrar validaciones con:

```text
PASS
```

No continuar si aparece algún:

```text
FAIL
```

---

# 12. Cargar las tablas finales

Solo ejecutar este paso si `05_validate_staging.sql` terminó correctamente.

```powershell
Get-Content .\scripts\sql\06_load_final.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Esto carga los datos desde `stg` hacia `olympics`.

---

# 13. Crear los índices

Ejecutar:

```powershell
Get-Content .\scripts\sql\07_create_indexes.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Debe crear 8 índices adicionales.

---

# 14. Validar la base cargada

Ejecutar:

```powershell
Get-Content .\scripts\sql\08_validate_loaded_data.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Debe terminar sin errores.

---

# 15. Validación global final

Ejecutar:

```powershell
Get-Content .\scripts\sql\10_final_validation.sql -Raw |
docker exec -i olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
-S localhost -U sa -P "$env:MSSQL_SA_PASSWORD" -C -d OlimpiadasDB
```

Debe mostrar:

```text
RESULTADO_GLOBAL = PASS
```

---

# 16. Conteos que deben obtener

Los conteos correctos son:

```text
ENTIDAD_GEOGRAFICA       282
POBLACION             17,024
NOC                      236
ATLETA               338,772
SEDE                      42
EDICION_OLIMPICA          61
DEPORTE                    65
DISCIPLINA                117
EVENTO                  3,106
PARTICIPACION         826,605
```

Total:

```text
1,186,310 filas
```

---

# 17. Cómo conectarse desde SSMS

Abrir SSMS y usar:

```text
Server name: localhost,1434
Authentication: SQL Server Authentication
Login: sa
Password: la del archivo .env
```

Si aparece la opción:

```text
Trust server certificate
```

habilitarla.

Luego seleccionar:

```text
OlimpiadasDB
```

---

# 18. Consulta rápida para verificar que todo funciona

Ejecutar en SSMS:

```sql
USE OlimpiadasDB;
GO

SELECT COUNT_BIG(*) AS atletas
FROM olympics.ATLETA;

SELECT COUNT_BIG(*) AS participaciones
FROM olympics.PARTICIPACION;

SELECT COUNT_BIG(*) AS ediciones
FROM olympics.EDICION_OLIMPICA;
```

Debe devolver:

```text
338772
826605
61
```

---

# 19. Qué NO deben ejecutar después de cargar

Una vez que la base ya esté cargada:

```text
NO ejecutar 00_reset_physical_tables.sql
NO ejecutar 03_reset_staging.sql
NO volver a ejecutar 06_load_final.sql
NO hacer DELETE
NO hacer TRUNCATE
NO hacer DROP
```

`06_load_final.sql` tiene un preflight que aborta si detecta datos existentes.

---

# 20. Si algo falla

## El contenedor no aparece

Ejecutar:

```powershell
docker compose up -d
docker ps
```

---

## SQL Server todavía no acepta conexión

Revisar:

```powershell
docker logs olimpiadas-sqlserver
```

Esperar hasta que SQL Server indique que está listo.

---

## No encuentra los CSV

Verificar:

```powershell
docker exec -it olimpiadas-sqlserver bash -lc "ls -lah /var/opt/mssql/import/processed/"
```

Si la carpeta está vacía, revisar el `docker-compose.yml` y confirmar que el proyecto tiene:

```text
data/processed/
```

con los 10 CSV.

---

## Error de contraseña

Volver a cargar:

```powershell
$env:MSSQL_SA_PASSWORD = (Get-Content .\.env | Where-Object { $_ -match '^MSSQL_SA_PASSWORD=' }) -replace '^MSSQL_SA_PASSWORD=', ''
```

---

## `OlimpiadasDB` ya existe

No ejecutar automáticamente resets ni `DROP DATABASE`.

Primero verificar si ya se cargó antes.

En SSMS:

```sql
SELECT DB_ID(N'OlimpiadasDB');
```

Si la base ya está completa, no hace falta reconstruirla.

---

# 21. Orden completo resumido

```text
1. docker compose up -d
2. cargar MSSQL_SA_PASSWORD en PowerShell
3. 00_create_database.sql
4. 01_create_tables.sql
5. 03_create_staging.sql
6. verificar 10 CSV dentro del contenedor
7. 04_bulk_load_staging.sql
8. 05_validate_staging.sql
9. 06_load_final.sql
10. 07_create_indexes.sql
11. 08_validate_loaded_data.sql
12. 10_final_validation.sql
13. conectarse por SSMS
14. empezar Stored Procedures / consultas T-SQL
```

---

# 22. Punto de inicio para el trabajo de procedimientos

Cuando obtengan:

```text
RESULTADO_GLOBAL = PASS
```

ya pueden trabajar directamente sobre:

```text
OlimpiadasDB.olympics
```

No usar:

```text
stg
```

para Stored Procedures o consultas de negocio.

---

# 23. Resumen final

No necesitan backup.

Solo necesitan:

```text
Docker
+
docker-compose.yml
+
.env
+
data/processed/*.csv
+
scripts/sql/
```

Con eso pueden reconstruir exactamente la base final validada.
