# Fase 3 — Modelo funcional y carga en MongoDB

**Proyecto:** OlimpiadasF1 · Grupo 7  
**Base MongoDB:** `OlimpiadasF3`  
**Servidor verificado:** MongoDB 8.3.7, local en `localhost:27017`  
**Ejecución:** 11 de octubre de 2026 · horarios registrados en UTC en los reportes CSV  
**Alcance realizado:** incisos a y b (modelo documental, carga, colecciones, índices y scripts). Los incisos c y d corresponden a los integrantes asignados; no se implementaron aquí.

## Objetivo y criterio de conservación

Transformar los diez CSV vigentes de `data/processed/` en documentos de MongoDB con un diseño orientado a los accesos previstos: historial por atleta y resultados por entidad geográfica/edición. Se conservan los agregados de población, los NOC sin entidad geográfica, las identidades y los resultados; no se asigna significado de país a un agregado ni se inventa una relación ausente.

Las participaciones se repiten intencionalmente en dos vistas de lectura: dentro del documento del atleta y dentro de la vista entidad/edición. No son filas nuevas ni deben sumarse entre colecciones. En ambas vistas se conserva `id_participacion`, y la auditoría confirma que cada ID aparece una sola vez dentro de cada vista.

## Diseño: cuatro colecciones

| Colección | Raíz y contenido | Uso principal |
|---|---|---|
| `atletas` | Un documento por `id_atleta`, con atributos del CSV y el arreglo completo `participaciones`. Cada participación conserva sus campos y anida edición/sede, evento/disciplina/deporte y NOC. | Buscar un atleta y desplegar su historial sin reconstruir joins entre tablas. |
| `entidades_geograficas` | Un documento por cada fila de `entidad_geografica.csv`, con nombre y código literales, serie `poblacion_anual`, NOC explícitamente vinculados, sedes y ediciones organizadas conocidas. | Consultar país o agregado, población histórica y sedes/ediciones. No se añadió un tipo país/región inferido. |
| `participaciones_por_pais` | Documentos particionados por entidad geográfica y edición, con atletas, eventos y resultados resumidos. Las participaciones sin entidad se guardan en buckets `NOC_SIN_ENTIDAD` o `SIN_NOC_SIN_ENTIDAD`; no se presentan como países. | Obtener resultados, participantes y medallas de una entidad por año/temporada sin cargar un único documento nacional ilimitado. |
| `catalogo_olimpico` | Colección polimórfica tipada con documentos `DEPORTE`, `DISCIPLINA`, `EVENTO`, `EDICION_OLIMPICA`, `SEDE` y `NOC`, con referencias descriptivas anidadas. | Navegar catálogos e identificar de forma explícita la jerarquía deporte → disciplina → evento y edición → sede. |

