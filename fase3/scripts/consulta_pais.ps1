<#
.SYNOPSIS
    Inciso d: muestra toda la información histórica de un país (participaciones, resultados,
    medallas, años de participación y si ha sido sede en alguna ocasión con sus respectivos años).

.EXAMPLE
    .\fase3\scripts\consulta_pais.ps1 "Guatemala"
    .\fase3\scripts\consulta_pais.ps1 GUA -Anio 2012
    .\fase3\scripts\consulta_pais.ps1 France -Temporada verano -Medalla oro
    .\fase3\scripts\consulta_pais.ps1 Argentina -Deporte Football
    .\fase3\scripts\consulta_pais.ps1 GUA -Formato json

.NOTES
    Usa mongosh si está instalado (URI predeterminada: mongodb://127.0.0.1:27018 para la
    instancia de fase3/compose.yaml, o mongodb://127.0.0.1:27017 si se ejecuta directamente).
    Si mongosh no está instalado, ejecuta mongosh dentro del contenedor MongoDB de
    fase3/compose.yaml, o del contenedor indicado en -Contenedor.
#>
param(
    [Parameter(Position = 0)] [string] $Pais,
    [string] $Anio,
    [string] $Temporada,
    [string] $Deporte,
    [string] $Medalla,
    [string] $Limite = "100",
    [ValidateSet("texto", "json")] [string] $Formato = "texto",
    [string] $Uri = "mongodb://127.0.0.1:27018",
    [string] $BaseDatos = "OlimpiadasF3",
    [string] $Contenedor
)

if (-not $Pais) {
    Write-Error "Indique el país o código NOC/ISO como primer parámetro, por ejemplo: .\consulta_pais.ps1 `"Guatemala`" o .\consulta_pais.ps1 GUA"
    exit 1
}

$script = Join-Path $PSScriptRoot "mongodb\07_consulta_pais.js"
$variables = [ordered]@{
    OLIMPIADAS_PAIS      = $Pais
    OLIMPIADAS_ANIO      = $Anio
    OLIMPIADAS_TEMPORADA = $Temporada
    OLIMPIADAS_DEPORTE   = $Deporte
    OLIMPIADAS_MEDALLA   = $Medalla
    OLIMPIADAS_LIMITE    = $Limite
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
            if (-not $Contenedor) { throw "MongoDB no está en ejecución. Inícielo con docker compose -f fase3/compose.yaml up -d --wait mongo o indique -Contenedor." }
        }
        docker cp $script "${Contenedor}:/tmp/07_consulta_pais.js" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el script al contenedor $Contenedor. ¿Está en ejecución?" }
        $argumentos = @("exec")
        foreach ($nombreVariable in $variables.Keys) {
            $argumentos += @("-e", "$nombreVariable=$($variables[$nombreVariable])")
        }
        $argumentos += @($Contenedor, "mongosh", "--quiet", "--file", "/tmp/07_consulta_pais.js")
        & docker @argumentos
    } else {
        throw "No se encontró mongosh ni docker."
    }
} finally {
    [Console]::OutputEncoding = $codificacionAnterior
}
exit $LASTEXITCODE
