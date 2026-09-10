# Evidencias del Bloque 5 — Modelo físico SQL Server

## 1. Estado y alcance

Se creó y validó el modelo físico SQL Server 2025 para `OlimpiadasDB`, utilizando exclusivamente el schema `olympics`.

Se crearon exactamente diez tablas finales. No se crearon tablas en `dbo`, no se crearon tablas auxiliares del modelo lógico y no se cargaron datos.

El Bloque 6 no fue iniciado y el Bloque 5 no se declara aprobado hasta revisión externa.

## 2. Archivos generados

- `scripts/sql/01_create_tables.sql`: DDL idempotente no destructivo.
- `scripts/sql/02_validate_schema.sql`: validación de metadatos, constraints, tablas extra y filas.
- `scripts/python/04_validate_physical_model.py`: validación de capacidades físicas contra los diez CSV finales.
- `docs/schema/physical_model_validation.csv`: resultado de la validación física de las 66 columnas del modelo.
- `docs/schema/edition_season_analysis.csv`: análisis de las 63 ediciones y resumen por temporada.

Comandos utilizados:

```powershell
.\.venv\Scripts\python.exe .\scripts\python\04_validate_physical_model.py
```

El DDL se ejecutó sobre `OlimpiadasDB` con las diez tablas inicialmente vacías. No se ejecutaron `INSERT`, `BULK INSERT`, `OPENROWSET`, `bcp` ni scripts de carga.

## 3. Tablas finales

1. `olympics.ENTIDAD_GEOGRAFICA`
2. `olympics.POBLACION`
3. `olympics.NOC`
4. `olympics.ATLETA`
5. `olympics.SEDE`
6. `olympics.EDICION_OLIMPICA`
7. `olympics.DEPORTE`
8. `olympics.DISCIPLINA`
9. `olympics.EVENTO`
10. `olympics.PARTICIPACION`

No se crearon `FUENTE`, `RESULTADO`, `MEDALLA` ni `TIPO_MEDALLA`.

## 4. Tipos físicos y ajustes respecto al ER

Se utilizó `NVARCHAR` para preservar tildes, nombres internacionales y caracteres Unicode.

Los tipos principales son:

| Tabla | Columnas principales |
|---|---|
| `ENTIDAD_GEOGRAFICA` | `id_entidad INT`, `nombre NVARCHAR(150)`, `codigo_pais CHAR(3)` |
| `POBLACION` | `id_entidad INT`, `anio SMALLINT`, `poblacion BIGINT` |
| `NOC` | `id_noc INT`, `codigo_noc CHAR(3)`, `nombre_noc NVARCHAR(150)`, `id_entidad INT`, `notas NVARCHAR(500)` |
| `ATLETA` | IDs `BIGINT`/`INT`, fechas `DATE`, medidas `DECIMAL(5,2)`, coordenadas `DECIMAL(9,6)` |
| `SEDE` | `id_sede INT`, `nombre NVARCHAR(150)`, `id_pais INT` |
| `EDICION_OLIMPICA` | `id_edicion INT`, `anio SMALLINT`, `temporada NVARCHAR(20)`, `id_sede INT` |
| `DEPORTE` | `id_deporte INT`, `nombre NVARCHAR(150)` |
| `DISCIPLINA` | `id_disciplina INT`, `id_deporte INT`, `nombre NVARCHAR(150)` |
| `EVENTO` | `id_evento BIGINT`, `id_disciplina INT`, `nombre NVARCHAR(300)` |
| `PARTICIPACION` | IDs `BIGINT`/`INT`, atributos textuales `NVARCHAR`, medidas `DECIMAL(5,2)`, `empatado BIT` |

Se realizaron dos ajustes físicos explícitos porque los CSV finales exceden las capacidades indicadas literalmente en el ER:

- `EDICION_OLIMPICA.temporada`: `NVARCHAR(20)` en lugar de `NVARCHAR(10)`. El máximo real es 18 caracteres y existen seis valores: `Summer`, `Winter`, `Intercalated Games`, `Summer Youth`, `Winter Youth` y `Equestrian`.
- `ATLETA.titulos`: `NVARCHAR(2000)` en lugar de `NVARCHAR(500)`. El máximo real es 1,518 caracteres.

