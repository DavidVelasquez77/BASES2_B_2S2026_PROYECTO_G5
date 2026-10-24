# Guía para la calificación de la Fase 3 (MongoDB)

Calificación: 24 de octubre de 2026. El enunciado avisa: *"se les pedirá hacer consultas en el momento. Las consultas no deben tardar en mostrar los resultados."*

Copiar los comandos desde este archivo abierto en el **editor** (no en la vista previa ni en un PDF): ahí se pierden los `*` de `COUNT(*)` y similares.

## 1. Estado del proyecto

| Inciso | Qué pide el enunciado | Quién | Dónde | Estado |
|---|---|---|---|---|
| a | Cargar los datos de la Fase 1 en MongoDB, completos y con las correcciones | David | base `OlimpiadasF3`, 4 colecciones | 42/42 validaciones, 0 diferencias |
| b | Scripts de colecciones, índices y carga, con documentación de fecha y hora | David | `fase3/scripts/mongodb/00`–`05`, `fase3/docs/mongodb/`, `fase3/docs/Evidence/` | completo |
| c | Script que recibe el **nombre de un atleta** y muestra todo (participaciones, resultados, medallas) | **Valery** | `06_consulta_atleta.js`, `consulta_atleta.ps1/.sh`, `docs/inciso_c/` | completo |
| d | Script que recibe un **país** y muestra todo, incluido si fue sede y en qué años | Helado | `07_consulta_pais.js`, `consulta_pais.ps1/.sh`, `docs/inciso_d/` | completo |

## 2. Antes de calificar

1. Abrir **Docker Desktop** y esperar a que esté corriendo. El contenedor `olimpiadas-fase3-mongo-1` (MongoDB 8.0, puerto **27018**) arranca solo y conserva los datos en el volumen `mongo_fase3_data`.
2. Abrir PowerShell en la carpeta del proyecto:

```powershell
cd "C:\Users\valer\Desktop\SBD2\BASES2_B_2S2026_PROYECTO_G7"
```
→ Se ubica en la carpeta del proyecto.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```
→ Permite ejecutar los scripts `.ps1` en esta ventana (solo mientras esté abierta).

```powershell
docker exec olimpiadas-fase3-mongo-1 mongosh OlimpiadasF3 --quiet --eval "for (const n of ['atletas','entidades_geograficas','participaciones_por_pais','catalogo_olimpico']) print(n+' = '+db.getCollection(n).countDocuments({}))"
```
→ Comprueba la base: **167295 atletas, 282 entidades, 4856 particiones por país y 2590 registros de catálogo**.

3. **MongoDB Compass** (si piden ver la base en interfaz): conectar a `mongodb://127.0.0.1:27018/?directConnection=true`, base `OlimpiadasF3`.

## 3. Explicación general (≈ 1 minuto)

> "En la Fase 3 migramos los datos olímpicos de la Fase 1 a **MongoDB 8.0**, en Docker con almacenamiento persistente. En vez de copiar las 10 tablas relacionales como 10 colecciones, diseñamos **4 colecciones según las consultas que hay que responder**:
>
> - **`atletas`**: un documento por atleta con **todas sus participaciones embebidas**, cada una con su edición, sede, evento, disciplina, deporte y NOC. Es la que usa el inciso c: un atleta se lee completo **en una sola lectura, sin joins**.
> - **`participaciones_por_pais`**: las mismas participaciones vistas por país, **partidas en un documento por país y edición** (4,856 documentos). Se parte por edición para no acercarse al **límite de 16 MB por documento**; el más grande pesa 1.3 MB. Es la que usa el inciso d.
> - **`entidades_geograficas`**: cada país con su serie de población, sus NOC y las ediciones que organizó como sede.
> - **`catalogo_olimpico`**: deportes, disciplinas, eventos, ediciones, sedes y NOC, para no perder registros que no tienen participaciones.
>
> La carga se hace con scripts de `mongosh` que leen los 10 CSV de la Fase 1, validan conteos, tipos y referencias, y no escriben si algo falla. Las colecciones tienen **validadores JSON Schema** y hay **11 índices** para las búsquedas. La validación final compara **campo por campo** contra los CSV: **42 de 42 pruebas correctas y 0 diferencias**. Los incisos c y d son dos scripts que consultan atleta y país, con filtros, y responden en milisegundos porque usan esos índices."

