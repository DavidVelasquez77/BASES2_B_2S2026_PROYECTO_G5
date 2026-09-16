# Registro de Hallazgos y Auditoría del Stored Procedure de País (Inciso e)

Este documento registra los hallazgos identificados durante la auditoría técnica de los Stored Procedures ([`SP_FINAL_REVIEW.md`]), las observaciones del coordinador (Velita), y las soluciones aplicadas en la versión final de **`olympics.sp_consultar_pais`**.

---

## 1. Resumen de Hallazgos y Acciones Aplicadas (SP_FINAL_REVIEW & Auditoría Canónica)

| ID | Prioridad | Hallazgo en Versión Inicial | Causa Técnica | Solución Implementada en Versión Final |
| :--- | :---: | :--- | :--- | :--- |
| **H1** | **HIGH** | Medallero oficial no incluía `id_noc` en clave única. | Hacía `SELECT DISTINCT p.id_edicion, p.id_evento, p.medalla`. Podía colapsar o mezclar representaciones históricas. | Se corrigió la clave lógica a: `SELECT DISTINCT p.id_edicion, p.id_evento, p.id_noc, p.medalla`. Se garantiza que la unidad del medallero sea Edición + Evento + NOC + Medalla. |
| **H2** | **HIGH** | Sin validación del dominio de `@temporada`. | Si el usuario pasaba un texto arbitrario (ej. `'Otoño'`), la consulta retornaba cero filas sin explicar la causa. | Se agregó validación explícita con lista cerrada y `COLLATE Latin1_General_CI_AI` para ser insensible a mayúsculas y acentos (ej. `'summer'` es válido). |
| **H3** | **HIGH** | `@top_participaciones` vulnerable a desbordes y valores negativos. | Si se enviaba `NULL`, `<= 0` o un número masivo (ej. 100,000), podía generar respuestas descontroladas. | Se normaliza automáticamente: `IF @top_participaciones IS NULL OR @top_participaciones <= 0 SET @top_participaciones = 50;` y se fija un tope superior seguro: `IF @top_participaciones > 1000 SET @top_participaciones = 1000;`. |
| **H4** | **CONTRACT** | `TOP 1` resolvía silenciosamente coincidencias parciales ambiguas. | Al buscar un fragmento como `'San'` o `'Guinea'`, el procedimiento seleccionaba arbitrariamente un solo país sin advertir al usuario. | Se implementó detección de ambigüedad: si hay más de 1 coincidencia en búsqueda parcial, retorna un resultset informativo con la lista de candidatos (`id_entidad`, `id_noc`, `nombre`, `codigo_iso`, `codigos_noc`) para que el usuario desempate. |
| **H5** | **MEDIUM** | Sensibilidad a acentos en búsquedas textuales de países. | Búsquedas como `'Peru'` vs `'Perú'` o `'Mexico'` vs `'México'` podían comportarse de manera desigual según la collation del servidor. | Se incorporó `COLLATE Latin1_General_CI_AI` en las comparaciones de texto, asegurando insensibilidad tanto a mayúsculas como a tildes y diacríticos. |
| **H6** | **MEDIUM** | Filtros de texto vulnerables a comodines SQL sin escapar. | En filtros como `@deporte` o `@pais_o_noc`, caracteres como `%`, `_` y `[` podían alterar el patrón de búsqueda `LIKE`. | Se limpian y escapan los caracteres comodín reemplazándolos con secuencias seguras `[%]`, `[_]`, `[[]`. |
| **H7** | **CONTRACT** | El detalle de participaciones carecía de columnas de identificación NOC. | El 4.º resultset no mostraba explícitamente el código NOC bajo el cual compitió el atleta en esa edición. | Se añadieron las columnas `codigo_noc`, `nombre_noc` y `pais_representado` para máxima claridad y trazabilidad. |
| **H8** | **HIGH** | NOCs históricos con `id_entidad IS NULL` eran descartados. | El SP exigía `id_entidad NOT NULL` y unía obligatoriamente con `ENTIDAD_GEOGRAFICA`. Delegaciones como `ROC` (Comité Olímpico Ruso), `EOR` (Refugiados), `ROT`, `AIN` y `COR` no podían consultarse. | Se desacopló la resolución entre `@id_entidad` y `@id_noc`. El SP consulta por `@id_noc` directo cuando la entidad geográfica es `NULL`, permitiendo acceder al medallero y atletas de `ROC`, `EOR`, etc. |

---

## 2. Hallazgos de Auditoría QA (Base Vigente: 712,020 Participaciones)

