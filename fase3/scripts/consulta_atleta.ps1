<#
.SYNOPSIS
    Inciso c: muestra toda la información de un atleta (participaciones, resultados y medallas).

.EXAMPLE
    .\fase3\scripts\consulta_atleta.ps1 "Usain Bolt"
    .\fase3\scripts\consulta_atleta.ps1 "Michael Phelps" -Anio 2008 -Medalla oro
    .\fase3\scripts\consulta_atleta.ps1 "Luis López" -Pais MEX
    .\fase3\scripts\consulta_atleta.ps1 -Id 104492 -Formato json

.NOTES
    Usa mongosh si está instalado (URI predeterminada: mongodb://127.0.0.1:27017; para la
    instancia de fase3/compose.yaml use -Uri mongodb://127.0.0.1:27018). Si mongosh no está
    instalado, ejecuta mongosh dentro del contenedor MongoDB de fase3/compose.yaml, o del
    contenedor indicado en -Contenedor.
#>
param(
    [Parameter(Position = 0)] [string] $Nombre,
    [string] $Deporte,
    [string] $Pais,
    [string] $Anio,
    [string] $Temporada,
    [string] $Medalla,
    [string] $Id,
    [ValidateSet("texto", "json")] [string] $Formato = "texto",
    [string] $Uri = "mongodb://127.0.0.1:27017",
    [string] $BaseDatos = "OlimpiadasF3",
    [string] $Contenedor
)

if (-not $Nombre -and -not $Id) {
    Write-Error "Indique el nombre del atleta como primer parámetro, por ejemplo: .\consulta_atleta.ps1 `"Usain Bolt`""
    exit 1
}

$script = Join-Path $PSScriptRoot "mongodb\06_consulta_atleta.js"
$variables = [ordered]@{
    OLIMPIADAS_ATLETA    = $Nombre
    OLIMPIADAS_ATLETA_ID = $Id
    OLIMPIADAS_DEPORTE   = $Deporte
    OLIMPIADAS_PAIS      = $Pais
    OLIMPIADAS_ANIO      = $Anio
    OLIMPIADAS_TEMPORADA = $Temporada
    OLIMPIADAS_MEDALLA   = $Medalla
    OLIMPIADAS_FORMATO   = $Formato
    OLIMPIADAS_MONGO_DB  = $BaseDatos
}

$codificacionAnterior = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
    if (Get-Command mongosh -ErrorAction SilentlyContinue) {
        $anteriores = @{}
        foreach ($nombreVariable in $variables.Keys) {
            $anteriores[$nombreVariable] = [Environment]::GetEnvironmentVariable($nombreVariable)
            [Environment]::SetEnvironmentVariable($nombreVariable, $variables[$nombreVariable])
        }
        try {
            mongosh $Uri --quiet --file $script
        } finally {
            foreach ($nombreVariable in $variables.Keys) {
                [Environment]::SetEnvironmentVariable($nombreVariable, $anteriores[$nombreVariable])
            }
        }
    } elseif (Get-Command docker -ErrorAction SilentlyContinue) {
        if (-not $Contenedor) {
            $compose = Join-Path (Split-Path $PSScriptRoot -Parent) "compose.yaml"
            $Contenedor = docker compose -f $compose ps -q mongo 2>$null | Select-Object -First 1
            if (-not $Contenedor) { throw "MongoDB no está en ejecución. Inícielo con .\fase3\run_import.ps1 o indique -Contenedor." }
        }
        docker cp $script "${Contenedor}:/tmp/06_consulta_atleta.js" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el script al contenedor $Contenedor. ¿Está en ejecución?" }
        $argumentos = @("exec")
        foreach ($nombreVariable in $variables.Keys) {
            $argumentos += @("-e", "$nombreVariable=$($variables[$nombreVariable])")
        }
        $argumentos += @($Contenedor, "mongosh", "--quiet", "--file", "/tmp/06_consulta_atleta.js")
        & docker @argumentos
    } else {
        throw "No se encontró mongosh ni docker."
    }
} finally {
    [Console]::OutputEncoding = $codificacionAnterior
}
exit $LASTEXITCODE