## 4. Inciso c: consulta de atleta (tu parte)

Primer parámetro: el nombre. Filtros opcionales: `-Deporte`, `-Pais` (NOC representado), `-Anio`, `-Temporada`, `-Medalla` (oro, plata, bronce, cualquiera), `-Id`, `-Formato json`.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Usain Bolt"
```
→ Ficha completa: 10 participaciones, 4 ediciones, **8 oros** (el relevo de 2008 sale sin medalla porque el COI se la retiró).

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Michael Phelps" -Anio 2008 -Medalla oro
```
→ Filtros combinados: **8 de 30 participaciones**, los 8 oros de Pekín.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Michael Phelps"
```
→ Totales de Phelps: **30 participaciones y 28 medallas (23 oro, 3 plata, 2 bronce)**.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "nadia comaneci"
```
→ Búsqueda sin mayúsculas ni acentos: encuentra a **Nadia Comăneci**.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "José González"
```
→ Homónimos: muestra **14 candidatos** con su id y no escoge uno solo.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Luis López" -Pais MEX
```
→ Resuelve un homónimo con un filtro: queda solo el gimnasta mexicano (id 30488).

```powershell
.\fase3\scripts\consulta_atleta.ps1 -Id 93113
```
→ Elige un atleta por su id (93113 es Michael Phelps).

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Erick Barrondo"
```
→ Atleta guatemalteco: plata en 20 km marcha (Londres 2012) y descalificaciones.

```powershell
.\fase3\scripts\consulta_atleta.ps1 "Michael Phelps" -Deporte natacion
```
→ Si un filtro no coincide, muestra los valores que sí existen (los deportes están en inglés: `Swimming`).

**El `.js` es la consulta; el `.ps1` es solo un envoltorio.** La consulta real está en `fase3/scripts/mongodb/06_consulta_atleta.js`, en JavaScript nativo de `mongosh`, dentro de la función `consultaAtleta(nombre, opciones)` (en Compass se llama directamente; ver 6.4.1). Como `mongosh --file` no recibe parámetros como `"Simone Biles" -Anio 2016`, se le pasan por **variables de entorno** (`OLIMPIADAS_ATLETA`, `OLIMPIADAS_ANIO`, `OLIMPIADAS_PAIS`, `OLIMPIADAS_DEPORTE`, `OLIMPIADAS_TEMPORADA`, `OLIMPIADAS_MEDALLA`), el mismo patrón de los scripts de carga de David. `consulta_atleta.ps1` (Windows) y `consulta_atleta.sh` (Linux) solo arman esas variables y ejecutan el `.js`, con `mongosh` instalado o dentro del contenedor de Docker.

Si piden ver el `.js` funcionando **sin el envoltorio**:

```powershell
docker cp fase3\scripts\mongodb\06_consulta_atleta.js olimpiadas-fase3-mongo-1:/tmp/06_consulta_atleta.js
```
→ Copia el script dentro del contenedor de MongoDB.

```powershell
docker exec -e OLIMPIADAS_ATLETA="Lionel Messi" olimpiadas-fase3-mongo-1 mongosh --quiet --file /tmp/06_consulta_atleta.js
```
→ Ejecuta el `.js` directamente con `mongosh`, pasando el nombre por variable de entorno. Mismo resultado que el `.ps1`. Para un filtro, agregar otro `-e`, por ejemplo `-e OLIMPIADAS_ANIO=2008`.

**Cómo funciona (para explicarlo):**

- Usa **una sola colección, `atletas`**, y lee **un solo documento**: todo lo demás (edición, sede, evento, disciplina, deporte, NOC, medalla) ya viene embebido en sus participaciones.
- Búsqueda en 3 niveles: (1) nombre exacto con los 3 índices de nombre (`nombre`, `nombre_completo`, `nombre_usado`): **1 clave y 1 documento examinados, 20–40 ms**; (2) si no hay coincidencia exacta, una pasada sin distinguir mayúsculas ni acentos (≈ 0.5 s); (3) si quedan varios atletas, lista candidatos para elegir por id.
- También encuentra registros que perdieron las letras acentuadas en la fuente (`"Jos Gonzlez"`).
- Las medallas se cuentan solo desde el campo `medalla`; una posición 1 sin medalla no cuenta como oro.
- El filtro de país es el **NOC representado** en cada participación, no la nacionalidad.
- No se agregaron índices nuevos porque la validación de David exige exactamente 11.

## 5. Inciso d: consulta de país (Helado)

Primer parámetro: el país (nombre, código NOC o código ISO3). Filtros: `-Anio`, `-Temporada`, `-Deporte`, `-Medalla`, `-Limite` (filas de detalle a mostrar, por defecto 100), `-Formato json`.

```powershell
.\fase3\scripts\consulta_pais.ps1 "Guatemala"
```
→ Ficha de Guatemala: población, NOC `GUA`, **nunca fue sede**, 591 participaciones, 263 atletas y **3 medallas** (Barrondo plata 2012, Adriana Ruano oro 2024, Jean Pierre Brol bronce 2024).

```powershell
.\fase3\scripts\consulta_pais.ps1 GUA -Medalla cualquiera
```
→ Solo las participaciones con medalla de Guatemala.

```powershell
.\fase3\scripts\consulta_pais.ps1 "France" -Anio 2024 -Temporada verano -Medalla oro
```
→ Francia: **6 ediciones como sede** (París 1900, 1924 y 2024; Chamonix 1924; Grenoble 1968; Albertville 1992) y sus **16 oros** de París 2024.

```powershell
.\fase3\scripts\consulta_pais.ps1 "Argentina" -Deporte Football
```
→ Fútbol argentino: 233 participaciones y **4 medallas oficiales**: platas en Ámsterdam 1928 y Atlanta 1996, oros en Atenas 2004 y Pekín 2008 (82 medallas de atletas, porque cada jugador recibe la suya).

```powershell
.\fase3\scripts\consulta_pais.ps1 "peru" -Medalla cualquiera
```
→ Sin acentos ni mayúsculas: resuelve **Perú** y sus 5 medallas.

```powershell
.\fase3\scripts\consulta_pais.ps1 "United"
```
→ Nombre ambiguo: lista Emiratos Árabes Unidos, Reino Unido y Estados Unidos con sus códigos.

```powershell
.\fase3\scripts\consulta_pais.ps1 USA -Anio 2016 -Temporada verano
```
→ Estados Unidos en Río 2016: **121 medallas (46 oro, 37 plata, 38 bronce)**, la cifra oficial.

**Importante sobre `-Anio`:** un año puede tener **varias ediciones** (verano, invierno, Juegos de la Juventud). Sin `-Temporada verano`, USA 2016 da 127 medallas porque suma también los Juegos de la Juventud de Invierno de Lillehammer 2016. Si piden "un país en tal año", agregar **`-Temporada verano`** (o `invierno`). Lo mismo aplica al inciso c.

**Doble medallero:** el inciso d muestra dos números. El **medallero oficial del país** cuenta 1 medalla por prueba (un oro en fútbol es 1 medalla para el país). Las **medallas de atletas** cuentan una por cada integrante (el mismo oro en fútbol son 18 medallas físicas). Por eso Francia 2024 tiene 16 oros oficiales y 53 oros de atletas.

El `.js` (`07_consulta_pais.js`) define la función `consultaPais(pais, opciones)`; el `.ps1`/`.sh` es el envoltorio, igual que en el inciso c. En Compass se pega el archivo y se llama la función (sección 6.4.1).

**Cómo funciona:** usa **tres colecciones**: `entidades_geograficas` (el país), `participaciones_por_pais` (sus participaciones y medallas) y `catalogo_olimpico` solo como respaldo para el nombre de una ciudad sede. Busca el país en `entidades_geograficas` (índice `ix_entidades_nombre` o `ix_entidades_codigo_pais`), de ahí obtiene sus NOC y las ediciones que organizó, y lee sus particiones de `participaciones_por_pais` con el índice `ix_part_pais_edicion` (`id_entidad`, `anio`, `temporada`).

## 5b. Consultas en vivo: qué pueden pedir

El enunciado dice que el día de la calificación se harán consultas en el momento. Lo más probable es que el auxiliar **elija un atleta o un país** y pida ejecutar los scripts c y d, a veces con un filtro. Probado el 23/10:

| Si piden… | Comando | Tiempo |
|---|---|---|
| un atleta | `.\fase3\scripts\consulta_atleta.ps1 "Simone Biles"` | 20–40 ms |
| un atleta en un año, deporte o país | agregar `-Anio 2016 -Temporada verano`, `-Deporte Gymnastics`, `-Pais USA` | 20–40 ms |
| solo sus medallas | agregar `-Medalla cualquiera` (u `oro`, `plata`, `bronce`) | 20–40 ms |
| un país | `.\fase3\scripts\consulta_pais.ps1 MEX` | 25–700 ms |
| un país en un año | agregar `-Anio 2024 -Temporada verano` | < 100 ms |
| si un país fue sede | la ficha del país lo muestra en "HISTORIAL COMO SEDE" | — |

Atletas probados: Simone Biles (11 medallas), Lionel Messi (1 oro), Shelly-Ann Fraser-Pryce (8), Eliud Kipchoge (4), Rafael Nadal (2 oros), Michael Jordan (2 oros), Adriana Ruano (1 oro), Kevin Cordón (sin medallas).

**Importante: los países se escriben en inglés o con su código.** El inciso d **no reconoce nombres en español**: "Estados Unidos", "Alemania", "Brasil", "Japón", "España" responden "No se encontró". Si el auxiliar lo dice en español, usar el **código olímpico**:

| País | Código | País | Código | País | Código |
|---|---|---|---|---|---|
| Estados Unidos | `USA` | México | `MEX` | Guatemala | `GUA` |
| Alemania | `GER` | Cuba | `CUB` | El Salvador | `ESA` |
| Brasil | `BRA` | Argentina | `ARG` | Honduras | `HON` |
| Japón | `JPN` | Colombia | `COL` | Costa Rica | `CRC` |
| España | `ESP` | Perú | `PER` | Panamá | `PAN` |
| Reino Unido | `GBR` | Venezuela | `VEN` | Nicaragua | `NCA` |
| China | `CHN` | República Dominicana | `DOM` | Puerto Rico | `PUR` |
| Francia | `FRA` | Ecuador | `ECU` | Uruguay | `URU` |
| Italia | `ITA` | Bolivia | `BOL` | Paraguay | `PAR` |
| Canadá | `CAN` | Jamaica | `JAM` | Kenia | `KEN` |
| Corea del Sur | `KOR` | Rusia | `RUS` | Países Bajos | `NED` |
| Australia | `AUS` | | | | |

México funciona también por nombre, con o sin tilde. **No usar `CHI` para Chile** (ver la sección 8).

## 6. Demostración en MongoDB Compass (interfaz)

Los scripts de los incisos c y d **se ejecutan en la terminal**, porque reciben el nombre o el país como parámetro. Compass sirve para **mostrar de dónde sacan los datos** y **que usan índices**. Son las capturas `inciso_c_07`/`08` e `inciso_d_10`/`11`.

### 6.1 Conectar

1. Abrir **MongoDB Compass** (ya está instalado).
2. En el panel izquierdo debe estar la conexión `127.0.0.1:27018`; hacer clic para conectar. Si no está: **+ Add new connection**, pegar `mongodb://127.0.0.1:27018/?directConnection=true` y **Save & Connect**.
3. Desplegar **OlimpiadasF3**: aparecen las 4 colecciones.