| ID | Caso | Resultado en BD (Canónico Vigente) | Resultado olympics.com | Explicación y Estado |
| :--- | :--- | :--- | :--- | :--- |
| **QA-A** | Guatemala (`GUA`) | 1 Oro, 1 Plata, 1 Bronce = **3** | 1 Oro, 1 Plata, 1 Bronce = **3** | **RESUELTO AL 100%:** 594 participaciones y 263 atletas distintos. Coincide exactamente con Olympedia y olympics.com tras excluir 614 asociaciones erróneas en el ETL. |
| **QA-B** | Delegación `ROC` (Rusia 2020) | **46** Oro, **71** Plata, **67** Bronce | N/A (Equipo Neutral) | **RESUELTO:** Consulta exitosa de las 1,689 participaciones y 1,151 atletas de ROC sin requerir `id_entidad`. |
| **QA-C** | Phelps (`USA`) | **23** Oro, **3** Plata, **2** Bronce = **28** | **23** Oro, **3** Plata, **2** Bronce = **28** | **RESUELTO:** El resultado canónico en BD coincide 100% con olympics.com tras la deduplicación del Bloque 4. Referencias anteriores a 46 oros quedaron obsoletas. |
| **QA-D** | Argentina Fútbol 2008 | 1 Oro, **37** preseas físicas | 1 Oro oficial, **18** preseas de plantilla | 37 filas con medalla Gold para jugadores registrados por múltiples fuentes. El SP otorga 1 solo Oro oficial al país. |
| **QA-E** | USA Basketball 2012 | 2 Oros, **42** preseas físicas | 2 Oros oficiales | Torneo masculino y femenino. El SP computa 2 títulos oficiales para Estados Unidos sin inflar el medallero. |
| **QA-F** | `Evidences_Inciso_e.md` | Contenía versión **antigua** del SP | N/A | Archivo eliminado y reemplazado por la documentación modular y auditada en `storeprocedure_pais/`. |

---

## 3. Validación de Casos Históricos y Calidad de Datos

### Caso 1: Guatemala (`GUA`)
- **Resultado en BD Sincronizada:** Exactamente 3 medallas con la clave oficial `(id_edicion, id_evento, id_noc, medalla)`:
  1. Adriana Ruano Oliva (París 2024, Foso olímpico femenino): **Oro**.
  2. Érick Barrondo (Londres 2012, `id_evento=1021`, Marcha 20 km): **Plata**.
  3. Jean-Pierre Brol Cárdenas (París 2024, Foso olímpico masculino): **Bronce**.
- **Preseas físicas entregadas a atletas:** 3 (coincidencia exacta 1:1 con el medallero oficial).
- **Participaciones totales:** 594. **Atletas distintos:** 263.
- **Contraste con Olympedia / olympics.com:** 263 atletas únicos y 3 medallas históricas reales (100% exactitud y fidelidad histórica).
- **Sedes:** Condición de Sede = `NO` (0 ediciones organizadas).

### Caso 2: Delegaciones Especiales sin País Físico (`ROC`, `EOR`)
- **ROC (Comité Olímpico Ruso):**
  - Participaciones: 1,689 | Atletas distintos: 1,151.
  - Medallas oficiales: 46 Oro, 71 Plata, 67 Bronce (Total: 184). Preseas a deportistas: 425.
- **EOR (Equipo Olímpico de Refugiados):**
  - Participaciones: 126 | Atletas distintos: 97.
  - Medallas: 1 Bronce (Cindy Ngamba / Winner Djankeu, Boxeo 75kg, París 2024).

### Caso 3: Argentina Fútbol Beijing 2008
- **Resultado en BD:** 1 Oro oficial, 37 preseas físicas, 64 participaciones, 64 atletas distintos.
- **Messi:** id_atleta 110178, medalla Gold.

### Caso 4: Sedes Olímpicas de Francia (`FRA`)
- **Resultado en BD:** 6 ediciones en 4 ciudades (París 1900, 1924, 2024; Chamonix 1924; Grenoble 1968; Albertville 1992). **Coincide 100% con olympics.com.**

### Caso 5: Michael Phelps
- **Resultado canónico en BD:** 23 Oro, 3 Plata, 2 Bronce = 28 medallas totales.
- **Contraste con olympics.com:** 100% de coincidencia exacta.

---

## 4. Estado de la Base de Datos Canónica Vigente

Validado con `10_final_validation.sql` en el contenedor `olimpiadas-sqlserver` (`RESULTADO_GLOBAL = PASS`):

```text
ENTIDAD_GEOGRAFICA = 282 filas
POBLACION          = 17,024 filas
NOC                = 236 filas
ATLETA             = 336,418 filas
SEDE               = 42 filas
EDICION_OLIMPICA   = 61 filas
DEPORTE            = 65 filas
DISCIPLINA         = 117 filas
EVENTO             = 2,986 filas
PARTICIPACION      = 712,020 filas
TOTAL FILAS        = 1,069,251 filas
```
