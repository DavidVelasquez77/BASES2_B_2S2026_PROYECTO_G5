# Consolidación — Bloque 4

Proceso determinístico y auditable por fuente. No se aplicó fuzzy matching automático.

- Identidades de atletas: **338772**.
- Matching STRONG: **177741**; CONTEXTUAL: **496**.
- Matching fuzzy automático: **0**.
- Unmatched: **190415**; ambiguous: **2857**.
- Participaciones antes de deduplicar: **832189**; después: **826605**.
- Participaciones con nacionalidad geográfica resuelta: **81**.
- Alineación Fuente 1 RAW/CLEAN segura: **299462**; atributos enriquecidos: **102995**.
- Fuente 4 exacta contra Fuente 2: **100/100**.
- NOC resueltos: **231**; no resueltos: **5**.
- Mapeos deporte-disciplina resueltos: **313**; pendientes: **0**.
- Duplicados conceptuales geográficos pendientes: **0**.
- Validaciones de modelo PASS: **56/56**; FAIL: **0**.
- SHA-256 RAW: **10/10**.

## Criterios

Los nombres normalizados se usan solo como claves auxiliares. Un match determinístico requiere nombre auxiliar exacto y compatibilidad de sexo; el nivel A agrega evidencia NOC compatible. Los candidatos múltiples se conservan como AMBIGUOUS. Las identidades sin candidato se conservan como UNMATCHED con un id global propio.

La jerarquía deportiva sigue DEPORTE → DISCIPLINA → EVENTO. La terminología se contrastó con https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3415338&parentDocumentId=3415336&skipCopyright=true&skipWatermark=true y https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=174689&parentDocumentId=174657&skipCopyright=true&skipWatermark=true. Las asignaciones no demostrables aparecen como PENDING_REVIEW.

Fuente 4 se comparó con Fuente 2 en 14 columnas comunes. Las coincidencias exactas se excluyen de la salida consolidada y quedan auditadas.

La carga SQL queda fuera del alcance de este bloque; las validaciones técnicas deben revisarse antes de cualquier carga.

No se cargó SQL Server, no se crearon tablas SQL, no se inició el Bloque 5 y no se declara aprobado este bloque.
