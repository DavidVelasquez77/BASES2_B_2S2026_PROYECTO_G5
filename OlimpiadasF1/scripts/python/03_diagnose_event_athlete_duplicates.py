"""Diagnóstico reproducible del caso Messi y duplicados semánticos del Bloque 4.

Esta fase es deliberadamente de solo diagnóstico: lee los CSV existentes, escribe
reportes en docs/consolidation/ y nunca escribe data/processed/ ni SQL Server.
"""
from __future__ import annotations

import hashlib
import itertools
import re
from collections import defaultdict
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


def s(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def norm_text(value: object) -> str:
    value = unidecode(s(value)).lower()
    value = value.replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def name_tokens(value: object) -> set[str]:
    return {token for token in norm_text(value).split() if len(token) > 1}


def event_gender(value: object) -> str:
    key = norm_text(value)
    if re.search(r"\b(women|woman|female|girls|girl)\b", key):
        return "WOMEN"
    if re.search(r"\b(men|man|male|boys|boy)\b", key):
        return "MEN"
    if re.search(r"\bmixed\b", key):
        return "MIXED"
    return "UNKNOWN"


def event_signature(value: object) -> str:
    """Clave conservadora para detectar aliases, no una transformación final."""
    key = norm_text(value)
    # norm_text separa la apóstrofe de Men's/Women's; volver a unir
    # semánticamente evita tratar la s posesiva como un token distinto.
    key = re.sub(r"\b(men|women) s\b", r"\1", key)
    key = re.sub(r"\b(olympic|olympics)\b", " ", key)
    key = re.sub(r"\b(mens|men)\b", "men", key)
    key = re.sub(r"\b(womens|women)\b", "women", key)
    tokens = [token for token in key.split() if token]
    # La firma usa tokens únicos ordenados para detectar reordenamientos y
    # repeticiones sintácticas como "Football Men's Football".
    return " ".join(sorted(set(tokens)))


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


def load_sources() -> dict[str, pd.DataFrame]:
    return {
        "f1_bios": read_csv(CLEANED / "fuente1_clean_bios.csv"),
        "f1_locs": read_csv(CLEANED / "fuente1_clean_bios_locs.csv"),
        "f1_raw_bios": read_csv(CLEANED / "fuente1_raw_bios.csv"),
        "f1_results": read_csv(CLEANED / "fuente1_raw_results.csv"),
        "f2": read_csv(CLEANED / "fuente2_athlete_events.csv"),
        "f3": read_csv(CLEANED / "fuente3_olympics_dataset.csv"),
        "f4": read_csv(CLEANED / "fuente4_datalab_export.csv"),
    }


def current_matching() -> pd.DataFrame:
    return read_csv(MATCHING / "athlete_matches.csv")


def diagnose_messi(sources: dict[str, pd.DataFrame], matching: pd.DataFrame, parts: pd.DataFrame, events: pd.DataFrame, editions: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    locs = sources["f1_locs"].set_index("athlete_id", drop=False)
    event_lookup = events.set_index("id_evento").to_dict("index")
    current_part = parts[parts["id_atleta"].isin({"110178", "167544"})].copy()
    edition_year = editions.set_index("id_edicion")["anio"].to_dict()
    current_part["anio"] = current_part["id_edicion"].map(edition_year).fillna("")
    current_part = current_part[current_part["anio"] == "2008"]
    match_index = {(s(row.get("fuente")), s(row.get("id_original"))): row for row in matching.to_dict("records")}

    source_rows = [
        ("fuente1", "fuente1_raw_results.csv", sources["f1_results"], "athlete_id", "111386", "Lionel Messi"),
        ("fuente2", "fuente2_athlete_events.csv", sources["f2"], "ID", "79053", "Lionel Andres Messi Cuccittini"),
    ]
    for source, filename, frame, id_col, original_id, expected_name in source_rows:
        found = frame[frame[id_col].astype(str) == original_id]
        if found.empty:
            continue
        for _, row in found.iterrows():
            if source == "fuente1":
                bio = locs.loc[original_id] if original_id in locs.index else {}
                birth_date = s(bio.get("born_date", "")) if hasattr(bio, "get") else ""
                name = s(row.get("nombre_competencia")) or expected_name
                event_original = s(row.get("event"))
                sport = ""
                discipline = s(row.get("discipline"))
                team = s(row.get("equipo"))
                year, season = s(row.get("year")), s(row.get("season"))
                medal, position, state = s(row.get("medalla")), s(row.get("posicion")), s(row.get("estado_resultado"))
                noc = s(row.get("noc_codigo"))
            else:
                bio = {}
                birth_date = ""
                name = s(row.get("name")) or expected_name
                event_original = s(row.get("event"))
                sport = s(row.get("sport"))
                discipline = sport
                team = s(row.get("equipo"))
                year, season = s(row.get("year")), s(row.get("season"))
                medal, position = s(row.get("medalla")), ""
                state = ""
                noc = s(row.get("noc_codigo"))
            match_row = match_index.get((source, original_id), {})
            global_id = s(match_row.get("id_atleta_global"))
            current = current_part[current_part["id_atleta"] == global_id]
            current = current[(current["equipo"] == team) | (current["equipo"] == "")]
            current = current[current["medalla"] == medal]
            current_event_id = s(current.iloc[0]["id_evento"]) if not current.empty else ""
            current_event_name = s(event_lookup.get(current_event_id, {}).get("nombre"))
            reason = s(match_row.get("criterio_match"))
            if source == "fuente1" and reason:
                reason = "Registro Fuente 1 quedó como identidad base; el otro nombre no igualó el alias auxiliar exacto."
            elif source == "fuente2":
                reason = "El matching actual exige alias normalizado exacto; 'Lionel Andrs Messi Cuccittini' no coincide con 'Lionel Messi' y no existe etapa contextual por tokens."
            records.append({
                "fuente": source, "archivo": f"data/intermediate/cleaned/{filename}", "id_original": original_id,
                "nombre_original": name, "id_atleta_global_actual": global_id, "fecha_nacimiento": birth_date,
                "noc": noc, "equipo": team, "anio": year, "temporada": season, "deporte": sport,
                "disciplina": discipline, "evento_original": event_original, "id_evento_actual": current_event_id,
                "evento_actual": current_event_name, "medalla": medal, "posicion": position,
                "estado_resultado": state, "estado_matching_actual": s(match_row.get("estado")),
                "tipo_match_actual": s(match_row.get("tipo_match")), "razon_no_fusion": reason,
            })
    return pd.DataFrame(records)


def event_diagnostics(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates: list[dict[str, object]] = []
    events = events.copy()
    events["genero"] = events["nombre"].map(event_gender)
    events["firma_alias"] = events["nombre"].map(event_signature)
    events["nombre_norm"] = events["nombre"].map(norm_text)
    for group_key, group in events.groupby(["nombre_deporte", "nombre_disciplina", "genero"], dropna=False):
        if len(group) < 2 or group_key[2] == "UNKNOWN":
            continue
        rows = list(group.to_dict("records"))
        for left, right in itertools.combinations(rows, 2):
            if left["nombre"] == right["nombre"]:
                continue
            sig_same = left["firma_alias"] == right["firma_alias"]
            similarity = SequenceMatcher(None, left["nombre_norm"], right["nombre_norm"]).ratio()
            token_left, token_right = set(left["firma_alias"].split()), set(right["firma_alias"].split())
            containment = bool(token_left and token_right and (token_left <= token_right or token_right <= token_left))
            if not (sig_same or (containment and similarity >= 0.72)):
                continue
            auto = "YES" if sig_same else "NO"
            rule = "misma firma de tokens: minúsculas, puntuación, Olympic(s), posesivo y reordenamiento seguro" if sig_same else "contención de tokens con similitud; requiere revisión"
            reason = "Mismo deporte, disciplina y género; firma equivalente sin conflicto textual evidente." if sig_same else "Candidato textual contextual; la firma no es idéntica y no se propone auto-merge."
            candidates.append({
                "id_evento_a": s(left["id_evento"]), "nombre_a": left["nombre"],
                "id_evento_b": s(right["id_evento"]), "nombre_b": right["nombre"],
                "deporte": left["nombre_deporte"], "disciplina": left["nombre_disciplina"],
                "genero_a": left["genero"], "genero_b": right["genero"],
                "similitud": round(similarity, 6), "regla_detectada": rule,
                "auto_merge_candidate": auto, "razon": reason,
            })
    candidate_frame = pd.DataFrame(candidates)
    if candidate_frame.empty:
        resolution = pd.DataFrame(columns=["evento_origen", "evento_canonico", "regla_aplicada", "confianza", "evidencia"])
    else:
        auto_rows = candidate_frame[candidate_frame["auto_merge_candidate"] == "YES"]
        resolution = pd.DataFrame([
            {
                "evento_origen": max(s(row["id_evento_a"]), s(row["id_evento_b"]), key=lambda x: int(x or 0)),
                "evento_canonico": min(s(row["id_evento_a"]), s(row["id_evento_b"]), key=lambda x: int(x or 0)),
                "regla_aplicada": row["regla_detectada"], "confianza": "ALTA",
                "evidencia": f"{row['nombre_a']} <-> {row['nombre_b']} | {row['deporte']} / {row['disciplina']} / {row['genero_a']}",
            }
            for _, row in auto_rows.iterrows()
        ])
    return candidate_frame, resolution


def athlete_diagnostics(atletas: pd.DataFrame, parts: pd.DataFrame, events: pd.DataFrame, editions: pd.DataFrame, nocs: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    events["firma_alias"] = events["nombre"].map(event_signature)
    event_map = events.set_index("id_evento")["firma_alias"].to_dict()
    event_name_map = events.set_index("id_evento")["nombre"].to_dict()
    edition_map = editions.set_index("id_edicion").apply(lambda r: f"{r['anio']} {r['temporada']}", axis=1).to_dict()
    noc_map = nocs.set_index("id_noc")["codigo_noc"].to_dict()
    context: defaultdict[str, dict[tuple[str, ...], list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for row in parts.to_dict("records"):
        key = (
            edition_map.get(s(row["id_edicion"]), ""), noc_map.get(s(row["id_noc"]), s(row["id_noc"])),
            s(row["equipo"]), event_map.get(s(row["id_evento"]), ""), s(row["medalla"]),
        )
        context[s(row["id_atleta"])][key].append({"evento": event_name_map.get(s(row["id_evento"]), ""), "medalla": s(row["medalla"]), "id_participacion": s(row["id_participacion"])})
    athlete_data = {}
    inverted: defaultdict[str, set[str]] = defaultdict(set)
    for row in atletas.to_dict("records"):
        identifier = s(row["id_atleta"])
        tokens = name_tokens(row["nombre"])
        athlete_data[identifier] = {"row": row, "tokens": tokens, "context": context.get(identifier, {})}
        for token in tokens:
            inverted[token].add(identifier)
    candidate_keys: list[tuple[str, str]] = []
    for identifier, data in athlete_data.items():
        tokens = data["tokens"]
        if len(tokens) < 2:
            continue
        postings = [inverted[token] for token in tokens if token in inverted]
        if not postings:
            continue
        possible = set.intersection(*postings)
        for other in possible:
            if int(other or 0) <= int(identifier or 0):
                continue
            other_tokens = athlete_data[other]["tokens"]
            if tokens <= other_tokens or other_tokens <= tokens or SequenceMatcher(None, norm_text(data["row"]["nombre"]), norm_text(athlete_data[other]["row"]["nombre"])).ratio() >= 0.86:
                candidate_keys.append((identifier, other))
    context_pair_count: defaultdict[tuple[tuple[str, ...], tuple[str, ...]], set[tuple[str, str]]] = defaultdict(set)
    preliminary = []
    for left_id, right_id in candidate_keys:
        left, right = athlete_data[left_id], athlete_data[right_id]
        shared_keys = set(left["context"]) & set(right["context"])
        compatible_keys = []
        for key in shared_keys:
            left_medal, right_medal = key[4], key[4]
            # The key already requires equality when both medals are present.
            compatible_keys.append(key)
        for key in compatible_keys:
            short_tokens = tuple(sorted(min(left["tokens"], right["tokens"], key=len)))
            context_pair_count[(short_tokens, key)].add((left_id, right_id))
        preliminary.append((left_id, right_id, compatible_keys))
    rows: list[dict[str, object]] = []
    for left_id, right_id, compatible_keys in preliminary:
        left, right = athlete_data[left_id], athlete_data[right_id]
        left_row, right_row = left["row"], right["row"]
        date_a, date_b = s(left_row.get("fecha_nacimiento")), s(right_row.get("fecha_nacimiento"))
        date_compatible = not date_a or not date_b or date_a == date_b
        for key in compatible_keys:
            short_tokens = tuple(sorted(min(left["tokens"], right["tokens"], key=len)))
            ambiguous_context = len(context_pair_count[(short_tokens, key)]) > 1
            decision = "AUTO_MERGE_CANDIDATE" if date_compatible and not ambiguous_context else "AMBIGUOUS"
            reason = "Nombre corto contenido en nombre largo + misma edición, NOC, equipo, alias de evento y medalla; candidato único." if decision == "AUTO_MERGE_CANDIDATE" else "Existe relación de nombre/contexto, pero requiere revisión por más de un candidato o conflicto de fecha."
            rows.append({
                "id_atleta_a": left_id, "nombre_a": left_row["nombre"], "id_atleta_b": right_id,
                "nombre_b": right_row["nombre"], "fecha_a": date_a, "fecha_b": date_b,
                "edicion": key[0], "noc": key[1], "equipo": key[2],
                "evento_a": left["context"][key][0]["evento"], "evento_b": right["context"][key][0]["evento"],
                "similitud_nombre": round(SequenceMatcher(None, norm_text(left_row["nombre"]), norm_text(right_row["nombre"])).ratio(), 6),
                "compatibilidad_contexto": "ALTA" if date_compatible else "FECHA_CONFLICTIVA",
                "decision_sugerida": decision, "razon": reason,
            })
    return pd.DataFrame(rows)


def main() -> int:
    before = processed_hashes()
    sources = load_sources()
    atletas = read_csv(PROCESSED / "atleta.csv")
    parts = read_csv(PROCESSED / "participacion.csv")
    editions = read_csv(PROCESSED / "edicion_olimpica.csv")
    events = read_csv(PROCESSED / "evento.csv")
    disciplines = read_csv(PROCESSED / "disciplina.csv")
    sports = read_csv(PROCESSED / "deporte.csv")
    nocs = read_csv(PROCESSED / "noc.csv")
    events = events.merge(disciplines[["id_disciplina", "id_deporte", "nombre"]].rename(columns={"nombre": "nombre_disciplina"}), on=["id_disciplina"], how="left")
    events = events.merge(sports[["id_deporte", "nombre"]].rename(columns={"nombre": "nombre_deporte"}), on=["id_deporte"], how="left")
    matching = current_matching()
    messi = diagnose_messi(sources, matching, parts, events, editions)
    write(messi, "messi_duplicate_diagnostic.csv")
    event_candidates, event_resolution = event_diagnostics(events)
    write(event_candidates, "event_alias_candidates.csv", ["id_evento_a", "nombre_a", "id_evento_b", "nombre_b", "deporte", "disciplina", "genero_a", "genero_b", "similitud", "regla_detectada", "auto_merge_candidate", "razon"])
    write(event_resolution, "event_alias_resolution_proposed.csv")
    athlete_candidates = athlete_diagnostics(atletas, parts, events, editions, nocs)
    write(athlete_candidates, "athlete_contextual_duplicate_candidates.csv")
    after = processed_hashes()
    unchanged = before == after
    messi_rows = messi.to_dict("records")
    high = int((athlete_candidates["decision_sugerida"] == "AUTO_MERGE_CANDIDATE").sum()) if not athlete_candidates.empty else 0
    ambiguous = int((athlete_candidates["decision_sugerida"] == "AMBIGUOUS").sum()) if not athlete_candidates.empty else 0
    event_auto = len(event_resolution)
    top_events = event_candidates.sort_values(["auto_merge_candidate", "similitud"], ascending=[False, False]).head(12) if not event_candidates.empty else event_candidates
    top_athletes = athlete_candidates.sort_values("similitud_nombre", ascending=False).head(12) if not athlete_candidates.empty else athlete_candidates
    lines = [
        "# Diagnóstico controlado — duplicados semánticos del Bloque 4", "",
        "## Alcance", "", "Esta ejecución solo diagnostica candidatos y no sobrescribe `data/processed/`, no modifica SQL y no ejecuta carga, reset, UPDATE, DELETE, TRUNCATE o DROP.", "",
        f"- Hashes de los CSV procesados antes/después del diagnóstico: **{'idénticos' if unchanged else 'CAMBIARON'}**.",
        f"- Conteos observados sin regeneración: ATLETA **{len(atletas)}**, EVENTO **{len(events)}**, PARTICIPACION **{len(parts)}**.", "",
        "## Causa concreta del caso Messi", "",
        "El registro de Fuente 1 (`Lionel Messi`, athlete_id 111386) quedó como identidad base. El registro de Fuente 2 (`Lionel Andrs Messi Cuccittini`, ID 79053) quedó `UNMATCHED` porque el matching existente exige alias normalizado exacto; no implementa contención de tokens ni una segunda etapa contextual para nombres cortos/largos.", "",
        "En eventos, la lógica existente usa `(id_disciplina, norm_aux(event_source))` como clave. Por eso `Football, Men (Olympic)` y `Football Men's Football` permanecen separados aunque comparten Football, género masculino, edición 2008, ARG, equipo Argentina y Gold.", "",
        "## Resultados del diagnóstico", "",
        f"- Pares de atletas candidatos con contexto compartido: **{len(athlete_candidates)}**.",
        f"- Pares de atletas sugeridos para auto-merge contextual: **{high}**.",
        f"- Pares de atletas ambiguos: **{ambiguous}**.",
        f"- Pares de eventos candidatos: **{len(event_candidates)}**.",
        f"- Aliases de eventos propuestos para auto-merge: **{event_auto}**.", "",
        "## Regla propuesta", "",
        "Event aliases: misma jerarquía deporte-disciplina, mismo género inferible, firma de tokens equivalente después de normalizar minúsculas, puntuación, posesivos, Olympic(s), repeticiones y reordenamientos seguros; no fusionar si existe conflicto semántico.", "",
        "Athletes: tokens significativos del nombre corto contenidos en el nombre largo, más misma edición, NOC, equipo, alias de evento y medalla; fecha igual o ausente en una sola fuente; un único candidato. Fechas distintas, NOC/equipo incompatibles o múltiples candidatos conservan `AMBIGUOUS`.", "",
        "La fase siguiente debe actualizar la lógica general, ejecutar regresiones y regenerar datos solo después de aprobación externa de este diagnóstico.", "",
        "## Ejemplos de candidatos de atletas", "",
    ]
    if not top_athletes.empty:
        lines.append("```text")
        lines.append(top_athletes.to_string(index=False))
        lines.append("```")
    else:
        lines.append("No se encontraron pares con contexto compartido.")
    lines.extend(["", "## Ejemplos de aliases de eventos", ""])
    if not top_events.empty:
        lines.append("```text")
        lines.append(top_events.to_string(index=False))
        lines.append("```")
    else:
        lines.append("No se encontraron aliases candidatos.")
    lines.extend(["", "## Riesgo", "", f"El universo contiene **{len(athlete_candidates)}** pares candidatos; **{high}** cumplen la regla propuesta y **{ambiguous}** quedan ambiguos. Por el volumen y la posibilidad de homónimos entre fuentes, el riesgo estimado de aplicar un auto-merge masivo sin una segunda revisión de unicidad por fuente es **ALTO**. La salida actual solo propone candidatos; no fusiona ninguno. Los pares ambiguos no se fusionan automáticamente.", "", "## Archivos generados", "", "- `messi_duplicate_diagnostic.csv`", "- `event_alias_candidates.csv`", "- `event_alias_resolution_proposed.csv`", "- `athlete_contextual_duplicate_candidates.csv`", "- `block4_duplicate_review.md`"])
    (REPORTS / "block4_duplicate_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Messi diagnostic rows: {len(messi)}")
    print(f"Athlete contextual candidates: {len(athlete_candidates)}; auto-merge candidates: {high}; ambiguous: {ambiguous}")
    print(f"Event alias candidates: {len(event_candidates)}; proposed auto-merge aliases: {event_auto}")
    print(f"Processed unchanged: {unchanged}")
    return 0 if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
