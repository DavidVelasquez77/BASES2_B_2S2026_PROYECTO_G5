param()

$ErrorActionPreference = 'Stop'
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$sourceDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'OlimpiadasF1/data/processed'
$expected = @('atleta.csv','deporte.csv','disciplina.csv','edicion_olimpica.csv','entidad_geografica.csv','evento.csv','noc.csv','participacion.csv','poblacion.csv','sede.csv')

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker no está disponible.' }
if (-not (Test-Path -LiteralPath $sourceDir -PathType Container)) { throw "Falta data/processed: $sourceDir" }
$actual = @(Get-ChildItem -LiteralPath $sourceDir -Filter '*.csv' -File | ForEach-Object Name | Sort-Object)
if (@(Compare-Object $expected $actual).Count -ne 0) { throw 'Se esperaban exactamente los diez CSV procesados.' }

function Invoke-Compose([string[]]$Arguments) {
    & docker compose -f $composeFile @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falló Docker Compose (código $LASTEXITCODE): $($Arguments -join ' ')" }
}

Write-Host 'Iniciando MongoDB de Fase 3...'
Invoke-Compose -Arguments @('up','-d','--wait','mongo')
Write-Host 'Comprobando que OlimpiadasF3 no tenga colecciones existentes...'
Invoke-Compose -Arguments @('run','--rm','mongo-cli','--file','fase3/scripts/mongodb/00_assert_empty.js')

$steps = @(
    '01_create_collections.js',
    '02_load_processed.js',
    '02_load_processed.js',
    '03_create_indexes.js',
    '04_validate_import.js'
)
try {
    for ($i = 0; $i -lt $steps.Count; $i++) {
        $step = $steps[$i]
        $env:OLIMPIADAS_MONGO_APPLY = if ($i -eq 2) { '1' } else { '0' }
        Write-Host "Ejecutando $step $(if ($i -eq 1) {'(preflight)'} elseif ($i -eq 2) {'(carga)'})..."
        Invoke-Compose -Arguments @('run','--rm','mongo-cli','--file',"fase3/scripts/mongodb/$step")
    }
    Write-Host 'IMPORTACION_Y_VALIDACION_PASS. La base quedó disponible en localhost:27018.'
} finally {
    Remove-Item Env:OLIMPIADAS_MONGO_APPLY -ErrorAction SilentlyContinue
}
