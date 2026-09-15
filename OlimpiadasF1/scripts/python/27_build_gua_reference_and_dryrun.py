"""Build an auditable GUA Olympic roster and dry-run the identity correction.

The reference is obtained from Olympedia's per-edition GUA result pages.  The
script does not modify processed CSVs.  It only writes a roster, a candidate
mapping and a diagnostic report for review before application.
"""
from __future__ import annotations

import csv
import difflib
import argparse
import html
import re
import time
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "quality"
ROSTER_CSV = OUT / "gua_olympedia_olympic_roster.csv"
MAP_CSV = OUT / "gua_identity_mapping_dryrun.csv"
MD = OUT / "gua_identity_mapping_dryrun.md"
CACHE_DIR: Path | None = None


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active = False
        self.href = ""
        self.parts: list[str] = []
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.active = True
            self.href = dict(attrs).get("href") or ""
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.active:
            text = " ".join("".join(self.parts).split())
            self.anchors.append((self.href, text))
            self.active = False


def fetch(url: str) -> str:
    if CACHE_DIR is not None:
        cache_file = CACHE_DIR / (url.rstrip("/").rsplit("/", 1)[-1] + ".html")
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")
    last: Exception | None = None
    for attempt in range(5):
        try:
            req = Request(url, headers={"User-Agent": "OlimpiadasF1-data-audit/1.0"})
            with urlopen(req, timeout=45) as response:
                return response.read().decode("utf-8")
        except (HTTPError, URLError) as exc:
            last = exc
            time.sleep(4 + attempt * 3)
    raise RuntimeError(f"No se pudo descargar {url}: {last}")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").strip().lower())
    value = value.replace("�", "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\([^)]*\)", "", value)
    return re.sub(r"[^a-z0-9]+", "", value)


def read_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        value = (value or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def result_athletes(page_html: str) -> dict[str, dict[str, str]]:
    """Parse only the result table; footer biography links are excluded."""
    start = page_html.find('<table class="table">')
    end = page_html.find("</table>", start)
    table = page_html[start:end] if start >= 0 and end >= 0 else ""
    found: dict[str, dict[str, str]] = {}
    for raw_row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.S):
        row_text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw_row)).split())
        links = list(re.finditer(r'/athletes/(\d+)[^>]*>(.*?)</a>', raw_row, flags=re.S))
        for index, link in enumerate(links):
            ref_id = link.group(1)
            next_start = links[index + 1].start() if index + 1 < len(links) else len(raw_row)
            segment = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw_row[link.end():next_start])).split())
            if len(links) == 1:
                segment = row_text
            status = ""
            for candidate in ("DNS", "DNF", "DQ", "NP", "HM"):
                if re.search(rf"\b{candidate}\b", segment):
                    status = candidate
                    break
            record = found.setdefault(ref_id, {"name": "", "statuses": ""})
            record["name"] = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", link.group(2))).split())
            statuses = [x for x in record["statuses"].split(";") if x]
            if status and status not in statuses:
                statuses.append(status)
            record["statuses"] = ";".join(statuses)
    return found


