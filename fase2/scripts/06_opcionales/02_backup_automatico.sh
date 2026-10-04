#!/bin/bash
# =============================================================================
# Fase 2 - Opcionales 02: respaldo automatico programado con cron
# (cubre el punto "realizar programacion de backups automaticos mediante cron")
#
# Este script se ejecuta DENTRO del contenedor de SQL Server. Hace un respaldo
# de las tres bases de la Fase 2 y deja una linea por base en la bitacora.
#
# Politica que implementa:
#   - domingo          respaldo completo (FULL)
#   - lunes a sabado   respaldo diferencial
# Es la politica habitual en un servidor real: un full semanal y diferenciales
# diarios, que es justo el esquema que este proyecto compara.
#
# Instalacion (ver 03_instalar_cron.sh, que automatiza estos pasos):
#   docker cp 02_backup_automatico.sh olimpiadas-sqlserver:/var/opt/mssql/fase2/
#   docker exec -u root olimpiadas-sqlserver chmod +x /var/opt/mssql/fase2/02_backup_automatico.sh
#   y registrar la entrada en el crontab del contenedor.
#
# Uso manual (para probarlo sin esperar a que cron lo dispare):
#   docker exec olimpiadas-sqlserver /var/opt/mssql/fase2/02_backup_automatico.sh
#   docker exec olimpiadas-sqlserver /var/opt/mssql/fase2/02_backup_automatico.sh FULL
#
# La contrasena NO se escribe en este archivo. Se lee de
# /var/opt/mssql/fase2/.credenciales, que 03_instalar_cron.ps1 genera desde el
# .env del proyecto con permisos 600 y propietario root.
#
# Por que un archivo y no la variable de entorno del contenedor:
# MSSQL_SA_PASSWORD conserva el valor con el que se creo el contenedor. Si la
# contrasena de sa se cambio despues con ALTER LOGIN, la variable queda
# desactualizada y todo intento de conexion falla con "Login failed for user
# 'sa'". Es exactamente lo que ocurrio en este proyecto. El archivo de
# credenciales se actualiza al reinstalar la tarea y evita ese desfase.
# =============================================================================

set -u

SQLCMD="/opt/mssql-tools18/bin/sqlcmd"
ARCHIVO_CRED="/var/opt/mssql/fase2/.credenciales"

if [ -r "$ARCHIVO_CRED" ]; then
    CLAVE=$(head -1 "$ARCHIVO_CRED")
else
    CLAVE="${MSSQL_SA_PASSWORD:-}"
fi

if [ -z "$CLAVE" ]; then
    echo "ERROR: no hay credenciales. Ejecute 03_instalar_cron.ps1 para generarlas." >&2
    exit 2
fi
DESTINO="/var/opt/mssql/fase2/backups/automaticos"
BITACORA="/var/opt/mssql/fase2/backups/automaticos/bitacora_cron.log"
BASES="OlimpiadasF2_Anio OlimpiadasF2_Deporte OlimpiadasF2_Deportista"

mkdir -p "$DESTINO"
# El motor de SQL Server corre como el usuario mssql: si la carpeta queda
# como propiedad de root, BACKUP falla con "Operating system error 5".
chown mssql:root "$DESTINO" 2>/dev/null || true

# El tipo se puede forzar por parametro; si no, lo decide el dia de la semana.
# date +%u devuelve 7 para domingo.
if [ $# -ge 1 ]; then
    TIPO="$1"
elif [ "$(date +%u)" = "7" ]; then
    TIPO="FULL"
else
    TIPO="DIFF"
fi

marca() { date '+%Y-%m-%d %H:%M:%S'; }

registrar() {
    echo "[$(marca)] $1" | tee -a "$BITACORA"
}

registrar "=== Inicio de respaldo automatico ($TIPO) ==="

for BASE in $BASES; do

    # Una base que todavia no existe se omite sin marcar error.
    EXISTE=$("$SQLCMD" -S localhost -U sa -P "$CLAVE" -C -h -1 -W \
             -Q "SET NOCOUNT ON; SELECT CASE WHEN DB_ID('$BASE') IS NULL THEN 0 ELSE 1 END;" 2>/dev/null | tr -d '[:space:]')

    if [ "$EXISTE" != "1" ]; then
        registrar "  $BASE: no existe, se omite"
        continue
    fi

    SELLO=$(date '+%Y%m%d_%H%M%S')
    ARCHIVO="$DESTINO/${BASE}_${TIPO}_${SELLO}.bak"

    if [ "$TIPO" = "FULL" ]; then
        OPCIONES="FORMAT, INIT, CHECKSUM, COMPRESSION"
    else
        OPCIONES="DIFFERENTIAL, FORMAT, INIT, CHECKSUM, COMPRESSION"
    fi

    INICIO=$(date +%s%3N)

    SALIDA=$("$SQLCMD" -S localhost -U sa -P "$CLAVE" -C -b \
        -Q "BACKUP DATABASE [$BASE] TO DISK = N'$ARCHIVO' WITH $OPCIONES;" 2>&1)
    CODIGO=$?

    FIN=$(date +%s%3N)
    DURACION=$((FIN - INICIO))

    if [ $CODIGO -eq 0 ]; then
        TAMANO=$(du -h "$ARCHIVO" 2>/dev/null | cut -f1)
        registrar "  $BASE: OK  tipo=$TIPO  ${DURACION}ms  tamano=$TAMANO  archivo=$(basename "$ARCHIVO")"

        # Verificacion inmediata: un respaldo que no se puede leer no sirve.
        if "$SQLCMD" -S localhost -U sa -P "$CLAVE" -C -b \
             -Q "RESTORE VERIFYONLY FROM DISK = N'$ARCHIVO' WITH CHECKSUM;" >/dev/null 2>&1; then
            registrar "  $BASE: verificacion del archivo correcta"
        else
            registrar "  $BASE: ALERTA - el respaldo no paso RESTORE VERIFYONLY"
        fi
    else
        registrar "  $BASE: ERROR al respaldar -> $(echo "$SALIDA" | head -2 | tr '\n' ' ')"
    fi
done

# Retencion: se conservan los ultimos 14 archivos y se borran los mas viejos,
# para que la carpeta no crezca sin limite.
CANTIDAD=$(ls -1t "$DESTINO"/*.bak 2>/dev/null | wc -l)
if [ "$CANTIDAD" -gt 14 ]; then
    ls -1t "$DESTINO"/*.bak | tail -n +15 | while read -r VIEJO; do
        rm -f "$VIEJO"
        registrar "  retencion: eliminado $(basename "$VIEJO")"
    done
fi

registrar "=== Fin del respaldo automatico ==="
echo "" >> "$BITACORA"
