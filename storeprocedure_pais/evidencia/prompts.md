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
- Retirar cualquier cálculo heurístico dentro de los procedimientos; la base de datos física `PARTICIPACION` es la fuente canónica oficial.
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

## 5. Auditoría QA Integral y Reconciliación Canónica (2026-09-15)

### Requerimientos Directos del Coordinador (Velita - Chat de Grupo):
> *"1. Actualizar pruebas y documentación:*
> *   - Guatemala: 594 participaciones.*
> *   - Guatemala: 263 atletas distintos.*
> *   - Medallero: 1 Gold, 1 Silver, 1 Bronze.*
> *   - Participaciones totales del proyecto: 712,020.*
> *   - Ya no usar 1,232 participaciones ni 802 atletas como valores vigentes.*
> *2. Mantener la separación entre:*
> *   - medallas oficiales por evento/NOC;*
> *   - preseas físicas entregadas a atletas.*
> *   La clave actual: id_edicion + id_evento + id_noc + medalla debe conservarse para evitar inflar deportes de equipo.*
> *3. Revisar y resolver la duplicación semántica de eventos.*
> *4. Corregir la documentación obsoleta de Phelps:*
> *   Ya no debe decir 46 oros / 56 medallas. El resultado canónico vigente es: 23 oros / 3 platas / 2 bronces = 28.*
> *5. Revisar los NOC históricos con id_entidad IS NULL:*
> *   Actualmente el SP descarta un NOC exacto si no tiene entidad geográfica asociada. Deben separar @id_noc y @id_entidad.*
> *6. Hacer la validación de @temporada insensible a mayúsculas y acentos, igual que el SP de atleta."*

### Acciones Técnicas Ejecutadas:
1. **Reconstrucción de la Base de Datos en Docker:** Se recargó `OlimpiadasDB` aplicando los scripts `00` al `10`, logrando `712,020` participaciones exactas (`RESULTADO_GLOBAL = PASS`).
2. **Refactorización de `sp_consultar_pais.sql`:**
   - Desacoplamiento de `@id_entidad` y `@id_noc` mediante tabla en memoria `@nocs_filtrados`.
   - Soporte para delegaciones independientes y de refugiados (`ROC`, `EOR`, `ROT`, `AIN`, `COR`).
   - Normalización insensible en `@temporada` con `COLLATE Latin1_General_CI_AI`.
3. **Actualización de Batería de Pruebas (`pruebas.sql`):** Casos 100% verificados y ejecutados con código de salida 0.
4. **Sincronización:** Copia fiel a `OlimpiadasF1/scripts/sql/14_sp_consultar_pais.sql`.
