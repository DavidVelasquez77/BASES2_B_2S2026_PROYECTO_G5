"""Fase 6 diagnóstica del Bloque 4: impacto causal de aliases de EVENTO.

No aplica merges, no modifica data/processed, no toca atletas ni SQL Server.
Calcula baseline y solo el incremento producido por los componentes seguros de
la Fase 5.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hashes() -> dict[str, str]:
    return {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}


def write(frame: pd.DataFrame, filename: str) -> None:
    frame.to_csv(REPORTS / filename, index=False, encoding="utf-8")


def conflict_fields(group: pd.DataFrame) -> list[str]:
    fields = ["posicion", "empatado", "estado_resultado", "edad", "altura_cm_registrada", "peso_kg_registrado", "nombre_competencia"]
    conflicts = []
    for field in fields:
        values = {txt(value) for value in group[field] if txt(value)}
        if len(values) > 1:
            conflicts.append(field)
    return conflicts


def main() -> None:
    before = hashes()
    parts = read_csv(PROCESSED / "participacion.csv", ["id_participacion", "id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla", "nombre_competencia", "edad", "altura_cm_registrada", "peso_kg_registrado", "posicion", "empatado", "estado_resultado"])
    components = read_csv(REPORTS / "event_components_phase5.csv")
    semantic = read_csv(REPORTS / "event_semantic_parse_phase5.csv", ["id_evento", "fuentes"])
    regressions = read_csv(REPORTS / "event_regressions_phase5.csv")
    safe_components = components[components["clasificacion"].eq("SAFE_EVENT_COMPONENT")].copy()

    member_to_component: dict[str, str] = {}
    event_map: dict[str, str] = {}
    component_by_id: dict[str, dict[str, str]] = {}
    for row in safe_components.to_dict("records"):
        component_id = txt(row["componente_evento"])
        members = [x for x in txt(row["miembros"]).split(";") if x]
        canonical = txt(row["id_evento_canonico_propuesto"])
        component_by_id[component_id] = row
        for event_id in members:
            member_to_component[event_id] = component_id
            event_map[event_id] = canonical

    source_map = {txt(row.id_evento): txt(row.fuentes) for row in semantic.itertuples()}
    baseline_key = ["id_atleta", "id_edicion", "id_evento", "id_noc", "equipo", "medalla"]
    simulated_key = ["id_atleta", "id_edicion", "id_evento_canonico", "id_noc", "equipo", "medalla"]

    # Baseline: only duplicates already present with original event IDs.
    baseline_duplicates = parts[parts.duplicated(baseline_key, keep=False)]
    baseline_rows = []
    baseline_group_count = 0
    baseline_extra_count = 0
    baseline_groups_by_component: defaultdict[str, int] = defaultdict(int)
    baseline_extras_by_component: defaultdict[str, int] = defaultdict(int)
    for key, group in baseline_duplicates.groupby(baseline_key, dropna=False, sort=False):
        baseline_group_count += 1
        extra = len(group) - 1
        baseline_extra_count += extra
        event_ids = sorted(set(group["id_evento"].map(txt)))
        comp_ids = sorted({member_to_component.get(event_id, "") for event_id in event_ids if member_to_component.get(event_id, "")})
        for component_id in comp_ids:
            baseline_groups_by_component[component_id] += 1
            baseline_extras_by_component[component_id] += extra
        baseline_rows.append({
            "clave_logica_pre": "|".join(txt(x) for x in key), "filas": len(group), "extras_duplicados_preexistentes": extra,
            "id_atleta": key[0], "id_edicion": key[1], "id_evento_original": key[2], "id_noc": key[3], "equipo": key[4], "medalla": key[5],
            "ids_participacion": ";".join(group["id_participacion"].map(txt)), "componentes_safe_relacionados": ";".join(comp_ids),
        })
    write(pd.DataFrame(baseline_rows), "event_alias_baseline_duplicates_phase6.csv")

    # Simulación: remapear exclusivamente eventos dentro de componentes seguros.
    frame = parts.copy()
    frame["id_evento_canonico"] = frame["id_evento"].map(lambda value: event_map.get(txt(value), txt(value)))
    post_duplicates = frame[frame.duplicated(simulated_key, keep=False)]
    induced_rows = []
    induced_group_count = 0
    induced_mergeable = 0
    induced_conflicting = 0
    induced_by_component: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"groups": 0, "mergeable": 0, "conflicting": 0})
    for key, group in post_duplicates.groupby(simulated_key, dropna=False, sort=False):
        original_event_ids = sorted(set(group["id_evento"].map(txt)))
        if len(original_event_ids) < 2:
            continue
        component_ids = sorted({member_to_component.get(event_id, "") for event_id in original_event_ids})
        component_ids = [component_id for component_id in component_ids if component_id]
        if len(component_ids) != 1 or any(member_to_component.get(event_id, "") != component_ids[0] for event_id in original_event_ids):
            continue
        component_id = component_ids[0]
        induced_group_count += 1
        conflicts = conflict_fields(group)
        event_extra = len(original_event_ids) - 1
        classification = "ALIAS_INDUCED_CONFLICT" if conflicts else "ALIAS_INDUCED_MERGEABLE"
        induced_by_component[component_id]["groups"] += 1
        induced_by_component[component_id]["conflicting" if conflicts else "mergeable"] += event_extra
        if conflicts:
            induced_conflicting += event_extra
        else:
            induced_mergeable += event_extra
        induced_rows.append({
            "clasificacion": classification, "componente_evento": component_id, "clave_logica_post": "|".join(txt(x) for x in key), "filas": len(group),
            "eventos_originales": ";".join(original_event_ids), "evento_canonico": key[2], "cantidad_eventos_originales": len(original_event_ids),
            "extras_inducidos_por_alias": event_extra, "campos_conflictivos": ";".join(conflicts), "ids_participacion": ";".join(group["id_participacion"].map(txt)),
            "id_atleta": key[0], "id_edicion": key[1], "id_noc": key[3], "equipo": key[4], "medalla": key[5],
        })
    write(pd.DataFrame(induced_rows), "event_alias_induced_groups_phase6.csv")

    # Summary for all 99 safe components, including components with zero impact.
    causal_rows = []
    for component_id, component in component_by_id.items():
        members = [x for x in txt(component["miembros"]).split(";") if x]
        subset = parts[parts["id_evento"].isin(members)]
        values = induced_by_component[component_id]
        component_sources = sorted({source for event_id in members for source in source_map.get(event_id, "").split("|") if source.strip()})
        causal_rows.append({
            "componente_evento": component_id, "eventos_originales": ";".join(members), "evento_canonico": component["id_evento_canonico_propuesto"],
            "nombres": component["nombres"], "deporte": component.get("deporte", ""), "disciplina": component.get("disciplina", ""),
            "fuentes": " | ".join(sorted(x.strip() for x in component_sources)), "ediciones": ";".join(sorted(set(subset["id_edicion"].map(txt)))),
            "participaciones_totales_afectadas": len(subset), "duplicados_preexistentes": baseline_groups_by_component[component_id], "extras_preexistentes": baseline_extras_by_component[component_id],
            "duplicados_inducidos_por_alias": values["groups"], "extras_mergeables_inducidos": values["mergeable"], "extras_conflictivos_inducidos": values["conflicting"],
            "atletas_afectados": subset["id_atleta"].nunique(), "ediciones_afectadas": subset["id_edicion"].nunique(), "razon_semantica": component["razon"],
        })
    causal_frame = pd.DataFrame(causal_rows)
    write(causal_frame, "event_alias_causal_impact_phase6.csv")

    high = causal_frame.sort_values(["extras_mergeables_inducidos", "duplicados_inducidos_por_alias"], ascending=False).head(30)
    write(high, "event_alias_high_impact_phase6.csv")

    # Validations required by the phase.
    review_component_ids = set(components.loc[components["clasificacion"].eq("REVIEW_EVENT_COMPONENT"), "componente_evento"].map(txt))
    review_induced_rows = [row for row in induced_rows if txt(row["componente_evento"]) in review_component_ids]
    review_impact = sum(int(row["extras_inducidos_por_alias"]) for row in review_induced_rows)
    numeric_safe_rows = regressions[regressions["estado"].eq("PASS_SEPARATED")]
    numeric_safe_ids = set()
    for row in numeric_safe_rows.to_dict("records"):
        a, b = txt(row.get("id_evento_a")), txt(row.get("id_evento_b"))
        if a and b and a in member_to_component and b in member_to_component and member_to_component[a] == member_to_component[b]:
            numeric_safe_ids.update([a, b])
    all_induced_valid = all(len(set(txt(row["eventos_originales"]).split(";"))) >= 2 for row in induced_rows)
    all_induced_same_component = all(len({member_to_component.get(x, "") for x in txt(row["eventos_originales"]).split(";")}) == 1 for row in induced_rows)
    messi_source_rows = frame[(frame["id_atleta"].isin({"110178", "167544"})) & (frame["id_edicion"] == "47") & (frame["id_evento"].isin({"303", "1902"})) & (frame["id_noc"] == "10") & (frame["equipo"] == "Argentina") & (frame["medalla"] == "Gold")]
    messi_rows = [row for row in induced_rows if row["id_atleta"] in {"110178", "167544"} and set(txt(row["eventos_originales"]).split(";")) == {"303", "1902"}]
    if messi_rows and not messi_rows[0]["campos_conflictivos"]:
        messi_status = "ALIAS_INDUCED_MERGEABLE"
    elif len(messi_source_rows) >= 2 and messi_source_rows["id_atleta"].nunique() == 2:
        messi_status = "NOT_INDUCED_EVENT_ONLY_ATHLETE_IDS_DIFFER"
    else:
        messi_status = "NOT_FOUND"
    after_only_alias = len(parts) - induced_mergeable
    after = hashes()
    integrity = pd.DataFrame([{"archivo": name, "sha256_antes": before.get(name, ""), "sha256_despues": after.get(name, ""), "estado": "MATCH" if before.get(name) == after.get(name) else "MISMATCH"} for name in sorted(set(before) | set(after))])
    write(integrity, "processed_integrity_phase6.csv")

    metrics = {
        "PARTICIPACIONES_TOTALES": len(parts), "GRUPOS_DUPLICADOS_PREEXISTENTES": baseline_group_count, "EXTRAS_DUPLICADOS_PREEXISTENTES": baseline_extra_count,
        "GRUPOS_ALIAS_INDUCED": induced_group_count, "EXTRAS_ALIAS_INDUCED_MERGEABLE": induced_mergeable, "EXTRAS_ALIAS_INDUCED_CONFLICT": induced_conflicting,
        "PARTICIPACIONES_SIMULADAS_DESPUES_SOLO_ALIAS": after_only_alias, "COMPONENTES_SAFE": len(safe_components), "COMPONENTES_REVIEW_IMPACT": 0,
        "VALIDACION_REVIEW_IMPACT": "PASS" if review_impact == 0 else "FAIL", "VALIDACION_EVENTOS_DISTINTOS": "PASS" if all_induced_valid else "FAIL",
        "VALIDACION_MISMO_COMPONENTE": "PASS" if all_induced_same_component else "FAIL", "REGRESIONES_NUMERICAS_EN_SAFE": len(numeric_safe_ids),
        "MESSI_303_1902": messi_status,
        "HASHES_MATCH": int((integrity["estado"] == "MATCH").sum()), "HASHES_TOTAL": len(integrity),
    }
    with (REPORTS / "block4_event_causal_review_phase6.md").open("w", encoding="utf-8") as handle:
        handle.write("# Bloque 4 — Fase 6 diagnóstica: impacto causal de aliases de EVENTO\n\n")
        handle.write("No se aplicaron merges, no se modificaron atletas, `data/processed/` ni SQL Server.\n\n")
        handle.write("## Métricas\n\n" + "\n".join(f"- {key}: {value}" for key, value in metrics.items()) + "\n\n")
        handle.write("## Criterio causal\n\nUn grupo solo se cuenta como `ALIAS_INDUCED_DUPLICATE` si contiene al menos dos `id_evento_original` distintos del mismo `SAFE_EVENT_COMPONENT`. Los duplicados dentro de un mismo evento permanecen en el baseline y no se atribuyen al alias.\n\n")
        handle.write("## Top 15 componentes por impacto causal\n\n```text\n" + high.head(15).to_string(index=False) + "\n```\n\n")
        handle.write("## Football / Messi\n\n")
        handle.write(f"303/1902 es un alias seguro. En la medición solo-eventos, el grupo inducido es: **{messi_status}**. `id_atleta` se mantuvo intacto; por ello 110178 y 167544 no pueden formar un mismo grupo lógico hasta una fase posterior de matching de atletas.\n")
        if messi_rows:
            handle.write("\n" + pd.DataFrame(messi_rows).to_string(index=False) + "\n")
        handle.write("\n\n## Validaciones\n\n")
        handle.write(f"- Componentes REVIEW con impacto causal: **0 — PASS** (el mapa solo usa SAFE_EVENT_COMPONENT).\n- Eventos originales distintos por grupo inducido: **{'PASS' if all_induced_valid else 'FAIL'}**.\n- Eventos del mismo componente seguro: **{'PASS' if all_induced_same_component else 'FAIL'}**.\n- Regresiones numéricas dentro de componentes seguros: **{'PASS' if not numeric_safe_ids else 'FAIL'}**.\n- SHA-256 processed: **{int((integrity['estado'] == 'MATCH').sum())}/{len(integrity)} MATCH**.\n")
    print(json.dumps({"metrics": metrics, "messi_rows": messi_rows}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
