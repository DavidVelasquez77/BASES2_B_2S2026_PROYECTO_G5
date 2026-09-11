"""Fase 5 diagnóstica del Bloque 4: semántica numérica conservadora de EVENTO.

No aplica merges, no modifica atletas, no reescribe data/processed y no toca
SQL Server. Solo genera reportes de aliases, componentes e impacto simulado.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from unidecode import unidecode

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "consolidation"
REPORTS.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, usecols=usecols)


def txt(value: object) -> str:
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return ""
    return str(value).strip()


def norm(value: object) -> str:
    value = unidecode(txt(value)).lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def tokens(value: object) -> list[str]:
    key = norm(value)
    key = re.sub(r"\b(men|women) s\b", r"\1", key)
    return key.split()


def gender(value: object) -> str:
    return {"m": "men", "male": "men", "man": "men", "f": "women", "female": "women", "woman": "women"}.get(norm(value), norm(value))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def processed_hashes() -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}


def write(frame: pd.DataFrame, filename: str) -> None:
    frame.to_csv(REPORTS / filename, index=False, encoding="utf-8")


GENERIC = {"olympic", "olympics", "games", "game", "event", "events", "competition", "competitions"}
GENRE = {"men", "women", "male", "female"}
YOUTH = {"youth", "yog", "young"}
MODALITY = {"single", "double", "singles", "doubles", "pair", "pairs", "four", "five", "eight", "team", "individual", "relay", "tandem", "mixed", "sprint", "pursuit", "shot", "coxed", "coxless", "lightweight", "heavyweight", "middleweight", "open", "freestyle", "classic", "combined", "qualification", "final"}
UNIT_WORDS = r"metres?|meters?|m|kilometres?|kilometers?|km|miles?|yards?|kg|kilograms?"
ATOM = r"(?:<=|>=|<|>|\+|-)?\d[\d,]*(?:\.\d+)?"
NUM_EXPR = rf"{ATOM}(?:\s*(?:/|and)\s*{ATOM})*"
NUM_UNIT_RE = re.compile(rf"(?P<num>{NUM_EXPR})\s*(?P<unit>{UNIT_WORDS})(?![a-z])", re.I)
WEIGHT_RE = re.compile(rf"(?P<num>{ATOM}(?:\s*-\s*{ATOM})?(?:\s*(?:/|and)\s*{ATOM})*)\s*(?P<unit>kg|kilograms?)(?![a-z])", re.I)


def canonical_number(value: str) -> str:
    value = re.sub(r"\s+", "", value.lower())
    parts = re.split(r"/|and", value)
    result = []
    for part in parts:
        part = part.replace(",", "")
        part = part.replace("≤", "<=").replace("≥", ">=")
        result.append(part)
    return "/".join(result)


def canonical_unit(value: str) -> str:
    key = value.lower()
    if key in {"metre", "metres", "meter", "meters", "m"}: return "m"
    if key in {"kilometre", "kilometres", "kilometer", "kilometers", "km"}: return "km"
    if key in {"mile", "miles"}: return "mile"
    if key in {"yard", "yards"}: return "yd"
    return "kg"


def parent_counter(meta: dict[str, set[str]]) -> Counter[str]:
    values: list[str] = []
    for field in ["deporte", "disciplina"]:
        values.extend(tokens(next(iter(meta[field]), "")))
    return Counter(values)


def parse_event(name: str, meta: dict[str, set[str]]) -> dict[str, object]:
    original = txt(name).lower().replace("≤", "<=").replace("≥", ">=")
    numeric_matches = list(NUM_UNIT_RE.finditer(original))
    weight_matches = list(WEIGHT_RE.finditer(original))
    distance_values: list[str] = []
    weight_values: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in numeric_matches:
        number = canonical_number(match.group("num"))
        unit = canonical_unit(match.group("unit"))
        if unit == "kg":
            weight_values.append(f"{number}:kg")
        else:
            distance_values.append(f"{number}:{unit}")
        spans.append((match.start(), match.end()))
    for match in weight_matches:
        number = canonical_number(match.group("num"))
        item = f"{number}:kg"
        if item not in weight_values:
            weight_values.append(item)
        spans.append((match.start(), match.end()))
    cleaned = original
    for start, end in sorted(set(spans), reverse=True):
        cleaned = cleaned[:start] + " " + cleaned[end:]
    raw = tokens(cleaned)
    raw_counter = Counter(raw)
    pcount = parent_counter(meta)
    residual = raw_counter - pcount
    for key in list(residual):
        if key in GENERIC or key in GENRE or key in YOUTH or key in {"non", "medal"}:
            residual.pop(key, None)
    for key in MODALITY:
        residual.pop(key, None)
    youth = bool(set(raw) & YOUTH)
    non_medal = bool(re.search(r"\bnon\s+medal\b", original))
    modalities = tuple(sorted(x for x in raw if x in MODALITY))
    gender_values = {gender(x) for x in meta["genero"] if txt(x)}
    parsed_gender = next(iter(gender_values)) if len(gender_values) == 1 else ""
    parent_needed = Counter({key: 1 for key in pcount})
    redundancy = sum(max(0, raw_counter[key] - parent_needed[key]) for key in pcount)
    remaining = tuple(sorted(residual.elements()))
    semantic_key = [
        next(iter(meta["deporte"]), "") if len(meta["deporte"]) == 1 else "",
        next(iter(meta["disciplina"]), "") if len(meta["disciplina"]) == 1 else "",
        parsed_gender, "youth" if youth else "adult", "non_medal" if non_medal else "medal",
        modalities, tuple(distance_values), tuple(weight_values), tuple(x for x in raw if x in {"coxed", "coxless"}), remaining,
    ]
    return {
        "deporte": semantic_key[0], "disciplina": semantic_key[1], "genero": parsed_gender,
        "categoria_edad": semantic_key[3], "condicion_medalla": semantic_key[4],
        "modalidad": " | ".join(modalities), "team_individual": "team" if "team" in raw else ("individual" if "individual" in raw else ""),
        "distancia_normalizada": " | ".join(distance_values), "distancia_compuesta": " | ".join(x for x in distance_values if "/" in x),
        "categoria_peso": " | ".join(weight_values), "aparato": " | ".join(x for x in raw if x in {"coxed", "coxless"}),
        "numero_participantes": " | ".join(x for x in modalities if x in {"single", "double", "pair", "pairs", "four", "five", "eight", "team", "individual", "relay", "tandem"}),
        "youth": "YES" if youth else "NO", "non_medal": "YES" if non_medal else "NO", "modificadores_restantes": " | ".join(remaining),
        "redundancia_padre": redundancy, "semantic_key": json.dumps(semantic_key, ensure_ascii=False),
    }


def components(edges: list[tuple[str, str]]) -> list[set[str]]:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        graph[a].add(b); graph[b].add(a)
    seen: set[str] = set(); result = []
    for start in sorted(graph, key=int):
        if start in seen: continue
        stack = [start]; group: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen: continue
            seen.add(node); group.add(node); stack.extend(graph[node] - seen)
        result.append(group)
    return result


def main() -> None:
    before = processed_hashes()
    events = read_csv(PROCESSED / "evento.csv", ["id_evento", "id_disciplina", "nombre"])
    parts = read_csv(PROCESSED / "participacion.csv", ["id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla", "nombre_competencia", "edad", "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado", "estado_resultado"])
    candidates = read_csv(REPORTS / "event_alias_candidates_refined.csv")
    meta: defaultdict[str, dict[str, set[str]]] = defaultdict(lambda: {"deporte": set(), "disciplina": set(), "genero": set(), "fuentes": set()})
    coexist: dict[tuple[str, str], str] = {}
    for row in candidates.to_dict("records"):
        a, b = txt(row["id_evento_a"]), txt(row["id_evento_b"])
        for event_id, gender_field, source_field in [(a, "genero_a", "fuentes_a"), (b, "genero_b", "fuentes_b")]:
            meta[event_id]["deporte"].add(norm(row["deporte"]))
            meta[event_id]["disciplina"].add(norm(row["disciplina"]))
            meta[event_id]["genero"].add(gender(row[gender_field]))
            meta[event_id]["fuentes"].update(x.strip() for x in txt(row[source_field]).split("|") if x.strip())
        coexist[tuple(sorted((a, b)))] = txt(row["coexistencia_misma_fuente"])
    names = {txt(row.id_evento): txt(row.nombre) for row in events.itertuples()}
    parsed = {event_id: parse_event(name, meta[event_id]) for event_id, name in names.items()}
    parse_rows = [{"id_evento": event_id, "nombre": names[event_id], **{k: v for k, v in value.items() if k != "semantic_key"}, "semantic_key": value["semantic_key"], "fuentes": " | ".join(sorted(meta[event_id]["fuentes"]))} for event_id, value in parsed.items()]
    write(pd.DataFrame(parse_rows), "event_semantic_parse_phase5.csv")

    def decision(a: str, b: str, row: dict[str, str] | None = None) -> tuple[str, str]:
        pa, pb = parsed[a], parsed[b]
        overlap = coexist.get(tuple(sorted((a, b))), txt((row or {}).get("coexistencia_misma_fuente")))
        if overlap: return "CONFLICT_EVENT_ALIAS", "Coexistencia en misma fuente/edición."
        for field in ["deporte", "disciplina", "genero"]:
            if not pa[field] or not pb[field]: return "REVIEW_EVENT_ALIAS", f"No se puede demostrar {field}."
            if pa[field] != pb[field]: return "REVIEW_EVENT_ALIAS", f"{field} incompatible: {pa[field]} != {pb[field]}."
        if pa["semantic_key"] != pb["semantic_key"]:
            return "REVIEW_EVENT_ALIAS", "Difieren distancia, secuencia numérica, peso, modalidad, edad, medalla o modificadores; no se autoriza por similitud textual."
        return "SAFE_EVENT_ALIAS", "Todos los atributos semánticos coinciden; la diferencia restante es formato o redundancia del deporte padre."

    alias_rows = []; pair_class: dict[tuple[str, str], str] = {}; pair_reason: dict[tuple[str, str], str] = {}
    for row in candidates.to_dict("records"):
        a, b = txt(row["id_evento_a"]), txt(row["id_evento_b"]); key = tuple(sorted((a, b)))
        classification, reason = decision(a, b, row); pair_class[key] = classification; pair_reason[key] = reason
        alias_rows.append({**row, "semantic_key_a": parsed[a]["semantic_key"], "semantic_key_b": parsed[b]["semantic_key"], "distancia_a": parsed[a]["distancia_normalizada"], "distancia_b": parsed[b]["distancia_normalizada"], "peso_a": parsed[a]["categoria_peso"], "peso_b": parsed[b]["categoria_peso"], "modalidad_a": parsed[a]["modalidad"], "modalidad_b": parsed[b]["modalidad"], "clasificacion_phase5": classification, "razon_phase5": reason})
    write(pd.DataFrame(alias_rows), "event_alias_refined_phase5.csv")

    coverage: defaultdict[str, set[str]] = defaultdict(set)
    editions: defaultdict[str, set[str]] = defaultdict(set)
    for row in parts[["id_evento", "id_edicion"]].itertuples(index=False):
        coverage[txt(row.id_evento)].add(txt(row.id_edicion)); editions[txt(row.id_evento)].add(txt(row.id_edicion))
    safe_edges = [key for key, value in pair_class.items() if value == "SAFE_EVENT_ALIAS"]
    event_components = []; event_map: dict[str, str] = {}; member_to_component: dict[str, str] = {}
    for index, member_set in enumerate(sorted(components(safe_edges), key=lambda x: min(map(int, x))), 1):
        members = sorted(member_set, key=int); pairs = [(a, b) for a in members for b in members if int(a) < int(b)]
        statuses = [pair_class.get(tuple(sorted(pair)), "MISSING_PAIR") for pair in pairs]
        missing = [pair for pair, status in zip(pairs, statuses) if status != "SAFE_EVENT_ALIAS"]
        classification = "SAFE_EVENT_COMPONENT" if not missing else "REVIEW_EVENT_COMPONENT"
        def score(event_id: str) -> tuple:
            p = parsed[event_id]; rank = max([{"fuente1": 4, "fuente2": 3, "fuente3": 2, "fuente4": 1}.get(x, 0) for x in meta[event_id]["fuentes"]] or [0])
            return (-int(p["redundancia_padre"]), rank, len(coverage[event_id]), -len(tokens(names[event_id])), -int(event_id))
        canonical = max(members, key=score)
        component_id = f"EV5{index:05d}"
        for member in members:
            member_to_component[member] = component_id
            if classification == "SAFE_EVENT_COMPONENT": event_map[member] = canonical
        event_components.append({"componente_evento": component_id, "miembros": ";".join(members), "nombres": " | ".join(names[x] for x in members), "deporte": " | ".join(sorted(set(parsed[x]["deporte"] for x in members))), "disciplina": " | ".join(sorted(set(parsed[x]["disciplina"] for x in members))), "pares_evaluados": len(pairs), "pares_safe": sum(x == "SAFE_EVENT_ALIAS" for x in statuses), "pares_review": sum(x == "REVIEW_EVENT_ALIAS" for x in statuses), "pares_conflict": sum(x == "CONFLICT_EVENT_ALIAS" for x in statuses), "pares_faltantes": sum(x == "MISSING_PAIR" for x in statuses), "clasificacion": classification, "id_evento_canonico_propuesto": canonical if classification == "SAFE_EVENT_COMPONENT" else "", "nombre_canonico_propuesto": names[canonical] if classification == "SAFE_EVENT_COMPONENT" else "", "razon": "Todos los pares internos son SAFE_EVENT_ALIAS; canon existente con menor redundancia numérica/semántica y cobertura determinista." if not missing else "Componente en revisión: contiene REVIEW/CONFLICT/MISSING_PAIR interno."})
    write(pd.DataFrame(event_components), "event_components_phase5.csv")

    frame = parts.copy(); frame["id_evento_canonico"] = frame["id_evento"].map(lambda x: event_map.get(txt(x), txt(x)))
    key_cols = ["id_atleta", "id_edicion", "id_evento_canonico", "id_noc", "equipo", "medalla"]
    impact_rows = []; total_mergeable = 0; total_conflicting = 0
    for comp in event_components:
        members = set(txt(comp["miembros"]).split(";")); subset = frame[frame["id_evento"].isin(members)]; duplicate_subset = subset[subset.duplicated(key_cols, keep=False)]
        mergeable = 0; conflicting = 0; group_count = 0; details = []
        for key, group in duplicate_subset.groupby(key_cols, dropna=False, sort=False):
            group_count += 1; conflicts = []
            for field in ["posicion", "empatado", "estado_resultado", "edad", "altura_cm_registrada", "peso_kg_registrado", "nombre_competencia"]:
                if len({txt(x) for x in group[field] if txt(x)}) > 1: conflicts.append(field)
            extra = len(group) - 1
            if conflicts: conflicting += extra
            else: mergeable += extra
            details.append({"grupo": "|".join(txt(x) for x in key), "filas": len(group), "extras": extra, "clasificacion": "CONFLICTING" if conflicts else "MERGEABLE", "campos_conflictivos": ";".join(conflicts)})
        total_mergeable += mergeable; total_conflicting += conflicting
        impact_rows.append({"componente_evento": comp["componente_evento"], "clasificacion_componente": comp["clasificacion"], "miembros": comp["miembros"], "nombres": comp["nombres"], "participaciones_afectadas": len(subset), "grupos_potencialmente_duplicados": group_count, "extras_mergeables": mergeable, "extras_conflictivos": conflicting, "detalle_grupos": json.dumps(details, ensure_ascii=False)})
    write(pd.DataFrame(impact_rows), "event_participation_impact_phase5.csv")

    high = []
    for impact, comp in zip(impact_rows, event_components):
        if int(impact["extras_mergeables"]) > 100:
            high.append({"componente_evento": comp["componente_evento"], "deporte": comp["deporte"], "disciplina": comp["disciplina"], "eventos": comp["miembros"], "nombres": comp["nombres"], "fuentes": " | ".join(sorted(set().union(*(meta[x]["fuentes"] for x in comp["miembros"].split(";"))))), "ediciones": " | ".join(sorted(set().union(*(editions[x] for x in comp["miembros"].split(";"))))), "participaciones_afectadas": impact["participaciones_afectadas"], "deduplicaciones": impact["extras_mergeables"], "razon_semantica": comp["razon"]})
    write(pd.DataFrame(high), "event_high_impact_audit_phase5.csv")

    regression_specs = [("500 metres != 1500 metres", "500 metres", "1500 metres"), ("200 metres != 1200 metres", "200 metres", "1200 metres"), ("5.5 metres != 6.5 metres", "5.5 metres", "6.5 metres"), ("10 km != 15 km", "10 km", "15 km"), ("10 km != 10/15 km Pursuit", "10 km", "10/15 km pursuit"), ("5 km != 5/10 km Pursuit", "5 km", "5/10 km pursuit"), ("Single Shot != Double Shot", "single shot", "double shot"), ("Singles != Doubles", "singles", "doubles"), ("Team != Individual", "team", "individual"), ("Four != Four/Five", "four", "four five"), ("Youth != Adult", "youth", "adult"), ("coxed != coxless", "coxed", "coxless"), ("lightweight != heavyweight/open", "lightweight", "heavyweight"), ("Dramatic != Epic", "dramatic works", "epic works"), ("Dramatic != Lyric", "dramatic works", "lyric works")]
    def search_norm(value: object) -> str:
        value = unidecode(txt(value)).lower()
        value = re.sub(r"(?<=\d),(?=\d)", "", value)
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", value)).strip()
    norm_names = {event_id: search_norm(name) for event_id, name in names.items()}
    def find(phrase: str, used: str = "") -> str:
        wanted = set(search_norm(phrase).split()); found = [x for x, name in norm_names.items() if wanted.issubset(set(name.split()))]
        return sorted(found, key=int)[0] if found else ""
    regressions = []
    for label, left_phrase, right_phrase in regression_specs:
        left = find(left_phrase); right = find(right_phrase, left_phrase)
        if left and right:
            classification, reason = decision(left, right); status = "PASS_SEPARATED" if classification != "SAFE_EVENT_ALIAS" else "FAIL_UNSAFE_ALIAS"
            detail = f"{names[left]} || {names[right]}"
        else:
            classification, reason, status, detail = "NOT_AVAILABLE", "No se encontraron ambos ejemplos en evento.csv.", "NOT_AVAILABLE_IN_PROCESSED_EVENTO", f"left={names.get(left, '')}; right={names.get(right, '')}"
        regressions.append({"prueba": label, "id_evento_a": left, "id_evento_b": right, "clasificacion": classification, "estado": status, "detalle": detail, "motivo": reason})
    write(pd.DataFrame(regressions), "event_regressions_phase5.csv")

    messi_key = tuple(sorted(("303", "1902"))); messi_class = pair_class.get(messi_key, "NOT_ANALYZED"); messi_reason = pair_reason.get(messi_key, "No hay par en candidatos.")
    after = processed_hashes(); integrity = pd.DataFrame([{"archivo": name, "sha256_antes": before.get(name, ""), "sha256_despues": after.get(name, ""), "estado": "MATCH" if before.get(name) == after.get(name) else "MISMATCH"} for name in sorted(set(before) | set(after))]); write(integrity, "processed_integrity_phase5.csv")
    metrics = {"EVENTOS_TOTALES": len(events), "PARES_ANALIZADOS": len(candidates), "SAFE_EVENT_ALIAS": sum(x == "SAFE_EVENT_ALIAS" for x in pair_class.values()), "REVIEW_EVENT_ALIAS": sum(x == "REVIEW_EVENT_ALIAS" for x in pair_class.values()), "CONFLICT_EVENT_ALIAS": sum(x == "CONFLICT_EVENT_ALIAS" for x in pair_class.values()), "COMPONENTES_SEGUROS": sum(x["clasificacion"] == "SAFE_EVENT_COMPONENT" for x in event_components), "EVENTOS_AFECTADOS": sum(len(txt(x["miembros"]).split(";")) for x in event_components if x["clasificacion"] == "SAFE_EVENT_COMPONENT"), "PARTICIPACIONES_ANTES": len(parts), "PARTICIPACIONES_SIMULADAS_DESPUES": len(parts) - total_mergeable, "EXTRAS_MERGEABLES": total_mergeable, "EXTRAS_CONFLICTIVOS": total_conflicting, "COMPONENTES_MAS_100_DEDUP": len(high), "HASHES_MATCH": int((integrity["estado"] == "MATCH").sum()), "HASHES_TOTAL": len(integrity)}
    with (REPORTS / "block4_event_review_phase5.md").open("w", encoding="utf-8") as handle:
        handle.write("# Bloque 4 — Fase 5 diagnóstica: semántica numérica de EVENTO\n\nEsta fase no aplica merges, no modifica atletas, no regenera `data/processed/` y no modifica SQL Server.\n\n")
        handle.write("## Métricas\n\n" + "\n".join(f"- {k}: {v}" for k, v in metrics.items()) + "\n\n")
        handle.write("## Regresiones\n\n```text\n" + pd.DataFrame(regressions).to_string(index=False) + "\n```\n\n")
        handle.write(f"## Football/Messi\n\n303 `{names.get('303', '')}` ↔ 1902 `{names.get('1902', '')}`: **{messi_class}**. {messi_reason}\n\n")
        handle.write("## Componentes de alto impacto\n\n```text\n" + (pd.DataFrame(high).to_string(index=False) if high else "Ninguno") + "\n```\n\n")
        handle.write(f"SHA-256 de processed antes/después: {int((integrity['estado'] == 'MATCH').sum())}/{len(integrity)} MATCH. Los SAFE_ATHLETE_COMPONENT de Fases anteriores siguen invalidados provisionalmente.\n")
    print(json.dumps({"metrics": metrics, "messi": {"classification": messi_class, "reason": messi_reason}, "regressions": regressions}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
