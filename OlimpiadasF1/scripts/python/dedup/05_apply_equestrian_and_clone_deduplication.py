"""Script 05: Aplicacion Oficial de Etapa D (Homologacion Ecuestre y Fusion de Clones Kaggle).

Objetivo:
1. Homologar eventos ecuestres y genericos (Dressage, Jumping, Eventing) para corregir
   la inflacion artificial de medallas (ej. Isabell Werth de 14 a 8 oros oficiales).
2. Fusionar de forma determinista atletas sinteticos de Kaggle (ID >= 145000) que son
   clones de atletas canonicos de Olympedia (ej. Michael Ii -> Michael Phelps,
   Frederick Lewis -> Carl Lewis, Raymond Ewry -> Ray Ewry, Larysa -> Larisa Latynina, etc.).
3. Consolidar participaciones gemelas resultantes preservando la mejor medalla y posicion.
4. Preservar de forma ESTRICTA el 100% de los datos de Guatemala (id_noc = 87: 263 atletas, 594 part, 3 medallas).
5. Mantener integridad referencial 100% (0 FKs rotas).
"""

import csv
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
BACKUP_DIR = ROOT / "data" / "backup_pre_dedup_etapa_d"
REPORTS_DIR = ROOT / "docs" / "dedup"

MEDAL_RANK = {"Gold": 3, "Silver": 2, "Bronze": 1, "": 0, "None": 0}

def clean_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # Remover nombres de casada entre parentesis (-xxx)
    s = re.sub(r"\(-[^)]*\)", "", s)
    # Remover apodos entre comillas
    s = re.sub(r'\"[^\"]*\"', "", s)
    # Remover sufijos generacionales
    s = re.sub(r"\b(jr\.?|sr\.?|ii|iii|iv)\b", "", s, flags=re.I)
    # Normalizar acentos
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
    s = re.sub(r"[^a-zA-Z\s]", " ", s)
    tokens = [t.lower() for t in s.split() if len(t) > 1]
    return " ".join(tokens)

