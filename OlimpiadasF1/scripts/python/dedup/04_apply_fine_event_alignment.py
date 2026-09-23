"""Script 04: Alineación Fina de Disciplinas y Eventos Residuales (Etapa C).

Objetivos:
1. Respaldar data/processed/ en data/backup_pre_dedup_etapa_c/.
2. Homologar eventos residuales de deportes de invierno, ecuestres y náuticos mediante
   sinónimos olímpicos exactos ('Open' <-> 'Mixed', 'Race Walk' <-> 'Walk', etc.).
3. Desarmar prefijos compuestos respetando jerarquía de disciplina sobre deporte.
4. Blindar al 100% a Guatemala (NOC 87: 263 atletas, 594 participaciones, 3 medallas).
5. Consolidar participaciones gemelas en el mismo atleta, edición y evento canónico.
6. Garantizar CERO llaves foráneas rotas en SQL Server.
7. Validar contra el COI (Bolt: 10 part / 8 oros; Phelps: 28 medallas; Messi: 1 oro).
"""

import csv
import json
import re
import shutil
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
BACKUP_DIR = ROOT / "data" / "backup_pre_dedup_etapa_c"
PREVIEW_DIR = ROOT / "data" / "preview_etapa_c"
REPORTS_DIR = ROOT / "docs" / "dedup"

MEDAL_RANK = {"Gold": 3, "Silver": 2, "Bronze": 1, "": 0, "None": 0}

def norm_text(value: str) -> str:
    if not value:
        return ""
    val = value.replace("\u00d7", "x").replace("×", "x")
    val = unicodedata.normalize("NFKD", val).encode("ASCII", "ignore").decode("utf-8").lower()
    val = val.replace("’", "'")
    val = re.sub(r"[^a-z0-9]+", " ", val)
    return re.sub(r"\s+", " ", val).strip()

def event_sig_v3(name: str, sport: str, discipline: str) -> str:
    val = norm_text(name)
    sp = norm_text(sport)
    disc = norm_text(discipline)
    
    # 1. Normalizar sinónimos históricos COI vs Kaggle
    val = re.sub(r"\brace walk\b", "walk", val)
    val = re.sub(r"\bmixed \(men\) s\b", "open", val)
    val = re.sub(r"\bmixed\b", "open", val)
    val = re.sub(r"\bthree day event\b", "eventing", val)
    val = re.sub(r"\bsynchronized swimming\b", "artistic swimming", val)
    
    # 2. Desarmar prefijos respetando orden de longitud (compuestos primero)
    prefixes = sorted(set([
        sp, disc, "coxed", "coxless", "alpine", "cross country", "freestyle",
        "nordic", "speed", "artistic", "rhythmic", "trampoline", "equestrianism",
        "equestrian", "jumping", "dressage", "eventing"
    ]), key=len, reverse=True)
    
    for prefix in prefixes:
        if prefix:
            val = re.sub(rf"\b{prefix}\b", " ", val)
            
    val = re.sub(r"(\d+)\s*x\s*(\d+)", r"\1x\2", val)
    val = re.sub(r"\b(men|women) s\b", r"\1", val)
    val = re.sub(r"\b(olympic|olympics|yog|non medal)\b", " ", val)
    val = re.sub(r"\b(mens|men)\b", "men", val)
    val = re.sub(r"\b(womens|women)\b", "women", val)
    val = re.sub(r"\bm\b", "metres", val)
    val = re.sub(r"\bmeters\b", "metres", val)
    val = re.sub(r"\bx\b", " ", val)
    tokens = [t for t in val.split() if t]
    return " ".join(sorted(set(tokens)))

