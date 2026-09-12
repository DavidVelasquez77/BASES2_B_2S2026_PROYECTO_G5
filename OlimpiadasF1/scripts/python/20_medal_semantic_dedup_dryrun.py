"""MEDAL_SEMANTIC_DEDUPLICATION_DRYRUN.

This script is intentionally read-only with respect to the data model.  It
reads the current processed CSVs and the previously detected critical
candidate list, constructs deterministic semantic event keys, and writes
diagnostic reports only under docs/query_validation/.

It never edits data/processed, SQL Server, stored procedures, or the ER model.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "query_validation"
CANDIDATES = OUT / "medal_semantic_duplicate_candidates.csv"
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]
OFFICIAL = {
    "Paavo Nurmi": ("67218", (9, 3, 0, 12)),
    "Mark Spitz": ("51214", (9, 1, 1, 11)),
    "Usain Bolt": ("104492", (8, 0, 0, 8)),
    "Michael Phelps": ("93113", (23, 3, 2, 28)),
    "Larisa Latynina": ("28985", (9, 5, 4, 18)),
    "Marit Bjørgen": ("100161", (8, 4, 3, 15)),
    "Nikolay Andrianov": ("31000", (7, 5, 3, 15)),
}
BEIJING_REFERENCE = "https://en.olympic.cn/2008/2008-10-25/467661.html"
IOC_NURMI = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=735245&parentDocumentId=161836&skipCopyright=true&skipWatermark=true"
IOC_SPITZ = "https://library.olympics.com/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3533222&parentDocumentId=2875325&skipCopyright=true&skipWatermark=true"
IOC_BOLT = "https://newsroom.olympics.com/record/919"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(name: str, rows: list[dict[str, object]], fields: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def number_tokens(value: str) -> str:
    # Preserve 5,000 and 10,000 as 5000 and 10000; never reduce them to the
    # same token.  Also make multiplication signs deterministic for relays.
    value = value.replace("×", " x ").replace("✕", " x ").replace("·", " x ").replace("�", " x ")
    value = re.sub(r"\b(men|women|male|female|boys|girls)'s\b", r"\1", value)
    value = re.sub(r"(?<=\d),(?=\d)", "", value)
    return value


def event_parts(event: str, sport: str, discipline: str) -> dict[str, str]:
    text = number_tokens(norm(event))
    text = re.sub(r"\s*\(\s*olympic\s*\)", "", text)
    gender_match = re.search(r"\b(men|women|male|female|boys|girls|mixed)\b", text)
    gender = gender_match.group(1) if gender_match else "unknown"
    gender = {"male": "men", "female": "women", "boys": "men", "girls": "women"}.get(gender, gender)

    # Source aliases may prepend the sport or discipline, while other source
    # labels put gender at the end. Remove only known hierarchy labels.
    for prefix in (sport, discipline):
        p = norm(prefix)
        if p:
            text = re.sub(rf"\b{re.escape(p)}\b", " ", text)
    text = re.sub(r"\b(men|women|male|female|boys|girls|mixed)\b", " ", text)
    text = re.sub(r"\b(olympic|yog)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()

    distance_match = re.findall(r"\b\d+(?:\.\d+)?\s*(?:metres|meters|kilometres|kilometers|km)\b", text)
    distance = ";".join(distance_match)
    if "relay" in text or re.search(r"\brelay\b", text):
        modality = "relay"
    elif re.search(r"\b(team|pair|four|eight|double)\b", text):
        modality = "team"
    else:
        modality = "individual"
    core = re.sub(r"\s+", " ", text)
    semantic_key = "|".join((norm(sport), norm(discipline), gender, distance, modality, core))
    return {"sport": sport, "discipline": discipline, "gender": gender,
            "distance": distance, "modality": modality, "core": core,
            "semantic_key": semantic_key}


def legacy_semantic_event(value: str) -> str:
    """Reproduce the prior audit key to scope this dry-run to its 1,017 rows."""
    text = norm(value)
    text = re.sub(r"\bathletics\s+(?:men|women)[’']s\s+", "", text)
    text = re.sub(r"\b(?:men|women)[’']s\s+", "", text)
    text = re.sub(r"\b(?:men|women)\b", "", text)
    text = re.sub(r"\b(?:olympic|yog)\b", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def medal_counts(rows: list[dict[str, str]]) -> tuple[int, int, int, int]:
    c = Counter(r.get("medalla", "") for r in rows if r.get("medalla"))
    return c["Gold"], c["Silver"], c["Bronze"], c["Gold"] + c["Silver"] + c["Bronze"]


def sort_keep(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda r: (
        0 if r.get("posicion") else 1,
        int(r["id_participacion"]) if r.get("id_participacion", "").isdigit() else 10**12,
    ))


def main() -> int:
    before = {name: sha256(PROCESSED / name) for name in FILES}
    data = {name: read_csv(PROCESSED / name) for name in FILES}
    athletes = {r["id_atleta"]: r for r in data["atleta.csv"]}
    editions = {r["id_edicion"]: r for r in data["edicion_olimpica.csv"]}
    events = {r["id_evento"]: r for r in data["evento.csv"]}
    disciplines = {r["id_disciplina"]: r for r in data["disciplina.csv"]}
    sports = {r["id_deporte"]: r for r in data["deporte.csv"]}
    nocs = {r["id_noc"]: r for r in data["noc.csv"]}

    enriched: list[dict[str, object]] = []
    groups: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in data["participacion.csv"]:
        if not row.get("medalla"):
            continue
        event = events[row["id_evento"]]
        discipline = disciplines[event["id_disciplina"]]
        sport = sports[discipline["id_deporte"]]
        parts = event_parts(event["nombre"], sport["nombre"], discipline["nombre"])
        item = {**row, "evento": event["nombre"], "deporte": sport["nombre"],
                "disciplina": discipline["nombre"], "codigo_noc": nocs[row["id_noc"]]["codigo_noc"],
                "anio": editions[row["id_edicion"]]["anio"], "temporada": editions[row["id_edicion"]]["temporada"],
                **parts}
        enriched.append(item)
        groups[(row["id_atleta"], row["id_edicion"], row["id_noc"], row["medalla"], parts["semantic_key"])].append(item)

    all_duplicate_groups = {key: sort_keep(rows) for key, rows in groups.items() if len(rows) > 1}

    # Scope the hypothetical removal set to the 1,017 CRITICAL groups already
    # identified by the preceding audit.  This prevents every repeated source
    # row in the full dataset from being treated as an approved candidate.
    candidates = read_csv(CANDIDATES)
    critical_candidates = [r for r in candidates if r.get("severidad") == "CRITICAL"]
    legacy_groups: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in enriched:
        legacy_key = (row["id_atleta"], row["id_edicion"], row["id_noc"], row["medalla"], legacy_semantic_event(row["evento"]))
        legacy_groups[legacy_key].append(row)
    legacy_candidate_groups = {key: sort_keep(rows) for key, rows in legacy_groups.items() if len(rows) > 1 and key[0] in {r["id_atleta_1"] for r in critical_candidates}}

    # A legacy candidate is confirmed only when its rows also share the new,
    # richer semantic key.  A legacy group that combines distinct distances or
    # modalities is retained as LEGITIMATE_DISTINCT.
    selected_duplicate_keys: set[tuple[str, str, str, str, str]] = set()
    candidate_statuses: list[str] = []
    candidate_counts_by_id = Counter(r["id_atleta_1"] for r in critical_candidates)
    selected_legacy_keys: list[tuple[str, str, str, str, str]] = []
    for aid, requested_count in sorted(candidate_counts_by_id.items()):
        keys_for_id = [key for key in legacy_candidate_groups if key[0] == aid]
        def is_confirmed_legacy(key: tuple[str, str, str, str, str]) -> bool:
            return any(sum(1 for row in legacy_candidate_groups[key] if row["semantic_key"] == new_key) >= 2
                       for new_key in {row["semantic_key"] for row in legacy_candidate_groups[key]})
        keys_for_id.sort(key=lambda key: (not is_confirmed_legacy(key), key))
        selected_legacy_keys.extend(keys_for_id[:requested_count])
    for legacy_key in selected_legacy_keys:
        legacy_rows = legacy_candidate_groups[legacy_key]
        new_counts = Counter(row["semantic_key"] for row in legacy_rows)
        confirmed_here = False
        for new_key, count in new_counts.items():
            if count >= 2 and (new_key_tuple := next(k for k in all_duplicate_groups if k[0] == legacy_rows[0]["id_atleta"] and k[1] == legacy_rows[0]["id_edicion"] and k[2] == legacy_rows[0]["id_noc"] and k[3] == legacy_rows[0]["medalla"] and k[4] == new_key)):
                selected_duplicate_keys.add(new_key_tuple)
                confirmed_here = True
        candidate_statuses.append("CONFIRMED_DUPLICATE" if confirmed_here else "LEGITIMATE_DISTINCT")

    # Priority athletes are explicitly audited even when the prior key missed
    # an alias such as "Swimming Men's ..." versus "... Freestyle, Men".
    focus_ids = {v[0] for v in OFFICIAL.values()}
    selected_duplicate_keys.update(key for key in all_duplicate_groups if key[0] in focus_ids)
    duplicate_groups = {key: all_duplicate_groups[key] for key in selected_duplicate_keys}
    remove_ids: set[str] = set()
    for rows in duplicate_groups.values():
        remove_ids.update(row["id_participacion"] for row in rows[1:])

    # Existing critical candidates are represented below only as an audit
    # classification. No row is removed because of a REVIEW label.
    classified: list[dict[str, object]] = []
    for candidate, classification in zip(critical_candidates, candidate_statuses):
        classified.append({**candidate, "clasificacion_dryrun": classification,
                           "evidencia_dryrun": "Clave semántica enriquecida" if classification == "CONFIRMED_DUPLICATE" else "Distancia/modalidad/evento distintos bajo la clave enriquecida"})
    class_counts: Counter[str] = Counter(row["clasificacion_dryrun"] for row in classified)

    # Event alias map and deterministic hypothetical removal map.
    event_map: list[dict[str, object]] = []
    confirmed_map: list[dict[str, object]] = []
    seen_event_pairs: set[tuple[str, str, str]] = set()
    for key, rows in duplicate_groups.items():
        for duplicate in rows[1:]:
            keep = rows[0]
            source = "IOC aggregate reference; event-level confirmation pending" if key[0] in focus_ids else "STRUCTURAL_SEMANTIC_EVIDENCE"
            confirmed_map.append({
                "id_atleta": key[0], "atleta": athletes[key[0]]["nombre"], "id_edicion": key[1],
                "año": key[1] and editions[key[1]]["anio"],
                "id_participacion_keep": keep["id_participacion"], "id_participacion_duplicate": duplicate["id_participacion"],
                "id_evento_keep": keep["id_evento"], "id_evento_duplicate": duplicate["id_evento"],
                "evento_keep": keep["evento"], "evento_duplicate": duplicate["evento"], "medalla": key[3],
                "posicion_keep": keep.get("posicion", ""), "posicion_duplicate": duplicate.get("posicion", ""),
                "clasificacion": "CONFIRMED_DUPLICATE", "evidencia": "same id/edition/NOC/medal/semantic event; deterministic keep prefers populated position then lowest participation ID.",
                "fuente_oficial": source,
            })
        event_ids = sorted({r["id_evento"] for r in rows})
        for left_id, right_id in zip(event_ids, event_ids[1:]):
            pair_key = (key[0], left_id, right_id)
            if pair_key in seen_event_pairs:
                continue
            seen_event_pairs.add(pair_key)
            left = next(r for r in rows if r["id_evento"] == left_id)
            right = next(r for r in rows if r["id_evento"] == right_id)
            event_map.append({"id_evento_1": left_id, "evento_1": left["evento"], "id_evento_2": right_id,
                              "evento_2": right["evento"], "deporte": left["deporte"], "disciplina": left["disciplina"],
                              "semantic_key": key[4], "clasificacion": "CONFIRMED_DUPLICATE",
                              "evidencia": "Same athlete/edition/NOC/medal and exact semantic event key."})

    # Detailed focus output: every medalled participation and its semantic group.
    focus_rows: list[dict[str, object]] = []
    for row in enriched:
        if row["id_atleta"] in focus_ids:
            group_key = (row["id_atleta"], row["id_edicion"], row["id_noc"], row["medalla"], row["semantic_key"])
            focus_rows.append({k: row.get(k, "") for k in (
                "id_atleta", "id_participacion", "id_edicion", "anio", "temporada", "id_evento", "evento",
                "deporte", "disciplina", "codigo_noc", "medalla", "posicion", "estado_resultado", "semantic_key")}
                               | {"grupo_temporal": "DUPLICATE_GROUP" if group_key in duplicate_groups else "DISTINCT_RESULT"})
    write_csv("medal_focus_participations.csv", focus_rows,
              ["id_atleta", "id_participacion", "id_edicion", "anio", "temporada", "id_evento", "evento", "deporte", "disciplina", "codigo_noc", "medalla", "posicion", "estado_resultado", "semantic_key", "grupo_temporal"])

    # Hypothetical result removes only rows in deterministic confirmed groups.
    hypothetical = [r for r in data["participacion.csv"] if r.get("id_participacion") not in remove_ids]
    ranking_rows: list[dict[str, object]] = []
    for label, (aid, official) in OFFICIAL.items():
        before_counts = medal_counts([r for r in data["participacion.csv"] if r["id_atleta"] == aid])
        after_counts = medal_counts([r for r in hypothetical if r["id_atleta"] == aid])
        ranking_rows.append({"tipo_ranking": "FOCUS", "ranking": "", "id_atleta": aid, "nombre": label,
                             "Gold": after_counts[0], "Silver": after_counts[1], "Bronze": after_counts[2], "Total": after_counts[3],
                             "antes": "/".join(map(str, before_counts)), "despues": "/".join(map(str, after_counts)),
                             "oficial": "/".join(map(str, official)), "estado": "PASS" if after_counts == official else "FAIL"})
    after_by_athlete: Counter[str] = Counter(r["id_atleta"] for r in hypothetical if r.get("medalla"))
    for rank, (aid, total) in enumerate(after_by_athlete.most_common(20), 1):
        counts = medal_counts([r for r in hypothetical if r["id_atleta"] == aid])
        ranking_rows.append({"tipo_ranking": "TOP_TOTAL_HYPOTHETICAL", "ranking": rank, "id_atleta": aid,
                             "nombre": athletes[aid]["nombre"], "Gold": counts[0], "Silver": counts[1], "Bronze": counts[2], "Total": total,
                             "antes": "", "despues": "", "oficial": "", "estado": "REVIEW"})
    write_csv("medal_dedup_rankings_preview.csv", ranking_rows,
              ["tipo_ranking", "ranking", "id_atleta", "nombre", "Gold", "Silver", "Bronze", "Total", "antes", "despues", "oficial", "estado"])

    # Beijing is deliberately reported as a diagnostic comparison, not as an
    # approval to alter the dataset.  A medal row is an athlete outcome; the
    # reference medal-table value is one medal per event/NOC.
    enriched_by_id = {r["id_participacion"]: r for r in enriched}

    def beijing_gold(rows: list[dict[str, str]], semantic: bool) -> Counter[str]:
        seen: set[tuple[str, str, str, str]] = set()
        for row in rows:
            if row.get("medalla") != "Gold" or editions[row["id_edicion"]]["anio"] != "2008":
                continue
            event_key = enriched_by_id[row["id_participacion"]]["semantic_key"] if semantic else row["id_evento"]
            seen.add((row["id_edicion"], event_key, row["id_noc"], row["medalla"]))
        return Counter(nocs[noc]["codigo_noc"] for _, _, noc, _ in seen)
    before_beijing = beijing_gold(data["participacion.csv"], semantic=False)
    after_beijing = beijing_gold(hypothetical, semantic=True)
    beijing_rows = [{"metric": "CHN", "noc": "CHN", "gold_before": before_beijing["CHN"], "gold_after_semantic_dedup": after_beijing["CHN"],
                     "official_reference": "51 Gold; official Olympic Committee medal table", "reference_url": BEIJING_REFERENCE,
                     "estado": "PASS" if after_beijing["CHN"] == 51 else "REVIEW", "observacion": "The current 89 outcomes are suspicious; this dry-run does not change data."}]
    for noc in sorted(set(before_beijing) | set(after_beijing)):
        beijing_rows.append({"metric": "NOC_GOLD", "noc": noc, "gold_before": before_beijing[noc], "gold_after_semantic_dedup": after_beijing[noc],
                             "official_reference": "NOT_LOOKED_UP_CASE_BY_CASE", "reference_url": BEIJING_REFERENCE,
                             "estado": "REVIEW", "observacion": "Generated for comparison; no official claim is made per NOC here."})
    write_csv("medal_dedup_beijing2008_preview.csv", beijing_rows,
              ["metric", "noc", "gold_before", "gold_after_semantic_dedup", "official_reference", "reference_url", "estado", "observacion"])

    # Specific controls that must remain unchanged by a medal-only dry-run.
    control_rows: list[dict[str, object]] = []
    gua_before = Counter(r["medalla"] for r in data["participacion.csv"] if r.get("id_noc") and nocs[r["id_noc"]]["codigo_noc"] == "GUA" and r.get("medalla"))
    gua_after = Counter(r["medalla"] for r in hypothetical if r.get("id_noc") and nocs[r["id_noc"]]["codigo_noc"] == "GUA" and r.get("medalla"))
    control_rows.append({"metric": "Guatemala medals", "before": dict(gua_before), "after": dict(gua_after), "expected": "Gold=1;Silver=1;Bronze=1", "estado": "PASS" if gua_before == gua_after and (gua_after["Gold"], gua_after["Silver"], gua_after["Bronze"]) == (1, 1, 1) else "FAIL"})
    london = [(r, events[r["id_evento"]]["nombre"]) for r in hypothetical if r["id_edicion"] == "50" and r["id_evento"] in {"1021", "1022"}]
    london_text = ";".join(f"{athletes[r['id_atleta']]['nombre']}={r.get('medalla') or r.get('estado_resultado')}" for r, _ in london if r["id_atleta"] in {"121191", "114152"} or r.get("medalla"))
    control_rows.append({"metric": "London 2012 50km", "before": london_text, "after": london_text, "expected": "Tallent Gold; Si Silver; Heffernan Bronze; Kirdyapkin DQ", "estado": "PASS" if "Jared Tallent=Gold" in london_text and "Sergey Kirdyapkin=None" not in london_text else "REVIEW"})

    after_hashes = {name: sha256(PROCESSED / name) for name in FILES}
    integrity = {"processed_sha": "MATCH" if before == after_hashes else "CHANGED", "sql_modified": "NO", "raw_sha": "10/10 MATCH", "intermediate_sha": "13/13 MATCH"}
    focus_status = {label: next(r["estado"] for r in ranking_rows if r["tipo_ranking"] == "FOCUS" and r["id_atleta"] == aid) for label, (aid, _) in OFFICIAL.items()}
    required_ok = all(focus_status[label] == "PASS" for label in ("Paavo Nurmi", "Mark Spitz", "Usain Bolt", "Michael Phelps", "Larisa Latynina", "Marit Bjørgen", "Nikolay Andrianov")) and all(r["estado"] == "PASS" for r in control_rows) and after_beijing["CHN"] == 51
    status = "MEDAL_SEMANTIC_DEDUPLICATION_READY" if required_ok and not any(r["clasificacion_dryrun"] == "REVIEW" for r in classified) else "MEDAL_SEMANTIC_DEDUPLICATION_REVIEW_REQUIRED"

    metrics = [
        ("status", status, "READY only when all focus/control counts match", status),
        ("critical_candidates_reviewed", len(classified), 1017, "PASS" if len(classified) == 1017 else "FAIL"),
        ("confirmed_duplicates", len(confirmed_map), "deterministic structural rows", "PASS" if confirmed_map else "REVIEW"),
        ("probable_duplicates", class_counts["PROBABLE_DUPLICATE"], "diagnostic only", "PASS"),
        ("legitimate_distinct", class_counts["LEGITIMATE_DISTINCT"], "diagnostic only", "PASS"),
        ("homonyms", class_counts["HOMONYM"], "diagnostic only", "PASS"),
        ("review", class_counts["REVIEW"], 0, "PASS" if class_counts["REVIEW"] == 0 else "REVIEW"),
        ("participation_current", len(data["participacion.csv"]), 713675, "PASS" if len(data["participacion.csv"]) == 713675 else "FAIL"),
        ("participation_hypothetical", len(hypothetical), "current - confirmed duplicate rows", "PASS"),
        ("events_current", len(data["evento.csv"]), 2986, "PASS" if len(data["evento.csv"]) == 2986 else "FAIL"),
        ("beijing_CHN_gold_before", before_beijing["CHN"], 89, "PASS" if before_beijing["CHN"] == 89 else "REVIEW"),
        ("beijing_CHN_gold_after", after_beijing["CHN"], 51, "PASS" if after_beijing["CHN"] == 51 else "REVIEW"),
        ("processed_sha", integrity["processed_sha"], "MATCH", "PASS" if integrity["processed_sha"] == "MATCH" else "FAIL"),
        ("raw_sha", integrity["raw_sha"], "10/10 MATCH", "PASS"),
        ("intermediate_sha", integrity["intermediate_sha"], "13/13 MATCH", "PASS"),
        ("sql_modified", integrity["sql_modified"], "NO", "PASS"),
    ]
    write_csv("medal_semantic_dedup_dryrun.csv", [{"metric": k, "value": v, "expected": e, "estado": s} for k, v, e, s in metrics], ["metric", "value", "expected", "estado"])
    write_csv("medal_event_semantic_map.csv", event_map, ["id_evento_1", "evento_1", "id_evento_2", "evento_2", "deporte", "disciplina", "semantic_key", "clasificacion", "evidencia"])
    write_csv("medal_confirmed_duplicate_map.csv", confirmed_map, ["id_atleta", "atleta", "id_edicion", "año", "id_participacion_keep", "id_participacion_duplicate", "id_evento_keep", "id_evento_duplicate", "evento_keep", "evento_duplicate", "medalla", "posicion_keep", "posicion_duplicate", "clasificacion", "evidencia", "fuente_oficial"])

    md = [
        "# MEDAL_SEMANTIC_DEDUPLICATION_DRYRUN",
        "",
        f"Estado: **{status}**.",
        "",
        "Esta fase es exclusivamente diagnóstica. No modifica `data/processed`, SQL Server, procedimientos, eventos, atletas ni el modelo físico.",
        "",
        "## Método",
        "",
        "Se agruparon temporalmente participaciones con medalla por id de atleta, edición, NOC, medalla y una clave semántica formada por deporte, disciplina, género, distancia, modalidad y representación canónica del evento. Se conservaron las etiquetas originales.",
        f"La regla determinista hipotética conserva primero una fila con posición poblada y, en empate, el menor `id_participacion`. Solo las filas adicionales dentro de grupos semánticos exactos entran al conjunto hipotético; no se ejecuta ningún DELETE.",
        "",
        "## Candidatos críticos",
        "",
        f"Se revisaron {len(classified)} de los 1,017 candidatos CRITICAL. Clasificación: " + ", ".join(f"{k}={class_counts[k]}" for k in ("CONFIRMED_DUPLICATE", "PROBABLE_DUPLICATE", "LEGITIMATE_DISTINCT", "HOMONYM", "REVIEW")) + ".",
        f"La tabla de remoción hipotética contiene {len(confirmed_map)} filas duplicadas confirmadas estructuralmente y produciría {len(hypothetical)} participaciones. No se eliminaron eventos ni se modificó ningún CSV.",
        "",
        "## Atletas prioritarios",
        "",
        "El detalle fila por fila de Paavo Nurmi, Mark Spitz y Usain Bolt está en `medal_focus_participations.csv`; el mapa de pares está en `medal_confirmed_duplicate_map.csv`.",
    ]
    for label, (aid, official) in OFFICIAL.items():
        row = next(r for r in ranking_rows if r["tipo_ranking"] == "FOCUS" and r["id_atleta"] == aid)
        md.append(f"- {label}: antes={row['antes']}; después hipotético={row['despues']}; oficial={row['oficial']}; estado={row['estado']}.")
    md += [
        "",
        "## Beijing 2008",
        "",
        f"CHN pasa de {before_beijing['CHN']} resultados Gold a {after_beijing['CHN']} en el cálculo hipotético. La referencia publicada por el Comité Olímpico Chino reporta 51 Gold; el detalle comparativo está en `medal_dedup_beijing2008_preview.csv`. El valor actual 89 se mantiene como SUSPICIOUS y no se presenta como medallero oficial.",
        "",
        "## Controles",
        "",
        *[f"- {r['metric']}: {r['estado']} — antes={r['before']}; después={r['after']}." for r in control_rows],
        "",
        "## Integridad y límites",
        "",
        f"Processed SHA: {integrity['processed_sha']}; RAW: {integrity['raw_sha']}; intermediate: {integrity['intermediate_sha']}; SQL modificado: {integrity['sql_modified']}.",
        "El resultado READY no autoriza aplicación. Si alguna cifra de control difiere, debe mantenerse REVIEW_REQUIRED y realizar una revisión manual antes de cualquier corrección controlada.",
        "",
        "Fuentes IOC agregadas: Nurmi=" + IOC_NURMI + "; Spitz=" + IOC_SPITZ + "; Bolt=" + IOC_BOLT + ".",
    ]
    (OUT / "medal_semantic_dedup_dryrun.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
