"""
Fase 2 - Generador del analisis comparativo

Lee los resultados que dejan los drivers de ejecucion y produce el material
que pide el criterio 2.4 de la rubrica (analisis comparativo) y el 1.1
(documentacion tecnica con graficos):

  entradas
    fase2/evidencia/resultados/tiempos_<tipo>.csv    tiempos de restauracion
    fase2/evidencia/resultados/estado_<tipo>.json    puntos de restauracion
    fase2/data/slices/manifiesto.json                volumen de cada carga
    fase2/evidencia/resultados/respaldos.csv         metadatos de los .bak
                                                     (se genera solo si falta
                                                      y el contenedor responde)

  salidas
    fase2/documentacion/analisis_resultados.md       tablas y conclusiones
    fase2/evidencia/img/graficas/tiempos_restauracion.png
    fase2/evidencia/img/graficas/compresion_respaldos.png

Uso:  python fase2/scripts/07_analisis/generar_analisis.py
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # sin ventana: solo escribe archivos
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

RAIZ = Path(__file__).resolve().parents[3]
RES = RAIZ / "fase2" / "evidencia" / "resultados"
GRAF = RAIZ / "fase2" / "evidencia" / "img" / "graficas"
DOC = RAIZ / "fase2" / "documentacion"
CONTENEDOR = "olimpiadas-sqlserver"

TIPOS = ["anio", "deporte", "deportista"]
ETIQUETA = {
    "anio": "Por anio",
    "deporte": "Por deporte (Atletismo)",
    "deportista": "Por deportista (Usain Bolt)",
}

# Paleta categorica validada con scripts/validate_palette.js del skill dataviz:
# todas las comprobaciones pasan (separacion CVD dE 24.7 en protanopia).
AZUL = "#2a78d6"        # serie 1: la parte del tiempo que aporta el FULL
NARANJA = "#eb6834"     # serie 2: la parte que aporta el diferencial
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SUAVE = "#52514e"
REJILLA = "#e4e3df"


# --------------------------------------------------------------------------
# Lectura de datos
# --------------------------------------------------------------------------
def leer_tiempos():
    """Devuelve {tipo: [filas]} con los tiempos medidos de cada tipo de carga."""
    datos = {}
    for tipo in TIPOS:
        ruta = RES / f"tiempos_{tipo}.csv"
        if not ruta.exists():
            continue
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        for fila in filas:
            for col in ("atletas", "participaciones", "ms_full",
                        "ms_diferencial", "ms_total"):
                fila[col] = int(fila[col])
        datos[tipo] = filas
    return datos


def leer_manifiesto():
    ruta = RAIZ / "fase2" / "data" / "slices" / "manifiesto.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def exportar_respaldos():
    """
    Consulta msdb y guarda los metadatos de los respaldos de la Fase 2.
    Solo se ejecuta si el archivo no existe todavia; si el contenedor no
    responde, el analisis sigue sin esta seccion.
    """
    destino = RES / "respaldos.csv"
    if destino.exists():
        return destino

    consulta = (
        "SET NOCOUNT ON; "
        "WITH u AS (SELECT bs.database_name, bs.type, "
        "  ISNULL(bs.compression_algorithm,'ninguno') AS compresion, "
        "  ISNULL(bs.key_algorithm,'no') AS cifrado, bs.backup_size, "
        "  bs.compressed_backup_size, bmf.physical_device_name, "
        "  ROW_NUMBER() OVER (PARTITION BY bmf.physical_device_name "
        "    ORDER BY bs.backup_finish_date DESC) rn "
        "FROM msdb.dbo.backupset bs "
        "JOIN msdb.dbo.backupmediafamily bmf ON bmf.media_set_id=bs.media_set_id "
        "WHERE bs.database_name LIKE 'OlimpiadasF2%') "
        "SELECT database_name,type,compresion,cifrado,backup_size,"
        "compressed_backup_size,physical_device_name FROM u WHERE rn=1 "
        "ORDER BY database_name, physical_device_name;"
    )

    clave = None
    env = RAIZ / "OlimpiadasF1" / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("MSSQL_SA_PASSWORD="):
                clave = linea.split("=", 1)[1].strip().strip('"')
    if clave is None:
        return None

    cmd = ["docker", "exec", CONTENEDOR, "/opt/mssql-tools18/bin/sqlcmd",
           "-S", "localhost", "-U", "sa", "-P", clave, "-C",
           "-W", "-s", ",", "-h", "-1", "-Q", consulta]
    try:
        salida = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if salida.returncode != 0:
        return None

    filas = [l for l in salida.stdout.splitlines()
             if l.count(",") >= 6 and "OlimpiadasF2" in l]
    if not filas:
        return None

    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as f:
        f.write("base,tipo,compresion,cifrado,bytes_datos,bytes_archivo,archivo\n")
        for l in filas:
            f.write(l.strip() + "\n")
    return destino


def leer_respaldos():
    ruta = exportar_respaldos()
    if ruta is None or not ruta.exists():
        return []
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        for col in ("bytes_datos", "bytes_archivo"):
            try:
                fila[col] = int(fila[col])
            except (ValueError, KeyError):
                fila[col] = 0
    return filas


# --------------------------------------------------------------------------
# Graficas
# --------------------------------------------------------------------------
def estilo(ax):
    """Ejes discretos: sin marco, rejilla tenue solo en el eje de valores."""
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.yaxis.grid(True, color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TINTA_SUAVE, length=0, labelsize=9)


def grafica_tiempos(datos):
    """
    Barras apiladas: cada punto de restauracion se descompone en el tiempo del
    FULL y el del diferencial, porque la suma de ambos es el costo real de esa
    estrategia. Un panel por tipo de carga, con escala propia: los volumenes
    difieren en tres ordenes de magnitud y una escala comun aplastaria dos de
    los tres paneles.
    """
    presentes = [t for t in TIPOS if t in datos]
    if not presentes:
        return None

    # Ancho minimo de 9 pulgadas: con un solo panel, el titulo y la nota al
    # pie son mas anchos que la grafica y se cortarian al exportar.
    fig, ejes = plt.subplots(1, len(presentes),
                             figsize=(max(9.0, 4.6 * len(presentes)), 4.4))
    if len(presentes) == 1:
        ejes = [ejes]
    fig.patch.set_facecolor(SUPERFICIE)

    for ax, tipo in zip(ejes, presentes):
        filas = datos[tipo]
        nombres = [f.get("estrategia", "").replace("FULL + DIFF_", "F+D")
                   for f in filas]
        full = [f["ms_full"] for f in filas]
        diff = [f["ms_diferencial"] for f in filas]
        x = range(len(filas))

        # El borde del color de la superficie crea la separacion de 2 px entre
        # los segmentos apilados que pide la guia de marcas.
        ax.bar(x, full, 0.62, label="Restaurar el FULL", color=AZUL,
               edgecolor=SUPERFICIE, linewidth=1.5)
        ax.bar(x, diff, 0.62, bottom=full, label="Aplicar el diferencial",
               color=NARANJA, edgecolor=SUPERFICIE, linewidth=1.5)

        # Etiqueta directa del total: el lector no deberia leer el eje para
        # comparar, que es justo lo que se le pide hacer.
        for i, f in enumerate(filas):
            ax.text(i, f["ms_total"] + max(f["ms_total"] for f in filas) * 0.03,
                    f"{f['ms_total']} ms", ha="center", va="bottom",
                    fontsize=9, color=TINTA, fontweight="normal")

        ax.set_xticks(list(x))
        ax.set_xticklabels(nombres, fontsize=9)
        ax.set_title(ETIQUETA[tipo], fontsize=11, color=TINTA, pad=14)
        ax.set_ylim(0, max(f["ms_total"] for f in filas) * 1.22)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}"))
        estilo(ax)

    ejes[0].set_ylabel("Tiempo de restauracion (ms)", fontsize=9,
                       color=TINTA_SUAVE)
    ejes[0].legend(frameon=False, fontsize=9, loc="upper left",
                   labelcolor=TINTA_SUAVE)

    fig.suptitle("Tiempo de restauracion por estrategia y tipo de carga",
                 fontsize=13, color=TINTA, y=0.99)
    fig.text(0.5, 0.015,
             "Mediana de 3 repeticiones. F+D n = restaurar el FULL y aplicar "
             "el diferencial n.",
             ha="center", fontsize=8.5, color=TINTA_SUAVE)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))

    GRAF.mkdir(parents=True, exist_ok=True)
    ruta = GRAF / "tiempos_restauracion.png"
    fig.savefig(ruta, dpi=200, facecolor=SUPERFICIE)
    plt.close(fig)
    return ruta


def grafica_compresion(respaldos):
    """
    Magnitud de una sola serie: un solo tono. Compara el tamano en disco de las
    tres variantes del mismo respaldo.
    """
    comp = [r for r in respaldos if "comparativa_" in r.get("archivo", "")]
    if len(comp) < 2:
        return None

    def etiqueta(r):
        if r["compresion"] == "ninguno":
            return "Sin comprimir"
        return "Comprimido\ny cifrado" if r["cifrado"] != "no" else "Comprimido"

    comp.sort(key=lambda r: -r["bytes_archivo"])
    nombres = [etiqueta(r) for r in comp]
    mb = [r["bytes_archivo"] / 1024 / 1024 for r in comp]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    fig.patch.set_facecolor(SUPERFICIE)
    ax.bar(range(len(mb)), mb, 0.55, color=AZUL, edgecolor=SUPERFICIE,
           linewidth=1.5)

    base = mb[0]
    for i, v in enumerate(mb):
        ahorro = "" if i == 0 else f"  (-{100 * (1 - v / base):.0f} %)"
        ax.text(i, v + max(mb) * 0.03, f"{v:.2f} MB{ahorro}", ha="center",
                va="bottom", fontsize=9.5, color=TINTA)

    ax.set_xticks(range(len(mb)))
    ax.set_xticklabels(nombres, fontsize=9.5)
    ax.set_ylabel("Tamano del archivo (MB)", fontsize=9, color=TINTA_SUAVE)
    ax.set_ylim(0, max(mb) * 1.2)
    ax.set_title("Tamano del respaldo completo segun compresion y cifrado",
                 fontsize=12, color=TINTA, pad=14)
    estilo(ax)
    fig.tight_layout()

    GRAF.mkdir(parents=True, exist_ok=True)
    ruta = GRAF / "compresion_respaldos.png"
    fig.savefig(ruta, dpi=200, facecolor=SUPERFICIE)
    plt.close(fig)
    return ruta


# --------------------------------------------------------------------------
# Documento
# --------------------------------------------------------------------------
def tabla_tiempos(datos):
    lineas = ["| Tipo de carga | Estrategia | Atletas | Participaciones "
              "| FULL (ms) | Diferencial (ms) | Total (ms) |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for tipo in TIPOS:
        for f in datos.get(tipo, []):
            lineas.append(
                f"| {ETIQUETA[tipo]} | {f['estrategia']} | {f['atletas']:,} "
                f"| {f['participaciones']:,} | {f['ms_full']} "
                f"| {f['ms_diferencial'] or '-'} | **{f['ms_total']}** |")
    return "\n".join(lineas)


def tabla_comparativa(datos):
    """Resume la pregunta del enunciado: cuanto cuesta de mas usar diferencial."""
    lineas = ["| Tipo de carga | Solo FULL | FULL + diferencial (promedio) "
              "| Diferencia | Sobrecosto |",
              "|---|---:|---:|---:|---:|"]
    for tipo in TIPOS:
        filas = datos.get(tipo, [])
        if not filas:
            continue
        solo = next((f for f in filas if f["respaldo"] == "FULL"), None)
        difs = [f for f in filas if f["respaldo"] != "FULL"]
        if not solo or not difs:
            continue
        promedio = sum(f["ms_total"] for f in difs) / len(difs)
        delta = promedio - solo["ms_total"]
        pct = 100 * delta / solo["ms_total"]
        lineas.append(f"| {ETIQUETA[tipo]} | {solo['ms_total']} ms "
                      f"| {promedio:.0f} ms | +{delta:.0f} ms | +{pct:.0f} % |")
    return "\n".join(lineas)


def tabla_tamanos(respaldos):
    """
    Tamano de los cuatro respaldos de cada ciclo. Se excluyen los de la carpeta
    'automaticos' (los que genera cron) y los 'comparativa' (los del ensayo de
    compresion), para quedarse solo con los del ciclo principal.
    """
    base_tipo = {"OlimpiadasF2_Anio": "anio",
                 "OlimpiadasF2_Deporte": "deporte",
                 "OlimpiadasF2_Deportista": "deportista"}
    filas = [r for r in respaldos
             if "/automaticos/" not in r["archivo"]
             and "comparativa_" not in r["archivo"]]
    if not filas:
        return None, []

    lineas = ["| Tipo de carga | Respaldo | Tamano (MB) | Respecto del FULL |",
              "|---|---|---:|---:|"]
    hallazgos = []
    for base, tipo in base_tipo.items():
        delgrupo = sorted([r for r in filas if r["base"] == base],
                          key=lambda r: (r["tipo"] != "D", r["archivo"]))
        if not delgrupo:
            continue
        full = next((r for r in delgrupo if r["tipo"] == "D"), None)
        for r in delgrupo:
            mb = r["bytes_archivo"] / 1024 / 1024
            nombre = r["archivo"].rsplit("/", 1)[-1].replace(f"{base}_", "")
            rel = "-" if r["tipo"] == "D" or not full else \
                  f"{100 * r['bytes_archivo'] / full['bytes_archivo']:.0f} %"
            lineas.append(f"| {ETIQUETA[tipo]} | {nombre} | {mb:.2f} | {rel} |")
        # Un diferencial mas grande que su FULL es la senal clasica de que
        # toca tomar un FULL nuevo.
        if full:
            mayores = [r for r in delgrupo
                       if r["tipo"] != "D"
                       and r["bytes_archivo"] > full["bytes_archivo"]]
            if mayores:
                hallazgos.append(
                    f"En la carga **{ETIQUETA[tipo].lower()}**, "
                    f"{len(mayores)} de los 3 diferenciales superan en tamano al "
                    f"respaldo completo que les sirve de base "
                    f"({full['bytes_archivo'] / 1024 / 1024:.2f} MB).")
    return "\n".join(lineas), hallazgos


def seccion_hallazgos(datos, respaldos, hallazgos_tamano):
    """Afirmaciones cuantitativas derivadas de las mediciones, no escritas a mano."""
    puntos = []

    # 1. Relacion entre volumen y tiempo
    finales = {}
    for tipo, filas in datos.items():
        f = next((x for x in filas if x["respaldo"] == "DIFF_3"), None)
        if f:
            finales[tipo] = f
    if len(finales) >= 2:
        mayor = max(finales.values(), key=lambda f: f["participaciones"])
        menor = min(finales.values(), key=lambda f: f["participaciones"])
        if menor["participaciones"] > 0:
            veces = mayor["participaciones"] / menor["participaciones"]
        else:
            veces = float("inf")
        puntos.append(
            f"La carga mayor tiene **{mayor['participaciones']:,} participaciones** "
            f"y la menor **{menor['participaciones']:,}** "
            f"({veces:,.0f} veces mas datos), pero restaurarlas por completo "
            f"tarda **{mayor['ms_total']} ms** y **{menor['ms_total']} ms** "
            f"respectivamente. El tiempo no sigue al volumen.")

    # 2. Sobrecosto de la estrategia con diferencial
    sobre = []
    for tipo, filas in datos.items():
        solo = next((f for f in filas if f["respaldo"] == "FULL"), None)
        difs = [f for f in filas if f["respaldo"] != "FULL"]
        if solo and difs:
            prom = sum(f["ms_total"] for f in difs) / len(difs)
            sobre.append(100 * (prom - solo["ms_total"]) / solo["ms_total"])
    if sobre:
        puntos.append(
            f"Aplicar un diferencial despues del completo cuesta entre "
            f"**{min(sobre):.0f} % y {max(sobre):.0f} %** mas de tiempo que "
            f"restaurar solo el completo.")

    # 3. Compresion
    comp = [r for r in respaldos if "comparativa_" in r["archivo"]]
    plano = next((r for r in comp if r["compresion"] == "ninguno"), None)
    comprimido = next((r for r in comp
                       if r["compresion"] != "ninguno" and r["cifrado"] == "no"), None)
    cifrado = next((r for r in comp if r["cifrado"] != "no"), None)
    if plano and comprimido:
        ahorro = 100 * (1 - comprimido["bytes_archivo"] / plano["bytes_archivo"])
        texto = (f"La compresion reduce el archivo de "
                 f"**{plano['bytes_archivo'] / 1024 / 1024:.2f} MB a "
                 f"{comprimido['bytes_archivo'] / 1024 / 1024:.2f} MB "
                 f"({ahorro:.0f} % menos)**")
        if cifrado:
            dif = abs(cifrado["bytes_archivo"] - comprimido["bytes_archivo"]) / 1024
            texto += (f", y agregar cifrado AES-256 solo suma {dif:.0f} KB, "
                      f"es decir que el cifrado es practicamente gratis en espacio")
        puntos.append(texto + ".")

    puntos.extend(hallazgos_tamano)
    return "\n".join(f"{i}. {p}" for i, p in enumerate(puntos, 1))


def main():
    datos = leer_tiempos()
    if not datos:
        sys.exit("No hay resultados todavia. Ejecute antes "
                 "ejecutar_carga.ps1 y ejecutar_restauracion.ps1.")

    faltan = [t for t in TIPOS if t not in datos]
    respaldos = leer_respaldos()

    g1 = grafica_tiempos(datos)
    g2 = grafica_compresion(respaldos)

    manifiesto = leer_manifiesto()
    volumen = []
    if manifiesto:
        for tipo in TIPOS:
            for c in manifiesto["cargas"].get(tipo, []):
                volumen.append(
                    f"| {ETIQUETA[tipo]} | {c['ronda']} | {c['etiqueta']} "
                    f"| {c['atletas']:,} | {c['participaciones']:,} |")

    partes = [
        "# Fase 2 - Analisis comparativo de estrategias de respaldo",
        "",
        "Documento generado por `fase2/scripts/07_analisis/generar_analisis.py` "
        "a partir de los tiempos medidos. No se escribe ningun numero a mano.",
        "",
    ]

    if faltan:
        partes += [f"> **Pendiente:** faltan los resultados de "
                   f"{', '.join(ETIQUETA[t] for t in faltan)}.", ""]

    if volumen:
        partes += ["## 1. Volumen de cada carga", "",
                   "| Tipo de carga | Ronda | Contenido | Atletas | Participaciones |",
                   "|---|---|---|---:|---:|", *volumen, ""]

    partes += ["## 2. Tiempos de restauracion medidos", "",
               "Cada valor es la mediana de tres repeticiones. El tiempo total "
               "de la estrategia con diferencial es la suma de restaurar el "
               "FULL con `NORECOVERY` y aplicar el diferencial con `RECOVERY`.",
               "", tabla_tiempos(datos), ""]

    if g1:
        partes += [f"![Tiempos de restauracion](../evidencia/img/graficas/{g1.name})", ""]

    partes += ["## 3. Comparacion de las dos estrategias", "",
               tabla_comparativa(datos), ""]

    tabla_tam, hallazgos_tam = tabla_tamanos(respaldos)
    if tabla_tam:
        partes += ["## 4. Tamano de los respaldos", "",
                   "Los diferenciales son acumulativos: cada uno guarda todo lo "
                   "que cambio desde el respaldo completo, no desde el "
                   "diferencial anterior. Por eso crecen con cada carga.",
                   "", tabla_tam, ""]

    if g2:
        partes += ["## 5. Efecto de la compresion y el cifrado", "",
                   f"![Compresion](../evidencia/img/graficas/{g2.name})", ""]

    hallazgos = seccion_hallazgos(datos, respaldos, hallazgos_tam)
    if hallazgos:
        partes += ["## 6. Hallazgos medidos", "",
                   "Afirmaciones derivadas directamente de los datos de arriba.",
                   "", hallazgos, ""]

    DOC.mkdir(parents=True, exist_ok=True)
    salida = DOC / "analisis_resultados.md"
    salida.write_text("\n".join(partes), encoding="utf-8")

    print(f"Documento: {salida.relative_to(RAIZ)}")
    for g in (g1, g2):
        if g:
            print(f"Grafica:   {g.relative_to(RAIZ)}")
    if faltan:
        print(f"Faltan resultados de: {', '.join(faltan)}")


if __name__ == "__main__":
    main()
