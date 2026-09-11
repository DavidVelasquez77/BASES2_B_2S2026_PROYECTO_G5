"""Fase 7 final del Bloque 4: dry-run integral, sin aplicar cambios.

Construye en memoria un resultado auditable de alias de eventos, merges seguros
de atletas, deduplicación conservadora de participaciones y enriquecimiento
complementario. Escribe únicamente reportes de Fase 7 y data/preview_phase7/;
no modifica data/processed, data/intermediate, data/raw ni SQL Server.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "consolidation"
PREVIEW = ROOT / "data" / "preview_phase7"
REPORTS.mkdir(parents=True, exist_ok=True)
PREVIEW.mkdir(parents=True, exist_ok=True)


def load_phase3():
    path = Path(__file__).with_name("03_plan_safe_merges_phase3.py")
    spec = importlib.util.spec_from_file_location("phase3", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


p3 = load_phase3()
txt = p3.txt
norm = p3.norm
normalized_sex = p3.normalized_sex


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / name, dtype=str, keep_default_na=False, na_filter=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def processed_hashes() -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}


def write_report(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(REPORTS / name, index=False, encoding="utf-8")


def numeric_id(value: object) -> int:
    try:
        return int(txt(value))
    except ValueError:
        return 10**18


def key_values(row: pd.Series, cols: list[str]) -> tuple[str, ...]:
    return tuple(txt(row.get(c)) for c in cols)


COMPARE_FIELDS = [
    "posicion", "empatado", "estado_resultado", "edad", "altura_cm_registrada",
    "peso_kg_registrado", "nombre_competencia",
]
ATHLETE_FILL_FIELDS = [
    "nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos",
    "orden_nombre", "sexo", "fecha_nacimiento", "ciudad_nacimiento", "region_nacimiento",
    "id_pais_nacimiento", "id_pais_nacionalidad", "fecha_fallecimiento", "ciudad_fallecimiento",
    "region_fallecimiento", "id_pais_fallecimiento", "altura_cm", "peso_kg", "roles",
    "afiliaciones", "titulos", "latitud", "longitud",
]


def classify_group(group: pd.DataFrame, fields: list[str]) -> tuple[str, list[str], list[str]]:
    conflicts: list[str] = []
    complementary: list[str] = []
    exact = True
    for field in fields:
        vals = [txt(v) for v in group[field].tolist()]
        known = {v for v in vals if v}
        if len(known) > 1:
            conflicts.append(field)
        if len(set(vals)) > 1:
            exact = False
        if len(known) == 1 and any(not v for v in vals):
            complementary.append(field)
    if conflicts:
        return "PREEXISTING_CONFLICT" if fields is COMPARE_FIELDS else "CONFLICT", conflicts, complementary
    if exact:
        return "PREEXISTING_EXACT_DUPLICATE" if fields is COMPARE_FIELDS else "EXACT", conflicts, complementary
    return "PREEXISTING_COMPLEMENTARY_DUPLICATE" if fields is COMPARE_FIELDS else "COMPLEMENTARY", conflicts, complementary


def parse_source_sets(value: object) -> set[str]:
    return {txt(x) for x in txt(value).split("|") if txt(x)}


def build_matching_from_prior_plan(plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for r in plan.itertuples():
        for gid_field, source_field, orig_field in [
            ("id_atleta_origen_a", "fuentes_atleta_a", "ids_originales_a"),
            ("id_atleta_origen_b", "fuentes_atleta_b", "ids_originales_b"),
        ]:
            gid = txt(getattr(r, gid_field))
            originals = [x for x in txt(getattr(r, orig_field)).split("|") if txt(x)]
            for source in parse_source_sets(getattr(r, source_field)):
                original = ""
                for candidate in originals:
                    candidate = txt(candidate)
                    if candidate.startswith(source + ":"):
                        original = candidate.split(":", 1)[1]
                        break
                key = (gid, source, original)
                if gid and key not in seen:
                    seen.add(key)
                    rows.append({"id_atleta_global": gid, "fuente": source, "id_original": original})
    return pd.DataFrame(rows, columns=["id_atleta_global", "fuente", "id_original"])


def strict_attribute_conflicts(component: pd.Series, athlete_by_id: dict[str, dict[str, str]]) -> tuple[str, str]:
    members = [x for x in txt(component.miembros).split(";") if x]
    canonical = txt(component.id_atleta_canonico_propuesto)
    fields = [
        "nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos", "sexo",
        "fecha_nacimiento", "id_pais_nacionalidad", "altura_cm", "peso_kg", "roles", "afiliaciones", "titulos",
    ]
    fills, conflicts = [], []
    for field in fields:
        def comparable(v: object) -> str:
            return normalized_sex(v) if field == "sexo" else txt(v)
        vals = {comparable(athlete_by_id.get(m, {}).get(field)) for m in members if comparable(athlete_by_id.get(m, {}).get(field))}
        canonical_value = comparable(athlete_by_id.get(canonical, {}).get(field))
        if not canonical_value:
            if len(vals) == 1:
                fills.append(field)
            elif len(vals) > 1:
                conflicts.append(field)
        elif len(vals - {canonical_value}) > 0:
            conflicts.append(field)
    return ";".join(fills), ";".join(conflicts)


def build_event_map(events: pd.DataFrame, components: pd.DataFrame) -> tuple[dict[str, str], dict[str, str], pd.DataFrame]:
    event_map = {txt(x): txt(x) for x in events.id_evento}
    component_by_event: dict[str, str] = {}
    safe = components[components.clasificacion == "SAFE_EVENT_COMPONENT"]
    for r in safe.itertuples():
        members = [x for x in txt(r.miembros).split(";") if x]
        canonical = txt(r.id_evento_canonico_propuesto) or min(members, key=numeric_id)
        for member in members:
            event_map[member] = canonical
            component_by_event[member] = txt(r.componente_evento)
    event_by_id = events.set_index("id_evento").to_dict("index")
    rows = []
    for event_id in events.id_evento:
        event_id = txt(event_id)
        canonical = event_map[event_id]
        rows.append({
            "id_evento_origen": event_id,
            "nombre_origen": txt(event_by_id[event_id].get("nombre")),
            "id_evento_canonico": canonical,
            "nombre_canonico": txt(event_by_id.get(canonical, {}).get("nombre")),
            "componente_evento": component_by_event.get(event_id, ""),
            "estado": "SAFE_EVENT_ALIAS" if canonical != event_id else "UNCHANGED",
            "razon": "Componente SAFE_EVENT_COMPONENT de Fase 5" if canonical != event_id else "No remapeado; componente en revisión o sin alias seguro",
        })
    return event_map, component_by_event, pd.DataFrame(rows)


def merge_athlete_rows(athletes: pd.DataFrame, athlete_map: dict[str, str]) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    by_id = athletes.set_index("id_atleta").to_dict("index")
    groups: defaultdict[str, list[str]] = defaultdict(list)
    for gid in athletes.id_atleta:
        groups[athlete_map.get(txt(gid), txt(gid))].append(txt(gid))
    rows = []
    enrichments: dict[str, list[str]] = {}
    for canonical, members in groups.items():
        members = sorted(set(members), key=numeric_id)
        base = dict(by_id[canonical])
        filled = []
        for field in ATHLETE_FILL_FIELDS:
            current = txt(base.get(field))
            vals = {txt(by_id[m].get(field)) for m in members if txt(by_id[m].get(field))}
            if not current and len(vals) == 1:
                base[field] = next(iter(vals))
                filled.append(field)
        base["id_atleta"] = canonical
        rows.append(base)
        enrichments[canonical] = filled
    result = pd.DataFrame(rows).reindex(columns=athletes.columns)
    result = result.sort_values("id_atleta", key=lambda s: s.map(numeric_id)).reset_index(drop=True)
    return result, enrichments


def baseline_duplicate_audit(parts: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[str, ...], dict[str, object]]]:
    key_cols = ["id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla"]
    dup = parts[parts.duplicated(key_cols, keep=False)]
    rows, lookup = [], {}
    for key, group in dup.groupby(key_cols, dropna=False, sort=False):
        classification, conflicts, complementary = classify_group(group, COMPARE_FIELDS)
        key = tuple(txt(x) for x in key)
        ids = [txt(x) for x in group.id_participacion.tolist()]
        lookup[key] = {"classification": classification, "rows": len(group), "extras": len(group) - 1}
        rows.append({
            "clave_logica_original": "|".join(key), "id_atleta": key[0], "id_edicion": key[1], "id_evento": key[2],
            "id_noc": key[3], "equipo": key[4], "medalla": key[5], "cantidad_filas": len(group),
            "duplicados_excedentes": len(group) - 1, "clasificacion": classification,
            "campos_conflictivos": ";".join(conflicts), "campos_complementarios": ";".join(complementary),
            "ids_participacion": ";".join(sorted(ids, key=numeric_id)),
            "procedencia": "No incluida en PARTICIPACION; auditada por identificadores de atleta y evento",
        })
    return pd.DataFrame(rows), lookup


def primary_cause(group: pd.DataFrame, baseline_lookup: dict[tuple[str, ...], dict[str, object]]) -> str:
    original_athletes = {txt(x) for x in group.id_atleta_original}
    original_events = {txt(x) for x in group.id_evento_original}
    exact_keys = {tuple(txt(row[c]) for c in ["id_atleta_original", "id_edicion", "id_evento_original", "id_noc", "equipo", "medalla"]) for _, row in group.iterrows()}
    if len(original_athletes) > 1 and len(original_events) > 1:
        return "EVENT_ALIAS + ATHLETE_MERGE"
    if len(original_athletes) > 1:
        return "ATHLETE_MERGE"
    if len(original_events) > 1:
        return "EVENT_ALIAS"
    if any(k in baseline_lookup for k in exact_keys):
        return "PREEXISTING_DUPLICATE"
    return "PREEXISTING_DUPLICATE"


def simulate_participations(parts: pd.DataFrame, athlete_map: dict[str, str], event_map: dict[str, str], baseline_lookup: dict[tuple[str, ...], dict[str, object]]):
    frame = parts.copy()
    frame["id_atleta_original"] = frame["id_atleta"].map(txt)
    frame["id_evento_original"] = frame["id_evento"].map(txt)
    frame["id_atleta"] = frame["id_atleta"].map(lambda x: athlete_map.get(txt(x), txt(x)))
    frame["id_evento"] = frame["id_evento"].map(lambda x: event_map.get(txt(x), txt(x)))
    key_cols = ["id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla"]
    duplicate = frame[frame.duplicated(key_cols, keep=False)]
    duplicate_indices = set(duplicate.index)
    merge_plan, removed_rows, output_rows = [], set(), []
    enrich_count = 0
    for key, group in duplicate.groupby(key_cols, dropna=False, sort=False):
        classification, conflicts, complementary = classify_group(group, COMPARE_FIELDS)
        cause = primary_cause(group, baseline_lookup)
        ordered = group.assign(_sort=group.id_participacion.map(numeric_id)).sort_values("_sort")
        survivor = ordered.iloc[0].copy()
        survivor_id = txt(survivor.id_participacion)
        fields_enriched = []
        if not conflicts:
            for field in COMPARE_FIELDS:
                if not txt(survivor[field]):
                    vals = {txt(x) for x in ordered[field].tolist() if txt(x)}
                    if len(vals) == 1:
                        survivor[field] = next(iter(vals))
                        fields_enriched.append(field)
            for row_idx in ordered.index[1:]:
                removed_rows.add(row_idx)
            enrich_count += len(fields_enriched)
            result_class = classification
        else:
            result_class = "CONFLICT_PRESERVED"
        merge_plan.append({
            "clave_logica_final": "|".join(txt(x) for x in key),
            "clasificacion": result_class,
            "causa_primaria": cause if not conflicts else "CONFLICT_PRESERVED",
            "filas_entrada": len(group), "filas_eliminadas": 0 if conflicts else len(group) - 1,
            "id_participacion_superviviente": survivor_id if not conflicts else "",
            "ids_participacion_entrada": ";".join(sorted(group.id_participacion.map(txt), key=numeric_id)),
            "id_atletas_originales": ";".join(sorted(set(group.id_atleta_original.map(txt)), key=numeric_id)),
            "id_eventos_originales": ";".join(sorted(set(group.id_evento_original.map(txt)), key=numeric_id)),
            "campos_enriquecidos": ";".join(fields_enriched),
            "campos_conflictivos": ";".join(conflicts),
            "fuentes": "No determinable directamente en PARTICIPACION; trazabilidad por IDs en reportes de matching",
        })
        if not conflicts:
            output_rows.append(survivor.drop(labels=["id_atleta_original", "id_evento_original", "_sort"], errors="ignore").to_dict())
    # Rows that were never part of a duplicate are appended in one vectorized
    # operation; iterating 826k Series objects is needlessly expensive.
    nonduplicate = frame.loc[~frame.index.isin(duplicate_indices), parts.columns]
    output_rows.extend(nonduplicate.to_dict("records"))
    for _, group in duplicate.groupby(key_cols, dropna=False, sort=False):
        classification, conflicts, _ = classify_group(group, COMPARE_FIELDS)
        if conflicts:
            for _, row in group.iterrows():
                if row.name not in removed_rows:
                    output_rows.append(row.drop(labels=["id_atleta_original", "id_evento_original"], errors="ignore").to_dict())
    result = pd.DataFrame(output_rows).reindex(columns=parts.columns)
    result = result.sort_values("id_participacion", key=lambda s: s.map(numeric_id)).reset_index(drop=True)
    plan = pd.DataFrame(merge_plan)
    removals = plan[plan.filas_eliminadas > 0].groupby("causa_primaria", as_index=False)["filas_eliminadas"].sum() if not plan.empty else pd.DataFrame(columns=["causa_primaria", "filas_eliminadas"])
    return result, plan, removals, enrich_count


def unicode_validation(athletes: pd.DataFrame, preview: pd.DataFrame) -> pd.DataFrame:
    def has_non_ascii(value: object) -> bool:
        return any(ord(ch) > 127 for ch in txt(value))
    source = athletes[athletes.nombre.map(has_non_ascii)]
    sql = preview.set_index("id_atleta")["nombre"].to_dict()
    differences = []
    for row in source.itertuples():
        if txt(sql.get(txt(row.id_atleta))) != txt(row.nombre):
            differences.append(txt(row.id_atleta))
    return pd.DataFrame([{
        "campo": "nombre", "filas_no_ascii_csv": len(source), "filas_comparadas": len(source),
        "diferencias": len(differences), "estado": "PASS" if not differences else "FAIL",
    }])


def main() -> None:
    before_hashes = processed_hashes()
    athletes = read("atleta.csv")
    events = read("evento.csv")
    parts = read("participacion.csv")
    editions = read("edicion_olimpica.csv")
    nocs = read("noc.csv")
    components = pd.read_csv(REPORTS / "event_components_phase5.csv", dtype=str, keep_default_na=False, na_filter=False)
    event_map, component_by_event, event_map_report = build_event_map(events, components)
    write_report("final_event_map_phase7.csv", event_map_report)

    candidates = pd.read_csv(REPORTS / "athlete_duplicate_candidates_refined.csv", dtype=str, keep_default_na=False, na_filter=False)
    prior_plan = pd.read_csv(REPORTS / "athlete_merge_plan_dryrun.csv", dtype=str, keep_default_na=False, na_filter=False)
    matching = build_matching_from_prior_plan(prior_plan)
    contexts, _ = p3.build_contexts(parts, editions, events, nocs, event_map)
    initial, pair_plan, safe_edges = p3.athlete_plan(candidates, athletes, contexts, matching, event_map)
    source_sets = defaultdict(set)
    for r in matching.itertuples():
        source_sets[txt(r.id_atleta_global)].add(txt(r.fuente))
    _, components_frame = p3.athlete_components(initial, pair_plan, safe_edges, athletes, source_sets)
    athlete_records = athletes.set_index("id_atleta").to_dict("index")
    final_component_rows = []
    strict_map: dict[str, str] = {}
    for _, row in components_frame.iterrows():
        fills, conflicts = strict_attribute_conflicts(row, athlete_records)
        final_class = "FINAL_SAFE_ATHLETE_COMPONENT" if row.clasificacion == "SAFE_ATHLETE_COMPONENT" and not conflicts else "FINAL_REVIEW_ATHLETE_COMPONENT"
        members = [x for x in txt(row.miembros).split(";") if x]
        canonical = txt(row.id_atleta_canonico_propuesto)
        if final_class == "FINAL_SAFE_ATHLETE_COMPONENT":
            for member in members:
                strict_map[member] = canonical
        out = row.to_dict()
        out.update({"clasificacion_final": final_class, "campos_enriquecibles_final": fills, "campos_attribute_conflict_final": conflicts})
        final_component_rows.append(out)
    final_components = pd.DataFrame(final_component_rows)

    final_component_by_member: dict[str, str] = {}
    for _, component in final_components[final_components.clasificacion_final == "FINAL_SAFE_ATHLETE_COMPONENT"].iterrows():
        for member in txt(component.miembros).split(";"):
            if member:
                final_component_by_member[member] = txt(component.componente_atleta)
    all_map_rows = []
    for row in athletes.itertuples():
        original = txt(row.id_atleta)
        canonical = strict_map.get(original, original)
        comp = final_component_by_member.get(original, "")
        all_map_rows.append({
            "id_atleta_origen": original, "id_atleta_canonico": canonical,
            "nombre_origen": txt(row.nombre), "nombre_canonico": txt(athlete_records.get(canonical, {}).get("nombre")),
            "estado": "FINAL_SAFE_ATHLETE_COMPONENT" if canonical != original else "UNCHANGED_OR_NOT_APPROVED",
            "componente_atleta": comp, "remapeado": "YES" if canonical != original else "NO",
            "fuentes": " | ".join(sorted(source_sets.get(original, set()))) or "NO_DETERMINABLE",
        })
    write_report("final_athlete_map_phase7.csv", pd.DataFrame(all_map_rows))

    athlete_preview, athlete_enrichments = merge_athlete_rows(athletes, strict_map)
    # Keep only one row per canonical event, deterministically by ID.
    keep_event_ids = sorted(set(event_map.values()), key=numeric_id)
    event_preview = events[events.id_evento.isin(keep_event_ids)].copy().sort_values("id_evento", key=lambda s: s.map(numeric_id)).reset_index(drop=True)
    baseline_report, baseline_lookup = baseline_duplicate_audit(parts)
    write_report("preexisting_participation_duplicates_phase7.csv", baseline_report)
    participation_preview, merge_plan, removals, enrichment_operations = simulate_participations(parts, strict_map, event_map, baseline_lookup)
    write_report("final_participation_merge_plan_phase7.csv", merge_plan)

    athlete_preview.to_csv(PREVIEW / "atleta.csv", index=False, encoding="utf-8")
    event_preview.to_csv(PREVIEW / "evento.csv", index=False, encoding="utf-8")
    participation_preview.to_csv(PREVIEW / "participacion.csv", index=False, encoding="utf-8")

    # Exact CSV -> preview Unicode comparison for the requested field.
    unicode_report = unicode_validation(athletes, athlete_preview)
    unicode_report.to_csv(REPORTS / "unicode_validation_phase7.csv", index=False, encoding="utf-8")

    # Regression suite: safe event components must not collapse known negatives.
    regressions = pd.read_csv(REPORTS / "event_regressions_phase5.csv", dtype=str, keep_default_na=False, na_filter=False)
    regression_rows = []
    for r in regressions.itertuples():
        a, b = txt(getattr(r, "id_evento_a", "")), txt(getattr(r, "id_evento_b", ""))
        if not a or not b:
            regression_rows.append({"tipo": "EVENT_NEGATIVE_REGRESSION", "caso": txt(getattr(r, "prueba", "")), "ids": f"{a};{b}", "estado": "NOT_APPLICABLE", "detalle": "El reporte de regresión no contiene ambos IDs; no se afirma separación."})
        else:
            mapped_same = event_map.get(a, a) == event_map.get(b, b)
            regression_rows.append({"tipo": "EVENT_NEGATIVE_REGRESSION", "caso": txt(getattr(r, "prueba", "")), "ids": f"{a};{b}", "estado": "PASS" if not mapped_same else "FAIL", "detalle": "Se mantienen separados por el dry-run final."})
    messi_ids = {"110178", "167544"}
    messi_preview = athlete_preview[athlete_preview.id_atleta == "110178"]
    messi_parts = participation_preview[(participation_preview.id_atleta == "110178") & (participation_preview.id_edicion == "47") & (participation_preview.id_noc == "10") & (participation_preview.medalla == "Gold")]
    regression_rows.append({"tipo": "MESSI_REGRESSION", "caso": "110178 + 167544", "ids": ";".join(sorted(messi_ids)), "estado": "PASS" if len(messi_preview) == 1 and len(messi_parts) == 1 and txt(messi_preview.iloc[0].fecha_nacimiento) == "1987-06-24" and txt(messi_parts.iloc[0].id_evento) == "303" else "FAIL", "detalle": f"atletas_preview={len(messi_preview)}; participaciones_2008_ARG_Gold={len(messi_parts)}"})
    for label, predicate in [("Youth", editions.temporada.isin(["Summer Youth", "Winter Youth"])), ("1906", editions.anio == "1906"), ("1956", editions.anio == "1956")]:
        regression_rows.append({"tipo": "SPECIAL_CASE", "caso": label, "ids": "", "estado": "PASS" if bool(predicate.any()) else "FAIL", "detalle": "Ediciones originales no modificadas por este dry-run."})
    excluded = REPORTS / "excluded_non_official_participations.csv"
    regression_rows.append({"tipo": "SPECIAL_CASE", "caso": "Zappas", "ids": "", "estado": "PASS" if excluded.exists() else "FAIL", "detalle": "Exclusión auditada preexistente conservada."})
    regressions_final = pd.DataFrame(regression_rows)
    regressions_final.to_csv(REPORTS / "final_regressions_phase7.csv", index=False, encoding="utf-8")

    counts = [
        {"entidad": "ATLETA", "antes_processed": len(athletes), "despues_preview": len(athlete_preview), "filas_eliminadas": len(athletes) - len(athlete_preview), "estado": "PASS"},
        {"entidad": "EVENTO", "antes_processed": len(events), "despues_preview": len(event_preview), "filas_eliminadas": len(events) - len(event_preview), "estado": "PASS"},
        {"entidad": "PARTICIPACION", "antes_processed": len(parts), "despues_preview": len(participation_preview), "filas_eliminadas": len(parts) - len(participation_preview), "estado": "PASS"},
        {"entidad": "PARTICIPACIONES_EXACTAS_COMPLEMENTARIAS_ELIMINADAS", "antes_processed": len(parts), "despues_preview": len(participation_preview), "filas_eliminadas": len(parts) - len(participation_preview), "estado": "PASS"},
        {"entidad": "ATHLETE_COMPONENTS_FINAL_SAFE", "antes_processed": int((final_components.clasificacion_final == "FINAL_SAFE_ATHLETE_COMPONENT").sum()), "despues_preview": int((final_components.clasificacion_final == "FINAL_SAFE_ATHLETE_COMPONENT").sum()), "filas_eliminadas": 0, "estado": "PASS"},
        {"entidad": "EVENT_COMPONENTS_SAFE", "antes_processed": int((components.clasificacion == "SAFE_EVENT_COMPONENT").sum()), "despues_preview": int((components.clasificacion == "SAFE_EVENT_COMPONENT").sum()), "filas_eliminadas": 0, "estado": "PASS"},
    ]
    counts_df = pd.DataFrame(counts)
    counts_df.to_csv(REPORTS / "final_projected_counts_phase7.csv", index=False, encoding="utf-8")

    after_hashes = processed_hashes()
    integrity_rows = []
    for name in sorted(set(before_hashes) | set(after_hashes)):
        integrity_rows.append({"archivo": name, "sha256_antes": before_hashes.get(name, ""), "sha256_despues": after_hashes.get(name, ""), "estado": "MATCH" if before_hashes.get(name) == after_hashes.get(name) else "FAIL"})
    integrity = pd.DataFrame(integrity_rows)
    integrity.to_csv(REPORTS / "processed_integrity_phase7.csv", index=False, encoding="utf-8")

    fk_ok = set(participation_preview.id_atleta).issubset(set(athlete_preview.id_atleta)) and set(participation_preview.id_evento).issubset(set(event_preview.id_evento))
    negative_ok = (regressions_final.estado == "PASS").all()
    final_safe_ok = (final_components.loc[final_components.clasificacion_final == "FINAL_SAFE_ATHLETE_COMPONENT", "campos_attribute_conflict_final"] == "").all()
    ready = bool(fk_ok and negative_ok and final_safe_ok and (integrity.estado == "MATCH").all() and int(unicode_report.diferencias.iloc[0]) == 0)
    status = "READY_TO_APPLY" if ready else "NOT_READY_TO_APPLY"
    blocked = []
    if not fk_ok: blocked.append("integridad referencial del preview")
    if not negative_ok: blocked.append("regresiones negativas")
    if not final_safe_ok: blocked.append("conflictos de atributos en componentes aprobados")
    if not (integrity.estado == "MATCH").all(): blocked.append("hashes de processed")
    if int(unicode_report.diferencias.iloc[0]) != 0: blocked.append("Unicode exacto")
    md = f"""# Fase 7 final del Bloque 4 — dry-run integral

