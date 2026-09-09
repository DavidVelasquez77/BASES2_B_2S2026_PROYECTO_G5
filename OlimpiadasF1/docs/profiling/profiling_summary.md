# Profiling diagnóstico de fuentes olímpicas

> Este informe describe los CSV originales sin limpiarlos, transformarlos, homologarlos, deduplicarlos ni modificar sus valores.

- Fecha de ejecución: `2026-09-08T22:17:19.352561-06:00`
- Python: `3.14.7`
- pandas: `3.0.5`
- Directorio analizado: `C:/Users/Vela/Desktop/BASES2/LAB/PROYECTO1/OlimpiadasF1/data/raw`
- Archivos analizados: **10**

## Validaciones de integridad

- Archivos esperados: `10`.
- Archivos analizados: `10`.
- SHA-256 contra `docs/source_manifest.csv`: **10 de 10 coinciden**.
- Los hashes se compararon antes y después del profiling; el script solo lee `data/raw`.

## Resumen por archivo

| Fuente | Archivo | Filas | Columnas | Filas vacías | Columnas vacías | Duplicados exactos | Tamaño (bytes) | Codificación |
|---|---|---:|---:|---:|---:|---:|---:|---|
| fuente1 | `data/raw/fuente1/clean/bios.csv` | 145500 | 10 | 0 | 0 | 0 | 10984430 | `utf-8` |
| fuente1 | `data/raw/fuente1/clean/bios_locs.csv` | 145500 | 12 | 0 | 0 | 0 | 12714370 | `utf-8` |
| fuente1 | `data/raw/fuente1/clean/noc_regions.csv` | 230 | 3 | 0 | 0 | 0 | 3825 | `utf-8` |
| fuente1 | `data/raw/fuente1/clean/populations.csv` | 266 | 66 | 0 | 0 | 0 | 180131 | `utf-8` |
| fuente1 | `data/raw/fuente1/clean/results.csv` | 308408 | 11 | 0 | 0 | 126 | 33351982 | `utf-8` |
| fuente1 | `data/raw/fuente1/raw/bios.csv` | 145500 | 16 | 0 | 0 | 0 | 27969433 | `utf-8` |
| fuente1 | `data/raw/fuente1/raw/results.csv` | 308408 | 11 | 0 | 1 | 110 | 34250752 | `utf-8` |
| fuente2 | `data/raw/fuente2/athlete_events.csv` | 271116 | 15 | 0 | 0 | 1385 | 41500688 | `utf-8` |
| fuente3 | `data/raw/fuente3/olympics_dataset.csv` | 252565 | 11 | 0 | 0 | 0 | 26988833 | `utf-8` |
| fuente4 | `data/raw/fuente4/datalab_export.csv` | 100 | 16 | 0 | 0 | 0 | 17063 | `utf-8-sig` |

## Hallazgos importantes

Los siguientes hallazgos son señales diagnósticas para revisar en el Bloque 3; no constituyen reglas de limpieza.

- Hay duplicados exactos en: `results.csv` (126), `results.csv` (110), `athlete_events.csv` (1385).
- Hay columnas completamente vacías en: `results.csv` (1).
- Categorías especiales detectadas: `POSITION_EQUALS_PREFIX` (167), `EMPTY_STRING` (110), `NON_ASCII` (29), `MEDAL_VALUE` (20), `SPECIAL_TOKEN` (12), `POTENTIAL_OUTLIER_IQR` (10), `LEADING_OR_TRAILING_SPACE` (5), `POSITION_CATEGORY` (4).

## Fechas y años

| Archivo | Columna | No vacíos | Parseables | No parseables | Mínimo | Máximo |
|---|---|---:|---:|---:|---|---|
| `data/raw/fuente1/clean/bios.csv` | `born_date` | 143693 | 143693 | 0 | 1828-10-25 | 2009-01-01 |
| `data/raw/fuente1/clean/bios.csv` | `died_date` | 33940 | 33940 | 0 | 1900-04-23 | 2023-12-28 |
| `data/raw/fuente1/clean/bios_locs.csv` | `born_date` | 143693 | 143693 | 0 | 1828-10-25 | 2009-01-01 |
| `data/raw/fuente1/clean/bios_locs.csv` | `died_date` | 33940 | 33940 | 0 | 1900-04-23 | 2023-12-28 |
| `data/raw/fuente1/clean/results.csv` | `year` | 305807 | 305807 | 0 | 1896.0 | 2022.0 |
| `data/raw/fuente1/raw/bios.csv` | `Born` | 143772 | 22767 | 121005 | 1848-08-27 | 2008-08-26 |
| `data/raw/fuente1/raw/bios.csv` | `Died` | 34042 | 4953 | 29089 | 1900-04-23 | 2023-12-21 |
| `data/raw/fuente2/athlete_events.csv` | `Year` | 271116 | 271116 | 0 | 1896 | 2016 |
| `data/raw/fuente3/olympics_dataset.csv` | `Year` | 252565 | 252565 | 0 | 1896 | 2024 |
| `data/raw/fuente4/datalab_export.csv` | `year` | 100 | 100 | 0 | 1900 | 2016 |

