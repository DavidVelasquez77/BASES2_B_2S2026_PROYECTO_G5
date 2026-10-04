# Manual de usuario — Respaldo y restauración

Fase 2 · Sistemas de Bases de Datos 2 · Grupo 7

Esta guía explica cómo ejecutar, verificar e interpretar cada operación de
respaldo y restauración del proyecto. Está escrita para que alguien que no
participó en el desarrollo pueda reproducir el trabajo completo desde cero.

---

## 1. Requisitos previos

| Requisito | Cómo verificarlo |
|---|---|
| Docker Desktop encendido | `docker ps` debe listar `olimpiadas-sqlserver` |
| El contenedor corriendo | `docker ps --filter name=olimpiadas-sqlserver` |
| Python 3 instalado | `python --version` |
| Permiso para correr scripts | ver el paso 1.1 |

### 1.1 Habilitar la ejecución de scripts en PowerShell

Windows bloquea los scripts `.ps1` por defecto. En la ventana donde se va a
trabajar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Aplica solo a esa ventana y se deshace al cerrarla. Si no se ejecuta, el
primer script falla con `running scripts is disabled on this system`.

### 1.2 La contraseña

Nunca se escribe en los scripts. Se lee del archivo `OlimpiadasF1/.env`, que no
está versionado. Para tenerla disponible en la sesión:

```powershell
$pw = (Select-String -Path "OlimpiadasF1\.env" -Pattern '^MSSQL_SA_PASSWORD=').Line `
      -replace '^MSSQL_SA_PASSWORD=','' -replace '"',''
```

> **Advertencia.** La variable de entorno `MSSQL_SA_PASSWORD` que tiene el
> contenedor por dentro conserva el valor con el que se creó. Si la contraseña
> de `sa` se cambió después con `ALTER LOGIN`, esa variable queda
> desactualizada y cualquier conexión hecha desde adentro del contenedor falla
> con `Login failed for user 'sa'`. Por eso la tarea programada lee la clave de
> un archivo aparte y no de la variable.

---

## 2. Preparar los datos (una sola vez)

```powershell
python fase2\scripts\00_generar_slices.py
```

Lee los CSV limpios de `OlimpiadasF1/data/processed/` y escribe en
`fase2/data/slices/` los archivos que consume cada carga, más un
`manifiesto.json` con los conteos esperados. Salida normal:

```
Catalogos (carga inicial)
   entidad_geografica         282
   ...
Carga por anio
   r1  Rio de Janeiro 2016      atletas=12,305  participaciones= 15,118
```

Si los conteos no coinciden con los del manifiesto durante la carga, es que los
CSV de origen cambiaron y hay que volver a generar los recortes.

---

## 3. Ejecutar un ciclo completo

Un ciclo cubre un tipo de carga. Hay tres: `anio`, `deporte`, `deportista`.

### 3.1 Carga y respaldos

```powershell
.\fase2\scripts\ejecutar_carga.ps1 -Tipo anio
```

Hace, en orden: crea la base, crea las diez tablas, carga los catálogos, toma
el **respaldo completo**, y después carga cada una de las tres rondas tomando
un **respaldo diferencial** tras cada una. Cierra con el inventario de
respaldos y la medición de fragmentación.

El script se detiene seis veces para que se tome la captura de pantalla. Cuando
se detiene muestra:

```
  >>> TOME LA CAPTURA AHORA: anio - carga r1
      Debe verse el reloj de Windows en la barra de tareas.
      Presione Enter para continuar:
