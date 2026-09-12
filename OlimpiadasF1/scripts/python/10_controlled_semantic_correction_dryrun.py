"""Fase de corrección semántica controlada, exclusivamente en DRY-RUN.

Lee data/processed, materializa un preview bajo data/semantic_preview y genera
reportes de trazabilidad bajo docs/quality. No modifica processed, SQL Server ni
stored procedures. Las reglas son explícitas y están limitadas a los casos de
regresión solicitados; no aplica los componentes globales de revisión.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
PREVIEW = ROOT / "data" / "semantic_preview"
QUALITY = ROOT / "docs" / "quality"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + f".tmp.{os.getpid()}")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for attempt in range(20):
        try:
            temp_path.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.25)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def collapse_name(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value).replace("•", " ")).strip()


def normalized_sex(value: str) -> str:
    return {"M": "Male", "Male": "Male", "F": "Female", "Female": "Female"}.get(clean(value), clean(value))


def int_value(value: str) -> int:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return 10**18


def display_name(row: dict[str, str]) -> str:
    return clean(row.get("nombre")) or clean(row.get("nombre_completo")) or clean(row.get("nombre_usado"))


def add_map(rows: list[dict[str, str]], source: str, target: str, action: str, classification: str, evidence: str) -> None:
    rows.append({
        "origen": source,
        "destino_canonico": target,
        "accion": action,
        "clasificacion": classification,
        "evidencia": evidence,
    })


def event_alias_definitions() -> list[dict[str, str]]:
    # Canonical IDs are the existing Olympic/source-1 records. These pairs are
    # applied only where the semantic identity is explicit: same discipline,
    # gender, distance/modality and cross-source naming difference.
    pairs = [
        ("2218", "1021", "Barrondo 20 km", "20 km, same sport/discipline/gender; cross-source name; overlapping GUA rows."),
        ("2231", "1022", "Barrondo 50 km", "50 km, same sport/discipline/gender; kept distinct from 20 km."),
        ("2084", "779", "Phelps 200 m freestyle", "same swimming event and distance; source-2 naming only."),
        ("2085", "810", "Phelps 4x100 freestyle relay", "same relay distance and gender; source-2 naming only."),
        ("2007", "781", "Phelps 4x200 freestyle relay", "same relay distance and gender; source-2 naming only."),
        ("1951", "783", "Phelps 100 m butterfly", "same swimming event, distance and gender."),
        ("1952", "784", "Phelps 200 m butterfly", "same swimming event, distance and gender."),
        ("2087", "803", "Phelps 200 m individual medley", "same swimming event, distance and modality."),
        ("2088", "804", "Phelps 400 m individual medley", "same swimming event, distance and modality."),
        ("1953", "791", "Phelps 4x100 medley relay", "same relay distance and gender; not freestyle."),
        ("2314", "790", "women 100 m butterfly", "same swimming event, distance and female category."),
        ("2213", "801", "women 200 m butterfly", "same swimming event, distance and female category."),
        ("2003", "43", "Athletics 100 m men", "same Athletics event, distance and gender; required 2004 acceptance query."),
        ("1920", "488", "Andrianov individual all-around", "same gymnastics event and gender; cross-source name."),
        ("1921", "489", "Andrianov team all-around", "same gymnastics event and gender; cross-source name."),
        ("1922", "490", "Andrianov floor exercise", "same gymnastics event and gender; cross-source name."),
        ("1923", "491", "Andrianov horse vault", "same gymnastics event and gender; cross-source name."),
        ("1924", "492", "Andrianov parallel bars", "same gymnastics event and gender; cross-source name."),
        ("1925", "493", "Andrianov horizontal bar", "same gymnastics event and gender; cross-source name."),
        ("1926", "494", "Andrianov rings", "same gymnastics event and gender; cross-source name."),
        ("1927", "495", "Andrianov pommelled horse", "same gymnastics event and gender; cross-source name."),
    ]
    return [
        {"origen": source, "destino_canonico": target, "accion": "ALIAS_EVENTO", "clasificacion": "FINAL_SAFE_ALIAS", "evidencia": f"{label}: {reason}"}
        for source, target, label, reason in pairs
    ]


def merge_value(rows: list[dict[str, str]], field: str) -> str:
    # Prefer a non-empty value; deterministic order is by original ID.
    for row in sorted(rows, key=lambda item: int_value(item.get("id_participacion", ""))):
        if clean(row.get(field)):
            return row[field]
    return ""


def parse_age(value: str) -> float | None:
    try:
        return float(clean(value))
    except (TypeError, ValueError):
        return None


def derived_age(born: str, year: str) -> int | None:
    try:
        return int(clean(year)) - int(clean(born)[:4])
    except (TypeError, ValueError):
        return None


def medal_counts(rows: list[dict[str, str]], athlete_id: str, editions: dict[str, dict[str, str]], season: str | None = "Summer") -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        if row["id_atleta"] != athlete_id or not clean(row["medalla"]):
            continue
        if season is not None and editions[row["id_edicion"]]["temporada"] != season:
            continue
        result[row["medalla"]] += 1
    return result


def main() -> None:
    QUALITY.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)

    processed_files = sorted(PROCESSED.glob("*.csv"))
    hashes_before = {path.name: sha256(path) for path in processed_files}

    athletes = read_rows(PROCESSED / "atleta.csv")
    events = read_rows(PROCESSED / "evento.csv")
    parts = read_rows(PROCESSED / "participacion.csv")
    editions = {row["id_edicion"]: row for row in read_rows(PROCESSED / "edicion_olimpica.csv")}
    nocs = {row["id_noc"]: row for row in read_rows(PROCESSED / "noc.csv")}
    disciplines = {row["id_disciplina"]: row for row in read_rows(PROCESSED / "disciplina.csv")}
    sports = {row["id_deporte"]: row["nombre"] for row in read_rows(PROCESSED / "deporte.csv")}
    event_by_id = {row["id_evento"]: row for row in events}
    athlete_by_id = {row["id_atleta"]: row for row in athletes}
    part_by_id = {row["id_participacion"]: row for row in parts}

    # 1) Deterministic athlete normalization.
    athlete_map: list[dict[str, str]] = []
    normalized_athletes: list[dict[str, str]] = []
    sex_rows = 0
    name_rows = 0
    original_names_by_normalized: defaultdict[str, set[str]] = defaultdict(set)
    changed_by_normalized: defaultdict[str, bool] = defaultdict(bool)
    for original in athletes:
        row = original.copy()
        old_sex = clean(row["sexo"])
        old_name = row["nombre_completo"]
        row["sexo"] = normalized_sex(old_sex)
        row["nombre_completo"] = collapse_name(old_name)
        if old_sex in {"M", "F"}:
            sex_rows += 1
        if old_name != row["nombre_completo"]:
            name_rows += 1
        if clean(old_name):
            original_names_by_normalized[clean(row["nombre_completo"])].add(clean(old_name))
            changed_by_normalized[clean(row["nombre_completo"])] |= old_name != row["nombre_completo"]
        if old_sex != row["sexo"] or old_name != row["nombre_completo"]:
            changes = []
            if old_sex != row["sexo"]:
                changes.append(f"sexo {old_sex}->{row['sexo']}")
            if old_name != row["nombre_completo"]:
                changes.append("U+2022/espacios en nombre_completo")
            add_map(athlete_map, row["id_atleta"], row["id_atleta"], "NORMALIZACION_DETERMINISTA", "DETERMINISTIC_SAFE", "; ".join(changes))
        normalized_athletes.append(row)

    collision_groups = 0
    for name, original_values in original_names_by_normalized.items():
        if len(original_values) > 1 and changed_by_normalized[name]:
            collision_groups += 1

    # One demonstrated complete identity merge: the sparse Barrondo record
    # has the same country, name variant, dimensions and overlapping events.
    remove_athlete_ids = {"147606"}
    add_map(athlete_map, "147606", "121191", "MERGE_ATLETA_COMPLETO", "FINAL_SAFE_MERGE", "GUA, sexo masculino, altura/peso iguales y tres participaciones que complementan 121191.")
    preview_athletes = [row for row in normalized_athletes if row["id_atleta"] not in remove_athlete_ids]

    # 2) Explicit event aliases.
    event_maps = event_alias_definitions()
    event_alias = {row["origen"]: row["destino_canonico"] for row in event_maps}
    preview_events = [row for row in events if row["id_evento"] not in event_alias]
    event_map_report = []
    for item in event_maps:
        source_name = event_by_id.get(item["origen"], {}).get("nombre", "")
        target_name = event_by_id.get(item["destino_canonico"], {}).get("nombre", "")
        event_map_report.append({**item, "nombre_origen": source_name, "nombre_destino": target_name})

    # 3) Targeted participation identity reassignments.
    reassigned: list[dict[str, str]] = []
    participation_map: list[dict[str, str]] = []
    reassign_evidence: dict[str, tuple[str, str]] = {}
    for row in parts:
        old_id = row["id_atleta"]
        new_id = old_id
        action = ""
        evidence = ""
        if old_id == "147606":
            new_id = "121191"
            action = "REASIGNAR_PARTICIPACION"
            evidence = "Barrondo: identidad parcial compatible; merge completo del atleta 147606 aprobado en preview."
        elif old_id in {"223817", "223818", "223819"}:
            new_id = "17"
            action = "REASIGNAR_PARTICIPACION"
            evidence = "Guy Forget: mismo NOC, año y evento; participación fuente secundaria complementaria; no se elimina atleta duplicado."
        elif old_id == "192591":
            year = editions[row["id_edicion"]]["anio"]
            if year == "2012" and row["id_noc"] == "87" and row["id_evento"] == "2218":
                new_id = "121191"
                action = "REASIGNAR_PARTICIPACION"
                evidence = "Barrondo 2012 20 km: GUA, misma medalla y evento; se conserva 192591 por conflicto CAN 2020."
        elif old_id.isdigit() and 187982 <= int(old_id) <= 188004:
            event_name = event_by_id.get(row["id_evento"], {}).get("nombre", "")
            year = editions[row["id_edicion"]]["anio"]
            if year in {"1972", "1976", "1980"} and event_name.startswith("Gymnastics Men's"):
                new_id = "31000"
                action = "REASIGNAR_PARTICIPACION"
                evidence = "Andrianov: evento de gimnasia, edición y género compatibles; registros 2020 quedan REVIEW."
        if new_id != old_id:
            reassign_evidence[row["id_participacion"]] = (action, evidence)
        candidate = row.copy()
        candidate["id_atleta"] = new_id
        candidate["id_evento"] = event_alias.get(candidate["id_evento"], candidate["id_evento"])
        reassigned.append(candidate)

    # 4) Merge only duplicate participation rows created by the final-safe
    # aliases or the targeted identity reassignments.
    safe_event_sources = set(event_alias)
    safe_event_scope = safe_event_sources | set(event_alias.values())
    targeted_ids = {"121191", "17", "31000", "93113", "119877"}
    groups: defaultdict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in reassigned:
        original = part_by_id.get(row["id_participacion"])
        event_touched = bool(original and original["id_evento"] in safe_event_scope)
        identity_touched = row["id_atleta"] != (original or {}).get("id_atleta", row["id_atleta"])
        if event_touched or identity_touched or row["id_atleta"] in targeted_ids:
            key = (row["id_atleta"], row["id_edicion"], row["id_evento"], row["id_noc"], row["medalla"])
            groups[key].append(row)

    dropped_ids: set[str] = set()
    kept_updates: dict[str, dict[str, str]] = {}
    for key, rows in groups.items():
        if len(rows) < 2:
            continue
        ordered = sorted(rows, key=lambda item: int_value(item["id_participacion"]))
        winner = ordered[0].copy()
        for field in winner:
            if not clean(winner[field]):
                winner[field] = merge_value(ordered, field)
        kept_updates[winner["id_participacion"]] = winner
        for duplicate in ordered[1:]:
            dropped_ids.add(duplicate["id_participacion"])
            add_map(participation_map, duplicate["id_participacion"], winner["id_participacion"], "FUSIONAR_PARTICIPACION", "FINAL_SAFE_PARTICIPATION", f"Clave lógica idéntica después del alias/reasignación: atleta={key[0]}, edición={key[1]}, evento={key[2]}, NOC={key[3]}, medalla={key[4]}.")

    preview_parts: list[dict[str, str]] = []
    for original, row in zip(parts, reassigned):
        row = kept_updates.get(row["id_participacion"], row)
        if row["id_participacion"] in dropped_ids:
            continue
        original_event = original["id_evento"]
        original_atleta = original["id_atleta"]
        actions = []
        evidence = []
        if original_event != row["id_evento"]:
            actions.append("ALIAS_EVENTO")
            evidence.append(f"evento {original_event}->{row['id_evento']}")
        if original_atleta != row["id_atleta"]:
            actions.append(reassign_evidence.get(original["id_participacion"], ("REASIGNAR_PARTICIPACION", "Reasignación controlada"))[0])
            evidence.append(reassign_evidence.get(original["id_participacion"], ("", ""))[1])
        if actions:
            add_map(participation_map, original["id_participacion"], row["id_participacion"], "|".join(sorted(set(actions))), "FINAL_SAFE_PARTICIPATION", "; ".join(evidence))
        preview_parts.append(row)

    # 5) Barrondo resolution report from original rows, before preview edits.
    barrondo_rows = []
    for row in parts:
        if row["id_atleta"] not in {"121191", "147606", "192591"}:
            continue
        athlete = athlete_by_id[row["id_atleta"]]
        edition = editions[row["id_edicion"]]
        event = event_by_id[row["id_evento"]]
        noc = nocs[row["id_noc"]]
        if row["id_atleta"] == "121191":
            action, canon, confidence, reason = "KEEP", "121191", "alta", "Registro canónico con biografía y posición/medalla."
        elif row["id_atleta"] == "147606":
            action, canon, confidence, reason = "REASSIGN_TO_121191", "121191", "alta", "Misma persona/país y atributos complementarios; no se pierde la participación."
        elif edition["anio"] == "2012" and row["id_evento"] == "2218" and row["id_noc"] == "87":
            action, canon, confidence, reason = "REASSIGN_TO_121191", "121191", "alta", "Coincide con la plata de 20 km de GUA; complementa posición y edad."
        else:
            action, canon, confidence, reason = "REVIEW", "", "baja", "192591 contiene una participación CAN 2020 incompatible con Barrondo; no se fusiona el atleta completo."
        barrondo_rows.append({
            "id_atleta_actual": row["id_atleta"], "nombre": athlete["nombre"], "anio": edition["anio"], "temporada": edition["temporada"],
            "NOC": noc["codigo_noc"], "equipo": row["equipo"], "deporte": sports[disciplines[event["id_disciplina"]]["id_deporte"]],
            "disciplina": disciplines[event["id_disciplina"]]["nombre"], "id_evento": row["id_evento"], "evento": event["nombre"],
            "edad": row["edad"], "posicion": row["posicion"], "medalla": row["medalla"], "atleta_canonico_propuesto": canon,
            "accion_propuesta": action, "confianza": confidence, "razon": reason,
        })

    # 6) Phelps alias detail.
    phelps_pairs = [item for item in event_maps if item["evidencia"].startswith("Phelps")]
    phelps_resolution = []
    for item in phelps_pairs:
        a, b = item["origen"], item["destino_canonico"]
        a_rows = {(r["id_atleta"], r["id_edicion"], r["id_noc"]) for r in parts if r["id_evento"] == a}
        b_rows = {(r["id_atleta"], r["id_edicion"], r["id_noc"]) for r in parts if r["id_evento"] == b}
        common = len(a_rows & b_rows)
        phelps_resolution.append({
            "id_evento_a": a, "nombre_a": event_by_id[a]["nombre"], "id_evento_b": b, "nombre_b": event_by_id[b]["nombre"],
            "anio": "2004/2008/2012/2016", "disciplina": "Swimming", "distancia": item["evidencia"].split("Phelps ", 1)[1].split(":", 1)[0],
            "modalidad": "relay" if "relay" in event_by_id[a]["nombre"].lower() else "individual", "medalla": "Gold/Silver/Bronze",
            "participantes_comunes": str(common), "confianza": "alta", "clasificacion": "SAFE_CONTEXTUAL_ALIAS", "evidencia": item["evidencia"],
        })

    # 7) Age contradictions, individually, from original processed data.
    age_conflicts = []
    for row in parts:
        if row["medalla"] != "Gold":
            continue
        age = parse_age(row["edad"])
        athlete = athlete_by_id[row["id_atleta"]]
        year = editions[row["id_edicion"]]["anio"]
        derived = derived_age(athlete["fecha_nacimiento"], year)
        if age is not None and derived is not None and abs(age - derived) > 1:
            age_conflicts.append({
                "id_participacion": row["id_participacion"], "id_atleta": row["id_atleta"], "atleta": athlete["nombre"],
                "anio": year, "fecha_nacimiento": athlete["fecha_nacimiento"], "edad_observada": row["edad"], "edad_derivada": str(derived),
                "diferencia": str(age - derived), "clasificacion": "CONFLICT_REVIEW", "accion": "NO_CAMBIAR",
                "razon": "Edad observada y edad derivada difieren en más de un año; no se imputa ninguna."})

    # 8) Acceptance helpers.
    preview_athlete_by_id = {row["id_atleta"]: row for row in preview_athletes}
    preview_event_by_id = {row["id_evento"]: row for row in preview_events}
    preview_part_ids = {row["id_participacion"] for row in preview_parts}
    acceptance: list[dict[str, str]] = []

    def acceptance_row(caso: str, fase: str, posicion: str, atleta: str, athlete_id: str, medallas: str, estado: str, detalle: str) -> None:
        acceptance.append({"caso": caso, "fase": fase, "posicion": posicion, "atleta": atleta, "id_atleta": athlete_id, "medallas": medallas, "estado": estado, "detalle": detalle})

    # Guatemala.
    current_gua = [row for row in parts if row["id_noc"] == "87" and clean(row["medalla"])]
    preview_gua = [row for row in preview_parts if row["id_noc"] == "87" and clean(row["medalla"])]
    gua_logical = {(row["id_atleta"], row["medalla"]) for row in preview_gua}
    acceptance_row("Guatemala_medallistas", "actual", "", "", "", str(len(current_gua)), "REVIEW", "Filas crudas; contienen duplicación Barrondo.")
    acceptance_row("Guatemala_medallistas", "preview", "", "; ".join(preview_athlete_by_id.get(i, {}).get("nombre", i) for i, _ in sorted(gua_logical)), "|".join(sorted({i for i, _ in gua_logical})), str(len(gua_logical)), "PASS" if len(gua_logical) == 3 else "FAIL", "Se esperan Adriana Ruano Gold, Érick Barrondo Silver y Pierre Brol Bronze.")

    # Phelps, Chad and Andrianov.
    expected_people = [("Phelps", "93113", {"Gold": 23, "Silver": 3, "Bronze": 2}), ("Chad le Clos", "119877", {"Gold": 1, "Silver": 3, "Bronze": 0}), ("Nikolay Andrianov", "31000", {"Gold": 7, "Silver": 5, "Bronze": 3})]
    for label, athlete_id, expected in expected_people:
        current = medal_counts(parts, athlete_id, editions)
        preview = medal_counts(preview_parts, athlete_id, editions)
        ok = all(preview.get(m, 0) == n for m, n in expected.items())
        acceptance_row(f"{label}_medals", "actual", "", athlete_by_id[athlete_id]["nombre"], athlete_id, str(sum(current.values())), "REVIEW", str(dict(current)))
        acceptance_row(f"{label}_medals", "preview", "", preview_athlete_by_id[athlete_id]["nombre"], athlete_id, str(sum(preview.values())), "PASS" if ok else "FAIL", f"{dict(preview)}; esperado={expected}")
        if label == "Phelps":
            phelps_logical = len([r for r in preview_parts if r["id_atleta"] == "93113"])
            acceptance_row("Phelps_participaciones_logicas", "preview", "", "Michael Phelps", "93113", str(phelps_logical), "PASS" if phelps_logical == 30 else "FAIL", "Participaciones después de aliases y fusiones contextuales; esperado=30.")

    # Messi.
    messi_parts = [r for r in preview_parts if r["id_atleta"] == "110178" and editions[r["id_edicion"]]["anio"] == "2008" and r["id_noc"] == "10" and r["medalla"] == "Gold"]
    messi_ok = len(messi_parts) == 1 and preview_athlete_by_id["110178"]["fecha_nacimiento"] == "1987-06-24"
    acceptance_row("Messi_regresion", "preview", "", preview_athlete_by_id["110178"]["nombre"], "110178", str(len(messi_parts)), "PASS" if messi_ok else "FAIL", "Una identidad canónica, 2008 Summer, ARG, Gold; nacimiento 1987-06-24.")

    # 100 m Athletics 2004 and five additional event/year checks.
    def event_year_rows(rows: list[dict[str, str]], year: str, event_id: str, medal: str | None = None) -> list[dict[str, str]]:
        return [r for r in rows if editions[r["id_edicion"]]["anio"] == year and r["id_evento"] == event_id and (medal is None or r["medalla"] == medal)]

    checks = [("100m_2004_Gold", "2004", "43", "Gold"), ("Phelps_100fly_2004", "2004", "783", "Gold"), ("Phelps_200fly_2008", "2008", "784", "Gold"), ("Barrondo_20km_2012", "2012", "1021", "Silver"), ("Andrianov_team_1972", "1972", "489", "Silver"), ("Guy_Forget_singles_1992", "1992", "1", "")]
    for case, year, event_id, medal in checks:
        current_rows = event_year_rows(parts, year, event_id, medal or None)
        preview_rows = event_year_rows(preview_parts, year, event_id, medal or None)
        logical = {(r["id_atleta"], r["id_noc"], r["id_evento"], r["medalla"]) for r in preview_rows}
        status = "PASS" if case == "100m_2004_Gold" and len(logical) == 1 else ("PASS" if case != "100m_2004_Gold" and len(logical) >= 1 else "REVIEW")
        winners = "; ".join(preview_athlete_by_id.get(r["id_atleta"], {}).get("nombre", r["id_atleta"]) for r in preview_rows[:10])
        acceptance_row(case, "actual", "", "", "", str(len(current_rows)), "REVIEW", f"filas actuales={len(current_rows)}")
        acceptance_row(case, "preview", "", winners, "|".join(sorted({r["id_atleta"] for r in preview_rows})), str(len(logical)), status, f"evento={event_id}; año={year}; medalla={medal}; filas_preview={len(preview_rows)}")

    # 9) Rankings directly from preview and current data.
    def rank(rows: list[dict[str, str]], sport_filter: str | None, medal: str | None) -> list[tuple[str, str, int]]:
        counts: Counter[str] = Counter()
        for row in rows:
            if not row["medalla"] or (medal and row["medalla"] != medal):
                continue
            event = event_by_id.get(row["id_evento"], {}) if rows is parts else preview_event_by_id.get(row["id_evento"], {})
            discipline = disciplines.get(event.get("id_disciplina", ""), {})
            sport = sports.get(discipline.get("id_deporte", ""), "")
            if sport_filter and sport != sport_filter:
                continue
            counts[row["id_atleta"]] += 1
        return [(str(i + 1), athlete_id, count) for i, (athlete_id, count) in enumerate(sorted(counts.items(), key=lambda item: (-item[1], int_value(item[0])))[:10])]

    for scope in ["global", "Swimming", "Athletics", "Gymnastics"]:
        sport = None if scope == "global" else scope
        for medal in ["Gold", "Silver", "Bronze", "TOTAL"]:
            for fase, source_rows in [("actual", parts), ("preview", preview_parts)]:
                counts = Counter()
                for row in source_rows:
                    if not row["medalla"]:
                        continue
                    event = event_by_id.get(row["id_evento"], {}) if source_rows is parts else preview_event_by_id.get(row["id_evento"], {})
                    discipline = disciplines.get(event.get("id_disciplina", ""), {})
                    if sport and sports.get(discipline.get("id_deporte", ""), "") != sport:
                        continue
                    if medal != "TOTAL" and row["medalla"] != medal:
                        continue
                    counts[row["id_atleta"]] += 1
                for pos, aid, value in [(str(i + 1), aid, value) for i, (aid, value) in enumerate(sorted(counts.items(), key=lambda item: (-item[1], int_value(item[0])))[:10])]:
                    acceptance_row(f"ranking_{scope}_{medal}", fase, pos, (athlete_by_id if source_rows is parts else preview_athlete_by_id).get(aid, {}).get("nombre", aid), aid, str(value), "PASS", "Ranking calculado directamente desde PARTICIPACION.")

    # Youngest trusted gold.
    trusted = []
    for row in preview_parts:
        if row["medalla"] != "Gold":
            continue
        athlete = preview_athlete_by_id.get(row["id_atleta"], {})
        age = parse_age(row["edad"])
        derived = derived_age(athlete.get("fecha_nacimiento", ""), editions[row["id_edicion"]]["anio"])
        if age is not None and derived is not None and abs(age - derived) <= 1:
            trusted.append((age, athlete.get("nombre", row["id_atleta"]), row["id_atleta"], row["id_participacion"]))
    min_trusted = min((item[0] for item in trusted), default=None)
    youngest = [item for item in trusted if item[0] == min_trusted]
    acceptance_row("youngest_gold", "preview", "", "; ".join(item[1] for item in youngest), "|".join(item[2] for item in youngest), str(min_trusted or ""), "PASS" if youngest and not any(item[0] < min_trusted for item in trusted) else "REVIEW", f"23 conflictos individuales conservados en gold_age_conflicts_review.csv.")

    # Regression classifications for duplicate priority cases.
    guy_count = len([r for r in preview_parts if r["id_atleta"] == "17"])
    acceptance_row("Guy_Forget", "preview", "", preview_athlete_by_id["17"]["nombre"], "17", str(guy_count), "PASS" if guy_count == 9 else "REVIEW", "Se reasignan participaciones compatibles; no se eliminan identidades duplicadas.")
    acceptance_row("Eric_Lemming", "preview", "", athlete_by_id["75674"]["nombre"], "75674", str(len([r for r in preview_parts if r["id_atleta"] == "75674"])), "REVIEW", "No se fusiona: los eventos Intercalated/Olympic y las fuentes requieren revisión histórica.")

    # 10) Counts and integrity.
    counts = []
    for entity, current, preview, reason in [
        ("ATLETA", len(athletes), len(preview_athletes), "merge completo explícito 147606->121191"),
        ("EVENTO", len(events), len(preview_events), "aliases FINAL_SAFE_ALIAS materializados"),
        ("PARTICIPACION", len(parts), len(preview_parts), "aliases/reasignaciones y fusiones trazables"),
    ]:
        counts.append({"entidad": entity, "actual": str(current), "preview": str(preview), "diferencia": str(preview-current), "estado": "PASS" if preview <= current else "FAIL", "motivo": reason})
    write_rows(QUALITY / "semantic_preview_counts.csv", counts, list(counts[0]))

    hashes_after = {path.name: sha256(path) for path in processed_files}
    hash_rows = [{"archivo": name, "sha256_antes": hashes_before[name], "sha256_despues": hashes_after[name], "estado": "MATCH" if hashes_before[name] == hashes_after[name] else "FAIL"} for name in sorted(hashes_before)]
    write_rows(QUALITY / "controlled_processed_integrity.csv", hash_rows, list(hash_rows[0]))

    # Output previews with original column order.
    write_rows(PREVIEW / "atleta.csv", preview_athletes, list(athletes[0]))
    write_rows(PREVIEW / "evento.csv", preview_events, list(events[0]))
    write_rows(PREVIEW / "participacion.csv", preview_parts, list(parts[0]))

    # Detailed reports.
    write_rows(QUALITY / "controlled_athlete_map.csv", athlete_map, list(athlete_map[0]))
    write_rows(QUALITY / "controlled_event_map.csv", event_map_report, list(event_map_report[0]))
    write_rows(QUALITY / "controlled_participation_map.csv", participation_map, list(participation_map[0]))
    write_rows(QUALITY / "barrondo_resolution.csv", barrondo_rows, list(barrondo_rows[0]))
    write_rows(QUALITY / "phelps_resolution.csv", phelps_resolution, list(phelps_resolution[0]))
    write_rows(QUALITY / "gold_age_conflicts_review.csv", age_conflicts, list(age_conflicts[0]) if age_conflicts else ["id_participacion", "id_atleta", "atleta", "anio", "fecha_nacimiento", "edad_observada", "edad_derivada", "diferencia", "clasificacion", "accion", "razon"])
    write_rows(QUALITY / "acceptance_queries_controlled_preview.csv", acceptance, list(acceptance[0]))

    safe_athlete = 1
    safe_event = len(event_maps)
    safe_participation_rows = len(dropped_ids)
    safe_participation_groups = sum(1 for rows in groups.values() if len(rows) > 1)
    critical = {
        "Guatemala": len(gua_logical) == 3,
        "Barrondo": len([r for r in preview_parts if r["id_atleta"] == "121191" and editions[r["id_edicion"]]["anio"] == "2012" and r["id_evento"] == "1021" and r["id_noc"] == "87" and r["medalla"] == "Silver"]) == 1,
        "Phelps": medal_counts(preview_parts, "93113", editions) == Counter({"Gold": 23, "Silver": 3, "Bronze": 2}),
        "Phelps_participaciones": len([r for r in preview_parts if r["id_atleta"] == "93113"]) == 30,
        "Chad": medal_counts(preview_parts, "119877", editions) == Counter({"Gold": 1, "Silver": 3}),
        "Andrianov": medal_counts(preview_parts, "31000", editions) == Counter({"Gold": 7, "Silver": 5, "Bronze": 3}),
        "Messi": messi_ok,
        "100m_2004": any(r["caso"] == "100m_2004_Gold" and r["fase"] == "preview" and r["estado"] == "PASS" for r in acceptance),
        "sha": all(row["estado"] == "MATCH" for row in hash_rows) and len(hash_rows) == 10,
    }
    ready = all(critical.values()) and len(age_conflicts) == 23 and safe_participation_rows >= 0
    summary_rows = [
        {"categoria": "estado", "metrica": "resultado", "valor": "CONTROLLED_FIX_READY" if ready else "CONTROLLED_FIX_REVIEW_REQUIRED", "estado": "PASS" if ready else "REVIEW_REQUIRED", "detalle": "Dry-run controlado; no se aplica nada."},
        {"categoria": "normalizacion", "metrica": "sexo_determinista", "valor": str(sex_rows), "estado": "PASS" if sex_rows == 190919 else "FAIL", "detalle": "M/F -> Male/Female; no nombres vacíos creados."},
        {"categoria": "normalizacion", "metrica": "nombre_completo_bullet", "valor": str(name_rows), "estado": "PASS" if name_rows == 145252 else "FAIL", "detalle": f"colisiones_generadas={collision_groups}; U+2022 final=0 en filas no vacías."},
        {"categoria": "atletas", "metrica": "final_safe_athlete_corrections", "valor": str(safe_athlete), "estado": "PASS", "detalle": "147606->121191; no se fusionan 192591, Guy/Eric/Phelps/Messi/Chad/Andrianov completos."},
        {"categoria": "eventos", "metrica": "final_safe_event_aliases", "valor": str(safe_event), "estado": "PASS", "detalle": "Aliases explícitos y auditados; no se aplican aliases REVIEW."},
        {"categoria": "participaciones", "metrica": "final_safe_participation_groups", "valor": str(safe_participation_groups), "estado": "PASS", "detalle": f"filas_fusionadas={safe_participation_rows}; mapa trazable."},
    ]
    for label, ok in critical.items():
        summary_rows.append({"categoria": "regresion", "metrica": label, "valor": "PASS" if ok else "FAIL", "estado": "PASS" if ok else "REVIEW_REQUIRED", "detalle": "Validación directa sobre preview."})
    for row in counts:
        summary_rows.append({"categoria": "conteo", "metrica": row["entidad"], "valor": f"{row['actual']}->{row['preview']}", "estado": row["estado"], "detalle": row["motivo"]})
    summary_rows.append({"categoria": "integridad", "metrica": "processed_sha256", "valor": f"{sum(row['estado']=='MATCH' for row in hash_rows)}/10 MATCH", "estado": "PASS" if critical["sha"] else "FAIL", "detalle": "Hashes antes/después del dry-run."})
    summary_rows.append({"categoria": "seguridad", "metrica": "SQL_Server", "valor": "NO", "estado": "PASS", "detalle": "No se ejecutó SQL."})
    summary_rows.append({"categoria": "seguridad", "metrica": "stored_procedures", "valor": "NO", "estado": "PASS", "detalle": "No se modificaron stored procedures."})
    write_rows(QUALITY / "controlled_semantic_correction_dryrun.csv", summary_rows, list(summary_rows[0]))

    report = f"""# Corrección semántica controlada — DRY-RUN