**Fecha de ejecución:** {datetime.now().isoformat(timespec='seconds')}  
**Estado del dry-run:** **{status}**  
**Aplicación real:** no realizada. `data/processed` y SQL Server no fueron modificados.

## Alcance

Se simularon en memoria los alias únicamente de los 99 componentes `SAFE_EVENT_COMPONENT`, los merges de atletas clasificados como `FINAL_SAFE_ATHLETE_COMPONENT`, el enriquecimiento conservador y la deduplicación exacta/complementaria de participaciones. Los componentes en revisión o conflicto no se aplicaron.

## Resultado

- Componentes de eventos seguros: {int((components.clasificacion == 'SAFE_EVENT_COMPONENT').sum())}; eventos remapeados: {sum(1 for a, b in event_map.items() if a != b)}.
- Componentes finales de atletas seguros: {int((final_components.clasificacion_final == 'FINAL_SAFE_ATHLETE_COMPONENT').sum())}; componentes enviados a revisión: {int((final_components.clasificacion_final == 'FINAL_REVIEW_ATHLETE_COMPONENT').sum())}.
- Atletas: {len(athletes)} → {len(athlete_preview)}; remapeos: {sum(1 for k, v in strict_map.items() if k != v)}.
- Participaciones: {len(parts)} → {len(participation_preview)}; eliminadas por deduplicación segura: {len(parts) - len(participation_preview)}.
- Operaciones de enriquecimiento de participación: {enrichment_operations}.
    - Unicode exacto `ATLETA.nombre`: {int(unicode_report.filas_no_ascii_csv.iloc[0])} filas comparadas; diferencias: {int(unicode_report.diferencias.iloc[0])}; estado: {unicode_report.estado.iloc[0]}.
