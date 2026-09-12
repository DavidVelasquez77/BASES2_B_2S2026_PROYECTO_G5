# Hallazgos de calidad de datos reportados al equipo

Los cuatro hallazgos se detectaron al construir `olympics.sp_historial_atleta` y afectan la interpretación de cualquier consulta de medallas, no solo la de este procedimiento. Todos son reproducibles con las consultas incluidas.

---

## 1. Participaciones duplicadas entre fuentes — impacto alto

La misma participación quedó registrada bajo dos nomenclaturas de evento, con campos complementarios.

```sql
SELECT e.nombre AS evento, p.posicion, p.edad, p.medalla
FROM olympics.PARTICIPACION p
JOIN olympics.EVENTO e            ON e.id_evento   = p.id_evento
JOIN olympics.EDICION_OLIMPICA eo ON eo.id_edicion = p.id_edicion
WHERE p.id_atleta = 93113 AND eo.anio = 2004 AND e.nombre LIKE N'%Butterfly%'
ORDER BY e.nombre;
```

Resultado:

```
100 metres Butterfly, Men (Olympic)     posición=1     edad=NULL    Gold
200 metres Butterfly, Men (Olympic)     posición=1     edad=NULL    Gold
Swimming Men's 100 metres Butterfly     posición=NULL  edad=19.00   Gold
Swimming Men's 200 metres Butterfly     posición=NULL  edad=19.00   Gold
```

**Consecuencia:** Michael Phelps (`id_atleta = 93113`) aparece con **56 medallas** (46 oro, 6 plata, 4 bronce). La cifra real es **28** (23 oro, 3 plata, 2 bronce). Exactamente el doble.

Alcance sobre los 64,842 medallistas:

```sql
WITH m AS (
  SELECT p.id_atleta,
         SUM(CASE WHEN e.nombre LIKE '%(Olympic%'     THEN 1 ELSE 0 END) AS f1,
         SUM(CASE WHEN e.nombre NOT LIKE '%(Olympic%' THEN 1 ELSE 0 END) AS f2
  FROM olympics.PARTICIPACION p
  JOIN olympics.EVENTO e ON e.id_evento = p.id_evento
  WHERE p.medalla IS NOT NULL
  GROUP BY p.id_atleta)
SELECT 'duplicado exacto' AS caso, COUNT(*) FROM m WHERE f1 = f2 AND f1 > 0
UNION ALL SELECT 'solo estilo 1', COUNT(*) FROM m WHERE f2 = 0
UNION ALL SELECT 'solo estilo 2', COUNT(*) FROM m WHERE f1 = 0
UNION ALL SELECT 'mezcla desigual', COUNT(*) FROM m WHERE f1 > 0 AND f2 > 0 AND f1 <> f2;
```

| Caso | Atletas |
|---|---:|
| Conteo exactamente duplicado | 15,766 |
| Solo nomenclatura de una fuente | 19,441 |
| Solo nomenclatura de la otra | 28,741 |
| Mezcla desigual | 894 |

Afecta a **~24% de los medallistas**: el traslape entre fuentes.

> Nota: el criterio `LIKE '%(Olympic%'` sirve para dimensionar el problema, pero **no es un clasificador confiable de fuente** — `Singles, Men (Intercalated)` es estilo fuente 1 y no lleva ese sufijo. Se usa solo como medición aproximada.

---

## 2. Atletas duplicados

```sql
SELECT a.id_atleta, a.nombre, a.sexo, a.fecha_nacimiento,
       (SELECT COUNT(*) FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta) AS participaciones
FROM olympics.ATLETA a WHERE a.nombre = N'Guy Forget' ORDER BY a.id_atleta;
```

```
17       Guy Forget   Male   1965-01-04   9 participaciones
223817   Guy Forget   M      NULL         1
223818   Guy Forget   M      NULL         1
223819   Guy Forget   M      NULL         1
```

Cuatro identidades para la misma persona. `17` es la canónica; las otras tres quedaron sin fusionar y sin datos biográficos.

El caso más extremo encontrado es **`Eric Lemming`, con diez `id_atleta`**:

```sql
SELECT a.id_atleta, a.nombre, a.fecha_nacimiento,
       (SELECT COUNT(*) FROM olympics.PARTICIPACION p WHERE p.id_atleta = a.id_atleta) AS participaciones
FROM olympics.ATLETA a WHERE a.nombre = N'Eric Lemming' ORDER BY a.id_atleta;
```

El `75674` es el canónico (nacido 1880-02-22 en Göteborg, 23 participaciones, 8 medallas); `257132`–`257140` están vacíos con una participación cada uno.

Como contrapeso: la deduplicación biográfica funcionó bien en general — solo **1 grupo** de homónimos comparte fecha de nacimiento.

---

## 3. Dominio de `sexo` sin homologar

```sql
SELECT sexo, COUNT(*) AS atletas FROM olympics.ATLETA GROUP BY sexo ORDER BY COUNT(*) DESC;
```

| Valor | Atletas |
|---|---:|
| `M` | 135,640 |
| `Male` | 106,325 |
| `F` | 55,279 |
| `Female` | 39,175 |