def main():
    print("=== INICIANDO ETAPA D: HOMOLOGACION ECUESTRE Y FUSION DE CLONES KAGGLE ===")

    # 1. Crear backup de seguridad
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for fname in ["atleta.csv", "participacion.csv", "evento.csv"]:
            shutil.copy2(PROCESSED_DIR / fname, BACKUP_DIR / fname)
        print(f"Backup creado exitosamente en: {BACKUP_DIR}")
    else:
        print(f"Directorio de backup ya existente: {BACKUP_DIR}")

    # 2. Cargar eventos
    events = {}
    event_fields = []
    with (PROCESSED_DIR / "evento.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        event_fields = reader.fieldnames
        for row in reader:
            events[int(row["id_evento"])] = row
    print(f"Eventos cargados: {len(events):,}")

    # 3. Cargar atletas
    athletes = {}
    athlete_fields = []
    with (PROCESSED_DIR / "atleta.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        athlete_fields = reader.fieldnames
        for row in reader:
            aid = int(row["id_atleta"])
            athletes[aid] = row
            athletes[aid]["clean_name"] = clean_name(row["nombre"])
    print(f"Atletas cargados: {len(athletes):,}")

    # 4. Cargar participaciones
    participations = []
    part_fields = []
    p_by_athlete = defaultdict(set)
    nocs_by_athlete = defaultdict(set)

    with (PROCESSED_DIR / "participacion.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        part_fields = reader.fieldnames
        for row in reader:
            participations.append(row)
            aid = int(row["id_atleta"])
            ed = int(row["id_edicion"])
            ev = int(row["id_evento"])
            p_by_athlete[aid].add((ed, ev))
            if row.get("id_noc"):
                try:
                    nocs_by_athlete[aid].add(int(float(row["id_noc"])))
                except ValueError:
                    pass
    print(f"Participaciones cargadas: {len(participations):,}")

    # 5. Definir Mapeo de Eventos Ecuestres y Genericos
    # Mapea eventos Kaggle y Paris 2024 a sus equivalentes canónicos de Olympedia
    eq_event_map = {
        # Dressage
        2283: 209,  # Equestrianism Mixed Dressage, Individual -> Individual, Open (Olympic)
        2284: 210,  # Equestrianism Mixed Dressage, Team -> Team, Open (Olympic)
        2261: 209,  # Equestrianism Men's Dressage, Individual -> Individual, Open (Olympic)
        2262: 210,  # Equestrianism Men's Dressage, Team -> Team, Open (Olympic)
        2943: 209,  # Dressage Individual (Paris 2024) -> Individual, Open (Olympic)
        2942: 210,  # Dressage Team (Paris 2024) -> Team, Open (Olympic)
        # Jumping
        2194: 209,  # Equestrianism Men's Jumping, Individual -> Individual, Open (Olympic)
        2195: 210,  # Equestrianism Men's Jumping, Team -> Team, Open (Olympic)
        2818: 209,  # Jumping Individual (Paris 2024) -> Individual, Open (Olympic)
        2817: 210,  # Jumping Team (Paris 2024) -> Team, Open (Olympic)
        # Eventing
        2028: 210,  # Equestrianism Mixed Three-Day Event, Team -> Team, Open (Olympic)
        2838: 208,  # Eventing Individual (Paris 2024) -> Individual, Open (Olympic)
        2837: 210,  # Eventing Team (Paris 2024) -> Team, Open (Olympic)
    }

    # Aplicar mapeo de eventos a participaciones
    for p in participations:
        ev_id = int(p["id_evento"])
        if ev_id in eq_event_map:
            p["id_evento"] = str(eq_event_map[ev_id])

    # 6. Indexar Atletas Olympedia (< 145000) por (edicion, evento, noc, sexo)
    print("Construyendo indice de participaciones canonicas (Olympedia)...")
    olymp_index = defaultdict(list)
    for aid in p_by_athlete:
        if aid < 145000:
            sex = athletes[aid].get("sexo", "").strip().lower()
            for ed, ev in p_by_athlete[aid]:
                # Si el evento fue mapeado por eq_event_map, usar el mapeado
                canon_ev = eq_event_map.get(ev, ev)
                for noc in nocs_by_athlete[aid]:
                    olymp_index[(ed, canon_ev, noc, sex)].append(aid)

    # 7. Identificar fusiones de atletas sinteticos de Kaggle (ID >= 145000)
    print("Identificando atletas sinteticos a fusionar con canonicos...")
    athlete_mapping = {}

    for aid in p_by_athlete:
        if aid >= 145000:
            # PROTEGER GUATEMALA (id_noc = 87)
            if 87 in nocs_by_athlete[aid]:
                continue
            
            sex = athletes[aid].get("sexo", "").strip().lower()
            synth_parts = {(ed, eq_event_map.get(ev, ev)) for ed, ev in p_by_athlete[aid]}
            synth_nocs = nocs_by_athlete[aid]

            candidate_counts = defaultdict(int)
            for ed, ev in synth_parts:
                for noc in synth_nocs:
                    for o_aid in olymp_index.get((ed, ev, noc, sex), []):
                        candidate_counts[o_aid] += 1

            if not candidate_counts:
                continue

            synth_cname = athletes[aid]["clean_name"]
            synth_tokens = set(synth_cname.split())

            best_cand = None
            best_overlap = 0

            for o_aid, cnt in candidate_counts.items():
                o_cname = athletes[o_aid]["clean_name"]
                o_tokens = set(o_cname.split())
                shared_tokens = synth_tokens & o_tokens
                overlap = cnt

                # Regla 1: Nombre limpio identico
                if synth_cname and o_cname and synth_cname == o_cname:
                    best_cand = o_aid
                    break

                # Regla 2: Apellido o token significativo compartido (len >= 4) y traslape total o mayoritario
                if any(len(t) >= 4 for t in shared_tokens):
                    if overlap == len(synth_parts):
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_cand = o_aid
                    elif overlap >= 2 and overlap > best_overlap:
                        best_overlap = overlap
                        best_cand = o_aid

                # Regla 3: Token unico sintético contenido en tokens canonicos con traslape total >= 2
                elif len(synth_tokens) == 1 and synth_tokens.issubset(o_tokens):
                    if overlap == len(synth_parts) and len(synth_parts) >= 2:
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_cand = o_aid

                # Regla 4: Traslape total >= 3 participaciones y prefijo de nombre coincidente (>= 3 letras)
                elif overlap == len(synth_parts) and len(synth_parts) >= 3:
                    if any(t1[:3] == t2[:3] for t1 in synth_tokens for t2 in o_tokens if len(t1)>=3 and len(t2)>=3):
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_cand = o_aid

            if best_cand:
                athlete_mapping[aid] = best_cand

    # Mapeos manuales explicitos para leyendas corruptas por Kaggle (split de comas / maiden names)
    manual_maps = {
        285121: 93113,   # Michael Ii -> Michael Phelps
        255339: 28985,   # Larysa (diriy-) -> Larisa Latynina
        312213: 50859,   # Jennifer (-cumpelik) -> Jenny Thompson
        248399: 28979,   # Nellya (-achasov) -> Nelli Kim
        246634: 28419,   # gnes (klein) -> Agnes Keleti
        208091: 28782,   # Nadia (-conner) -> Nadia Comaneci
        292117: 67273,   # Viljo (koukkari-) -> Ville Ritola
        323485: 11443,   # Isabelle Werth -> Isabell Werth
    }
    for s_id, o_id in manual_maps.items():
        athlete_mapping[s_id] = o_id

    print(f"Total atletas mapeados para fusion: {len(athlete_mapping):,}")

    # 8. Consolidar Participaciones
    print("Consolidando participaciones y resolviendo filas gemelas...")
    retained_participations = []
    part_groups = defaultdict(list)
    for p in participations:
        # Si es de Guatemala, se mantiene intacta directamente
        if p.get("id_noc") == "87":
            retained_participations.append(dict(p))
            continue
        
        orig_aid = int(p["id_atleta"])
        can_aid = athlete_mapping.get(orig_aid, orig_aid)
        key = (can_aid, int(p["id_edicion"]), int(p["id_evento"]))
        part_groups[key].append(p)

    for (can_aid, ed, ev), p_list in part_groups.items():
        if len(p_list) == 1:
            p = dict(p_list[0])
            p["id_atleta"] = str(can_aid)
            retained_participations.append(p)
        else:
            best_p = dict(p_list[0])
            best_p["id_atleta"] = str(can_aid)
            for other in p_list[1:]:
                m_curr = best_p.get("medalla") or ""
                m_other = other.get("medalla") or ""
                if MEDAL_RANK.get(m_other, 0) > MEDAL_RANK.get(m_curr, 0):
                    best_p["medalla"] = other["medalla"]
                if not best_p.get("posicion") and other.get("posicion"):
                    best_p["posicion"] = other["posicion"]
                if not best_p.get("id_noc") and other.get("id_noc"):
                    best_p["id_noc"] = other["id_noc"]
                if not best_p.get("id_resultado") and other.get("id_resultado"):
                    best_p["id_resultado"] = other["id_resultado"]
            retained_participations.append(best_p)

    print(f"Participaciones consolidadas: {len(participations):,} -> {len(retained_participations):,} (-{len(participations)-len(retained_participations):,})")

    # 9. Filtrar Atletas Vigentes
    active_athlete_ids = {int(p["id_atleta"]) for p in retained_participations}
    # Mantener tambien atletas con metadata que no hayan sido fusionados
    retained_athletes = []
    merged_ids = set(athlete_mapping.keys())
    for aid, a in athletes.items():
        if aid not in merged_ids and (aid in active_athlete_ids or aid < 145000):
            row_dict = {k: a[k] for k in athlete_fields if k in a}
            retained_athletes.append(row_dict)

    retained_athletes.sort(key=lambda x: int(x["id_atleta"]))
    print(f"Atletas vigentes retenidos: {len(athletes):,} -> {len(retained_athletes):,} (-{len(athletes)-len(retained_athletes):,})")

    # 10. Filtrar Eventos Vigentes
    active_event_ids = {int(p["id_evento"]) for p in retained_participations}
    retained_events = []
    for ev_id, ev in events.items():
        if ev_id in active_event_ids or ev_id not in eq_event_map:
            retained_events.append(ev)
    retained_events.sort(key=lambda x: int(x["id_evento"]))
    print(f"Eventos vigentes retenidos: {len(events):,} -> {len(retained_events):,} (-{len(events)-len(retained_events):,})")

    # 11. Validaciones Estrictas de Seguridad
    print("\n=== EJECUTANDO VALIDACIONES ESTRICTAS DE SEGURIDAD ===")
    
    # Guatemala
    gua_parts = sum(1 for p in retained_participations if p.get("id_noc") == "87")
    gua_athletes = {int(p["id_atleta"]) for p in retained_participations if p.get("id_noc") == "87"}
    gua_medals = sum(1 for p in retained_participations if p.get("id_noc") == "87" and p.get("medalla") in ["Gold", "Silver", "Bronze"])
    print(f"Guatemala Participaciones: {gua_parts} (Requerido: 594)")
    print(f"Guatemala Atletas: {len(gua_athletes)} (Requerido: 263)")
    print(f"Guatemala Medallas: {gua_medals} (Requerido: 3)")
    assert gua_parts == 594, f"ERROR: Guatemala participaciones {gua_parts} != 594"
    assert len(gua_athletes) == 263, f"ERROR: Guatemala atletas {len(gua_athletes)} != 263"
    assert gua_medals == 3, f"ERROR: Guatemala medallas {gua_medals} != 3"

    # Usain Bolt (104492)
    bolt_parts = [p for p in retained_participations if int(p["id_atleta"]) == 104492]
    bolt_golds = sum(1 for p in bolt_parts if p.get("medalla") == "Gold")
    print(f"Usain Bolt (104492): {len(bolt_parts)} participaciones, {bolt_golds} oros (Requerido: 8 oros)")
    assert bolt_golds == 8, f"ERROR: Bolt oros {bolt_golds} != 8"

    # Michael Phelps (93113)
    phelps_parts = [p for p in retained_participations if int(p["id_atleta"]) == 93113]
    phelps_golds = sum(1 for p in phelps_parts if p.get("medalla") == "Gold")
    phelps_medals = sum(1 for p in phelps_parts if p.get("medalla") in ["Gold", "Silver", "Bronze"])
    print(f"Michael Phelps (93113): {len(phelps_parts)} participaciones, {phelps_golds} oros, {phelps_medals} medallas (Requerido: 23 oros, 28 medallas)")
    assert phelps_golds == 23, f"ERROR: Phelps oros {phelps_golds} != 23"
    assert phelps_medals == 28, f"ERROR: Phelps medallas {phelps_medals} != 28"

    # Michael Ii (285121) no debe tener participaciones
    assert not any(int(p["id_atleta"]) == 285121 for p in retained_participations), "ERROR: Michael Ii no fue eliminado!"

    # Isabell Werth (11443)
    werth_parts = [p for p in retained_participations if int(p["id_atleta"]) == 11443]
    werth_golds = sum(1 for p in werth_parts if p.get("medalla") == "Gold")
    werth_silvers = sum(1 for p in werth_parts if p.get("medalla") == "Silver")
    print(f"Isabell Werth (11443): {len(werth_parts)} participaciones, {werth_golds} oros, {werth_silvers} platas (Requerido oficial: 8 oros, 6 platas)")
    assert werth_golds == 8, f"ERROR: Werth oros {werth_golds} != 8"
    assert werth_silvers == 6, f"ERROR: Werth platas {werth_silvers} != 6"

    # Larisa Latynina (28985)
    latynina_parts = [p for p in retained_participations if int(p["id_atleta"]) == 28985]
    latynina_golds = sum(1 for p in latynina_parts if p.get("medalla") == "Gold")
    latynina_medals = sum(1 for p in latynina_parts if p.get("medalla") in ["Gold", "Silver", "Bronze"])
    print(f"Larisa Latynina (28985): {len(latynina_parts)} participaciones, {latynina_golds} oros, {latynina_medals} medallas (Requerido oficial: 9 oros, 18 medallas)")
    assert latynina_golds == 9, f"ERROR: Latynina oros {latynina_golds} != 9"
    assert latynina_medals == 18, f"ERROR: Latynina medallas {latynina_medals} != 18"

    # Integridad referencial
    ret_athlete_ids = {int(a["id_atleta"]) for a in retained_athletes}
    ret_event_ids = {int(e["id_evento"]) for e in retained_events}
    broken_a = sum(1 for p in retained_participations if int(p["id_atleta"]) not in ret_athlete_ids)
    broken_e = sum(1 for p in retained_participations if int(p["id_evento"]) not in ret_event_ids)
    print(f"Integridad referencial: Atletas rotos={broken_a}, Eventos rotos={broken_e}")
    assert broken_a == 0, f"ERROR: {broken_a} participaciones con atleta roto!"
    assert broken_e == 0, f"ERROR: {broken_e} participaciones con evento roto!"

    # 12. Escribir archivos CSV procesados
    print("\nEscribiendo CSVs actualizados en data/processed/...")
    
    with (PROCESSED_DIR / "participacion.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=part_fields)
        writer.writeheader()
        writer.writerows(retained_participations)

    with (PROCESSED_DIR / "atleta.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=athlete_fields)
        writer.writeheader()
        writer.writerows(retained_athletes)

    with (PROCESSED_DIR / "evento.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=event_fields)
        writer.writeheader()
        writer.writerows(retained_events)

    # 13. Guardar reporte de auditoria
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_data = {
        "etapa": "D",
        "descripcion": "Homologacion Ecuestre y Fusion de Clones Kaggle",
        "atletas_previos": len(athletes),
        "atletas_finales": len(retained_athletes),
        "atletas_eliminados": len(athletes) - len(retained_athletes),
        "participaciones_previas": len(participations),
        "participaciones_finales": len(retained_participations),
        "participaciones_eliminadas": len(participations) - len(retained_participations),
        "eventos_previos": len(events),
        "eventos_finales": len(retained_events),
        "guatemala": {
            "participaciones": gua_parts,
            "atletas": len(gua_athletes),
            "medallas": gua_medals
        },
        "leyendas_validadas": {
            "Usain Bolt": f"{bolt_golds} oros",
            "Michael Phelps": f"{phelps_golds} oros, {phelps_medals} medallas",
            "Isabell Werth": f"{werth_golds} oros, {werth_silvers} platas",
            "Larisa Latynina": f"{latynina_golds} oros, {latynina_medals} medallas"
        }
    }
    with (REPORTS_DIR / "stage_d_summary.json").open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print("\n=== ETAPA D COMPLETADA CON EXITO AL 100% ===")

if __name__ == "__main__":
    main()
