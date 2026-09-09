# Evidencias del Bloque 4 — Matching, deduplicación y consolidación

## Estado

El Bloque 4 fue regenerado después de la revisión técnica. No se declara aprobado y los CSV finales no se consideran todavía aptos para carga SQL porque permanece una validación en `FAIL`: una participación sin edición. La jerarquía deporte-disciplina quedó resuelta sin pendientes. No se inició el Bloque 5.

## Objetivo y ejecución

El proceso consolida las cuatro fuentes olímpicas en diez archivos compatibles con el modelo ER, con trazabilidad de matching, geografía, nacionalidad, jerarquía deportiva y deduplicación.

```powershell
& '.\.venv\Scripts\python.exe' '.\scripts\python\03_match_and_consolidate.py'
```

Punto de entrada: `scripts/python/03_match_and_consolidate.py`.

## Matching de atletas corregido

Las claves de nombre, sexo y texto normalizado son auxiliares; no sustituyen el valor almacenado. Cuando sexo o NOC son comparables, cualquier incompatibilidad elimina obligatoriamente al candidato aunque el conjunto quede vacío.

Reglas finales:

- `DETERMINISTIC_STRONG`: nombre auxiliar exacto, sexo comparable igual, NOC comparable compatible y candidato único.
- `DETERMINISTIC_CONTEXTUAL`: después del filtro obligatorio de sexo/NOC, candidato único por año, deporte o disciplina y evento compartidos.
- `DETERMINISTIC_AMBIGUOUS`: la evidencia no distingue un candidato único; no se fusiona.
- `NEW_SOURCE_ENTITY`: no existe candidato fuerte ni contextual; se conserva como identidad separada.
- Matching fuzzy automático: 0.

Conteos externos finales:

- STRONG: 177,741.
- CONTEXTUAL: 496.
- AMBIGUOUS: 2,857.
- UNMATCHED: 190,415.
- Identidades base de Fuente 1: 145,500.
- Identidades globales finales: 338,772.

Contra la ejecución anterior se compararon 517,009 identidades de fuente. Cambiaron 14,545 matches previamente existentes al considerar conjuntamente ID global, estado o tipo: 14,542 cambiaron de ID global, 893 dejaron de estar matched y 14,386 cambiaron de tipo. Además, 1,623 casos antes no matched pasaron a matched. El detalle está en `docs/consolidation/athlete_match_changes.csv`.

## Alineación Fuente 1 RAW/CLEAN

`fuente1_raw_results.csv` y `fuente1_clean_results.csv` se alinearon mediante una clave de contenido estable, sin asumir correspondencia por número de fila. Cuando había varios candidatos, el match solo se consideró seguro si `year`, `season`, `posicion` y `empatado` coincidían entre todos ellos.

- Filas RAW: 308,408.
- Filas CLEAN: 308,408.
- Matches seguros: 299,462.
- No encontrados: 8,675.
- Ambiguos: 271.
- Posiciones enriquecidas: 48,337.
- Valores `empatado` enriquecidos: 54,658.
- Atributos enriquecidos totales: 102,995.
- Año o temporada enriquecidos: 0.

La participación histórica asociada a `1888-89 Zappas Olympic Games` sigue sin año y temporada simples en ambos archivos. Por ello su `id_edicion` permanece nulo; no se inventó una edición.

Adicionalmente, la única disciplina vacía de 2022 se resolvió como `Alpine Skiing (Skiing)`: las otras 72 filas de la misma edición y evento `Slalom, Women (Olympic)` contienen unánimemente esa disciplina. La evidencia está en `docs/consolidation/source1_missing_discipline_enrichment.csv`.

## Entidades geográficas y NOC

La construcción geográfica compara primero código de población, aliases explícitos y nombre canónico. Un código NOC diferente del ISO3 ya no crea por sí solo otra entidad.

- ENTIDAD_GEOGRAFICA anterior: 363.
- ENTIDAD_GEOGRAFICA final: 282.
- Duplicados conceptuales corregidos: 81.
- Posibles duplicados normalizados restantes: 0.
- Registros de población conservados: 17,024, incluidos los agregados.
- NOC resueltos: 231.
- NOC sin entidad segura: 5.

La auditoría está en `docs/consolidation/geographic_entity_duplicates.csv` y los matches NOC en `data/intermediate/matching/noc_entity_matches.csv`.

## Nacionalidad de participación

`PARTICIPACION.id_pais_nacionalidad` ya no se genera siempre nulo. Solo se utiliza el valor de nacionalidad disponible y se mapea por código o nombre/alias exacto; no se utiliza el NOC como sustituto automático.

- Participaciones finales con nacionalidad resuelta: 81.
- Valores originales distintos resueltos: 20.
- Valores de nacionalidad presentes pero no resolubles: 0.
- Participaciones sin valor de nacionalidad en la fuente: 826,525.

