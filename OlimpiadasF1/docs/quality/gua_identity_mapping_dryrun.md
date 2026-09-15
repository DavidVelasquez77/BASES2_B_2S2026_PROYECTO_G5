# Dry-run de reconciliación GUA por edición

Estado: **NO_APLICADO**

La referencia se obtuvo de las páginas de resultados de Guatemala por edición en Olympedia. Se excluyeron Youth Olympic Games porque el objetivo de 263 corresponde al conteo de Olympic Games.

- Atletas de referencia únicos: **263**.
- Registros incluidos por edición: **339**.
- Filas de resultados fuera del conteo 263: **10**.
- Referencias con candidato único por nombre+edición: **327**.
- Referencias ambiguas: **2**.
- Referencias sin candidato exacto: **10**.
- IDs locales candidatos distintos: **258**.

## Regla de seguridad

El dry-run no elimina participaciones ni fusiona entidades. Una asociación solo podrá retirarse cuando la referencia por edición demuestre que el atleta local no pertenece al roster GUA de esa edición. Las coincidencias ambiguas y los nombres sin candidato quedan documentados.

## Archivos

- `docs\quality\gua_olympedia_olympic_roster.csv`: roster de referencia por edición.
- `docs\quality\gua_identity_mapping_dryrun.csv`: mapa candidato reproducible.

Referencia principal: https://www.olympedia.org/countries/GUA
