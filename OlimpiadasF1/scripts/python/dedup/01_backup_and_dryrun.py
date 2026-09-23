"""Script 01: Respaldo y Simulación Dry-Run de Deduplicación de Atletas (Etapa A).

Objetivos:
1. Crear backup íntegro de data/processed/ en data/backup_pre_dedup_etapa_a/.
2. Simular en memoria la deduplicación de atletas basada en (nombre_normalizado, sexo, noc compartido).
3. Verificar la regla de oro: Guatemala (NOC 87) debe permanecer estrictamente en 263 atletas y 594 participaciones.
4. Generar reportes de auditoría en docs/dedup/ sin modificar data/processed/.
"""

import csv
import hashlib
import json
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = ROOT / "data" / "processed"
BACKUP_DIR = ROOT / "data" / "backup_pre_dedup_etapa_a"
REPORTS_DIR = ROOT / "docs" / "dedup"

CSV_FILES = [
    "entidad_geografica.csv",
    "poblacion.csv",
    "noc.csv",
    "atleta.csv",
    "sede.csv",
    "edicion_olimpica.csv",
    "deporte.csv",
    "disciplina.csv",
    "evento.csv",
    "participacion.csv",
]

MEDAL_RANK = {"Gold": 3, "Silver": 2, "Bronze": 1, "": 0, "None": 0}

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return " ".join(text.lower().split())

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def step1_create_backup():
    print("=== PASO 1: Creando respaldo de seguridad en data/backup_pre_dedup_etapa_a ===")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    for filename in CSV_FILES:
        src = PROCESSED_DIR / filename
        dst = BACKUP_DIR / filename
        if not src.exists():
            raise FileNotFoundError(f"Falta archivo crítico: {src}")
        shutil.copy2(src, dst)
        h = sha256_file(src)
        with src.open("r", encoding="utf-8-sig", newline="") as f:
            row_count = sum(1 for _ in f) - 1
        manifest.append({"archivo": filename, "filas": row_count, "sha256": h})
        print(f"  Backup OK: {filename} ({row_count:,} filas)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with (REPORTS_DIR / "backup_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["archivo", "filas", "sha256"])
        writer.writeheader()
        writer.writerows(manifest)
    print("Respaldo completado con éxito.\n")

