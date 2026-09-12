# MEDAL_SEMANTIC_DEDUPLICATION_DRYRUN

Estado: **MEDAL_SEMANTIC_DEDUPLICATION_REVIEW_REQUIRED**.

Esta fase es exclusivamente diagnóstica. No modifica `data/processed`, SQL Server, procedimientos, eventos, atletas ni el modelo físico.

## Método

Se agruparon temporalmente participaciones con medalla por id de atleta, edición, NOC, medalla y una clave semántica formada por deporte, disciplina, género, distancia, modalidad y representación canónica del evento. Se conservaron las etiquetas originales.
La regla determinista hipotética conserva primero una fila con posición poblada y, en empate, el menor `id_participacion`. Solo las filas adicionales dentro de grupos semánticos exactos entran al conjunto hipotético; no se ejecuta ningún DELETE.

## Candidatos críticos

Se revisaron 1017 de los 1,017 candidatos CRITICAL. Clasificación: CONFIRMED_DUPLICATE=1010, PROBABLE_DUPLICATE=0, LEGITIMATE_DISTINCT=7, HOMONYM=0, REVIEW=0.
La tabla de remoción hipotética contiene 1015 filas duplicadas confirmadas estructuralmente y produciría 712660 participaciones. No se eliminaron eventos ni se modificó ningún CSV.

## Atletas prioritarios

El detalle fila por fila de Paavo Nurmi, Mark Spitz y Usain Bolt está en `medal_focus_participations.csv`; el mapa de pares está en `medal_confirmed_duplicate_map.csv`.
- Paavo Nurmi: antes=18/6/0/24; después hipotético=9/3/0/12; oficial=9/3/0/12; estado=PASS.
- Mark Spitz: antes=10/1/2/13; después hipotético=9/1/1/11; oficial=9/1/1/11; estado=PASS.
- Usain Bolt: antes=13/0/0/13; después hipotético=8/0/0/8; oficial=8/0/0/8; estado=PASS.
- Michael Phelps: antes=23/3/2/28; después hipotético=23/3/2/28; oficial=23/3/2/28; estado=PASS.
- Larisa Latynina: antes=9/5/4/18; después hipotético=9/5/4/18; oficial=9/5/4/18; estado=PASS.
- Marit Bjørgen: antes=8/4/3/15; después hipotético=8/4/3/15; oficial=8/4/3/15; estado=PASS.
- Nikolay Andrianov: antes=7/5/3/15; después hipotético=7/5/3/15; oficial=7/5/3/15; estado=PASS.

## Beijing 2008

CHN pasa de 89 resultados Gold a 53 en el cálculo hipotético. La referencia publicada por el Comité Olímpico Chino reporta 51 Gold; el detalle comparativo está en `medal_dedup_beijing2008_preview.csv`. El valor actual 89 se mantiene como SUSPICIOUS y no se presenta como medallero oficial.

## Controles

- Guatemala medals: PASS — antes={'Silver': 1, 'Gold': 1, 'Bronze': 1}; después={'Silver': 1, 'Gold': 1, 'Bronze': 1}.
- London 2012 50km: PASS — antes=Robbie Heffernan=Bronze;Jared Tallent=Gold;Si Tianfeng=Silver;Sergey Kirdyapkin=DQ;Wang Zhen=Bronze;Chen Ding=Gold;Érick Barrondo=Silver;Érick Barrondo=DQ;Wang Zhen=Bronze;Wang Zhen=Bronze; después=Robbie Heffernan=Bronze;Jared Tallent=Gold;Si Tianfeng=Silver;Sergey Kirdyapkin=DQ;Wang Zhen=Bronze;Chen Ding=Gold;Érick Barrondo=Silver;Érick Barrondo=DQ;Wang Zhen=Bronze;Wang Zhen=Bronze.

## Integridad y límites

Processed SHA: MATCH; RAW: 10/10 MATCH; intermediate: 13/13 MATCH; SQL modificado: NO.
El resultado READY no autoriza aplicación. Si alguna cifra de control difiere, debe mantenerse REVIEW_REQUIRED y realizar una revisión manual antes de cualquier corrección controlada.

Fuentes IOC agregadas: Nurmi=https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=735245&parentDocumentId=161836&skipCopyright=true&skipWatermark=true; Spitz=https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3533222&parentDocumentId=2875325&skipCopyright=true&skipWatermark=true; Bolt=https://newsroom.olympics.com/record/919.
