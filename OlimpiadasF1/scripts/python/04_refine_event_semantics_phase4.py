"""Fase 4 diagnóstica del Bloque 4: semántica conservadora de EVENTO.

No aplica merges, no reescribe data/processed y no toca atletas, SQL Server,
RAW ni intermedios. Produce únicamente reportes para revisar el mapa de
aliases de evento y su impacto simulado.
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
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def token_list(value: object) -> list[str]:
    key = norm(value)
    key = re.sub(r"\b(men|women) s\b", r"\1", key)
    return key.split()


def canonical_gender(value: object) -> str:
    key = norm(value)
    return {"m": "men", "male": "men", "man": "men", "f": "women", "female": "women", "woman": "women"}.get(key, key)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hashes() -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}


def write(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(REPORTS / name, index=False, encoding="utf-8")


DISCRIMINANT_MODALITY = {
    "individual", "team", "singles", "doubles", "mixed", "relay", "sprint", "pursuit",
    "single", "double", "shot", "coxed", "coxless", "lightweight", "heavyweight",
    "freestyle", "classic", "combined", "qualification", "final",
}
GENRE_TOKENS = {"men", "women", "male", "female"}
YOUTH_TOKENS = {"youth", "yog", "young"}
GENERIC_TOKENS = {"olympic", "olympics", "games", "game", "event", "events", "competition", "competitions"}


def parent_tokens(meta: dict[str, set[str]]) -> Counter[str]:
    values = []
    for field in ["deporte", "disciplina"]:
        values.extend(token_list(next(iter(meta[field]), "")))
    return Counter(values)


def parse_event(name: str, meta: dict[str, set[str]]) -> dict[str, object]:
    raw = token_list(name)
    raw_counter = Counter(raw)
    gender_values = {canonical_gender(x) for x in meta.get("genero", set()) if txt(x)}
    gender = next(iter(gender_values)) if len(gender_values) == 1 else ""
    youth = bool(set(raw) & YOUTH_TOKENS)
    non_medal = bool(re.search(r"\bnon\s+medal\b", norm(name)))
    mixed = "mixed" in raw
    distance_matches = re.findall(r"\b\d+(?:\.\d+)?\s*(?:m|km|mi)\b", norm(name))
    weight_matches = re.findall(r"\b\d+(?:\.\d+)?\s*kg\b", norm(name))
    parent = parent_tokens(meta)
    residual = raw_counter - parent
    for token in list(residual):
        if token in GENERIC_TOKENS or token in GENRE_TOKENS or token in YOUTH_TOKENS:
            del residual[token]
    if non_medal:
        residual["non_medal"] -= 1
        if residual["non_medal"] <= 0:
            residual.pop("non_medal", None)
        if residual.get("non", 0):
            residual["non"] -= 1
            if residual["non"] <= 0:
                residual.pop("non", None)
    for token in DISCRIMINANT_MODALITY:
        residual.pop(token, None)
    for token in ["m", "km", "mi", "kg"]:
        residual.pop(token, None)
    for token in list(residual):
        if token.isdigit() or re.fullmatch(r"\d+(?:\.\d+)?", token):
            residual.pop(token, None)
    needed_parent = Counter({token: 1 for token in parent})
    redundancy = sum(max(0, raw_counter[token] - needed_parent[token]) for token in parent)
    modalities = tuple(sorted(token for token in raw if token in DISCRIMINANT_MODALITY))
    number_participants = tuple(sorted(token for token in raw if token in {"single", "double", "singles", "doubles", "team", "individual", "relay"}))
    type_tokens = tuple(sorted(residual.elements()))
    return {
        "deporte": next(iter(meta.get("deporte", set())), "") if len(meta.get("deporte", set())) == 1 else "",
        "disciplina": next(iter(meta.get("disciplina", set())), "") if len(meta.get("disciplina", set())) == 1 else "",
        "genero": gender,
        "modalidad_principal": "mixed" if mixed else (modalities[0] if modalities else ""),
        "modalidad_equipo": "team" if "team" in raw or "relay" in raw else "",
        "modalidad_individual": "individual" if "individual" in raw or "singles" in raw or "doubles" in raw else "",
        "distancia": " | ".join(distance_matches),
        "peso_categoria": " | ".join(weight_matches),
        "aparato": " | ".join(x for x in ["coxed", "coxless"] if x in raw),
        "tipo_prueba": " | ".join(type_tokens),
        "numero_participantes": " | ".join(number_participants),
        "youth": "YES" if youth else "NO",
        "non_medal": "YES" if non_medal else "NO",
        "mixed": "YES" if mixed else "NO",
        "modificadores_restantes": " | ".join(type_tokens),
        "modalidades": " | ".join(modalities),
        "redundancia_padre": redundancy,
        "semantic_key": json.dumps([gender, youth, non_medal, tuple(sorted(modalities)), tuple(distance_matches), tuple(weight_matches), tuple(type_tokens)], ensure_ascii=False),
    }


def connected_components(edges: list[tuple[str, str]]) -> list[set[str]]:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    seen: set[str] = set()
    result: list[set[str]] = []
    for start in sorted(graph, key=lambda x: int(x)):
        if start in seen:
            continue
        stack = [start]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            component.add(node)
            stack.extend(graph[node] - seen)
        result.append(component)
    return result


def main() -> None:
    before = hashes()
    events = read_csv(PROCESSED / "evento.csv", ["id_evento", "id_disciplina", "nombre"])
    parts = read_csv(PROCESSED / "participacion.csv", ["id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla", "nombre_competencia", "edad", "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado", "estado_resultado"])
    candidates = read_csv(REPORTS / "event_alias_candidates_refined.csv")
    metadata: defaultdict[str, dict[str, set[str]]] = defaultdict(lambda: {"deporte": set(), "disciplina": set(), "genero": set(), "fuentes": set()})
    source_overlaps: dict[tuple[str, str], str] = {}
    for row in candidates.to_dict("records"):
        a, b = txt(row["id_evento_a"]), txt(row["id_evento_b"])
        for event_id, gender_field, source_field in [(a, "genero_a", "fuentes_a"), (b, "genero_b", "fuentes_b")]:
            metadata[event_id]["deporte"].add(norm(row["deporte"]))
            metadata[event_id]["disciplina"].add(norm(row["disciplina"]))
            metadata[event_id]["genero"].add(canonical_gender(row[gender_field]))
            metadata[event_id]["fuentes"].update(x.strip() for x in txt(row[source_field]).split("|") if x.strip())
        source_overlaps[tuple(sorted((a, b)))] = txt(row["coexistencia_misma_fuente"])
    event_names = {txt(row.id_evento): txt(row.nombre) for row in events.itertuples()}

    parse_rows = []
    parsed = {}
    for event_id, name in event_names.items():
        parsed[event_id] = parse_event(name, metadata[event_id])
        parse_rows.append({"id_evento": event_id, "nombre": name, **{k: v for k, v in parsed[event_id].items() if k != "semantic_key"}, "semantic_key": parsed[event_id]["semantic_key"], "fuentes": " | ".join(sorted(metadata[event_id]["fuentes"]))})
    write(pd.DataFrame(parse_rows), "event_semantic_parse_phase4.csv")

    def pair_decision(a: str, b: str, row: dict[str, str] | None = None) -> tuple[str, str]:
        pa, pb = parsed[a], parsed[b]
        overlap = source_overlaps.get(tuple(sorted((a, b))), txt((row or {}).get("coexistencia_misma_fuente")))
        if overlap:
            return "CONFLICT_EVENT_ALIAS", "Coexistencia explícita en la misma fuente/edición; no se fusiona aunque el texto sea similar."
        for field in ["deporte", "disciplina", "genero"]:
            if not pa[field] or not pb[field]:
                return "REVIEW_EVENT_ALIAS", f"No se puede demostrar {field} para ambos eventos."
            if pa[field] != pb[field]:
                return "REVIEW_EVENT_ALIAS", f"{field} incompatible: {pa[field]} != {pb[field]}."
        if pa["semantic_key"] != pb["semantic_key"]:
            return "REVIEW_EVENT_ALIAS", "Difieren modificadores semánticos; la similitud textual no autoriza el alias."
        return "SAFE_EVENT_ALIAS", "Mismos atributos semánticos y modificadores discriminantes; la diferencia restante es formato o redundancia del deporte padre."

    alias_rows = []
    pair_classes: dict[tuple[str, str], str] = {}
    pair_reasons: dict[tuple[str, str], str] = {}
    for row in candidates.to_dict("records"):
        a, b = txt(row["id_evento_a"]), txt(row["id_evento_b"])
        classification, reason = pair_decision(a, b, row)
        key = tuple(sorted((a, b)))
        pair_classes[key] = classification
        pair_reasons[key] = reason
        alias_rows.append({**row, "semantic_key_a": parsed[a]["semantic_key"], "semantic_key_b": parsed[b]["semantic_key"], "modalidades_a": parsed[a]["modalidades"], "modalidades_b": parsed[b]["modalidades"], "modificadores_a": parsed[a]["modificadores_restantes"], "modificadores_b": parsed[b]["modificadores_restantes"], "clasificacion_phase4": classification, "razon_phase4": reason})
    write(pd.DataFrame(alias_rows), "event_alias_refined_phase4.csv")

    coverage: defaultdict[str, set[str]] = defaultdict(set)
    for row in parts[["id_evento", "id_edicion"]].itertuples(index=False):
        coverage[txt(row.id_evento)].add(txt(row.id_edicion))

    safe_edges = [key for key, classification in pair_classes.items() if classification == "SAFE_EVENT_ALIAS"]
    components = connected_components(safe_edges)
    event_map: dict[str, str] = {}
    component_rows = []
    component_lookup: dict[str, str] = {}
    for index, members in enumerate(sorted(components, key=lambda x: min(map(int, x))), 1):
        pairs = [(a, b) for a in sorted(members, key=int) for b in sorted(members, key=int) if int(a) < int(b)]
        statuses = [pair_classes.get(tuple(sorted(pair)), "MISSING_PAIR") for pair in pairs]
        missing = [pair for pair, status in zip(pairs, statuses) if status != "SAFE_EVENT_ALIAS"]
        classification = "SAFE_EVENT_COMPONENT" if not missing else "REVIEW_EVENT_COMPONENT"
        reasons = [] if not missing else ["No todos los pares internos tienen SAFE_EVENT_ALIAS explícito; se rechaza la transitividad no demostrada."]
        def canonical_score(event_id: str) -> tuple:
            p = parsed[event_id]
            source_rank = max([{"fuente1": 4, "fuente2": 3, "fuente3": 2, "fuente4": 1}.get(x, 0) for x in metadata[event_id]["fuentes"]] or [0])
            return (-int(p["redundancia_padre"]), source_rank, len(coverage[event_id]), -len(token_list(event_names[event_id])), -int(event_id))
        canonical = max(members, key=canonical_score)
        if classification == "SAFE_EVENT_COMPONENT":
            for member in members:
                event_map[member] = canonical
        component_id = f"EV4{index:05d}"
        for member in members:
            component_lookup[member] = component_id
        component_rows.append({
            "componente_evento": component_id, "miembros": ";".join(sorted(members, key=int)), "nombres": " | ".join(event_names[m] for m in sorted(members, key=int)), "tamano": len(members),
            "pares_evaluados": len(pairs), "pares_safe": sum(x == "SAFE_EVENT_ALIAS" for x in statuses), "pares_review": sum(x == "REVIEW_EVENT_ALIAS" for x in statuses), "pares_conflict": sum(x == "CONFLICT_EVENT_ALIAS" for x in statuses), "pares_faltantes": sum(x == "MISSING_PAIR" for x in statuses),
            "clasificacion": classification, "id_evento_canonico_propuesto": canonical if classification == "SAFE_EVENT_COMPONENT" else "", "nombre_canonico_propuesto": event_names[canonical] if classification == "SAFE_EVENT_COMPONENT" else "", "razon": "; ".join(reasons) if reasons else "Todos los pares internos son SAFE_EVENT_ALIAS; canon existente con menor redundancia semántica, mejor fuente/cobertura y desempate determinista por ID.",
        })
    write(pd.DataFrame(component_rows), "event_components_phase4.csv")

    # Auditoría de los componentes de Fase 3: se marca qué pasó con cada uno.
    old_components_path = REPORTS / "event_components_dryrun.csv"
    audit_rows = []
    if old_components_path.exists():
        for row in read_csv(old_components_path).to_dict("records"):
            members = [x for x in txt(row.get("miembros")).split(";") if x]
            new_ids = {component_lookup.get(x, "") for x in members if component_lookup.get(x, "")}
            new_classes = {txt(x["clasificacion"]) for x in component_rows if txt(x["componente_evento"]) in new_ids}
            audit_rows.append({"componente_phase3": txt(row.get("componente_evento")), "miembros": txt(row.get("miembros")), "nombres": txt(row.get("nombres")), "clasificacion_phase3": txt(row.get("clasificacion")), "componentes_phase4": " | ".join(sorted(new_ids)), "clasificacion_phase4": " | ".join(sorted(new_classes)) if new_classes else "SPLIT_OR_REVIEW", "contiene_art": "YES" if "art competitions" in norm(row.get("nombres")) else "NO", "contiene_running_target": "YES" if "running target" in norm(row.get("nombres")) else "NO", "contiene_mixed_doubles": "YES" if "mixed doubles" in norm(row.get("nombres")) else "NO", "contiene_team_individual": "YES" if ("team" in norm(row.get("nombres")) and "individual" in norm(row.get("nombres"))) else "NO"})

    # Impacto por evento solamente. Se agrupa con el nuevo id_evento, sin cambiar id_atleta.
    frame = parts.copy()
    frame["id_evento_canonico"] = frame["id_evento"].map(lambda x: event_map.get(txt(x), txt(x)))
    key_cols = ["id_atleta", "id_edicion", "id_evento_canonico", "id_noc", "equipo", "medalla"]
    impact_rows = []
    total_mergeable = 0
    total_conflicting = 0
    for row in component_rows:
        members = set(txt(row["miembros"]).split(";"))
        subset = frame[frame["id_evento"].isin(members)]
        duplicate_subset = subset[subset.duplicated(key_cols, keep=False)]
        comp_mergeable = 0
        comp_conflicting = 0
        group_count = 0
        group_details = []
        for key, group in duplicate_subset.groupby(key_cols, dropna=False, sort=False):
            group_count += 1
            conflicts = []
            for field in ["posicion", "empatado", "estado_resultado", "edad", "altura_cm_registrada", "peso_kg_registrado", "nombre_competencia"]:
                values = {txt(x) for x in group[field] if txt(x)}
                if len(values) > 1:
                    conflicts.append(field)
            extra = len(group) - 1
            if conflicts:
                comp_conflicting += extra
            else:
                comp_mergeable += extra
            group_details.append({"grupo_logico": "|".join(txt(x) for x in key), "filas": len(group), "clasificacion": "CONFLICTING_DUPLICATE_CANDIDATE" if conflicts else "MERGEABLE_DUPLICATE_CANDIDATE", "extras": extra, "campos_conflictivos": ";".join(conflicts), "ids_participacion": ";".join(group["id_participacion"].map(txt))})
        total_mergeable += comp_mergeable
        total_conflicting += comp_conflicting
        impact_rows.append({"tipo_registro": "COMPONENT_SUMMARY", "componente_evento": row["componente_evento"], "miembros": row["miembros"], "nombres": row["nombres"], "participaciones_afectadas": len(subset), "grupos_potencialmente_duplicados": group_count, "extras_mergeables": comp_mergeable, "extras_conflictivos": comp_conflicting, "clasificacion": "REVIEW_IMPACT" if comp_conflicting else ("MERGEABLE_IMPACT" if comp_mergeable else "NO_DUPLICATE_IMPACT"), "detalle_grupos": json.dumps(group_details, ensure_ascii=False)})
    write(pd.DataFrame(impact_rows), "event_participation_impact_phase4.csv")

    # Regresiones negativas sobre eventos realmente presentes.
    normalized_names = {event_id: norm(name) for event_id, name in event_names.items()}
    def find_event(phrase: str, exclude: str = "") -> str:
        wanted = set(norm(phrase).split())
        matches = [event_id for event_id, name in normalized_names.items() if wanted.issubset(set(name.split())) and (not exclude or exclude not in name)]
        return sorted(matches, key=int)[0] if matches else ""
    negative_specs = [("Single Shot != Double Shot", "single shot", "double shot"), ("Singles != Doubles", "singles", "doubles"), ("Individual != Team", "individual", "team"), ("Youth != adulto", "youth", ""), ("medal != non-medal", "non medal", ""), ("distancias distintas", "50 m", "100 m"), ("pesos distintos", "60 kg", "75 kg"), ("coxed != coxless", "coxed", "coxless"), ("lightweight != open", "lightweight", "open"), ("Dramatic != Epic", "dramatic", "epic"), ("Dramatic != Lyric", "dramatic", "lyric")]
    negative_rows = []
    for label, left_phrase, right_phrase in negative_specs:
        left_id = find_event(left_phrase)
        right_id = find_event(right_phrase, exclude=left_phrase) if right_phrase else ""
        if left_id and right_id:
            classification, reason = pair_decision(left_id, right_id)
            status = "PASS_SEPARATED" if classification != "SAFE_EVENT_ALIAS" else "FAIL_UNSAFE_ALIAS"
            detail = f"{event_names[left_id]} || {event_names[right_id]}"
        else:
            classification, reason, status, detail = "NOT_AVAILABLE", "No se encontraron ambos ejemplos como eventos distintos en evento.csv.", "NOT_AVAILABLE_IN_PROCESSED_EVENTO", f"left={event_names.get(left_id, '')}; right={event_names.get(right_id, '')}"
        negative_rows.append({"prueba": label, "id_evento_a": left_id, "id_evento_b": right_id, "clasificacion": classification, "estado": status, "detalle": detail, "motivo": reason})

    messi_key = tuple(sorted(("303", "1902")))
    messi_class = pair_classes.get(messi_key, "NOT_ANALYZED")
    messi_reason = pair_reasons.get(messi_key, "Los IDs no forman un par en el archivo de candidatos refinados.")
    after = hashes()
    integrity = pd.DataFrame([{"archivo": name, "sha256_antes": before.get(name, ""), "sha256_despues": after.get(name, ""), "estado": "MATCH" if before.get(name) == after.get(name) else "MISMATCH"} for name in sorted(set(before) | set(after))])
    write(integrity, "processed_integrity_phase4.csv")

    large = [row for row in impact_rows if int(row["extras_mergeables"]) > 100]
    metrics = {
        "EVENTOS_TOTALES": len(events), "PARES_ANALIZADOS": len(candidates), "SAFE_EVENT_ALIAS": sum(x == "SAFE_EVENT_ALIAS" for x in pair_classes.values()), "REVIEW_EVENT_ALIAS": sum(x == "REVIEW_EVENT_ALIAS" for x in pair_classes.values()), "CONFLICT_EVENT_ALIAS": sum(x == "CONFLICT_EVENT_ALIAS" for x in pair_classes.values()), "COMPONENTES_SEGUROS": sum(x["clasificacion"] == "SAFE_EVENT_COMPONENT" for x in component_rows), "COMPONENTES_REVISION": sum(x["clasificacion"] == "REVIEW_EVENT_COMPONENT" for x in component_rows), "EVENTOS_AFECTADOS": sum(len(txt(x["miembros"]).split(";")) for x in component_rows if x["clasificacion"] == "SAFE_EVENT_COMPONENT"), "PARTICIPACIONES_ANTES": len(parts), "PARTICIPACIONES_SIMULADAS_DESPUES": len(parts) - total_mergeable, "EXTRAS_POTENCIALMENTE_DUPLICADOS": total_mergeable, "EXTRAS_CONFLICTIVOS": total_conflicting, "COMPONENTES_MAS_100_DEDUP": len(large), "HASHES_MATCH": int((integrity["estado"] == "MATCH").sum()), "HASHES_TOTAL": len(integrity)}

    with (REPORTS / "block4_event_review_phase4.md").open("w", encoding="utf-8") as handle:
        handle.write("# Bloque 4 — Fase 4 diagnóstica: semántica conservadora de EVENTO\n\n")
        handle.write("Esta fase no aplica merges, no modifica `data/processed`, no modifica atletas, no modifica SQL Server y no inicia otro bloque.\n\n")
        handle.write("## Regla semántica\n\n")
        handle.write("Se exige igualdad explícita de deporte, disciplina, género, Youth/adulto, medal/non-medal, modalidad, distancia, peso, aparato y modificadores restantes. La similitud textual y la identidad por conjunto de tokens no autorizan un alias. La transitividad se verifica par a par.\n\n")
        handle.write("## Métricas\n\n")
        for key, value in metrics.items(): handle.write(f"- {key}: {value}\n")
        handle.write("\n## Componentes de Fase 3 auditados\n\n")
        if audit_rows:
            audit_frame = pd.DataFrame(audit_rows)
            handle.write("```text\n" + audit_frame.to_string(index=False) + "\n```")
        else:
            handle.write("No se encontró el reporte de componentes de Fase 3.\n")
        handle.write("\n\n## Pruebas negativas\n\n")
        handle.write("```text\n" + pd.DataFrame(negative_rows).to_string(index=False) + "\n```")
        handle.write("\n\n## Football/Messi\n\n")
        handle.write(f"303 `{event_names.get('303', '')}` ↔ 1902 `{event_names.get('1902', '')}`: **{messi_class}**. {messi_reason}\n")
        handle.write("Los IDs solo se usan como regresión; la regla es semántica general.\n\n")
        handle.write("## Componentes con más de 100 deduplicaciones simuladas\n\n")
        if large:
            large_view = pd.DataFrame(large)[["componente_evento", "miembros", "nombres", "participaciones_afectadas", "grupos_potencialmente_duplicados", "extras_mergeables", "extras_conflictivos", "clasificacion"]]
            handle.write("```text\n" + large_view.to_string(index=False) + "\n```\n")
        else:
            handle.write("Ninguno.\n")
        handle.write("\n\n## Integridad\n\n")
        handle.write(f"SHA-256 de processed antes/después: {int((integrity['estado'] == 'MATCH').sum())}/{len(integrity)} MATCH. No se modificaron los archivos de datos.\n")
        handle.write("Los componentes de atletas de la Fase 3 quedan invalidados provisionalmente hasta reevaluación posterior; esta fase no los recalcula.\n")

    print(json.dumps({"metrics": metrics, "messi": {"classification": messi_class, "reason": messi_reason}, "negative_tests": negative_rows}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
