# Registro de Hallazgos y Auditoría del Stored Procedure de País (Inciso e)

Este documento registra los hallazgos identificados durante la auditoría técnica de los Stored Procedures ([`SP_FINAL_REVIEW.md`], las observaciones del coordinador (Velita), y las soluciones aplicadas en la versión final de **`olympics.sp_consultar_pais`**.

---

## 1. Resumen de Hallazgos y Acciones Aplicadas (SP_FINAL_REVIEW)

| ID | Prioridad | Hallazgo en Versión Inicial | Causa Técnica | Solución Implementada en Versión Final |
| :--- | :---: | :--- | :--- | :--- |
| **H1** | **HIGH** | Medallero oficial no incluía `id_noc` en clave única. | Hacía `SELECT DISTINCT p.id_edicion, p.id_evento, p.medalla`. Podía colapsar o mezclar representaciones históricas. | Se corrigió la clave lógica a: `SELECT DISTINCT p.id_edicion, p.id_evento, p.id_noc, p.medalla`. Se garantiza que la unidad del medallero sea Edición + Evento + NOC + Medalla. |
| **H2** | **HIGH** | Sin validación del dominio de `@temporada`. | Si el usuario pasaba un texto arbitrario (ej. `'Otoño'`), la consulta retornaba cero filas sin explicar la causa. | Se agregó validación explícita con lista cerrada: `IF @temporada NOT IN (N'Summer', N'Winter', N'Summer Youth', N'Winter Youth', N'Intercalated Games')` retorna un mensaje de error claro. |
| **H3** | **HIGH** | `@top_participaciones` vulnerable a desbordes y valores negativos. | Si se enviaba `NULL`, `<= 0` o un número masivo (ej. 100,000), podía generar respuestas descontroladas. | Se normaliza automáticamente: `IF @top_participaciones IS NULL OR @top_participaciones <= 0 SET @top_participaciones = 50;` y se fija un tope superior seguro: `IF @top_participaciones > 1000 SET @top_participaciones = 1000;`. |
| **H4** | **CONTRACT** | `TOP 1` resolvía silenciosamente coincidencias parciales ambiguas. | Al buscar un fragmento como `'San'` o `'Guinea'`, el procedimiento seleccionaba arbitrariamente un solo país sin advertir al usuario. | Se implementó detección de ambigüedad: si hay más de 1 coincidencia en búsqueda parcial, retorna un resultset informativo con la lista de candidatos (`id_entidad`, `nombre`, `codigo_pais`, `codigos_noc`) para que el usuario desempate. |
| **H5** | **MEDIUM** | Sensibilidad a acentos en búsquedas textuales de países. | Búsquedas como `'Peru'` vs `'Perú'` o `'Mexico'` vs `'México'` podían comportarse de manera desigual según la collation del servidor. | Se incorporó `COLLATE Latin1_General_CI_AI` en las comparaciones de texto, asegurando insensibilidad tanto a mayúsculas como a tildes y diacríticos. |
| **H6** | **MEDIUM** | Filtros de texto vulnerables a comodines SQL sin escapar. | En filtros como `@deporte` o `@pais_o_noc`, caracteres como `%`, `_` y `[` podían alterar el patrón de búsqueda `LIKE`. | Se limpian y escapan los caracteres comodín reemplazándolos con secuencias seguras `[%]`, `[_]`, `[[]`. |
| **H7** | **CONTRACT** | El detalle de participaciones carecía de columnas de identificación NOC. | El 4.º resultset no mostraba explícitamente el código NOC bajo el cual compitió el atleta en esa edición. | Se añadieron las columnas `codigo_noc`, `nombre_noc` y `pais_representado` para máxima claridad y trazabilidad. |

---

## 2. Hallazgos de Auditoría QA (2026-09-14) — Discrepancias BD vs olympics.com

Estos hallazgos fueron identificados durante la auditoría QA integral de verificación en vivo contra el contenedor Docker `olimpiadas-sqlserver`.

**Causa raíz común:** La BD integra 4 fuentes heterogéneas que registraron los mismos eventos olímpicos con nombres y `id_evento` diferentes (aliases). La deduplicación ETL consolidó participaciones pero no fusionó aliases de eventos en un solo `id_evento`. Por tanto, la clave `DISTINCT (id_edicion, id_evento, id_noc, medalla)` produce conteos superiores a los de olympics.com.

| ID | Caso | Resultado en BD (Post-Reload) | Resultado olympics.com | Explicación y Estado |
| :--- | :--- | :--- | :--- | :--- |
| **QA-A** | Guatemala (`GUA`) | 1 Oro, 1 Plata, 1 Bronce = **3** | 1 Oro, 1 Plata, 1 Bronce = **3** | **RESUELTO:** Tras recargar la base de datos con los CSV limpios (`data/processed/participacion.csv`), las 2 filas alias de Barrondo fueron retiradas del modelo. Coincidencia 100% con olympics.com. |
| **QA-B** | China 2008 (`CHN`) | **97** Oros oficiales | **51** Oros | Múltiples fuentes registraron los mismos 51 eventos con `id_evento` distintos. |
| **QA-C** | Phelps | **46** Oros, **56** Total | **23** Oros, **28** Total | Los eventos de natación de Phelps tienen registros duplicados por fuente. |
| **QA-D** | Argentina Fútbol 2008 | 1 Oro, **37** preseas | 1 Oro, **18** preseas | 37 filas con medalla Gold para jugadores registrados por múltiples fuentes. |
| **QA-E** | USA Basketball 2012 | 2 Oros, **42** preseas | 2 Oros, **24** preseas | Jugadores registrados por más de una fuente. |
| **QA-F** | `Evidences_Inciso_e.md` | Contenía versión **antigua** del SP | N/A | El archivo embebía código sin H1-H7, sin `id_noc` en clave, sin control de ambigüedad, sin validación de temporada, sin escape de comodines, y con la cifra obsoleta de 1,090,667 filas. **Resuelto:** archivo eliminado y documentación actualizada. |

**Decisión de tratamiento:** El SP reporta fielmente los datos de la BD canónica `olympics.PARTICIPACION` (712,658 filas) sin aplicar deduplicación adicional de aliases de eventos, tal como lo establece el principio de **No-Deduplicación en Caliente** del proyecto. Las diferencias respecto a olympics.com se documentan de forma transparente en toda la documentación del inciso.

---

## 3. Validación de Casos Históricos y Calidad de Datos

### Caso 1: Guatemala (`GUA`)
- **Resultado en BD Sincronizada:** Exactamente 3 medallas con la clave oficial `(id_edicion, id_evento, id_noc, medalla)`:
  1. Adriana Ruano Oliva (París 2024, Foso olímpico femenino): **Oro**.
  2. Érick Barrondo (Londres 2012, `id_evento=1021`, Marcha 20 km): **Plata**.
  3. Jean Pierre Brol Cárdenas (París 2024, Foso olímpico masculino): **Bronce**.
- **Preseas físicas entregadas a atletas:** 3 (coincidencia exacta 1:1 con el medallero oficial).
- **Participaciones totales:** 1,232. **Atletas distintos:** 802.
- **Contraste con olympics.com:** 3 medallas históricas reales (100% exactitud).
- **Sedes:** Condición de Sede = `NO` (0 ediciones organizadas).

### Caso 2: Argentina Fútbol Beijing 2008
- **Resultado en BD:** 1 Oro oficial, 37 preseas físicas, 64 participaciones, 64 atletas distintos.
- **Contraste con olympics.com:** 1 Oro, 18 preseas (plantilla oficial).
- **Messi:** id_atleta 110178, medalla Gold.

### Caso 3: Sedes Olímpicas de Francia (`FRA`)
- **Resultado en BD:** 6 ediciones en 4 ciudades (París 1900, 1924, 2024; Chamonix 1924; Grenoble 1968; Albertville 1992). **Coincide 100% con olympics.com.**

### Caso 4: Australia (`AUS` / `ANZ`)
- `ENTIDAD_GEOGRAFICA`: `id_entidad = 30`, `nombre = 'Australia'`, `codigo_pais = 'AUS'` (No es nulo).
- `NOC`: Códigos `AUS` y `ANZ` (Australasia, 1908 y 1912), ambos con `id_entidad = 30`.

### Caso 5: Michael Phelps
- **Resultado en BD:** 46 Oro, 6 Plata, 4 Bronce = 56 preseas totales.
- **Contraste con olympics.com:** 23 Oro, 3 Plata, 2 Bronce = 28 totales.

### Caso 6: Atleta más joven con Oro (Top 5)
1. Aileen Riggin (USA): 13.0 años, Amberes 1920.
2. Hans Bourquin (SUI): 13.0 años, Ámsterdam 1928.
3. Marjorie Gestring (USA): 13.0 años, Berlín 1936.
4. Donna de Varona (USA): 13.0 años, Roma 1960.
5. Klaus Zerta (GER): 13.0 años, Roma 1960.

---

## 4. Estado de la Base de Datos al Concluir la Revisión

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
PARTICIPACION      = 712,658 filas
TOTAL FILAS        = 1,069,889 filas
```