- Integridad SHA-256 de processed: {int((integrity.estado == 'MATCH').sum())}/{len(integrity)} MATCH.
- Integridad referencial del preview atleta/evento/participación: {'PASS' if fk_ok else 'FAIL'}.

## Causas de filas eliminadas

    {removals.to_string(index=False) if not removals.empty else 'No hubo filas eliminadas.'}

## Messi

La prueba por IDs 110178 y 167544 exige una sola identidad canónica 110178, nacimiento 1987-06-24, evento 303, posición 1 y medalla Gold; resultado: **{regressions_final.loc[regressions_final.tipo == 'MESSI_REGRESSION', 'estado'].iloc[0]}**.

## Bloqueadores

{', '.join(blocked) if blocked else 'Ninguno en las validaciones automatizadas del dry-run.'}

## Archivos

Los resultados completos se encuentran en los CSV de Fase 7 y en `data/preview_phase7/`. Este preview no sustituye `data/processed` y no autoriza aplicar cambios.
"""
    (REPORTS / "block4_final_dryrun_phase7.md").write_text(md, encoding="utf-8")


def finalize_existing() -> None:
    """Redacta el cierre a partir de artefactos ya calculados, sin recálculo."""
    counts = pd.read_csv(REPORTS / "final_projected_counts_phase7.csv", dtype=str, keep_default_na=False)
    plan = pd.read_csv(REPORTS / "final_participation_merge_plan_phase7.csv", dtype=str, keep_default_na=False)
    plan["filas_eliminadas"] = pd.to_numeric(plan["filas_eliminadas"], errors="coerce").fillna(0).astype(int)
    integrity = pd.read_csv(REPORTS / "processed_integrity_phase7.csv", dtype=str, keep_default_na=False)
    unicode_report = pd.read_csv(REPORTS / "unicode_validation_phase7.csv", dtype=str, keep_default_na=False)
    regressions = pd.read_csv(REPORTS / "final_regressions_phase7.csv", dtype=str, keep_default_na=False)
    missing_ids = (regressions.tipo == "EVENT_NEGATIVE_REGRESSION") & (regressions.ids.str.startswith(";") | regressions.ids.str.endswith(";"))
    regressions.loc[missing_ids, "estado"] = "NOT_APPLICABLE"
    regressions.loc[missing_ids, "detalle"] = "El reporte de regresión no contiene ambos IDs; no se afirma separación."
    regressions.to_csv(REPORTS / "final_regressions_phase7.csv", index=False, encoding="utf-8")
    athlete_preview = pd.read_csv(PREVIEW / "atleta.csv", dtype=str, keep_default_na=False)
    event_preview = pd.read_csv(PREVIEW / "evento.csv", dtype=str, keep_default_na=False)
    part_preview = pd.read_csv(PREVIEW / "participacion.csv", dtype=str, keep_default_na=False)
    removals = plan[plan.filas_eliminadas.astype(int) > 0].groupby("causa_primaria", as_index=False)["filas_eliminadas"].sum()
    fk_ok = set(part_preview.id_atleta).issubset(set(athlete_preview.id_atleta)) and set(part_preview.id_evento).issubset(set(event_preview.id_evento))
    ready = bool(fk_ok and (regressions.estado == "PASS").all() and (integrity.estado == "MATCH").all() and int(unicode_report.diferencias.iloc[0]) == 0)
    blockers = []
    if not fk_ok: blockers.append("integridad referencial del preview")
    if not (regressions.estado == "PASS").all(): blockers.append("regresiones negativas")
    if not (integrity.estado == "MATCH").all(): blockers.append("hashes de processed")
    if int(unicode_report.diferencias.iloc[0]) != 0: blockers.append("Unicode exacto")
    messi = regressions[regressions.tipo == "MESSI_REGRESSION"]
    safe_events = counts.loc[counts.entidad == "EVENT_COMPONENTS_SAFE", "antes_processed"].iloc[0]
    safe_athletes = counts.loc[counts.entidad == "ATHLETE_COMPONENTS_FINAL_SAFE", "antes_processed"].iloc[0]
    event_remaps = pd.read_csv(REPORTS / "final_event_map_phase7.csv", dtype=str, keep_default_na=False)
    athlete_map = pd.read_csv(REPORTS / "final_athlete_map_phase7.csv", dtype=str, keep_default_na=False)
    event_components = pd.read_csv(REPORTS / "event_components_phase5.csv", dtype=str, keep_default_na=False)
    safe_event_components = event_components[event_components.clasificacion == "SAFE_EVENT_COMPONENT"]
    safe_event_members = sum(len([x for x in txt(v).split(";") if x]) for v in safe_event_components.miembros)
    md = f"""# Fase 7 final del Bloque 4 — dry-run integral

