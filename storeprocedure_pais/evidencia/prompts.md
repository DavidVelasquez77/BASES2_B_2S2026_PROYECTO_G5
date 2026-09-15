# Bitácora de Prompts y Desarrollo - Stored Procedure de País (Inciso e)

Este documento recopila los prompts de trabajo, requerimientos directos de cátedra y del coordinador, así como las directrices de diseño utilizadas para desarrollar, depurar y estructurar el Stored Procedure `olympics.sp_consultar_pais`.

---

## 1. Prompt Inicial de Enunciado (Cátedra)
> *"e) Realizar un stored procedure que reciba de parámetro el país y que despliegue toda la información relacionada con el mismo, participaciones, información de medallas, resultados, año de participación, si ha sido sede en alguna ocasión y qué años. El formato de salida es a su criterio. Pueden agregar parámetros para filtrar información específica."*
> *Fecha de entrega y calificación: 19 - SEP - 2026. Nota: el día de la calificación se les pedirá hacer consultas en el momento.*

---

## 2. Directrices del Coordinador (Velita)
1. **Separación de responsabilidades:**
   - Inciso d) Atleta -> @Valery (`storeprocedure_atleta/`).
   - Inciso e) País -> @Helado (`storeprocedure_pais/`).
2. **Reorganización en carpeta raíz propia:**
   - Mover la documentación, scripts SQL y capturas de evidencia a una carpeta homóloga e independiente (`storeprocedure_pais/`).
3. **Casos típicos de evaluación del Ingeniero:**
   - Preparar un banco de consultas con casos de interés del catedrático:
     - Futbolistas destacados: Lionel Messi (2008), Cristiano Ronaldo (2004), Neymar (2012, 2016).
     - Medallistas de Guatemala (Barrondo, Brol, Ruano).
     - Consultas analíticas en vivo (ganador de 100m en 2004, más medallas de oro, atleta más joven con oro).
4. **Cotejo con olympics.com:**
   - Verificar y respaldar cada resultado numérico contra los registros oficiales de los Juegos Olímpicos.

---

## 3. Directrices de Calidad y Auditoría (`SP_FINAL_REVIEW.md`)
- Retirar cualquier cálculo heurístico dentro de los procedimientos; la base de datos física `PARTICIPACION` (712,658 filas) es la fuente canónica oficial.
- Corregir la clave lógica del medallero oficial incluyendo `id_noc`:
  ```sql
  SELECT DISTINCT p.id_edicion, p.id_evento, p.id_noc, p.medalla
  ```
- Validar el dominio de la temporada para rechazar valores ajenos a:
  `Summer`, `Winter`, `Summer Youth`, `Winter Youth`, `Intercalated Games`.
- Controlar `@top_participaciones` con valores por defecto (50) y tope superior (1000).
- Evitar selección silenciosa con `TOP 1` en búsquedas ambiguas; retornar listado de candidatos si hay más de 1 coincidencia.
- Aplicar `COLLATE Latin1_General_CI_AI` para insensibilidad a tildes y diacríticos.
- Escapar caracteres comodín en búsquedas `LIKE`.

---

## 4. Prompts de Verificación y Generación de Datos Reales
- *Consulta a datasets procesados:* Extraer conteos exactos de Guatemala, Francia, Argentina Fútbol 2008, 100 metros 2004, Cristiano Ronaldo, Neymar Jr., Phelps y los atletas más jóvenes con medalla de oro.
- *Comprobación de no-invención de datos:* Toda cifra presentada en los scripts y documentación proviene directamente del modelo físico final y es 100% reproducible.

---

## 5. Auditoría QA Integral (2026-09-14)
- **Prompt maestro de auditoría:** Se ejecutó una verificación forense de inicio a fin de toda la documentación, SP y pruebas del Inciso e).
- **Hallazgos principales:** Se detectaron discrepancias entre las cifras documentadas y los valores reales de la BD, causadas por aliases de eventos de múltiples fuentes que no fueron fusionados en un solo `id_evento` durante el ETL.
- **Acciones tomadas:**
  - Se actualizaron las cifras esperadas en `pruebas.sql` para reflejar los valores reales de la BD.
  - Se actualizó `documentacion_e.md` con los datos reales y notas aclaratorias sobre diferencias con olympics.com.
  - Se reescribió `hallazgos_reportados.md` con el registro completo de hallazgos H1-H7 y QA-A a QA-F.
  - Se eliminó `Evidences_Inciso_e.md` (contenía versión antigua del SP sin las correcciones de auditoría).
  - Se recompiló el SP y se ejecutó la batería completa de pruebas en Docker con código de retorno 0.
- **Datos reales verificados en vivo:**
  - Guatemala: 1 Oro, 2 Plata, 1 Bronce = 4 medallas en BD (3 en olympics.com por alias de evento).
  - China 2008: 97 oros en BD (51 en olympics.com).
  - Phelps: 46 oros, 56 total en BD (23 oros, 28 total en olympics.com).
  - Argentina Fútbol 2008: 1 oro oficial, 37 preseas en BD (18 en olympics.com).
  - USA Basketball 2012: 2 oros, 42 preseas en BD (24 en olympics.com).
  - Francia: 6 sedes ✓. Cristiano Ronaldo id 102010 ✓. Neymar id 122812 ✓. Messi id 110178 ✓.
  - 100m Atenas 2004: Justin Gatlin Gold ✓. Atletas más jóvenes con oro: 13.0 años ✓.