### 6.2 Inciso c: el documento de un atleta

1. Abrir la colección **`atletas`**, pestaña **Documents**.
2. En la barra de filtro escribir (con el nombre del campo, si no **Find** queda bloqueado):

```
{ nombre: "Usain Bolt" }
```

3. Pulsar **Find**: sale **1 – 1 of 1**.
4. Desplegar **`participaciones: Array (10)`** y luego un elemento (por ejemplo el `1`): se ven `edicion` (año 2008, Beijing), `evento`, `posicion` y `medalla` **embebidos dentro del atleta**.

*Qué decir:* "Este es el único documento que lee el script del inciso c: el atleta trae dentro todas sus participaciones con la edición, el evento y la medalla, por eso no hacen falta joins."

5. Con el mismo filtro, pulsar **Explain** (vista **Visual Tree**): **IXSCAN** sobre **`ix_atletas_nombre`**, **1 documento devuelto, 1 examinado, 1 clave examinada, 0 ms**.

*Qué decir:* "La búsqueda por nombre usa el índice: MongoDB examina exactamente una clave y un documento, en lugar de recorrer los 167 mil atletas."

### 6.3 Inciso d: una partición de un país

1. Abrir la colección **`participaciones_por_pais`**, pestaña **Documents**.
2. Filtro (Guatemala es `id_entidad` 109):

