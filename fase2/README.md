# Fase 2 — Respaldo y Restauración de Bases de Datos

Proyecto de Sistemas de Bases de Datos 2 · Grupo 7 · Segundo semestre 2026

Motor: **SQL Server 2025 Developer** en Docker, con almacenamiento persistente
en el volumen `sqlserver_data` (requisito del enunciado, sección 8.3).

---

## Qué hace este proyecto

Para cada uno de los tres tipos de carga que pide el enunciado se construye una
base independiente y se le aplica el ciclo completo de respaldo y restauración:

```
carga inicial (catálogos) ──► FULL
   carga r1 ──► DIFERENCIAL 1
   carga r2 ──► DIFERENCIAL 2
   carga r3 ──► DIFERENCIAL 3
        ──► fragmentación ──► ELIMINAR LA BASE
        ──► restaurar FULL              (medir tiempo, validar)
        ──► restaurar FULL + DIFF 1/2/3 (medir tiempo, validar)
```

En total: **3 respaldos completos y 9 diferenciales.**

| Base | Tipo de carga | r1 | r2 | r3 |
|---|---|---|---|---|
| `OlimpiadasF2_Anio` | por año | Río 2016 | Tokio 2020 | París 2024 |
| `OlimpiadasF2_Deporte` | por deporte (Atletismo) | Río 2016 | Tokio 2020 | París 2024 |
| `OlimpiadasF2_Deportista` | por deportista (Usain Bolt) | Atenas 2004 | Pekín 2008 | Londres 2012 |

### Dos decisiones que conviene conocer

**Diferencial y no incremental.** SQL Server no tiene respaldo incremental: sus
tipos son FULL, DIFFERENTIAL y LOG. El enunciado permite elegir "dependiendo de
las limitaciones del sistema de bases de datos elegido", y aquí la limitación es
del motor. Consecuencia práctica: para llegar al estado de la carga N se
restauran **dos** archivos (el FULL y el diferencial N), no la cadena completa.

**Atletismo en lugar de 100 m planos femenino.** El enunciado propone ese evento
como ejemplo ("deberán elegir **por ejemplo**"), pero **no existe en París 2024**
en los datos: Río 2016 tiene 85 filas, Tokio 2020 tiene 68 y París ninguna.
París sí tiene atletismo, así que se usa el deporte completo y las tres
ediciones quedan cubiertas.

---

## Orden de ejecución

Requisito previo: **Docker Desktop encendido** y el contenedor
`olimpiadas-sqlserver` corriendo.

### Paso 0 — Generar los recortes (una sola vez)

```powershell
python fase2\scripts\00_generar_slices.py
```

Lee los CSV limpios de `OlimpiadasF1/data/processed/` y escribe los 26 archivos
de carga en `fase2/data/slices/`, más un `manifiesto.json` con los conteos.

### Pasos 1 a 6 — Un ciclo por cada tipo de carga

```powershell
# por año
.\fase2\scripts\ejecutar_carga.ps1        -Tipo anio
.\fase2\scripts\ejecutar_restauracion.ps1 -Tipo anio

# por deporte
.\fase2\scripts\ejecutar_carga.ps1        -Tipo deporte
.\fase2\scripts\ejecutar_restauracion.ps1 -Tipo deporte

# por deportista
.\fase2\scripts\ejecutar_carga.ps1        -Tipo deportista
.\fase2\scripts\ejecutar_restauracion.ps1 -Tipo deportista
```

Los scripts se **detienen solos** en cada punto donde hay que tomar una captura
y muestran en amarillo qué se está capturando. Se continúa con Enter.

Opciones útiles:

| Opción | Para qué |
|---|---|
| `-SinPausa` | Corre de corrido, sin pedir capturas. Para ensayar o repetir mediciones. |
| `-Comprimir` | Aplica compresión a los respaldos de ese ciclo. |
| `-Repeticiones 5` | Cuántas veces se repite cada medición de restauración (por defecto 3). |

### Paso 7 — Alcance opcional

```powershell
# compresión y cifrado: genera tres versiones del mismo respaldo y las compara
docker exec olimpiadas-sqlserver /opt/mssql-tools18/bin/sqlcmd `
  -S localhost -U sa -P "<clave del .env>" -C -f 65001 -W -s "|" `
  -v DB="OlimpiadasF2_Anio" -v CLAVE_CERT="Fase2-Cert-2026-G7" `
  -i /var/opt/mssql/fase2/scripts/06_opcionales/01_compresion_y_cifrado.sql

# respaldos automáticos programados con cron
.\fase2\scripts\06_opcionales\03_instalar_cron.ps1
```

---

## Estructura

```
fase2/
  scripts/
    00_generar_slices.py          genera los recortes desde los CSV limpios
    ejecutar_carga.ps1            driver: cargas + respaldos + validaciones
    ejecutar_restauracion.ps1     driver: restauraciones + medición de tiempos
    01_ddl/                       crear base, crear tablas
    02_carga/                     carga inicial y carga por ronda
    03_backup/                    respaldo completo y diferencial
    04_restauracion/              eliminar, restaurar full, restaurar diferencial
    05_validacion/                conteos y muestra, fragmentación, alerta de integridad
    06_opcionales/                compresión, cifrado, cron
  data/slices/                    archivos de carga generados (no se editan a mano)
  evidencia/
    img/                          capturas de pantalla
    logs/                         bitácora de cada ejecución, con fecha y hora
    resultados/                   estado_<tipo>.json y tiempos_<tipo>.csv
  documentacion/
```

Dentro del contenedor, todo vive bajo `/var/opt/mssql/fase2/`, que está en el
volumen persistente:

```
/var/opt/mssql/fase2/
  slices/      los archivos de carga
  scripts/     copia de los scripts
  backups/     los .bak, el certificado y los respaldos automáticos
  .credenciales  clave de sa para la tarea de cron (permisos 600, root)
```

---

## Cuatro cosas que cuestan tiempo si no se saben

**`CODEPAGE` no existe en SQL Server sobre Linux.** `BULK INSERT ... WITH
CODEPAGE='65001'` falla con el error 16202. Los CSV son UTF-8 y las columnas son
`NVARCHAR`, así que se leen bien sin esa opción.

**Una ruta con `/*` dentro de un comentario rompe el script entero.** T-SQL
admite comentarios anidados: escribir `catalogos/*.csv` dentro de un bloque
`/* ... */` abre un comentario nuevo, y el `*/` final solo cierra ese. El lote
queda sin terminar y el `USE` nunca se ejecuta, de modo que todo corre contra
`master` y falla con "Invalid object name".

**Los CSV traen los enteros como `19.0`.** Los generó pandas, que convierte a
flotante cualquier columna entera con nulos. `BULK INSERT` no puede convertir
eso a `INT` y rechaza la fila con el error 4864. La Fase 1 lo resolvía cargando
primero a tablas de staging de texto; aquí se normaliza al generar el recorte.

**La variable `MSSQL_SA_PASSWORD` del contenedor puede estar desactualizada.**
Conserva el valor con el que se creó el contenedor. Si la contraseña de `sa` se
cambió después con `ALTER LOGIN` —que es lo que pasó en este proyecto—, todo
intento de conexión desde adentro falla con "Login failed for user 'sa'". Por eso
la tarea de cron lee la clave de un archivo de credenciales y no de la variable.

---

## Verificación rápida del entorno

```powershell
docker ps --filter name=olimpiadas-sqlserver
docker exec olimpiadas-sqlserver ls -lh /var/opt/mssql/fase2/backups/
```
