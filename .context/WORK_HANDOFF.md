# WORK HANDOFF - PROYECTO OLIMPIADAS FASE 1

## 1. Alcance del proyecto

Proyecto de Bases de Datos 2 - Fase 1.

Se debe construir una base de datos relacional unificada de información histórica de los Juegos Olímpicos utilizando cuatro fuentes:

1. Keith Galli Olympics Dataset
   https://github.com/KeithGalli/Olympics-Dataset

2. Kaggle - 120 years of Olympic history
   athlete_events.csv

3. Kaggle - Summer Olympics Medals 1896-2024
   olympics_dataset.csv

4. DataCamp - R Olympics
   datalab_export.csv

Además, Olympics.com debe utilizarse para revisión de calidad de información olímpica.

---

# 2. Responsabilidad del integrante actual

Este integrante únicamente debe completar:

## Inciso a

Modelo de datos y diagrama entidad-relación.

## Inciso b

Extraer, limpiar, homologar, consolidar y cargar la información de las cuatro fuentes a una base de datos relacional.

## Inciso c

Entregar todos los scripts utilizados para:

- creación de la base;
- tablas;
- claves primarias;
- claves foráneas;
- índices;
- carga de datos;
- archivos fuente.

NO debe implementar:

## Inciso d

Stored procedure por atleta.

## Inciso e

Stored procedure por país.

Estos serán realizados por otros dos integrantes.

Sin embargo, la base debe quedar completamente preparada para que los stored procedures puedan realizarse sin modificar el modelo.

---

# 3. Reglas dadas por el ingeniero

- Evitar Wizards.
- Todo debe quedar reproducible mediante scripts.
- No descartar datos útiles solo porque otras fuentes no los tengan.
- Los valores faltantes pueden almacenarse como NULL.
- Los IDs de las diferentes fuentes no representan necesariamente a la misma entidad.
- Las fuentes deben limpiarse, homologarse y consolidarse.
- La base final debe ser unificada.
- No deben mantenerse rastros de Fuente 1, Fuente 2, etc. dentro del modelo final.
- Los IDs originales se pueden utilizar durante ETL/matching, pero no deben permanecer como identificadores de la base unificada.
- Los agregados de populations.csv deben tomarse en cuenta.
- Código de país y código NOC deben conservarse por separado.
- Deporte y disciplina son diferentes y deben modelarse jerárquicamente utilizando información oficial.
- La sede debe ser una entidad y estar asociada al país.
- La medalla puede mantenerse dentro de PARTICIPACION.
- No es obligatorio crear una tabla RESULTADO.

---

# 4. Modelo ER actual

Las entidades finales son:

1. ENTIDAD_GEOGRAFICA
2. POBLACION
3. NOC
4. ATLETA
5. SEDE
6. EDICION_OLIMPICA
7. DEPORTE
8. DISCIPLINA
9. EVENTO
10. PARTICIPACION

No crear:

- FUENTE
- RESULTADO
- TIPO_MEDALLA
- MEDALLA

---

# 5. ENTIDAD_GEOGRAFICA

Actualmente se decidió:

ENTIDAD_GEOGRAFICA
- id_entidad INT PK
- nombre VARCHAR(150)
- codigo_pais CHAR(3) NULL

IMPORTANTE:

No agregar actualmente un atributo `tipo`.

Motivo:

populations.csv contiene países y también agregados como:

- Arab World
- High income
- Africa Eastern and Southern

El ingeniero confirmó que estos agregados deben tomarse en cuenta.

Se consideró agregar:

tipo = PAIS / REGION / GRUPO_ECONOMICO / AGREGADO

pero ese dato NO existe directamente en los CSV proporcionados.

Como el ingeniero todavía no ha confirmado que se pueda derivar de metadata externa, se decidió NO agregar información inventada al ER.

Las relaciones olímpicas como:

- país de nacimiento;
- nacionalidad;
- sede;
- país de fallecimiento;

deben homologarse durante ETL únicamente contra entidades que realmente correspondan a países.

---

# 6. POBLACION

POBLACION
- id_entidad INT PK FK
- anio SMALLINT PK
- poblacion BIGINT NULL