```
{ id_entidad: 109, anio: 2012 }
```

3. **Find**: sale 1 documento, la partición de Guatemala en Londres 2012; dentro de `participaciones` está la plata de Érick Barrondo.

*Qué decir:* "Cada documento es un país en una edición; así ningún documento crece sin límite. El script del inciso d lee solo las particiones del país."

4. **Explain**: **IXSCAN** sobre **`ix_part_pais_edicion`**, 1 clave y 1 documento examinados.

### 6.4 Consultas en la consola de Compass (pestaña ">_ MONGOSH")

Con **Open MongoDB shell** se abre una consola dentro de Compass. Ahí se pueden hacer consultas directas a la base y también **ejecutar los incisos c y d como funciones** (6.4.1).

#### 6.4.1 Ejecutar los incisos c y d en Compass

1. Abrir `fase3/scripts/mongodb/06_consulta_atleta.js` en VS Code, seleccionar todo (`Ctrl + A`) y copiar (`Ctrl + C`).
2. En la consola de Compass, pegar (`Ctrl + V`) y Enter. Responde: *"Función consultaAtleta(nombre, opciones) lista"*.
3. Llamar la función (mismos filtros que en PowerShell, en minúsculas):

```
consultaAtleta("Usain Bolt")
```
→ La ficha completa de Bolt, igual que en la terminal.

