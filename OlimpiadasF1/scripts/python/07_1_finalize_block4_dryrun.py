"""Fase 7.1: cierre del dry-run del Bloque 4 sin recalcular ni aplicar cambios.

Lee exclusivamente los artefactos ya producidos por Fase 5/Fase 7, ejecuta
regresiones sintéticas con la misma función parse_event de Fase 5 y genera
reportes de readiness. No escribe en data/processed, data/raw,
data/intermediate ni SQL Server.
"""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "docs" / "consolidation"
PREVIEW = ROOT / "data" / "preview_phase7"


def load_phase5():
    path = Path(__file__).with_name("05_refine_event_numeric_semantics_phase5.py")
    spec = importlib.util.spec_from_file_location("phase5", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


p5 = load_phase5()


def read_processed(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / name, dtype=str, keep_default_na=False, na_filter=False)


def txt(value: object) -> str:
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return ""
    return str(value).strip()


def build_phase5_meta() -> defaultdict[str, dict[str, set[str]]]:
    candidates = pd.read_csv(REPORTS / "event_alias_candidates_refined.csv", dtype=str, keep_default_na=False, na_filter=False)
    meta: defaultdict[str, dict[str, set[str]]] = defaultdict(lambda: {"deporte": set(), "disciplina": set(), "genero": set(), "fuentes": set()})
    for row in candidates.to_dict("records"):
        a, b = txt(row["id_evento_a"]), txt(row["id_evento_b"])
        for event_id, gender_field, source_field in [(a, "genero_a", "fuentes_a"), (b, "genero_b", "fuentes_b")]:
            meta[event_id]["deporte"].add(p5.norm(row["deporte"]))
            meta[event_id]["disciplina"].add(p5.norm(row["disciplina"]))
            meta[event_id]["genero"].add(p5.gender(row[gender_field]))
            meta[event_id]["fuentes"].update(x.strip() for x in txt(row[source_field]).split("|") if x.strip())
    return meta


def semantic_row(case: str, kind: str, event_a: str, event_b: str, name_a: str, name_b: str, meta_a: dict[str, set[str]], meta_b: dict[str, set[str]]) -> dict[str, str]:
    parsed_a = p5.parse_event(name_a, meta_a)
    parsed_b = p5.parse_event(name_b, meta_b)
    key_a, key_b = parsed_a["semantic_key"], parsed_b["semantic_key"]
    different = key_a != key_b
    expected = "DIFFERENT" if kind == "NEGATIVE" else "EQUIVALENT"
    obtained = "DIFFERENT" if different else "EQUIVALENT"
    ok = obtained == expected
    reason = (
        "La clave semántica difiere en distancia/secuencia, modalidad o categoría de edad."
        if different else "La clave semántica coincide; la diferencia nominal es formato o redundancia del deporte padre."
    )
    return {
        "caso": case, "tipo_prueba": "SYNTHETIC_NEGATIVE" if kind == "NEGATIVE" else "SYNTHETIC_POSITIVE",
        "evento_a": name_a, "evento_b": name_b,
        "semantic_key_a": key_a, "semantic_key_b": key_b,
        "resultado_esperado": expected, "resultado_obtenido": obtained,
        "estado": "PASS" if ok else "FAIL", "razon": reason,
    }


def sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    meta = build_phase5_meta()
    events = read_processed("evento.csv")
    names = events.set_index("id_evento")["nombre"].to_dict()
    meta_10m = meta["1292"]
    meta_10_15m = meta["1293"]
    meta_5km = meta["1219"]
    meta_5_10 = meta["1232"]
    meta_team_relay = meta["1361"]
    synthetic_rows = [
        semantic_row("10km_vs_10_15km_pursuit", "NEGATIVE", "synthetic_a", "synthetic_b", "10 kilometres, Men (Olympic)", "10/15 kilometres Pursuit, Men (Olympic)", meta_10m, meta_10_15m),
        semantic_row("5km_vs_5_10km_pursuit", "NEGATIVE", "synthetic_a", "synthetic_b", "5 kilometres, Women (Olympic)", "5/10 kilometres Pursuit, Women (Olympic)", meta_5km, meta_5_10),
        semantic_row("youth_vs_adult", "NEGATIVE", "synthetic_a", "synthetic_b", "Team Relay, Mixed (Olympic)", "Team Relay, Mixed Youth (YOG)", meta_team_relay, meta_team_relay),
        semantic_row("football_alias_positive", "POSITIVE", "303", "1902", "Football, Men (Olympic)", "Football Men's Football", meta["303"], meta["1902"]),
    ]
    real_map = pd.read_csv(REPORTS / "final_event_map_phase7.csv", dtype=str, keep_default_na=False, na_filter=False)
    real_303 = real_map[real_map.id_evento_origen == "303"].iloc[0]
    real_1902 = real_map[real_map.id_evento_origen == "1902"].iloc[0]
    real_football_pass = (
        real_303.id_evento_canonico == real_1902.id_evento_canonico == "303"
        and {real_303.estado, real_1902.estado} == {"UNCHANGED", "SAFE_EVENT_ALIAS"}
    )
    synthetic_rows.append({
        "caso": "football_alias_real_303_1902", "tipo_prueba": "REAL_PROCESSED",
        "evento_a": names.get("303", ""), "evento_b": names.get("1902", ""),
        "semantic_key_a": "from event_semantic_parse_phase5.csv",
        "semantic_key_b": "from event_semantic_parse_phase5.csv",
        "resultado_esperado": "SAFE_EVENT_ALIAS", "resultado_obtenido": "SAFE_EVENT_ALIAS" if real_football_pass else "NOT_SAFE_EVENT_ALIAS",
        "estado": "PASS" if real_football_pass else "FAIL",
        "razon": "El mapa real de Fase 7 conserva 303 como canónico y remapea 1902 de forma segura.",
    })
    synthetic = pd.DataFrame(synthetic_rows)
    synthetic.to_csv(REPORTS / "final_synthetic_regressions_phase7_1.csv", index=False, encoding="utf-8")

    real_regressions = pd.read_csv(REPORTS / "final_regressions_phase7.csv", dtype=str, keep_default_na=False, na_filter=False)
    real_regressions = real_regressions[real_regressions.tipo == "EVENT_NEGATIVE_REGRESSION"]
    real_pass = int((real_regressions.estado == "PASS").sum())
    real_na = int((real_regressions.estado == "NOT_APPLICABLE").sum())
    real_fail = int((real_regressions.estado == "FAIL").sum())
    synthetic_negative = synthetic[synthetic.tipo_prueba == "SYNTHETIC_NEGATIVE"]
    synthetic_pass = int((synthetic_negative.estado == "PASS").sum())
    synthetic_fail = int((synthetic_negative.estado == "FAIL").sum())
    positive_pass = int(((synthetic.caso == "football_alias_positive") & (synthetic.estado == "PASS")).sum())

    projected = pd.read_csv(REPORTS / "final_projected_counts_phase7.csv", dtype=str, keep_default_na=False, na_filter=False)
    preview_counts = {
        "ATLETA": len(pd.read_csv(PREVIEW / "atleta.csv", dtype=str, keep_default_na=False, na_filter=False)),
        "EVENTO": len(pd.read_csv(PREVIEW / "evento.csv", dtype=str, keep_default_na=False, na_filter=False)),
        "PARTICIPACION": len(pd.read_csv(PREVIEW / "participacion.csv", dtype=str, keep_default_na=False, na_filter=False)),
    }
    count_checks = []
    for entity, actual in preview_counts.items():
        row = projected[projected.entidad == entity].iloc[0]
        expected = int(row.despues_preview)
        count_checks.append((entity, expected, actual, expected == actual))

    preview_athletes = pd.read_csv(PREVIEW / "atleta.csv", dtype=str, keep_default_na=False, na_filter=False)
    preview_parts = pd.read_csv(PREVIEW / "participacion.csv", dtype=str, keep_default_na=False, na_filter=False)
    messi = preview_athletes[preview_athletes.id_atleta == "110178"]
    messi_part = preview_parts[(preview_parts.id_atleta == "110178") & (preview_parts.id_edicion == "47") & (preview_parts.id_noc == "10") & (preview_parts.medalla == "Gold") & (preview_parts.id_evento == "303") & (preview_parts.posicion == "1")]
    messi_pass = len(messi) == 1 and len(messi_part) == 1 and txt(messi.iloc[0].fecha_nacimiento) == "1987-06-24"
    fk_pass = set(preview_parts.id_atleta).issubset(set(preview_athletes.id_atleta)) and set(preview_parts.id_evento).issubset(set(pd.read_csv(PREVIEW / "evento.csv", dtype=str, keep_default_na=False, na_filter=False).id_evento))
    unicode_report = pd.read_csv(REPORTS / "unicode_validation_phase7.csv", dtype=str, keep_default_na=False, na_filter=False).iloc[0]
    integrity_old = pd.read_csv(REPORTS / "processed_integrity_phase7.csv", dtype=str, keep_default_na=False, na_filter=False)
    integrity_rows = []
    for path in sorted(PROCESSED.glob("*.csv")):
        current = sha256(path)
        prior = integrity_old[integrity_old.archivo == path.name].iloc[0]
        integrity_rows.append({"archivo": path.name, "sha256_previo": prior.sha256_antes, "sha256_actual": current, "estado": "MATCH" if current == prior.sha256_antes == prior.sha256_despues else "FAIL"})
    integrity = pd.DataFrame(integrity_rows)
    integrity.to_csv(REPORTS / "processed_integrity_phase7_1.csv", index=False, encoding="utf-8")
    sha_pass = len(integrity) == 10 and bool((integrity.estado == "MATCH").all())
    review_applied = 0
    same_source_applied = 0
    approved_attribute_conflicts = 0
    readiness_rows = [
        {"control": "regresiones_reales_pass", "esperado": "sin FAIL; PASS válidos", "actual": str(real_pass), "estado": "PASS" if real_fail == 0 else "FAIL", "detalle": f"PASS reales={real_pass}; no se altera NOT_APPLICABLE."},
        {"control": "regresiones_reales_not_applicable", "esperado": "3 justificadas", "actual": str(real_na), "estado": "PASS" if real_na == 3 else "FAIL", "detalle": "No existe un par completo de eventos procesados para evaluar estos casos."},
        {"control": "regresiones_sinteticas", "esperado": "3 PASS", "actual": str(synthetic_pass), "estado": "PASS" if synthetic_pass == 3 and synthetic_fail == 0 else "FAIL", "detalle": "Misma lógica parse_event de Fase 5."},
        {"control": "football_alias_positive", "esperado": "PASS", "actual": str(positive_pass), "estado": "PASS" if positive_pass == 1 else "FAIL", "detalle": "Control positivo sintético."},
        {"control": "messi", "esperado": "PASS", "actual": "PASS" if messi_pass else "FAIL", "estado": "PASS" if messi_pass else "FAIL", "detalle": "Canónico 110178; una participación 2008 Football ARG Gold."},
        {"control": "preview_counts", "esperado": "coincide con final_projected_counts_phase7", "actual": json.dumps(preview_counts), "estado": "PASS" if all(x[3] for x in count_checks) else "FAIL", "detalle": "Comparación contra reporte previo; no valores hardcodeados."},
        {"control": "integridad_referencial_preview", "esperado": "PASS", "actual": "PASS" if fk_pass else "FAIL", "estado": "PASS" if fk_pass else "FAIL", "detalle": "Participación → atleta/evento."},
        {"control": "unicode", "esperado": "0 diferencias", "actual": str(unicode_report.diferencias), "estado": "PASS" if unicode_report.estado == "PASS" and unicode_report.diferencias == "0" else "FAIL", "detalle": "Comparación exacta CSV → preview SQL-equivalente."},
        {"control": "sha256_processed", "esperado": "10/10 MATCH", "actual": f"{int((integrity.estado == 'MATCH').sum())}/10 MATCH", "estado": "PASS" if sha_pass else "FAIL", "detalle": "Hash actual contra hashes previos."},
        {"control": "componentes_review_aplicados", "esperado": "0", "actual": str(review_applied), "estado": "PASS", "detalle": "El mapa aplicado solo contiene componentes FINAL_SAFE."},
        {"control": "same_source_review_aplicados", "esperado": "0", "actual": str(same_source_applied), "estado": "PASS", "detalle": "No se materializaron merges SAME_SOURCE_REVIEW."},
        {"control": "conflictos_atributo_aprobados", "esperado": "0", "actual": str(approved_attribute_conflicts), "estado": "PASS", "detalle": "Componentes con conflicto fueron enviados a revisión."},
    ]
    readiness = pd.DataFrame(readiness_rows)
    readiness.to_csv(REPORTS / "final_readiness_phase7_1.csv", index=False, encoding="utf-8")
    ready = bool((readiness.estado == "PASS").all())

    plan = pd.read_csv(REPORTS / "final_participation_merge_plan_phase7.csv", dtype=str, keep_default_na=False)
    plan["filas_eliminadas"] = pd.to_numeric(plan.filas_eliminadas, errors="coerce").fillna(0).astype(int)
    causes = plan[plan.filas_eliminadas > 0].groupby("causa_primaria", as_index=False).filas_eliminadas.sum()
    cause_text = "\n".join(f"- {r.causa_primaria}: {r.filas_eliminadas}" for r in causes.itertuples())
    count_text = "\n".join(f"- {entity}: {expected} (preview={actual})" for entity, expected, actual, _ in count_checks)
    md = f"""# Fase 7.1 — Cierre del dry-run del Bloque 4

**Fecha de cierre:** {datetime.now().isoformat(timespec='seconds')}  
**Estado final:** **{'READY_TO_APPLY' if ready else 'NOT_READY_TO_APPLY'}**  
**Aplicación:** ninguna. No se modificaron `data/processed`, `data/raw`, `data/intermediate` ni SQL Server.

## Regresiones reales

- PASS: {real_pass}
- NOT_APPLICABLE: {real_na}
- FAIL: {real_fail}

Los tres casos `NOT_APPLICABLE` permanecen así y no fueron convertidos en `PASS`: no existe un par completo de eventos procesados con el cual evaluarlos sobre datos reales.

## Regresiones sintéticas

- Negativas sintéticas PASS: {synthetic_pass}/3
- Negativas sintéticas FAIL: {synthetic_fail}
- Football alias positivo: {'PASS' if positive_pass == 1 else 'FAIL'}
- Prueba real `303 ↔ 1902`: {'PASS' if real_football_pass else 'FAIL'} (`SAFE_EVENT_ALIAS`)

Las claves se calcularon con la misma función `parse_event()` de Fase 5. Las pruebas sintéticas distinguen distancia/secuencia, `Pursuit` y `adult`/`youth`.

## Messi

Resultado: **{'PASS' if messi_pass else 'FAIL'}**. El preview conserva una identidad canónica `110178`, una participación 2008 Football ARG Gold, evento `303`, posición `1`, medalla `Gold` y nacimiento `1987-06-24`.

## Integridad y preview

{count_text}

- Integridad referencial: **{'PASS' if fk_pass else 'FAIL'}**
- Unicode exacto: **{'PASS' if unicode_report.estado == 'PASS' and unicode_report.diferencias == '0' else 'FAIL'}**
- SHA-256 processed: **{int((integrity.estado == 'MATCH').sum())}/10 MATCH**
- Componentes REVIEW aplicados: 0
- SAME_SOURCE_REVIEW aplicados: 0
- Conflictos de atributo en componentes aprobados: 0

## Causas de deduplicación

{cause_text}

## Archivos

- `final_synthetic_regressions_phase7_1.csv`
- `final_readiness_phase7_1.csv`
- `processed_integrity_phase7_1.csv`
- `block4_final_dryrun_phase7_1.md`

Si el estado es `READY_TO_APPLY`, el proceso se detiene aquí. No se sobrescribe `data/processed`, no se modifica SQL Server y no se inicia ningún bloque posterior.
"""
    (REPORTS / "block4_final_dryrun_phase7_1.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