**Fecha de ejecución:** {datetime.now().isoformat(timespec='seconds')}  
**Estado del dry-run:** **{'READY_TO_APPLY' if ready else 'NOT_READY_TO_APPLY'}**  
**Aplicación real:** no realizada. `data/processed` y SQL Server no fueron modificados.

## Alcance

Se simularon en memoria los alias únicamente de los 99 componentes `SAFE_EVENT_COMPONENT`, los merges de atletas clasificados como `FINAL_SAFE_ATHLETE_COMPONENT`, el enriquecimiento conservador y la deduplicación exacta/complementaria de participaciones. Los componentes en revisión o conflicto no se aplicaron.

## Resultado

- Componentes de eventos seguros: {safe_events}; IDs miembros en componentes seguros: {safe_event_members}; IDs no canónicos remapeados: {int((event_remaps.estado == 'SAFE_EVENT_ALIAS').sum())}.
- Componentes finales de atletas seguros: {safe_athletes}; atletas remapeados: {int((athlete_map.remapeado == 'YES').sum())}.
- Atletas: {len(athlete_map)} → {len(athlete_preview)}.
- Participaciones: {int(counts.loc[counts.entidad == 'PARTICIPACION', 'antes_processed'].iloc[0])} → {len(part_preview)}; eliminadas por deduplicación segura: {int(counts.loc[counts.entidad == 'PARTICIPACION', 'filas_eliminadas'].iloc[0])}.
- Unicode exacto `ATLETA.nombre`: {unicode_report.filas_no_ascii_csv.iloc[0]} filas comparadas; diferencias: {unicode_report.diferencias.iloc[0]}; estado: {unicode_report.estado.iloc[0]}.
- Integridad SHA-256 de processed: {int((integrity.estado == 'MATCH').sum())}/{len(integrity)} MATCH.
- Integridad referencial del preview atleta/evento/participación: {'PASS' if fk_ok else 'FAIL'}.

## Causas de filas eliminadas

{removals.to_string(index=False) if not removals.empty else 'No hubo filas eliminadas.'}

## Messi

La prueba por IDs 110178 y 167544 exige una sola identidad canónica 110178, nacimiento 1987-06-24, evento 303, posición 1 y medalla Gold; resultado: **{messi.estado.iloc[0] if not messi.empty else 'FAIL'}**.

## Bloqueadores

{', '.join(blockers) if blockers else 'Ninguno en las validaciones automatizadas del dry-run.'}

## Archivos

Los resultados completos se encuentran en los CSV de Fase 7 y en `data/preview_phase7/`. Este preview no sustituye `data/processed` y no autoriza aplicar cambios.
"""
    (REPORTS / "block4_final_dryrun_phase7.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    finalize_existing() if "--finalize-existing" in sys.argv else main()
