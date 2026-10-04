<#
===============================================================================
 Fase 2 - Driver de restauracion y medicion de tiempos

 Ejecuta la Fase 3 del enunciado para UN tipo de carga:

     eliminar la base
       -> restaurar solo el FULL          (estrategia A)  + validar
       -> restaurar FULL + DIFERENCIAL 1  (estrategia B)  + validar
       -> restaurar FULL + DIFERENCIAL 2                  + validar
       -> restaurar FULL + DIFERENCIAL 3                  + validar

 Cada restauracion se cronometra. Como los tiempos son de pocos cientos de
 milisegundos, una sola medicion no es confiable: por defecto se repite tres
 veces y se reporta la mediana, que es lo que se usa en el analisis
 comparativo.

 Los diferenciales de SQL Server son acumulativos, asi que para llegar al
 estado N se restauran DOS archivos (FULL + diferencial N) y no la cadena
 completa. Por eso cada medicion reinicia desde cero.

 Requisito: haber corrido antes ejecutar_carga.ps1 para el mismo tipo, que es
 quien deja fase2/evidencia/resultados/estado_<tipo>.json con los conteos que
 debe reproducir cada punto de restauracion.

 Uso:
     .\fase2\scripts\ejecutar_restauracion.ps1 -Tipo anio
     .\fase2\scripts\ejecutar_restauracion.ps1 -Tipo anio -Repeticiones 5
     .\fase2\scripts\ejecutar_restauracion.ps1 -Tipo anio -SinPausa
===============================================================================
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('anio', 'deporte', 'deportista')]
    [string]$Tipo,

    [ValidateRange(1, 10)]
    [int]$Repeticiones = 3,

    [switch]$SinPausa
)

$ErrorActionPreference = 'Stop'

$raiz        = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$contenedor  = 'olimpiadas-sqlserver'
$sqlcmd      = '/opt/mssql-tools18/bin/sqlcmd'
$scriptsCont = '/var/opt/mssql/fase2/scripts'

$sufijo = @{ 'anio' = 'Anio'; 'deporte' = 'Deporte'; 'deportista' = 'Deportista' }[$Tipo]
$db     = "OlimpiadasF2_$sufijo"

$carpetaLogs = Join-Path $raiz 'fase2\evidencia\logs'
$carpetaRes  = Join-Path $raiz 'fase2\evidencia\resultados'
foreach ($c in @($carpetaLogs, $carpetaRes)) {
    if (-not (Test-Path $c)) { New-Item -ItemType Directory -Path $c -Force | Out-Null }
}
$log = Join-Path $carpetaLogs ("restauracion_{0}_{1}.log" -f $Tipo, (Get-Date -Format 'yyyyMMdd_HHmmss'))

$envFile = Join-Path $raiz 'OlimpiadasF1\.env'
$linea   = Select-String -Path $envFile -Pattern '^MSSQL_SA_PASSWORD=' | Select-Object -First 1
$clave   = $linea.Line -replace '^MSSQL_SA_PASSWORD=', '' -replace '"', ''

# Puntos de restauracion esperados, escritos por ejecutar_carga.ps1
$rutaEstado = Join-Path $carpetaRes "estado_$Tipo.json"
if (-not (Test-Path $rutaEstado)) {
    throw "Falta $rutaEstado. Ejecute primero: .\fase2\scripts\ejecutar_carga.ps1 -Tipo $Tipo"
}
$estado = Get-Content $rutaEstado -Raw | ConvertFrom-Json

# --------------------------------------------------------------------------
function Escribir {
    param([string]$Texto, [string]$Color = 'Gray')
    $marca = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$marca] $Texto" -ForegroundColor $Color
    Add-Content -Path $log -Value "[$marca] $Texto" -Encoding utf8
}

function Titulo {
    param([string]$Texto)
    $barra = '=' * 78
    Write-Host ''
    Write-Host $barra -ForegroundColor Cyan
    Write-Host "  $Texto" -ForegroundColor Cyan
    Write-Host $barra -ForegroundColor Cyan
    Add-Content -Path $log -Value "`r`n$barra`r`n  $Texto`r`n$barra" -Encoding utf8
}

function EjecutarSql {
    param([string]$Script, [string[]]$Variables = @(), [switch]$Silencioso)
    $argumentos = @('exec', $contenedor, $sqlcmd,
                    '-S', 'localhost', '-U', 'sa', '-P', $clave, '-C', '-b',
                    '-f', '65001', '-W', '-s', '|', '-i', "$scriptsCont/$Script")
    foreach ($v in $Variables) { $argumentos += @('-v', $v) }

    $salida = & docker @argumentos 2>&1 | Out-String
    if (-not $Silencioso) { Write-Host $salida }
    Add-Content -Path $log -Value $salida -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Fallo $Script (codigo $LASTEXITCODE)" }
    return $salida
}

function Captura {
    param([string]$Nombre)
    if ($SinPausa) { return }
    Write-Host ''
    Write-Host "  >>> TOME LA CAPTURA AHORA: $Nombre" -ForegroundColor Yellow
    Write-Host "      Debe verse el reloj de Windows en la barra de tareas." -ForegroundColor Yellow
    Read-Host "      Presione Enter para continuar"
    Escribir "Captura registrada: $Nombre"
}