```
consultaAtleta("Michael Phelps", { anio: 2008, temporada: "verano", medalla: "oro" })
```
→ Con filtros: un objeto `{ filtro: valor }`. Opciones: `id`, `deporte`, `pais`, `anio`, `temporada`, `medalla`, `formato`.

```
consultaAtleta(null, { id: 93113 })
```
→ Por id, sin nombre.

*Qué decir:* "El archivo define la función `consultaAtleta`. Desde la terminal, los envoltorios `.ps1` y `.sh` le pasan los parámetros por variables de entorno y la ejecutan; en la consola de mongosh o de Compass se pega el archivo y se llama la función directamente."

**Inciso d:** igual, pegando `fase3/scripts/mongodb/07_consulta_pais.js` (responde *"Función consultaPais(pais, opciones) lista"*). Se pueden pegar los dos archivos en la misma consola.

```
consultaPais("Guatemala")
```
→ La ficha completa de Guatemala.

```
consultaPais("France", { anio: 2024, temporada: "verano", medalla: "oro" })
```
→ Con filtros. Opciones: `anio`, `temporada`, `deporte`, `medalla`, `limite`, `formato`.

Si se cierra la pestaña de la consola, hay que volver a pegar los archivos.

**Qué se cambió para que funcione en la consola** (por si lo preguntan): antes, cada `.js` era un script que leía las variables de entorno y se ejecutaba de inmediato. Ahora todo su código está dentro de una función (`consultaAtleta` / `consultaPais`) que recibe los parámetros como argumentos. Al final del archivo, si existen las variables de entorno (lo que hacen los `.ps1`/`.sh`), se llama la función con ellas; si no existen (al pegarlo en la consola), solo queda definida. Las salidas anticipadas que usaban `quit()` ahora usan `return`, para no cerrar la consola, y un parámetro inválido lanza un error en vez de salir con código 1. La lógica de la consulta no cambió: se comprobó comparando la salida original y la nueva en 29 casos.

#### 6.4.2 Consultas directas

Primero:

```
use("OlimpiadasF3")
```
→ Selecciona la base.

Regla: `find` recibe un **objeto** `{ campo: "valor" }`. Escribir solo `find("Lionel Messi")` da error.

```
db.atletas.find({ nombre: "Lionel Messi" })
```
→ El documento completo del atleta.

```
db.atletas.find({ nombre: "Lionel Messi" }, { _id: 0, nombre: 1, "participaciones.edicion.anio": 1, "participaciones.evento.nombre": 1, "participaciones.medalla": 1 })
```
→ Solo algunos campos (proyección): año, evento y medalla. Messi: Pekín 2008, fútbol, oro.

```
db.atletas.countDocuments({ "participaciones.noc.codigo_noc": "GUA" })
```
→ Cuántos atletas representaron a Guatemala alguna vez: **263**.

