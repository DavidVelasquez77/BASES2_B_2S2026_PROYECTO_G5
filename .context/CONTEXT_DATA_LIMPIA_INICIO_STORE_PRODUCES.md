# Handoff: datos limpios para procedimientos almacenados

## Conexión

- Base: `OlimpiadasDB`.
- Schemas de trabajo: `olympics` y `stg`.
- Contenedor: `olimpiadas-sqlserver`.
- Puerto publicado: `localhost,1434`.
- La contraseña se obtiene únicamente desde `.env`; no se copia en este documento.

## Tablas y rutas de consulta

Las diez tablas finales son `ENTIDAD_GEOGRAFICA` (PK `id_entidad`), `POBLACION` (PK compuesta `id_entidad, anio`), `NOC` (`id_noc`), `ATLETA` (`id_atleta`), `SEDE` (`id_sede`), `EDICION_OLIMPICA` (`id_edicion`), `DEPORTE` (`id_deporte`), `DISCIPLINA` (`id_disciplina`), `EVENTO` (`id_evento`) y `PARTICIPACION` (`id_participacion`).

Ruta para consultas de un atleta:

`ATLETA -> PARTICIPACION -> EDICION_OLIMPICA -> EVENTO -> DISCIPLINA -> DEPORTE`, con `PARTICIPACION.id_noc -> NOC` cuando se necesita país/equipo.

Ruta para consultas por país:

`ENTIDAD_GEOGRAFICA -> NOC -> PARTICIPACION -> ATLETA`, y `PARTICIPACION -> EDICION_OLIMPICA` para series históricas.

`NOC.id_entidad` es una relación geográfica modelada y no equivale automáticamente a un código ISO3. `PARTICIPACION.id_pais_nacionalidad` es otra relación distinta. No fusionar NOC, país de nacionalidad y entidad geográfica por igualdad textual o de código.

## Semántica de participación

- `medalla` admite `Gold`, `Silver`, `Bronze` o `NULL`.
- `posicion` es nullable; `empatado` es `BIT`.
- `estado_resultado` puede conservar `DNF`, `DNS`, `DQ` o `DSQ`; no existe un estado artificial `FINISHED`.
- Los identificadores son los IDs globales finales, no los identificadores originales de cada fuente.
- Las temporadas finales son `Summer`, `Winter`, `Intercalated Games`, `Summer Youth` y `Winter Youth`.
- 1906 queda representado como `Intercalated Games`.
- Las pruebas ecuestres de 1956 están asociadas a `1956 Summer`; no existe una edición `Equestrian`.

## Magnitudes e índices

Conteos: 282 entidades geográficas, 17,024 poblaciones, 236 NOC, 338,772 atletas, 42 sedes, 61 ediciones, 65 deportes, 117 disciplinas, 3,106 eventos y 826,605 participaciones.

Índices adicionales: `IX_PARTICIPACION_id_atleta`, `IX_PARTICIPACION_id_edicion`, `IX_PARTICIPACION_id_evento`, `IX_PARTICIPACION_id_noc`, `IX_PARTICIPACION_id_pais_nacionalidad`, `IX_ATLETA_id_pais_nacionalidad`, `IX_NOC_id_entidad` e `IX_SEDE_id_pais`.

## Procedimientos siguientes

Los procedimientos almacenados de atleta y país deben usar las rutas anteriores, filtrar de forma explícita por IDs y conservar la distinción NOC/país. No deben modificar datos. Su implementación corresponde a otro integrante y no forma parte del Bloque 7.
