# Reconciliación de identidades GUA

Estado: **APPLIED_TO_PROCESSED**

## Resultado vigente

- Padrón de referencia de Olympic Games: **263 personas GUA únicas**.
- Filas GUA Olympic Games conservadas: **585**.
- Filas GUA Youth Olympic Games conservadas fuera del padrón 263: **9**.
- `data/processed/participacion.csv`: **712,020 filas**.
- Cobertura por edición: **PASS** en las 18 ediciones olímpicas GUA, incluida 1988 Winter.
- Asociaciones GUA fuera del padrón por edición: **614 excluidas** del CSV procesado.
- Asociaciones reasignadas a IDs canónicos: **8**.
- IDs ambiguos no fusionados automáticamente: documentados en `gua_ambiguous_cases.csv`.

## Regla aplicada

La pertenencia GUA se validó por `id_edicion` y roster de esa edición, no por nombre global. Las variantes de fuente de una misma persona se reasignaron al ID canónico solamente cuando la evidencia de edición era suficiente. Los casos dudosos se conservaron como revisión o quedaron fuera de la asociación GUA de esa edición; no se fusionaron homónimos a ciegas.

## Evidencia y reproducibilidad

- `gua_olympedia_olympic_roster.csv`: 263 IDs de referencia y 339 apariciones por edición.
- `gua_identity_mapping_dryrun.csv`: mapa reproducible previo a la aplicación.
- `gua_identity_mapping_applied.csv`: mapa aplicado.
- `gua_removed_associations.csv`: asociaciones GUA excluidas con motivo.
- `gua_ambiguous_cases.csv`: casos ambiguos y resolución.
- `gua_canonical_validation.csv`: validación final por edición y conteos.
- `gua_canonical_manifest_after.csv`: hashes antes/después de los 10 CSV procesados.

## Archivos no modificados

No se modificaron `data/raw`, `data/intermediate`, `atleta.csv`, `evento.csv`, SQL Server ni Stored Procedures. El respaldo completo previo está en `data/backup_before_gua_canonical_apply/`.

Referencia externa: https://www.olympedia.org/countries/GUA