No se truncaron valores ni se suavizaron silenciosamente las restricciones.

Los datos de latitud y longitud caben en el rango de `DECIMAL(9,6)`, que es el tipo definido por el ER. Los CSV contienen más de seis decimales en algunos casos; antes del Bloque 6 debe confirmarse si la precisión adicional debe conservarse aumentando el tipo físico.

## 5. Claves primarias

- `ENTIDAD_GEOGRAFICA`: `id_entidad`.
- `POBLACION`: `(id_entidad, anio)`.
- `NOC`: `id_noc`.
- `ATLETA`: `id_atleta`.
- `SEDE`: `id_sede`.
- `EDICION_OLIMPICA`: `id_edicion`.
- `DEPORTE`: `id_deporte`.
- `DISCIPLINA`: `id_disciplina`.
- `EVENTO`: `id_evento`.
- `PARTICIPACION`: `id_participacion`.

## 6. Claves foráneas

- `POBLACION.id_entidad` → `ENTIDAD_GEOGRAFICA.id_entidad`.
- `NOC.id_entidad` → `ENTIDAD_GEOGRAFICA.id_entidad`, nullable.
- `ATLETA.id_pais_nacimiento`, `id_pais_nacionalidad`, `id_pais_fallecimiento` → `ENTIDAD_GEOGRAFICA.id_entidad`, nullable.
- `SEDE.id_pais` → `ENTIDAD_GEOGRAFICA.id_entidad`.
- `EDICION_OLIMPICA.id_sede` → `SEDE.id_sede`, nullable.
- `DISCIPLINA.id_deporte` → `DEPORTE.id_deporte`.
- `EVENTO.id_disciplina` → `DISCIPLINA.id_disciplina`.
- `PARTICIPACION.id_atleta` → `ATLETA.id_atleta`.
- `PARTICIPACION.id_edicion` → `EDICION_OLIMPICA.id_edicion`.
- `PARTICIPACION.id_evento` → `EVENTO.id_evento`.
- `PARTICIPACION.id_noc` → `NOC.id_noc`, nullable.
- `PARTICIPACION.id_pais_nacionalidad` → `ENTIDAD_GEOGRAFICA.id_entidad`, nullable.

`NOC.id_entidad` permanece nullable; los cinco NOC sin entidad segura no fueron modificados para conseguir validaciones artificiales.

## 7. Restricciones UNIQUE

- `NOC(codigo_noc)`: los 236 códigos finales son distintos y no hay NULL.
- `SEDE(nombre, id_pais)`.
- `EDICION_OLIMPICA(anio, temporada)`.
- `DEPORTE(nombre)`.
- `DISCIPLINA(id_deporte, nombre)`.
- `EVENTO(id_disciplina, nombre)`.

No se creó `UNIQUE` sobre `ENTIDAD_GEOGRAFICA.codigo_pais`, porque existen entidades históricas o agregadas y códigos NULL.

## 8. Restricciones CHECK

- `EDICION_OLIMPICA.temporada` se limita a los seis valores observados en los CSV finales.
- `PARTICIPACION.medalla` permite únicamente `Gold`, `Silver`, `Bronze` o NULL.
- `PARTICIPACION.posicion` debe ser mayor que cero o NULL.

No se agregaron checks de edad, altura o peso que pudieran rechazar valores históricos atípicos.

## 9. Validación física contra CSV

El reporte `docs/schema/physical_model_validation.csv` contiene exactamente 66 columnas evaluadas, incluyendo explícitamente `ATLETA.id_pais_nacimiento`, `ATLETA.id_pais_nacionalidad` y `ATLETA.id_pais_fallecimiento`.

```text
COBERTURA: 66/66
PASS: 63
FAIL: 3
```

Los tres `FAIL` son pérdidas de precisión por el tipo físico actual, no columnas faltantes ni desbordamientos de rango:

| Tabla.columna | Tipo SQL actual | Máx. enteros observados | Máx. decimales observados | Valores que requieren redondeo | Estado |
|---|---:|---:|---:|---:|---|
| `ATLETA.latitud` | `DECIMAL(9,6)` | 2 | 16 | 63,726 | FAIL |
| `ATLETA.longitud` | `DECIMAL(9,6)` | 3 | 16 | 62,549 | FAIL |
| `PARTICIPACION.peso_kg_registrado` | `DECIMAL(5,2)` | 3 | 13 | 6 | FAIL |

