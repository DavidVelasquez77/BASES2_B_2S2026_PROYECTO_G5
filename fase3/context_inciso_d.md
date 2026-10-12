# Contexto de trabajo — Inciso d: consulta por país

## Encargo

Implementar un método/script que reciba un **país** y muestre información relacionada: participaciones, resultados, medallas, años de participación y si fue sede, con los años respectivos. Se admiten filtros opcionales. El formato es libre, pero la respuesta debe ser comprensible y rápida durante la evaluación.

Este archivo orienta la implementación; **no es el método terminado**. No volver a importar datos ni modificar CSV o documentos para resolver la consulta.

## Conexión y recorrido de datos

- Base cargada en este equipo: `OlimpiadasF3` en `mongodb://127.0.0.1:27017`. El Compose de Fase 3 en `27018` corresponde a una instancia nueva separada y actualmente vacía. La URI debe ser configurable en el método.
- Buscar primero en `entidades_geograficas` por nombre o `codigo_pais`. Esa colección contiene nombre/código, `poblacion_anual[]`, `nocs[]`, `sedes[]` y `ediciones_organizadas[]`. Hay **282 entidades**, incluidos agregados estadísticos que **no deben anunciarse automáticamente como países**.
- Con el `id_entidad` encontrado, leer `participaciones_por_pais` por `tipo_agrupacion: "ENTIDAD_GEOGRAFICA"` e `id_entidad`. Son **4,856 buckets** en toda la base, uno por entidad/NOC especial y edición; cada bucket tiene año, temporada, edición/sede y participaciones resumidas con atleta, evento → disciplina → deporte, NOC, equipo, resultado y medalla.
- Los NOC sin entidad geográfica quedan en buckets `NOC_SIN_ENTIDAD` o `SIN_NOC_SIN_ENTIDAD`. No adjudicarlos a un país por parecido textual o nacionalidad del atleta.
- Mapas de campos/tipos: `fase3/db structure/entidades_geograficas.json` y `fase3/db structure/participaciones_por_pais.json`. Código que construye los buckets: `fase3/scripts/mongodb/02_load_processed.js`.

## Índices y estrategia

La consulta normal requiere **dos lecturas indexadas**, no una colección por tabla: `ix_entidades_nombre` o `ix_entidades_codigo_pais` para la ficha, y `ix_part_pais_edicion` (`id_entidad`, `anio`, `temporada`) para los buckets. `ix_part_pais_medalla` ayuda a filtrar documentos con medallas. El método puede unir esas dos respuestas en **un solo resultado** para el usuario. No cargar todos los países para filtrar luego en memoria.

El límite de MongoDB es **16 MiB por documento**. El bucket de mayor tamaño medido en la carga documentada fue 1,338,035 bytes. Mantener la partición por edición; si en una futura fuente un bucket creciera demasiado, dividir ese bucket concreto, no concentrar todo el país en un único documento. Al devolver historiales extensos, permitir filtros/paginación sin perder la posibilidad de consultar el total.

## Contrato mínimo recomendado

Entrada: `pais` obligatorio (nombre o código), opcionales `anio`, `temporada`, `deporte`, `medalla` o paginación. Describir si el parámetro representa entidad geográfica, NOC o ambos; no mezclarlos silenciosamente. Si la búsqueda devuelve agregados o ambigüedad, mostrar candidatos o advertencia, no elegir arbitrariamente.

Salida:

```text
entidad y código original; NOC vinculados
población disponible (serie o resumen claramente identificado)
sedes y ediciones organizadas conocidas, con años y temporada
ediciones en las que hubo participación y cantidad por edición
atletas únicos y participaciones (métricas separadas)
detalle: atleta, NOC/equipo, año/temporada/sede, deporte/disciplina/evento,
         posición/estado y medalla
conteos de medallas con definición explícita
filtros aplicados y tamaño total de la respuesta
```

Ordenar de forma determinística por año, temporada, evento e `id_participacion`. Para obtener biografía completa de un atleta, usar su `id_atleta` en `atletas` **solo cuando se solicite**; el bucket ya contiene el resumen necesario para la consulta de país.

## Decisiones semánticas que importan

1. El país de **representación olímpica** se deriva de `NOC.id_entidad`, no de `id_pais_nacionalidad`, `codigo_pais` ni de una coincidencia de nombre. Hay relaciones faltantes y casos conflictivos preservados.
2. Distinguir `atletas únicos` (IDs distintos) de `participaciones` (filas/IDs de participación). No sumar la copia embebida en `atletas` a la vista de país.
3. En pruebas de equipo, contar atletas con medalla y contar **medallas del país por prueba** puede dar números distintos. Si se muestran ambos, etiquetar la unidad; no publicar un medallero nacional como oficial sumando medallas de todos los integrantes. Definir la clave de una medalla lógica con cuidado y no fusionar eventos solo por nombres parecidos.
4. `ediciones_organizadas` refleja sedes **informadas en los CSV**. Hay ediciones sin `id_sede`; ausencia de vínculo no prueba que un país nunca fue sede.
5. No descartar agregados de población ni convertirlos a país. Un nombre de entidad estadística puede existir en `entidades_geograficas` sin significar un equipo olímpico.
6. `temporada` tiene cinco categorías: Summer, Winter, Intercalated Games, Summer Youth y Winter Youth. No convertir Youth a Summer/Winter ordinario.

## Pruebas de aceptación sugeridas

- `Guatemala` / `GUA`: la ficha actual tiene NOC `GUA` y **20 buckets** por edición. Comparar el resultado por nombre y código. El desglose de medallas de la vista actual debe revisarse contra las participaciones, con unidad claramente definida.
- País con varias ediciones y sede conocida: mostrar sedes/años sin recorrer todas las colecciones manualmente.
- País sin participaciones, agregado estadístico y NOC sin entidad: respuestas diferenciadas, sin atribución falsa.
- Filtrar por año, temporada y medalla; comprobar que detalle y totales coincidan.
- Medir búsquedas de entidad y de buckets con `explain("executionStats")`; registrar índices usados y documentos examinados. No prometer un tiempo fijo sin medición.
- Probar un país grande para detectar respuestas excesivas; aplicar paginación o filtros cuando corresponda.

Consulta de exploración **solo lectura** en PowerShell, desde `PROYECTO1`:

```powershell
mongosh 'mongodb://127.0.0.1:27017/OlimpiadasF3' --quiet --eval 'const g=db.entidades_geograficas.findOne({nombre:"Guatemala"}); printjson({nombre:g&&g.nombre,nocs:g&&g.nocs,sedes:g&&g.sedes,ediciones_organizadas:g&&g.ediciones_organizadas,particiones:g?db.participaciones_por_pais.countDocuments({tipo_agrupacion:"ENTIDAD_GEOGRAFICA",id_entidad:g.id_entidad}):0})'
```

## Entregables del integrante

Script/método ejecutable, instrucciones y ejemplos, capturas reales con fecha/hora, pruebas de país normal/agregado/NOC sin entidad/entrada inexistente, explicación de métricas de medalla y evidencia de uso de índices. **No declarar terminado el inciso d solo porque los buckets ya existen:** falta el método solicitado y su validación funcional.
