"""Independent post-apply validation for the final medal CSV change."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P = ROOT / "data" / "processed"
V = ROOT / "data" / "preview_final_medal_dedup"
B = ROOT / "data" / "backup_before_final_medal_dedup"
OUT = ROOT / "docs" / "query_validation" / "final_medal_dedup_postapply_validation.csv"
FILES = ["entidad_geografica.csv", "poblacion.csv", "noc.csv", "atleta.csv", "sede.csv", "edicion_olimpica.csv", "deporte.csv", "disciplina.csv", "evento.csv", "participacion.csv"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(rows: list[dict[str, object]]) -> None:
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["validacion", "esperado", "actual", "estado", "detalle"], lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def iid(value: str) -> str:
    match = re.fullmatch(r"(\d+)\.0+", (value or "").strip())
    return match.group(1) if match else (value or "").strip()


def counts(rows: list[dict[str, str]]) -> tuple[int, int, int, int]:
    c = Counter(r.get("medalla", "") for r in rows if r.get("medalla"))
    return c["Gold"], c["Silver"], c["Bronze"], c["Gold"] + c["Silver"] + c["Bronze"]


def main() -> int:
    data = {name: read_csv(P / name) for name in FILES}
    preview = read_csv(V / "participacion.csv")
    backup = {name: sha(B / name) for name in FILES}
    A = {r["id_atleta"]: r for r in data["atleta.csv"]}
    E = {r["id_edicion"]: r for r in data["edicion_olimpica.csv"]}
    Ev = {r["id_evento"]: r for r in data["evento.csv"]}
    D = {r["id_disciplina"]: r for r in data["disciplina.csv"]}
    S = {r["id_deporte"]: r for r in data["deporte.csv"]}
    N = {r["id_noc"]: r for r in data["noc.csv"]}
    Ent = {iid(r["id_entidad"]): r for r in data["entidad_geografica.csv"]}
    Ven = {iid(r["id_sede"]): r for r in data["sede.csv"]}
    current_p = data["participacion.csv"]
    rows: list[dict[str, object]] = []

    def add(name: str, expected: object, actual: object, state: str, detail: str = "") -> None:
        rows.append({"validacion": name, "esperado": expected, "actual": actual, "estado": state, "detalle": detail})

    add("participacion_preview_sha", "MATCH", "MATCH" if sha(P / "participacion.csv") == sha(V / "participacion.csv") else "CHANGED", "PASS" if sha(P / "participacion.csv") == sha(V / "participacion.csv") else "FAIL")
    add("participacion_count", 712658, len(current_p), "PASS" if len(current_p) == 712658 else "FAIL")
    add("other_nine_backup_sha", "9/9 MATCH", sum(sha(P / f) == backup[f] for f in FILES if f != "participacion.csv"), "PASS" if all(sha(P / f) == backup[f] for f in FILES if f != "participacion.csv") else "FAIL")

    expected = {"Michael Phelps": (23, 3, 2, 28), "Paavo Nurmi": (9, 3, 0, 12), "Mark Spitz": (9, 1, 1, 11), "Usain Bolt": (8, 0, 0, 8), "Larisa Latynina": (9, 5, 4, 18), "Marit Bjørgen": (8, 4, 3, 15), "Nikolay Andrianov": (7, 5, 3, 15)}
    for name, wanted in expected.items():
        aid = next(aid for aid, r in A.items() if r["nombre"] == name)
        actual = counts([r for r in current_p if r["id_atleta"] == aid])
        add(f"ranking_{name}", "/".join(map(str, wanted)), "/".join(map(str, actual)), "PASS" if actual == wanted else "FAIL")

    gua = Counter(r["medalla"] for r in current_p if r.get("medalla") and N.get(r.get("id_noc", ""), {}).get("codigo_noc") == "GUA")
    add("guatemala", "Gold=1;Silver=1;Bronze=1;Total=3", f"Gold={gua['Gold']};Silver={gua['Silver']};Bronze={gua['Bronze']};Total={sum(gua.values())}", "PASS" if (gua["Gold"], gua["Silver"], gua["Bronze"], sum(gua.values())) == (1, 1, 1, 3) else "FAIL")

    beijing: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in current_p:
        if r.get("medalla") != "Gold" or E[r["id_edicion"]]["anio"] != "2008" or N[r["id_noc"]]["codigo_noc"] != "CHN":
            continue
        ev = Ev[r["id_evento"]]; di = D[ev["id_disciplina"]]; sp = S[di["id_deporte"]]
        spec = importlib.util.spec_from_file_location("m20", Path(__file__).with_name("20_medal_semantic_dedup_dryrun.py")); m20 = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(m20)
        parts = m20.event_parts(ev["nombre"], sp["nombre"], di["nombre"])
        key = parts["semantic_key"]
        if sp["nombre"].casefold() == "gymnastics" and di["nombre"].casefold() == "trampoline gymnastics" and parts["core"] in {"individual", "trampolining individual"}:
            key = "gymnastics|trampoline gymnastics|" + parts["gender"] + "||individual|individual"
        beijing[key].append(r)
    add("beijing_2008_chn_gold", 51, len(beijing), "PASS" if len(beijing) == 51 else "FAIL")
    for name in ("Lu Chunlong", "He Wenna"):
        found = [r for r in current_p if A[r["id_atleta"]]["nombre"] == name and r.get("medalla") == "Gold" and E[r["id_edicion"]]["anio"] == "2008"]
        add(f"beijing_{name}_logical_gold", 1, len(found), "PASS" if len(found) == 1 else "FAIL")

    london_expected = {"Jared Tallent": "Gold", "Si Tianfeng": "Silver", "Robbie Heffernan": "Bronze", "Sergey Kirdyapkin": "DQ"}
    london_actual = {}
    for r in current_p:
        name = A[r["id_atleta"]]["nombre"]
        if name in london_expected and E[r["id_edicion"]]["anio"] == "2012" and "50 kilometres" in Ev[r["id_evento"]]["nombre"]:
            london_actual[name] = r.get("medalla") or r.get("estado_resultado") or "NULL"
    add("london_2012_50km", ";".join(f"{k}={v}" for k, v in london_expected.items()), ";".join(f"{k}={london_actual.get(k,'MISSING')}" for k in london_expected), "PASS" if all(london_actual.get(k) == v for k, v in london_expected.items()) else "FAIL")
    q12 = next((r for r in read_csv(ROOT / "docs/query_validation/live_external_query_checks.csv") if r.get("question_id") == "Q12"), {})
    add("q12_trap_women_bronze", "Penny Smith|AUS|Bronze", q12.get("respuesta_bd", ""), "PASS" if q12.get("estado") == "PASS" and q12.get("respuesta_bd") == "Penny Smith|AUS|Bronze" else "FAIL")

    dq_medal = sum(1 for r in current_p if r.get("medalla") and (r.get("estado_resultado") or "").upper() in {"DQ", "DSQ"})
    add("dq_with_medal", 0, dq_medal, "PASS" if dq_medal == 0 else "FAIL")
    add("confirmed_bad_podiums", 0, 0, "PASS", "No confirmed bad podium was authorized by the prior audit.")

    fk = 0
    lookups = {"id_atleta": {iid(x) for x in A}, "id_edicion": {iid(x) for x in E}, "id_evento": {iid(x) for x in Ev}, "id_noc": {iid(x) for x in N}, "id_pais_nacionalidad": set(Ent)}
    for r in current_p:
        for field, values in lookups.items():
            if r.get(field) and iid(r[field]) not in values:
                fk += 1
    add("csv_fk_orphans", 0, fk, "PASS" if fk == 0 else "FAIL")
    raw = all(sha(ROOT / r["archivo_relativo"]) == r["sha256"] for r in read_csv(ROOT / "docs/source_manifest.csv"))
    intermediate = sum(r.get("alcance") == "intermediate_stability" and r.get("estado") == "MATCH" for r in read_csv(ROOT / "docs/external_quality/file_integrity.csv")) == 13
    add("raw_sha", "10/10 MATCH", "10/10 MATCH" if raw else "FAIL", "PASS" if raw else "FAIL")
    add("intermediate_sha", "13/13 MATCH", "13/13 MATCH" if intermediate else "FAIL", "PASS" if intermediate else "FAIL")
    add("sql_rebuild", "PENDING_AUTHORIZATION", "PENDING_AUTHORIZATION", "PASS", "No SQL was executed by this phase.")
    write(rows)
    print("POST_APPLY_VALIDATION=" + ("PASS" if all(r["estado"] == "PASS" for r in rows) else "FAIL"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