Los otros cuatro DECIMAL no requieren redondeo con los valores actuales:

| Tabla.columna | Tipo SQL actual | Máx. enteros | Máx. decimales | Redondeo |
|---|---:|---:|---:|---:|
| `ATLETA.altura_cm` | `DECIMAL(5,2)` | 3 | 0 | 0 |
| `ATLETA.peso_kg` | `DECIMAL(5,2)` | 3 | 1 | 0 |
| `PARTICIPACION.edad` | `DECIMAL(5,2)` | 2 | 0 | 0 |
| `PARTICIPACION.altura_cm_registrada` | `DECIMAL(5,2)` | 3 | 0 | 0 |

La validación no declara PASS cuando existe pérdida de precisión. El rango entero de las siete columnas sí cabe en sus tipos actuales.

Se verificaron especialmente:

- longitudes máximas de texto;
- rangos de `INT`, `SMALLINT` y `BIGINT`;
- población máxima de 8,024,997,028;
- años entre 1896 y 2024;
- temporadas observadas;
- valores de sexo `F`, `Female`, `M`, `Male`;
- estados `DNF`, `DNS`, `DQ`;
- medallas `Gold`, `Silver`, `Bronze`;
- códigos de país y NOC de tres caracteres;
- rangos de latitud y longitud;
- fechas ISO compatibles con `DATE`;
- medidas numéricas de atleta y participación;
- valores booleanos de `empatado`.

### Precisión y escala

La lectura exacta con `Decimal` separa los dígitos enteros de los decimales observados y detecta valores cuyos dígitos posteriores a la escala SQL serían redondeados por SQL Server. Para conservar todos los valores actuales sin pérdida, las recomendaciones mínimas son:

- `ATLETA.latitud`: `DECIMAL(18,16)`.
- `ATLETA.longitud`: `DECIMAL(19,16)`.
- Si ambas coordenadas deben compartir tipo: `DECIMAL(19,16)`.
- `PARTICIPACION.peso_kg_registrado`: `DECIMAL(16,13)`.

No se modificó el DDL ni ningún CSV. `DECIMAL(9,6)` no conserva exactamente las coordenadas actuales; requiere redondeo en 63,726 latitudes y 62,549 longitudes.

## 10. Validación real del schema

`02_validate_schema.sql` consultó `sys.tables`, `sys.columns`, `sys.key_constraints`, `sys.foreign_keys`, `sys.check_constraints`, índices y particiones.

Resultados:

| Validación | Resultado |
|---|---:|
| Tablas esperadas bajo `olympics` | 10/10 |
| Tablas extra bajo `olympics` | 0 |
| Tablas finales en `dbo` | 0 |
| Columnas tipo/longitud/NULL | 66/66 PASS |
| PK y UNIQUE inspeccionados | 16 |
| FK inspeccionadas | 14 |
| CHECK inspeccionados | 3 |
| Tablas vacías | 10/10 |

Las diez tablas quedaron vacías al finalizar este bloque.

La sección adicional de `02_validate_schema.sql` inspecciona `sys.columns.precision` y `sys.columns.scale` para las siete columnas DECIMAL y compara cada valor con el contrato esperado del DDL. La validación SQL de metadatos resulta PASS para los tipos actualmente definidos (`DECIMAL(5,2)` y `DECIMAL(9,6)`); esto confirma la estructura instalada, pero no elimina los tres FAIL de capacidad observados contra los CSV.

## 11. Análisis de temporadas y ediciones

`docs/schema/edition_season_analysis.csv` contiene 63 filas `EDITION` y seis filas `SEASON_SUMMARY`, sin modificar `data/processed`.

| Temporada | Ediciones | Años | Participaciones |
|---|---:|---|---:|
| `Summer` | 31 | 1896–2024, incluyendo 1906 | 709,543 |
| `Winter` | 24 | 1924–2022 | 108,387 |
| `Intercalated Games` | 1 | 1906 | 2,300 |
| `Summer Youth` | 3 | 2010, 2014, 2018 | 1,391 |
| `Winter Youth` | 3 | 2012, 2016, 2020 | 4,684 |
| `Equestrian` | 1 | 1956 | 300 |

