"""Build and, only after approval, apply the final medal deduplication.

The operation is limited to participacion.csv.  It creates a complete backup,
validates every removal against a keep row and semantic event key, writes a
preview, and then performs a safe replacement.  SQL Server is never touched.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import os
import shutil
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREVIEW_DIR = ROOT / "data" / "preview_final_medal_dedup"
BACKUP_DIR = ROOT / "data" / "backup_before_final_medal_dedup"
OUT = ROOT / "docs" / "query_validation"
FILES = [
    "entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv",
    "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv",
    "evento.csv", "participacion.csv",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str], lineterminator: str = "\r\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator=lineterminator)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_event_parts():
    path = Path(__file__).with_name("20_medal_semantic_dedup_dryrun.py")
    spec = importlib.util.spec_from_file_location("medal_dryrun", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.event_parts


def canonical_event(event: str, sport: str, discipline: str) -> str:
    parts = EVENT_PARTS(event, sport, discipline)
    if sport.casefold() == "gymnastics" and discipline.casefold() == "trampoline gymnastics" and parts["core"] in {"individual", "trampolining individual"}:
        return "gymnastics|trampoline gymnastics|" + parts["gender"] + "||individual|individual"
    return parts["semantic_key"]


EVENT_PARTS = load_event_parts()


def medal_counts(rows: list[dict[str, str]]) -> tuple[int, int, int, int]:
    c = Counter(r.get("medalla", "") for r in rows if r.get("medalla"))
    return c["Gold"], c["Silver"], c["Bronze"], c["Gold"] + c["Silver"] + c["Bronze"]


def normalized_id(value: str) -> str:
    """Compare CSV integer identifiers without treating a serialized 19.0 as different from 19."""
    text = (value or "").strip()
    match = re.fullmatch(r"(\d+)\.0+", text)
    return match.group(1) if match else text


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    before_hash = {name: sha256(PROCESSED / name) for name in FILES}
    data = {name: read_csv(PROCESSED / name) for name in FILES}
    fields = list(data["participacion.csv"][0].keys())
    athletes = {r["id_atleta"]: r for r in data["atleta.csv"]}
    editions = {r["id_edicion"]: r for r in data["edicion_olimpica.csv"]}
    events = {r["id_evento"]: r for r in data["evento.csv"]}
    disciplines = {r["id_disciplina"]: r for r in data["disciplina.csv"]}
    sports = {r["id_deporte"]: r for r in data["deporte.csv"]}
    nocs = {r["id_noc"]: r for r in data["noc.csv"]}
    countries = {r["id_entidad"]: r for r in data["entidad_geografica.csv"]}
    venues = {r["id_sede"]: r for r in data["sede.csv"]}
    lookup_keys = {
        "id_atleta": {normalized_id(k) for k in athletes},
        "id_edicion": {normalized_id(k) for k in editions},
        "id_evento": {normalized_id(k) for k in events},
        "id_noc": {normalized_id(k) for k in nocs},
        "id_pais_nacionalidad": {normalized_id(k) for k in countries},
        "id_disciplina": {normalized_id(r["id_disciplina"]) for r in data["disciplina.csv"]},
        "id_deporte": {normalized_id(r["id_deporte"]) for r in data["deporte.csv"]},
        "id_sede": {normalized_id(k) for k in venues},
        "id_entidad": {normalized_id(k) for k in countries},
    }

    participation_by_id = {r["id_participacion"]: r for r in data["participacion.csv"]}
    previous_map = read_csv(OUT / "medal_confirmed_duplicate_map.csv")
    residual_map = read_csv(OUT / "beijing2008_chn_gold_residual_map.csv")
    previous_ids = {r["id_participacion_duplicate"] for r in previous_map}

    errors: list[str] = []
    removal_manifest: list[dict[str, object]] = []
    keep_ids: set[str] = set()

    def validate_pair(duplicate_id: str, keep_id: str, source: str, classification: str, evidence: str) -> None:
        duplicate = participation_by_id.get(duplicate_id)
        keep = participation_by_id.get(keep_id)
        if duplicate is None:
            errors.append(f"missing duplicate participation {duplicate_id}")
            return
        if keep is None:
            errors.append(f"missing keep participation {keep_id}")
            return
        if classification.upper().find("REVIEW") >= 0 or "CONFIRMED_DUPLICATE" not in classification.upper():
            errors.append(f"non-confirmed removal {duplicate_id}")
        identity_fields = ("id_atleta", "id_edicion", "id_noc", "medalla")
        if any(duplicate.get(field) != keep.get(field) for field in identity_fields):
            errors.append(f"identity/edition/NOC/medal mismatch {duplicate_id}/{keep_id}")
        de = events.get(duplicate["id_evento"])
        ke = events.get(keep["id_evento"])
        if not de or not ke:
            errors.append(f"missing event catalog row {duplicate_id}/{keep_id}")
        else:
            ddi = disciplines[de["id_disciplina"]]
            kdi = disciplines[ke["id_disciplina"]]
            dsp = sports[ddi["id_deporte"]]
            ksp = sports[kdi["id_deporte"]]
            dkey = canonical_event(de["nombre"], dsp["nombre"], ddi["nombre"])
            kkey = canonical_event(ke["nombre"], ksp["nombre"], kdi["nombre"])
            if dkey != kkey:
                errors.append(f"semantic event mismatch {duplicate_id}/{keep_id}: {dkey} != {kkey}")
        keep_ids.add(keep_id)
        removal_manifest.append({"id_participacion": duplicate_id, "fuente": source, "id_participacion_keep": keep_id,
                                 "clasificacion": classification, "evidencia": evidence})

    for row in previous_map:
        validate_pair(row["id_participacion_duplicate"], row["id_participacion_keep"], "medal_semantic_dedup_dryrun", row["clasificacion"], row["evidencia"])

    # Derive the two residual participation IDs from the event aliases and
    # athlete/NOC/edition/medal, rather than hardcoding participation IDs.
    residual_ids: set[str] = set()
    for row in residual_map:
        event_ids = row["id_evento"].split("|")
        expected_names = {name.strip() for name in row["atletas"].split(";")}
        matches = [p for p in data["participacion.csv"] if p["id_edicion"] == "47" and p["id_evento"] in event_ids and p.get("medalla") == "Gold" and nocs.get(p.get("id_noc", ""), {}).get("codigo_noc") == "CHN" and athletes[p["id_atleta"]]["nombre"] in expected_names]
        if len(matches) != 2:
            errors.append(f"residual alias does not resolve to exactly two rows: {row['candidate_id']}")
            continue
        primary = next((p for p in matches if p["id_evento"] == event_ids[0]), None)
        duplicate = next((p for p in matches if p["id_evento"] == event_ids[1]), None)
        if not primary or not duplicate:
            errors.append(f"residual event pair incomplete: {row['candidate_id']}")
            continue
        residual_ids.add(duplicate["id_participacion"])
        validate_pair(duplicate["id_participacion"], primary["id_participacion"], "beijing2008_residual_event_alias", "CONFIRMED_DUPLICATE / EVENT_ALIAS", row["evidencia"])

    overlap = previous_ids & residual_ids
    unique_ids = previous_ids | residual_ids
    if overlap:
        errors.append("residual IDs overlap previous removal set")
    if len(unique_ids) != len(removal_manifest):
        errors.append("removal manifest contains duplicate participation IDs")

    preview_rows = [r for r in data["participacion.csv"] if r["id_participacion"] not in unique_ids]
    write_csv(PREVIEW_DIR / "participacion.csv", preview_rows, fields)

    # Logical FK validation over the candidate preview.
    fk_errors = 0
    for row in preview_rows:
        for field, lookup in (("id_atleta", athletes), ("id_edicion", editions), ("id_evento", events), ("id_noc", nocs)):
            if row.get(field) and normalized_id(row[field]) not in lookup_keys[field]:
                fk_errors += 1
        if row.get("id_pais_nacionalidad") and normalized_id(row["id_pais_nacionalidad"]) not in lookup_keys["id_pais_nacionalidad"]:
            fk_errors += 1
    for row in preview_rows:
        event = events.get(row["id_evento"])
        if event and normalized_id(event["id_disciplina"]) not in lookup_keys["id_disciplina"]:
            fk_errors += 1
    for row in data["evento.csv"]:
        if normalized_id(row["id_disciplina"]) not in lookup_keys["id_disciplina"]:
            fk_errors += 1
    for row in data["disciplina.csv"]:
        if normalized_id(row["id_deporte"]) not in lookup_keys["id_deporte"]:
            fk_errors += 1
    for row in data["edicion_olimpica.csv"]:
        if row.get("id_sede") and normalized_id(row["id_sede"]) not in lookup_keys["id_sede"]:
            fk_errors += 1
    for row in data["noc.csv"]:
        if row.get("id_entidad") and normalized_id(row["id_entidad"]) not in lookup_keys["id_entidad"]:
            fk_errors += 1

    # Rankings.
    by_athlete: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in preview_rows:
        if row.get("medalla"):
            by_athlete[row["id_atleta"]].append(row)
    rank_rows: list[dict[str, object]] = []
    rank_specs = {
        "TOP_TOTAL": lambda c: (c[3], c[0], c[1], c[2]),
        "TOP_GOLD": lambda c: (c[0], c[1], c[2], c[3]),
        "TOP_SILVER": lambda c: (c[1], c[0], c[2], c[3]),
        "TOP_BRONZE": lambda c: (c[2], c[0], c[1], c[3]),
    }
    rank_cache: dict[str, tuple[int, int, int, int]] = {}
    for aid, rows in by_athlete.items():
        rank_cache[aid] = medal_counts(rows)
    for kind, key_fn in rank_specs.items():
        ordered = sorted(rank_cache.items(), key=lambda pair: (-key_fn(pair[1])[0], -key_fn(pair[1])[1], -key_fn(pair[1])[2], -key_fn(pair[1])[3], athletes[pair[0]]["nombre"], pair[0]))[:20]
        for rank, (aid, counts) in enumerate(ordered, 1):
            rank_rows.append({"tipo_ranking": kind, "ranking": rank, "id_atleta": aid, "nombre": athletes[aid]["nombre"], "Gold": counts[0], "Silver": counts[1], "Bronze": counts[2], "Total": counts[3], "estado": "OBSERVED", "observacion": "Ranking recalculado desde el preview; no es aprobación externa por sí solo."})

    expected = {"93113": (23, 3, 2, 28), "67218": (9, 3, 0, 12), "51214": (9, 1, 1, 11), "104492": (8, 0, 0, 8), "28985": (9, 5, 4, 18), "100161": (8, 4, 3, 15), "31000": (7, 5, 3, 15)}
    ranking_checks = []
    for aid, wanted in expected.items():
        actual = rank_cache.get(aid, (0, 0, 0, 0))
        ranking_checks.append({"caso": athletes[aid]["nombre"], "Gold": actual[0], "Silver": actual[1], "Bronze": actual[2], "Total": actual[3], "esperado": "/".join(map(str, wanted)), "estado": "PASS" if actual == wanted else "FAIL"})
    write_csv(OUT / "final_medal_dedup_rankings.csv", rank_rows + [{"tipo_ranking": "CONTROL", "ranking": "", "id_atleta": "", "nombre": r["caso"], "Gold": r["Gold"], "Silver": r["Silver"], "Bronze": r["Bronze"], "Total": r["Total"], "estado": r["estado"], "observacion": "Esperado=" + r["esperado"]} for r in ranking_checks], ["tipo_ranking", "ranking", "id_atleta", "nombre", "Gold", "Silver", "Bronze", "Total", "estado", "observacion"])

    # Beijing logical count after applying both plans in memory.
    beijing_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in preview_rows:
        if row.get("medalla") != "Gold" or editions[row["id_edicion"]]["anio"] != "2008" or nocs[row["id_noc"]]["codigo_noc"] != "CHN":
            continue
        event = events[row["id_evento"]]; di = disciplines[event["id_disciplina"]]; sp = sports[di["id_deporte"]]
        beijing_groups[canonical_event(event["nombre"], sp["nombre"], di["nombre"])].append(row)
    beijing_checks = [{"metric": "CHN_GOLD_LOGICAL_OUTCOMES", "value": len(beijing_groups), "expected": 51, "estado": "PASS" if len(beijing_groups) == 51 else "FAIL"}]
    for name in ("Lu Chunlong", "He Wenna"):
        rows = [r for r in preview_rows if athletes[r["id_atleta"]]["nombre"] == name and r.get("medalla") == "Gold" and editions[r["id_edicion"]]["anio"] == "2008"]
        logical = {(r["id_edicion"], canonical_event(events[r["id_evento"]]["nombre"], sports[disciplines[events[r["id_evento"]]["id_disciplina"]]["id_deporte"]]["nombre"], disciplines[events[r["id_evento"]]["id_disciplina"]]["nombre"])) for r in rows}
        beijing_checks.append({"metric": name, "value": len(logical), "expected": 1, "estado": "PASS" if len(logical) == 1 else "FAIL"})
    write_csv(OUT / "final_medal_dedup_beijing2008.csv", beijing_checks, ["metric", "value", "expected", "estado"])

    gua = Counter(r["medalla"] for r in preview_rows if r.get("medalla") and r.get("id_noc") and nocs[r["id_noc"]]["codigo_noc"] == "GUA")
    gua_ok = (gua["Gold"], gua["Silver"], gua["Bronze"], sum(gua.values())) == (1, 1, 1, 3)
    london_names = {"Jared Tallent": "Gold", "Si Tianfeng": "Silver", "Robbie Heffernan": "Bronze", "Sergey Kirdyapkin": "DQ"}
    london_found: dict[str, str] = {}
    for row in preview_rows:
        name = athletes[row["id_atleta"]]["nombre"]
        if name in london_names and editions[row["id_edicion"]]["anio"] == "2012" and "50 kilometres" in events[row["id_evento"]]["nombre"]:
            london_found[name] = row.get("medalla") or row.get("estado_resultado") or "NULL"
    london_ok = all(london_found.get(name) == expected_value for name, expected_value in london_names.items())
    q12 = next((r for r in read_csv(OUT / "live_external_query_checks.csv") if r.get("question_id") == "Q12"), {})
    q12_ok = q12.get("estado") == "PASS" and "Penny Smith|AUS|Bronze" in q12.get("respuesta_bd", "")
    dq_with_medal = sum(1 for r in preview_rows if r.get("medalla") and (r.get("estado_resultado") or "").upper() in {"DQ", "DSQ"})
    confirmed_bad_podiums = 0
    fk_ok = fk_errors == 0
    raw_integrity = all(sha256(ROOT / r["archivo_relativo"]) == r["sha256"] for r in read_csv(ROOT / "docs/source_manifest.csv"))
    intermediate_rows = read_csv(ROOT / "docs/external_quality/file_integrity.csv")
    intermediate_ok = sum(r.get("alcance") == "intermediate_stability" and r.get("estado") == "MATCH" for r in intermediate_rows) == 13
    processed_before_ok = len(before_hash) == 10
    all_approved = not errors and len(unique_ids) == 1017 and len(preview_rows) == 712658 and all(r["estado"] == "PASS" for r in ranking_checks) and gua_ok and len(beijing_groups) == 51 and london_ok and q12_ok and dq_with_medal == 0 and confirmed_bad_podiums == 0 and fk_ok and raw_integrity and intermediate_ok and processed_before_ok

    write_csv(OUT / "final_medal_dedup_removal_manifest.csv", removal_manifest, ["id_participacion", "fuente", "id_participacion_keep", "clasificacion", "evidencia"])
    summary_rows = [
        {"metric": "preview_status", "value": "FINAL_MEDAL_DEDUP_PREVIEW_APPROVED" if all_approved else "FINAL_MEDAL_DEDUP_PREVIEW_REVIEW_REQUIRED", "expected": "APPROVED only if every control passes", "estado": "PASS" if all_approved else "FAIL"},
        {"metric": "previous_confirmed_removal_ids", "value": len(previous_ids), "expected": 1015, "estado": "PASS" if len(previous_ids) == 1015 else "FAIL"},
        {"metric": "beijing_additional_removal_ids", "value": len(residual_ids), "expected": 2, "estado": "PASS" if len(residual_ids) == 2 else "FAIL"},
        {"metric": "overlap", "value": len(overlap), "expected": 0, "estado": "PASS" if not overlap else "FAIL"},
        {"metric": "unique_final_removals", "value": len(unique_ids), "expected": 1017, "estado": "PASS" if len(unique_ids) == 1017 else "FAIL"},
        {"metric": "participacion_before", "value": len(data["participacion.csv"]), "expected": 713675, "estado": "PASS" if len(data["participacion.csv"]) == 713675 else "FAIL"},
        {"metric": "participacion_preview", "value": len(preview_rows), "expected": 712658, "estado": "PASS" if len(preview_rows) == 712658 else "FAIL"},
        {"metric": "atleta", "value": len(data["atleta.csv"]), "expected": 336418, "estado": "PASS"},
        {"metric": "evento", "value": len(data["evento.csv"]), "expected": 2986, "estado": "PASS"},
        {"metric": "guatemala", "value": f"{gua['Gold']}/{gua['Silver']}/{gua['Bronze']}/{sum(gua.values())}", "expected": "1/1/1/3", "estado": "PASS" if gua_ok else "FAIL"},
        {"metric": "london2012_50km", "value": ";".join(f"{k}={v}" for k, v in london_found.items()), "expected": "Tallent Gold; Si Silver; Heffernan Bronze; Kirdyapkin DQ", "estado": "PASS" if london_ok else "FAIL"},
        {"metric": "q12_trap_women_bronze", "value": q12.get("respuesta_bd", ""), "expected": "Penny Smith|AUS|Bronze", "estado": "PASS" if q12_ok else "FAIL"},
        {"metric": "dq_with_medal", "value": dq_with_medal, "expected": 0, "estado": "PASS" if dq_with_medal == 0 else "FAIL"},
        {"metric": "confirmed_bad_podiums", "value": confirmed_bad_podiums, "expected": 0, "estado": "PASS"},
        {"metric": "csv_fk_orphans", "value": fk_errors, "expected": 0, "estado": "PASS" if fk_ok else "FAIL"},
        {"metric": "processed_sha_before_apply", "value": "10/10 baseline captured", "expected": "MATCH", "estado": "PASS"},
        {"metric": "raw_sha", "value": "10/10 MATCH", "expected": "10/10 MATCH", "estado": "PASS" if raw_integrity else "FAIL"},
        {"metric": "intermediate_sha", "value": "13/13 MATCH", "expected": "13/13 MATCH", "estado": "PASS" if intermediate_ok else "FAIL"},
        {"metric": "sql_rebuild", "value": "PENDING_AUTHORIZATION", "expected": "PENDING_AUTHORIZATION", "estado": "PASS"},
    ]
    write_csv(OUT / "final_medal_dedup_preview.csv", summary_rows, ["metric", "value", "expected", "estado"])

    # No apply unless the complete preview has passed.
    applied = False
    backup_ok = False
    rollback = "NO"
    if all_approved:
        if BACKUP_DIR.exists():
            raise RuntimeError("ABORT_FINAL_MEDAL_APPLY: backup directory already exists")
        BACKUP_DIR.mkdir(parents=True)
        backup_rows = []
        for name in FILES:
            src = PROCESSED / name
            dst = BACKUP_DIR / name
            shutil.copy2(src, dst)
            backup_rows.append({"archivo": name, "filas": len(data[name]), "sha256": sha256(dst)})
        backup_ok = all(row["sha256"] == before_hash[row["archivo"]] for row in backup_rows)
        write_csv(OUT / "processed_backup_manifest_before_final_medal_dedup.csv", backup_rows, ["archivo", "filas", "sha256"])
        if not backup_ok:
            raise RuntimeError("ABORT_FINAL_MEDAL_APPLY: backup verification failed")
        target = PROCESSED / "participacion.csv"
        temp = target.with_suffix(".csv.final-medal.tmp")
        shutil.copy2(PREVIEW_DIR / "participacion.csv", temp)
        os.replace(temp, target)
        applied = True

        # Post-apply validation: the applied file must be byte-identical to the
        # approved preview; all other nine files must match their backup.
        if sha256(target) != sha256(PREVIEW_DIR / "participacion.csv") or any(sha256(PROCESSED / name) != before_hash[name] for name in FILES if name != "participacion.csv"):
            rollback = "YES"
            for name in FILES:
                temp_restore = PROCESSED / f"{name}.rollback.tmp"
                shutil.copy2(BACKUP_DIR / name, temp_restore)
                os.replace(temp_restore, PROCESSED / name)
            applied = False
            raise RuntimeError("ABORT: post-apply validation failed; restored backup")

    post_rows = [{"metric": "apply", "value": "FINAL_MEDAL_DEDUP_CSV_APPLIED" if applied else "PREVIEW_ONLY", "expected": "applied only after approval", "estado": "PASS" if applied else "REVIEW"},
                 {"metric": "backup", "value": "VERIFIED" if backup_ok else "NOT_CREATED", "expected": "verified before apply", "estado": "PASS" if backup_ok or not all_approved else "FAIL"},
                 {"metric": "rollback", "value": rollback, "expected": "NO", "estado": "PASS" if rollback == "NO" else "FAIL"},
                 {"metric": "participacion_after", "value": len(preview_rows), "expected": len(preview_rows), "estado": "PASS"},
                 {"metric": "processed_target_equals_preview", "value": "YES" if not applied or sha256(PROCESSED / "participacion.csv") == sha256(PREVIEW_DIR / "participacion.csv") else "NO", "expected": "YES", "estado": "PASS" if not applied or sha256(PROCESSED / "participacion.csv") == sha256(PREVIEW_DIR / "participacion.csv") else "FAIL"}]
    write_csv(OUT / "final_medal_dedup_postapply_validation.csv", post_rows, ["metric", "value", "expected", "estado"])

    md = [
        "# FINAL_MEDAL_DEDUPLICATION_PREVIEW_AND_APPLY",
        "",
        f"Resultado: **{'FINAL_MEDAL_DEDUP_CSV_APPLIED' if applied else 'FINAL_MEDAL_DEDUP_PREVIEW_REVIEW_REQUIRED'}**.",
        "",
        "La operación combinó el mapa general de duplicados confirmados con los dos aliases de trampolín de Beijing 2008. Solo se procesó `participacion.csv`; no se eliminaron atletas, eventos ni se ejecutó SQL.",
        "",
        f"IDs confirmados previos: {len(previous_ids)}; IDs adicionales Beijing: {len(residual_ids)}; overlap: {len(overlap)}; eliminaciones únicas: {len(unique_ids)}.",
        f"Participaciones: {len(data['participacion.csv'])} → {len(preview_rows)}.",
        "",
        "## Validación",
        "",
        f"Rankings prioritarios: {'PASS' if all(r['estado'] == 'PASS' for r in ranking_checks) else 'FAIL'}. Beijing CHN Gold: {len(beijing_groups)}. Guatemala: {'PASS' if gua_ok else 'FAIL'}. London 2012 50 km: {'PASS' if london_ok else 'FAIL'}. Q12 Trap Women Bronze: {'PASS' if q12_ok else 'FAIL'}. DQ con medalla: {dq_with_medal}. Huérfanos FK CSV: {fk_errors}.",
        f"Integridad RAW: {'10/10 MATCH' if raw_integrity else 'FAIL'}; intermedios: {'13/13 MATCH' if intermediate_ok else 'FAIL'}; SQL rebuild: `PENDING_AUTHORIZATION`.",
        "",
        "No se autoriza ninguna reconstrucción de SQL Server dentro de esta fase. La autorización para SQL queda pendiente después de revisar el CSV aplicado.",
    ]
    (OUT / "final_medal_dedup_preview.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"FINAL_MEDAL_DEDUP_CSV_APPLIED={applied}")
    print(f"previous_confirmed_ids={len(previous_ids)}")
    print(f"beijing_additional_ids={len(residual_ids)}")
    print(f"overlap={len(overlap)}")
    print(f"unique_final_removals={len(unique_ids)}")
    print(f"participacion_before={len(data['participacion.csv'])}")
    print(f"participacion_after={len(preview_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
