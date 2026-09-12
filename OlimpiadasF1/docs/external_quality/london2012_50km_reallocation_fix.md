# London 2012 Men's 50 km Race Walk — Historical Reallocation Fix

Estado: **LONDON2012_REALLOCATION_FIX_SUCCESS**

La corrección está limitada al evento `id_evento=1022`, edición London 2012 (`id_edicion=50`). No se realizó matching global, merge de atletas, modificación de eventos, corrección de edades ni cambio de procedimientos almacenados.

## Resultado

- Filas de participación antes: **713678**
- Filas históricas confirmadas: **3** — `675066, 754821, 767781`
- Filas en preview: **713675**
- Filas eliminadas en esta ejecución: **3**
- Acción: **applied and SQL rebuilt**
- ATLETA: **336418**
- EVENTO: **2986**

## Resultado vigente conservado

- Jared Tallent — AUS — posición 1 — Gold
- Si Tianfeng — CHN — posición 2 — Silver
- Robbie Heffernan — IRL — posición 3 — Bronze
- Sergey Kirdyapkin — RUS — DQ — NULL

La fuente IOC documenta el contexto de reasignación de medallas de Londres 2012 y la documentación oficial de Londres identifica la prueba de 50 km. [IOC medal table changes](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=208905&parentDocumentId=176545&skipCopyright=true&skipWatermark=true) · [London 2012 official programme](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158773&parentDocumentId=71295&skipCopyright=true&skipWatermark=true)

## Evidencia de identidad

Las filas históricas eliminadas tienen los mismos atleta real, edición, evento y NOC que la fila canónica vigente. Sus IDs de atleta son secundarios y no se fusionó ni modificó `ATLETA`. La fila secundaria de Robert Heffernan se inspeccionó; al no ser posición 4, quedó en `REVIEW` y no se eliminó.

## Validaciones

Consultar `london2012_50km_reallocation_validation.csv`. Todas las consultas de aceptación del preview resultaron PASS antes de la aplicación.

Validación posterior de SQL:

- `staging.PARTICIPACION`: **713675**, PASS.
- `olympics.PARTICIPACION`: **713675**, PASS.
- `10_final_validation.sql`: **26/26 PASS**.
- `11_special_cases_validation.sql`: **8/8 PASS**.
- FK huérfanas: **0**.
- PK duplicadas: **0**.
- Constraints: **10 PK, 6 UNIQUE, 14 FK, 3 CHECK**, PASS.
- Índices adicionales: **8**, PASS.
- Unicode: **26261** nombres no ASCII comparados, **0** diferencias, PASS.
- Auditoría externa: **EXTERNAL_OLYMPIC_QUALITY_AUDIT_PASS**, conflictos críticos **0**.

Los IDs históricos `675066`, `754821` y `767781` no existen en la tabla final. El evento 1022 conserva el resultado vigente de Tallent, Si, Heffernan y Kirdyapkin.

## Trazabilidad y rollback

El mapa completo está en `london2012_50km_reallocation_map.csv`. La copia de respaldo queda en `data/backup_before_london2012_reallocation_fix/`. La guardia de `03_create_staging.sql` detectó tablas staging existentes después del reset; estaban vacías, por lo que se continuó de forma reproducible con `04_bulk_load_staging.sql`, sin cargar datos parcialmente ni modificar otras entidades.