El archivo incluye la combinación `id_edicion`, `anio`, `temporada`, `id_sede`, `sede` y la cantidad de participaciones por edición.

Hallazgos conceptuales:

- `Equestrian` corresponde a los eventos ecuestres de 1956 realizados en Estocolmo por las restricciones australianas de cuarentena. No representa una edición olímpica independiente: debe asociarse a la edición Summer 1956, conservando la sede/ubicación específica si el diseño lo permite.
- `Intercalated Games` corresponde a Atenas 1906. La documentación IOC/Olympic Studies Centre la trata como edición intercalada/intermedia y no como Juegos Olímpicos oficiales modernos. No es coherente como edición ordinaria del alcance actual.
- `Summer Youth`: 2010 Singapur, 2014 Nanjing y 2018 Buenos Aires; son Juegos Olímpicos de la Juventud de verano, no ediciones Summer ordinarias.
- `Winter Youth`: 2012 Innsbruck, 2016 Lillehammer y 2020 Lausanne; son Juegos Olímpicos de la Juventud de invierno, no ediciones Winter ordinarias.
- `Summer` y `Winter` ordinarias son coherentes con el modelo, aunque algunas filas carecen de `id_sede`; esa ausencia debe revisarse en Bloque 4 antes de una aprobación final del alcance.

Por tanto, se requiere una revisión temporal del Bloque 4 antes de aprobar el Bloque 5: definir si las categorías no oficiales/juveniles se excluyen del alcance, se modelan separadamente o se documentan con una política explícita. No se aplicó ninguna de esas decisiones en este bloque.

Referencias IOC/Olympic Studies Centre utilizadas para la interpretación: [The Olympic Movement](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3703315&parentDocumentId=172552&skipCopyright=true&skipWatermark=true), [Historical Archives](https://library.olympics.com/Default/basicfilesdownload.ashx?itemGuid=2ECE9BE9-EA5F-4F0F-97DF-84C75B6BC60A), [Olympic Games style guide](https://library.olympics.com/Default/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=172063&skipWatermark=true) y [Youth Olympic Games](https://library.olympics.com/network/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3156139&parentDocumentId=3156138).

## 12. Estrategia de reejecución

`01_create_tables.sql` no ejecuta `DROP TABLE`. Si una tabla ya existe, la conserva y continúa; la estructura se verifica con `02_validate_schema.sql`.

La recreación destructiva no está automatizada. Si se requiere un entorno limpio, debe utilizarse una base de desarrollo descartable y volver a ejecutar primero `00_create_database.sql` y después `01_create_tables.sql`.

## 13. Evidencias visuales previstas

Las capturas deben mostrar fecha y hora actual del sistema:

1. [ ] ejecución de `01_create_tables.sql`;
2. [ ] listado de las diez tablas bajo schema `olympics`;
3. [ ] estructura y tipos de columnas;
4. [ ] PK y UNIQUE;
5. [ ] FK;
6. [ ] CHECK constraints;
7. [ ] validación general de `02_validate_schema.sql`;
8. [ ] confirmación de las diez tablas vacías.

No se cargaron datos y no se inició el Bloque 6.

## 14. Decisiones pendientes antes del Bloque 6

- Decidir si latitud y longitud deben cambiar a un tipo que conserve todos los valores actuales; la recomendación mínima conjunta es `DECIMAL(19,16)`.
- Decidir el tratamiento de `PARTICIPACION.peso_kg_registrado`, cuyo tipo actual redondearía 6 valores; la recomendación mínima observada es `DECIMAL(16,13)`.
- Revisar en Bloque 4 `Equestrian`, `Intercalated Games`, `Summer Youth` y `Winter Youth` antes de aceptar esas categorías como `EDICION_OLIMPICA`.
- Revisar externamente los dos ajustes de capacidad: `temporada NVARCHAR(20)` y `titulos NVARCHAR(2000)`.
- Ejecutar la carga únicamente después de revisar el DDL, las restricciones y los archivos finales.