def main() -> None:
    global CACHE_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=None)
    CACHE_DIR = parser.parse_args().cache_dir
    OUT.mkdir(parents=True, exist_ok=True)
    editions = read_csv("edicion_olimpica.csv")
    athletes = read_csv("atleta.csv")
    participations = read_csv("participacion.csv")
    nocs = read_csv("noc.csv")
    athlete_by_id = {row["id_atleta"]: row for row in athletes}
    noc_by_id = {row["id_noc"]: row.get("codigo_noc", "") for row in nocs}
    edition_by_id = {row["id_edicion"]: row for row in editions}

    country_parser = AnchorParser()
    country_html = fetch("https://www.olympedia.org/countries/GUA")
    country_parser.feed(country_html)
    olympedia_editions: list[tuple[str, int, str]] = []
    for href, text in country_parser.anchors:
        match = re.fullmatch(r"/countries/GUA/editions/(\d+)", href)
        if not match or text != "Results":
            continue
        # The adjacent edition link is not captured by this small parser, so
        # resolve the year/season from the local processed edition contract.
        # Olympedia IDs are stable and the mapping below is explicit by title.
        oid = match.group(1)
        if oid in {"10", "13", "17", "18", "19", "20", "21", "22", "43", "23", "24", "25", "26", "53", "54", "59", "61", "63"}:
            olympedia_editions.append((oid, 0, ""))

    # Stable known correspondence between Olympedia edition IDs and the
    # project's edition attributes.  This excludes Youth Olympic Games.
    correspondence = {
        "10": (1932, "Summer"), "13": (1952, "Summer"),
        "17": (1968, "Summer"), "18": (1972, "Summer"),
        "19": (1976, "Summer"), "20": (1980, "Summer"),
        "21": (1984, "Summer"), "22": (1988, "Summer"),
        "43": (1988, "Winter"), "23": (1992, "Summer"),
        "24": (1996, "Summer"), "25": (2000, "Summer"),
        "26": (2004, "Summer"), "53": (2008, "Summer"),
        "54": (2012, "Summer"), "59": (2016, "Summer"),
        "61": (2020, "Summer"), "63": (2024, "Summer"),
    }
    local_edition_by_year_season = {
        (int(row["anio"]), row["temporada"]): row["id_edicion"]
        for row in editions
    }

    roster: list[dict[str, str]] = []
    for olympedia_id, _, _ in olympedia_editions:
        year, season = correspondence[olympedia_id]
        local_id = local_edition_by_year_season.get((year, season), "")
        page_athletes = result_athletes(fetch(f"https://www.olympedia.org/countries/GUA/editions/{olympedia_id}"))
        for ref_id, athlete_data in page_athletes.items():
            text = athlete_data["name"]
            roster.append({
                "olympedia_edition_id": olympedia_id,
                "anio": str(year),
                "temporada": season,
                "id_edicion_local": local_id,
                "olympedia_athlete_id": ref_id,
                "nombre_referencia": text,
                "nombre_normalizado": normalize(text),
                "estados_observados": athlete_data["statuses"],
                "referencia": f"https://www.olympedia.org/countries/GUA/editions/{olympedia_id}",
            })

    # The country summary reports 263 Olympic Games participants. The result
    # pages also show ten non-starters in historical result tables: eight
    # DNS-only entries and two 1976 DNF-only entries. Keep them in the audit
    # roster, but exclude them from the 263-person reference set.
    non_starter_ids = {"923316", "923317", "1005418", "2404575", "2404577", "2305533", "2305534", "2305834", "1006150", "700460"}
    for row in roster:
        row["contado_en_referencia_263"] = "NO" if row["olympedia_athlete_id"] in non_starter_ids else "YES"
        row["motivo_referencia"] = "No starter en la tabla de resultados (DNS/DNF-only); excluido del conteo Olympedia 263." if row["contado_en_referencia_263"] == "NO" else "Participante de referencia."

    roster.sort(key=lambda row: (int(row["anio"]), row["temporada"], int(row["olympedia_athlete_id"])))
    with ROSTER_CSV.open("w", encoding="utf-8", newline="") as handle:
        fields = list(roster[0])
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(roster)

    refs_by_edition: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in roster:
        if row["contado_en_referencia_263"] == "YES":
            refs_by_edition[row["id_edicion_local"]].append(row)

    # Index every local GUA row by the names actually carried by that row and
    # by the athlete entity.  Matching is performed only within the same
    # edition, never across all years.
    local_rows_by_edition: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in participations:
        if noc_by_id.get(row.get("id_noc", "")) == "GUA" and edition_by_id.get(row.get("id_edicion", ""), {}).get("temporada") in {"Summer", "Winter"}:
            local_rows_by_edition[row["id_edicion"]].append(row)

    mapping_rows: list[dict[str, str]] = []
    for ref in roster:
        if ref["contado_en_referencia_263"] != "YES":
            continue
        edition_id = ref["id_edicion_local"]
        candidates: defaultdict[str, int] = defaultdict(int)
        candidate_names: defaultdict[str, set[str]] = defaultdict(set)
        for part in local_rows_by_edition.get(edition_id, []):
            athlete = athlete_by_id.get(part["id_atleta"], {})
            values = [
                athlete.get("nombre", ""), athlete.get("nombre_completo", ""),
                athlete.get("nombre_usado", ""), athlete.get("nombre_original", ""),
                athlete.get("otros_nombres", ""), athlete.get("apodos", ""),
                part.get("nombre_competencia", ""),
            ]
            normalized_values = {normalize(value) for value in values if normalize(value)}
            if ref["nombre_normalizado"] in normalized_values:
                candidates[part["id_atleta"]] += 1
                candidate_names[part["id_atleta"]].add(athlete.get("nombre", ""))

        if not candidates:
            # Keep a diagnostic fuzzy candidate only; it is not applicable
            # evidence and cannot cause a deletion or merge.
            all_names = sorted({normalize(athlete.get("nombre", "")) for athlete in athlete_by_id.values() if athlete.get("nombre")})
            close = difflib.get_close_matches(ref["nombre_normalizado"], all_names, n=3, cutoff=0.88)
            mapping_rows.append({
                "olympedia_edition_id": ref["olympedia_edition_id"],
                "id_edicion": edition_id,
                "anio": ref["anio"], "temporada": ref["temporada"],
                "olympedia_athlete_id": ref["olympedia_athlete_id"],
                "nombre_referencia": ref["nombre_referencia"],
                "id_atleta_candidato": "", "nombre_local_candidato": "",
                "filas_edicion_candidato": "0", "clasificacion": "UNMATCHED_REFERENCE",
                "decision": "REVIEW_REQUIRED",
                "motivo": "No existe coincidencia exacta segura en los campos de nombre de la participación/atleta dentro de la edición.",
                "candidatos_fuzzy_diagnostico": ";".join(close),
                "referencia": ref["referencia"],
            })
            continue

        ordered = sorted(candidates.items(), key=lambda item: (-item[1], int(item[0])))
        best_count = ordered[0][1]
        best = [athlete_id for athlete_id, count in ordered if count == best_count]
        classification = "STRONG_NAME_EDITION_MATCH" if len(best) == 1 else "AMBIGUOUS_SAME_NAME_EDITION"
        decision = "KEEP_CANDIDATE" if len(best) == 1 else "REVIEW_REQUIRED"
        chosen = best[0] if len(best) == 1 else ""
        mapping_rows.append({
            "olympedia_edition_id": ref["olympedia_edition_id"],
            "id_edicion": edition_id,
            "anio": ref["anio"], "temporada": ref["temporada"],
            "olympedia_athlete_id": ref["olympedia_athlete_id"],
            "nombre_referencia": ref["nombre_referencia"],
            "id_atleta_candidato": chosen,
            "nombre_local_candidato": " || ".join(sorted({name for athlete_id in best for name in candidate_names[athlete_id] if name})),
            "filas_edicion_candidato": str(sum(candidates[athlete_id] for athlete_id in best)),
            "clasificacion": classification,
            "decision": decision,
            "motivo": "Coincidencia exacta normalizada de nombre dentro de la misma edición; requiere consolidación de IDs si hay duplicados históricos." if len(best) == 1 else "Más de un ID local coincide con el mismo atleta y edición; no fusionar automáticamente.",
            "candidatos_fuzzy_diagnostico": "",
            "referencia": ref["referencia"],
        })

    with MAP_CSV.open("w", encoding="utf-8", newline="") as handle:
        fields = list(mapping_rows[0])
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(mapping_rows)

    unique_refs = {row["olympedia_athlete_id"] for row in roster if row["contado_en_referencia_263"] == "YES"}
    strong = [row for row in mapping_rows if row["decision"] == "KEEP_CANDIDATE"]
    ambiguous = [row for row in mapping_rows if row["clasificacion"] == "AMBIGUOUS_SAME_NAME_EDITION"]
    unmatched = [row for row in mapping_rows if row["clasificacion"] == "UNMATCHED_REFERENCE"]
    candidate_ids = {row["id_atleta_candidato"] for row in strong}
    md_lines = [
        "# Dry-run de reconciliación GUA por edición",
        "",
        "Estado: **NO_APLICADO**",
        "",
        "La referencia se obtuvo de las páginas de resultados de Guatemala por edición en Olympedia. Se excluyeron Youth Olympic Games porque el objetivo de 263 corresponde al conteo de Olympic Games.",
        "",
        f"- Atletas de referencia únicos: **{len(unique_refs)}**.",
        f"- Registros incluidos por edición: **{sum(row['contado_en_referencia_263'] == 'YES' for row in roster)}**.",
        f"- Filas de resultados fuera del conteo 263: **{sum(row['contado_en_referencia_263'] == 'NO' for row in roster)}**.",
        f"- Referencias con candidato único por nombre+edición: **{len(strong)}**.",
        f"- Referencias ambiguas: **{len(ambiguous)}**.",
        f"- Referencias sin candidato exacto: **{len(unmatched)}**.",
        f"- IDs locales candidatos distintos: **{len(candidate_ids)}**.",
        "",
        "## Regla de seguridad",
        "",
        "El dry-run no elimina participaciones ni fusiona entidades. Una asociación solo podrá retirarse cuando la referencia por edición demuestre que el atleta local no pertenece al roster GUA de esa edición. Las coincidencias ambiguas y los nombres sin candidato quedan documentados.",
        "",
        "## Archivos",
        "",
        f"- `{ROSTER_CSV.relative_to(ROOT)}`: roster de referencia por edición.",
        f"- `{MAP_CSV.relative_to(ROOT)}`: mapa candidato reproducible.",
        "",
        "Referencia principal: https://www.olympedia.org/countries/GUA",
    ]
    MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"reference_unique_athletes={len(unique_refs)}")
    print(f"roster_rows={len(roster)}")
    print(f"strong_reference_matches={len(strong)}")
    print(f"ambiguous_reference_matches={len(ambiguous)}")
    print(f"unmatched_reference_matches={len(unmatched)}")
    print(f"candidate_local_ids={len(candidate_ids)}")


if __name__ == "__main__":
    main()