El mismo concepto en dos codificaciones. Cualquier consulta por sexo debe usar `IN ('F','Female')` o pierde la mitad de los registros. Es el hallazgo más fácil de corregir y el que más probablemente aparezca en la defensa.

---

## 4. Separador residual en `nombre_completo`

```sql
SELECT COUNT(*) FROM olympics.ATLETA
WHERE nombre_completo LIKE N'%' + NCHAR(8226) + N'%';
-- 145,252
```

El carácter `•` (U+2022) quedó como separador: `Lionel Andrés•Messi Cuccittini`. Afecta a prácticamente todas las 145,500 filas que tienen `nombre_completo`.

---

## Qué se hizo desde el inciso d

- **Hallazgos 3 y 4:** se normalizan **solo en la salida** del procedimiento (`M`→`Male`, `•`→espacio), conservando el valor crudo en `sexo_original`. No se modificó ninguna tabla.

- **Hallazgo 2 (atletas duplicados):** no se corrige. El SP lo maneja con su control de ambigüedad: cuando una búsqueda por nombre trae varios atletas, devuelve la lista de candidatos con sus conteos para que se elija el correcto.

- **Hallazgo 1 (eventos duplicados):** el SP **no unifica eventos**, pero sí **cuenta bien las medallas** y muestra las dos cifras lado a lado.

  El duplicado tiene una firma estructural aprovechable: dentro de un grupo (atleta, año, disciplina, medalla), las filas de una nomenclatura traen `posicion` y las de la otra traen `edad`, complementariamente. Si hay *n* filas con `posicion` y *n* con `edad`, el conteo real es *n*. Esto permite **contar** sin resolver **qué** evento es el duplicado de cuál.

  Cobertura sobre los 78,998 grupos con medalla: **78,847 determinables = 99.81%** (27,416 con firma limpia, 23,632 de una sola nomenclatura, 27,799 de una sola fila, 151 indeterminados). Reproducible con la prueba **T16** de `pruebas.sql`.

  La prueba **T17** verifica además que el único caso capaz de subcontar —un grupo con firma limpia que además tenga filas sin `posicion` ni `edad`— **no existe en esta base: 0 grupos**.

  Se aplica a **las dos cantidades**: medallas y participaciones. La firma sirve igual en filas sin medalla.

  **Validación contra la realidad, en tres atletas de épocas, deportes y países distintos.** El estimado acierta los tres desgloses en los tres casos:

  | Atleta | Época · deporte · NOC | Crudo | Estimado | Medallas reales |
  |---|---|---|---|---|
  | Michael Phelps (`93113`) | 2000–2016 · natación · USA | 46/6/4 = 56 | **23/3/2 = 28** | 23 oro, 3 plata, 2 bronce |
  | Chad le Clos (`119877`) | 2012–2016 · natación · RSA | 2/6/0 = 8 | **1/3/0 = 4** | 1 oro, 3 plata |
  | Nikolay Andrianov (`31000`) | 1972–1980 · gimnasia · URS | 14/10/6 = 30 | **7/5/3 = 15** | 7 oro, 5 plata, 3 bronce |

  En participaciones, Phelps pasa de `60` a `30`, que son sus eventos reales (1 en Sídney 2000 + 8 + 8 + 7 + 6).

  Y distingue el caso sin duplicación: Chad le Clos con `@temporada = 'Summer Youth'` da estimado **igual** al crudo (`1/3/1 = 5`), porque los Juegos de la Juventud vienen de una sola fuente. No divide todo entre dos.

  El método no recibe ninguna información externa sobre medallas: solo cuenta pares de `posicion`/`edad`.

  El conteo crudo nunca se altera, donde la firma no concluye se reporta el crudo con aviso, y no se escribe nada en la base.

Se evaluaron y descartaron dos vías de corrección más agresivas, ambas con medición:

1. `GROUP BY` por atleta/año/deporte/medalla — subcontaría: Phelps ganó oro en 100 m y 200 m mariposa el mismo año y quedarían fundidas.
2. Normalizar nombres de evento y emparejar los dos estilos — solo 495 pares limpios de 3,007 eventos, con 997 nombres que no encajan en ningún patrón y grupos ambiguos donde `Singles, Men (Olympic)`, `Singles, Men (Intercalated)` y `Singles, Men (Olympic (non-medal))` colapsan a la misma clave. Fusionarlos mezclaría un evento con medalla, uno de 1906 y uno sin medalla.

El detalle está en `prompts.md` §3.6.

**Unificar los eventos sigue siendo trabajo del Bloque 4.** Lo que hace el SP es contar bien y decir cómo lo hizo.

---

## Otro detalle de entorno (no es de datos)

`disciplina.csv` falla con `ROWTERMINATOR = '0x0a'` en **cualquier** checkout de Windows con `core.autocrlf=true`, no solo en una copia puntual. De los seis archivos configurados como LF en `04_bulk_load_staging.sql`, es el único con campos entrecomillados (21 filas como `53,31,"20 kilometres, Men"`), y ahí el `\r` sobrante rompe el parser en vez de ser absorbido por la limpieza `REPLACE(NCHAR(13))`.

Un `.gitattributes` que fije los finales de línea de `*.csv` haría el script determinista en todas las máquinas. Queda a criterio del responsable del inciso c.
