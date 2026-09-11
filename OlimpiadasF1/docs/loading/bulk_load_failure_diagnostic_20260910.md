# Diagnóstico controlado de Msg 4879 en `04_bulk_load_staging.sql`

## Resultado

**Causa raíz: `ROW_TERMINATOR`**.

El CSV oficial `data/processed/evento.csv` es válido y tiene tres columnas por fila, pero está serializado con **CRLF**. El script oficial fuerza `ROWTERMINATOR = '0x0a'`. En SQL Server 2025 sobre Linux, la prueba mínima del archivo oficial falla con ese terminador, mientras que la misma carga aislada funciona con `ROWTERMINATOR = '0x0d0a'`.

No se modificó el CSV oficial, no se modificó `04_bulk_load_staging.sql`, no se ejecutó `06_load_final.sql` y no se crearon índices.

## Schema staging real

La definición real de las diez tablas `stg.*` coincide con `scripts/sql/03_create_staging.sql`:

- 66 columnas comparadas.
- 66/66 compatibles.
- Todas son `NVARCHAR(MAX) NULL`.
- Collation observada: `SQL_Latin1_General_CP1_CI_AS`.
- `stg.EVENTO` tiene exactamente:
  - ordinal 1: `id_evento NVARCHAR(MAX)`;
  - ordinal 2: `id_disciplina NVARCHAR(MAX)`;
  - ordinal 3: `nombre NVARCHAR(MAX)`.

No hay `STALE_STAGING_SCHEMA` ni `STAGING_COLUMN_DEFINITION`.

Detalle completo: `staging_schema_diagnostic_20260910.csv`.

## Serialización de `evento.csv`

El archivo actual presenta:

- UTF-8 decodificable: sí.
- BOM: no.
- Terminadores: 3008 `CRLF`.
- Última línea terminada: sí.
- Header: `['id_evento', 'id_disciplina', 'nombre']`.
- Primera fila parseada: `['1', '96', 'Singles, Men (Olympic)']`.
- Primeras cinco filas válidas.
- NULL bytes: 0.
- Caracteres de control inesperados: 0.

`csv.reader` procesó todo el archivo:

- Filas de datos: **3,007**.
- Filas con cantidad distinta de 3 columnas: **0**.
- Longitud máxima de `nombre`: **157**.

El respaldo anterior conserva el mismo delimitador, quotechar y doble comilla, pero era UTF-8 con BOM y terminadores LF. El archivo actual es UTF-8 sin BOM y CRLF. La comparación está en `evento_csv_serialization_comparison_20260910.csv`.

## Pruebas aisladas

### Archivo oficial con el terminador del script

Prueba en `stg.__TEST_EVENTO_BULK` temporal:

```sql
ROWTERMINATOR = '0x0a'
```

Resultado: **FAIL**, 0 filas cargadas; el error observado en la ejecución oficial fue Msg 4879 y la prueba aislada terminó con Msg 7330 al no poder obtener una fila del proveedor BULK.

### Archivo mínimo de diagnóstico

Se creó únicamente `data/diagnostic/evento_minimal.csv`, con dos filas UTF-8 y el mismo campo quoted con coma interna. Con `ROWTERMINATOR = '0x0a'` cargó **2/2 filas** en la tabla temporal.

Esto demuestra que la coma interna de `"Singles, Men (Olympic)"` y el soporte `FORMAT='CSV'`/`FIELDQUOTE='"'` funcionan correctamente.

### Archivo oficial con CRLF

Con el mismo schema temporal y:

```sql
ROWTERMINATOR = '0x0d0a'
```

`evento.csv` cargó **3,007/3,007 filas** y la primera fila quedó como `1|96|Singles, Men (Olympic)`.

Como control adicional, `deporte.csv` es LF y cargó **65 filas** con `ROWTERMINATOR = '0x0a'`. Los CSV oficiales actuales no comparten un único terminador: hay archivos CRLF y archivos LF.

La distribución observada en los diez CSV es:

- CRLF: `atleta.csv`, `edicion_olimpica.csv`, `evento.csv`, `participacion.csv`.
- LF: `deporte.csv`, `disciplina.csv`, `entidad_geografica.csv`, `noc.csv`, `poblacion.csv`, `sede.csv`.

## Rollback y estado de SQL

Después del fallo de la transacción global de `04_bulk_load_staging.sql`:

- Las 10 tablas staging tienen 0 filas.
- Las tablas finales `olympics.*` tienen 0 filas porque fueron recreadas vacías y `06_load_final.sql` no se ejecutó.
- Las tablas temporales `stg.__TEST_EVENTO_BULK` y `stg.__TEST_GENERIC_BULK` fueron eliminadas.

## Causa clasificada

**`ROW_TERMINATOR`**.

La evidencia excluye:

- `STALE_STAGING_SCHEMA`: schema staging compatible 66/66.
- `STAGING_COLUMN_DEFINITION`: `nombre` es `NVARCHAR(MAX)`.
- `FILE_ENCODING`: UTF-8 decodificable y sin bytes inválidos.
- `SQLSERVER_CSV_PARSER` como causa general: el parser funciona con el archivo mínimo y con `evento.csv` usando CRLF.
- La coma interna como causa: el campo quoted se conserva correctamente en las pruebas válidas.

## Cambio mínimo recomendado — no aplicado

No se modifica todavía el ETL. En la siguiente reconstrucción controlada, `04_bulk_load_staging.sql` debe usar el terminador que corresponde a cada CSV oficial actual:

- archivos CRLF: `ROWTERMINATOR = '0x0d0a'`;
- archivos LF: `ROWTERMINATOR = '0x0a'`.

La recomendación debe implementarse de forma explícita por `BULK INSERT` o mediante una parametrización reproducible basada en la serialización comprobada, manteniendo `FORMAT='CSV'`, `FIELDQUOTE='"'`, los campos quoted con comas y la lectura Unicode. No debe normalizarse ni reescribirse `data/processed/`.

## Integridad final

- SHA-256 de `data/processed/`: **10/10 MATCH**.
- CSV oficial modificado: **no**.
- Reconstrucción completa reintentada: **no**.
- `06_load_final.sql`: **no ejecutado**.
- Índices creados: **no**.

Reportes generados:

- `staging_schema_diagnostic_20260910.csv`
- `evento_csv_serialization_comparison_20260910.csv`
- `bulk_load_failure_diagnostic_20260910.csv`
- este documento.
