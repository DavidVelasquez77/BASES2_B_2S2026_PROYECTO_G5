# Contexto de trabajo — Inciso c: consulta por atleta

## Encargo

Implementar un método/script cuyo **primer parámetro sea el nombre del atleta** y que muestre su información, participaciones, resultados y medallas. Puede aceptar filtros opcionales por deporte, país y año. El formato de salida lo decide el integrante, pero debe ser claro y responder rápido durante la evaluación.

Este archivo orienta la implementación; **no es el método terminado**. No volver a importar datos, recrear colecciones ni modificar los CSV para implementar la consulta.

## Conexión y documentos disponibles

- Base ya cargada en este equipo: `OlimpiadasF3` en `mongodb://127.0.0.1:27017`. El Compose nuevo de `fase3/compose.yaml` expone **otra** instancia en `27018`, actualmente vacía; no confundirlas. En otra máquina, hacer configurable la URI.
- Colección principal: `atletas`. Hay **167,295 documentos**, uno por `id_atleta`.
- Un atleta contiene su perfil y el arreglo `participaciones[]`. Las **367,793** participaciones totales incluyen `id_participacion`, edición/sede, evento → disciplina → deporte, NOC, equipo, posición, estado y medalla. No se necesitan joins para la consulta básica.
- Mapa de campos/tipos: `fase3/db structure/atletas.json`. Implementación del documento: `fase3/scripts/mongodb/02_load_processed.js`. Manual de validación: `fase3/docs/Evidence/Evidences_Fase3.md`.
- Índices existentes: `ix_atletas_nombre`, `ix_atletas_nombre_completo`, `ix_atletas_nombre_usado` e `ix_atletas_participaciones_edicion`. Para búsquedas exactas por nombre, verificar con `explain("executionStats")` que se usa un índice; no prometer que cualquier búsqueda parcial lo hará.

## Contrato mínimo recomendado

Entrada: `nombre` obligatorio; opcionales `deporte`, `pais`, `anio` o `temporada`, con valores documentados. Validar tipos, longitud y valores vacíos. Un resultado ambiguo **no debe escoger un atleta arbitrariamente**: devolver candidatos con `id_atleta`, nombre, fecha de nacimiento y contexto disponible, para que el usuario elija. No fusionar identidades por similitud de nombre.

Salida para un atleta resuelto:

```text
id_atleta y nombres disponibles
datos personales, nacionalidad y países informados (sin inventar faltantes)
participaciones: edición/año/temporada/sede, deporte/disciplina/evento,
                 NOC/equipo, resultado/posición/estado y medalla
totales claramente rotulados (participaciones, oros, platas, bronces)
filtros aplicados y total de filas antes/después del filtro
```

Ordenar participaciones de forma determinística por año, edición, evento e `id_participacion`. Si se necesita paginación, documentar que los totales se calculan sobre el conjunto filtrado completo, no solo sobre la página visible. Conservar `null` como ausencia; no convertir textos descriptivos (`NA`, `None`, etc.) globalmente.

## Decisiones semánticas que importan

1. **Usar solo `atletas.participaciones` para contar**, nunca sumar la copia de `participaciones_por_pais`: ambas vistas representan los mismos IDs.
2. Una medalla de atleta se cuenta a partir de participaciones con `medalla` Gold/Silver/Bronze. No tratar `posicion=1` como oro si `medalla` es nula ni contar filas `DQ` como medallas.
3. `pais_nacionalidad` y `noc.entidad` pueden diferir. Si el filtro es por **país representado**, usar el NOC de cada participación; si se refiere a nacionalidad, llamarlo explícitamente así. No equiparar códigos por texto.
4. Los nombres pueden tener variantes Unicode. Conservar el valor almacenado al mostrarlo. Si se implementa búsqueda flexible, escapar expresiones regulares, limitar candidatos y documentar si es o no insensible a acentos; no reemplazar el nombre original.
5. La base ya conserva casos sin sede o sin entidad NOC. Mostrarlos como no informados; no completar por suposición.

## Pruebas de aceptación sugeridas

- `Michael Phelps`: resolver un documento; el documento actual contiene **30 filas de participación**. Mostrar también el desglose de medallas, calculado desde `medalla`; no confundir filas con medallas.
- Búsqueda inexistente: salida vacía y mensaje comprensible, sin error técnico.
- Nombre ambiguo: lista de candidatos, sin unión automática.
- Filtrar Phelps por un año/deporte y verificar que cada fila devuelta cumple el filtro; totales y detalle deben concordar.
- Un nombre con caracteres no ASCII: entrada y salida conservan el Unicode exacto.
- Medir al menos una consulta por nombre con `explain("executionStats")`; registrar claves/documentos examinados y tiempo observado, sin prometer una latencia fija.

Consulta de exploración **solo lectura** en PowerShell, desde `PROYECTO1`:

```powershell
mongosh 'mongodb://127.0.0.1:27017/OlimpiadasF3' --quiet --eval 'const a=db.atletas.findOne({nombre:"Michael Phelps"}); printjson({id_atleta:a&&a.id_atleta,nombre:a&&a.nombre,participaciones:a&&a.participaciones.length,primera:a&&a.participaciones[0]})'
```

## Entregables del integrante

Script/método ejecutable, instrucciones y ejemplos de uso, capturas reales con fecha/hora, pruebas de casos y breve explicación de índices y límites. **No declarar terminado el inciso c solo porque la colección ya contiene los datos:** falta el método solicitado y su validación funcional.
