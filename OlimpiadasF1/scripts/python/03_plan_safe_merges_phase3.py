"""Fase 3 del Bloque 4: plan seguro de merges, únicamente dry-run.

Lee los CSV existentes, recalcula componentes con las reglas conservadoras de
la Fase 3 y escribe reportes de auditoría. No modifica data/processed,
data/intermediate, data/raw ni SQL Server, y no aplica ningún merge.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from unidecode import unidecode


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
CLEANED = ROOT / "data" / "intermediate" / "cleaned"
MATCHING = ROOT / "data" / "intermediate" / "matching"
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


def tokens(value: object) -> set[str]:
    return {x for x in norm(value).split() if len(x) > 1}


def event_signature(value: object) -> str:
    key = norm(value)
    key = re.sub(r"\b(men|women) s\b", r"\1", key)
    key = re.sub(r"\b(olympic|olympics)\b", " ", key)
    return " ".join(sorted(set(key.split())))


def event_multiset(value: object) -> tuple[str, ...]:
    key = norm(value)
    key = re.sub(r"\b(men|women) s\b", r"\1", key)
    key = re.sub(r"\b(olympic|olympics)\b", " ", key)
    return tuple(sorted(key.split()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def processed_hashes() -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}


def dump(frame: pd.DataFrame, filename: str, columns: list[str] | None = None) -> None:
    if columns is not None:
        frame = frame.reindex(columns=columns)
    frame.to_csv(REPORTS / filename, index=False, encoding="utf-8")


def normalized_sex(value: object) -> str:
    return {"male": "M", "man": "M", "m": "M", "female": "F", "woman": "F", "f": "F"}.get(norm(value), norm(value))


def components_from_edges(edges: list[tuple[str, str]]) -> list[set[str]]:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    output: list[set[str]] = []
    seen: set[str] = set()
    for start in sorted(graph):
        if start in seen:
            continue
        stack = [start]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.add(current)
            stack.extend(graph[current] - seen)
        output.append(component)
    return output


def safe_event_components(event_candidates: pd.DataFrame, events: pd.DataFrame, parts: pd.DataFrame, editions: pd.DataFrame):
    event_by_id = events.set_index("id_evento").to_dict("index")
    # La calidad de fuente se toma del reporte refinado. La cobertura histórica
    # se calcula sobre las participaciones procesadas, sin releer los cuatro
    # archivos fuente completos.
    source_by_event: defaultdict[str, set[str]] = defaultdict(set)
    for row in event_candidates.to_dict("records"):
        for field in ["id_evento_a", "id_evento_b"]:
            event_id = txt(row.get(field))
            source_field = "fuentes_a" if field.endswith("a") else "fuentes_b"
            source_by_event[event_id].update(x.strip() for x in txt(row.get(source_field)).split("|") if x.strip())
    event_meta: defaultdict[str, dict[str, set[str]]] = defaultdict(lambda: {"deporte": set(), "disciplina": set(), "genero": set()})
    edge_info: dict[tuple[str, str], dict[str, str]] = {}
    for row in event_candidates.to_dict("records"):
        a, b = txt(row.get("id_evento_a")), txt(row.get("id_evento_b"))
        event_meta[a]["deporte"].add(norm(row.get("deporte")))
        event_meta[b]["deporte"].add(norm(row.get("deporte")))
        event_meta[a]["disciplina"].add(norm(row.get("disciplina")))
        event_meta[b]["disciplina"].add(norm(row.get("disciplina")))
        event_meta[a]["genero"].add(norm(row.get("genero_a")))
        event_meta[b]["genero"].add(norm(row.get("genero_b")))
        edge_info[tuple(sorted((a, b)))] = {"coexistencia": txt(row.get("coexistencia_misma_fuente"))}
    edition_label = {txt(r.id_edicion): f"{txt(r.anio)} {txt(r.temporada)}" for r in editions.itertuples()}
    coverage_by_event: defaultdict[str, set[str]] = defaultdict(set)
    for row in parts[["id_evento", "id_edicion"]].itertuples(index=False):
        coverage_by_event[txt(row.id_evento)].add(edition_label.get(txt(row.id_edicion), txt(row.id_edicion)))
    safe = event_candidates[event_candidates["clasificacion_final"].eq("SAFE_ALIAS")]
    edges = [(txt(r.id_evento_a), txt(r.id_evento_b)) for r in safe.itertuples()]
    edge_class: dict[tuple[str, str], str] = {}
    edge_reason: dict[tuple[str, str], str] = {}
    for r in event_candidates.itertuples():
        key = tuple(sorted((txt(r.id_evento_a), txt(r.id_evento_b))))
        edge_class[key] = txt(r.clasificacion_final)
        edge_reason[key] = txt(r.razon_refinada)
    components = components_from_edges(edges)
    safe_map: dict[str, str] = {}
    component_rows: list[dict[str, object]] = []
    merge_rows: list[dict[str, object]] = []
    for index, members in enumerate(sorted(components, key=lambda x: min(map(int, x))), 1):
        pairs = [(a, b) for a in sorted(members) for b in sorted(members) if int(a) < int(b)]
        internal_classes = [edge_class.get(tuple(sorted(pair)), "MISSING_PAIR") for pair in pairs]
        conflict_pairs = [pair for pair in pairs if edge_class.get(tuple(sorted(pair))) in {"CONFLICT_ALIAS", "REVIEW_ALIAS"}]
        missing_pairs = [pair for pair in pairs if edge_class.get(tuple(sorted(pair))) == "MISSING_PAIR"]
        sports = set().union(*(event_meta[member]["deporte"] for member in members)) - {""}
        disciplines = set().union(*(event_meta[member]["disciplina"] for member in members)) - {""}
        genders = set().union(*(event_meta[member]["genero"] for member in members)) - {""}
        coexistence = [edge_info.get(tuple(sorted((a, b))), {}).get("coexistencia", "") for a, b in pairs]
        reasons: list[str] = []
        if conflict_pairs:
            reasons.append("contiene CONFLICT_ALIAS/REVIEW_ALIAS interno")
        if missing_pairs:
            reasons.append("transitividad no demostrada: faltan pares SAFE_ALIAS explícitos")
        if len(sports) > 1 or len(disciplines) > 1 or len(genders) > 1:
            reasons.append("deporte/disciplina/género no homogéneos")
        if any(coexistence):
            reasons.append("coexistencia en misma fuente/edición")
        classification = "SAFE_EVENT_COMPONENT" if not reasons else "REVIEW_EVENT_COMPONENT"
        def event_score(member: str) -> tuple:
            value = event_by_id.get(member, {})
            name = txt(value.get("nombre"))
            source_names = source_by_event.get(member, set())
            source_rank = max([{"fuente1": 4, "fuente2": 3, "fuente3": 2, "fuente4": 1}.get(x, 0) for x in source_names] or [0])
            coverage = len(coverage_by_event.get(member, set()))
            repeated_tokens = len(event_multiset(name)) - len(set(event_multiset(name)))
            informative = len(re.sub(r"[^A-Za-z0-9À-ÿ]+", "", name))
            return (informative, source_rank, coverage, -repeated_tokens, -int(member))
        canonical = max(members, key=event_score)
        if classification == "SAFE_EVENT_COMPONENT":
            for member in members:
                safe_map[member] = canonical
        source_names = {txt(event_by_id.get(m, {}).get("nombre")) for m in members}
        component_rows.append({
            "componente_evento": f"EV{index:05d}", "miembros": ";".join(sorted(members, key=int)),
            "nombres": " | ".join(sorted(source_names)), "tamano": len(members),
            "deportes": " | ".join(sorted(sports)), "disciplinas": " | ".join(sorted(disciplines)),
            "generos": " | ".join(sorted(genders)), "pares_evaluados": len(pairs),
            "pares_safe": sum(x == "SAFE_ALIAS" for x in internal_classes),
            "pares_conflict_review": len(conflict_pairs), "pares_faltantes": len(missing_pairs),
            "coexistencia": " | ".join(sorted(set(x for x in coexistence if x))),
            "clasificacion": classification, "id_evento_canonico_propuesto": canonical,
            "nombre_canonico_propuesto": txt(event_by_id.get(canonical, {}).get("nombre")),
            "razon": "; ".join(reasons) if reasons else "Todos los pares internos son SAFE_ALIAS; atributos de dominio homogéneos; canon elegido por información, calidad de fuente, cobertura y desempate por ID.",
        })
        for member in sorted(members, key=int):
            merge_rows.append({
                "componente_evento": f"EV{index:05d}", "id_evento_origen": member,
                "nombre_origen": txt(event_by_id.get(member, {}).get("nombre")),
                "id_evento_canonico_propuesto": canonical if classification == "SAFE_EVENT_COMPONENT" else "",
                "nombre_canonico_propuesto": txt(event_by_id.get(canonical, {}).get("nombre")) if classification == "SAFE_EVENT_COMPONENT" else "",
                "merge_propuesto": "YES" if classification == "SAFE_EVENT_COMPONENT" and member != canonical else "NO",
                "estado_componente": classification, "razon": component_rows[-1]["razon"],
            })
    return safe_map, pd.DataFrame(component_rows), pd.DataFrame(merge_rows)


def source_details(matching: pd.DataFrame):
    sources: defaultdict[str, set[str]] = defaultdict(set)
    originals: defaultdict[str, set[str]] = defaultdict(set)
    for row in matching.to_dict("records"):
        gid, source, original = txt(row.get("id_atleta_global")), txt(row.get("fuente")), txt(row.get("id_original"))
        if gid:
            sources[gid].add(source)
            originals[gid].add(f"{source}:{original}")
    return sources, originals


def build_contexts(parts: pd.DataFrame, editions: pd.DataFrame, events: pd.DataFrame, nocs: pd.DataFrame, event_map: dict[str, str]):
    ed = {txt(r.id_edicion): f"{txt(r.anio)} {txt(r.temporada)}" for r in editions.itertuples()}
    ev = {txt(r.id_evento): txt(r.nombre) for r in events.itertuples()}
    noc = {txt(r.id_noc): txt(r.codigo_noc) for r in nocs.itertuples()}
    contexts: defaultdict[str, set[str]] = defaultdict(set)
    for row in parts.itertuples():
        athlete = txt(row.id_atleta)
        original_event = txt(row.id_evento)
        canonical_event = event_map.get(original_event, original_event)
        key = " | ".join([ed.get(txt(row.id_edicion), ""), noc.get(txt(row.id_noc), txt(row.id_noc)), txt(row.equipo), canonical_event, txt(row.medalla)])
        contexts[athlete].add(key)
    return contexts, ev


def bio_check(left: pd.Series, right: pd.Series) -> tuple[list[str], list[str], list[str]]:
    hard: list[str] = []
    unknown: list[str] = []
    signals: list[str] = []
    for field in ["fecha_nacimiento", "fecha_fallecimiento", "id_pais_nacionalidad"]:
        a, b = txt(left.get(field)), txt(right.get(field))
        if not a or not b:
            unknown.append(field)
        elif a != b:
            hard.append(f"{field}: {a} != {b}")
    a, b = normalized_sex(left.get("sexo")), normalized_sex(right.get("sexo"))
    if not a or not b:
        unknown.append("sexo")
    elif a != b:
        hard.append(f"sexo: {a} != {b}")
    for field in ["altura_cm", "peso_kg"]:
        av, bv = txt(left.get(field)), txt(right.get(field))
        if not av or not bv:
            unknown.append(field)
            continue
        try:
            diff = abs(float(av) - float(bv))
            signals.append(f"{field}: diferencia={diff:g}; señal, no regla de rechazo")
        except ValueError:
            unknown.append(field)
    return hard, unknown, signals


def athlete_plan(candidates: pd.DataFrame, athletes: pd.DataFrame, contexts, matching: pd.DataFrame, event_map: dict[str, str]):
    initial = candidates[candidates["clasificacion_final"].isin(["EXACT_DUPLICATE_IDENTITY", "STRONG_ALIAS"])].copy()
    athlete_by_id = athletes.set_index("id_atleta")
    sources, originals = source_details(matching)
    partners: defaultdict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
    for r in initial.itertuples():
        group = tuple(sorted(tokens(r.nombre_a) | tokens(r.nombre_b)))
        partners[(txt(r.id_atleta_a), group)].add(txt(r.id_atleta_b))
        partners[(txt(r.id_atleta_b), group)].add(txt(r.id_atleta_a))
    rows: list[dict[str, object]] = []
    safe_edges: list[tuple[str, str]] = []
    for r in initial.itertuples():
        a, b = txt(r.id_atleta_a), txt(r.id_atleta_b)
        left = athlete_by_id.loc[a] if a in athlete_by_id.index else pd.Series(dtype=str)
        right = athlete_by_id.loc[b] if b in athlete_by_id.index else pd.Series(dtype=str)
        shared = contexts.get(a, set()) & contexts.get(b, set())
        group = tuple(sorted(tokens(r.nombre_a) | tokens(r.nombre_b)))
        unique = len(partners[(a, group)]) == 1 and len(partners[(b, group)]) == 1
        hard, unknown, signals = bio_check(left, right)
        same_source = sorted(sources.get(a, set()) & sources.get(b, set()))
        reasons: list[str] = []
        if not shared: reasons.append("sin contexto compartido tras aplicar solo eventos SAFE_EVENT_COMPONENT")
        if not unique: reasons.append("más de un socio plausible en el grupo nominal/contextual")
        if hard: reasons.append("contradicción biográfica conocida: " + "; ".join(hard))
        if same_source: reasons.append("SAME_SOURCE_REVIEW: " + ",".join(same_source))
        if same_source:
            classification = "SAME_SOURCE_REVIEW"
        elif hard or not shared or not unique:
            classification = "REVIEW_ATHLETE_PAIR"
        else:
            classification = "SAFE_ATHLETE_PAIR"
            safe_edges.append((a, b))
        rows.append({
            "id_atleta_origen_a": a, "nombre_a": txt(r.nombre_a), "id_atleta_origen_b": b, "nombre_b": txt(r.nombre_b),
            "fuentes_atleta_a": " | ".join(sorted(sources.get(a, set()))), "fuentes_atleta_b": " | ".join(sorted(sources.get(b, set()))),
            "ids_originales_a": " | ".join(sorted(originals.get(a, set()))), "ids_originales_b": " | ".join(sorted(originals.get(b, set()))),
            "contextos_compartidos": json.dumps(sorted(shared), ensure_ascii=False),
            "biografia_estado": "CONFLICT" if hard else ("UNKNOWN/COMPATIBLE" if unknown else "COMPATIBLE"),
            "senales_altura_peso": " | ".join(signals), "same_source": " | ".join(same_source),
            "clasificacion": classification, "razon": "; ".join(reasons) if reasons else "Contexto compartido, candidato único y sin contradicción biográfica conocida.",
            "event_aliases_used": "SAFE_EVENT_COMPONENT_ONLY" if shared else "NONE",
        })
    return initial, pd.DataFrame(rows), safe_edges


def completeness(row: pd.Series) -> tuple[int, int]:
    fields = ["nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos", "sexo", "fecha_nacimiento", "ciudad_nacimiento", "region_nacimiento", "id_pais_nacimiento", "id_pais_nacionalidad", "fecha_fallecimiento", "ciudad_fallecimiento", "region_fallecimiento", "id_pais_fallecimiento", "altura_cm", "peso_kg", "roles", "afiliaciones", "titulos", "latitud", "longitud"]
    present = sum(bool(txt(row.get(f))) for f in fields)
    critical = sum(bool(txt(row.get(f))) for f in ["nombre_completo", "sexo", "fecha_nacimiento", "id_pais_nacionalidad", "roles"])
    return present, critical


def athlete_components(initial: pd.DataFrame, pair_plan: pd.DataFrame, safe_edges, athletes: pd.DataFrame, sources):
    initial_edges = [(txt(r.id_atleta_a), txt(r.id_atleta_b)) for r in initial.itertuples()]
    pair_status = {tuple(sorted((txt(r.id_atleta_origen_a), txt(r.id_atleta_origen_b)))): txt(r.clasificacion) for r in pair_plan.itertuples()}
    all_components = components_from_edges(initial_edges)
    by_id = athletes.set_index("id_atleta")
    safe_set = {tuple(sorted(x)) for x in safe_edges}
    maps: dict[str, str] = {}
    rows: list[dict[str, object]] = []
    for idx, members in enumerate(sorted(all_components, key=lambda x: min(map(int, x))), 1):
        # Una componente grande nunca se aprueba por transitividad implícita:
        # se reporta en revisión sin materializar una matriz cuadrática.
        oversized = len(members) > 100
        if oversized:
            pairs = [(a, b) for a, b in initial_edges if a in members and b in members]
        else:
            pairs = [(a, b) for a in sorted(members) for b in sorted(members) if int(a) < int(b)]
        statuses = [pair_status.get(tuple(sorted(p)), "MISSING_PAIR") for p in pairs]
        missing = [p for p in pairs if pair_status.get(tuple(sorted(p))) is None]
        if oversized:
            missing.append(("OVERSIZED_COMPONENT", "TRANSITIVITY"))
        bad = [p for p, status in zip(pairs, statuses) if status != "SAFE_ATHLETE_PAIR"]
        component_sources = set().union(*(sources.get(member, set()) for member in members))
        same_source = [p for p in pairs if pair_status.get(tuple(sorted(p))) == "SAME_SOURCE_REVIEW"]
        attribute_conflicts = [p for p, status in zip(pairs, statuses) if status == "REVIEW_ATHLETE_PAIR"]
        reasons: list[str] = []
        if missing: reasons.append("transitividad no demostrada: falta relación explícita para cada par interno")
        if bad: reasons.append("contiene pares no SAFE_ATHLETE_PAIR")
        if same_source: reasons.append("contiene SAME_SOURCE_REVIEW")
        classification = "SAFE_ATHLETE_COMPONENT" if not reasons else "REVIEW_ATHLETE_COMPONENT"
        scored = sorted(((completeness(by_id.loc[m]) if m in by_id.index else (0, 0), m) for m in members), reverse=True)
        canonical, score = scored[0][1], scored[0][0]
        if classification == "SAFE_ATHLETE_COMPONENT":
            for member in members:
                maps[member] = canonical
        rows.append({
            "componente_atleta": f"AT{idx:06d}", "miembros": ";".join(sorted(members, key=int)),
            "nombres": " | ".join(txt(by_id.loc[m, "nombre"]) for m in sorted(members, key=int) if m in by_id.index),
            "tamano": len(members), "fuentes": " | ".join(sorted(component_sources)),
            "pares_evaluados": len(pairs), "pares_safe": sum(s == "SAFE_ATHLETE_PAIR" for s in statuses),
            "pares_review_conflict": len(bad), "pares_same_source_review": len(same_source),
            "transitividad_insegura": "YES" if missing else "NO", "attribute_conflict": "YES" if attribute_conflicts else "NO",
            "clasificacion": classification, "id_atleta_canonico_propuesto": canonical,
            "nombre_canonico_propuesto": txt(by_id.loc[canonical, "nombre"]) if canonical in by_id.index else "",
            "puntuacion_completitud_canonico": f"{score[0]}/{score[1]}",
            "razon": "; ".join(reasons) if reasons else "Componente clique con todos los pares SAFE; canon por completitud biográfica, luego ID estable.",
        })
    return maps, pd.DataFrame(rows)


def enrichment_for_component(component_row: pd.Series, athlete_records: dict[str, dict[str, str]]) -> tuple[str, str]:
    members = [x for x in txt(component_row.get("miembros")).split(";") if x]
    canonical = txt(component_row.get("id_atleta_canonico_propuesto"))
    fields = ["nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos", "sexo", "fecha_nacimiento", "id_pais_nacionalidad", "altura_cm", "peso_kg", "roles", "afiliaciones", "titulos"]
    fill, conflict = [], []
    def comparable(field: str, value: object) -> str:
        return normalized_sex(value) if field == "sexo" else txt(value)
    for field in fields:
        vals = {comparable(field, athlete_records.get(m, {}).get(field)) for m in members if comparable(field, athlete_records.get(m, {}).get(field))}
        canonical_value = comparable(field, athlete_records.get(canonical, {}).get(field))
        if not canonical_value:
            if len(vals) == 1: fill.append(field)
            elif len(vals) > 1: conflict.append(field)
        elif len(vals - {canonical_value}) > 0:
            conflict.append(field)
    return ";".join(fill), ";".join(conflict)


def participation_impact(parts: pd.DataFrame, athlete_map: dict[str, str], event_map: dict[str, str]):
    frame = parts.copy()
    frame["id_atleta_canonico"] = frame["id_atleta"].map(lambda x: athlete_map.get(txt(x), txt(x)))
    frame["id_evento_canonico"] = frame["id_evento"].map(lambda x: event_map.get(txt(x), txt(x)))
    key_cols = ["id_atleta_canonico", "id_edicion", "id_evento_canonico", "id_noc", "equipo", "medalla"]
    # Solo se materializan grupos con al menos dos filas; recorrer todos los
    # grupos únicos de PARTICIPACION hace el dry-run innecesariamente costoso.
    duplicate_rows = frame[frame.duplicated(key_cols, keep=False)]
    groups = duplicate_rows.groupby(key_cols, dropna=False, sort=False)
    rows: list[dict[str, object]] = []
    mergeable_extra = 0
    conflicting_extra = 0
    for key, group in groups:
        if len(group) < 2:
            continue
        conflicts = []
        for field in ["posicion", "empatado", "estado_resultado", "edad", "altura_cm_registrada", "peso_kg_registrado", "nombre_competencia"]:
            values = {txt(x) for x in group[field] if txt(x)}
            if len(values) > 1:
                conflicts.append(field)
        classification = "MERGEABLE_DUPLICATE_CANDIDATE" if not conflicts else "CONFLICTING_DUPLICATE_CANDIDATE"
        extra = len(group) - 1
        if conflicts: conflicting_extra += extra
        else: mergeable_extra += extra
        rows.append({
            "grupo_logico": "|".join(txt(x) for x in key), "filas": len(group),
            "duplicados_mergeables": extra if not conflicts else 0, "duplicados_conflictivos": extra if conflicts else 0,
            "clasificacion": classification, "ids_participacion": ";".join(group["id_participacion"].map(txt)),
            "atletas_originales": ";".join(sorted(set(group["id_atleta"].map(txt)))), "eventos_originales": ";".join(sorted(set(group["id_evento"].map(txt)))),
            "campos_conflictivos": ";".join(conflicts), "id_atleta_canonico": key[0], "id_evento_canonico": key[2],
        })
    return pd.DataFrame(rows), mergeable_extra, conflicting_extra


def main() -> None:
    print("Fase 3: inicio", flush=True)
    before = processed_hashes()
    candidates_e = read_csv(REPORTS / "event_alias_candidates_refined.csv", ["id_evento_a", "nombre_a", "id_evento_b", "nombre_b", "deporte", "disciplina", "genero_a", "genero_b", "fuentes_a", "fuentes_b", "coexistencia_misma_fuente", "clasificacion_final", "razon_refinada"])
    candidates_a = read_csv(REPORTS / "athlete_duplicate_candidates_refined.csv", ["id_atleta_a", "nombre_a", "id_atleta_b", "nombre_b", "clasificacion_final"])
    athletes = read_csv(PROCESSED / "atleta.csv", ["id_atleta", "nombre", "nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos", "sexo", "fecha_nacimiento", "ciudad_nacimiento", "region_nacimiento", "id_pais_nacimiento", "id_pais_nacionalidad", "fecha_fallecimiento", "ciudad_fallecimiento", "region_fallecimiento", "id_pais_fallecimiento", "altura_cm", "peso_kg", "roles", "afiliaciones", "titulos", "latitud", "longitud"])
    parts = read_csv(PROCESSED / "participacion.csv", ["id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "nombre_competencia", "edad", "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado", "estado_resultado", "medalla"])
    events = read_csv(PROCESSED / "evento.csv", ["id_evento", "id_disciplina", "nombre"])
    editions = read_csv(PROCESSED / "edicion_olimpica.csv", ["id_edicion", "anio", "temporada", "id_sede"])
    nocs = read_csv(PROCESSED / "noc.csv", ["id_noc", "codigo_noc"])
    matching = read_csv(MATCHING / "athlete_matches.csv", ["fuente", "id_original", "id_atleta_global"])
    print("Fase 3: entradas cargadas", flush=True)

    event_map, event_components, event_plan = safe_event_components(candidates_e, events, parts, editions)
    print(f"Fase 3: eventos evaluados={len(event_components)}", flush=True)
    dump(event_plan, "event_merge_plan_dryrun.csv")
    dump(event_components, "event_components_dryrun.csv")
    contexts, _ = build_contexts(parts, editions, events, nocs, event_map)
    initial, pair_plan, safe_edges = athlete_plan(candidates_a, athletes, contexts, matching, event_map)
    print(f"Fase 3: pares reevaluados={len(initial)}", flush=True)
    athlete_map, athlete_components_frame = athlete_components(initial, pair_plan, safe_edges, athletes, source_details(matching)[0])
    print(f"Fase 3: componentes atletas={len(athlete_components_frame)}", flush=True)
    # Add deterministic enrichment information to component report.
    if not athlete_components_frame.empty:
        safe_rows = athlete_components_frame[athlete_components_frame["clasificacion"].eq("SAFE_ATHLETE_COMPONENT")]
        needed_ids = {member for value in safe_rows["miembros"] for member in txt(value).split(";") if member}
        athlete_records = athletes[athletes["id_atleta"].isin(needed_ids)].set_index("id_atleta").to_dict("index")
        enrichment_rows = []
        for _, row in athlete_components_frame.iterrows():
            if txt(row["clasificacion"]) == "SAFE_ATHLETE_COMPONENT":
                enrichment_rows.append(enrichment_for_component(row, athlete_records))
            else:
                enrichment_rows.append(("", ""))
        fills, conflicts = zip(*enrichment_rows)
        athlete_components_frame["campos_a_rellenar"] = list(fills)
        athlete_components_frame["campos_attribute_conflict"] = list(conflicts)
        athlete_components_frame.loc[athlete_components_frame["campos_attribute_conflict"].ne(""), "attribute_conflict"] = "YES"
        pair_plan["id_atleta_canonico_propuesto"] = pair_plan.apply(lambda r: athlete_map.get(txt(r["id_atleta_origen_a"]), txt(r["id_atleta_origen_a"])) if txt(r["clasificacion"]) == "SAFE_ATHLETE_PAIR" else "", axis=1)
    dump(pair_plan, "athlete_merge_plan_dryrun.csv")
    dump(athlete_components_frame, "athlete_components_dryrun.csv")
    impact, mergeable, conflicting = participation_impact(parts, athlete_map, event_map)
    print(f"Fase 3: grupos participacion={len(impact)}", flush=True)
    dump(impact, "participation_merge_impact_dryrun.csv")

    # Reproducible sample sets requested by the review.
    samples = []
    for label, frame, n in [
        ("SAFE_ATHLETE_COMPONENT", athlete_components_frame[athlete_components_frame.clasificacion.eq("SAFE_ATHLETE_COMPONENT")], 30),
        ("REVIEW_ATHLETE_COMPONENT", athlete_components_frame[athlete_components_frame.clasificacion.eq("REVIEW_ATHLETE_COMPONENT")], 30),
        ("SAME_SOURCE_REVIEW", pair_plan[pair_plan.clasificacion.eq("SAME_SOURCE_REVIEW")], 30),
        ("SAFE_EVENT_COMPONENT", event_components[event_components.clasificacion.eq("SAFE_EVENT_COMPONENT")], 30),
        ("REVIEW_EVENT_COMPONENT", event_components[event_components.clasificacion.eq("REVIEW_EVENT_COMPONENT")], 30),
    ]:
        for _, row in frame.head(n).iterrows():
            samples.append({"muestra": label, **{str(k): row[k] for k in frame.columns}})
    safe_components = athlete_components_frame[athlete_components_frame.clasificacion.eq("SAFE_ATHLETE_COMPONENT")].copy()
    if not safe_components.empty:
        safe_components["confidence_sort"] = safe_components["puntuacion_completitud_canonico"].map(lambda x: int(txt(x).split("/")[0]) if txt(x) else 0)
        for _, row in safe_components.sort_values(["confidence_sort", "componente_atleta"]).head(30).iterrows():
            samples.append({"muestra": "SAFE_ATHLETE_COMPONENT_LOWEST_CONFIDENCE", **{str(k): row[k] for k in athlete_components_frame.columns}})
    dump(pd.DataFrame(samples), "phase3_samples.csv")

    after = processed_hashes()
    integrity = pd.DataFrame([{"archivo": name, "sha256_antes": before.get(name, ""), "sha256_despues": after.get(name, ""), "estado": "MATCH" if before.get(name) == after.get(name) else "MISMATCH"} for name in sorted(set(before) | set(after))])
    dump(integrity, "processed_integrity_phase3.csv")

    messi = pair_plan[pair_plan.apply(lambda r: {txt(r.get("id_atleta_origen_a")), txt(r.get("id_atleta_origen_b"))} == {"110178", "167544"}, axis=1)]
    messi_rows = impact[impact["atletas_originales"].map(lambda x: set(txt(x).split(";")) == {"110178", "167544"})] if not impact.empty else pd.DataFrame()
    counts = {"SAFE_EVENT_COMPONENTS": int((event_components.clasificacion == "SAFE_EVENT_COMPONENT").sum()), "REVIEW_EVENT_COMPONENTS": int((event_components.clasificacion == "REVIEW_EVENT_COMPONENT").sum()), "EVENTS_AFFECTED": int(sum(len(txt(x).split(";")) for x in event_components.loc[event_components.clasificacion == "SAFE_EVENT_COMPONENT", "miembros"])), "ATHLETE_PAIRS_REEVALUATED": int(len(initial)), "SAFE_ATHLETE_COMPONENTS": int((athlete_components_frame.clasificacion == "SAFE_ATHLETE_COMPONENT").sum()), "REVIEW_ATHLETE_COMPONENTS": int((athlete_components_frame.clasificacion == "REVIEW_ATHLETE_COMPONENT").sum()), "ATHLETES_IN_SAFE_COMPONENTS": int(sum(len(txt(x).split(";")) for x in athlete_components_frame.loc[athlete_components_frame.clasificacion == "SAFE_ATHLETE_COMPONENT", "miembros"])), "SAME_SOURCE_REVIEW": int((pair_plan.clasificacion == "SAME_SOURCE_REVIEW").sum()), "ATTRIBUTE_CONFLICT": int((athlete_components_frame.attribute_conflict == "YES").sum()), "PARTICIPATIONS_BEFORE": len(parts), "PARTICIPATIONS_SIMULATED_AFTER": len(parts) - mergeable, "MERGEABLE_DUPLICATE_EXTRAS": mergeable, "CONFLICTING_DUPLICATE_EXTRAS": conflicting}
    with (REPORTS / "block4_merge_plan_phase3.md").open("w", encoding="utf-8") as handle:
        handle.write("# Bloque 4 — Fase 3: plan seguro de merges (dry-run)\n\n")
        handle.write("Esta fase genera únicamente un plan reproducible. No modifica `data/processed`, `data/intermediate`, `data/raw`, SQL Server ni aplica merges.\n\n")
        handle.write("## Reglas aplicadas\n\n")
        handle.write("- Los eventos se evalúan como componentes de grafo y solo `SAFE_ALIAS` puede proponer un mapa. Todo conflicto, coexistencia, par ausente o incompatibilidad de dominio deja el componente en revisión.\n")
        handle.write("- Los atletas se reevaluaron usando exclusivamente esos eventos seguros. Se rechaza la aprobación automática ante contradicciones biográficas, ambigüedad, misma fuente o transitividad no demostrada.\n")
        handle.write("- El canónico se elige por completitud biográfica, después por información disponible y finalmente por ID estable; no por mínimo ID como regla primaria.\n")
        handle.write("- Las participaciones solo se agrupan en memoria por atleta/evento canónicos y claves de participación. No se deduplica ningún CSV.\n\n")
        handle.write("## Métricas reales\n\n")
        for k, v in counts.items(): handle.write(f"- {k}: {v}\n")
        handle.write("\n## Regresión Lionel Messi\n\n")
        if not messi.empty:
            handle.write(messi.to_csv(index=False))
        else:
            handle.write("No se encontró el par esperado 110178/167544 en los pares reevaluados.\n")
        handle.write("\nParticipación lógica asociada:\n\n")
        handle.write(messi_rows.to_csv(index=False) if not messi_rows.empty else "No se encontró grupo lógico de participación en el dry-run.\n")
        handle.write("\n## Integridad\n\n")
        handle.write(f"CSV procesados antes: {sum(x == y for x, y in zip(before.values(), before.values()))}/{len(before)} MATCH. Después: {int((integrity.estado == 'MATCH').sum())}/{len(integrity)} MATCH.\n")
        handle.write("Los archivos de salida son planes y reportes diagnósticos; la aprobación y cualquier merge requieren revisión posterior.\n")

    print(json.dumps({"counts": counts, "processed_hashes_match": int((integrity.estado == "MATCH").sum()), "processed_hashes_total": len(integrity), "messi_pair_rows": len(messi), "messi_groups": len(messi_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