def main():
    print("=== INICIANDO APLICACIÓN OFICIAL DE ETAPA C (ALINEACIÓN FINA DE EVENTOS) ===")

    # 1. Crear backup de seguridad de la Etapa C
    print("\n1. Creando backup de seguridad en data/backup_pre_dedup_etapa_c/...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ["evento.csv", "participacion.csv", "atleta.csv"]:
        shutil.copy2(PROCESSED_DIR / fname, BACKUP_DIR / fname)
    print("Backup completado.")

    # 2. Cargar tablas
    deportes = {}
    with (PROCESSED_DIR / "deporte.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            deportes[r["id_deporte"]] = r["nombre"]

    disciplinas = {}
    with (PROCESSED_DIR / "disciplina.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            disciplinas[r["id_disciplina"]] = (r["id_deporte"], r["nombre"])

    eventos = {}
    evento_fields = []
    with (PROCESSED_DIR / "evento.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        evento_fields = reader.fieldnames
        for r in reader:
            disc = disciplinas.get(r["id_disciplina"], ("1", "?"))
            dep = deportes.get(disc[0], "?")
            eventos[r["id_evento"]] = {
                "id_evento": r["id_evento"],
                "id_disciplina": r["id_disciplina"],
                "deporte": dep,
                "disciplina": disc[1],
                "nombre": r["nombre"],
                "is_olympedia": "(Olympic)" in r["nombre"] or "(YOG)" in r["nombre"]
            }

    participations = []
    part_fields = []
    part_counts_by_event = Counter()
    with (PROCESSED_DIR / "participacion.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        part_fields = reader.fieldnames
        for r in reader:
            participations.append(r)
            part_counts_by_event[r["id_evento"]] += 1

    total_participations = len(participations)
    print(f"Total eventos cargados: {len(eventos):,}")
    print(f"Total participaciones cargadas: {total_participations:,}")

    # 3. Mapeo semántico refinado
    sig_groups = defaultdict(list)
    for e_id, ev in eventos.items():
        dep_norm = norm_text(ev["deporte"])
        disc_norm = norm_text(ev["disciplina"])
        key_disc = disc_norm if "equestrian" in dep_norm else dep_norm
        sig = (key_disc, event_sig_v3(ev["nombre"], ev["deporte"], ev["disciplina"]))
        sig_groups[sig].append(e_id)

    event_to_canonical = {}
    alias_reports = []

    for sig, e_ids in sig_groups.items():
        if len(e_ids) == 1:
            event_to_canonical[e_ids[0]] = e_ids[0]
            continue

        def score_event(eid):
            ev = eventos[eid]
            is_olymp = 10 if "(Olympic)" in ev["nombre"] and "(non-medal)" not in ev["nombre"] else 0
            is_yog = 5 if "(YOG)" in ev["nombre"] else 0
            no_nonmedal = 2 if "(non-medal)" not in ev["nombre"] else -5
            cnt = part_counts_by_event[eid]
            return (is_olymp, is_yog, no_nonmedal, cnt, -int(eid))

        can_eid = max(e_ids, key=score_event)
        for eid in e_ids:
            event_to_canonical[eid] = can_eid
            if eid != can_eid:
                alias_reports.append({
                    "id_evento_secundario": eid,
                    "nombre_secundario": eventos[eid]["nombre"],
                    "id_evento_canonico": can_eid,
                    "nombre_canonico": eventos[can_eid]["nombre"],
                    "deporte": eventos[can_eid]["deporte"],
                    "disciplina": eventos[can_eid]["disciplina"],
                    "part_secundario": part_counts_by_event[eid],
                    "part_canonico": part_counts_by_event[can_eid]
                })

    print(f"Total eventos alias mapeados a canónicos en Etapa C: {len(alias_reports):,}")

    # 4. Consolidar participaciones gemelas
    retained_parts = []
    part_groups = defaultdict(list)

    for p in participations:
        if p.get("id_noc") == "87":
            # Escudo de Guatemala: 100% Intacto
            retained_parts.append(dict(p))
            continue

        can_e_id = event_to_canonical[p["id_evento"]]
        key = (p["id_atleta"], p["id_edicion"], can_e_id)
        part_groups[key].append(p)

    redundant_count = 0
    for key, p_list in part_groups.items():
        if len(p_list) == 1:
            p = dict(p_list[0])
            p["id_evento"] = key[2]
            retained_parts.append(p)
        else:
            redundant_count += (len(p_list) - 1)
            best_p = dict(p_list[0])
            best_p["id_evento"] = key[2]
            for other in p_list[1:]:
                m_curr = best_p.get("medalla") or ""
                m_other = other.get("medalla") or ""
                if MEDAL_RANK.get(m_other, 0) > MEDAL_RANK.get(m_curr, 0):
                    best_p["medalla"] = other["medalla"]
                if not best_p.get("posicion") and other.get("posicion"):
                    best_p["posicion"] = other["posicion"]
                if not best_p.get("id_noc") and other.get("id_noc"):
                    best_p["id_noc"] = other["id_noc"]
            retained_parts.append(best_p)

    # 5. Filtrar eventos preservando llaves foráneas completas
    used_event_ids = {p["id_evento"] for p in retained_parts}
    canonical_event_ids = set(event_to_canonical.values())
    retained_event_ids = used_event_ids | canonical_event_ids

    retained_events = []
    with (PROCESSED_DIR / "evento.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["id_evento"] in retained_event_ids:
                retained_events.append(r)

    # 6. Validaciones estrictas de seguridad
    retained_e_set = {e["id_evento"] for e in retained_events}
    missing_fks = used_event_ids - retained_e_set
    if missing_fks:
        raise RuntimeError(f"ABORTADO: Existen {len(missing_fks)} eventos en participacion no presentes en evento.csv")

    # Guatemala
    gua_parts = [r for r in retained_parts if r.get("id_noc") == "87"]
    gua_athletes = len({r["id_atleta"] for r in gua_parts})
    gua_medals = sum(1 for r in gua_parts if r.get("medalla") in ("Gold", "Silver", "Bronze"))
    if gua_athletes != 263 or len(gua_parts) != 594:
        raise RuntimeError(f"ABORTADO: Guatemala no coincide (atletas={gua_athletes}, participaciones={len(gua_parts)})")
    if gua_medals != 3:
        raise RuntimeError(f"ABORTADO: Guatemala no tiene 3 medallas (encontradas: {gua_medals})")

    # Usain Bolt
    bolt_parts = [r for r in retained_parts if r["id_atleta"] == "104492"]
    bolt_golds = sum(1 for r in bolt_parts if r.get("medalla") == "Gold")
    if len(bolt_parts) != 10 or bolt_golds != 8:
        raise RuntimeError(f"ABORTADO: Usain Bolt difiere de la realidad COI (participaciones={len(bolt_parts)}, oros={bolt_golds})")

    # Michael Phelps
    phelps_parts = [r for r in retained_parts if r["id_atleta"] == "93113"]
    phelps_medals = Counter(r.get("medalla") for r in phelps_parts if r.get("medalla"))
    if phelps_medals.get("Gold") != 23 or phelps_medals.get("Silver") != 3 or phelps_medals.get("Bronze") != 2:
        raise RuntimeError(f"ABORTADO: Michael Phelps difiere del récord olímpico (medallas={dict(phelps_medals)})")

    # Lionel Messi
    messi_parts = [r for r in retained_parts if r["id_atleta"] == "110178"]
    messi_golds = sum(1 for r in messi_parts if r.get("medalla") == "Gold")
    if len(messi_parts) != 1 or messi_golds != 1:
        raise RuntimeError(f"ABORTADO: Lionel Messi difiere del registro oficial (participaciones={len(messi_parts)}, oros={messi_golds})")

    # 7. Escribir Preview y Reportes
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    print("\nEscribiendo archivos en preview_etapa_c...")

    with (PREVIEW_DIR / "evento.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=evento_fields)
        writer.writeheader()
        writer.writerows(retained_events)

    with (PREVIEW_DIR / "participacion.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=part_fields)
        writer.writeheader()
        writer.writerows(retained_parts)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORTS_DIR / "stage_c_event_mappings.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id_evento_secundario", "nombre_secundario", "id_evento_canonico",
            "nombre_canonico", "deporte", "disciplina", "part_secundario", "part_canonico"
        ])
        writer.writeheader()
        writer.writerows(alias_reports)

    # 8. Aplicar cambios a data/processed/
    print("\nAplicando cambios oficiales en data/processed/...")
    shutil.copy2(PREVIEW_DIR / "evento.csv", PROCESSED_DIR / "evento.csv")
    shutil.copy2(PREVIEW_DIR / "participacion.csv", PROCESSED_DIR / "participacion.csv")

    print(f"\nAPLICACIÓN DE ETAPA C COMPLETADA CON ÉXITO:")
    print(f"  evento.csv: {len(eventos):,} -> {len(retained_events):,} eventos")
    print(f"  participacion.csv: {total_participations:,} -> {len(retained_parts):,} participaciones")
    print(f"  Participaciones gemelas eliminadas: {redundant_count:,}")
    print(f"  Guatemala: {gua_athletes} atletas, {len(gua_parts)} participaciones, {gua_medals} medallas (100% INTACTA)")
    print(f"  Usain Bolt: {len(bolt_parts)} carreras, {bolt_golds} oros (100% fiel al COI)")
    print(f"  Michael Phelps: {len(phelps_parts)} carreras, 28 medallas (23/3/2) (100% fiel al COI)")
    print(f"  Lionel Messi: {len(messi_parts)} participaciones, {messi_golds} oro (100% fiel al COI)")

if __name__ == "__main__":
    main()