```
db.atletas.find({ participaciones: { $elemMatch: { "noc.codigo_noc": "GUA", medalla: { $ne: null } } } }, { _id: 0, nombre: 1 })
```
→ Atletas guatemaltecos con medalla: **Érick Barrondo, Jean-Pierre Brol y Adriana Ruano**. `$elemMatch` exige que la misma participación cumpla las dos condiciones.

```
db.entidades_geograficas.findOne({ nombre: "France" }, { _id: 0, nombre: 1, ediciones_organizadas: 1 })
```
→ Las ediciones que organizó Francia (1900, 1924 verano e invierno, 1968, 1992 y 2024).

```
db.atletas.find({ nombre: "Lionel Messi" }).explain("executionStats").executionStats
```
→ Estadísticas de la búsqueda: `totalKeysExamined: 1`, `totalDocsExamined: 1` (usa el índice `ix_atletas_nombre`).

### 6.5 Otras vistas útiles

- **Indexes** (pestaña de cada colección): muestra los índices de esa colección. En `atletas` son 5 (el `_id_` y 4 secundarios).
- **Validation**: muestra el JSON Schema que valida cada documento.
- **Schema** → **Analyze**: muestra los campos y sus tipos a partir de una muestra.

## 7. Preguntas probables y cómo responderlas

**¿Por qué 4 colecciones y no 10?**
En MongoDB se modela según las consultas, no según las tablas. Las dos consultas del enunciado (atleta y país) se resuelven leyendo un documento o unas pocas particiones, sin joins. Las 10 tablas siguen representadas: dentro de los documentos y en el catálogo.

**¿Por qué embebieron las participaciones dentro del atleta?**
Porque el inciso c pide todo lo de un atleta, y así sale en una sola lectura. Un atleta tiene pocas participaciones (el documento más grande pesa 57 KB), así que el arreglo no crece sin control.

**¿No es redundante tener las participaciones en dos colecciones?**
Sí, a propósito: es **desnormalización**. Son dos vistas de lectura de los mismos hechos, con el mismo `id_participacion`. Nunca se suman entre colecciones. Se acepta la duplicación porque los datos son históricos (casi no cambian) y a cambio cada consulta es rápida.

**¿Por qué `participaciones_por_pais` está partida por edición?**
Por el **límite de 16 MB por documento** de MongoDB. Un solo documento con todo el historial de Estados Unidos podría acercarse a ese límite. Partido por edición, el documento más grande pesa 1.34 MB (medido con `$bsonSize`).

**¿Cómo saben que los datos están completos?**
`04_validate_import.js` hace 42 comprobaciones: conteos de cada colección, comparación campo por campo contra los CSV (más de 4 millones de campos de atleta y 5 millones de participación, **0 diferencias**), los 25,911 nombres con caracteres especiales comparados exactamente, los hashes SHA-256 de los 10 CSV, validadores, índices y tamaño BSON.

**¿Qué se corrigió respecto a la carga relacional?** (el enunciado dice *"si algo falló en la carga relacional, aquí debe estar corregido"*)
Se eliminaron 3 participaciones duplicadas (367,796 → 367,793), se corrigieron 3 participaciones contra Olympedia y el informe oficial del COI, y se corrigió la jerarquía evento → disciplina → deporte en los 2,069 eventos del catálogo. Todo está documentado con fecha y hash en `OlimpiadasF1/docs/quality/` y en `PHASE3_MONGODB.md`.

**¿Dónde está la fecha y hora de ejecución?** (inciso b)
En los reportes CSV de `fase3/docs/mongodb/` (inicio y fin de cada etapa, en UTC), en `PHASE3_MONGODB.md` (la carga tomó 110.8 s y los índices 3.5 s) y en las capturas del manual. Los incisos c y d imprimen su fecha y hora en cada consulta.

**¿Qué índices hay y para qué?**
11 secundarios. Para el inciso c: `ix_atletas_nombre`, `ix_atletas_nombre_completo` e `ix_atletas_nombre_usado`. Para el d: `ix_entidades_nombre`, `ix_entidades_codigo_pais`, `ix_part_pais_edicion` e `ix_part_pais_medalla`. Los demás sirven para el historial por edición, la población por año y el catálogo.

**¿Cómo demuestran que las consultas usan índices?**
Con `explain("executionStats")`: la búsqueda exacta de un atleta examina **1 clave y 1 documento** con `IXSCAN` sobre `ix_atletas_nombre` (captura `inciso_c_08_compass_explain.png`).

