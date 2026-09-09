# Cleaning y homologación por fuente — Bloque 3

Este informe documenta transformaciones reproducibles por fuente. No realiza matching entre atletas, deduplicación global, consolidación final ni carga a SQL Server.

## Alcance ejecutado

- Archivos RAW validados y procesados: **10**.
- Archivos intermedios generados: **10**.
- Valores realmente modificados: **1604828**.
- Operaciones/valores procesados: **9218178**; esta métrica no equivale a modificaciones.
- Frecuencia acumulada de casos no resueltos: **83423**.
- Hashes SHA-256 coincidentes: **10/10**.
- Registros descartados: **0**.
- Duplicados exactos: analizados y conservados.

## Reglas aplicadas

- `strip()` únicamente sobre valores textuales; se conservaron tildes, Unicode y caracteres no ASCII.
- Marcadores de ausencia normalizados de forma dependiente de la columna. `Nan`, `DNS`, `DNF`, `DQ` y `DSQ` no se convirtieron globalmente a NULL.
- Medallas normalizadas exclusivamente a `Gold`, `Silver`, `Bronze` o NULL.
- Posiciones RAW separadas en `posicion`, `empatado`, `estado_resultado`, `pos_original` y `pos_clasificacion`.
- Fechas limpias normalizadas a ISO; Born/Died RAW se conservaron y se descompusieron solo cuando fue seguro.
- Games separado en `year` y `season`, con `games_original` temporal para trazabilidad.
- Mediciones convertidas a números cuando fue posible; no se eliminaron posibles atípicos.
- NOC descriptivo y código NOC se conservaron en columnas diferenciadas; no se asumió equivalencia con Country Code.
- populations.csv pasó a formato largo sin eliminar agregados.
- La matriz de ausencia por archivo y columna está en `missing_value_matrix.csv`; los campos descriptivos no reciben NA/N/A/null/None de forma global.

## Archivos intermedios

- `data/intermediate/cleaned/fuente1_clean_bios.csv`
- `data/intermediate/cleaned/fuente1_clean_bios_locs.csv`
- `data/intermediate/cleaned/fuente1_clean_noc_regions.csv`
- `data/intermediate/cleaned/fuente1_clean_populations_long.csv`
- `data/intermediate/cleaned/fuente1_clean_results.csv`
- `data/intermediate/cleaned/fuente1_raw_bios.csv`
- `data/intermediate/cleaned/fuente1_raw_results.csv`
- `data/intermediate/cleaned/fuente2_athlete_events.csv`
- `data/intermediate/cleaned/fuente3_olympics_dataset.csv`
- `data/intermediate/cleaned/fuente4_datalab_export.csv`

## Matriz de ausencia

`missing_value_matrix.csv` documenta cuándo el vacío, los marcadores semánticos y `No medal` se convierten a NULL. El vacío se normaliza después de `strip()`; los marcadores semánticos no se aplican a nombres, apodos, títulos, equipos, eventos, afiliaciones ni otros campos descriptivos.

## Resumen por archivo

| Archivo | Filas entrada | Filas salida | Columnas entrada | Columnas salida | Nulos antes | Nulos después | Modificados | Procesados | Descartados |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `data/raw/fuente1/clean/bios.csv` | 145500 | 145500 | 10 | 10 | 299423 | 299423 | 209664 | 686720 | 0 |
| `data/raw/fuente1/clean/bios_locs.csv` | 145500 | 145500 | 12 | 12 | 451333 | 451333 | 211474 | 977720 | 0 |
| `data/raw/fuente1/clean/noc_regions.csv` | 230 | 230 | 3 | 3 | 209 | 209 | 0 | 209 | 0 |
| `data/raw/fuente1/clean/populations.csv` | 266 | 17024 | 66 | 4 | 94 | 94 | 16930 | 50978 | 0 |
| `data/raw/fuente1/clean/results.csv` | 308408 | 308408 | 11 | 11 | 481382 | 481382 | 589000 | 1422929 | 0 |
| `data/raw/fuente1/raw/bios.csv` | 145500 | 145500 | 16 | 26 | 1009969 | 1632901 | 0 | 1291412 | 0 |
| `data/raw/fuente1/raw/results.csv` | 308408 | 308408 | 11 | 16 | 1069525 | 1180549 | 0 | 2655703 | 0 |
| `data/raw/fuente2/athlete_events.csv` | 271116 | 271116 | 15 | 15 | 363853 | 363853 | 363934 | 1626777 | 0 |
| `data/raw/fuente3/olympics_dataset.csv` | 252565 | 252565 | 11 | 11 | 213747 | 213747 | 213747 | 505130 | 0 |
| `data/raw/fuente4/datalab_export.csv` | 100 | 100 | 16 | 15 | 114 | 114 | 79 | 600 | 0 |

## Ejemplos antes/después

| Archivo/campo | Antes | Después |
|---|---|---|
| `fuente1/raw/results.csv` / `Pos` | `=17` | `pos_original='=17'`, `posicion=17`, `empatado=True`, `estado_resultado=NULL` |
| `fuente1/raw/results.csv` / `Pos` | `DNS` | `pos_original='DNS'`, `posicion=NULL`, `empatado=False`, `estado_resultado='DNS'` |
| `fuente2/athlete_events.csv` / `Medal` | `NA` | `medalla=NULL` |
| `fuente3/olympics_dataset.csv` / `Medal` | `No medal` | `medalla=NULL` |
| `fuente4/datalab_export.csv` / `index` | índice técnico | columna excluida; `id` se conserva |
| `fuente1/clean/populations.csv` / `1960` | formato ancho | fila(s) `country_name`, `country_code`, `year`, `population` |

## Duplicados

Los duplicados exactos de `clean/results.csv`, `raw/results.csv` y `athlete_events.csv` están en `duplicate_analysis.csv`. No se eliminó ningún registro; la muestra y las columnas involucradas quedan disponibles para la revisión del Bloque 4.

## Casos no resueltos

Los casos no resueltos se conservaron en los intermedios y se detallan en `unresolved_values.csv`. Incluyen posiciones complejas como `AC`, formatos de rondas y valores de Born/Died que no permiten extraer una fecha completa o una interpretación segura.

## Integridad

La validación SHA-256 se ejecutó antes y después del proceso. Todos los archivos coinciden con `docs/source_manifest.csv`; ningún archivo de `data/raw` fue escrito.

## Pendiente para revisión

- Revisar la semántica de posiciones complejas antes del matching.
- Revisar las inconsistencias Games/year/season registradas, si existen.
- Revisar duplicados exactos antes de cualquier deduplicación global.
- Confirmar la estrategia de matching para NOC descriptivo, NOC codificado y Country Code.
- No iniciar el Bloque 4 hasta aprobar este bloque.