La colección `participaciones_por_pais` se particiona por edición porque un único documento por país podría crecer con el historial y acercarse al máximo BSON. MongoDB limita cada documento a 16 MiB; el tamaño se midió con `$bsonSize` después de la carga. La recomendación oficial es modelar según los patrones de acceso y evitar arreglos ilimitados ([límite de BSON](https://www.mongodb.com/docs/manual/reference/limits/), [datos embebidos](https://www.mongodb.com/docs/manual/data-modeling/embedding/), [arreglos ilimitados](https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/unbounded-arrays/)).

### Raíces JSON y recorrido de las consultas

Los nombres de los diez CSV identifican archivos de entrada; no determinan las colecciones. Las dos raíces de lectura principales son:

```text
atletas (raíz: id_atleta)
  datos personales + país de nacimiento/nacionalidad/fallecimiento
  participaciones[]
    edición → sede → entidad geográfica
    evento → disciplina → deporte
    NOC → entidad geográfica
    equipo, resultado, posición, medalla y medidas registradas

participaciones_por_pais (raíz: entidad/NOC + edición)
  entidad + edición → sede
  participaciones[]
    atleta resumido + evento → disciplina → deporte
    NOC, equipo, resultado, posición, medalla y medidas registradas
```

Para el inciso c, se busca un documento de `atletas` por nombre y se recorre su arreglo `participaciones`: no hace falta reconstruir las relaciones entre CSV. Para el inciso d, se lee `entidades_geograficas` por nombre para obtener población, NOC y sedes, y se leen las particiones de `participaciones_por_pais` por `id_entidad`. Esas particiones llevan resultados y atletas por edición; la ficha completa de un atleta se obtiene por `id_atleta` cuando se solicite una biografía. Los NOC sin entidad permanecen en sus buckets explícitos. La partición por edición evita que el historial de un país crezca sin límite dentro de un solo documento.

| CSV de entrada | Representación en MongoDB |
|---|---|
| `atleta.csv` | Documento raíz de `atletas`; datos identificativos resumidos también en la vista país. |
| `participacion.csv` | Arreglo anidado en `atletas` y copia de lectura en `participaciones_por_pais`, ambas con el mismo `id_participacion`. |
| `entidad_geografica.csv`, `poblacion.csv` | Documento de `entidades_geograficas` con serie `poblacion_anual`; referencias descriptivas en otras vistas. |
| `noc.csv` | NOC anidados y registros tipados en `catalogo_olimpico`, incluidos los que no tienen entidad. |
| `sede.csv`, `edicion_olimpica.csv` | Edición y sede embebidas en las participaciones; registros tipados en el catálogo. |
| `deporte.csv`, `disciplina.csv`, `evento.csv` | Jerarquía evento → disciplina → deporte embebida en resultados; catálogo para conservar incluso registros sin participaciones. |

Una comprobación con `explain("executionStats")` de las rutas básicas examinó un documento y una clave para `atletas.nombre = Michael Phelps`, un documento y una clave para `entidades_geograficas.nombre = Guatemala`, y 20 documentos y 20 claves para las particiones de Guatemala por `id_entidad`. Se usaron `ix_atletas_nombre`, `ix_entidades_nombre` e `ix_part_pais_edicion`, respectivamente. Son observaciones de esta instalación local, no una garantía de tiempo fijo.

## Relaciones y casos especiales preservados

- `id_pais_nacionalidad` se conserva separado de NOC. Para la vista de representación por país se utiliza únicamente la relación explícita `NOC.id_entidad`; no se equipara `codigo_noc` con `codigo_pais`.
- **365,916** participaciones se asignaron a una entidad mediante `NOC.id_entidad`. **1,877** no tienen entidad geográfica; se guardaron en buckets NOC/sin-NOC y no se contaron como participaciones de un país.
- Hay **55** filas en las que `id_pais_nacionalidad` difiere de la entidad explícita del NOC. Ambos datos se conservaron sin sobrescribir uno con el otro; la vista país representa el NOC.
- Las 282 entidades geográficas se conservaron tal como aparecen. Los agregados estadísticos permanecen con su nombre y código; no se agregó un atributo que los clasifique como países.
- Hay **cinco NOC sin entidad geográfica**. Sus participaciones permanecen en los buckets sin entidad, junto con una participación que no trae NOC.
- **Ocho ediciones** tienen `id_sede` vacío en los CSV. Se guardaron con `sede: null` y no se completaron por inferencia; por ello, la lista de años organizados refleja únicamente las sedes informadas en processed.
- Las cadenas descriptivas se conservaron exactamente. Solo las celdas vacías se representan como BSON `null`; textos como `NA` en columnas descriptivas no se sustituyeron globalmente.
- Las fechas ISO se guardan como BSON Date en UTC; los enteros como Int32/Int64 y los decimales como Decimal128 para evitar convertirlos a binario aproximado.
- Los CSV consolidados no contienen linaje por campo/fuente original. Se conserva `origen_csv` para identificar el CSV procesado de cada documento y los identificadores presentes, pero no se inventa una atribución a una de las cuatro fuentes originales.

## Fuente y conteos de entrada

Se procesaron exactamente estos diez archivos, sin modificarlos:

| CSV | Filas |
|---|---:|
| `entidad_geografica.csv` | 282 |
| `poblacion.csv` | 17,024 |
| `noc.csv` | 236 |
| `atleta.csv` | 167,295 |
| `sede.csv` | 42 |
| `edicion_olimpica.csv` | 61 |
| `deporte.csv` | 65 |
| `disciplina.csv` | 117 |
| `evento.csv` | 2,069 |
| `participacion.csv` | 367,793 |
| **Total de filas fuente** | **554,984** |

Los conteos actuales fueron leídos de `data/processed/`; no se reutilizaron conteos históricos de otras ejecuciones. El manifiesto `processed_source_manifest.csv` registra SHA-256 antes/después de preparar la carga; `load_validation.csv` vuelve a comparar los diez hashes con los archivos vigentes.

## Resultado de la ejecución

Base `OlimpiadasF3`; cuatro colecciones creadas con validadores JSON Schema en modo `strict` y acción `error`.

| Colección | Documentos | Participaciones/filas anidadas |
|---|---:|---:|
| `atletas` | 167,295 | 367,793 |
| `entidades_geograficas` | 282 | 17,024 observaciones de población |
| `participaciones_por_pais` | 4,856 particiones | 367,793 |
| `catalogo_olimpico` | 2,590 | — |

**Resultado tras la revisión del diseño:** 42 validaciones posteriores PASS; 0 FAIL. Se compararon 4,182,375 campos de atleta y 5,516,895 campos de participación en su documento de atleta contra los CSV; diferencias: **0**. La vista país/NOC se comparó también en sus 15 campos de participación: 5,516,895 comparaciones, **0 diferencias**. La validación adicional contrasta los campos de entidad geográfica, población y los seis tipos del catálogo con los CSV respectivos. De los nombres en `atleta.csv`, 25,911 contienen caracteres no ASCII; se compararon exactamente todos los nombres contra MongoDB y se encontraron **0 diferencias**.

La revisión detectó que los 2,069 registros `EVENTO` del catálogo tenían un envoltorio redundante: `disciplina` contenía de nuevo el evento antes de la disciplina. El 12 de octubre de 2026 se verificó que los datos repetidos coincidían, se corrigió esa jerarquía en los 2,069 documentos y se ajustó el cargador para futuras ejecuciones. Ahora cada `EVENTO.disciplina` contiene directamente `id_disciplina`, `nombre`, `id_deporte` y `deporte`. La validación comprueba esta forma en todos los eventos. El cambio no alteró los diez CSV ni las otras tres colecciones.

### Tamaños BSON medidos en MongoDB

| Colección | Máximo | Promedio | Límite |
|---|---:|---:|---:|
| `atletas` | 57,025 bytes | 2,757 bytes | 16,777,216 bytes |
| `entidades_geograficas` | 3,491 bytes | 2,543 bytes | 16,777,216 bytes |
| `participaciones_por_pais` | 1,338,035 bytes | 61,235 bytes | 16,777,216 bytes |
| `catalogo_olimpico` | 426 bytes | 275 bytes | 16,777,216 bytes |

Todos los máximos están por debajo del límite. Antes de insertar, el máximo conservador del ensamblado fue 1,512,131 bytes (`bson_size_preflight.csv`); después de persistir, MongoDB midió el máximo real con `$bsonSize`: 1,338,035 bytes (`bson_size_report.csv`).

## Índices adicionales

Se crearon/verificaron **11 índices secundarios**, además de los `_id_` automáticos:

| Índice | Uso |
|---|---|
| `ix_atletas_nombre` | Nombre principal del atleta. |
| `ix_atletas_nombre_completo` | Nombre completo alternativo. |
| `ix_atletas_nombre_usado` | Nombre usado en las fuentes. |
| `ix_atletas_participaciones_edicion` | Filtro del historial embebido por edición. |
| `ix_entidades_nombre` | Búsqueda literal de entidad/agregado. |
| `ix_entidades_codigo_pais` | Búsqueda por código disponible; excluye nulos. |
| `ix_entidades_poblacion_anio` | Acceso por año a la serie de población. |
| `ix_part_pais_edicion` | Entidad + año + temporada. |
| `ix_part_pais_medalla` | Filtrar medallas por entidad. |
| `ix_catalogo_tipo_id` | Resolver referencias por tipo e ID. |
| `ix_catalogo_tipo_nombre` | Buscar dentro de cada catálogo por nombre. |

El detalle de claves y motivo está en `indexes_created.csv`.

## Scripts y orden reproducible

**La base documentada ya está cargada en `localhost:27017`.** El Compose añadido para instalaciones nuevas publica otra instancia en `localhost:27018`; no contiene automáticamente los datos de `27017`. Los lanzadores `run_import.ps1` y `run_import.sh` sirven para esa instalación nueva y vacía, no para verificar o sobrescribir la base vigente. El [manual técnico y de evidencias](../Evidence/Evidences_Fase3.md) utiliza comandos de comprobación dirigidos a `27017`, con resultados esperados y espacios para capturas reales. Los mapas JSON de las cuatro colecciones están en `fase3/db structure/`.

Si se trabaja con una carga anterior al ajuste de la jerarquía del catálogo, ejecutar primero `05_correct_catalog_event_hierarchy.js` en modo lectura; el script informa cuántos documentos requieren corrección. Para aplicarla, requiere `OLIMPIADAS_MONGO_APPLY=1`. Es idempotente y verifica los 2,069 eventos antes y después. El cargador actual ya produce la jerarquía corregida.

`02_load_processed.js` exige exactamente los diez archivos y conteos vigentes, valida tipos, claves y referencias, mide BSON y por defecto no escribe. Para aplicar, requiere explícitamente `OLIMPIADAS_MONGO_APPLY=1`; además aborta si las colecciones destino ya contienen datos. No ejecuta `DROP`, `DELETE` ni `TRUNCATE`.

`02a_backfill_nested_athlete_id.js` se ejecutó una vez para completar `id_atleta` dentro de cada subdocumento de participación. Fue una actualización aditiva: 367,793 subdocumentos en 167,293 perfiles, derivados de la relación padre ya existente; no se recargaron ni borraron documentos. El script de carga actual ya incluye ese campo para futuras ejecuciones.

La carga total se midió en **110.816 s** (23:22:07.300–23:23:58.116 UTC); la creación de índices en **3.453 s** (23:25:30.954–23:25:34.407 UTC); el ajuste aditivo tomó **20.573 s**. Los tiempos de carga y del ajuste están registrados en sus reportes; los índices llevan inicio/fin por índice.

## Reportes generados

- `fase3/docs/mongodb/processed_source_manifest.csv`: SHA-256 de los diez CSV antes/después de preparar la carga.
- `fase3/docs/mongodb/preflight_validation.csv`: conteos, claves duplicadas, referencias huérfanas, conversiones y casos conservados sin inferencia.
- `fase3/docs/mongodb/preflight_metrics.csv`: duración real de la pasada de solo lectura.
- `fase3/docs/mongodb/bson_size_preflight.csv`: medición de documentos antes de la carga.
- `fase3/docs/mongodb/bson_size_report.csv`: máximo BSON por colección; post-carga, medido con `$bsonSize`.
- `fase3/docs/mongodb/load_metrics.csv`: etapas, filas y tiempos reales de lectura/carga, con inicio/fin UTC.
- `fase3/docs/mongodb/indexes_created.csv`: índices, claves, motivo e instante de creación/verificación.
- `fase3/docs/mongodb/migration_adjustments.csv`: registro del ajuste aditivo de la vista embebida.
- `fase3/docs/mongodb/load_validation.csv`: conteos, comparación exacta de campos, Unicode, dominios, hashes, validadores e índices.
- `fase3/docs/mongodb/catalog_event_hierarchy_correction_20261012.csv`: resultado histórico de la corrección puntual del catálogo.

**Estado:** incisos a y b ejecutados en MongoDB y auditados contra los CSV procesados. No se declara la Fase 3 completa: faltan los métodos de consulta de atleta y país (incisos c y d) y la revisión del equipo/ingeniero. No se modificaron SQL Server ni `data/processed/` durante la carga.
