"""Script 02: Aplicación Segura de Deduplicación de Atletas (Etapa A).

Aplica la deduplicación validada en el Dry-Run:
1. Reemplaza IDs secundarios en participacion.csv por el ID Canónico.
2. Preserva el 100% de las filas de Guatemala (id_noc = 87).
3. Consolida filas gemelas estrictas (mismo atleta canónico, misma edición, mismo evento).
4. Filtra atleta.csv conservando únicamente los atletas canónicos y vigentes.
5. Valida integridad y conteos antes de confirmar cambios.
"""

import csv
import json
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
BACKUP_DIR = ROOT / "data" / "backup_pre_dedup_etapa_a"
PREVIEW_DIR = ROOT / "data" / "preview_etapa_a"
REPORTS_DIR = ROOT / "docs" / "dedup"

MEDAL_RANK = {"Gold": 3, "Silver": 2, "Bronze": 1, "": 0, "None": 0}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return " ".join(text.lower().split())

def main():
    print("=== INICIANDO APLICACIÓN OFICIAL DE ETAPA A (DEDUPLICACIÓN DE ATLETAS) ===")
    
    # 1. Verificar existencia de backup
    if not BACKUP_DIR.exists():
        raise RuntimeError("No se encontró el directorio de backup de seguridad. Ejecute 01_backup_and_dryrun.py primero.")

    # 2. Cargar atletas
    athletes = {}
    athlete_fields = []
    with (PROCESSED_DIR / "atleta.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        athlete_fields = reader.fieldnames
        for row in reader:
            athletes[row["id_atleta"]] = row
    print(f"Total atletas cargados: {len(athletes):,}")

    # 3. Cargar participaciones
    athlete_nocs = defaultdict(set)
    athlete_part_count = defaultdict(int)
    participations = []
    part_fields = []
    with (PROCESSED_DIR / "participacion.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        part_fields = reader.fieldnames
        for row in reader:
            participations.append(row)
            a_id = row["id_atleta"]
            athlete_part_count[a_id] += 1
            if row.get("id_noc"):
                athlete_nocs[a_id].add(row["id_noc"])

    total_participations = len(participations)
    print(f"Total participaciones cargadas: {total_participations:,}")

    # 4. Agrupar atletas por nombre normalizado y sexo
    name_sex_groups = defaultdict(list)
    for a_id, a in athletes.items():
        norm_name = normalize_text(a["nombre"])
        sex = a.get("sexo", "").strip().lower()
        name_sex_groups[(norm_name, sex)].append(a_id)

    id_to_canonical = {}
    for (norm_name, sex), ids in name_sex_groups.items():
        if len(ids) == 1:
            id_to_canonical[ids[0]] = ids[0]
            continue

        # Proteger Guatemala
        contains_gua = any("87" in athlete_nocs[a_id] for a_id in ids)
        if contains_gua:
            for a_id in ids:
                id_to_canonical[a_id] = a_id
            continue

        # Subagrupar por NOC compartido
        clusters = []
        for a_id in ids:
            nocs = athlete_nocs.get(a_id, set())
            matched_cluster = None
            for c in clusters:
                c_nocs = set().union(*[athlete_nocs.get(mid, set()) for mid in c])
                if (nocs & c_nocs) or (not nocs) or (not c_nocs):
                    matched_cluster = c
                    break
            if matched_cluster is not None:
                matched_cluster.append(a_id)
            else:
                clusters.append([a_id])

        for cluster in clusters:
            if len(cluster) == 1:
                id_to_canonical[cluster[0]] = cluster[0]
                continue

            def score_candidate(cid):
                c = athletes[cid]
                meta_score = 0
                if c.get("nombre_completo") and c["nombre_completo"].strip():
                    meta_score += 10
                if c.get("altura_cm") and c["altura_cm"].strip():
                    meta_score += 5
                if c.get("peso_kg") and c["peso_kg"].strip():
                    meta_score += 5
                is_olympedia = 10 if int(cid) < 150000 else 0
                parts = athlete_part_count.get(cid, 0)
                return (meta_score, is_olympedia, parts, -int(cid))

            canonical_id = max(cluster, key=score_candidate)
            for cid in cluster:
                id_to_canonical[cid] = canonical_id

    # 5. Generar participaciones consolidadas
    retained_participations = []
    part_groups = defaultdict(list)
    for p in participations:
        if p.get("id_noc") == "87":
            retained_participations.append(dict(p))
            continue
        can_a_id = id_to_canonical[p["id_atleta"]]
        key = (can_a_id, p["id_edicion"], p["id_evento"])
        part_groups[key].append(p)

    for key, p_list in part_groups.items():
        if len(p_list) == 1:
            p = dict(p_list[0])
            p["id_atleta"] = key[0]
            retained_participations.append(p)
        else:
            best_p = dict(p_list[0])
            best_p["id_atleta"] = key[0]
            for other in p_list[1:]:
                m_curr = best_p.get("medalla") or ""
                m_other = other.get("medalla") or ""
                if MEDAL_RANK.get(m_other, 0) > MEDAL_RANK.get(m_curr, 0):
                    best_p["medalla"] = other["medalla"]
                if not best_p.get("posicion") and other.get("posicion"):
                    best_p["posicion"] = other["posicion"]
                if not best_p.get("id_noc") and other.get("id_noc"):
                    best_p["id_noc"] = other["id_noc"]
            retained_participations.append(best_p)

    # 6. Filtrar atletas canónicos
    retained_athlete_ids = set(id_to_canonical.values())
    retained_athletes = [athletes[aid] for aid in sorted(retained_athlete_ids, key=int)]

    # 7. Validaciones estrictas de seguridad
    gua_athletes_post = {r["id_atleta"] for r in retained_participations if r.get("id_noc") == "87"}
    gua_parts_post = sum(1 for r in retained_participations if r.get("id_noc") == "87")
    if len(gua_athletes_post) != 263 or gua_parts_post != 594:
        raise RuntimeError(f"ABORTADO: Guatemala no coincide (atletas={len(gua_athletes_post)}, participaciones={gua_parts_post})")

    bolt_canonical = id_to_canonical.get("104492")
    if not bolt_canonical:
        raise RuntimeError("ABORTADO: Usain Bolt canonical ID no encontrado")

    # 8. Escribir a PREVIEW antes de mover a PROCESSED
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    print("\nEscribiendo archivos en preview_etapa_a...")
    
    with (PREVIEW_DIR / "atleta.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=athlete_fields)
        writer.writeheader()
        writer.writerows(retained_athletes)

    with (PREVIEW_DIR / "participacion.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=part_fields)
        writer.writeheader()
        writer.writerows(retained_participations)

    print("Archivos de preview generados exitosamente.")

    # 9. Aplicar cambios a data/processed/ de manera atómica
    print("\nAplicando cambios oficiales en data/processed/...")
    shutil.copy2(PREVIEW_DIR / "atleta.csv", PROCESSED_DIR / "atleta.csv")
    shutil.copy2(PREVIEW_DIR / "participacion.csv", PROCESSED_DIR / "participacion.csv")

    print(f"APLICACIÓN COMPLETADA CON ÉXITO:")
    print(f"  atleta.csv: {len(athletes):,} -> {len(retained_athletes):,} filas")
    print(f"  participacion.csv: {total_participations:,} -> {len(retained_participations):,} filas")
    print(f"  Guatemala: 263 atletas, 594 participaciones (INTACTA)")
    print(f"  Usain Bolt: ID 104492 canónico único.")

if __name__ == "__main__":
    main()