```

> **Importante.** Hay que presionar Enter también en la **última** pausa. El
> paso que guarda `estado_<tipo>.json` viene después, y ese archivo es
> obligatorio para la restauración. Si la ventana se cierra antes, los datos se
> pueden recuperar del log, pero es más simple no cerrarla.

Opciones:

| Opción | Efecto |
|---|---|
| `-Comprimir` | aplica `WITH COMPRESSION` a los respaldos del ciclo |
| `-SinPausa` | corre de corrido, sin pedir capturas |

### 3.2 Restauración y medición de tiempos

```powershell
.\fase2\scripts\ejecutar_restauracion.ps1 -Tipo anio
```

Para cada uno de los cuatro puntos de restauración: elimina la base, restaura,
valida la integridad y cronometra. Repite cada medición tres veces y reporta la
mediana, porque a esta escala una sola medición varía demasiado.

Con `-Repeticiones 5` se puede subir el número de repeticiones.

### 3.3 Repetir una sola restauración

Si una captura salió mal, no hace falta rehacer el ciclo:

```powershell
.\fase2\scripts\recapturar_restauracion.ps1 -Tipo deporte -Punto 3
```

`-Punto` acepta `full`, `1`, `2` o `3`. No modifica el archivo de tiempos.

---

## 4. Cómo se hace cada operación por dentro

Los scripts anteriores son envoltorios. Estas son las operaciones reales, por
si hay que ejecutarlas sueltas.

### 4.1 Respaldo completo

```sql
BACKUP DATABASE [OlimpiadasF2_Anio]
TO DISK = N'/var/opt/mssql/fase2/backups/OlimpiadasF2_Anio_FULL.bak'
WITH INIT, CHECKSUM, STATS = 25, NO_COMPRESSION;
```

| Cláusula | Para qué |
|---|---|
| `INIT` | sobrescribe el archivo. Sin esto SQL Server **anexa** un juego de respaldo más y el `.bak` crece indefinidamente |
| `CHECKSUM` | verifica cada página al escribirla |
| `STATS = 25` | imprime el avance cada 25 %, que es lo que queda en el log |

### 4.2 Respaldo diferencial

```sql
BACKUP DATABASE [OlimpiadasF2_Anio]
TO DISK = N'/var/opt/mssql/fase2/backups/OlimpiadasF2_Anio_DIFF_1.bak'
WITH DIFFERENTIAL, INIT, CHECKSUM, STATS = 25;
```

Un diferencial guarda todo lo que cambió **desde el último respaldo completo**,
no desde el diferencial anterior. Son acumulativos.

### 4.3 Restauración

Restaurar **solo el completo** deja la base lista para usarse:

```sql
RESTORE DATABASE [OlimpiadasF2_Anio]
FROM DISK = N'.../OlimpiadasF2_Anio_FULL.bak'
WITH REPLACE, RECOVERY, STATS = 25;
```

Restaurar **completo + diferencial** son dos pasos, y el primero debe ir con
`NORECOVERY`:

```sql
RESTORE DATABASE [OlimpiadasF2_Anio]
FROM DISK = N'.../OlimpiadasF2_Anio_FULL.bak'
WITH REPLACE, NORECOVERY, STATS = 25;

RESTORE DATABASE [OlimpiadasF2_Anio]
FROM DISK = N'.../OlimpiadasF2_Anio_DIFF_3.bak'
WITH RECOVERY, STATS = 25;
```

> Entre los dos pasos la base aparece como **`Restoring...`** y no acepta
> consultas. Eso es lo normal, no un error. Si el completo se restaura con
> `RECOVERY` por equivocación, ya no se le puede aplicar el diferencial y hay
> que empezar de nuevo.

Para llegar al estado de la carga 3 se restauran **dos** archivos, el completo
y el diferencial 3. No hace falta aplicar los diferenciales 1 y 2.

---

## 5. Validar que el respaldo sirve

### 5.1 Antes de necesitarlo

```sql
RESTORE VERIFYONLY FROM DISK = N'.../OlimpiadasF2_Anio_FULL.bak' WITH CHECKSUM;
```

Comprueba que el archivo se puede leer y que los checksums cuadran, sin
restaurar nada. Respuesta esperada:

```
The backup set on file 1 is valid.
```

Los scripts de respaldo ya lo ejecutan automáticamente después de cada
respaldo.

### 5.2 Después de restaurar

```powershell
docker exec olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P $pw -C -f 65001 -W -s "|" `
  -v DB="OlimpiadasF2_Anio" -v ESP_ATLETAS="34250" -v ESP_PART="58317" `
  -i /var/opt/mssql/fase2/scripts/05_validacion/03_alerta_integridad.sql