function DuracionDeSalida {
    <# Extrae la columna duracion_ms que imprimen los scripts de restauracion. #>
    param([string]$Salida)
    $fila = ($Salida -split "`n") | Where-Object { $_ -match '^RESTORE .*\|\d+\s*$' } | Select-Object -First 1
    if ($null -eq $fila) { return $null }
    return [int](($fila.Trim() -split '\|')[-1])
}

function Mediana {
    param([int[]]$Valores)
    $o = $Valores | Sort-Object
    $n = $o.Count
    if ($n % 2 -eq 1) { return $o[[int](($n - 1) / 2)] }
    return [int](($o[$n / 2 - 1] + $o[$n / 2]) / 2)
}

# --------------------------------------------------------------------------
Titulo "FASE 3 - RESTAURACION DE $($Tipo.ToUpper())  ->  base $db"
Escribir "Log: $log"
Escribir "Repeticiones por medicion: $Repeticiones"
Escribir "Puntos de restauracion declarados: $($estado.puntos.Count)"

& docker cp (Join-Path $raiz 'fase2\scripts') "${contenedor}:/var/opt/mssql/fase2/" | Out-Null
& docker exec -u root $contenedor chown -R mssql:root /var/opt/mssql/fase2 | Out-Null

$mediciones = @()

foreach ($punto in $estado.puntos) {

    $esFull = ($punto.respaldo -eq 'FULL')
    $etiqueta = if ($esFull) { 'FULL' } else { "FULL + $($punto.respaldo)" }
    $numero = if ($esFull) { $null } else { $punto.respaldo -replace 'DIFF_', '' }

    Titulo "RESTAURACION: $etiqueta   ($($punto.descripcion))"

    $tiemposFull = @()
    $tiemposDiff = @()

    foreach ($intento in 1..$Repeticiones) {
        Escribir "Repeticion $intento de $Repeticiones"

        EjecutarSql '04_restauracion/01_eliminar_base.sql' @("DB=$db") -Silencioso | Out-Null

        if ($esFull) {
            $s = EjecutarSql '04_restauracion/02_restaurar_full.sql' @("DB=$db", 'MODO=RECOVERY') -Silencioso
            $tiemposFull += (DuracionDeSalida $s)
        }
        else {
            $s = EjecutarSql '04_restauracion/02_restaurar_full.sql' @("DB=$db", 'MODO=NORECOVERY') -Silencioso
            $tiemposFull += (DuracionDeSalida $s)
            $s = EjecutarSql '04_restauracion/03_restaurar_diferencial.sql' @("DB=$db", "N=$numero") -Silencioso
            $tiemposDiff += (DuracionDeSalida $s)
        }
    }

    $mFull = Mediana $tiemposFull
    $mDiff = 0
    if ($tiemposDiff.Count -gt 0) { $mDiff = Mediana $tiemposDiff }
    $total = $mFull + $mDiff

    Escribir "Tiempos FULL (ms): $($tiemposFull -join ', ')  -> mediana $mFull"
    if ($tiemposDiff.Count -gt 0) {
        Escribir "Tiempos DIFF (ms): $($tiemposDiff -join ', ')  -> mediana $mDiff"
    }
    Escribir "TOTAL mediana: $total ms" 'Green'

    # Validacion de integridad contra los conteos que dejo la carga
    Titulo "VALIDACION de $etiqueta"
    EjecutarSql '05_validacion/01_conteos_y_muestra.sql' @("DB=$db")
    EjecutarSql '05_validacion/03_alerta_integridad.sql' `
        @("DB=$db", "ESP_ATLETAS=$($punto.atletas)", "ESP_PART=$($punto.participaciones)")
    Escribir "Integridad correcta: $($punto.atletas) atletas, $($punto.participaciones) participaciones" 'Green'

    Captura "$Tipo - restauracion $etiqueta"

    $mediciones += [ordered]@{
        tipo                  = $Tipo
        estrategia            = $etiqueta
        respaldo              = $punto.respaldo
        descripcion           = $punto.descripcion
        atletas               = $punto.atletas
        participaciones       = $punto.participaciones
        ms_full               = $mFull
        ms_diferencial        = $mDiff
        ms_total              = $total
        repeticiones          = $Repeticiones
        mediciones_full_ms    = ($tiemposFull -join ' ')
        mediciones_diff_ms    = ($tiemposDiff -join ' ')
    }
}

# --------------------------------------------------------------------------
$rutaCsv = Join-Path $carpetaRes "tiempos_$Tipo.csv"
$mediciones | ForEach-Object { [pscustomobject]$_ } |
    Export-Csv -Path $rutaCsv -NoTypeInformation -Encoding utf8

Titulo 'RESUMEN DE TIEMPOS'
$mediciones | ForEach-Object { [pscustomobject]$_ } |
    Format-Table estrategia, atletas, participaciones, ms_full, ms_diferencial, ms_total -AutoSize

Escribir "Resultados guardados en $rutaCsv" 'Green'
Captura "$Tipo - resumen de tiempos"
