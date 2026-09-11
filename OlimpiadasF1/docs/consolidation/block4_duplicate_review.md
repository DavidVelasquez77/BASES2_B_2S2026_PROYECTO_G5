# Diagnóstico controlado — duplicados semánticos del Bloque 4

## Alcance

Esta ejecución solo diagnostica candidatos y no sobrescribe `data/processed/`, no modifica SQL y no ejecuta carga, reset, UPDATE, DELETE, TRUNCATE o DROP.

- Hashes de los CSV procesados antes/después del diagnóstico: **idénticos**.
- Conteos observados sin regeneración: ATLETA **338772**, EVENTO **3106**, PARTICIPACION **826605**.

## Causa concreta del caso Messi

El registro de Fuente 1 (`Lionel Messi`, athlete_id 111386) quedó como identidad base. El registro de Fuente 2 (`Lionel Andrs Messi Cuccittini`, ID 79053) quedó `UNMATCHED` porque el matching existente exige alias normalizado exacto; no implementa contención de tokens ni una segunda etapa contextual para nombres cortos/largos.

En eventos, la lógica existente usa `(id_disciplina, norm_aux(event_source))` como clave. Por eso `Football, Men (Olympic)` y `Football Men's Football` permanecen separados aunque comparten Football, género masculino, edición 2008, ARG, equipo Argentina y Gold.

## Resultados del diagnóstico

- Pares de atletas candidatos con contexto compartido: **77391**.
- Pares de atletas sugeridos para auto-merge contextual: **71706**.
- Pares de atletas ambiguos: **5685**.
- Pares de eventos candidatos: **928**.
- Aliases de eventos propuestos para auto-merge: **154**.

## Regla propuesta

Event aliases: misma jerarquía deporte-disciplina, mismo género inferible, firma de tokens equivalente después de normalizar minúsculas, puntuación, posesivos, Olympic(s), repeticiones y reordenamientos seguros; no fusionar si existe conflicto semántico.

Athletes: tokens significativos del nombre corto contenidos en el nombre largo, más misma edición, NOC, equipo, alias de evento y medalla; fecha igual o ausente en una sola fuente; un único candidato. Fechas distintas, NOC/equipo incompatibles o múltiples candidatos conservan `AMBIGUOUS`.

La fase siguiente debe actualizar la lógica general, ejecutar regresiones y regenerar datos solo después de aprobación externa de este diagnóstico.

## Ejemplos de candidatos de atletas

```text
id_atleta_a          nombre_a id_atleta_b          nombre_b    fecha_a fecha_b     edicion noc   equipo                   evento_a                   evento_b  similitud_nombre compatibilidad_contexto    decision_sugerida                                                                                                            razon
     332352   Landin Jacobsen      332361   Landin Jacobsen                    2024 Summer DEN  Denmark                        Men                        Men               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          2    Arnaud Boetsch      197394    Arnaud Boetsch 1969-04-01         1996 Summer FRA   France       Tennis Men's Doubles       Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          3      Jean Borotra      198422      Jean Borotra 1898-08-13         1924 Summer FRA France-2       Tennis Men's Doubles       Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          3      Jean Borotra      198421      Jean Borotra 1898-08-13         1924 Summer FRA   France       Tennis Mixed Doubles       Tennis Mixed Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          4   Jacques Brugnon      200760   Jacques Brugnon 1895-05-11         1920 Summer FRA France-1       Tennis Men's Doubles       Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          4   Jacques Brugnon      200761   Jacques Brugnon 1895-05-11         1924 Summer FRA France-1       Tennis Men's Doubles       Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          6 Nicolas Chatelain      205589 Nicolas Chatelain 1970-01-13         1992 Summer FRA France-1 Table Tennis Men's Doubles Table Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          7     Patrick Chila      206306     Patrick Chila 1969-11-27         2004 Summer FRA   France Table Tennis Men's Singles Table Tennis Men's Singles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          7     Patrick Chila      206305     Patrick Chila 1969-11-27         2000 Summer FRA France-1 Table Tennis Men's Doubles Table Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          7     Patrick Chila      206304     Patrick Chila 1969-11-27         1996 Summer FRA France-1 Table Tennis Men's Doubles Table Tennis Men's Doubles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          7     Patrick Chila      206303     Patrick Chila 1969-11-27         1996 Summer FRA   France Table Tennis Men's Singles Table Tennis Men's Singles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
          7     Patrick Chila      206307     Patrick Chila 1969-11-27         2008 Summer FRA   France Table Tennis Men's Singles Table Tennis Men's Singles               1.0                    ALTA AUTO_MERGE_CANDIDATE Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único.
```

## Ejemplos de aliases de eventos

```text
id_evento_a                                             nombre_a id_evento_b                                            nombre_b    deporte          disciplina genero_a genero_b  similitud                                                                             regla_detectada auto_merge_candidate                                                                                 razon
       2860                            Women's Team Pursuit Team        3044                                Women's Team Pursuit    Cycling       Cycling Track    WOMEN    WOMEN   0.888889 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
       2903                             Women's Team Sprint Team        3080                                 Women's Team Sprint    Cycling       Cycling Track    WOMEN    WOMEN   0.883721 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
       2976                              Men's Team Pursuit Team        3099                                  Men's Team Pursuit    Cycling       Cycling Track      MEN      MEN   0.878049 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
       2980                               Men's Team Sprint Team        3102                                   Men's Team Sprint    Cycling       Cycling Track      MEN      MEN   0.871795 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        503                         Rope Climbing, Men (Olympic)         933                               Rope Climbing, Men () Gymnastics Artistic Gymnastics      MEN      MEN   0.809524 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        908                          Volleyball, Women (Olympic)        2063                       Volleyball Women's Volleyball Volleyball          Volleyball    WOMEN    WOMEN   0.754717 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        637             Lightweight Double Sculls, Men (Olympic)        3011                     Lightweight Men's Double Sculls     Rowing              Rowing      MEN      MEN   0.735294 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        909                            Volleyball, Men (Olympic)        2036                         Volleyball Men's Volleyball Volleyball          Volleyball      MEN      MEN   0.734694 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        724                               Skeet, Women (Olympic)        2870                                         Skeet Women   Shooting            Shooting    WOMEN    WOMEN   0.733333 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        907                    Beach Volleyball, Women (Olympic)        2296           Beach Volleyball Women's Beach Volleyball Volleyball    Beach Volleyball    WOMEN    WOMEN   0.732394 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
        338                              Hockey, Women (Olympic)        1944                               Hockey Women's Hockey     Hockey              Hockey    WOMEN    WOMEN   0.731707 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
         77 Pole Archery, Small Birds, Individual, Men (Olympic)        2618 Archery Men's Pole Archery, Small Birds, Individual    Archery             Archery      MEN      MEN   0.729167 misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro                  YES Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente.
```

## Riesgo

El universo contiene **77391** pares candidatos; **71706** cumplen la regla propuesta y **5685** quedan ambiguos. Por el volumen y la posibilidad de homónimos entre fuentes, el riesgo estimado de aplicar un auto-merge masivo sin una segunda revisión de unicidad por fuente es **ALTO**. La salida actual solo propone candidatos; no fusiona ninguno. Los pares ambiguos no se fusionan automáticamente.

## Archivos generados

- `messi_duplicate_diagnostic.csv`
- `event_alias_candidates.csv`
- `event_alias_resolution_proposed.csv`
- `athlete_contextual_duplicate_candidates.csv`
- `block4_duplicate_review.md`