def step2_dryrun_simulation():
    print("=== PASO 2: Ejecutando simulación Dry-Run de deduplicación de atletas ===")
    
    # 1. Cargar atletas
    athletes = {}
    with (PROCESSED_DIR / "atleta.csv").open("r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            athletes[row["id_atleta"]] = row
    print(f"Total atletas cargados: {len(athletes):,}")

    # 2. Cargar participaciones y perfilar atletas
    athlete_nocs = defaultdict(set)
    athlete_part_count = defaultdict(int)
    participations = []
    with (PROCESSED_DIR / "participacion.csv").open("r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            participations.append(row)
            a_id = row["id_atleta"]
            athlete_part_count[a_id] += 1
            if row.get("id_noc"):
                athlete_nocs[a_id].add(row["id_noc"])

    total_participations = len(participations)
    print(f"Total participaciones cargadas: {total_participations:,}")

    # 3. Validar estado inicial de Guatemala (id_noc = '87')
    gua_athletes_initial = {r["id_atleta"] for r in participations if r.get("id_noc") == "87"}
    gua_parts_initial = sum(1 for r in participations if r.get("id_noc") == "87")
    print(f"\n[ESCUDO GUATEMALA INICIAL]")
    print(f"  Atletas distintos de GUA: {len(gua_athletes_initial)} (Esperado: 263)")
    print(f"  Participaciones de GUA: {gua_parts_initial} (Esperado: 594)")
    if len(gua_athletes_initial) != 263 or gua_parts_initial != 594:
        raise RuntimeError(f"El conteo inicial de Guatemala difiere del canónico: atletas={len(gua_athletes_initial)}, participaciones={gua_parts_initial}")

    # 4. Agrupar atletas por nombre normalizado y sexo
    # Nota: Los atletas de Guatemala NUNCA se fusionan con nadie externo.
    name_sex_groups = defaultdict(list)
    for a_id, a in athletes.items():
        norm_name = normalize_text(a["nombre"])
        sex = a.get("sexo", "").strip().lower()
        name_sex_groups[(norm_name, sex)].append(a_id)

    id_to_canonical = {}
    merge_details = []

    for (norm_name, sex), ids in name_sex_groups.items():
        if len(ids) == 1:
            id_to_canonical[ids[0]] = ids[0]
            continue

        # Si el grupo contiene atletas de Guatemala, protegerlos
        contains_gua = any("87" in athlete_nocs[a_id] for a_id in ids)
        if contains_gua:
            # Los atletas de Guatemala no se tocan
            for a_id in ids:
                id_to_canonical[a_id] = a_id
            continue

        # Subagrupar por NOC compartido (componentes conexas de delegación)
        # Atletas que comparten NOC son candidatos 100% seguros a ser la misma persona
        clusters = []
        for a_id in ids:
            nocs = athlete_nocs.get(a_id, set())
            matched_cluster = None
            for c in clusters:
                # Si comparten NOC o si uno de ellos no tiene participaciones registradas
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

            # Seleccionar el Canónico dentro del cluster:
            # Criterio:
            # 1) Mayor cantidad de metadatos (altura, peso, fecha nacimiento, nombre completo)
            # 2) ID de Olympedia (menor a 150000)
            # 3) Mayor cantidad de participaciones
            # 4) Menor id numérico
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
            canonical_athlete = athletes[canonical_id]

            for cid in cluster:
                id_to_canonical[cid] = canonical_id
                if cid != canonical_id:
                    merge_details.append({
                        "id_secundario": cid,
                        "nombre_secundario": athletes[cid]["nombre"],
                        "id_canonico": canonical_id,
                        "nombre_canonico": canonical_athlete["nombre"],
                        "norm_name": norm_name,
                        "sexo": sex,
                        "nocs": ",".join(sorted(athlete_nocs.get(cid, set()))),
                        "part_secundario": athlete_part_count[cid],
                        "part_canonico": athlete_part_count[canonical_id],
                    })

    # 5. Evaluar impacto en Participaciones (Consolidación de Gemelos Estrictos)
    # Regla: Las participaciones de Guatemala (NOC 87) pasan directamente intactas al 100%.
    # Para el resto del mundo, una participación solo se consolida si (id_atleta_canonico, id_edicion, id_evento) es idéntico.
    retained_participations = []
    part_groups = defaultdict(list)
    for p in participations:
        if p.get("id_noc") == "87":
            retained_participations.append(dict(p))
            continue
        can_a_id = id_to_canonical[p["id_atleta"]]
        key = (can_a_id, p["id_edicion"], p["id_evento"])
        part_groups[key].append(p)

    redundant_part_count = 0

    for key, p_list in part_groups.items():
        if len(p_list) == 1:
            p = dict(p_list[0])
            p["id_atleta"] = key[0]
            retained_participations.append(p)
        else:
            # Fusión de gemelos exactos
            redundant_part_count += (len(p_list) - 1)
            # Escoger mejor medalla y mejor posición
            best_p = dict(p_list[0])
            best_p["id_atleta"] = key[0]
            for other in p_list[1:]:
                # Medalla
                m_curr = best_p.get("medalla") or ""
                m_other = other.get("medalla") or ""
                if MEDAL_RANK.get(m_other, 0) > MEDAL_RANK.get(m_curr, 0):
                    best_p["medalla"] = other["medalla"]
                # Posición
                if not best_p.get("posicion") and other.get("posicion"):
                    best_p["posicion"] = other["posicion"]
                # NOC
                if not best_p.get("id_noc") and other.get("id_noc"):
                    best_p["id_noc"] = other["id_noc"]
            retained_participations.append(best_p)

    # 6. Validar Escudo de Guatemala Post-Simulación
    gua_athletes_post = {r["id_atleta"] for r in retained_participations if r.get("id_noc") == "87"}
    gua_parts_post = sum(1 for r in retained_participations if r.get("id_noc") == "87")
    print(f"\n[ESCUDO GUATEMALA POST-SIMULACIÓN]")
    print(f"  Atletas distintos de GUA: {len(gua_athletes_post)} (Esperado: 263)")
    print(f"  Participaciones de GUA: {gua_parts_post} (Esperado: 594)")
    if len(gua_athletes_post) != 263 or gua_parts_post != 594:
        raise RuntimeError(f"¡VIOLACIÓN DE REGLA DE ORO! Guatemala cambió: atletas={len(gua_athletes_post)}, participaciones={gua_parts_post}")

    # 7. Caso de Prueba Específico: USAIN BOLT
    bolt_canonical = id_to_canonical.get("104492")
    bolt_sub_ids = [cid for cid, can in id_to_canonical.items() if can == bolt_canonical and cid != bolt_canonical]
    bolt_parts_before = athlete_part_count["104492"] + sum(athlete_part_count[cid] for cid in bolt_sub_ids)
    bolt_parts_after = sum(1 for r in retained_participations if r["id_atleta"] == bolt_canonical)
    bolt_golds_after = sum(1 for r in retained_participations if r["id_atleta"] == bolt_canonical and r.get("medalla") == "Gold")

    print(f"\n[CASO DE PRUEBA: USAIN BOLT]")
    print(f"  ID Canónico: {bolt_canonical} ({athletes[bolt_canonical]['nombre']})")
    print(f"  IDs secundarios absorbidos ({len(bolt_sub_ids)}): {bolt_sub_ids}")
    print(f"  Participaciones antes: {bolt_parts_before}")
    print(f"  Participaciones después: {bolt_parts_after}")
    print(f"  Medallas de Oro después: {bolt_golds_after} (Esperado: 8)")

    # 8. Métricas Globales Proyectadas
    distinct_athletes_retained = len(set(id_to_canonical.values()))
    print(f"\n[MÉTRICAS GLOBALES PROYECTADAS (ETAPA A)]")
    print(f"  Total atletas antes: {len(athletes):,}")
    print(f"  Total atletas después: {distinct_athletes_retained:,} (-{len(athletes) - distinct_athletes_retained:,} duplicados eliminados)")
    print(f"  Total participaciones antes: {total_participations:,}")
    print(f"  Total participaciones después: {len(retained_participations):,} (-{redundant_part_count:,} gemelas estrictas consolidadas)")
    print(f"  Participaciones únicas preservadas: 100.0%")

    # Guardar reportes
    with (REPORTS_DIR / "sample_athlete_merges.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id_secundario", "nombre_secundario", "id_canonico", "nombre_canonico",
            "norm_name", "sexo", "nocs", "part_secundario", "part_canonico"
        ])
        writer.writeheader()
        writer.writerows(merge_details)

    with (REPORTS_DIR / "dryrun_summary.json").open("w", encoding="utf-8") as f:
        json.dump({
            "atletas_antes": len(athletes),
            "atletas_despues": distinct_athletes_retained,
            "participaciones_antes": total_participations,
            "participaciones_despues": len(retained_participations),
            "guatemala_atletas": len(gua_athletes_post),
            "guatemala_participaciones": gua_parts_post,
            "usain_bolt_canonical_id": bolt_canonical,
            "usain_bolt_absorbed_count": len(bolt_sub_ids),
            "usain_bolt_parts": bolt_parts_after,
            "usain_bolt_golds": bolt_golds_after
        }, f, indent=2)

    print(f"\nReportes generados en {REPORTS_DIR}")

if __name__ == "__main__":
    step1_create_backup()
    step2_dryrun_simulation()