Reporte: `docs/consolidation/participation_nationality_mapping.csv`.

## Deporte, disciplina y evento

La jerarquía final conserva nombres canónicos y no almacena las claves auxiliares normalizadas como nombres. Las etiquetas de Fuente 1 con forma `Discipline (Sport)` se interpretan por la jerarquía explícita de la propia fuente. Las demás se contrastan con el programa y la evolución olímpica oficiales:

- https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3415338&parentDocumentId=3415336&skipCopyright=true&skipWatermark=true
- https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=174689&parentDocumentId=174657&skipCopyright=true&skipWatermark=true

Resultado del reporte por fuente y valor:

- Mapeos resueltos: 313.
- Filas cubiertas por mapeos resueltos: 832,189.
- Pendientes: 0.

Las etiquetas genéricas o multivalor se resolvieron mediante patrones inequívocos del evento. Para las 17 filas históricas cuyo valor fuente era `Wrestling` pero cuyos eventos pertenecían a Glíma, atletismo, remo o ciclismo, se aplicó una regla de dos pasos: primero se resolvió la fila con evento explícito y después se propagó únicamente cuando el mismo atleta, fuente y edición tenían una sola disciplina compañera ya resuelta. No hubo asignaciones cuando el contexto ofrecía más de una alternativa.

La ausencia de pendientes deportivos no hace que los CSV sean aptos para carga SQL: todavía existe una participación sin `id_edicion`, que viola el modelo obligatorio.

## Deduplicación regenerada

El cambio de `id_atleta` obligó a reconstruir participaciones y recalcular las claves lógicas. Solo se excluyeron duplicados exactos demostrables; `PROBABLE_DUPLICATE` y `CONFLICT` se conservaron.

| Métrica | Ejecución anterior | Ejecución corregida | Cambio |
|---|---:|---:|---:|
| Participaciones de entrada | 832,189 | 832,189 | 0 |
| Participaciones finales | 826,666 | 826,606 | -60 |
| Exactos entre fuentes excluidos | 4,060 | 4,120 | +60 |
| Exactos dentro de fuente excluidos | 1,463 | 1,463 | 0 |
| PROBABLE_DUPLICATE conservados | 139,940 | 142,148 | +2,208 |
| CONFLICT conservados | 263 | 264 | +1 |

Fuente 4 continúa con 100/100 matches exactos contra Fuente 2 y sus 100 filas se excluyen de la participación consolidada.

## Conteos finales

| Entidad | Filas |
|---|---:|
| entidad_geografica | 282 |
| poblacion | 17,024 |
| noc | 236 |
| atleta | 338,772 |
| sede | 42 |
| edicion_olimpica | 63 |
| deporte | 65 |
| disciplina | 117 |
| evento | 3,106 |
| participacion | 826,606 |

## Validaciones finales

`docs/consolidation/final_validations.csv` contiene 56 validaciones:

- PASS: 55.
- FAIL: 1.
- Todas las PK son únicas.
- Todas las FK no nulas apuntan a registros existentes.
- Todos los campos obligatorios cumplen `NOT NULL`, excepto `PARTICIPACION.id_edicion` en una fila.
- Las 42 sedes tienen país.
- No hay nombres nulos en deporte, disciplina o evento.
- Medallas inválidas: 0.
- FAIL de obligatoriedad: una participación sin `id_edicion`.
- Jerarquía deporte-disciplina: 0 pendientes, validación `PASS`.

## Integridad e idempotencia

- SHA-256 RAW: 10/10 `MATCH` contra `docs/source_manifest.csv`.
- Los diez archivos de `data/intermediate/cleaned/` conservaron el mismo SHA-256 antes y después.
- Dos ejecuciones consecutivas generaron hashes idénticos para los diez CSV de `data/processed/`.
- Reportes: `docs/consolidation/hash_validation.csv`, `intermediate_integrity.csv` y `processed_idempotence.csv`.

## Evidencias visuales pendientes

Las capturas deben mostrar fecha y hora del sistema:

1. [ ] ejecución final con los conteos STRONG/CONTEXTUAL/AMBIGUOUS/UNMATCHED;
2. [ ] reporte de cambios de matching;
3. [ ] alineación RAW/CLEAN y atributos enriquecidos;
4. [ ] entidades geográficas y reporte sin duplicados normalizados;
5. [ ] nacionalidades de participación resueltas;
6. [ ] mapeo deporte-disciplina con 313 resueltos, 832,189 filas cubiertas y 0 pendientes;
7. [ ] deduplicación antes/después;
8. [ ] validaciones con 55 PASS y 1 FAIL;
9. [ ] SHA-256 RAW 10/10 e idempotencia 10/10.

No se cargó SQL Server, no se crearon tablas SQL y no se inició el Bloque 5.