**¿Qué son los validadores?**
JSON Schema en modo `strict` con acción `error`: MongoDB rechaza cualquier documento que no cumpla la estructura y los tipos definidos en `01_create_collections.js`.

**¿Qué tipos de datos usaron?**
Fechas como `Date` (UTC), enteros como `Int32`/`Int64` y decimales (estatura, peso, edad) como `Decimal128` para no perder precisión. Los vacíos se guardan como `null`.

**¿Por qué el país es por NOC y no por nacionalidad?**
Porque un atleta compite representando a un comité olímpico (NOC). La nacionalidad se conserva aparte, sin mezclarla.

**¿Por qué mongosh y no Python u otro lenguaje?**
Para que todo el proyecto use la misma herramienta del motor. Los parámetros llegan por variables de entorno, y los `.ps1`/`.sh` son solo envoltorios para llamarlo cómodo en Windows y Linux.

## 8. Detalles conocidos y cómo responder

- **Chile y Bahréin (error de datos heredado de la Fase 1).** En `OlimpiadasF1/data/processed/noc.csv`, el NOC `CHI` (Chile) quedó ligado a la entidad "Channel Islands" (cuyo código ISO es `CHI`) y el NOC `BRN` (Bahréin) a "Brunei Darussalam" (ISO `BRN`). Se emparejó el código olímpico con el código ISO de otro país. Efecto: en el inciso d, `Chile` sale con 0 participaciones y sus 1,429 participaciones aparecen bajo "Channel Islands"; igual con Bahréin (229) bajo Brunei. El inciso c no se ve afectado (cada participación conserva su NOC "Chile"). Si aparece y no se corrigió: *"Es un error de emparejamiento NOC–país que viene de la Fase 1: el código olímpico CHI de Chile coincide con el código ISO de las Islas del Canal. Está identificado; la corrección son dos celdas de `noc.csv` y recargar."*

- **El formato JSON del inciso d** imprime con el formato de la consola de MongoDB (`poblacion: Long('17602431')`), que no es JSON estándar. Si lo notan: *"es la notación extendida de mongosh; cambiando `printjson` por `EJSON.stringify` sale JSON estándar"* (la corrección está probada). El inciso c sí produce JSON estándar.
- **En `INCISO_D_CONSULTA_PAIS.md` (sección 9.1)** los enlaces a evidencias apuntan a la computadora de Helado; los archivos sí están en `fase3/docs/inciso_d/evidencia/`.
- **Puertos:** la base del manual de David está en el **27017** (su instalación local); la de `compose.yaml`, que es la que usamos los demás, en el **27018**. Los scripts c y d detectan el contenedor solos.
- **Eventos fusionados en la Fase 1 (ejemplo: Brasil, Río 2016).** `consulta_pais.ps1 Brazil -Anio 2016 -Temporada verano -Medalla oro` da **6 oros**, pero Brasil ganó 7. El oro de **voleibol de playa** (Alison Cerutti y Bruno Schmidt) está dentro de "Volleyball, Men" (voleibol de sala), así que cuenta como un solo oro. Por la misma fusión, Evandro Gonçalves (9.º en playa) aparece con oro y "Posición 9". Si lo notan: *"El script cuenta bien sobre los datos cargados; la diferencia viene de la consolidación de la Fase 1, donde se fusionaron los eventos de voleibol de playa y de sala. MongoDB tiene exactamente lo de los CSV (validado campo por campo)."*
- **Atletas duplicados con y sin acentos:** por ejemplo "Wéverton Pereira da Silva" y "Wverton Silva", o "Éder Carbonera" y "der Carbonera". La deduplicación de la Fase 1 no los unió, por eso el conteo de "atletas únicos" del inciso d puede salir más alto que el real. El medallero oficial por prueba no se ve afectado, porque cuenta una medalla por evento.
- **Datos de la Fase 1:** algunos atletas parecen mal deduplicados (por ejemplo, "José González" id 6172 y 157204, o el 30486 que junta equitación, gimnasia y tiro). Los scripts muestran lo que está en la base; no corrigen datos porque solo leen.
- **Juegos de la Juventud:** un año puede tener varias ediciones; usar `-Temporada verano` para comparar con cifras oficiales.
