<#
===============================================================================
 Fase 2 - Repetir UN punto de restauracion

 Sirve para volver a generar la salida de una sola restauracion cuando la
 captura de pantalla se perdio o salio mal, sin tener que repetir el ciclo
 completo de carga y restauracion.

 Hace exactamente lo mismo que ejecutar_restauracion.ps1 para ese punto:
 elimina la base, restaura, y valida la integridad contra los conteos que
 quedaron registrados en estado_<tipo>.json.

 NO modifica tiempos_<tipo>.csv: las mediciones buenas ya estan guardadas y
 este script es solo para la evidencia visual.

 Uso:
     .\fase2\scripts\recapturar_restauracion.ps1 -Tipo deporte -Punto 3
     .\fase2\scripts\recapturar_restauracion.ps1 -Tipo anio    -Punto full

 Parametros:
     -Tipo    anio | deporte | deportista
     -Punto   full | 1 | 2 | 3
===============================================================================
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('anio', 'deporte', 'deportista')]
    [string]$Tipo,

    [Parameter(Mandatory = $true)]
    [ValidateSet('full', '1', '2', '3')]
    [string]$Punto
)

$ErrorActionPreference = 'Stop'

$raiz        = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$contenedor  = 'olimpiadas-sqlserver'
$sqlcmd      = '/opt/mssql-tools18/bin/sqlcmd'
$scriptsCont = '/var/opt/mssql/fase2/scripts'

$sufijo = @{ 'anio' = 'Anio'; 'deporte' = 'Deporte'; 'deportista' = 'Deportista' }[$Tipo]
$db     = "OlimpiadasF2_$sufijo"

$envFile = Join-Path $raiz 'OlimpiadasF1\.env'
$linea   = Select-String -Path $envFile -Pattern '^MSSQL_SA_PASSWORD=' | Select-Object -First 1
$clave   = $linea.Line -replace '^MSSQL_SA_PASSWORD=', '' -replace '"', ''

$rutaEstado = Join-Path $raiz "fase2\evidencia\resultados\estado_$Tipo.json"
if (-not (Test-Path $rutaEstado)) { throw "Falta $rutaEstado" }
$estado = Get-Content $rutaEstado -Raw | ConvertFrom-Json

$respaldo = if ($Punto -eq 'full') { 'FULL' } else { "DIFF_$Punto" }
$infoPunto = $estado.puntos | Where-Object { $_.respaldo -eq $respaldo } | Select-Object -First 1
if ($null -eq $infoPunto) { throw "No hay un punto de restauracion '$respaldo' en $rutaEstado" }

function EjecutarSql {
    param([string]$Script, [string[]]$Variables = @())
    $argumentos = @('exec', $contenedor, $sqlcmd,
                    '-S', 'localhost', '-U', 'sa', '-P', $clave, '-C', '-b',
                    '-f', '65001', '-W', '-s', '|', '-i', "$scriptsCont/$Script")
    foreach ($v in $Variables) { $argumentos += @('-v', $v) }
    & docker @argumentos
    if ($LASTEXITCODE -ne 0) { throw "Fallo $Script (codigo $LASTEXITCODE)" }
}

$barra = '=' * 78
$etiqueta = if ($Punto -eq 'full') { 'FULL' } else { "FULL + DIFF_$Punto" }

Write-Host ''
Write-Host $barra -ForegroundColor Cyan
Write-Host "  RESTAURACION: $etiqueta   ($($infoPunto.descripcion))" -ForegroundColor Cyan
Write-Host $barra -ForegroundColor Cyan

& docker cp (Join-Path $raiz 'fase2\scripts') "${contenedor}:/var/opt/mssql/fase2/" | Out-Null

EjecutarSql '04_restauracion/01_eliminar_base.sql' @("DB=$db")

if ($Punto -eq 'full') {
    EjecutarSql '04_restauracion/02_restaurar_full.sql' @("DB=$db", 'MODO=RECOVERY')
}
else {
    EjecutarSql '04_restauracion/02_restaurar_full.sql' @("DB=$db", 'MODO=NORECOVERY')
    EjecutarSql '04_restauracion/03_restaurar_diferencial.sql' @("DB=$db", "N=$Punto")
}

Write-Host ''
Write-Host $barra -ForegroundColor Cyan
Write-Host "  VALIDACION de $etiqueta" -ForegroundColor Cyan
Write-Host $barra -ForegroundColor Cyan

EjecutarSql '05_validacion/01_conteos_y_muestra.sql' @("DB=$db")
EjecutarSql '05_validacion/03_alerta_integridad.sql' `
    @("DB=$db", "ESP_ATLETAS=$($infoPunto.atletas)", "ESP_PART=$($infoPunto.participaciones)")

Write-Host ''
Write-Host "Integridad correcta: $($infoPunto.atletas) atletas, $($infoPunto.participaciones) participaciones" -ForegroundColor Green
Write-Host "Tome la captura ahora. Los tiempos del CSV no se modificaron." -ForegroundColor Yellow
