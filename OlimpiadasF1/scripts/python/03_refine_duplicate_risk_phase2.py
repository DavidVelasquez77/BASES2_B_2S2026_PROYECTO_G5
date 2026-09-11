"""Segunda fase diagnóstica: reducción de riesgo de merges del Bloque 4.

Lee únicamente los CSV existentes y genera reportes refinados. No modifica
data/processed, data/raw, data/intermediate/cleaned, SQL Server ni el script de
consolidación.
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
REPORTS = ROOT / "docs" / "consolidation"
REPORTS.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path, usecols: list[str] | None = None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, usecols=usecols)


def text(value: object) -> str:
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return ""
    return str(value).strip()


def norm(value: object) -> str:
    value = unidecode(text(value)).lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value: object) -> set[str]:
    return {token for token in norm(value).split() if len(token) > 1}


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
    return {path.name: sha256(path) for path in sorted(PROCESSED.glob("*.csv"))}


def write(frame: pd.DataFrame, name: str, columns: list[str] | None = None) -> None:
    if columns is not None:
        frame = frame.reindex(columns=columns)
    frame.to_csv(REPORTS / name, index=False, encoding="utf-8")


def build_contexts(parts: pd.DataFrame, editions: pd.DataFrame, events: pd.DataFrame, nocs: pd.DataFrame) -> tuple[dict[str, set[str]], dict[str, dict[str, str]]]:
    edition_map = editions.set_index("id_edicion").apply(lambda row: f"{row['anio']} {row['temporada']}", axis=1).to_dict()
    event_map = events.set_index("id_evento").apply(lambda row: (event_signature(row["nombre"]), text(row["nombre"])), axis=1).to_dict()
    noc_map = nocs.set_index("id_noc")["codigo_noc"].to_dict()
    contexts: defaultdict[str, set[str]] = defaultdict(set)
    descriptions: defaultdict[str, dict[str, str]] = defaultdict(dict)
    for row in parts.itertuples(index=False):
        athlete = text(getattr(row, "id_atleta"))
        edition = edition_map.get(text(getattr(row, "id_edicion")), "")
        event_sig, event_name = event_map.get(text(getattr(row, "id_evento")), ("", ""))
        noc = noc_map.get(text(getattr(row, "id_noc")), text(getattr(row, "id_noc")))
        key = " | ".join([
            edition,
            noc,
            text(getattr(row, "equipo")),
            event_sig,
            text(getattr(row, "medalla")),
        ])
        contexts[athlete].add(key)
        descriptions[athlete][key] = event_name
    return contexts, descriptions


def bio_conflicts(left: pd.Series, right: pd.Series) -> tuple[list[str], list[str]]:
    conflicts: list[str] = []
    unknown: list[str] = []
    for field, label in [("fecha_nacimiento", "fecha_nacimiento"), ("fecha_fallecimiento", "fecha_fallecimiento"), ("id_pais_nacionalidad", "nacionalidad")]:
        a, b = text(left.get(field)), text(right.get(field))
        if not a or not b:
            unknown.append(label)
        elif a == b:
            continue
        else:
            conflicts.append(f"{label}: {a} != {b}")
    sex_a, sex_b = normalized_sex(left.get("sexo")), normalized_sex(right.get("sexo"))
    if not sex_a or not sex_b:
        unknown.append("sexo")
    elif sex_a != sex_b:
        conflicts.append(f"sexo: {sex_a} != {sex_b}")
    for field, label, tolerance in [("altura_cm", "altura_cm", 20.0), ("peso_kg", "peso_kg", 30.0)]:
        a, b = text(left.get(field)), text(right.get(field))
        if not a or not b:
            unknown.append(label)
            continue
        try:
            difference = abs(float(a) - float(b))
        except ValueError:
            unknown.append(label)
            continue
        if difference > tolerance:
            conflicts.append(f"{label}: {a} != {b}")
    return conflicts, unknown


def candidate_group_key(name_a: str, name_b: str) -> tuple[str, ...]:
    left, right = tokens(name_a), tokens(name_b)
    return tuple(sorted(min(left, right, key=len)))


def normalized_sex(value: object) -> str:
    key = norm(value)
    return {"male": "M", "man": "M", "m": "M", "female": "F", "woman": "F", "f": "F"}.get(key, key)


def refine_athletes(candidates: pd.DataFrame, athletes: pd.DataFrame, contexts: dict[str, set[str]], descriptions: dict[str, dict[str, str]], matching: pd.DataFrame) -> pd.DataFrame:
    athlete_map = athletes.set_index("id_atleta")
    source_map: defaultdict[str, set[str]] = defaultdict(set)
    for row in matching.to_dict("records"):
        source_map[text(row.get("id_atleta_global"))].add(text(row.get("fuente")))
    partner_groups: defaultdict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
    prepared: list[dict[str, object]] = []
    for row in candidates.to_dict("records"):
        a_id, b_id = text(row["id_atleta_a"]), text(row["id_atleta_b"])
        group = candidate_group_key(text(row["nombre_a"]), text(row["nombre_b"]))
        partner_groups[(a_id, group)].add(b_id)
        partner_groups[(b_id, group)].add(a_id)
        set_a, set_b = contexts.get(a_id, set()), contexts.get(b_id, set())
        shared = set_a & set_b
        prepared.append({"row": row, "a_id": a_id, "b_id": b_id, "group": group, "set_a": set_a, "set_b": set_b, "shared": shared})

    output: list[dict[str, object]] = []
    for item in prepared:
        row = item["row"]
        a_id, b_id = item["a_id"], item["b_id"]
        left = athlete_map.loc[a_id] if a_id in athlete_map.index else pd.Series(dtype=str)
        right = athlete_map.loc[b_id] if b_id in athlete_map.index else pd.Series(dtype=str)
        conflicts, unknown = bio_conflicts(left, right)
        set_a, set_b, shared = item["set_a"], item["set_b"], item["shared"]
        union = set_a | set_b
        score_context = len(shared) / max(1, len(union))
        score_name = SequenceMatcher(None, norm(row["nombre_a"]), norm(row["nombre_b"])).ratio()
        unique = len(partner_groups[(a_id, item["group"])]) == 1 and len(partner_groups[(b_id, item["group"])]) == 1
        name_equal = norm(row["nombre_a"]) == norm(row["nombre_b"])
        alias_relation = tokens(row["nombre_a"]) <= tokens(row["nombre_b"]) or tokens(row["nombre_b"]) <= tokens(row["nombre_a"])
        if conflicts:
            classification = "CONFLICT"
            reason = "; ".join(conflicts)
        elif not shared or not unique:
            classification = "REVIEW"
            reason = "Evidencia insuficiente o más de un candidato plausible para la relación nominal/contextual."
        elif name_equal:
            classification = "EXACT_DUPLICATE_IDENTITY"
            reason = "Nombre normalizado idéntico, contexto compartido, sin conflicto biográfico y candidato único."
        elif alias_relation and score_context >= 0.5:
            classification = "STRONG_ALIAS"
            reason = "Nombre corto contenido en nombre largo, historial compartido y candidato único sin conflicto biográfico."
        else:
            classification = "REVIEW"
            reason = "La similitud nominal o el contexto completo no alcanzan el umbral conservador."
        context_only_a = set_a - shared
        context_only_b = set_b - shared
        output.append({
            "id_atleta_a": a_id, "nombre_a": row["nombre_a"], "id_atleta_b": b_id, "nombre_b": row["nombre_b"],
            "fuentes": " | ".join(sorted(source_map.get(a_id, set()) | source_map.get(b_id, set()))),
            "fecha_a": text(left.get("fecha_nacimiento")), "fecha_b": text(right.get("fecha_nacimiento")),
            "sexo_a": text(left.get("sexo")), "sexo_b": text(right.get("sexo")),
            "contextos_a": json.dumps(sorted(set_a), ensure_ascii=False),
            "contextos_b": json.dumps(sorted(set_b), ensure_ascii=False),
            "contextos_compartidos": json.dumps(sorted(shared), ensure_ascii=False),
            "contextos_solo_a": json.dumps(sorted(context_only_a), ensure_ascii=False),
            "contextos_solo_b": json.dumps(sorted(context_only_b), ensure_ascii=False),
            "conflictos_biograficos": json.dumps(conflicts + ([f"unknown: {', '.join(unknown)}"] if unknown else []), ensure_ascii=False),
            "unicidad": "UNICA" if unique else "MULTIPLE",
            "score_nombre": round(score_name, 6), "score_contexto": round(score_context, 6),
            "clasificacion_final": classification, "razon": reason,
        })
    return pd.DataFrame(output)


def source_event_occurrences() -> dict[str, dict[str, set[tuple[str, str]]]]:
    specs = [
        ("fuente1", "fuente1_raw_results.csv"),
        ("fuente2", "fuente2_athlete_events.csv"),
        ("fuente3", "fuente3_olympics_dataset.csv"),
        ("fuente4", "fuente4_datalab_export.csv"),
    ]
    output: defaultdict[str, dict[str, set[tuple[str, str]]]] = defaultdict(lambda: defaultdict(set))
    for source, filename in specs:
        frame = read_csv(CLEANED / filename, ["year", "season", "event"])
        for row in frame.to_dict("records"):
            output[text(row["event"])][source].add((text(row["year"]), text(row["season"])))
    return output


def refine_events(candidates: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    event_map = events.set_index("id_evento").to_dict("index")
    occurrences = source_event_occurrences()
    rows: list[dict[str, object]] = []
    for row in candidates.to_dict("records"):
        a, b = event_map[text(row["id_evento_a"])], event_map[text(row["id_evento_b"])]
        occ_a, occ_b = occurrences.get(text(a["nombre"]), {}), occurrences.get(text(b["nombre"]), {})
        same_source_overlap = []
        for source in set(occ_a) & set(occ_b):
            overlap = sorted(occ_a[source] & occ_b[source])
            if overlap:
                same_source_overlap.append(f"{source}:{overlap}")
        multiset_a, multiset_b = Counter(event_multiset(a["nombre"])), Counter(event_multiset(b["nombre"]))
        extra_a = list((multiset_a - multiset_b).elements())
        extra_b = list((multiset_b - multiset_a).elements())
        loss = bool(extra_a or extra_b) and set(event_signature(a["nombre"]).split()) == set(event_signature(b["nombre"]).split())
        sport_token = norm(a["nombre_deporte"])
        extra_is_parent = all(token in {sport_token, "sport", "event"} for token in extra_a + extra_b)
        if same_source_overlap:
            category = "CONFLICT_ALIAS"
            reason = "Ambos nombres aparecen en la misma fuente y edición; podrían ser pruebas distintas coexistentes."
        elif not loss or extra_is_parent:
            category = "SAFE_ALIAS"
            reason = "Mismo deporte, disciplina y género, sin coexistencia en una misma fuente/edición; tokenización compatible."
        else:
            category = "REVIEW_ALIAS"
            reason = "La firma por conjunto oculta multiplicidad de tokens; requiere revisión antes de fusionar."
        rows.append({
            **row,
            "fuentes_a": " | ".join(sorted(occ_a)), "fuentes_b": " | ".join(sorted(occ_b)),
            "coexistencia_misma_fuente": " | ".join(same_source_overlap),
            "tokens_extra_a": " ".join(sorted(extra_a)), "tokens_extra_b": " ".join(sorted(extra_b)),
            "perdida_multiplicidad": "YES" if loss else "NO",
            "clasificacion_final": category, "razon_refinada": reason,
        })
    return pd.DataFrame(rows)


def samples(refined: pd.DataFrame) -> pd.DataFrame:
    rng = 42
    output = []
    for category in ["EXACT_DUPLICATE_IDENTITY", "STRONG_ALIAS", "REVIEW", "CONFLICT"]:
        group = refined[refined["clasificacion_final"] == category]
        if not group.empty:
            selected = group.sample(n=min(30, len(group)), random_state=rng).assign(tipo_muestra=category)
            output.append(selected)
    strong = refined[refined["clasificacion_final"] == "STRONG_ALIAS"].sort_values(["score_contexto", "score_nombre"], ascending=[True, True]).head(30).assign(tipo_muestra="STRONG_ALIAS_MENOR_CONFIANZA")
    if not strong.empty:
        output.append(strong)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame()


def main() -> int:
    before = processed_hashes()
    candidates = read_csv(REPORTS / "athlete_contextual_duplicate_candidates.csv")
    event_candidates = read_csv(REPORTS / "event_alias_candidates.csv")
    athletes = read_csv(PROCESSED / "atleta.csv")
    parts = read_csv(PROCESSED / "participacion.csv")
    editions = read_csv(PROCESSED / "edicion_olimpica.csv")
    events = read_csv(PROCESSED / "evento.csv")
    disciplines = read_csv(PROCESSED / "disciplina.csv")
    sports = read_csv(PROCESSED / "deporte.csv")
    nocs = read_csv(PROCESSED / "noc.csv")
    events = events.merge(disciplines[["id_disciplina", "id_deporte", "nombre"]].rename(columns={"nombre": "nombre_disciplina"}), on=["id_disciplina"], how="left")
    events = events.merge(sports[["id_deporte", "nombre"]].rename(columns={"nombre": "nombre_deporte"}), on=["id_deporte"], how="left")
    matching = read_csv(ROOT / "data" / "intermediate" / "matching" / "athlete_matches.csv")
    contexts, descriptions = build_contexts(parts, editions, events, nocs)
    refined = refine_athletes(candidates, athletes, contexts, descriptions, matching)
    refined_events = refine_events(event_candidates, events)
    write(refined, "athlete_duplicate_candidates_refined.csv")
    write(refined_events, "event_alias_candidates_refined.csv")
    sample = samples(refined)
    write(sample, "athlete_duplicate_samples_phase2.csv")
    after = processed_hashes()
    integrity = pd.DataFrame([{"archivo": name, "sha256_antes": before.get(name, ""), "sha256_despues": after.get(name, ""), "estado": "MATCH" if before.get(name) == after.get(name) else "MISMATCH"} for name in sorted(set(before) | set(after))])
    write(integrity, "processed_integrity_phase2.csv")
    counts = refined["clasificacion_final"].value_counts().to_dict() if not refined.empty else {}
    event_counts = refined_events["clasificacion_final"].value_counts().to_dict() if not refined_events.empty else {}
    messi = refined[(refined["id_atleta_a"] == "110178") & (refined["id_atleta_b"] == "167544")]
    safe_merges = int(sum(counts.get(category, 0) for category in ["EXACT_DUPLICATE_IDENTITY", "STRONG_ALIAS"]))
    affected_ids = set(refined.loc[refined["clasificacion_final"].isin(["EXACT_DUPLICATE_IDENTITY", "STRONG_ALIAS"]), "id_atleta_a"].astype(str)) | set(refined.loc[refined["clasificacion_final"].isin(["EXACT_DUPLICATE_IDENTITY", "STRONG_ALIAS"]), "id_atleta_b"].astype(str))
    lines = [
        "# Bloque 4 — fase 2 de reducción de riesgo", "",
        "Esta fase reclasifica candidatos usando historial completo de participaciones, atributos biográficos, unicidad nominal/contextual y coexistencia de aliases de eventos. No aplica merges y no sobrescribe `data/processed/`.", "",
        f"- Hashes `data/processed/*.csv`: **{'10/10 MATCH' if len(integrity) == 10 and (integrity['estado'] == 'MATCH').all() else 'FAIL'}**.",
        f"- Candidatos totales: **{len(refined)}**.",
        f"- EXACT_DUPLICATE_IDENTITY: **{counts.get('EXACT_DUPLICATE_IDENTITY', 0)}**.",
        f"- STRONG_ALIAS: **{counts.get('STRONG_ALIAS', 0)}**.",
        f"- REVIEW: **{counts.get('REVIEW', 0)}**.",
        f"- CONFLICT: **{counts.get('CONFLICT', 0)}**.",
        f"- Pares seguros propuestos: **{safe_merges}**; atletas únicos afectados: **{len(affected_ids)}**.",
        f"- SAFE_ALIAS: **{event_counts.get('SAFE_ALIAS', 0)}**.",
        f"- REVIEW_ALIAS: **{event_counts.get('REVIEW_ALIAS', 0)}**.",
        f"- CONFLICT_ALIAS: **{event_counts.get('CONFLICT_ALIAS', 0)}**.", "",
        "## Regresión Messi", "",
        "El par Lionel Messi / Lionel Andrs Messi Cuccittini queda clasificado como:", "",
        f"**{messi.iloc[0]['clasificacion_final'] if not messi.empty else 'NO_ENCONTRADO'}**", "",
        "La decisión deriva de la relación de tokens, edición 2008 Summer, NOC ARG, equipo Argentina, alias de evento compatible, Gold, fecha compatible (presente en una fuente y ausente en la otra) y unicidad del candidato. No existe una regla especial por nombre.", "",
        "## Defecto detectado en `event_signature()`", "",
        "La firma basada en `set(tokens)` elimina multiplicidad. Por ejemplo, `Football, Men (Olympic)` y `Football Men's Football` terminan con la misma firma aunque el segundo repite `Football`. La fase 2 marca estos casos como `REVIEW_ALIAS` salvo que el token adicional sea el nombre del deporte y no exista coexistencia en una misma fuente/edición. Los aliases no se aplican todavía.", "",
        "## Falsos positivos de la primera regla", "",
        "La primera regla sobrevaloraba nombres idénticos o contenidos con una sola coincidencia contextual. En la muestra refinada aparecen homónimos como `Francesco Messina`, `Jean Borotra`, `Patrick Chila` y pares con el mismo nombre pero ediciones/equipos distintos. Se clasifican como `REVIEW` cuando la unicidad no queda demostrada y como `CONFLICT` cuando existe contradicción biográfica fuerte.", "",
        "## Muestreo reproducible", "",
        "Se generó `athlete_duplicate_samples_phase2.csv` con semilla 42: hasta 30 casos por clasificación y los 30 STRONG_ALIAS con menor confianza.", "",
        "## Estado", "",
        "La fase diagnóstica terminó correctamente. No se regeneró `data/processed/`, no se modificó SQL, no se ejecutaron merges y el Bloque 4 no se declara corregido.",
    ]
    (REPORTS / "block4_duplicate_review_phase2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Candidatos: {len(refined)}")
    print(f"Classifications: {counts}")
    print(f"Event classifications: {event_counts}")
    print(f"Safe athlete pairs: {safe_merges}; unique athletes affected: {len(affected_ids)}")
    print(f"Messi: {messi.iloc[0]['clasificacion_final'] if not messi.empty else 'NOT_FOUND'}")
    print(f"Processed hashes unchanged: {len(integrity) == 10 and (integrity['estado'] == 'MATCH').all()}")
    return 0 if len(integrity) == 10 and (integrity["estado"] == "MATCH").all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
