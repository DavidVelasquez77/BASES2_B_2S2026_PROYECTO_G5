# Revisión de la delegación GUA — 2020

Estado: **DIAGNOSTIC_ONLY**

Referencia de contraste: [https://www.olympedia.org/countries/GUA/editions/61](https://www.olympedia.org/countries/GUA/editions/61)

## Resultado

- Filas GUA en el CSV: **48**.
- IDs de atleta GUA: **47**.
- Delegación de referencia: **24 atletas**.
- Coincidencias de roster: **24**.
- Filas duplicadas de un atleta que sí aparece en el roster: **1**.
- Filas con nombre fuera del roster 2020: **23**.

## Interpretación

La comparación confirma una contaminación de matching en las filas GUA de 2020. El reporte no elimina ni reasigna filas: solo identifica las que requieren un mapa de corrección aprobado.

## Archivo generado

- `docs\quality\gua_2020_roster_review.csv`
- Comando: `python scripts/python/25_review_gua_2020_roster.py`