```

Comprueba tres cosas y **corta con error** si alguna falla:

1. que los conteos coincidan con los esperados
2. que no haya filas huérfanas (participaciones que apunten a un atleta,
   edición, evento o NOC inexistente)
3. que `DBCC CHECKDB` no reporte daños

Salida correcta:

```
ATLETA|34250|34250|OK
PARTICIPACION|58317|58317|OK
huerfanos_atleta|huerfanos_edicion|huerfanos_evento|huerfanos_noc|resultado
0|0|0|0|OK
Integridad verificada en OlimpiadasF2_Anio: conteos y referencias correctos
```

Salida cuando algo está mal:

```
ATLETA|26621|34250|ALERTA
Msg 50000, Level 16: ALERTA DE INTEGRIDAD en OlimpiadasF2_Anio:
1 comprobacion(es) fallaron. Atletas 26621/34250 ...
```

Además `sqlcmd` termina con código distinto de cero, así que la alerta
detiene cualquier script que la invoque.

---

## 6. Cómo leer los registros

Cada ejecución deja un log con sello de tiempo en `fase2/evidencia/logs/`:

```
carga_anio_20261004_065143.log
restauracion_anio_20261004_070012.log
```

Qué buscar dentro:

| Línea | Qué significa |
|---|---|
| `Processed 3184 pages ... in 0.066 seconds` | el motor terminó el respaldo; páginas y velocidad |
| `The backup set on file 1 is valid` | el archivo pasó la verificación |
| `tipo_respaldo\|...\|duracion_ms` | duración medida por el script, más precisa que la de `msdb` |
| `Punto de restauracion DIFF_2: 26621 atletas` | estado que ese respaldo debe reproducir al restaurarse |
| `Captura registrada: ...` | el operador confirmó la captura y el script siguió |
| `ALERTA DE INTEGRIDAD` | la validación falló; el resto del log dice en qué |

Para ver solo lo esencial de un log:

```powershell
Select-String -Path fase2\evidencia\logs\carga_anio_*.log `
  -Pattern "PASO|Punto de restauracion|ALERTA|finalizado"
```

---

## 7. Alcance opcional

### 7.1 Compresión y cifrado

```powershell
docker exec olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P $pw -C -f 65001 -W -s "|" `
  -v DB="OlimpiadasF2_Anio" -v CLAVE_CERT="Fase2-Cert-2026-G7" `
  -i /var/opt/mssql/fase2/scripts/06_opcionales/01_compresion_y_cifrado.sql
```

Genera tres versiones del mismo respaldo —sin comprimir, comprimido, y
comprimido con cifrado AES-256— y las compara.

> Un respaldo cifrado **solo se puede restaurar en una instancia que tenga el
> mismo certificado**. El script lo exporta a
> `/var/opt/mssql/fase2/backups/certificado/`. Si se pierde, el respaldo es
> irrecuperable.

### 7.2 Respaldos automáticos

```powershell
.\fase2\scripts\06_opcionales\03_instalar_cron.ps1
```

Instala una tarea diaria a las 02:00 que hace respaldo completo los domingos y
diferencial el resto de los días, verifica cada archivo y conserva los últimos
catorce.

Para ver la bitácora:

```powershell
docker exec olimpiadas-sqlserver cat /var/opt/mssql/fase2/backups/automaticos/bitacora_cron.log
```

Para desinstalar: `.\fase2\scripts\06_opcionales\03_instalar_cron.ps1 -Desinstalar`

> **Limitación conocida.** La imagen de SQL Server no arranca `cron` al
> iniciarse, así que después de reiniciar el contenedor hay que volver a correr
> el instalador. En un servidor real esto se resolvería con `systemd`, con el
> Agente de SQL Server, o con un contenedor aparte para la programación.

---

## 8. Generar el análisis

Con los tres ciclos terminados:

```powershell
python fase2\scripts\07_analisis\generar_analisis.py
```

Produce `fase2/documentacion/analisis_resultados.md` con las tablas
comparativas y las dos gráficas, tomando los números de los CSV de mediciones.
Ningún valor se escribe a mano. Se puede volver a ejecutar las veces que haga
falta.

---

## 9. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `running scripts is disabled on this system` | falta el paso 1.1 |
| `Login failed for user 'sa'` desde dentro del contenedor | la variable de entorno está desactualizada; usar el archivo de credenciales (ver 1.2) |
| `Invalid object name 'olympics.X'` | la sesión está en `master`; agregar `USE <base>;` |
| `Cannot open backup device ... error 5` | la carpeta pertenece a `root` y el motor corre como `mssql`; `chown -R mssql:root /var/opt/mssql/fase2/backups` |
| `Bulk load data conversion error ... (4864)` | el CSV trae enteros como `19.0`; regenerar los recortes con `00_generar_slices.py` |
| `Keyword or statement option 'CODEPAGE' is not supported on the 'Linux' platform` | no usar `CODEPAGE` en `BULK INSERT`; los CSV son UTF-8 y las columnas `NVARCHAR` |
| `The backup cannot be performed because 'ENCRYPTION' was requested after the media was formatted` | el `.bak` ya existe sin cifrado; usar `WITH FORMAT` |
| La base queda en `Restoring...` | se restauró el completo con `NORECOVERY` y falta aplicar el diferencial |
| `Falta estado_<tipo>.json` | no se presionó Enter en la última pausa de la carga; se reconstruye desde el log |
