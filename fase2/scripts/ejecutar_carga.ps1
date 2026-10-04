<#
===============================================================================
 Fase 2 - Driver de carga y respaldo

 Ejecuta el ciclo completo de UN tipo de carga:

     crear base -> crear tablas -> carga inicial -> FULL
       -> carga r1 -> DIFF 1
       -> carga r2 -> DIFF 2
       -> carga r3 -> DIFF 3
       -> fragmentacion

 Despues de cada carga y de cada respaldo se ejecuta la validacion (conteos y
 muestra de cada tabla) y el script se detiene para que se tome la captura de
 pantalla, que es lo que pide el enunciado.

 Todo queda ademas en un archivo de log con la fecha y hora de cada paso, en
 fase2/evidencia/logs/.

 Uso:
     .\fase2\scripts\ejecutar_carga.ps1 -Tipo anio
     .\fase2\scripts\ejecutar_carga.ps1 -Tipo deporte  -Comprimir
     .\fase2\scripts\ejecutar_carga.ps1 -Tipo deportista -SinPausa

 Parametros:
     -Tipo       anio | deporte | deportista            (obligatorio)
     -Comprimir  aplica WITH COMPRESSION a los respaldos (alcance opcional)
     -SinPausa   no se detiene a pedir capturas; util para repetir mediciones
===============================================================================
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('anio', 'deporte', 'deportista')]
    [string]$Tipo,

    [switch]$Comprimir,
    [switch]$SinPausa
)

$ErrorActionPreference = 'Stop'

# --------------------------------------------------------------------------
# Rutas y constantes
# --------------------------------------------------------------------------
$raiz        = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$contenedor  = 'olimpiadas-sqlserver'
$sqlcmd      = '/opt/mssql-tools18/bin/sqlcmd'
$scriptsCont = '/var/opt/mssql/fase2/scripts'

$sufijo = @{ 'anio' = 'Anio'; 'deporte' = 'Deporte'; 'deportista' = 'Deportista' }[$Tipo]
$db     = "OlimpiadasF2_$sufijo"
$flagComp = '0'
if ($Comprimir) { $flagComp = '1' }

$carpetaLogs = Join-Path $raiz 'fase2\evidencia\logs'
if (-not (Test-Path $carpetaLogs)) { New-Item -ItemType Directory -Path $carpetaLogs -Force | Out-Null }
$log = Join-Path $carpetaLogs ("carga_{0}_{1}.log" -f $Tipo, (Get-Date -Format 'yyyyMMdd_HHmmss'))

# Contrasena: se lee del .env, nunca se escribe en el script ni en el log.
$envFile = Join-Path $raiz 'OlimpiadasF1\.env'
if (-not (Test-Path $envFile)) { throw "No se encontro $envFile" }
$linea = Select-String -Path $envFile -Pattern '^MSSQL_SA_PASSWORD=' | Select-Object -First 1
if ($null -eq $linea) { throw "El archivo .env no contiene MSSQL_SA_PASSWORD" }
$clave = $linea.Line -replace '^MSSQL_SA_PASSWORD=', '' -replace '"', ''

# --------------------------------------------------------------------------
# Funciones auxiliares
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
    param([string]$Script, [string[]]$Variables = @())
    $argumentos = @('exec', $contenedor, $sqlcmd,
                    '-S', 'localhost', '-U', 'sa', '-P', $clave, '-C', '-b',
                    '-f', '65001', '-W', '-s', '|',
                    '-i', "$scriptsCont/$Script")
    foreach ($v in $Variables) { $argumentos += @('-v', $v) }

    $salida = & docker @argumentos 2>&1 | Out-String
    Write-Host $salida
    Add-Content -Path $log -Value $salida -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        Escribir "FALLO el script $Script (codigo $LASTEXITCODE)" 'Red'
        throw "Fallo $Script"
    }
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

