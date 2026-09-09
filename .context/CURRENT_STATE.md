# CURRENT STATE — PROYECTO OLIMPIADAS FASE 1

## Corte del estado

- Fecha y hora de esta revisión: 2026-09-08 21:55:35 -06:00.
- Proyecto: `OlimpiadasF1`.
- Alcance actual: Fase 1, incisos a, b y c.
- Los incisos d y e quedan fuera del alcance de este integrante.

## Estado del Bloque 1

El Bloque 1 está **técnicamente concluido** y su cierre documental fue intentado en esta sesión. El cierre visual completo queda condicionado por una limitación del entorno: Computer Use no expuso aplicaciones nativas locales (`apps: []`), por lo que no fue posible abrir Docker Desktop, SSMS, una aplicación de terminal ni una herramienta local para capturar y guardar imágenes reales.

No se fabricaron ni simularon capturas.

La matriz detallada está en:

- `OlimpiadasF1/docs/Evidence/Evidences.md`

## Hechos establecidos por el handoff y el estado del proyecto

- La base objetivo es SQL Server 2025 Developer Edition ejecutado mediante Docker.
- La base se llama `OlimpiadasDB`.
- Los schemas previstos son `stg` y `olympics`.
- El contenedor previsto es `olimpiadas-sqlserver`.
- El mapeo de puertos previsto es `1434:1433`.
- El montaje previsto es `./data:/var/opt/mssql/import:ro`.
- El volumen persistente previsto es `sqlserver_data:/var/opt/mssql`.
- El manifiesto de fuentes usa SHA-256 y se genera mediante `scripts/python/00_source_manifest.py`.
- El modelo final contiene diez entidades: `ENTIDAD_GEOGRAFICA`, `POBLACION`, `NOC`, `ATLETA`, `SEDE`, `EDICION_OLIMPICA`, `DEPORTE`, `DISCIPLINA`, `EVENTO` y `PARTICIPACION`.
- No se deben crear entidades `FUENTE`, `RESULTADO`, `TIPO_MEDALLA` ni `MEDALLA`.

## Comprobaciones realizadas en esta sesión

- Se encontraron exactamente 10 CSV en `OlimpiadasF1/data/raw`.
- `OlimpiadasF1/docs/source_manifest.csv` contiene 10 registros de archivos además del encabezado.
- Existe una evidencia visual preexistente: `OlimpiadasF1/docs/img/evidence_00_create_database.sql.png`.
- Esa imagen fue inspeccionada y muestra SSMS con `localhost,1434`, `OlimpiadasDB`, el script `00_create_database.sql`, ejecución correcta y fecha/hora visibles.
- El cliente Docker no pudo conectarse al daemon desde esta sesión debido a acceso denegado al pipe `docker_engine`.
- El ejecutable de `.venv` existe, pero no pudo iniciarse por acceso denegado.
- El Python global disponible respondió `3.12.7`; `pip` no está disponible en ese intérprete.

## Evidencias pendientes

No se obtuvieron capturas nuevas para Docker, versión de SQL Server, schemas, persistencia, montaje de datos, entorno Python, código y ejecución del manifiesto ni contenido del CSV. La causa común es la ausencia de aplicaciones locales accesibles mediante Computer Use; el detalle por evidencia está en `Evidences.md`.

## Estado del Bloque 2

El profiling diagnóstico del Bloque 2 fue ejecutado sin modificar `data/raw`.

- Script: `OlimpiadasF1/scripts/python/01_profile_sources.py`.
- CSV analizados: 10.
- Columnas perfiladas: 171.
- Detecciones especiales reportadas: 357.
- SHA-256 coincidentes: 10/10.
- `data/raw` intacto: sí.
- Python: 3.14.7.
- pandas: 3.0.5.
- Reportes: `OlimpiadasF1/docs/profiling/`.
- Documentación: `OlimpiadasF1/docs/Evidence/Evidences_Bloque2.md`.

El Bloque 2 **no está aprobado**. Las evidencias visuales reales quedan pendientes porque Computer Use no expuso aplicaciones nativas locales en esta sesión. No se inventaron capturas.

## Estado de continuidad

El Bloque 3 **no ha iniciado**.

## Próximo paso autorizado

Revisar externamente el script y los reportes del Bloque 2, completar las capturas visuales reales con fecha y hora visibles y resolver las observaciones documentadas antes de aprobar el bloque o iniciar el Bloque 3.
