"""Matching, deduplicación y consolidación reproducible del Bloque 4.

Lee únicamente los diez CSV de data/intermediate/cleaned y genera salidas en
data/intermediate/matching, data/processed y docs/consolidation. No modifica
data/raw, no crea tablas SQL y no aplica fuzzy matching automático.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from unidecode import unidecode


ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "intermediate" / "cleaned"
MATCH_DIR = ROOT / "data" / "intermediate" / "matching"
PROCESSED_DIR = ROOT / "data" / "processed"
CONSOLIDATION_DIR = ROOT / "docs" / "consolidation"
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_FILE = ROOT / "docs" / "source_manifest.csv"

INPUT_FILES = [
    "fuente1_clean_bios.csv",
    "fuente1_clean_bios_locs.csv",
    "fuente1_clean_noc_regions.csv",
    "fuente1_clean_populations_long.csv",
    "fuente1_clean_results.csv",
    "fuente1_raw_bios.csv",
    "fuente1_raw_results.csv",
    "fuente2_athlete_events.csv",
    "fuente3_olympics_dataset.csv",
    "fuente4_datalab_export.csv",
]

SOURCE_PRIORITY = {"fuente1": 0, "fuente2": 1, "fuente3": 2, "fuente4": 3}
MEDALS = {"gold": "Gold", "silver": "Silver", "bronze": "Bronze"}

# Explicit historical/code aliases. They are not inferred from equality of
# NOC and population codes; each appears in the audit criterion column.
NOC_COUNTRY_ALIASES = {
    "GER": "DEU",
    "GDR": "DEU",
    "FRG": "DEU",
    "SAA": "DEU",
    "GRE": "GRC",
    "NED": "NLD",
    "SUI": "CHE",
    "URS": "RUS",
}

# City-to-country mappings are deliberately explicit and auditable. Cities
# absent from this table keep id_pais NULL rather than receiving a guess.
CITY_COUNTRY_CODES = {
    "athens": "GRC", "athina": "GRC", "paris": "FRA", "st louis": "USA",
    "london": "GBR", "stockholm": "SWE", "antwerp": "BEL", "antwerpen": "BEL",
    "amsterdam": "NLD", "los angeles": "USA", "berlin": "DEU", "helsinki": "FIN",
    "melbourne": "AUS", "rome": "ITA", "roma": "ITA", "tokyo": "JPN",
    "mexico city": "MEX", "montreal": "CAN", "moskva": "RUS", "munich": "DEU",
    "moscow": "RUS", "seoul": "KOR", "barcelona": "ESP", "atlanta": "USA",
    "sydney": "AUS", "beijing": "CHN", "rio de janeiro": "BRA", "sochi": "RUS",
    "calgary": "CAN", "sarajevo": "BIH", "lillehammer": "NOR", "albertville": "FRA",
    "salt lake city": "USA", "torino": "ITA", "turin": "ITA", "vancouver": "CAN",
    "innsbruck": "AUT", "lake placid": "USA", "chamonix": "FRA",
    "garmisch partenkirchen": "DEU", "squaw valley": "USA", "cortina dampezzo": "ITA", "cortina d ampezzo": "ITA",
    "sankt moritz": "CHE", "st moritz": "CHE", "sapporo": "JPN", "grenoble": "FRA",
    "nagano": "JPN", "oslo": "NOR",
}

# Official Olympic terminology treats a discipline as a branch of a sport and
# an event as a competition under that branch. This map captures branches
# visible in the supplied labels. Labels not safely classified remain in the
# mapping report with PENDING_REVIEW and are retained as an explicit fallback.
SPORT_PARENT_OVERRIDES = {
    "diving": "Aquatics", "marathon swimming": "Aquatics", "swimming": "Aquatics",
    "synchronized swimming": "Aquatics", "artistic swimming": "Aquatics", "water polo": "Aquatics",
    "canoeing": "Canoeing", "canoe sprint": "Canoeing", "canoe slalom": "Canoeing",
    "cycling": "Cycling", "cycling road": "Cycling", "cycling track": "Cycling",
    "cycling bmx freestyle": "Cycling", "cycling bmx racing": "Cycling",
    "cycling mountain bike": "Cycling", "cycling road cycling mountain bike": "Cycling",
    "cycling road cycling track": "Cycling", "cycling road triathlon": "Cycling",
    "alpine skiing": "Skiing", "cross country skiing": "Skiing", "freestyle skiing": "Skiing",
    "ski jumping": "Skiing", "nordic combined": "Skiing", "military ski patrol": "Skiing",
    "ski mountaineering": "Skiing", "figure skating": "Skating", "speed skating": "Skating",
    "short track speed skating": "Skating", "bobsleigh": "Sliding Sports", "luge": "Sliding Sports",
    "skeleton": "Sliding Sports", "equestrian": "Equestrian", "equestrianism": "Equestrian",
    "equestrian dressage": "Equestrian", "equestrian jumping": "Equestrian",
    "equestrian eventing": "Equestrian", "artistic gymnastics": "Gymnastics",
    "rhythmic gymnastics": "Gymnastics", "trampoline gymnastics": "Gymnastics",
    "trampolining": "Gymnastics", "3x3 basketball": "Basketball",
    "3x3 basketball basketball": "Basketball", "baseball softball": "Baseball/Softball",
    "beach volleyball": "Volleyball", "rugby sevens": "Rugby",
}

IOC_PROGRAMME_REFERENCE = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3415338&parentDocumentId=3415336&skipCopyright=true&skipWatermark=true"
IOC_EVOLUTION_REFERENCE = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=174689&parentDocumentId=174657&skipCopyright=true&skipWatermark=true"

# Equivalencias nominales explícitas para vincular denominaciones NOC con la
# nomenclatura del dataset de población sin crear una segunda entidad país.
GEOGRAPHIC_NAME_ALIASES = {
    "great britain": "united kingdom",
    "russia": "russian federation",
    "south korea": "korea rep",
    "north korea": "korea dem peoples rep",
    "iran": "iran islamic rep",
    "egypt": "egypt arab rep",
    "venezuela": "venezuela rb",
    "slovakia": "slovak republic",
    "kyrgyzstan": "kyrgyz republic",
    "syria": "syrian arab republic",
    "laos": "lao pdr",
    "moldova": "moldova",
    "brunei": "brunei darussalam",
    "cape verde": "cabo verde",
    "macedonia": "north macedonia",
    "turkey": "turkiye",
    "yemen": "yemen rep",
}

# Canonical sport/discipline pairs. These are explicit so each automatic
# resolution can cite either the current IOC programme or its historical
# evolution reference. Generic multi-discipline labels remain pending.
CANONICAL_SPORT_DISCIPLINE = {
    "3x3 basketball": ("Basketball", "Basketball 3x3"),
    "3x3 basketball basketball": ("Basketball", "Basketball 3x3"),
    "aeronautics": ("Aeronautics", "Aeronautics"),
    "alpine skiing": ("Skiing", "Alpine Skiing"),
    "alpinism": ("Mountaineering", "Alpinism"),
    "archery": ("Archery", "Archery"),
    "art competitions": ("Art Competitions", "Art Competitions"),
    "artistic gymnastics": ("Gymnastics", "Artistic Gymnastics"),
    "artistic swimming": ("Aquatics", "Artistic Swimming"),
    "athletics": ("Athletics", "Athletics"),
    "australian rules football": ("Australian Rules Football", "Australian Rules Football"),
    "badminton": ("Badminton", "Badminton"),
    "bandy": ("Bandy", "Bandy"),
    "baseball": ("Baseball/Softball", "Baseball"),
    "basketball": ("Basketball", "Basketball"),
    "basque pelota": ("Basque Pelota", "Basque Pelota"),
    "beach volleyball": ("Volleyball", "Beach Volleyball"),
    "biathlon": ("Biathlon", "Biathlon"),
    "bobsleigh": ("Bobsleigh", "Bobsleigh"),
    "boxing": ("Boxing", "Boxing"),
    "breaking": ("Breaking", "Breaking"),
    "canoe slalom": ("Canoeing", "Canoe Slalom"),
    "canoe sprint": ("Canoeing", "Canoe Sprint"),
    "cricket": ("Cricket", "Cricket"),
    "croquet": ("Croquet", "Croquet"),
    "cross country skiing": ("Skiing", "Cross Country Skiing"),
    "curling": ("Curling", "Curling"),
    "cycling bmx freestyle": ("Cycling", "BMX Freestyle"),
    "cycling bmx racing": ("Cycling", "BMX Racing"),
    "cycling mountain bike": ("Cycling", "Mountain Bike"),
    "cycling road": ("Cycling", "Cycling Road"),
    "cycling track": ("Cycling", "Cycling Track"),
    "diving": ("Aquatics", "Diving"),
    "fencing": ("Fencing", "Fencing"),
    "figure skating": ("Skating", "Figure Skating"),
    "football": ("Football", "Football"),
    "freestyle skiing": ("Skiing", "Freestyle Skiing"),
    "glima": ("Glíma", "Glíma"),
    "golf": ("Golf", "Golf"),
    "gymnastics": ("Gymnastics", "Artistic Gymnastics"),
    "handball": ("Handball", "Handball"),
    "hockey": ("Hockey", "Hockey"),
    "hockey 5s": ("Hockey", "Hockey 5s"),
    "ice hockey": ("Ice Hockey", "Ice Hockey"),
    "jeu de paume": ("Jeu de Paume", "Jeu de Paume"),
    "judo": ("Judo", "Judo"),
    "karate": ("Karate", "Karate"),
    "lacrosse": ("Lacrosse", "Lacrosse"),
    "luge": ("Luge", "Luge"),
    "marathon swimming": ("Aquatics", "Marathon Swimming"),
    "military ski patrol": ("Skiing", "Military Ski Patrol"),
    "modern pentathlon": ("Modern Pentathlon", "Modern Pentathlon"),
    "motorboating": ("Motorboating", "Motorboating"),
    "nordic combined": ("Skiing", "Nordic Combined"),
    "polo": ("Polo", "Polo"),
    "racquets": ("Racquets", "Racquets"),
    "rhythmic gymnastics": ("Gymnastics", "Rhythmic Gymnastics"),
    "roque": ("Roque", "Roque"),
    "rowing": ("Rowing", "Rowing"),
    "rugby": ("Rugby", "Rugby"),
    "rugby sevens": ("Rugby", "Rugby Sevens"),
    "sailing": ("Sailing", "Sailing"),
    "savate": ("Savate", "Savate"),
    "shooting": ("Shooting", "Shooting"),
    "short track speed skating": ("Skating", "Short Track Speed Skating"),
    "skateboarding": ("Roller Sports", "Skateboarding"),
    "skeleton": ("Bobsleigh", "Skeleton"),
    "ski jumping": ("Skiing", "Ski Jumping"),
    "ski mountaineering": ("Ski Mountaineering", "Ski Mountaineering"),
    "snowboarding": ("Skiing", "Snowboard"),
    "softball": ("Baseball/Softball", "Softball"),
    "speed skating": ("Skating", "Speed Skating"),
    "speed skiing": ("Skiing", "Speed Skiing"),
    "sport climbing": ("Sport Climbing", "Sport Climbing"),
    "surfing": ("Surfing", "Surfing"),
    "swimming": ("Aquatics", "Swimming"),
    "synchronized swimming": ("Aquatics", "Artistic Swimming"),
    "table tennis": ("Table Tennis", "Table Tennis"),
    "taekwondo": ("Taekwondo", "Taekwondo"),
    "tennis": ("Tennis", "Tennis"),
    "trampoline gymnastics": ("Gymnastics", "Trampoline Gymnastics"),
    "trampolining": ("Gymnastics", "Trampoline Gymnastics"),
    "triathlon": ("Triathlon", "Triathlon"),
    "tug of war": ("Tug-of-War", "Tug-of-War"),
    "volleyball": ("Volleyball", "Volleyball"),
    "water polo": ("Aquatics", "Water Polo"),
    "weightlifting": ("Weightlifting", "Weightlifting"),
    "winter pentathlon": ("Winter Pentathlon", "Winter Pentathlon"),
}

GENERIC_DISCIPLINE_LABELS = {"baseball softball", "canoeing", "cycling", "equestrian", "equestrianism", "mixed sports", "wrestling"}


def read_csv(name: str) -> pd.DataFrame:
    path = CLEAN_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Falta intermedio requerido: {path}")
    return pd.read_csv(path, dtype=object, keep_default_na=False, na_filter=False, low_memory=False)


def text(value: Any) -> str:
    if value is None or value is pd.NA:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def first_nonempty(*values: Any) -> str:
    for value in values:
        result = text(value)
        if result:
            return result
    return ""


def norm_aux(value: Any) -> str:
    value = text(value)
    if not value:
        return ""
    value = unidecode(value).casefold().replace("•", " ")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def norm_code(value: Any) -> str:
    return re.sub(r"\s+", "", text(value).upper())


def norm_sex(value: Any) -> str:
    key = norm_aux(value)
    return {"m": "M", "male": "M", "man": "M", "f": "F", "female": "F", "woman": "F"}.get(key, key.upper())


def norm_scalar(value: Any) -> str:
    value = text(value)
    if not value:
        return ""
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return norm_aux(value)


def number(value: Any) -> Any:
    value = text(value)
    if not value:
        return pd.NA
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NA
    if float(parsed).is_integer():
        return int(parsed)
    return float(parsed)


def integer(value: Any) -> Any:
    parsed = number(value)
    if parsed is pd.NA:
        return pd.NA
    return int(parsed)


def json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def sort_id(value: Any) -> tuple[int, Any]:
    value = text(value)
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def raw_hash_validation() -> pd.DataFrame:
    manifest = pd.read_csv(MANIFEST_FILE, dtype=str, keep_default_na=False)
    expected = dict(zip(manifest["archivo_relativo"], manifest["sha256"]))
    rows = []
    for path in sorted(RAW_DIR.rglob("*.csv")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rel = "data/raw/" + path.relative_to(RAW_DIR).as_posix()
        rows.append({"archivo_relativo": rel, "sha256_manifest": expected.get(rel, ""), "sha256_actual": digest,
                     "estado": "MATCH" if expected.get(rel) == digest else "MISMATCH"})
    result = pd.DataFrame(rows)
    if len(result) != 10 or not (result["estado"] == "MATCH").all():
        raise RuntimeError("La integridad RAW no es 10/10; proceso detenido.")
    return result


def source1_master(bios: pd.DataFrame, locs: pd.DataFrame, raw_bios: pd.DataFrame) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    loc_by_id = {text(row.athlete_id): row._asdict() for row in locs.itertuples(index=False)}
    bio_by_id = {text(row.athlete_id): row._asdict() for row in bios.itertuples(index=False)}
    raw_by_id = {text(row.athlete_id): row._asdict() for row in raw_bios.itertuples(index=False)}
    masters: dict[str, dict[str, Any]] = {}
    matching_rows = []
    for athlete_id in sorted(bio_by_id, key=sort_id):
        b, l, r = bio_by_id[athlete_id], loc_by_id.get(athlete_id, {}), raw_by_id.get(athlete_id, {})
        fields = {
            "nombre": first_nonempty(b.get("name"), r.get("used_name"), r.get("full_name"), r.get("original_name")),
            "nombre_completo": r.get("full_name", ""), "nombre_usado": r.get("used_name", ""),
            "nombre_original": r.get("original_name", ""), "otros_nombres": r.get("other_names", ""),
            "apodos": r.get("nick_petnames", ""), "orden_nombre": r.get("name_order", ""),
            "sexo": r.get("sex", ""), "fecha_nacimiento": first_nonempty(b.get("born_date"), r.get("born_date")),
            "ciudad_nacimiento": first_nonempty(b.get("born_city"), r.get("born_city")),
            "region_nacimiento": first_nonempty(b.get("born_region"), r.get("born_region")),
            "pais_nacimiento_valor": first_nonempty(b.get("born_country"), r.get("born_country")),
            "nacionalidad": r.get("nationality", ""), "fecha_fallecimiento": first_nonempty(b.get("died_date"), r.get("died_date")),
            "ciudad_fallecimiento": first_nonempty(r.get("died_city"), b.get("died_city")),
            "region_fallecimiento": first_nonempty(r.get("died_region"), b.get("died_region")),
            "pais_fallecimiento_valor": first_nonempty(r.get("died_country"), b.get("died_country")),
            "altura_cm": first_nonempty(b.get("height_cm"), r.get("height_cm")),
            "peso_kg": first_nonempty(b.get("weight_kg"), r.get("weight_kg")),
            "roles": r.get("roles", ""), "afiliaciones": r.get("affiliations", ""),
            "titulos": r.get("titles", ""), "latitud": first_nonempty(l.get("lat"), b.get("lat")),
            "longitud": first_nonempty(l.get("long"), b.get("long")),
            "noc_nombre": first_nonempty(b.get("noc_nombre"), r.get("noc_nombre")),
        }
        masters[athlete_id] = fields
        matching_rows.append({"fuente": "fuente1", "archivo": "data/intermediate/cleaned/fuente1_clean_bios.csv",
                              "id_original": athlete_id, "nombre_original": fields["nombre"],
                              "id_atleta_global": None, "tipo_match": "SOURCE1_BASE", "nivel_confianza": "A",
                              "criterio_match": "Identidad base de fuente 1 por athlete_id dentro de la misma fuente.",
                              "score_fuzzy": "", "estado": "MATCHED", "candidatos": "[]"})
    return masters, matching_rows


def resolve_sport_label(label: Any) -> tuple[str, str, str, str, str]:
    original = text(label)
    key = norm_aux(original)
    parenthetical = re.match(r"^\s*(.*?)\s*\((.*?)\)\s*$", original)
    if parenthetical:
        discipline_raw, sport_raw = parenthetical.group(1).strip(), parenthetical.group(2).strip()
        canonical = CANONICAL_SPORT_DISCIPLINE.get(norm_aux(discipline_raw))
        discipline = canonical[1] if canonical else discipline_raw
        sport = sport_raw
        return sport, discipline, "jerarquía explícita Discipline (Sport) en Fuente 1", IOC_EVOLUTION_REFERENCE, "RESOLVED"
    if key in CANONICAL_SPORT_DISCIPLINE:
        sport, discipline = CANONICAL_SPORT_DISCIPLINE[key]
        historical = key in {"aeronautics", "alpinism", "art competitions", "australian rules football", "basque pelota", "croquet", "glima", "jeu de paume", "motorboating", "polo", "racquets", "roque", "savate", "tug of war", "winter pentathlon"}
        criterion = "denominación histórica documentada en la evolución del programa olímpico" if historical else "denominación canónica contrastada con el programa olímpico"
        return sport, discipline, criterion, IOC_EVOLUTION_REFERENCE if historical else IOC_PROGRAMME_REFERENCE, "RESOLVED"
    if key in GENERIC_DISCIPLINE_LABELS or "," in original:
        sport = CANONICAL_SPORT_DISCIPLINE.get(key, (original, original))[0]
        return sport, original, "etiqueta genérica o multivalor; no permite identificar una disciplina única", IOC_PROGRAMME_REFERENCE, "PENDING_REVIEW"
    return original, original, "sin correspondencia oficial suficientemente específica", IOC_EVOLUTION_REFERENCE, "PENDING_REVIEW"


def resolve_sport_record(label: Any, event: Any) -> tuple[str, str, str, str, str]:
    sport, discipline, criterion, evidence, state = resolve_sport_label(label)
    if state == "RESOLVED":
        return sport, discipline, criterion, evidence, state
    label_key, event_key = norm_aux(label), norm_aux(event)
    resolved: tuple[str, str] | None = None
    if label_key == "wrestling":
        if "greco roman" in event_key:
            resolved = ("Wrestling", "Wrestling Greco-Roman")
        elif "freestyle" in event_key:
            resolved = ("Wrestling", "Wrestling Freestyle")
    elif label_key == "canoeing" and event_key:
        resolved = ("Canoeing", "Canoe Slalom" if "slalom" in event_key else "Canoe Sprint")
    elif label_key in {"equestrian", "equestrianism"}:
        if "dressage" in event_key:
            resolved = ("Equestrian", "Equestrian Dressage")
        elif "three day" in event_key or "eventing" in event_key:
            resolved = ("Equestrian", "Equestrian Eventing")
        elif "vaulting" in event_key:
            resolved = ("Equestrian", "Equestrian Vaulting")
        elif "four in hand" in event_key:
            resolved = ("Equestrian", "Equestrian Driving")
        elif any(token in event_key for token in ["jumping", "high jump", "long jump", "hacks and hunter"]):
            resolved = ("Equestrian", "Equestrian Jumping")
    elif label_key == "baseball softball":
        if "baseball" in event_key:
            resolved = ("Baseball/Softball", "Baseball")
        elif "softball" in event_key:
            resolved = ("Baseball/Softball", "Softball")
    elif label_key in {"marathon swimming swimming"}:
        resolved = ("Aquatics", "Marathon Swimming" if "10km" in event_key or "10 km" in event_key else "Swimming")
    elif label_key in {"cycling", "cycling road cycling mountain bike", "cycling road cycling track", "cycling road triathlon"}:
        if "cross country" in event_key or "mountain" in event_key:
            resolved = ("Cycling", "Mountain Bike")
        elif label_key == "cycling road triathlon" and "individual" in event_key and "time trial" not in event_key:
            resolved = ("Triathlon", "Triathlon")
        elif any(token in event_key for token in ["road race", "individual time trial", "team time trial", "100 kilometres team"]):
            resolved = ("Cycling", "Cycling Road")
        elif any(token in event_key for token in ["bmx"]):
            resolved = ("Cycling", "BMX Racing")
        elif event_key:
            resolved = ("Cycling", "Cycling Track")
    elif label_key == "mixed sports":
        event_sport, event_discipline, event_criterion, _, event_state = resolve_sport_label(event)
        if event_state == "RESOLVED":
            resolved = (event_sport, event_discipline)
    if resolved is None and event_key:
        event_sport, event_discipline, _, _, event_state = resolve_sport_label(event)
        if event_state == "RESOLVED":
            resolved = (event_sport, event_discipline)
    if resolved:
        return resolved[0], resolved[1], "disciplina determinada por patrón inequívoco del evento y taxonomía olímpica", IOC_PROGRAMME_REFERENCE, "RESOLVED"
    return sport, discipline, criterion + "; el evento tampoco determina una disciplina única", evidence, state


def empty_profile() -> dict[str, set[str]]:
    return {"years": set(), "seasons": set(), "sports": set(), "disciplines": set(), "events": set(), "nocs": set()}


def merge_profile(target: dict[str, set[str]], source: dict[str, set[str]]) -> None:
    for key in target:
        target[key].update(source.get(key, set()))


def build_participation_profiles(specs: list[tuple[str, pd.DataFrame, str]]) -> dict[tuple[str, str], dict[str, set[str]]]:
    profiles: defaultdict[tuple[str, str], dict[str, set[str]]] = defaultdict(empty_profile)
    for source, frame, id_column in specs:
        for row in frame.to_dict(orient="records"):
            original_id = text(row.get(id_column))
            if not original_id:
                continue
            profile = profiles[(source, original_id)]
            year, season = text(row.get("year")), norm_aux(row.get("season"))
            label = first_nonempty(row.get("discipline"), row.get("sport"))
            sport, discipline, _, _, _ = resolve_sport_record(label, row.get("event"))
            event, noc = norm_aux(row.get("event")), norm_code(row.get("noc_codigo"))
            if year:
                profile["years"].add(year)
            if season:
                profile["seasons"].add(season)
            if sport:
                profile["sports"].add(norm_aux(sport))
            if discipline:
                profile["disciplines"].add(norm_aux(discipline))
            if event:
                profile["events"].add(event)
            if noc:
                profile["nocs"].add(noc)
    return dict(profiles)


def external_identities(frame: pd.DataFrame, source: str, file_name: str, id_column: str, profiles: dict[tuple[str, str], dict[str, set[str]]]) -> list[dict[str, Any]]:
    rows = []
    first = frame.drop_duplicates(subset=[id_column], keep="first")
    for row in first.to_dict(orient="records"):
        original_id = text(row.get(id_column))
        if not original_id:
            continue
        rows.append({
            "fuente": source, "archivo": f"data/intermediate/cleaned/{file_name}", "id_original": original_id,
            "nombre": first_nonempty(row.get("name")), "sexo": row.get("sex", ""),
            "noc_codigo": norm_code(row.get("noc_codigo")), "altura_cm": row.get("height", ""),
            "peso_kg": row.get("weight", ""), "nacionalidad": "", "fecha_nacimiento": "",
            "ciudad_nacimiento": "", "region_nacimiento": "", "pais_nacimiento_valor": "",
            "fecha_fallecimiento": "", "ciudad_fallecimiento": "", "region_fallecimiento": "",
            "pais_fallecimiento_valor": "", "nombre_completo": "", "nombre_usado": "",
            "nombre_original": "", "otros_nombres": "", "apodos": "", "orden_nombre": "",
            "roles": "", "afiliaciones": "", "titulos": "", "latitud": "", "longitud": "",
            "profile": profiles.get((source, original_id), empty_profile()),
        })
    return sorted(rows, key=lambda x: sort_id(x["id_original"]))


def canonical_noc(code: str) -> str:
    code = norm_code(code)
    return NOC_COUNTRY_ALIASES.get(code, code)


def profile_nocs_compatible(left: set[str], right: set[str]) -> bool:
    return bool({canonical_noc(code) for code in left} & {canonical_noc(code) for code in right})


def contextual_evidence(left: dict[str, set[str]], right: dict[str, set[str]]) -> tuple[bool, dict[str, list[str]]]:
    years = sorted(left["years"] & right["years"])
    sports = sorted(left["sports"] & right["sports"])
    disciplines = sorted(left["disciplines"] & right["disciplines"])
    events = sorted(left["events"] & right["events"])
    evidence = {"years": years, "sports": sports, "disciplines": disciplines, "events": events}
    return bool(years and events and (sports or disciplines)), evidence


def match_athletes(
    source1: dict[str, dict[str, Any]],
    source1_rows: list[dict[str, Any]],
    external: list[dict[str, Any]],
    profiles: dict[tuple[str, str], dict[str, set[str]]],
) -> tuple[dict[tuple[str, str], int], dict[int, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    global_records: dict[int, dict[str, Any]] = {}
    alias_index: defaultdict[str, set[int]] = defaultdict(set)
    next_id = 1
    contributions: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for athlete_id in sorted(source1, key=sort_id):
        fields = source1[athlete_id].copy()
        profile = profiles.get(("fuente1", athlete_id), empty_profile())
        global_records[next_id] = {"fields": fields, "profile": profile, "sources": {"fuente1"}, "source_ids": {"fuente1": athlete_id}, "safe": True}
        aliases = {norm_aux(fields.get("nombre")), norm_aux(fields.get("nombre_completo")), norm_aux(fields.get("nombre_usado")), norm_aux(fields.get("nombre_original"))}
        for alias in aliases - {""}:
            alias_index[alias].add(next_id)
        contributions[next_id].append({"fuente": "fuente1", "id_original": athlete_id, **fields})
        source1_rows[next_id - 1]["id_atleta_global"] = next_id
        next_id += 1

    identity_map: dict[tuple[str, str], int] = {}
    matching_rows = source1_rows[:]
    for item in external:
        alias = norm_aux(item["nombre"])
        candidates = set(alias_index.get(alias, set())) if alias else set()
        candidates = {gid for gid in candidates if global_records[gid]["safe"] and item["fuente"] not in global_records[gid]["sources"]}
        sex = norm_sex(item.get("sexo"))
        if sex:
            candidates = {gid for gid in candidates if not norm_sex(global_records[gid]["fields"].get("sexo")) or norm_sex(global_records[gid]["fields"].get("sexo")) == sex}
        item_profile = item["profile"]
        if item_profile["nocs"]:
            candidates = {gid for gid in candidates if not global_records[gid]["profile"]["nocs"] or profile_nocs_compatible(global_records[gid]["profile"]["nocs"], item_profile["nocs"])}

        candidate_list = sorted(candidates)
        strong = []
        for gid in candidate_list:
            candidate_sex = norm_sex(global_records[gid]["fields"].get("sexo"))
            candidate_nocs = global_records[gid]["profile"]["nocs"]
            if sex and candidate_sex and sex == candidate_sex and item_profile["nocs"] and candidate_nocs and profile_nocs_compatible(candidate_nocs, item_profile["nocs"]):
                strong.append(gid)
        contextual = []
        contextual_details = {}
        if not (len(candidate_list) == 1 and len(strong) == 1):
            for gid in candidate_list:
                compatible, evidence = contextual_evidence(global_records[gid]["profile"], item_profile)
                if compatible:
                    contextual.append(gid)
                    contextual_details[gid] = evidence

        state, confidence, match_type, criterion = "", "", "", ""
        if len(candidate_list) == 1 and len(strong) == 1:
            gid, state, confidence, match_type = strong[0], "MATCHED", "A", "DETERMINISTIC_STRONG"
            criterion = "Nombre auxiliar exacto + sexo comparable igual + NOC comparable compatible; candidato único."
        elif len(contextual) == 1:
            gid, state, confidence, match_type = contextual[0], "MATCHED", "B", "DETERMINISTIC_CONTEXTUAL"
            criterion = "Nombre auxiliar exacto + compatibilidad obligatoria de sexo/NOC + año, deporte/disciplina y evento compartidos: " + json_compact(contextual_details[gid])
        else:
            gid = next_id
            next_id += 1
            if len(candidate_list) > 1:
                state, match_type = "AMBIGUOUS", "DETERMINISTIC_AMBIGUOUS"
                criterion = "Nombre auxiliar exacto con múltiples candidatos; la evidencia contextual no produjo un candidato único."
            else:
                state, match_type = "UNMATCHED", "NEW_SOURCE_ENTITY"
                criterion = "Sin candidato fuerte ni contextual único después de aplicar compatibilidad obligatoria de sexo y NOC."

        if state == "MATCHED":
            global_records[gid]["sources"].add(item["fuente"])
            global_records[gid]["source_ids"][item["fuente"]] = item["id_original"]
            merge_profile(global_records[gid]["profile"], item_profile)
            for key, value in item.items():
                if key in {"fuente", "archivo", "id_original", "nombre", "noc_codigo", "profile"}:
                    continue
                if not text(global_records[gid]["fields"].get(key)) and text(value):
                    global_records[gid]["fields"][key] = value
            contributions[gid].append({k: v for k, v in item.items() if k != "profile"})
        else:
            fields = {
                "nombre": item.get("nombre", ""), "nombre_completo": item.get("nombre_completo", ""),
                "nombre_usado": item.get("nombre_usado", ""), "nombre_original": item.get("nombre_original", ""),
                "otros_nombres": item.get("otros_nombres", ""), "apodos": item.get("apodos", ""), "orden_nombre": item.get("orden_nombre", ""),
                "sexo": item.get("sexo", ""), "fecha_nacimiento": item.get("fecha_nacimiento", ""), "ciudad_nacimiento": item.get("ciudad_nacimiento", ""),
                "region_nacimiento": item.get("region_nacimiento", ""), "pais_nacimiento_valor": item.get("pais_nacimiento_valor", ""),
                "nacionalidad": item.get("nacionalidad", ""), "fecha_fallecimiento": item.get("fecha_fallecimiento", ""),
                "ciudad_fallecimiento": item.get("ciudad_fallecimiento", ""), "region_fallecimiento": item.get("region_fallecimiento", ""),
                "pais_fallecimiento_valor": item.get("pais_fallecimiento_valor", ""), "altura_cm": item.get("altura_cm", ""),
                "peso_kg": item.get("peso_kg", ""), "roles": item.get("roles", ""), "afiliaciones": item.get("afiliaciones", ""),
                "titulos": item.get("titulos", ""), "latitud": item.get("latitud", ""), "longitud": item.get("longitud", ""),
                "noc_nombre": "", "noc_codigo": item.get("noc_codigo", ""),
            }
            global_records[gid] = {"fields": fields, "profile": item_profile, "sources": {item["fuente"]}, "source_ids": {item["fuente"]: item["id_original"]}, "safe": state != "AMBIGUOUS"}
            if alias and state != "AMBIGUOUS":
                alias_index[alias].add(gid)
            contributions[gid].append({k: v for k, v in item.items() if k != "profile"})
        identity_map[(item["fuente"], item["id_original"])] = gid
        matching_rows.append({"fuente": item["fuente"], "archivo": item["archivo"], "id_original": item["id_original"],
                              "nombre_original": item["nombre"], "id_atleta_global": gid, "tipo_match": match_type,
                              "nivel_confianza": confidence, "criterio_match": criterion, "score_fuzzy": "",
                              "estado": state, "candidatos": json_compact(candidate_list)})
    for row in matching_rows:
        if row["fuente"] == "fuente1":
            identity_map[("fuente1", row["id_original"])] = int(row["id_atleta_global"])
    return identity_map, global_records, matching_rows, contributions


def canonical_geographic_name(value: Any) -> str:
    key = norm_aux(value)
    return GEOGRAPHIC_NAME_ALIASES.get(key, key)


def build_entities(population: pd.DataFrame, noc_regions: dict[str, str]) -> tuple[pd.DataFrame, dict[str, int], dict[str, int]]:
    records = []
    for row in population[["country_name", "country_code"]].drop_duplicates().to_dict(orient="records"):
        name, code = text(row["country_name"]), norm_code(row["country_code"])
        if name:
            records.append({"nombre": name, "codigo_pais": code, "origen": "population"})
    code_index = {norm_code(r["codigo_pais"]): r for r in records if norm_code(r["codigo_pais"])}
    name_index = {canonical_geographic_name(r["nombre"]): r for r in records if text(r["nombre"])}
    for noc_code, region in sorted(noc_regions.items()):
        if not region:
            continue
        target_code = NOC_COUNTRY_ALIASES.get(noc_code, noc_code)
        name_key = canonical_geographic_name(region)
        if target_code in code_index or name_key in name_index:
            continue
        record = {"nombre": region, "codigo_pais": "", "origen": "noc_regions"}
        records.append(record)
        name_index[name_key] = record
    records = sorted(records, key=lambda r: (norm_code(r["codigo_pais"]), canonical_geographic_name(r["nombre"]), norm_aux(r["nombre"])))
    rows, by_code, by_name = [], {}, {}
    for idx, record in enumerate(records, start=1):
        rows.append({"id_entidad": idx, "nombre": record["nombre"], "codigo_pais": record["codigo_pais"]})
        if record["codigo_pais"]:
            by_code[record["codigo_pais"]] = idx
        by_name[norm_aux(record["nombre"])] = idx
        by_name[canonical_geographic_name(record["nombre"])] = idx
    return pd.DataFrame(rows), by_code, by_name


def geographic_entity_duplicates(entities: pd.DataFrame) -> pd.DataFrame:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entities.to_dict(orient="records"):
        groups[canonical_geographic_name(row["nombre"])].append(row)
    rows = []
    for key, items in sorted(groups.items()):
        if len(items) > 1:
            rows.append({"nombre_normalizado": key, "ids": json_compact([item["id_entidad"] for item in items]),
                         "nombres": json_compact([item["nombre"] for item in items]),
                         "codigos": json_compact([item["codigo_pais"] for item in items]),
                         "estado": "POSSIBLE_DUPLICATE"})
    return pd.DataFrame(rows, columns=["nombre_normalizado", "ids", "nombres", "codigos", "estado"])


def map_nocs(
    noc_regions_frame: pd.DataFrame,
    all_codes: set[str],
    entities: pd.DataFrame,
    entity_by_code: dict[str, int],
    entity_by_name: dict[str, int],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int], list[dict[str, Any]]]:
    region_by_code = {norm_code(r["noc_codigo"]): text(r["region"]) for r in noc_regions_frame.to_dict(orient="records") if norm_code(r["noc_codigo"])}
    noc_rows, matches, mapping = [], [], {}
    conflicts = []
    for code in sorted(all_codes):
        name = region_by_code.get(code, "")
        target_code = NOC_COUNTRY_ALIASES.get(code, code)
        criterion, state, entity_id = "", "UNRESOLVED", None
        if target_code in entity_by_code:
            entity_id, criterion, state = entity_by_code[target_code], "código de país explícito o alias histórico documentado", "RESOLVED"
        elif canonical_geographic_name(name) in entity_by_name:
            entity_id, criterion, state = entity_by_name[canonical_geographic_name(name)], "nombre NOC o alias explícito coincide con entidad geográfica existente", "RESOLVED"
        elif norm_aux(name) in {"great britain", "united states"}:
            alias_name = {"great britain": "united kingdom", "united states": "united states"}[norm_aux(name)]
            if alias_name in entity_by_name:
                entity_id, criterion, state = entity_by_name[alias_name], "alias descriptivo explícito", "RESOLVED"
        if code == "ROT":
            entity_id, criterion, state = None, "delegación especial sin país; no se inventa entidad", "UNRESOLVED"
        mapping[code] = entity_id
        entity_name = ""
        country_code = ""
        if entity_id is not None:
            hit = entities[entities["id_entidad"] == entity_id].iloc[0]
            entity_name, country_code = text(hit["nombre"]), text(hit["codigo_pais"])
        matches.append({"noc_codigo": code, "noc_nombre": name, "entidad": entity_name, "country_code": country_code,
                        "criterio": criterion, "estado": state})
        noc_rows.append({"id_noc": None, "codigo_noc": code, "nombre_noc": name, "id_entidad": entity_id,
                         "notas": text(next((r["notes"] for r in noc_regions_frame.to_dict(orient="records") if norm_code(r["noc_codigo"]) == code), ""))})
        if state != "RESOLVED":
            conflicts.append({"tipo_conflicto": "NOC_ENTITY_UNRESOLVED", "clave": code, "atributo": "id_entidad",
                              "valores": name, "fuentes": "fuente1/clean/noc_regions.csv", "regla": criterion or "sin correspondencia segura", "estado": state})
    for idx, row in enumerate(sorted(noc_rows, key=lambda r: r["codigo_noc"]), start=1):
        row["id_noc"] = idx
    id_by_code = {r["codigo_noc"]: r["id_noc"] for r in noc_rows}
    return pd.DataFrame(noc_rows), pd.DataFrame(matches), id_by_code, conflicts


def map_country_value(value: Any, entity_by_code: dict[str, int], entity_by_name: dict[str, int], noc_mapping: dict[str, int | None]) -> Any:
    value = text(value)
    if not value:
        return pd.NA
    code = norm_code(value)
    if code in entity_by_code:
        return entity_by_code[code]
    if code in NOC_COUNTRY_ALIASES and NOC_COUNTRY_ALIASES[code] in entity_by_code:
        return entity_by_code[NOC_COUNTRY_ALIASES[code]]
    if code in noc_mapping and noc_mapping[code] is not None:
        return noc_mapping[code]
    return entity_by_name.get(canonical_geographic_name(value), pd.NA)


def city_code(city: Any) -> str:
    return CITY_COUNTRY_CODES.get(norm_aux(city), "")


def sport_mapping(records: list[dict[str, Any]]) -> pd.DataFrame:
    contexts: defaultdict[tuple[str, str, str, str], set[tuple[str, str]]] = defaultdict(set)
    initial = []
    for record in records:
        resolution = resolve_sport_record(record["discipline_source"], record["event_source"])
        initial.append(resolution)
        if resolution[4] == "RESOLVED":
            context_key = (record["fuente"], record["id_original"], record["year"], record["season"])
            contexts[context_key].add((resolution[0], resolution[1]))
    counts: Counter[tuple[str, str, str, str, str, str, str]] = Counter()
    for record, resolution in zip(records, initial):
        label, event = record["discipline_source"], record["event_source"]
        sport, discipline, criterion, evidence, state = resolution
        if state != "RESOLVED":
            context_key = (record["fuente"], record["id_original"], record["year"], record["season"])
            candidates = contexts.get(context_key, set())
            if len(candidates) == 1:
                sport, discipline = next(iter(candidates))
                criterion = "disciplina única de una fila compañera del mismo atleta, fuente y edición"
                evidence = IOC_EVOLUTION_REFERENCE
                state = "RESOLVED"
        record["deporte"], record["disciplina"] = sport, discipline
        counts[(record["fuente"], label, sport, discipline, criterion, evidence, state)] += 1
    rows = [{"fuente": source, "valor_fuente": label, "deporte_final": sport, "disciplina_final": discipline,
             "criterio": criterion, "evidencia_referencia": evidence, "estado": state, "filas_afectadas": count}
            for (source, label, sport, discipline, criterion, evidence, state), count in sorted(counts.items(), key=lambda item: tuple(norm_aux(value) for value in item[0][:4]))]
    return pd.DataFrame(rows)


def source4_overlap(source2: pd.DataFrame, source4: pd.DataFrame) -> pd.DataFrame:
    common = [("name", "name"), ("sex", "sex"), ("age", "age"), ("height", "height"), ("weight", "weight"),
              ("equipo", "equipo"), ("noc_codigo", "noc_codigo"), ("games_original", "games_original"),
              ("year", "year"), ("season", "season"), ("city", "city"), ("sport", "sport"), ("event", "event"), ("medalla", "medalla")]
    index: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)
    for row in source2.to_dict(orient="records"):
        key = tuple(norm_scalar(row.get(left, "")) for left, _ in common)
        index[key].append(text(row.get("ID")))
    rows = []
    for row in source4.to_dict(orient="records"):
        key = tuple(norm_scalar(row.get(right, "")) for _, right in common)
        candidates = index.get(key, [])
        state = "MATCHED_EXACT" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "NOT_FOUND"
        rows.append({"filas_fuente4_total": len(source4), "id_fuente4": text(row.get("id")),
                     "matches_fuente2": json_compact(candidates), "cantidad_matches": len(candidates),
                     "estado": state, "criterio": "igualdad normalizada en 14 columnas comunes"})
    return pd.DataFrame(rows)


def align_source1_raw_clean(raw: pd.DataFrame, clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    stable_columns = ["athlete_id", "discipline", "event", "nombre_competencia", "noc_codigo", "equipo", "medalla"]
    targets = ["year", "season", "posicion", "empatado"]
    clean_index: defaultdict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in clean.to_dict(orient="records"):
        key = tuple(norm_scalar(row.get(column)) for column in stable_columns)
        clean_index[key].append(row)
    output, safe, not_found, ambiguous = [], 0, 0, 0
    enriched = Counter()
    for row in raw.to_dict(orient="records"):
        key = tuple(norm_scalar(row.get(column)) for column in stable_columns)
        candidates = list(clean_index.get(key, []))
        for column in ["year", "season"]:
            value = norm_scalar(row.get(column))
            if value and candidates:
                filtered = [candidate for candidate in candidates if norm_scalar(candidate.get(column)) == value]
                candidates = filtered
        if not candidates:
            not_found += 1
            output.append(row)
            continue
        target_values = {tuple(norm_scalar(candidate.get(column)) for column in targets) for candidate in candidates}
        if len(target_values) != 1:
            ambiguous += 1
            output.append(row)
            continue
        safe += 1
        candidate = candidates[0]
        updated = row.copy()
        for column in targets:
            if not text(updated.get(column)) and text(candidate.get(column)):
                updated[column] = candidate[column]
                enriched[column] += 1
        output.append(updated)
    aligned = pd.DataFrame(output, columns=raw.columns)
    missing_before = int(((raw["year"].astype(str).str.strip() == "") | (raw["season"].astype(str).str.strip() == "")).sum())
    missing_after = int(((aligned["year"].astype(str).str.strip() == "") | (aligned["season"].astype(str).str.strip() == "")).sum())
    report = pd.DataFrame([{
        "filas_raw": len(raw), "filas_clean": len(clean), "matches_seguros": safe,
        "no_encontrados": not_found, "ambiguos": ambiguous,
        "year_enriquecido": enriched["year"], "season_enriquecida": enriched["season"],
        "posicion_enriquecida": enriched["posicion"], "empatado_enriquecido": enriched["empatado"],
        "atributos_enriquecidos": sum(enriched.values()),
        "edicion_incompleta_antes": missing_before, "edicion_incompleta_despues": missing_after,
        "ediciones_incompletas_resueltas": missing_before - missing_after,
        "criterio": "clave de contenido estable; candidatos múltiples solo son seguros si los cuatro atributos objetivo coinciden",
    }])
    return aligned, report


def enrich_source1_missing_disciplines(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = frame.copy()
    evidence: defaultdict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for row in frame.to_dict(orient="records"):
        discipline = text(row.get("discipline"))
        key = (text(row.get("year")), norm_aux(row.get("season")), norm_aux(row.get("event")))
        if discipline and all(key):
            evidence[key][discipline] += 1
    rows = []
    for index, row in output.iterrows():
        if text(row.get("discipline")):
            continue
        key = (text(row.get("year")), norm_aux(row.get("season")), norm_aux(row.get("event")))
        candidates = evidence.get(key, Counter())
        state = "RESOLVED" if len(candidates) == 1 else "AMBIGUOUS" if candidates else "UNRESOLVED"
        chosen = next(iter(candidates)) if len(candidates) == 1 else ""
        if chosen:
            output.at[index, "discipline"] = chosen
        rows.append({"fila_origen": int(index) + 2, "year": row.get("year", ""), "season": row.get("season", ""),
                     "event": row.get("event", ""), "disciplina_asignada": chosen,
                     "candidatos": json_compact(dict(candidates)), "estado": state,
                     "criterio": "misma edición y evento; todas las demás filas informadas coinciden en una única disciplina"})
    return output, pd.DataFrame(rows, columns=["fila_origen", "year", "season", "event", "disciplina_asignada", "candidatos", "estado", "criterio"])


def edition_and_venue(
    records: list[dict[str, Any]], entities: pd.DataFrame, entity_by_code: dict[str, int]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], int], dict[str, Any], list[dict[str, Any]]]:
    cities: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for record in records:
        year, season, city = text(record.get("year")), text(record.get("season")), text(record.get("city"))
        if year and season and city:
            cities[(year, season)][city] += 1
    edition_keys = sorted({(text(r.get("year")), text(r.get("season"))) for r in records if text(r.get("year")) and text(r.get("season"))}, key=lambda x: (int(x[0]), x[1]))
    venue_rows, venue_index, edition_rows, edition_index, conflicts = [], {}, [], {}, []
    for year, season in edition_keys:
        options = cities.get((year, season), Counter())
        chosen = options.most_common(1)[0][0] if options else ""
        if len(options) > 1:
            conflicts.append({"tipo_conflicto": "EDITION_CITY", "clave": f"{year}-{season}", "atributo": "ciudad",
                              "valores": json_compact(dict(options)), "fuentes": "fuentes 2/3/4", "regla": "se conserva la ciudad más frecuente y se documentan discrepancias", "estado": "REVIEW"})
        code = city_code(chosen)
        country_id = entity_by_code.get(code, pd.NA) if code else pd.NA
        venue_key = (norm_aux(chosen), text(country_id))
        if chosen and venue_key not in venue_index:
            venue_index[venue_key] = len(venue_rows) + 1
            venue_rows.append({"id_sede": venue_index[venue_key], "nombre": chosen, "id_pais": country_id})
        edition_id = len(edition_rows) + 1
        edition_index[(year, season)] = edition_id
        edition_rows.append({"id_edicion": edition_id, "anio": integer(year), "temporada": season,
                             "id_sede": venue_index.get(venue_key, pd.NA)})
    return pd.DataFrame(venue_rows), pd.DataFrame(edition_rows), edition_index, venue_index, conflicts


def build_participation_records(
    s1: pd.DataFrame, s2: pd.DataFrame, s3: pd.DataFrame, s4: pd.DataFrame,
    identity_map: dict[tuple[str, str], int], overlap: pd.DataFrame,
) -> list[dict[str, Any]]:
    records = []
    for source, frame, id_col, file_name in [
        ("fuente1", s1, "athlete_id", "fuente1_raw_results.csv"),
        ("fuente2", s2, "ID", "fuente2_athlete_events.csv"),
        ("fuente3", s3, "player_id", "fuente3_olympics_dataset.csv"),
        ("fuente4", s4, "id", "fuente4_datalab_export.csv"),
    ]:
        for row_number, row in enumerate(frame.to_dict(orient="records")):
            original_id = text(row.get(id_col))
            global_id = identity_map.get((source, original_id), pd.NA)
            overlap_state = ""
            if source == "fuente4":
                match_row = overlap.iloc[row_number]
                overlap_state = text(match_row["estado"])
            records.append({
                "fuente": source, "archivo": f"data/intermediate/cleaned/{file_name}", "fila_origen": row_number + 2,
                "id_original": original_id, "id_atleta": global_id, "nombre_original": first_nonempty(row.get("nombre_competencia"), row.get("name")),
                "year": first_nonempty(row.get("year")), "season": first_nonempty(row.get("season")), "city": first_nonempty(row.get("city")),
                "discipline_source": first_nonempty(row.get("discipline"), row.get("sport")), "sport_source": first_nonempty(row.get("sport")),
                "event_source": first_nonempty(row.get("event")), "noc_codigo": norm_code(row.get("noc_codigo")),
                "nationality_value": first_nonempty(row.get("nationality")), "equipo": first_nonempty(row.get("equipo")),
                "nombre_competencia": first_nonempty(row.get("nombre_competencia")), "edad": row.get("age", ""),
                "altura": row.get("height", ""), "peso": row.get("weight", ""), "posicion": row.get("posicion", ""),
                "empatado": row.get("empatado", ""), "estado_resultado": row.get("estado_resultado", ""),
                "medalla": row.get("medalla", ""), "source4_overlap": overlap_state,
            })
    return records


def final_sport_tables(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sports, disciplines, events = {}, {}, {}
    for record in records:
        parent, discipline = record["deporte"], record["disciplina"]
        sport_key = norm_aux(parent)
        disc_key = (sport_key, norm_aux(discipline))
        sports.setdefault(sport_key, parent)
        disciplines.setdefault(disc_key, discipline)
    sport_rows = [{"id_deporte": i, "nombre": name} for i, name in enumerate(sorted(sports.values(), key=norm_aux), start=1)]
    sport_id = {norm_aux(r["nombre"]): r["id_deporte"] for r in sport_rows}
    disc_rows = []
    for i, (key, name) in enumerate(sorted(disciplines.items()), start=1):
        disc_rows.append({"id_disciplina": i, "id_deporte": sport_id[key[0]], "nombre": name})
    disc_id = {(r["id_deporte"], norm_aux(r["nombre"])): r["id_disciplina"] for r in disc_rows}
    event_key_rows = {}
    for record in records:
        d_id = disc_id[(sport_id[norm_aux(record["deporte"])], norm_aux(record["disciplina"]))]
        record["id_disciplina"] = d_id
        event_key = (d_id, norm_aux(record["event_source"]))
        if event_key not in event_key_rows:
            event_key_rows[event_key] = len(event_key_rows) + 1
        record["id_evento"] = event_key_rows[event_key]
    event_rows = []
    event_names = {}
    for record in records:
        event_names.setdefault(record["id_evento"], record["event_source"])
    for event_id, name in sorted(event_names.items()):
        d_id = next(k[0] for k, v in event_key_rows.items() if v == event_id)
        event_rows.append({"id_evento": event_id, "id_disciplina": d_id, "nombre": name})
    return pd.DataFrame(sport_rows), pd.DataFrame(disc_rows), pd.DataFrame(event_rows)


def deduplicate_records(records: list[dict[str, Any]], noc_ids: dict[str, int], edition_ids: dict[tuple[str, str], int]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    exact_groups: defaultdict[str, list[int]] = defaultdict(list)
    probable_groups: defaultdict[str, list[int]] = defaultdict(list)
    for idx, record in enumerate(records):
        record["id_noc"] = noc_ids.get(record["noc_codigo"], pd.NA)
        record["id_edicion"] = edition_ids.get((record["year"], record["season"]), pd.NA)
        record["id_noc"] = record["id_noc"] if record["id_noc"] is not None else pd.NA
        exact = [record.get(k, "") for k in ["id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "nombre_competencia", "edad", "altura", "peso", "posicion", "empatado", "estado_resultado", "medalla"]]
        probable = [record.get(k, "") for k in ["id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "nombre_competencia"]]
        exact_groups[json_compact([text(v) for v in exact])].append(idx)
        probable_groups[json_compact([text(v) for v in probable])].append(idx)
    decisions = []
    decision_keys: set[tuple[str, int]] = set()
    decision_index: dict[tuple[str, int], int] = {}
    retained = [True] * len(records)
    priority = {"fuente1": 0, "fuente2": 1, "fuente3": 2, "fuente4": 3}
    for key, indices in exact_groups.items():
        sources = {records[i]["fuente"] for i in indices}
        if len(indices) == 1:
            continue
        ordered = sorted(indices, key=lambda i: (priority[records[i]["fuente"]], records[i]["fila_origen"]))
        for pos, idx in enumerate(ordered):
            is_retained = pos == 0
            if not is_retained:
                retained[idx] = False
            if records[idx]["fuente"] == "fuente4" and records[idx]["source4_overlap"] == "MATCHED_EXACT":
                reason, kind = "Fuente 4 contenida exactamente en Fuente 2; se conserva solo la fila priorizada.", "EXACT_CROSS_SOURCE_DUPLICATE"
            elif len(sources) > 1:
                reason, kind = "Clave lógica completa idéntica entre fuentes; se conserva la fuente de mayor prioridad.", "EXACT_CROSS_SOURCE_DUPLICATE"
            else:
                reason, kind = "Duplicado exacto dentro de la misma fuente; se conserva la primera fila estable.", "EXACT_SAME_SOURCE_DUPLICATE"
            decisions.append({"archivo": records[idx]["archivo"], "fuente": records[idx]["fuente"], "fila_origen": records[idx]["fila_origen"],
                              "id_original": records[idx]["id_original"], "clave_logica": key, "tipo": kind,
                              "retained": "YES" if is_retained else "NO", "motivo": reason})
            decision_keys.add((records[idx]["fuente"], records[idx]["fila_origen"]))
            decision_index[(records[idx]["fuente"], records[idx]["fila_origen"])] = len(decisions) - 1
    exact_index = {i for values in exact_groups.values() if len(values) > 1 for i in values}
    for key, indices in probable_groups.items():
        if len(indices) <= 1:
            continue
        if all(i in exact_index for i in indices):
            continue
        for idx in indices:
            decisions.append({"archivo": records[idx]["archivo"], "fuente": records[idx]["fuente"], "fila_origen": records[idx]["fila_origen"],
                              "id_original": records[idx]["id_original"], "clave_logica": key, "tipo": "CONFLICT" if len({records[i].get("medalla", "") for i in indices}) > 1 else "PROBABLE_DUPLICATE",
                              "retained": "YES", "motivo": "Coincide la clave lógica parcial, pero existen atributos diferentes; no se elimina automáticamente."})
            decision_keys.add((records[idx]["fuente"], records[idx]["fila_origen"]))
            decision_index[(records[idx]["fuente"], records[idx]["fila_origen"])] = len(decisions) - 1
    for idx, record in enumerate(records):
        if record["fuente"] != "fuente4" or record["source4_overlap"] != "MATCHED_EXACT" or not retained[idx]:
            continue
        retained[idx] = False
        key = (record["fuente"], record["fila_origen"])
        decision = {"archivo": record["archivo"], "fuente": record["fuente"], "fila_origen": record["fila_origen"],
                    "id_original": record["id_original"], "clave_logica": "MATCHED_EXACT_SOURCE4_SOURCE2",
                    "tipo": "EXACT_CROSS_SOURCE_DUPLICATE", "retained": "NO",
                    "motivo": "Coincidencia exacta normalizada en 14 columnas contra Fuente 2; se excluye de la consolidación y se conserva en el reporte."}
        if key in decision_index:
            decisions[decision_index[key]] = decision
        else:
            decisions.append(decision)
            decision_keys.add(key)
            decision_index[key] = len(decisions) - 1
    for idx, record in enumerate(records):
        if (record["fuente"], record["fila_origen"]) not in decision_keys:
            decisions.append({"archivo": record["archivo"], "fuente": record["fuente"], "fila_origen": record["fila_origen"],
                              "id_original": record["id_original"], "clave_logica": "", "tipo": "UNIQUE", "retained": "YES", "motivo": "Sin duplicado lógico detectado."})
            decision_keys.add((record["fuente"], record["fila_origen"]))
            decision_index[(record["fuente"], record["fila_origen"])] = len(decisions) - 1
    priority = {"EXACT_CROSS_SOURCE_DUPLICATE": 0, "EXACT_SAME_SOURCE_DUPLICATE": 1,
                "CONFLICT": 2, "PROBABLE_DUPLICATE": 3, "UNIQUE": 4}
    canonical: dict[tuple[str, int], dict[str, Any]] = {}
    for decision in decisions:
        key = (decision["fuente"], decision["fila_origen"])
        rank = (priority.get(decision["tipo"], 99), 0 if decision["retained"] == "NO" else 1)
        current = canonical.get(key)
        current_rank = (priority.get(current["tipo"], 99), 0 if current and current["retained"] == "NO" else 1) if current else (99, 99)
        if current is None or rank < current_rank:
            canonical[key] = decision
    decisions = sorted(canonical.values(), key=lambda d: (d["fuente"], d["fila_origen"]))
    return pd.DataFrame(decisions), [records[i] for i in range(len(records)) if retained[i]]


def attribute_conflicts(contributions: dict[int, list[dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    attrs = ["nombre", "sexo", "fecha_nacimiento", "altura_cm", "peso_kg", "nacionalidad", "noc_codigo"]
    for gid, items in contributions.items():
        for attr in attrs:
            values = [(text(item.get(attr)), item.get("fuente", ""), item.get("id_original", "")) for item in items if text(item.get(attr))]
            distinct = {norm_scalar(value) for value, _, _ in values if value}
            if len(distinct) > 1:
                rows.append({"id_atleta_global": gid, "atributo": attr, "valores": json_compact(sorted({v for v, _, _ in values})),
                             "fuentes": json_compact([{"fuente": s, "id_original": i, "valor": v} for v, s, i in values]),
                             "regla": "Se prioriza fuente 1; después fuente 2, fuente 3 y fuente 4. Se conserva el conflicto.", "estado": "REVIEW"})
    return pd.DataFrame(rows, columns=["id_atleta_global", "atributo", "valores", "fuentes", "regla", "estado"])


def build_athlete_table(global_records: dict[int, dict[str, Any]], entity_by_code: dict[str, int], entity_by_name: dict[str, int], noc_mapping: dict[str, int | None]) -> pd.DataFrame:
    rows = []
    for gid in sorted(global_records):
        f = global_records[gid]["fields"]
        rows.append({"id_atleta": gid, "nombre": f.get("nombre", ""), "nombre_completo": f.get("nombre_completo", ""),
                     "nombre_usado": f.get("nombre_usado", ""), "nombre_original": f.get("nombre_original", ""),
                     "otros_nombres": f.get("otros_nombres", ""), "apodos": f.get("apodos", ""), "orden_nombre": f.get("orden_nombre", ""),
                     "sexo": f.get("sexo", ""), "fecha_nacimiento": f.get("fecha_nacimiento", ""), "ciudad_nacimiento": f.get("ciudad_nacimiento", ""),
                     "region_nacimiento": f.get("region_nacimiento", ""), "id_pais_nacimiento": map_country_value(f.get("pais_nacimiento_valor"), entity_by_code, entity_by_name, noc_mapping),
                     "id_pais_nacionalidad": map_country_value(f.get("nacionalidad"), entity_by_code, entity_by_name, noc_mapping),
                     "fecha_fallecimiento": f.get("fecha_fallecimiento", ""), "ciudad_fallecimiento": f.get("ciudad_fallecimiento", ""),
                     "region_fallecimiento": f.get("region_fallecimiento", ""), "id_pais_fallecimiento": map_country_value(f.get("pais_fallecimiento_valor"), entity_by_code, entity_by_name, noc_mapping),
                     "altura_cm": number(f.get("altura_cm")), "peso_kg": number(f.get("peso_kg")), "roles": f.get("roles", ""),
                     "afiliaciones": f.get("afiliaciones", ""), "titulos": f.get("titulos", ""), "latitud": number(f.get("latitud")), "longitud": number(f.get("longitud"))})
    return pd.DataFrame(rows)


def map_participation_nationalities(records: list[dict[str, Any]], entities: pd.DataFrame,
                                    entity_by_code: dict[str, int], entity_by_name: dict[str, int],
                                    noc_mapping: dict[str, int | None]) -> pd.DataFrame:
    entity_names = {int(row["id_entidad"]): text(row["nombre"]) for row in entities.to_dict(orient="records")}
    summary: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    for record in records:
        original = text(record.get("nationality_value"))
        mapped = map_country_value(original, entity_by_code, entity_by_name, noc_mapping) if original else pd.NA
        record["id_pais_nacionalidad"] = mapped
        resolved = bool(original) and not pd.isna(mapped)
        state = "RESOLVED" if resolved else "UNRESOLVED" if original else "NO_VALUE"
        key = (original, text(mapped), entity_names.get(int(mapped), "") if resolved else "")
        summary[(state, *key)] += 1
    rows = [{"estado": state, "valor_original": value, "id_entidad": entity_id, "entidad": entity_name,
             "frecuencia": count, "criterio": "código ISO/NOC explícitamente mapeado o nombre/alias geográfico exacto" if state == "RESOLVED" else "sin valor" if state == "NO_VALUE" else "sin correspondencia geográfica segura"}
            for (state, value, entity_id, entity_name), count in sorted(summary.items())]
    return pd.DataFrame(rows)


def participant_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for idx, r in enumerate(records, start=1):
        medal = text(r.get("medalla"))
        medal = MEDALS.get(medal.casefold(), "") if medal else ""
        rows.append({"id_participacion": idx, "id_atleta": r.get("id_atleta"), "id_edicion": r.get("id_edicion"),
                     "id_evento": r.get("id_evento"), "id_noc": r.get("id_noc"),
                     "id_pais_nacionalidad": r.get("id_pais_nacionalidad", pd.NA), "equipo": r.get("equipo", ""),
                     "nombre_competencia": r.get("nombre_competencia", ""), "edad": number(r.get("edad")),
                     "altura_cm_registrada": number(r.get("altura")), "peso_kg_registrado": number(r.get("peso")),
                     "posicion": integer(r.get("posicion")), "empatado": text(r.get("empatado"),),
                     "estado_resultado": r.get("estado_resultado", ""), "medalla": medal})
    frame = pd.DataFrame(rows)
    if "empatado" in frame:
        frame["empatado"] = frame["empatado"].replace({"True": True, "False": False, "": pd.NA})
    return frame


def processed_counts(tables: dict[str, pd.DataFrame], origins: dict[str, Counter]) -> pd.DataFrame:
    rows = []
    pk_map = {"entidad_geografica": ["id_entidad"], "poblacion": ["id_entidad", "anio"], "noc": ["id_noc"],
              "atleta": ["id_atleta"], "sede": ["id_sede"], "edicion_olimpica": ["id_edicion"], "deporte": ["id_deporte"],
              "disciplina": ["id_disciplina"], "evento": ["id_evento"], "participacion": ["id_participacion"]}
    key_map = {"entidad_geografica": ["id_entidad"], "poblacion": ["id_entidad", "anio"], "noc": ["id_noc"], "atleta": ["id_atleta"],
               "sede": ["id_sede"], "edicion_olimpica": ["id_edicion", "anio", "temporada"], "deporte": ["id_deporte"],
               "disciplina": ["id_disciplina", "id_deporte"], "evento": ["id_evento", "id_disciplina"], "participacion": ["id_participacion", "id_atleta", "id_edicion", "id_evento"]}
    for entity, frame in tables.items():
        pk = pk_map[entity]
        duplicates = int(frame.duplicated(subset=pk).sum()) if not frame.empty else 0
        nulls = {column: int(frame[column].isna().sum() + (frame[column] == "").sum()) for column in key_map[entity] if column in frame}
        rows.append({"entidad": entity, "filas": len(frame), "pk_duplicadas": duplicates,
                     "columnas_clave_con_null": json_compact(nulls), "origen_registros": json_compact(dict(origins.get(entity, Counter())))})
    return pd.DataFrame(rows)


def validate_final(tables: dict[str, pd.DataFrame], sport_map_report: pd.DataFrame) -> pd.DataFrame:
    checks = []
    def add(name: str, expected: str, actual: Any, ok: bool, detail: str = ""):
        checks.append({"validacion": name, "esperado": expected, "actual": actual, "estado": "PASS" if ok else "FAIL", "detalle": detail})
    def null_count(frame: pd.DataFrame, column: str) -> int:
        return int((frame[column].isna() | frame[column].astype(str).str.strip().eq("")).sum())
    pk_map = {"entidad_geografica": ["id_entidad"], "poblacion": ["id_entidad", "anio"], "noc": ["id_noc"], "atleta": ["id_atleta"],
              "sede": ["id_sede"], "edicion_olimpica": ["id_edicion"], "deporte": ["id_deporte"], "disciplina": ["id_disciplina"],
              "evento": ["id_evento"], "participacion": ["id_participacion"]}
    for name, pk in pk_map.items():
        dup = int(tables[name].duplicated(subset=pk).sum())
        add(f"PK {name}", "0 duplicados", dup, dup == 0)
    editions = tables["edicion_olimpica"]
    add("Edición año+temporada", "única", int(editions.duplicated(["anio", "temporada"]).sum()), not editions.duplicated(["anio", "temporada"]).any())
    disciplines = tables["disciplina"]
    add("Disciplina dentro de deporte", "única", int(disciplines.duplicated(["id_deporte", "nombre"]).sum()), not disciplines.duplicated(["id_deporte", "nombre"]).any())
    events = tables["evento"]
    add("Evento dentro de disciplina", "único", int(events.duplicated(["id_disciplina", "nombre"]).sum()), not events.duplicated(["id_disciplina", "nombre"]).any())
    sports = tables["deporte"]
    add("Deporte nombre", "único", int(sports.duplicated(["nombre"]).sum()), not sports.duplicated(["nombre"]).any())
    venues = tables["sede"]
    add("Sede nombre+país", "única", int(venues.duplicated(["nombre", "id_pais"]).sum()), not venues.duplicated(["nombre", "id_pais"]).any())
    required = {
        "entidad_geografica": ["id_entidad", "nombre"], "poblacion": ["id_entidad", "anio"], "noc": ["id_noc"],
        "atleta": ["id_atleta", "nombre"], "sede": ["id_sede", "nombre", "id_pais"],
        "edicion_olimpica": ["id_edicion", "anio", "temporada"], "deporte": ["id_deporte", "nombre"],
        "disciplina": ["id_disciplina", "id_deporte", "nombre"], "evento": ["id_evento", "id_disciplina", "nombre"],
        "participacion": ["id_participacion", "id_atleta", "id_edicion", "id_evento"],
    }
    for table_name, columns in required.items():
        for column in columns:
            nulls = null_count(tables[table_name], column)
            add(f"NOT NULL {table_name}.{column}", "0 NULL", nulls, nulls == 0)
    fk_checks = [
        ("poblacion", "id_entidad", "entidad_geografica", False), ("noc", "id_entidad", "entidad_geografica", True),
        ("atleta", "id_pais_nacimiento", "entidad_geografica", True), ("atleta", "id_pais_nacionalidad", "entidad_geografica", True),
        ("atleta", "id_pais_fallecimiento", "entidad_geografica", True), ("sede", "id_pais", "entidad_geografica", False),
        ("edicion_olimpica", "id_sede", "sede", True), ("disciplina", "id_deporte", "deporte", False),
        ("evento", "id_disciplina", "disciplina", False), ("participacion", "id_atleta", "atleta", False),
        ("participacion", "id_edicion", "edicion_olimpica", False), ("participacion", "id_evento", "evento", False),
        ("participacion", "id_noc", "noc", True), ("participacion", "id_pais_nacionalidad", "entidad_geografica", True),
    ]
    for table_name, column, target, nullable in fk_checks:
        source_values = {value for value in tables[table_name][column].dropna() if text(value)}
        target_values = set(tables[target][pk_map[target][0]].dropna())
        invalid = source_values - target_values
        add(f"FK {table_name}.{column}", "referencias existentes", len(invalid), len(invalid) == 0,
            json_compact(sorted(map(str, invalid))[:20]) + ("; NULL permitido" if nullable else ""))
    p = tables["participacion"]
    allowed = {"", "Gold", "Silver", "Bronze"}
    invalid_medals = set(p["medalla"].fillna("").astype(str)) - allowed
    add("Medallas", "Gold/Silver/Bronze/NULL", len(invalid_medals), len(invalid_medals) == 0)
    pending_sports = int((sport_map_report["estado"] != "RESOLVED").sum())
    add("Jerarquía deporte-disciplina", "0 pendientes", pending_sports, pending_sports == 0,
        "Los pendientes impiden declarar los CSV aptos para carga SQL.")
    return pd.DataFrame(checks)


def main() -> int:
    before_hashes = raw_hash_validation()
    MATCH_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    CONSOLIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frames = {name: read_csv(name) for name in INPUT_FILES}
    bios, locs, noc_frame, population, clean_results, raw_bios, raw_results = (
        frames["fuente1_clean_bios.csv"], frames["fuente1_clean_bios_locs.csv"], frames["fuente1_clean_noc_regions.csv"],
        frames["fuente1_clean_populations_long.csv"], frames["fuente1_clean_results.csv"], frames["fuente1_raw_bios.csv"], frames["fuente1_raw_results.csv"]
    )
    s2, s3, s4 = frames["fuente2_athlete_events.csv"], frames["fuente3_olympics_dataset.csv"], frames["fuente4_datalab_export.csv"]
    raw_results, alignment_report = align_source1_raw_clean(raw_results, clean_results)
    write_csv(alignment_report, CONSOLIDATION_DIR / "source1_raw_clean_alignment.csv")
    raw_results, discipline_enrichment = enrich_source1_missing_disciplines(raw_results)
    write_csv(discipline_enrichment, CONSOLIDATION_DIR / "source1_missing_discipline_enrichment.csv")
    noc_regions = {norm_code(r["noc_codigo"]): text(r["region"]) for r in noc_frame.to_dict(orient="records") if norm_code(r["noc_codigo"])}
    profiles = build_participation_profiles([
        ("fuente1", raw_results, "athlete_id"), ("fuente2", s2, "ID"),
        ("fuente3", s3, "player_id"), ("fuente4", s4, "id"),
    ])
    source1, source1_match_rows = source1_master(bios, locs, raw_bios)
    external = external_identities(s2, "fuente2", "fuente2_athlete_events.csv", "ID", profiles) + external_identities(s3, "fuente3", "fuente3_olympics_dataset.csv", "player_id", profiles) + external_identities(s4, "fuente4", "fuente4_datalab_export.csv", "id", profiles)
    identity_map, global_records, match_rows, contributions = match_athletes(source1, source1_match_rows, external, profiles)
    matching = pd.DataFrame(match_rows)
    write_csv(matching, MATCH_DIR / "athlete_matches.csv")
    write_csv(matching[matching["estado"] == "AMBIGUOUS"], CONSOLIDATION_DIR / "athlete_ambiguous_matches.csv")
    write_csv(matching[matching["estado"] == "UNMATCHED"], CONSOLIDATION_DIR / "athlete_unmatched.csv")
    summary = matching.groupby(["fuente", "estado", "tipo_match"], dropna=False).size().reset_index(name="cantidad")
    summary["deterministic"] = summary["tipo_match"].astype(str).str.startswith("DETERMINISTIC")
    summary["fuzzy"] = False
    write_csv(summary, CONSOLIDATION_DIR / "athlete_matching_summary.csv")
    conflicts_attr = attribute_conflicts(contributions)
    write_csv(conflicts_attr, CONSOLIDATION_DIR / "attribute_conflicts.csv")
    entities, entity_by_code, entity_by_name = build_entities(population, noc_regions)
    geo_duplicates = geographic_entity_duplicates(entities)
    write_csv(geo_duplicates, CONSOLIDATION_DIR / "geographic_entity_duplicates.csv")
    all_codes = set(noc_regions) | set(s2["noc_codigo"].map(norm_code)) | set(s3["noc_codigo"].map(norm_code)) | set(s4["noc_codigo"].map(norm_code)) | set(raw_results["noc_codigo"].map(norm_code))
    all_codes.discard("")
    noc_table, noc_matches, noc_ids, noc_conflicts = map_nocs(noc_frame, all_codes, entities, entity_by_code, entity_by_name)
    write_csv(noc_matches, MATCH_DIR / "noc_entity_matches.csv")
    write_csv(noc_matches.groupby(["estado", "criterio"], dropna=False).size().reset_index(name="cantidad"), CONSOLIDATION_DIR / "noc_mapping_summary.csv")
    population_out = population.assign(id_entidad=[entity_by_code.get(norm_code(c), entity_by_name.get(norm_aux(n), pd.NA)) for c, n in zip(population["country_code"], population["country_name"])])
    population_out = population_out.rename(columns={"year": "anio"})[["id_entidad", "anio", "population"]].rename(columns={"population": "poblacion"})
    overlap = source4_overlap(s2, s4)
    write_csv(overlap, CONSOLIDATION_DIR / "source4_overlap.csv")
    records = build_participation_records(raw_results, s2, s3, s4, identity_map, overlap)
    sport_map_report = sport_mapping(records)
    write_csv(sport_map_report, MATCH_DIR / "sport_discipline_mapping.csv")
    sport_table, discipline_table, event_table = final_sport_tables(records)
    venue_table, edition_table, edition_ids, venue_index, edition_conflicts = edition_and_venue(records, entities, entity_by_code)
    dedup_report, retained_records = deduplicate_records(records, noc_ids, edition_ids)
    write_csv(dedup_report, CONSOLIDATION_DIR / "participation_deduplication.csv")
    noc_entity_mapping = {r["codigo_noc"]: r["id_entidad"] for r in noc_table.to_dict(orient="records")}
    nationality_report = map_participation_nationalities(retained_records, entities, entity_by_code, entity_by_name, noc_entity_mapping)
    write_csv(nationality_report, CONSOLIDATION_DIR / "participation_nationality_mapping.csv")
    participation = participant_table(retained_records)
    athlete_table = build_athlete_table(global_records, entity_by_code, entity_by_name, noc_entity_mapping)
    final_tables = {
        "entidad_geografica": entities, "poblacion": population_out, "noc": noc_table, "atleta": athlete_table,
        "sede": venue_table, "edicion_olimpica": edition_table, "deporte": sport_table, "disciplina": discipline_table,
        "evento": event_table, "participacion": participation,
    }
    for name, frame in final_tables.items():
        write_csv(frame, PROCESSED_DIR / f"{name}.csv")
    sport_conflicts = sport_map_report[sport_map_report["estado"] != "RESOLVED"].rename(
        columns={"valor_fuente": "clave", "disciplina_final": "valores", "criterio": "regla"}).assign(tipo_conflicto="SPORT_DISCIPLINE_PENDING")
    nationality_conflicts = nationality_report[nationality_report["estado"] == "UNRESOLVED"].rename(
        columns={"valor_original": "clave", "entidad": "valores", "criterio": "regla"}).assign(tipo_conflicto="PARTICIPATION_NATIONALITY_UNRESOLVED")
    dedup_conflicts = dedup_report[dedup_report["tipo"] == "CONFLICT"].rename(
        columns={"clave_logica": "clave", "motivo": "regla"}).assign(tipo_conflicto="PARTICIPATION_CONFLICT")
    geo_conflicts = geo_duplicates.rename(columns={"nombre_normalizado": "clave", "nombres": "valores"}).assign(tipo_conflicto="GEOGRAPHIC_DUPLICATE")
    conflicts = pd.concat([conflicts_attr.assign(tipo_conflicto="ATTRIBUTE", clave=conflicts_attr.get("id_atleta_global", "")),
                           pd.DataFrame(noc_conflicts), pd.DataFrame(edition_conflicts), sport_conflicts,
                           nationality_conflicts, dedup_conflicts, geo_conflicts], ignore_index=True, sort=False)
    write_csv(conflicts, CONSOLIDATION_DIR / "conflicts.csv")
    origins = {name: Counter() for name in final_tables}
    origins["entidad_geografica"]["fuente1_clean_populations_long"] = len(entities)
    origins["poblacion"]["fuente1_clean_populations_long"] = len(population_out)
    origins["noc"]["fuente1_noc_regions+participaciones"] = len(noc_table)
    for source in ["fuente1", "fuente2", "fuente3", "fuente4"]:
        origins["atleta"][source] = int(matching.loc[matching["fuente"] == source, "id_atleta_global"].nunique())
    origins["sede"]["fuentes2_3_4"] = len(venue_table)
    origins["edicion_olimpica"]["fuentes1_2_3_4"] = len(edition_table)
    origins["deporte"]["fuentes1_2_3_4"] = len(sport_table)
    origins["disciplina"]["fuentes1_2_3_4"] = len(discipline_table)
    origins["evento"]["fuentes1_2_3_4"] = len(event_table)
    origins["participacion"]["fuentes1_2_3_4"] = len(participation)
    counts = processed_counts(final_tables, origins)
    write_csv(counts, CONSOLIDATION_DIR / "processed_counts.csv")
    validations = validate_final(final_tables, sport_map_report)
    write_csv(validations, CONSOLIDATION_DIR / "final_validations.csv")
    after_hashes = raw_hash_validation()
    write_csv(after_hashes, CONSOLIDATION_DIR / "hash_validation.csv")
    strong_count = int((matching["tipo_match"] == "DETERMINISTIC_STRONG").sum())
    contextual_count = int((matching["tipo_match"] == "DETERMINISTIC_CONTEXTUAL").sum())
    ambiguous_count = int((matching["estado"] == "AMBIGUOUS").sum())
    unmatched_count = int((matching["estado"] == "UNMATCHED").sum())
    fuzzy_count = int((matching["score_fuzzy"].astype(str).str.len() > 0).sum())
    pending_sports = int((sport_map_report["estado"] != "RESOLVED").sum())
    failed_validations = int((validations["estado"] == "FAIL").sum())
    nationality_resolved = int(participation["id_pais_nacionalidad"].notna().sum())
    summary_lines = [
        "# Consolidación — Bloque 4", "", "Proceso determinístico y auditable por fuente. No se aplicó fuzzy matching automático.", "",
        f"- Identidades de atletas: **{len(athlete_table)}**.",
        f"- Matching STRONG: **{strong_count}**; CONTEXTUAL: **{contextual_count}**.",
        f"- Matching fuzzy automático: **{fuzzy_count}**.",
        f"- Unmatched: **{unmatched_count}**; ambiguous: **{ambiguous_count}**.",
        f"- Participaciones antes de deduplicar: **{len(records)}**; después: **{len(participation)}**.",
        f"- Participaciones con nacionalidad geográfica resuelta: **{nationality_resolved}**.",
        f"- Alineación Fuente 1 RAW/CLEAN segura: **{int(alignment_report.iloc[0]['matches_seguros'])}**; atributos enriquecidos: **{int(alignment_report.iloc[0]['atributos_enriquecidos'])}**.",
        f"- Fuente 4 exacta contra Fuente 2: **{int((overlap['estado'] == 'MATCHED_EXACT').sum())}/{len(overlap)}**.",
        f"- NOC resueltos: **{int((noc_matches['estado'] == 'RESOLVED').sum())}**; no resueltos: **{int((noc_matches['estado'] != 'RESOLVED').sum())}**.",
        f"- Mapeos deporte-disciplina resueltos: **{int((sport_map_report['estado'] == 'RESOLVED').sum())}**; pendientes: **{pending_sports}**.",
        f"- Duplicados conceptuales geográficos pendientes: **{len(geo_duplicates)}**.",
        f"- Validaciones de modelo PASS: **{int((validations['estado'] == 'PASS').sum())}/{len(validations)}**; FAIL: **{failed_validations}**.",
        f"- SHA-256 RAW: **{int((after_hashes['estado'] == 'MATCH').sum())}/10**.", "",
        "## Criterios", "", "Los nombres normalizados se usan solo como claves auxiliares. Un match determinístico requiere nombre auxiliar exacto y compatibilidad de sexo; el nivel A agrega evidencia NOC compatible. Los candidatos múltiples se conservan como AMBIGUOUS. Las identidades sin candidato se conservan como UNMATCHED con un id global propio.", "",
        f"La jerarquía deportiva sigue DEPORTE → DISCIPLINA → EVENTO. La terminología se contrastó con {IOC_PROGRAMME_REFERENCE} y {IOC_EVOLUTION_REFERENCE}. Las asignaciones no demostrables aparecen como PENDING_REVIEW.", "",
        "Fuente 4 se comparó con Fuente 2 en 14 columnas comunes. Las coincidencias exactas se excluyen de la salida consolidada y quedan auditadas.", "",
        "Los CSV no se declaran aptos para carga SQL mientras exista cualquier validación FAIL o mapeo deportivo pendiente.", "",
        "No se cargó SQL Server, no se crearon tablas SQL, no se inició el Bloque 5 y no se declara aprobado este bloque.",
    ]
    (CONSOLIDATION_DIR / "consolidation_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"Entidades finales generadas: {len(final_tables)}")
    print(f"Atletas globales: {len(athlete_table)}")
    print(f"Matching STRONG/CONTEXTUAL/AMBIGUOUS/UNMATCHED: {strong_count}/{contextual_count}/{ambiguous_count}/{unmatched_count}")
    print(f"Participaciones: {len(records)} -> {len(participation)}")
    print(f"Fuente 4 exacta contra Fuente 2: {(overlap['estado'] == 'MATCHED_EXACT').sum()}/{len(overlap)}")
    print(f"SHA-256 RAW: {(after_hashes['estado'] == 'MATCH').sum()}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
