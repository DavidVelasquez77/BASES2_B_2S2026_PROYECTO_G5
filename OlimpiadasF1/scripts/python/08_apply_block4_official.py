"""Aplicación oficial del resultado READY_TO_APPLY de Bloque 4.

Hace backup de los diez CSV procesados, sustituye únicamente atleta/evento/
participacion desde data/preview_phase7 y ejecuta validaciones CSV. No ejecuta
SQL, no toca SQL Server y restaura automáticamente desde el backup ante fallo.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREVIEW = ROOT / "data" / "preview_phase7"
BACKUP = ROOT / "data" / "backup_before_block4_apply"
REPORTS = ROOT / "docs" / "consolidation"
READINESS = REPORTS / "final_readiness_phase7_1.csv"

APPLIED = {"atleta.csv", "evento.csv", "participacion.csv"}
REQUIRED_PREVIEW = APPLIED
EXPECTED_PREVIEW = {"atleta.csv": 336419, "evento.csv": 3007, "participacion.csv": 733414}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], data: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def validation(validation_rows: list[dict[str, object]], name: str, expected: object, actual: object, state: str, detail: str = "") -> None:
    validation_rows.append({"validacion": name, "esperado": expected, "actual": actual, "estado": state, "detalle": detail})


def canonical_ref(value: object) -> str:
    value = str(value or "").strip()
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return value


def fk_check(child: list[dict[str, str]], child_field: str, parent: set[str], nullable: bool = False) -> tuple[int, str]:
    parent = {canonical_ref(value) for value in parent}
    missing = [r.get(child_field, "") for r in child if (r.get(child_field, "") or not nullable) and canonical_ref(r.get(child_field, "")) not in parent]
    return len(missing), ";".join(missing[:5])


def main() -> None:
    validation_rows: list[dict[str, object]] = []
    report_rows: list[dict[str, object]] = []
    backup_created = False
    applied = False
    failure: str = ""
    before_hashes: dict[str, str] = {}
    before_counts: dict[str, int] = {}
    try:
        readiness_rows = read_csv(READINESS)
        readiness_ok = bool(readiness_rows) and all(r.get("estado") == "PASS" for r in readiness_rows)
        validation(validation_rows, "readiness_phase7_1", "todas las filas PASS", "todas PASS" if readiness_ok else "existe estado distinto de PASS", "PASS" if readiness_ok else "FAIL")
        if not readiness_ok:
            raise RuntimeError("final_readiness_phase7_1.csv no tiene todas sus filas en PASS")

        preview_names = {p.name for p in PREVIEW.iterdir() if p.is_file()}
        preview_ok = preview_names == REQUIRED_PREVIEW
        validation(validation_rows, "archivos_preview", sorted(REQUIRED_PREVIEW), sorted(preview_names), "PASS" if preview_ok else "FAIL")
        if not preview_ok:
            raise RuntimeError(f"data/preview_phase7 contiene archivos distintos de {sorted(REQUIRED_PREVIEW)}")

        processed_files = sorted(PROCESSED.glob("*.csv"))
        if {p.name for p in processed_files} != {"atleta.csv", "deporte.csv", "disciplina.csv", "edicion_olimpica.csv", "entidad_geografica.csv", "evento.csv", "noc.csv", "participacion.csv", "poblacion.csv", "sede.csv"}:
            raise RuntimeError("data/processed no contiene exactamente los 10 CSV esperados")
        if BACKUP.exists() and any(BACKUP.iterdir()):
            backup_files = sorted(BACKUP.glob("*.csv"))
            if {p.name for p in backup_files} != {p.name for p in processed_files}:
                raise RuntimeError("data/backup_before_block4_apply existe pero no contiene exactamente los 10 CSV")
            backup_hashes = {p.name: sha256(p) for p in backup_files}
            current_hashes = {p.name: sha256(p) for p in processed_files}
            if backup_hashes != current_hashes:
                raise RuntimeError("el backup existente no coincide con el estado actual restaurado; no se sobrescribe")
        else:
            BACKUP.mkdir(parents=True, exist_ok=True)
            for path in processed_files:
                shutil.copy2(path, BACKUP / path.name)
        backup_created = True

        for path in processed_files:
            before_hashes[path.name] = sha256(path)
            before_counts[path.name] = rows(path)
        manifest_before = [{"archivo": name, "filas": before_counts[name], "sha256": before_hashes[name]} for name in sorted(before_hashes)]
        write_csv(REPORTS / "processed_backup_manifest_before_apply.csv", ["archivo", "filas", "sha256"], manifest_before)

        for name, expected in EXPECTED_PREVIEW.items():
            actual = rows(PREVIEW / name)
            if actual != expected:
                raise RuntimeError(f"conteo preview inesperado para {name}: {actual} != {expected}")

        for name in sorted(APPLIED):
            shutil.copy2(PREVIEW / name, PROCESSED / name)
        applied = True

        after_hashes = {p.name: sha256(p) for p in sorted(PROCESSED.glob("*.csv"))}
        after_counts = {p.name: rows(p) for p in sorted(PROCESSED.glob("*.csv"))}
        for name in sorted(before_hashes):
            preview_hash = sha256(PREVIEW / name) if name in APPLIED else ""
            if name in APPLIED:
                state = "MATCH" if after_hashes[name] == preview_hash else "FAIL"
            else:
                state = "MATCH" if after_hashes[name] == before_hashes[name] else "FAIL"
            report_rows.append({"entidad": name.removesuffix(".csv").upper(), "filas_antes": before_counts[name], "filas_despues": after_counts[name], "diferencia": after_counts[name] - before_counts[name], "sha_backup": before_hashes[name], "sha_preview": preview_hash, "sha_processed_final": after_hashes[name], "estado": state})
        if any(r["estado"] != "MATCH" for r in report_rows):
            raise RuntimeError("falló la igualdad preview/processed o la integridad de los otros siete CSV")

        # Materialized counts: modified entities use approved preview counts;
        # the other seven must equal their pre-apply counts.
        for r in report_rows:
            name = r["entidad"].lower() + ".csv"
            expected = EXPECTED_PREVIEW[name] if name in APPLIED else before_counts[name]
            validation(validation_rows, f"conteo_{name}", expected, after_counts[name], "PASS" if expected == after_counts[name] else "FAIL")

        athletes = read_csv(PROCESSED / "atleta.csv")
        parts = read_csv(PROCESSED / "participacion.csv")
        events = read_csv(PROCESSED / "evento.csv")
        disciplines = read_csv(PROCESSED / "disciplina.csv")
        entities = read_csv(PROCESSED / "entidad_geografica.csv")
        population = read_csv(PROCESSED / "poblacion.csv")
        nocs = read_csv(PROCESSED / "noc.csv")
        venues = read_csv(PROCESSED / "sede.csv")
        editions = read_csv(PROCESSED / "edicion_olimpica.csv")
        sports = read_csv(PROCESSED / "deporte.csv")

        athlete_ids = {r["id_atleta"] for r in athletes}
        event_ids = {r["id_evento"] for r in events}
        discipline_ids = {r["id_disciplina"] for r in disciplines}
        entity_ids = {r["id_entidad"] for r in entities}
        noc_ids = {r["id_noc"] for r in nocs}
        venue_ids = {r["id_sede"] for r in venues}
        edition_ids = {r["id_edicion"] for r in editions}
        sport_ids = {r["id_deporte"] for r in sports}

        fk_specs = [
            ("PARTICIPACION.id_atleta", parts, "id_atleta", athlete_ids, False),
            ("PARTICIPACION.id_edicion", parts, "id_edicion", edition_ids, False),
            ("PARTICIPACION.id_evento", parts, "id_evento", event_ids, False),
            ("PARTICIPACION.id_noc", parts, "id_noc", noc_ids, True),
            ("PARTICIPACION.id_pais_nacionalidad", parts, "id_pais_nacionalidad", entity_ids, True),
            ("EVENTO.id_disciplina", events, "id_disciplina", discipline_ids, False),
            ("DISCIPLINA.id_deporte", disciplines, "id_deporte", sport_ids, False),
            ("EDICION_OLIMPICA.id_sede", editions, "id_sede", venue_ids, True),
            ("SEDE.id_pais", venues, "id_pais", entity_ids, False),
            ("NOC.id_entidad", nocs, "id_entidad", entity_ids, True),
            ("POBLACION.id_entidad", population, "id_entidad", entity_ids, False),
            ("ATLETA.id_pais_nacimiento", athletes, "id_pais_nacimiento", entity_ids, True),
            ("ATLETA.id_pais_nacionalidad", athletes, "id_pais_nacionalidad", entity_ids, True),
            ("ATLETA.id_pais_fallecimiento", athletes, "id_pais_fallecimiento", entity_ids, True),
        ]
        for label, child, field, parent, nullable in fk_specs:
            missing, sample = fk_check(child, field, parent, nullable)
            validation(validation_rows, f"FK {label}", 0, missing, "PASS" if missing == 0 else "FAIL", sample)

        # Messi regression over the materialized processed files.
        messi_rows = [r for r in athletes if r["id_atleta"] in {"110178", "167544"} and "messi" in (r["nombre"] + r["nombre_completo"]).lower()]
        messi_parts = [r for r in parts if r["id_atleta"] == "110178" and r["id_edicion"] == "47" and r["id_noc"] == "10" and r["id_evento"] == "303" and r["posicion"] == "1" and r["medalla"] == "Gold" and r["equipo"] == "Argentina"]
        messi_ok = len(messi_rows) == 1 and messi_rows[0]["id_atleta"] == "110178" and messi_rows[0]["fecha_nacimiento"] == "1987-06-24" and len(messi_parts) == 1
        validation(validation_rows, "Messi", "una identidad 110178 y una participación 2008/ARG/303/posición 1/Gold", f"identidades={len(messi_rows)}; participaciones={len(messi_parts)}", "PASS" if messi_ok else "FAIL")

        # Special-case regressions already approved in Block 4.
        edition_pairs = {(r["anio"], r["temporada"]) for r in editions}
        special = [
            ("1906_Intercalated_Games", ("1906", "Intercalated Games") in edition_pairs and ("1906", "Summer") not in edition_pairs),
            ("1956_Summer_without_Equestrian", ("1956", "Summer") in edition_pairs and not any(r["temporada"] == "Equestrian" for r in editions)),
            ("Youth_preserved", any(r["temporada"] in {"Summer Youth", "Winter Youth"} for r in editions)),
            ("Zappas_excluded_audited", (REPORTS / "excluded_non_official_participations.csv").exists() and rows(REPORTS / "excluded_non_official_participations.csv") > 0),
            ("NOC_historicos", len(nocs) == 236 and len(noc_ids) == 236),
            ("poblacion_geografia", len(population) == 17024),
        ]
        for name, ok in special:
            validation(validation_rows, name, "PASS", "PASS" if ok else "FAIL", "PASS" if ok else "FAIL")

        unicode = read_csv(REPORTS / "unicode_validation_phase7_1.csv") if (REPORTS / "unicode_validation_phase7_1.csv").exists() else read_csv(REPORTS / "unicode_validation_phase7.csv")
        unicode_ok = unicode[0].get("diferencias") == "0" and unicode[0].get("estado") == "PASS"
        validation(validation_rows, "Unicode", "0 diferencias", unicode[0].get("diferencias"), "PASS" if unicode_ok else "FAIL")
        synthetic = read_csv(REPORTS / "final_synthetic_regressions_phase7_1.csv")
        alias_ok = all(r["estado"] == "PASS" for r in synthetic)
        validation(validation_rows, "aliases_numericos_y_regresiones", "sin FAIL; sintéticos PASS", "todos PASS" if alias_ok else "hay FAIL", "PASS" if alias_ok else "FAIL")
        duplicate_plan = read_csv(REPORTS / "final_participation_merge_plan_phase7.csv")
        conflicts = [r for r in duplicate_plan if r.get("clasificacion") == "CONFLICT_PRESERVED"]
        conflict_ok = len(conflicts) == 94
        validation(validation_rows, "duplicados_conflictivos_preservados", 94, len(conflicts), "PASS" if conflict_ok else "FAIL")

        validation_ok = all(r["estado"] == "PASS" for r in validation_rows)
        manifest_after = [{"archivo": name, "filas": after_counts[name], "sha256": after_hashes[name]} for name in sorted(after_hashes)]
        write_csv(REPORTS / "processed_manifest_after_block4_apply.csv", ["archivo", "filas", "sha256"], manifest_after)
        write_csv(REPORTS / "block4_apply_report.csv", ["entidad", "filas_antes", "filas_despues", "diferencia", "sha_backup", "sha_preview", "sha_processed_final", "estado"], report_rows)
        write_csv(REPORTS / "block4_apply_validation.csv", ["validacion", "esperado", "actual", "estado", "detalle"], validation_rows)

        # Replace the official processed-count report with materialized counts.
        prior_counts = {r["entidad"]: r for r in read_csv(REPORTS / "processed_counts.csv")}
        count_rows = []
        for name in ["entidad_geografica", "poblacion", "noc", "atleta", "sede", "edicion_olimpica", "deporte", "disciplina", "evento", "participacion"]:
            old = prior_counts.get(name, {})
            count_rows.append({"entidad": name, "filas": after_counts[name + ".csv"], "pk_duplicadas": old.get("pk_duplicadas", "0"), "columnas_clave_con_null": old.get("columnas_clave_con_null", ""), "origen_registros": "block4_apply_materialized" if name in {"atleta", "evento", "participacion"} else old.get("origen_registros", "")})
        write_csv(REPORTS / "processed_counts.csv", ["entidad", "filas", "pk_duplicadas", "columnas_clave_con_null", "origen_registros"], count_rows)

        final_ok = validation_ok and all(r["estado"] == "MATCH" for r in report_rows)
        if not final_ok:
            raise RuntimeError("una validación posterior falló")
    except Exception as exc:
        failure = str(exc)
        if backup_created:
            for path in BACKUP.glob("*.csv"):
                shutil.copy2(path, PROCESSED / path.name)
        applied = False
        validation(validation_rows, "APLICACION_FINAL", "todas las validaciones PASS", "BLOCK4_APPLY_FAILED", "FAIL", failure)
        report_rows = []
        for path in sorted(PROCESSED.glob("*.csv")):
            report_rows.append({"entidad": path.stem.upper(), "filas_antes": before_counts.get(path.name, ""), "filas_despues": rows(path), "diferencia": rows(path) - before_counts.get(path.name, rows(path)), "sha_backup": before_hashes.get(path.name, ""), "sha_preview": sha256(PREVIEW / path.name) if path.name in APPLIED else "", "sha_processed_final": sha256(path), "estado": "RESTORED" if backup_created else "NOT_APPLIED"})
        write_csv(REPORTS / "block4_apply_report.csv", ["entidad", "filas_antes", "filas_despues", "diferencia", "sha_backup", "sha_preview", "sha_processed_final", "estado"], report_rows)
        write_csv(REPORTS / "block4_apply_validation.csv", ["validacion", "esperado", "actual", "estado", "detalle"], validation_rows)

    status = "BLOCK4_APPLY_SUCCESS" if applied and not failure else "BLOCK4_APPLY_FAILED"
    (REPORTS / "block4_apply_final.md").write_text(
        f"# Aplicación oficial del Bloque 4\n\n**Estado:** {status}\n\n"
        f"**Declaración:** {'BLOQUE 4 CORREGIDO Y APROBADO' if status == 'BLOCK4_APPLY_SUCCESS' else 'BLOCK4_APPLY_FAILED'}\n\n"
        f"Se aplicaron únicamente atleta.csv, evento.csv y participacion.csv desde data/preview_phase7/.\n"
        f"SQL Server no fue modificado y no se ejecutaron scripts de carga SQL.\n"
        f"Backup: data/backup_before_block4_apply/\n"
        f"Detalle de error: {failure or 'ninguno'}\n",
        encoding="utf-8",
    )
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
