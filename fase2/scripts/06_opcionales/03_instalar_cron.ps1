<#
===============================================================================
 Fase 2 - Opcionales 03: instalar la programacion de respaldos con cron

 Deja el respaldo automatico funcionando dentro del contenedor de SQL Server:

   1. copia 02_backup_automatico.sh al contenedor y lo hace ejecutable
   2. instala cron (la imagen de SQL Server no lo trae)
   3. registra la entrada en el crontab
   4. arranca el servicio cron
   5. ejecuta el script una vez, para no tener que esperar a que dispare

 Programacion que instala:
     0 2 * * *   todos los dias a las 02:00
 El propio script decide si toca FULL (domingos) o diferencial (resto).

 Uso:
     .\fase2\scripts\06_opcionales\03_instalar_cron.ps1
     .\fase2\scripts\06_opcionales\03_instalar_cron.ps1 -Desinstalar

 Nota para el informe: cron dentro del contenedor se detiene cuando el
 contenedor se reinicia, porque la imagen no lo arranca sola. En un servidor
 real esto se resolveria con systemd, con el Agente de SQL Server, o con un
 contenedor aparte dedicado a la programacion. Se documenta como limitacion
 conocida de la implementacion.
===============================================================================
#>

[CmdletBinding()]
param([switch]$Desinstalar)

$ErrorActionPreference = 'Stop'

$raiz       = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$contenedor = 'olimpiadas-sqlserver'
$script     = '/var/opt/mssql/fase2/06_opcionales/02_backup_automatico.sh'
$entrada    = "0 2 * * * $script >> /var/opt/mssql/fase2/backups/automaticos/cron_stdout.log 2>&1"

function Paso { param([string]$T) ; Write-Host "  -> $T" -ForegroundColor Cyan }

if ($Desinstalar) {
    Paso 'Quitando la entrada del crontab'
    & docker exec -u root $contenedor bash -lc "crontab -l 2>/dev/null | grep -v '02_backup_automatico.sh' | crontab - ; echo 'crontab limpio'"
    Paso 'Deteniendo cron'
    & docker exec -u root $contenedor bash -lc "service cron stop 2>/dev/null || pkill cron || true"
    Write-Host 'Programacion desinstalada.' -ForegroundColor Green
    return
}

Write-Host ''
Write-Host 'Instalando respaldos automaticos con cron' -ForegroundColor Cyan
Write-Host ''

Paso 'Generando el archivo de credenciales dentro del contenedor'
# Se toma la clave del .env del proyecto y se deja en un archivo con permisos
# 600 propiedad de root. No se usa la variable de entorno del contenedor
# porque conserva el valor original de creacion y puede estar desactualizada.
$envFile = Join-Path $raiz 'OlimpiadasF1\.env'
$linea   = Select-String -Path $envFile -Pattern '^MSSQL_SA_PASSWORD=' | Select-Object -First 1
$clave   = $linea.Line -replace '^MSSQL_SA_PASSWORD=', '' -replace '"', ''
& docker exec -u root $contenedor bash -lc "mkdir -p /var/opt/mssql/fase2 && printf '%s' '$clave' > /var/opt/mssql/fase2/.credenciales && chmod 600 /var/opt/mssql/fase2/.credenciales && chown root:root /var/opt/mssql/fase2/.credenciales && echo 'credenciales escritas'"

Paso 'Copiando el script al contenedor'
& docker exec -u root $contenedor mkdir -p /var/opt/mssql/fase2/06_opcionales /var/opt/mssql/fase2/backups/automaticos | Out-Null
& docker cp (Join-Path $raiz 'fase2\scripts\06_opcionales\02_backup_automatico.sh') "${contenedor}:$script" | Out-Null

# El archivo se edito en Windows: se pasa a terminador LF o bash falla con
# "bad interpreter: /bin/bash^M".
& docker exec -u root $contenedor bash -lc "sed -i 's/\r$//' $script && chmod +x $script && chown mssql:root $script"

# La carpeta de destino debe pertenecer a mssql, que es el usuario con el que
# corre el motor: BACKUP escribe el archivo con ese usuario, no con root.
& docker exec -u root $contenedor bash -lc "chown -R mssql:root /var/opt/mssql/fase2/backups && echo 'permisos de la carpeta de respaldos corregidos'"

Paso 'Instalando cron dentro del contenedor'
# La redireccion va dentro de bash y no en PowerShell: al canalizar la salida
# de error de un ejecutable nativo, Windows PowerShell 5.1 la convierte en un
# error de terminacion aunque el comando haya funcionado (apt-get avisa por
# stderr que falta apt-utils, que es inofensivo).
& docker exec -u root $contenedor bash -lc "command -v cron >/dev/null 2>&1 || (apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq cron >/dev/null 2>&1) ; command -v cron >/dev/null 2>&1 && echo 'cron disponible' || echo 'ERROR: no se pudo instalar cron'"

Paso 'Registrando la entrada en el crontab'
& docker exec -u root $contenedor bash -lc "(crontab -l 2>/dev/null | grep -v '02_backup_automatico.sh' ; echo '$entrada') | crontab -"

Paso 'Arrancando el servicio cron'
& docker exec -u root $contenedor bash -lc "service cron start 2>/dev/null || cron"

Paso 'Crontab instalado:'
& docker exec -u root $contenedor bash -lc "crontab -l"

Write-Host ''
Paso 'Ejecutando el respaldo una vez para comprobar que funciona'
& docker exec -u root $contenedor bash -lc "$script"

Write-Host ''
Paso 'Archivos generados:'
& docker exec $contenedor bash -lc "ls -lh /var/opt/mssql/fase2/backups/automaticos/*.bak 2>/dev/null | tail -5"

Write-Host ''
Write-Host 'Listo. La bitacora queda en /var/opt/mssql/fase2/backups/automaticos/bitacora_cron.log' -ForegroundColor Green
