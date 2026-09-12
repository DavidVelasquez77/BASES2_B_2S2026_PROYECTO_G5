# Cierre de aplicación semántica controlada

Estado materializado: **PASS**.

Conteos actuales: ATLETA=336418, EVENTO=2986, PARTICIPACION=713678; total de las diez entidades=1070909.

Se reemplazaron únicamente atleta.csv, evento.csv y participacion.csv. Los otros siete CSV se compararon contra el respaldo byte a byte. Los cuatro casos históricos de 2012 quedaron en una sola participación lógica por atleta, con Tallent Gold, Si Silver, Heffernan Bronze y Kirdyapkin DQ sin medalla.

La base se reconstruyó desde staging con el orden oficial; la prevalidación y las validaciones finales SQL quedaron en PASS. El loader usa LF (0x0a), verificado byte a byte en los CSV vigentes. El intento de reaplicación se detuvo por ABORT_STATE_CHANGED antes de escribir, como protección de idempotencia.

La comparación exacta Unicode de ATLETA.nombre se documenta en `docs/loading/unicode_validation.csv`: 26261 nombres no ASCII, 0 diferencias. La validación SQL materializada se copia en `docs/quality/semantic_apply_sql_validation.csv`.

No se modificaron data/raw ni data/intermediate durante esta aplicación y no se inició ningún bloque posterior.
