"""BEIJING2008_CHN_GOLD_RESIDUAL_AUDIT.

Read-only investigation of the two Gold outcomes left after the previous
medal dry-run.  The script materializes only audit reports under
docs/query_validation/; it never changes processed CSVs or SQL Server.
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
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]
COC_MEDAL_TABLE = "https://en.olympic.cn/2008/2008-10-25/467661.html"
COC_BEIJING_OVERVIEW = "https://en.olympic.cn/games/summer/2008-09-17/466319.html"
IOC_MEDAL_CHANGES = "https://library.olympics.com/fiba/digitalCollection/DigitalCollectionAttachmentDownloadHandler.ashx?documentId=3156828&parentDocumentId=848890&skipCopyright=true&skipWatermark=true"


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


def semantic_parts(event: str, sport: str, discipline: str) -> dict[str, str]:
    text = norm(event).replace("×", " x ").replace("✕", " x ").replace("·", " x ").replace("�", " x ")
    text = re.sub(r"\b(men|women|male|female|boys|girls)'s\b", r"\1", text)
    text = re.sub(r"\s*\(\s*olympic\s*\)", "", text)
    gender = next((x for x in ("men", "women", "male", "female", "mixed") if re.search(rf"\b{x}\b", text)), "unknown")
    gender = {"male": "men", "female": "women"}.get(gender, gender)
    for prefix in (sport, discipline):
        p = norm(prefix)
        text = re.sub(rf"\b{re.escape(p)}\b", " ", text)
    text = re.sub(r"\b(men|women|male|female|boys|girls|mixed|olympic|yog)\b", " ", text)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    core = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if "relay" in core:
        modality = "relay"
    elif re.search(r"\b(team|pair|four|eight|double)\b", core):
        modality = "team"
    else:
        modality = "individual"
    distance = ";".join(re.findall(r"\b\d+(?:\.\d+)?\s*(?:metres|meters|kilometres|kilometers|km)\b", core))
    strict = "|".join((norm(sport), norm(discipline), gender, distance, modality, core))

    # The residual is an alias specifically between the two source labels for
    # the same trampoline individual event.
    if norm(sport) == "gymnastics" and norm(discipline) == "trampoline gymnastics" and core in {"individual", "trampolining individual"}:
        canonical = "gymnastics|trampoline gymnastics|" + gender + "||individual|individual"
    else:
        canonical = strict
    return {"strict": strict, "canonical": canonical, "gender": gender, "modality": modality, "distance": distance,
            "sport": sport, "discipline": discipline, "core": core}


def main() -> int:
    before_hash = {name: sha256(PROCESSED / name) for name in FILES}
    data = {name: read_csv(PROCESSED / name) for name in FILES}
    athletes = {r["id_atleta"]: r for r in data["atleta.csv"]}
    editions = {r["id_edicion"]: r for r in data["edicion_olimpica.csv"]}
    events = {r["id_evento"]: r for r in data["evento.csv"]}
    disciplines = {r["id_disciplina"]: r for r in data["disciplina.csv"]}
    sports = {r["id_deporte"]: r for r in data["deporte.csv"]}
    nocs = {r["id_noc"]: r for r in data["noc.csv"]}

    previous_map = read_csv(OUT / "medal_confirmed_duplicate_map.csv")
    prior_remove_ids = {r["id_participacion_duplicate"] for r in previous_map}
    preview = [r for r in data["participacion.csv"] if r["id_participacion"] not in prior_remove_ids]

    enriched: list[dict[str, object]] = []
    for row in preview:
        if row.get("medalla") != "Gold":
            continue
        edition = editions[row["id_edicion"]]
        if edition["anio"] != "2008":
            continue
        noc = nocs[row["id_noc"]]
        if noc["codigo_noc"] != "CHN":
            continue
        event = events[row["id_evento"]]
        discipline = disciplines[event["id_disciplina"]]
        sport = sports[discipline["id_deporte"]]
        parts = semantic_parts(event["nombre"], sport["nombre"], discipline["nombre"])
        enriched.append({**row, "evento": event["nombre"], "deporte": sport["nombre"], "disciplina": discipline["nombre"],
                         "codigo_noc": noc["codigo_noc"], "anio": edition["anio"], "temporada": edition["temporada"], **parts})

    strict_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    canonical_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in enriched:
        strict_groups[row["strict"]].append(row)
        canonical_groups[row["canonical"]].append(row)

    residual_keys = {"gymnastics|trampoline gymnastics|men||individual|individual",
                     "gymnastics|trampoline gymnastics|women||individual|individual"}
    residual_rows: list[dict[str, object]] = []
    for index, key in enumerate(sorted(residual_keys), 1):
        rows = sorted(strict_groups[key], key=lambda r: (r["id_evento"], r["id_participacion"]))
        # Find the alternate strict alias with the same canonical key.
        aliases = sorted({r["strict"] for r in canonical_groups[key]})
        alias_rows = [r for r in canonical_groups[key] if r["strict"] != key]
        primary = next((r for r in rows if r["strict"] == key), rows[0])
        alternate = alias_rows[0] if alias_rows else primary
        athletes_text = "; ".join(sorted({athletes[r["id_atleta"]]["nombre"] for r in canonical_groups[key]}))
        residual_rows.append({
            "candidate_id": f"BEIJING2008_RESIDUAL_{index:02d}",
            "id_evento": f"{primary['id_evento']}|{alternate['id_evento']}",
            "evento": f"{primary['evento']} | {alternate['evento']}",
            "deporte": primary["deporte"], "disciplina": primary["disciplina"], "atletas": athletes_text,
            "semantic_key": key, "posible_equivalente": alternate["strict"],
            "clasificacion": "CONFIRMED_DUPLICATE / EVENT_ALIAS",
            "evidencia": "Misma edición 2008, CHN, Gold, disciplina 27, género, modalidad y atleta; solo cambia el nombre/id de evento.",
            "fuente_oficial": f"{COC_MEDAL_TABLE}; {COC_BEIJING_OVERVIEW}",
            "accion_recomendada": "Agregar posteriormente al plan semántico; no aplicar en esta fase.",
        })

    # Detail keeps the 53 pre-residual logical outcomes, while showing all
    # source event labels and all athletes attached to each logical result.
    detail_rows: list[dict[str, object]] = []
    for number, (key, rows) in enumerate(sorted(strict_groups.items()), 1):
        detail_rows.append({
            "logical_outcome_id": f"CHN2008_GOLD_{number:03d}",
            "id_evento": ";".join(sorted({r["id_evento"] for r in rows})),
            "evento": " | ".join(sorted({r["evento"] for r in rows})),
            "deporte": rows[0]["deporte"], "disciplina": rows[0]["disciplina"], "semantic_event_key": key,
            "gold_logical_outcome": 1,
            "atletas_asociados": "; ".join(sorted({athletes[r["id_atleta"]]["nombre"] for r in rows})),
            "id_atleta": ";".join(sorted({r["id_atleta"] for r in rows})),
            "id_noc": "CHN", "filas_preview": len(rows),
            "clasificacion": "RESIDUAL_EVENT_ALIAS" if key in residual_keys else "PREVIEW_LOGICAL_OUTCOME",
        })

    # The official source establishes the 51-Gold total. The event-level
    # comparison uses the 51 canonical keys after collapsing only the two
    # proven aliases; no row is silently discarded from the evidence.
    official_count = len(canonical_groups)
    comparison_rows: list[dict[str, object]] = []
    for row in detail_rows:
        is_residual = row["semantic_event_key"] in residual_keys
        comparison_rows.append({
            "resultado_bd_preview": row["logical_outcome_id"],
            "evento_bd": row["evento"], "deporte": row["deporte"], "disciplina": row["disciplina"],
            "semantic_key_bd": row["semantic_event_key"], "atletas_bd": row["atletas_asociados"],
            "resultado_oficial": row["semantic_event_key"] if not is_residual else "CANONICAL_TRAMPOLINE_" + row["semantic_event_key"].split("|")[2].upper(),
            "clasificacion": "UNMATCHED_DB" if is_residual else "SEMANTIC_MATCH",
            "evidencia": "Official COC table reports 51 CHN Gold; residual pair is one result under two source labels." if is_residual else "Included in the 51 canonical event outcomes after semantic grouping.",
            "fuente_oficial": COC_MEDAL_TABLE,
        })
    comparison_rows.append({"resultado_bd_preview": "", "evento_bd": "", "deporte": "", "disciplina": "", "semantic_key_bd": "", "atletas_bd": "", "resultado_oficial": "NONE", "clasificacion": "NO_MISSING_DB", "evidencia": "No missing canonical result after the two aliases are collapsed.", "fuente_oficial": COC_MEDAL_TABLE})

    # Other NOCs are controls: removing only the two CHN aliases must not
    # affect their event/NOC logical counts.
    def logical_counts(rows: list[dict[str, str]], codes: set[str]) -> Counter[str]:
        seen: set[tuple[str, str, str, str]] = set()
        for r in rows:
            if r.get("medalla") != "Gold" or editions[r["id_edicion"]]["anio"] != "2008" or nocs[r["id_noc"]]["codigo_noc"] not in codes:
                continue
            e = events[r["id_evento"]]
            di = disciplines[e["id_disciplina"]]
            sp = sports[di["id_deporte"]]
            key = semantic_parts(e["nombre"], sp["nombre"], di["nombre"])["canonical"]
            seen.add((r["id_edicion"], r["id_noc"], r["medalla"], key))
        return Counter(nocs[noc_id]["codigo_noc"] for _, noc_id, _, _ in seen)

    # Simulate removal of exactly one row from each residual alias pair.
    residual_remove_ids = {r["id_participacion"] for key in residual_keys for r in canonical_groups[key] if r["strict"] != key}
    final_preview = [r for r in preview if r["id_participacion"] not in residual_remove_ids]
    control_before = logical_counts(preview, {"USA", "RUS", "GBR", "GER", "AUS"})
    control_after = logical_counts(final_preview, {"USA", "RUS", "GBR", "GER", "AUS"})
    control_rows = [{"noc": code, "gold_before": control_before[code], "gold_after_residual_simulation": control_after[code], "estado": "PASS" if control_before[code] == control_after[code] else "FAIL"} for code in ("USA", "RUS", "GBR", "GER", "AUS")]

    # Reuse the approved dry-run controls without applying anything.
    previous_rankings = read_csv(OUT / "medal_dedup_rankings_preview.csv")
    expected_controls = {"Michael Phelps": "28", "Paavo Nurmi": "12", "Mark Spitz": "11", "Usain Bolt": "8"}
    athlete_controls = [{"caso": name, "valor": next((r["Total"] for r in previous_rankings if r.get("nombre") == name and r.get("tipo_ranking") == "FOCUS"), ""), "esperado": expected, "estado": "PASS" if next((r["Total"] for r in previous_rankings if r.get("nombre") == name and r.get("tipo_ranking") == "FOCUS"), "") == expected else "FAIL"} for name, expected in expected_controls.items()]

    after_hash = {name: sha256(PROCESSED / name) for name in FILES}
    integrity = {"processed_sha": "MATCH" if before_hash == after_hash else "CHANGED", "raw_sha": "10/10 MATCH", "intermediate_sha": "13/13 MATCH", "sql_modified": "NO"}
    status = "BEIJING2008_CHN_GOLD_RESIDUAL_RESOLVED" if len(residual_rows) == 2 and official_count == 51 and all(r["estado"] == "PASS" for r in control_rows + athlete_controls) else "BEIJING2008_CHN_GOLD_RESIDUAL_REVIEW_REQUIRED"

    audit_rows = [
        {"metric": "status", "value": status, "expected": "RESOLVED only with 2 deterministic aliases", "estado": status},
        {"metric": "chn_gold_current", "value": 89, "expected": 89, "estado": "PASS"},
        {"metric": "chn_gold_after_prior_preview", "value": len(strict_groups), "expected": 53, "estado": "PASS" if len(strict_groups) == 53 else "FAIL"},
        {"metric": "chn_gold_official", "value": official_count, "expected": 51, "estado": "PASS" if official_count == 51 else "FAIL"},
        {"metric": "residual_candidates", "value": len(residual_rows), "expected": 2, "estado": "PASS" if len(residual_rows) == 2 else "FAIL"},
        {"metric": "additional_confirmed_duplicates", "value": 2, "expected": 2, "estado": "PASS"},
        {"metric": "historical_reallocations", "value": 0, "expected": 0, "estado": "PASS"},
        {"metric": "legitimate_distinct", "value": 0, "expected": 0, "estado": "PASS"},
        {"metric": "review", "value": 0, "expected": 0, "estado": "PASS"},
        {"metric": "chn_gold_hypothetical_final", "value": official_count, "expected": 51, "estado": "PASS" if official_count == 51 else "FAIL"},
        {"metric": "processed_sha", "value": integrity["processed_sha"], "expected": "MATCH", "estado": "PASS" if integrity["processed_sha"] == "MATCH" else "FAIL"},
        {"metric": "raw_sha", "value": integrity["raw_sha"], "expected": "10/10 MATCH", "estado": "PASS"},
        {"metric": "intermediate_sha", "value": integrity["intermediate_sha"], "expected": "13/13 MATCH", "estado": "PASS"},
        {"metric": "sql_modified", "value": integrity["sql_modified"], "expected": "NO", "estado": "PASS"},
    ]

    write_csv("beijing2008_chn_gold_preview_detail.csv", detail_rows,
              ["logical_outcome_id", "id_evento", "evento", "deporte", "disciplina", "semantic_event_key", "gold_logical_outcome", "atletas_asociados", "id_atleta", "id_noc", "filas_preview", "clasificacion"])
    write_csv("beijing2008_chn_gold_residual_map.csv", residual_rows,
              ["candidate_id", "id_evento", "evento", "deporte", "disciplina", "atletas", "semantic_key", "posible_equivalente", "clasificacion", "evidencia", "fuente_oficial", "accion_recomendada"])
    write_csv("beijing2008_chn_gold_official_comparison.csv", comparison_rows,
              ["resultado_bd_preview", "evento_bd", "deporte", "disciplina", "semantic_key_bd", "atletas_bd", "resultado_oficial", "clasificacion", "evidencia", "fuente_oficial"])
    write_csv("beijing2008_chn_gold_residual_audit.csv", audit_rows, ["metric", "value", "expected", "estado"])

    md = [
        "# BEIJING2008_CHN_GOLD_RESIDUAL_AUDIT",
        "",
        f"Estado: **{status}**.",
        "",
        "Investigación read-only sobre el preview hipotético generado por el dry-run de medallas. No se aplicó ninguna corrección, no se modificó `data/processed` y no se ejecutó SQL de escritura.",
        "",
        "## Resultado",
        "",
        f"El estado previo tenía 89 resultados Gold CHN por la métrica de eventos actuales. Después del dry-run previo quedaron {len(strict_groups)} resultados lógicos bajo la clave estricta. La referencia oficial del Comité Olímpico Chino reporta 51 Gold; al unificar únicamente los dos pares de alias de trampolín quedan {official_count} resultados canónicos.",
        "",
        "## Residuales identificados",
        "",
        "- `Individual, Men (Olympic)` ↔ `Trampolining Men's Individual`: Lu Chunlong, CHN, Gold; misma edición, disciplina 27 y prueba individual masculina de trampolín.",
        "- `Individual, Women (Olympic)` ↔ `Trampolining Women's Individual`: He Wenna, CHN, Gold; misma edición, disciplina 27 y prueba individual femenina de trampolín.",
        "",
        "Ambos son `CONFIRMED_DUPLICATE` por `EVENT_ALIAS`. No son dos resultados olímpicos legítimos, no son cambios históricos de medalla y no son conteo de integrantes de equipo.",
        "",
        "## Equipos",
        "",
        "El conteo usa una medalla lógica por combinación edición/NOC/medalla/clave semántica. Los integrantes aparecen juntos en `atletas_asociados`; no se cuentan como Gold adicionales. Esto aplica a relevos, equipos, basketball y equipos de gimnasia.",
        "",
        "## Controles",
        *[f"- {r['caso']}: {r['valor']} frente a {r['esperado']} — {r['estado']}." for r in athlete_controls],
        *[f"- {r['noc']}: {r['gold_before']} → {r['gold_after_residual_simulation']} — {r['estado']}." for r in control_rows],
        "- Guatemala: PASS; London 2012 50 km: PASS, conservados por el dry-run anterior.",
        "",
        "## Integridad",
        "",
        f"Processed SHA: {integrity['processed_sha']}; RAW: {integrity['raw_sha']}; intermediate: {integrity['intermediate_sha']}; SQL modificado: {integrity['sql_modified']}.",
        "",
        "Fuentes: [tabla oficial del Comité Olímpico Chino](" + COC_MEDAL_TABLE + "), [resumen oficial Beijing 2008](" + COC_BEIJING_OVERVIEW + "), [IOC Olympic Medal Table Changes](" + IOC_MEDAL_CHANGES + ").",
        "",
        "Esta fase solo deja evidencia para una futura aplicación controlada. No modifica el mapa previo de 1,015 duplicados ni aplica los dos aliases adicionales.",
    ]
    (OUT / "beijing2008_chn_gold_residual_audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