PK compuesta:

(id_entidad, anio)

El archivo original populations.csv tiene:

Country Name
Country Code
1960
1961
...
2023

Debe transformarse a:

entidad | año | población

---

# 7. NOC

NOC
- id_noc INT PK
- codigo_noc CHAR(3)
- nombre_noc VARCHAR(150)
- id_entidad INT FK NULL
- notas VARCHAR(500) NULL

Decisión confirmada con el ingeniero:

Conservar nombre y código NOC.

Ejemplo:

France
FRA

No asumir:

codigo_pais = codigo_noc

Ejemplo Alemania:

codigo_pais = DEU
codigo_noc = GER

La correspondencia debe ser explícita.

Un país puede tener múltiples NOC históricos:

Germany:
- GER
- GDR
- FRG
- SAA

Delegaciones especiales pueden tener:

id_entidad = NULL

Ejemplo:

ROT = Refugee Olympic Team

---

# 8. ATLETA

ATLETA
- id_atleta BIGINT PK
- nombre
- nombre_completo
- nombre_usado
- nombre_original
- otros_nombres
- apodos
- orden_nombre
- sexo
- fecha_nacimiento
- ciudad_nacimiento
- region_nacimiento
- id_pais_nacimiento FK
- id_pais_nacionalidad FK
- fecha_fallecimiento
- ciudad_fallecimiento
- region_fallecimiento
- id_pais_fallecimiento FK
- altura_cm
- peso_kg
- roles
- afiliaciones
- titulos
- latitud
- longitud

Los datos enriquecedores se conservan aunque solo aparezcan en una fuente.

Los valores ausentes quedan NULL.

---

# 9. SEDE

SEDE
- id_sede INT PK
- nombre VARCHAR(150)
- id_pais INT FK

La sede representa la ciudad.

Ejemplo:

Atenas -> Grecia

Una ciudad puede ser sede varias veces.

Ejemplo:

Paris:
- 1900
- 1924
- 2024

---

# 10. EDICION_OLIMPICA

EDICION_OLIMPICA
- id_edicion INT PK
- anio SMALLINT
- temporada VARCHAR(10)
- id_sede INT FK

UNIQUE recomendado:

(anio, temporada)

No mantener Games como atributo duplicado.

Games se deriva de:

año + temporada

---

# 11. Jerarquía deportiva

El ingeniero confirmó:

DEPORTE != DISCIPLINA

Jerarquía:

DEPORTE
    ↓
DISCIPLINA
    ↓
EVENTO

DEPORTE
- id_deporte
- nombre

DISCIPLINA
- id_disciplina
- id_deporte FK
- nombre

EVENTO
- id_evento
- id_disciplina FK
- nombre

La homologación debe apoyarse posteriormente en la fuente oficial olímpica.

---

# 12. PARTICIPACION

PARTICIPACION
- id_participacion BIGINT PK
- id_atleta BIGINT FK
- id_edicion INT FK
- id_evento BIGINT FK
- id_noc INT FK NULL
- id_pais_nacionalidad INT FK NULL
- equipo VARCHAR(250) NULL
- nombre_competencia VARCHAR(300) NULL
- edad DECIMAL NULL
- altura_cm_registrada DECIMAL NULL
- peso_kg_registrado DECIMAL NULL
- posicion INT NULL
- empatado BOOLEAN NULL
- estado_resultado VARCHAR(30) NULL
- medalla VARCHAR(20) NULL

---

# 13. Resultado

No se crea tabla RESULTADO.

Se almacena directamente en PARTICIPACION:

- posicion
- empatado
- estado_resultado
- medalla

Ejemplo normal:

posicion = 4
empatado = false
estado_resultado = NULL

Ejemplo empate:

Pos original = "=17"

Transformar:

posicion = 17
empatado = true
estado_resultado = NULL

Ejemplo especial:

DNS

Transformar:

posicion = NULL
estado_resultado = DNS

No almacenar FINISHED para resultados normales.

---

# 14. Medallas

No crear TIPO_MEDALLA ni MEDALLA.

PARTICIPACION.medalla puede contener:

- Gold
- Silver
- Bronze
- NULL

Los datasets registran la medalla en cada atleta.

En eventos grupales cada integrante puede tener:

Gold

en su propia participación.

Esto simplifica las consultas requeridas por el proyecto.

---

# 15. Columnas especiales conocidas

Fuente 1 RAW bios.csv incluye:

- Roles
- Sex
- Full name
- Used name
- Born
- Died
- NOC
- athlete_id
- Measurements
- Affiliations
- Nick/petnames
- Title(s)
- Other names
- Nationality
- Original name
- Name order

Fuente 1 CLEAN bios_locs.csv:

- athlete_id
- name
- born_date
- born_city
- born_region
- born_country
- NOC
- height_cm
- weight_kg
- died_date
- lat
- long

Fuente 1 RAW results.csv:

- Games
- Event
- Team
- Pos
- Medal
- As
- athlete_id
- NOC
- Discipline
- Nationality
- Unnamed: 7

`Unnamed: 7` fue comprobado como vacío y se puede descartar.

Fuente 1 CLEAN results.csv:

- year
- type
- discipline
- event
- as
- athlete_id
- noc
- team
- place
- tied
- medal

Fuente 1 noc_regions.csv:

- NOC
- region
- notes

Fuente 1 populations.csv:

- Country Name
- Country Code
- años 1960 a 2023

Fuente 2 athlete_events.csv:

- ID
- Name
- Sex
- Age
- Height
- Weight
- Team
- NOC
- Games
- Year
- Season
- City
- Sport
- Event
- Medal

Fuente 3 olympics_dataset.csv:

- player_id
- Name
- Sex
- Team
- NOC
- Year
- Season
- City
- Sport
- Event
- Medal

Fuente 4 datalab_export.csv:

- index
- id
- name
- sex
- age
- height
- weight
- team
- noc
- games
- year
- season
- city
- sport
- event
- medal

Fuente 4 contiene únicamente 100 filas y fue identificado como subconjunto compatible con Fuente 2.

No duplicar esos registros durante integración.

---

# 16. Transformaciones previstas

IDs originales:

- athlete_id
- ID
- player_id
- id

solo ETL/matching.

No quedan en modelo final.

Born:
descomponer a:
- fecha
- ciudad
- región
- país

Died:
descomponer a:
- fecha
- ciudad
- región
- país

Measurements:
descomponer a:
- altura
- peso

Games:
descomponer a:
- año
- temporada

Pos:
descomponer a:
- posicion
- empatado
- estado_resultado

No medal:
normalizar a NULL.

---

# 17. Filosofía ETL

NO:

CSV RAW
→ modelo final directamente

SÍ:

CSV RAW
→ profiling
→ limpieza
→ homologación
→ matching
→ deduplicación
→ consolidación
→ CSV procesados
→ scripts SQL
→ modelo final SQL Server

Nunca modificar:

data/raw/

Las transformaciones se escriben en:

data/intermediate/

y posteriormente:

data/processed/

---

# 18. Tecnología elegida

Base de datos:

Microsoft SQL Server 2025 Developer Edition

Se ejecuta mediante Docker.

Motivo:

La instalación nativa presentó problemas de localización/configuración regional.

Docker proporciona el mismo motor necesario para desarrollo y permite un entorno reproducible.

Contenedor:

olimpiadas-sqlserver

Puerto Windows:

1434

Puerto interno:

1433

SSMS:

conectar mediante:

localhost,1434

Authentication:

SQL Server Authentication

---

# 19. Docker

docker-compose.yml posee:

- volumen persistente SQL Server;
- montaje read-only de ./data.

Persistencia:

sqlserver_data:/var/opt/mssql

Datos:

./data:/var/opt/mssql/import:ro

Esto permite posteriormente usar rutas de contenedor como:

/var/opt/mssql/import/processed/...

en scripts BULK INSERT.

---

# 20. Estado SQL Server

Base creada:

OlimpiadasDB

Schemas:

stg
olympics

Archivo:

scripts/sql/00_create_database.sql

La base y schemas fueron creados por script, no mediante Wizard.

Persistencia verificada mediante:

docker compose down

docker compose up -d