## Números

Se revisaron las columnas `Age`, `Height`, `Weight`, `height_cm` y `weight_kg` cuando estuvieron presentes. Los mínimos, máximos, nulos, valores no numéricos y posibles atípicos se encuentran en `summary_columns.csv` y `special_values.csv`.

## NOC

- `data/raw/fuente1/clean/bios.csv` / `NOC`: 696 NOC distintos; 1 valores con patrón de tres letras mayúsculas y 695 valores descriptivos. Frecuentes: `[{"valor":"United States","frecuencia":10114},{"valor":"Great Britain","frecuencia":6421},{"valor":"France","frecuencia":6339},{"valor":"Canada","frecuencia":5276},{"valor":"Italy","frecuencia":5189}]`.
- `data/raw/fuente1/clean/bios_locs.csv` / `NOC`: 696 NOC distintos; 1 valores con patrón de tres letras mayúsculas y 695 valores descriptivos. Frecuentes: `[{"valor":"United States","frecuencia":10114},{"valor":"Great Britain","frecuencia":6421},{"valor":"France","frecuencia":6339},{"valor":"Canada","frecuencia":5276},{"valor":"Italy","frecuencia":5189}]`.
- `data/raw/fuente1/clean/noc_regions.csv` / `NOC`: 230 NOC distintos; 230 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"AFG","frecuencia":1},{"valor":"AHO","frecuencia":1},{"valor":"ALB","frecuencia":1},{"valor":"ALG","frecuencia":1},{"valor":"AND","frecuencia":1}]`.
- `data/raw/fuente1/clean/results.csv` / `noc`: 230 NOC distintos; 230 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"USA","frecuencia":21353},{"valor":"FRA","frecuencia":14276},{"valor":"GBR","frecuencia":13170},{"valor":"ITA","frecuencia":12129},{"valor":"CAN","frecuencia":11455}]`.
- `data/raw/fuente1/raw/bios.csv` / `NOC`: 696 NOC distintos; 1 valores con patrón de tres letras mayúsculas y 695 valores descriptivos. Frecuentes: `[{"valor":"United States","frecuencia":10114},{"valor":"Great Britain","frecuencia":6421},{"valor":"France","frecuencia":6339},{"valor":"Canada","frecuencia":5276},{"valor":"Italy","frecuencia":5189}]`.
- `data/raw/fuente1/raw/results.csv` / `NOC`: 230 NOC distintos; 230 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"USA","frecuencia":21353},{"valor":"FRA","frecuencia":14276},{"valor":"GBR","frecuencia":13170},{"valor":"ITA","frecuencia":12129},{"valor":"CAN","frecuencia":11455}]`.
- `data/raw/fuente2/athlete_events.csv` / `NOC`: 230 NOC distintos; 230 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"USA","frecuencia":18853},{"valor":"FRA","frecuencia":12758},{"valor":"GBR","frecuencia":12256},{"valor":"ITA","frecuencia":10715},{"valor":"GER","frecuencia":9830}]`.
- `data/raw/fuente3/olympics_dataset.csv` / `NOC`: 234 NOC distintos; 234 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"USA","frecuencia":16774},{"valor":"GBR","frecuencia":11998},{"valor":"FRA","frecuencia":11972},{"valor":"ITA","frecuencia":9351},{"valor":"GER","frecuencia":8866}]`.
- `data/raw/fuente4/datalab_export.csv` / `noc`: 9 NOC distintos; 9 valores con patrón de tres letras mayúsculas y 0 valores descriptivos. Frecuentes: `[{"valor":"FIN","frecuencia":33},{"valor":"NOR","frecuencia":32},{"valor":"USA","frecuencia":16},{"valor":"NED","frecuencia":12},{"valor":"CHN","frecuencia":2}]`.

## Medallas

- `data/raw/fuente1/clean/results.csv` / `medal`: `<EMPTY_STRING>` = 264269.
- `data/raw/fuente1/clean/results.csv` / `medal`: `Bronze` = 14810.
- `data/raw/fuente1/clean/results.csv` / `medal`: `Gold` = 14783.
- `data/raw/fuente1/clean/results.csv` / `medal`: `Silver` = 14546.
- `data/raw/fuente1/raw/results.csv` / `Medal`: `<EMPTY_STRING>` = 264269.
- `data/raw/fuente1/raw/results.csv` / `Medal`: `Bronze` = 14810.
- `data/raw/fuente1/raw/results.csv` / `Medal`: `Gold` = 14783.
- `data/raw/fuente1/raw/results.csv` / `Medal`: `Silver` = 14546.
- `data/raw/fuente2/athlete_events.csv` / `Medal`: `NA` = 231333.
- `data/raw/fuente2/athlete_events.csv` / `Medal`: `Gold` = 13372.
- `data/raw/fuente2/athlete_events.csv` / `Medal`: `Bronze` = 13295.
- `data/raw/fuente2/athlete_events.csv` / `Medal`: `Silver` = 13116.
- `data/raw/fuente3/olympics_dataset.csv` / `Medal`: `No medal` = 213747.
- `data/raw/fuente3/olympics_dataset.csv` / `Medal`: `Bronze` = 13070.
- `data/raw/fuente3/olympics_dataset.csv` / `Medal`: `Gold` = 13002.
- `data/raw/fuente3/olympics_dataset.csv` / `Medal`: `Silver` = 12746.
- `data/raw/fuente4/datalab_export.csv` / `medal`: `null` = 79.
- `data/raw/fuente4/datalab_export.csv` / `medal`: `Gold` = 9.
- `data/raw/fuente4/datalab_export.csv` / `medal`: `Bronze` = 8.
- `data/raw/fuente4/datalab_export.csv` / `medal`: `Silver` = 4.

## Posiciones

- `data/raw/fuente1/clean/results.csv` / `place`: distintos numéricos=185, distintos con `=`=0, distintos estados/otros=0; muestras numéricas=[{"valor":"5.0","frecuencia":21693},{"valor":"3.0","frecuencia":18503},{"valor":"4.0","frecuencia":17774},{"valor":"2.0","frecuencia":17718},{"valor":"1.0","frecuencia":16719},{"valor":"9.0","frecuencia":16129},{"valor":"6.0","frecuencia":15806},{"valor":"7.0","frecuencia":14729},{"valor":"8.0","frecuencia":12133},{"valor":"17.0","frecuencia":8662}]; muestras con `=`=[]; muestras de estados/otros=[].
- `data/raw/fuente1/raw/results.csv` / `Pos`: distintos numéricos=330, distintos con `=`=167, distintos estados/otros=2071; muestras numéricas=[{"valor":"1.0","frecuencia":11166},{"valor":"2.0","frecuencia":10648},{"valor":"3.0","frecuencia":9733},{"valor":"4.0","frecuencia":9341},{"valor":"5.0","frecuencia":8432},{"valor":"6.0","frecuencia":8191},{"valor":"7.0","frecuencia":7502},{"valor":"8.0","frecuencia":7280},{"valor":"9.0","frecuencia":6078},{"valor":"10.0","frecuencia":5685}]; muestras con `=`=[{"valor":"=9","frecuencia":7312},{"valor":"=5","frecuencia":5235},{"valor":"=17","frecuencia":5138},{"valor":"=33","frecuencia":1534},{"valor":"=13","frecuencia":1452},{"valor":"=7","frecuencia":1387},{"valor":"=3","frecuencia":1338},{"valor":"=11","frecuencia":1159},{"valor":"=19","frecuencia":586},{"valor":"=16","frecuencia":512}]; muestras de estados/otros=[{"valor":"DNS","frecuencia":8837},{"valor":"DNF","frecuencia":7943},{"valor":"AC","frecuencia":4833},{"valor":"DQ","frecuencia":1563},{"valor":"AC r1/2","frecuencia":634},{"valor":"AC r2/2","frecuencia":418},{"valor":"5 h1 r2/3","frecuencia":373},{"valor":"4 h1 r2/3","frecuencia":370},{"valor":"6 h1 r2/3","frecuencia":340},{"valor":"5 h2 r2/3","frecuencia":290}].

## Archivos generados

- `summary_files.csv`: una fila por CSV.
- `summary_columns.csv`: una fila por columna.
- `special_values.csv`: valores especiales y categorías diagnósticas.
- `hash_validation.csv`: comparación de SHA-256 contra el manifiesto.
- `profiling_summary.md`: este informe.

## Alcance y límites

No se aplicaron reglas de limpieza, no se transformaron valores, no se homologaron nombres, no se eliminaron duplicados, no se hizo matching entre atletas y no se escribieron archivos dentro de `data/raw`. El análisis de calidad y las decisiones de transformación quedan para el Bloque 3.