function ObtenerConteos {
    <#
      Devuelve @{ atletas = N; participaciones = M } de la base actual.
      Se usa para dejar registrado el estado en cada punto de respaldo: cada
      uno es un punto de restauracion distinto y hay que poder validarlo.
    #>
    $salida = & docker exec $contenedor $sqlcmd -S localhost -U sa -P $clave -C -h -1 -W -s '|' `
        -d $db -Q "SET NOCOUNT ON; SELECT CONCAT((SELECT COUNT(*) FROM olympics.ATLETA),'|',(SELECT COUNT(*) FROM olympics.PARTICIPACION));"
    $fila = $salida | Where-Object { $_ -match '^\d+\|\d+$' } | Select-Object -First 1
    if ($null -eq $fila) { throw 'No se pudieron leer los conteos de la base' }
    $v = $fila.Trim().Split('|')
    return @{ atletas = [int]$v[0]; participaciones = [int]$v[1] }
}

# Cada entrada es un punto de restauracion: que respaldo lo reproduce y que
# conteos debe devolver. El driver de restauracion lo lee para validar.
$puntos = @()

# --------------------------------------------------------------------------
# Preparacion: copiar scripts y recortes al contenedor
# --------------------------------------------------------------------------
Titulo "FASE 2 - CARGA POR $($Tipo.ToUpper())  ->  base $db"
Escribir "Log: $log"
Escribir "Compresion de respaldos: $(if ($Comprimir) { 'SI' } else { 'NO' })"

Escribir 'Copiando scripts y recortes al contenedor...'
& docker exec -u root $contenedor mkdir -p /var/opt/mssql/fase2/slices /var/opt/mssql/fase2/backups | Out-Null
& docker cp (Join-Path $raiz 'fase2\scripts') "${contenedor}:/var/opt/mssql/fase2/" | Out-Null
& docker cp (Join-Path $raiz 'fase2\data\slices\.') "${contenedor}:/var/opt/mssql/fase2/slices/" | Out-Null
& docker exec -u root $contenedor chown -R mssql:root /var/opt/mssql/fase2 | Out-Null
Escribir 'Listo.'

# --------------------------------------------------------------------------
# Paso 1: base y estructura
# --------------------------------------------------------------------------
Titulo 'PASO 1 - Crear la base y las tablas'
EjecutarSql '04_restauracion/01_eliminar_base.sql' @("DB=$db")
EjecutarSql '01_ddl/01_crear_base.sql'   @("DB=$db")
EjecutarSql '01_ddl/02_crear_tablas.sql' @("DB=$db")

# --------------------------------------------------------------------------
# Paso 2: carga inicial + FULL
# --------------------------------------------------------------------------
Titulo 'PASO 2 - Carga inicial (catalogos)'
EjecutarSql '02_carga/01_carga_inicial_catalogos.sql' @("DB=$db")
EjecutarSql '05_validacion/01_conteos_y_muestra.sql'  @("DB=$db")
Captura "$Tipo - carga inicial (catalogos)"

Titulo 'PASO 3 - Respaldo FULL'
EjecutarSql '03_backup/01_backup_full.sql' @("DB=$db", "COMPRIMIR=$flagComp")
$c = ObtenerConteos
$puntos += [ordered]@{
    respaldo        = 'FULL'
    descripcion     = 'solo catalogos (estado inmediatamente posterior a la carga inicial)'
    atletas         = $c.atletas
    participaciones = $c.participaciones
}
Escribir "Punto de restauracion FULL: $($c.atletas) atletas, $($c.participaciones) participaciones"

# --------------------------------------------------------------------------
# Pasos 4 a 9: las tres rondas, cada una con su diferencial
# --------------------------------------------------------------------------
$paso = 4
foreach ($n in 1..3) {
    $ronda = "r$n"

    Titulo "PASO $paso - Carga $ronda"
    EjecutarSql '02_carga/02_carga_ronda.sql'            @("DB=$db", "TIPO=$Tipo", "RONDA=$ronda")
    EjecutarSql '05_validacion/01_conteos_y_muestra.sql' @("DB=$db")
    Captura "$Tipo - carga $ronda"
    $paso++

    Titulo "PASO $paso - Respaldo DIFERENCIAL $n"
    EjecutarSql '03_backup/02_backup_diferencial.sql' @("DB=$db", "N=$n", "COMPRIMIR=$flagComp")
    $c = ObtenerConteos
    $puntos += [ordered]@{
        respaldo        = "DIFF_$n"
        descripcion     = "estado acumulado despues de la carga $ronda"
        atletas         = $c.atletas
        participaciones = $c.participaciones
    }
    Escribir "Punto de restauracion DIFF_${n}: $($c.atletas) atletas, $($c.participaciones) participaciones"
    $paso++
}

# --------------------------------------------------------------------------
# Paso 10: fragmentacion al cierre del tipo de carga
# --------------------------------------------------------------------------
Titulo "PASO $paso - Inventario de los respaldos generados"
# Una sola captura con los cuatro archivos, su tamano y su fecha y hora, en
# lugar de una captura por respaldo. El detalle de cada operacion (duracion,
# paginas, verificacion) queda en el log de esta misma ejecucion.
& docker exec $contenedor bash -lc "ls -lh --time-style=long-iso /var/opt/mssql/fase2/backups/${db}_*.bak"
EjecutarSql '03_backup/03_inventario_respaldos.sql' @("DB=$db")
Captura "$Tipo - inventario de los 4 respaldos"
$paso++

Titulo "PASO $paso - Nivel de fragmentacion"
EjecutarSql '05_validacion/02_fragmentacion.sql' @("DB=$db")
Captura "$Tipo - fragmentacion"

# --------------------------------------------------------------------------
# Cierre: se guardan los conteos finales, que la restauracion debe reproducir
# --------------------------------------------------------------------------
$final = ObtenerConteos

$estado = [ordered]@{
    tipo            = $Tipo
    base            = $db
    atletas         = $final.atletas
    participaciones = $final.participaciones
    comprimido      = [bool]$Comprimir
    fecha           = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    puntos          = $puntos
}
$rutaEstado = Join-Path $raiz "fase2\evidencia\resultados\estado_$Tipo.json"
New-Item -ItemType Directory -Path (Split-Path $rutaEstado) -Force | Out-Null
$estado | ConvertTo-Json -Depth 4 | Set-Content -Path $rutaEstado -Encoding utf8

Titulo 'CARGA COMPLETADA'
Escribir "Estado final: $($estado.atletas) atletas, $($estado.participaciones) participaciones" 'Green'
Escribir "Guardado en $rutaEstado"
Escribir "Siguiente paso:  .\fase2\scripts\ejecutar_restauracion.ps1 -Tipo $Tipo" 'Green'
