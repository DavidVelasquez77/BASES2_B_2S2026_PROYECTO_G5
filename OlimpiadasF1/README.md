# OlimpiadasF1

Proyecto de integración, limpieza, homologación y carga de datos históricos de atletas y eventos olímpicos. Las fuentes principales son resultados olímpicos, biografías de atletas, población por país y una fuente adicional de resultados.

## Estado de entrega

Los Bloques 1–6 están ejecutados. El Bloque 7 contiene la validación final y la preparación de entrega. La aprobación académica definitiva queda sujeta a revisión externa.

La base `OlimpiadasDB` contiene los schemas `olympics` y `stg`. El modelo final tiene diez entidades lógicas: `ENTIDAD_GEOGRAFICA`, `POBLACION`, `NOC`, `ATLETA`, `SEDE`, `EDICION_OLIMPICA`, `DEPORTE`, `DISCIPLINA`, `EVENTO` y `PARTICIPACION`. `stg` es infraestructura ETL y no una entidad del modelo conceptual.

Conteos finales: 282 entidades geográficas, 17,024 poblaciones, 236 NOC, 338,772 atletas, 42 sedes, 61 ediciones, 65 deportes, 117 disciplinas, 3,106 eventos y 826,605 participaciones.

## Requisitos y configuración

- Docker Desktop con SQL Server 2025 Developer.
- Python y las dependencias de `requirements.txt`.
- Un archivo `.env` local con `MSSQL_SA_PASSWORD=<TU_PASSWORD>`; no incluir contraseñas en documentación ni en control de versiones.

Levantar el servicio:

```powershell
docker compose up -d
```

La instancia queda disponible en `localhost,1434` y la base se llama `OlimpiadasDB`.

## Estructura y ejecución

- `data/raw/`: fuentes originales, inmutables.
- `data/intermediate/`: datos limpios por fuente.
- `data/processed/`: CSV finales para carga.
- `scripts/python/`: profiling, limpieza, consolidación y auditorías.
- `scripts/sql/`: DDL, staging, carga y validaciones.
- `docs/`: reportes, evidencias y documentación.

El orden reproducible está en [docs/EXECUTION_ORDER.md](docs/EXECUTION_ORDER.md). La validación final de solo lectura se ejecuta con `10_final_validation.sql`, `11_special_cases_validation.sql` y `12_functional_queries.sql`. No se deben volver a ejecutar scripts de carga sobre tablas pobladas.

## Modelo y ETL

La carga utiliza staging bajo `stg`, validaciones de conversión y una inserción explícita a `olympics`, respetando UTF-8, `NULL`, claves y dominios. Las temporadas finales son `Summer`, `Winter`, `Intercalated Games`, `Summer Youth` y `Winter Youth`. Las pruebas ecuestres de 1956 están homologadas a `1956 Summer`; 1906 queda como `Intercalated Games`.

Las claves y restricciones aprobadas son 10 PK, 6 UNIQUE, 14 FK y 3 CHECK. Los ocho índices adicionales se documentan en `docs/loading/indexes_created.csv`.

## Consultas funcionales

Las consultas de ejemplo para atleta, país/NOC, medallas, estados especiales, Unicode, temporadas y 1906 están en `scripts/sql/12_functional_queries.sql`. Los procedimientos almacenados de atleta y país pertenecen a otro integrante y no forman parte de este bloque.

## Seguridad y entrega

No se incluyen secretos, archivos `.env`, datos RAW ni archivos temporales en la entrega. La lista de comprobación está en [docs/FINAL_DELIVERY_CHECKLIST.md](docs/FINAL_DELIVERY_CHECKLIST.md). Las evidencias visuales del Bloque 7 quedan como espacios reservados para capturas reales; no se fabricaron imágenes.