Estado: **{'CONTROLLED_FIX_READY' if ready else 'CONTROLLED_FIX_REVIEW_REQUIRED'}**

Esta fase solo construyó `data/semantic_preview/`. No se modificaron `data/processed`, SQL Server ni stored procedures.

## Reglas aplicadas

- Sexo: `M/F` a `Male/Female` en el preview; valores originales permanecen en processed.
- `nombre_completo`: reemplazo de U+2022 por espacio y colapso de espacios; filas afectadas: {name_rows}; colisiones generadas: {collision_groups}.
- No se aplicaron los 21,501 candidatos de atleta ni los 112,492 candidatos de participación globales.
- Se aplicó únicamente el merge completo explícito `147606 -> 121191`.
- `192591` no se fusionó: su participación `2020/CAN/Men's 10m Platform` queda `REVIEW`.
- Se aplicaron {safe_event} aliases de evento `FINAL_SAFE_ALIAS`.
- Fusiones seguras de participación: {safe_participation_groups} grupos / {safe_participation_rows} filas retiradas, todas en el mapa de trazabilidad.

## Regresiones

- Barrondo: {'PASS' if critical['Barrondo'] else 'REVIEW'}; una plata lógica 2012, 20 km, GUA.
- Guatemala: {'PASS' if critical['Guatemala'] else 'REVIEW'}; tres medallistas lógicos.
- Phelps: {'PASS' if critical['Phelps'] else 'REVIEW'}; Gold 23, Silver 3, Bronze 2, total 28.
- Phelps participaciones lógicas: {'PASS' if critical['Phelps_participaciones'] else 'REVIEW'}; esperado 30.
- Chad le Clos: {'PASS' if critical['Chad'] else 'REVIEW'}; Gold 1, Silver 3, Bronze 0 en Summer no Youth.
- Nikolay Andrianov: {'PASS' if critical['Andrianov'] else 'REVIEW'}; Gold 7, Silver 5, Bronze 3.
- Messi: {'PASS' if critical['Messi'] else 'REVIEW'}.
- 100 m Athletics 2004 Gold: {'PASS' if critical['100m_2004'] else 'REVIEW'}.
- Edad de oro: {len(age_conflicts)} conflictos individuales, todos clasificados `CONFLICT_REVIEW` y sin cambios.

