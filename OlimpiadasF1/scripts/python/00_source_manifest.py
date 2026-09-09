from pathlib import Path
import csv
import hashlib

# Raíz del proyecto
ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT / "data" / "raw"
DOCS_DIR = ROOT / "docs"

DOCS_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = DOCS_DIR / "source_manifest.csv"


SOURCE_URLS = {
    "fuente1": "https://github.com/KeithGalli/Olympics-Dataset",
    "fuente2": "https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-andresults",
    "fuente3": "https://www.kaggle.com/datasets/stefanydeoliveira/summer-olympics-medals-1896-2024",
    "fuente4": "https://www.datacamp.com/datalab/datasets/r-olympics",
}


def calcular_sha256(ruta: Path) -> str:
    sha256 = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha256.update(bloque)

    return sha256.hexdigest()


archivos = sorted(RAW_DIR.rglob("*.csv"))

with OUTPUT_FILE.open(
    "w",
    newline="",
    encoding="utf-8"
) as csvfile:

    writer = csv.writer(csvfile)

    writer.writerow([
        "fuente",
        "archivo_relativo",
        "url_origen",
        "tamano_bytes",
        "sha256"
    ])

    for archivo in archivos:

        relativo_raw = archivo.relative_to(RAW_DIR)

        fuente = relativo_raw.parts[0]

        writer.writerow([
            fuente,
            archivo.relative_to(ROOT).as_posix(),
            SOURCE_URLS.get(fuente, ""),
            archivo.stat().st_size,
            calcular_sha256(archivo)
        ])


print(f"Archivos encontrados: {len(archivos)}")
print(f"Manifiesto generado en: {OUTPUT_FILE}")