Después de recrear el contenedor:

OlimpiadasDB
stg
olympics

continuaron existiendo.

---

# 21. Fuentes montadas en Docker

Actualmente SQL Server puede acceder a:

/var/opt/mssql/import/raw/

Se verificaron 10 CSV:

Fuente 1:
- clean/bios.csv
- clean/bios_locs.csv
- clean/noc_regions.csv
- clean/populations.csv
- clean/results.csv
- raw/bios.csv
- raw/results.csv

Fuente 2:
- athlete_events.csv

Fuente 3:
- olympics_dataset.csv

Fuente 4:
- datalab_export.csv

---

# 22. Python

Entorno:

.venv

Python:

3.14.7

Paquetes instalados actualmente:

- pandas
- numpy
- openpyxl
- RapidFuzz
- Unidecode

requirements.txt ya generado.

RapidFuzz NO se debe utilizar todavía.

Primero debe hacerse matching determinístico.

Fuzzy matching será únicamente para casos difíciles.

---

# 23. Manifiesto de fuentes

Existe:

scripts/python/00_source_manifest.py

Este script:

- recorre data/raw;
- encuentra los CSV;
- calcula tamaño;
- calcula hash SHA-256;
- registra URL de origen.

Genera:

docs/source_manifest.csv

Resultado actual:

10 archivos encontrados.

El manifiesto contiene:

- fuente
- archivo_relativo
- url_origen
- tamano_bytes
- sha256

Esto demuestra trazabilidad e integridad de los archivos originales.

NO implica crear una entidad FUENTE en el ER.

---

# 24. Documentación

El ingeniero indicó que TODO debe documentarse con capturas donde se vea fecha y hora.

Estructura actual aproximada:

docs/
├── ER/
│   └── ER_P1_G7.pdf
├── Evidence/
│   └── Evidences.md
├── img/
└── source_manifest.csv

Cada paso relevante del proyecto debe:

1. conservar script;
2. documentar qué se hizo;
3. explicar por qué;
4. registrar resultado;
5. tener evidencia visual cuando corresponda.

Nunca inventar capturas.

---

# 25. Evidencias requeridas para cerrar Bloque 1

1. SQL Server Docker
   - docker ps
   - olimpiadas-sqlserver
   - 1434 -> 1433

2. Versión SQL Server
   - SELECT @@VERSION
   - @@SERVERNAME
   - Edition
   - ProductVersion

3. Script 00_create_database.sql
   - creación de OlimpiadasDB
   - schema stg
   - schema olympics

4. Validación
   - OlimpiadasDB
   - stg
   - olympics

5. Persistencia Docker
   - docker compose down
   - docker compose up -d
   - BD continúa existiendo

6. Montaje de data
   - raw
   - intermediate
   - processed
   - 10 CSV visibles

7. Entorno Python
   - .venv
   - python --version
   - pip --version
   - pip list

8. Script 00_source_manifest.py
   - especialmente lógica SHA-256

9. Ejecución source manifest
   - Archivos encontrados: 10
   - ruta de salida

10. source_manifest.csv
    - mostrar columnas y varias filas

Toda captura debe mostrar fecha y hora del sistema.

---

# 26. Estado actual

BLOQUE 1:

Técnicamente terminado.

Pendiente:

cerrar formalmente la documentación y capturas en:

docs/Evidence/Evidences.md

NO iniciar Bloque 2 hasta terminar evidencias.

---

# 27. Próximo bloque

BLOQUE 2:

DATA PROFILING DE LOS 10 CSV.

Debe analizarse automáticamente:

- número de filas;
- columnas;
- tipos inferidos;
- nulos;
- porcentaje de nulos;
- duplicados exactos;
- cardinalidad;
- valores únicos;
- mínimo/máximo en fechas/números;
- codificación;
- posibles inconsistencias;
- valores especiales;
- ejemplos representativos.

Todavía NO limpiar datos.

Primero perfilar.

Cada resultado importante debe documentarse.

Para cada acción importante indicar:

EVIDENCIA:
qué captura debe tomar el usuario
qué debe verse
qué comando/script
y que fecha/hora sea visible.