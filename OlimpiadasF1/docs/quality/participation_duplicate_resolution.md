# Resolución puntual de participaciones duplicadas

Ejecución: `2026-10-11T16:46:44-06:00`. Se revisaron tres grupos duplicados por `id_atleta + id_edicion + id_evento` (seis filas). En cada grupo, los valores no vacíos de la fila escasa coincidían con la fila conservada; no añadían atributos únicos. Se retiraron exactamente tres filas, sin alterar los otros CSV ni RAW/intermediate.

Conteo de `participacion.csv`: 367796 → 367793.

SHA-256 antes: `580f06dbb7747eec99e9c111127c20ddc6b79ea653ad95fdf17f2164c49b38e5`  
SHA-256 después: `4f0739977323ed2dbda9f66f5c2ba544cc3126a3544e134e047c7396a8356b42`

## Casos

- **Antonia Matos (Matos Aycinena-, -de Massot) — 1932 Summer — Art Competitions Mixed Painting, Paintings:** se conserva `459825` y se retira del CSV la fila redundante `700934`. La fila conservada mantiene edad=27 según la fuente de datos; la fila escasa no agrega valores distintos. El informe IOC de 1932 confirma a Antonia Matos en la competición artística con mención honorífica. Olympedia registra nacimiento el 21-11-1902, lo que implicaría 29 años durante los Juegos; por tanto, los 27 años de la fuente de datos son un conflicto no resuelto y no se presentan como edad verificada.
- **Luis Villavicencio — 1976 Summer — Football, Men (Olympic):** se conserva `48190` y se retira del CSV la fila redundante `782134`. La fila escasa no agrega valores distintos. Se conserva el puesto 9 que trae la fuente, pero el informe de fútbol del IOC ubica a Guatemala en el puesto 10; la discrepancia afecta el resultado del equipo y debe revisarse para toda la plantilla, no solo para este atleta.
- **Allan Wellman — 1988 Summer — Football, Men (Olympic):** se conserva `48192` y se retira del CSV la fila redundante `786563`. La fila escasa no agrega valores distintos. Se conserva el puesto 13 que trae la fuente, pero el informe de fútbol del IOC ubica a Guatemala en el puesto 16; la discrepancia afecta el resultado del equipo y debe revisarse para toda la plantilla, no solo para este atleta.

## Verificación de fuentes

El [informe oficial del IOC para Los Ángeles 1932](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=2875488&parentDocumentId=2875401&skipCopyright=true&skipWatermark=true) incluye a Antonia Matos en los resultados de arte con mención honorífica; no confirma por sí solo la edad 27 conservada desde la fuente de datos. Olympedia registra nacimiento el 21-11-1902, que implicaría 29 años en esos Juegos; se deja la edad de la fuente sin cambiar, marcada como conflicto no resuelto y no como dato verificado. El [informe de fútbol del IOC](https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=158223&parentDocumentId=67117&skipCopyright=true&skipWatermark=true) lista a Guatemala en los puestos 10 (Montreal 1976) y 16 (Seúl 1988), mientras el CSV fuente conserva 9 y 13. Los puestos no se corrigieron aquí porque son resultados colectivos compartidos por las plantillas completas y cambiar solo dos atletas dejaría inconsistente el mismo evento; requiere revisión global de esos dos resultados de equipo.

Se buscaron las fichas individuales en Olympics.com, pero no se pudieron consultar directamente durante esta revisión. Se contrastaron las filas de fuentes y los documentos oficiales del IOC/Olympic Studies Centre.