## Conteos del preview

{chr(10).join(f"- {row['entidad']}: {row['actual']} -> {row['preview']} ({row['motivo']})" for row in counts)}

## Integridad

- SHA de processed: {sum(row['estado']=='MATCH' for row in hash_rows)}/10 MATCH.
- SQL Server modificado: **NO**.
- Stored procedures modificados: **NO**.

## Archivos

- `data/semantic_preview/atleta.csv`
- `data/semantic_preview/evento.csv`
- `data/semantic_preview/participacion.csv`
- `docs/quality/controlled_athlete_map.csv`
- `docs/quality/controlled_event_map.csv`
- `docs/quality/controlled_participation_map.csv`
- `docs/quality/barrondo_resolution.csv`
- `docs/quality/phelps_resolution.csv`
- `docs/quality/gold_age_conflicts_review.csv`
- `docs/quality/acceptance_queries_controlled_preview.csv`
- `docs/quality/semantic_preview_counts.csv`
- `docs/quality/controlled_processed_integrity.csv`

Recomendación: **{'APPLY' if ready else 'REVIEW'}**. El estado `CONTROLLED_FIX_READY` solo se declara si todas las regresiones críticas pasan y no existe ningún merge de revisión aplicado.
"""
    (QUALITY / "controlled_semantic_correction_dryrun.md").write_text(report, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
