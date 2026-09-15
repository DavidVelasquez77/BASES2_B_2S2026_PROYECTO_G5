"""Apply the reviewed GUA canonical correction to processed participations.

The correction is limited to GUA participation associations.  It preserves
all athlete entities, raw/intermediate data and non-GUA rows.  Olympic Games
are reconciled against the 263-person Olympedia reference; Youth Olympic
Games remain in the data and are reported separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "quality"
BACKUP = ROOT / "data" / "backup_before_gua_canonical_apply"
PREVIEW = ROOT / "data" / "preview_gua_canonical_apply"
MAPPING = OUT / "gua_identity_mapping_dryrun.csv"
ROSTER = OUT / "gua_olympedia_olympic_roster.csv"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not MAPPING.exists() or not ROSTER.exists():
        raise SystemExit("Faltan los artefactos de dry-run GUA; ejecutar primero el script 27.")

    processed_files = sorted(PROCESSED.glob("*.csv"))
    if len(processed_files) != 10:
        raise SystemExit(f"Se esperaban 10 CSV procesados; encontrados {len(processed_files)}.")

    fields_p, participations = read_csv(PROCESSED / "participacion.csv")
    fields_a, athletes = read_csv(PROCESSED / "atleta.csv")
    _, nocs = read_csv(PROCESSED / "noc.csv")
    _, editions = read_csv(PROCESSED / "edicion_olimpica.csv")
    noc_by_id = {row["id_noc"]: row.get("codigo_noc", "") for row in nocs}
    edition_by_id = {row["id_edicion"]: row for row in editions}
    athlete_by_id = {row["id_atleta"]: row for row in athletes}

    # Manual aliases are limited to a same-person variant within a specific
    # edition and are recorded below as reviewed cases.  The IDs for 2024 are
    # source aliases that otherwise split already-known Olympic identities.
    manual_reference_to_canonical = {
        "42706": "42384",   # Fernando Samoyoa -> Fernando Samoya
        "58519": "58107",   # Ángel Aldana/Aldama; retained as documented ambiguity
        "11307": "11249",   # Sylvia Luna -> Sylvia de Luna
        "38091": "37792",   # Alberic/Alberik de Suremain
        "48007": "47656",   # Karin/Karen Slowing-Aceituno
        "25640": "25450",   # Luis Villavicencio duplicate ID
        "25641": "25451",   # Allan Wellman duplicate ID
        "117898": "116505", # Juan Ignacio Maegli
        "123159": "121191", # Érick Barrondo
        "143541": "140045", # José Alejandro Barrondo
        "123253": "121277", # Jean-Pierre Brol
        "143538": "140042", # Ana Waleska Soto
    }
    source_aliases = {
        ("12", "265982"): "167002",  # Antonia Matos split in 1932
        ("30", "320284"): "25450",   # Luis Villavicencio duplicate
        ("36", "323238"): "25451",   # Allan Wellman duplicate
        ("61", "336654"): "140045",  # José Alejandro Barrondo
        ("61", "336655"): "121191",  # Érick Barrondo
        ("61", "336729"): "116505",  # Juan Ignacio Maegli
        ("61", "337121"): "121277",  # Jean-Pierre Brol
        ("61", "337125"): "140042",  # Ana Waleska Soto
    }

    with MAPPING.open("r", encoding="utf-8-sig", newline="") as handle:
        mapping_rows = list(csv.DictReader(handle))
    with ROSTER.open("r", encoding="utf-8-sig", newline="") as handle:
        roster_rows = list(csv.DictReader(handle))

    counted_refs = {
        row["olympedia_athlete_id"]
        for row in roster_rows
        if row.get("contado_en_referencia_263") == "YES"
    }
    if len(counted_refs) != 263:
        raise SystemExit(f"Referencia inválida: se esperaban 263 IDs y hay {len(counted_refs)}.")

    canonical_by_ref: dict[str, str] = {}
    for row in mapping_rows:
        ref_id = row["olympedia_athlete_id"]
        if ref_id not in counted_refs:
            continue
        candidate = row.get("id_atleta_candidato", "")
        if row.get("decision") != "KEEP_CANDIDATE":
            candidate = manual_reference_to_canonical.get(ref_id, "")
        if candidate:
            canonical_by_ref[ref_id] = candidate

    if set(canonical_by_ref) != counted_refs:
        missing = sorted(counted_refs - set(canonical_by_ref), key=int)
        raise SystemExit(f"ABORTADO: faltan referencias GUA por resolver: {missing}")

    allowed_by_edition: defaultdict[str, set[str]] = defaultdict(set)
    for row in mapping_rows:
        ref_id = row["olympedia_athlete_id"]
        if ref_id in canonical_by_ref:
            allowed_by_edition[row["id_edicion"]].add(canonical_by_ref[ref_id])

    before_hashes = {path.name: sha256(path) for path in processed_files}
    if args.apply and BACKUP.exists():
        existing_backup_files = list(BACKUP.glob("*.csv"))
        if len(existing_backup_files) >= 10:
            for existing in existing_backup_files:
                if before_hashes.get(existing.name) != sha256(existing):
                    raise SystemExit(f"ABORTADO: el respaldo completo no coincide con el estado actual: {existing.name}.")
        for existing in existing_backup_files:
            if before_hashes.get(existing.name) != sha256(existing):
                raise SystemExit(f"ABORTADO: respaldo parcial inconsistente: {existing.name}.")
    decisions: list[dict[str, str]] = []
    dedup_candidates: list[dict[str, str]] = []
    transformed: list[dict[str, str]] = []
    kept: list[dict[str, str]] = []
    seen_business: dict[tuple[str, ...], dict[str, str]] = {}
    removed = 0
    reassigned = 0
    kept_olympic = 0
    kept_youth = 0

    for row in participations:
        is_gua = noc_by_id.get(row.get("id_noc", "")) == "GUA"
        edition = edition_by_id.get(row.get("id_edicion", ""), {})
        season = edition.get("temporada", "")
        current_id = row.get("id_atleta", "")
        original_id = current_id
        action = "UNCHANGED_NON_GUA"
        reason = "Participación no GUA; fuera del alcance de esta corrección."

        if is_gua and season in {"Summer Youth", "Winter Youth"}:
            action = "KEEP_YOUTH_OUTSIDE_263"
            reason = "Participación Youth conservada; el padrón 263 corresponde a Olympic Games."
            kept_youth += 1
        elif is_gua and season in {"Summer", "Winter"}:
            alias = source_aliases.get((row["id_edicion"], current_id))
            if alias:
                row = dict(row)
                row["id_atleta"] = alias
                current_id = alias
                reassigned += 1
                action = "REASSIGNED_CANONICAL_ALIAS"
                reason = "Alias de fuente resuelto contra la misma persona y edición en la referencia."
            if current_id in allowed_by_edition.get(row["id_edicion"], set()):
                kept_olympic += 1
                if action == "UNCHANGED_NON_GUA":
                    action = "KEEP_CONFIRMED_GUA"
                    reason = "ID local presente en el padrón GUA de la misma edición."
                transformed.append({
                    "id_participacion": row["id_participacion"],
                    "id_edicion": row["id_edicion"],
                    "id_atleta_original": original_id,
                    "id_atleta_final": row["id_atleta"],
                    "nombre": athlete_by_id.get(original_id, {}).get("nombre", ""),
                    "accion": action,
                    "motivo": reason,
                })
            else:
                removed += 1
                decisions.append({
                    "id_participacion": row["id_participacion"],
                    "id_edicion": row["id_edicion"],
                    "id_atleta": original_id,
                    "nombre": athlete_by_id.get(original_id, {}).get("nombre", ""),
                    "accion": "EXCLUDE_GUA_ASSOCIATION",
                    "motivo": "No pertenece al padrón GUA de referencia para esa edición; asociación falsa o no resuelta.",
                    "estado": "REMOVED_FROM_GUA_ASSOCIATION",
                })
                continue

        business_key = tuple(row.get(field, "") for field in fields_p if field != "id_participacion")
        if business_key in seen_business:
            prior = seen_business[business_key]
            dedup_candidates.append({
                "id_participacion_eliminado": row["id_participacion"],
                "id_participacion_conservado": prior["id_participacion"],
                "id_atleta": row["id_atleta"],
                "id_edicion": row["id_edicion"],
                "id_evento": row["id_evento"],
                "motivo": "Duplicado exacto después de resolver alias; se conserva el menor id_participacion.",
            })
            continue
        seen_business[business_key] = row
        kept.append(row)

    gua_final_ids = {
        row["id_atleta"]
        for row in kept
        if noc_by_id.get(row.get("id_noc", "")) == "GUA"
        and edition_by_id.get(row.get("id_edicion", ""), {}).get("temporada", "") in {"Summer", "Winter"}
    }
    if len(gua_final_ids) != 263:
        raise SystemExit(f"ABORTADO: el resultado produciría {len(gua_final_ids)} IDs GUA olímpicos, no 263.")

    result_hashes: dict[str, str] = {}
    if args.apply:
        BACKUP.mkdir(parents=True, exist_ok=True)
        PREVIEW.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, str]] = []
        for path in processed_files:
            backup_path = BACKUP / path.name
            shutil.copy2(path, backup_path)
            _, path_rows = read_csv(path)
            manifest.append({"archivo": path.name, "filas": str(len(path_rows)), "sha256": before_hashes[path.name]})
            if path.name == "participacion.csv":
                write_csv(PREVIEW / path.name, fields_p, kept)
            else:
                shutil.copy2(path, PREVIEW / path.name)
        write_csv(OUT / "gua_canonical_backup_manifest.csv", ["archivo", "filas", "sha256"], manifest)
        # Replace the bytes in place. Windows can reject CopyFile2 when an
        # editor has a mapped section for a large CSV, while a normal write is
        # still safe once the source bytes have been materialized.
        processed_target = PROCESSED / "participacion.csv"
        processed_payload = (PREVIEW / "participacion.csv").read_bytes()
        with processed_target.open("wb") as handle:
            handle.write(processed_payload)
        result_hashes["participacion.csv"] = sha256(PROCESSED / "participacion.csv")
    else:
        write_csv(PREVIEW / "participacion.csv", fields_p, kept)
        result_hashes["participacion.csv"] = sha256(PREVIEW / "participacion.csv")

    write_csv(OUT / "gua_removed_associations.csv", list(decisions[0]) if decisions else ["id_participacion", "id_edicion", "id_atleta", "nombre", "accion", "motivo", "estado"], decisions)
    write_csv(OUT / "gua_canonical_duplicate_analysis.csv", list(dedup_candidates[0]) if dedup_candidates else ["id_participacion_eliminado", "id_participacion_conservado", "id_atleta", "id_edicion", "id_evento", "motivo"], dedup_candidates)
    write_csv(OUT / "gua_identity_mapping_applied.csv", ["olympedia_athlete_id", "id_atleta_canonico", "estado"], [{"olympedia_athlete_id": ref, "id_atleta_canonico": aid, "estado": "CANONICAL_GUA"} for ref, aid in sorted(canonical_by_ref.items(), key=lambda item: int(item[0]))])
    ambiguous = [
        {"caso": "Ángel Aldana / Ángel Aldama", "id_atleta": "58107", "estado": "AMBIGUOUS_DOCUMENTED", "motivo": "Diferencia de apellido entre referencia y fuente local; se conserva la asociación, no se fusiona con otro ID.", "referencia": "https://www.olympedia.org/countries/GUA/editions/17"},
        {"caso": "Luis Villavicencio", "id_atleta": "25450/320284", "estado": "RESOLVED_CANONICAL", "motivo": "Dos IDs locales; se conserva el registro biográfico completo 25450 y se reasigna 320284.", "referencia": "https://www.olympedia.org/countries/GUA/editions/19"},
        {"caso": "Allan Wellman", "id_atleta": "25451/323238", "estado": "RESOLVED_CANONICAL", "motivo": "Dos IDs locales; se conserva el registro biográfico completo 25451 y se reasigna 323238.", "referencia": "https://www.olympedia.org/countries/GUA/editions/22"},
    ]
    write_csv(OUT / "gua_ambiguous_cases.csv", list(ambiguous[0]), ambiguous)

    after_count = len(kept)
    report = [
        "# Corrección canónica GUA",
        "",
        f"Estado: **{'APPLIED_TO_PROCESSED' if args.apply else 'DRY_RUN'}**",
        "",
        "La corrección se limita a asociaciones GUA en participacion.csv. atleta.csv no se elimina ni se reescribe; los IDs fuente sin asociaciones GUA válidas permanecen para trazabilidad.",
        "",
        f"- Referencia Olympedia: **263 IDs únicos** y **339 registros por edición**.",
        f"- IDs GUA Olympic finales: **{len(gua_final_ids)}**.",
        f"- Filas de participación antes: **{len(participations)}**.",
        f"- Filas de participación después: **{after_count}**.",
        f"- Asociaciones GUA excluidas: **{removed}**.",
        f"- Reasignaciones de alias: **{reassigned}**.",
        f"- Duplicados exactos eliminados después de alias: **{len(dedup_candidates)}**.",
        f"- Participaciones Youth conservadas fuera del padrón 263: **{kept_youth}**.",
        "",
        "## Seguridad",
        "",
        "No se modificaron data/raw, data/intermediate, atleta.csv, evento.csv, SQL Server ni stored procedures. Los casos ambiguos están en `docs/quality/gua_ambiguous_cases.csv`.",
        "",
        "## Evidencia externa",
        "",
        "https://www.olympedia.org/countries/GUA",
    ]
    (OUT / "gua_canonical_apply.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("GUA_CANONICAL_APPLY_COMPLETE")
    print(f"gua_olympic_ids={len(gua_final_ids)}")
    print(f"participations_before={len(participations)}")
    print(f"participations_after={after_count}")
    print(f"removed_gua_associations={removed}")
    print(f"reassigned_aliases={reassigned}")
    print(f"exact_duplicates_removed={len(dedup_candidates)}")
    print(f"youth_rows_preserved={kept_youth}")
    print(f"mode={'APPLY' if args.apply else 'DRY_RUN'}")


if __name__ == "__main__":
    main()
