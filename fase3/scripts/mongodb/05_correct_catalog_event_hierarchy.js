// Corrige el envoltorio redundante de EVENTO.disciplina en una carga ya existente.
// La fuente de verdad sigue siendo evento.csv + disciplina.csv + deporte.csv.
const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const apply = process.env.OLIMPIADAS_MONGO_APPLY === "1";
const target = db.getSiblingDB(databaseName);
const catalog = target.getCollection("catalogo_olimpico");
const total = catalog.countDocuments({ tipo: "EVENTO" });
const legacyFilter = {
    tipo: "EVENTO",
    "disciplina.id_evento": { $exists: true },
    "disciplina.disciplina.id_disciplina": { $exists: true }
};
const correctFilter = {
    tipo: "EVENTO",
    "disciplina.id_disciplina": { $exists: true },
    "disciplina.deporte.id_deporte": { $exists: true },
    "disciplina.id_evento": { $exists: false }
};
const legacy = catalog.countDocuments(legacyFilter);
const correct = catalog.countDocuments(correctFilter);

if (total !== 2069 || legacy + correct !== total) {
    throw new Error("El catálogo EVENTO tiene una forma inesperada; no se modifica. " +
        JSON.stringify({ total, legacy, correct }));
}

let inconsistent = 0;
if (legacy > 0) {
    catalog.find(legacyFilter, {
        id_evento: 1, id_disciplina: 1, nombre: 1, disciplina: 1
    }).forEach(event => {
        const wrapper = event.disciplina;
        if (String(event.id_evento) !== String(wrapper.id_evento) ||
            event.nombre !== wrapper.nombre ||
            String(event.id_disciplina) !== String(wrapper.id_disciplina) ||
            String(event.id_disciplina) !== String(wrapper.disciplina.id_disciplina)) {
            inconsistent += 1;
        }
    });
}
if (inconsistent !== 0) {
    throw new Error("Hay " + inconsistent + " EVENTO con datos distintos entre el envoltorio y la raíz; no se modifica.");
}

if (!apply) {
    printjson({ estado: "PREFLIGHT_PASS", base: databaseName, total, por_corregir: legacy,
        ya_correctos: correct, inconsistencias: inconsistent, cambios: 0 });
} else {
    const result = catalog.updateMany(legacyFilter, [
        { $set: { disciplina: "$disciplina.disciplina" } }
    ]);
    const finalCorrect = catalog.countDocuments(correctFilter);
    const finalLegacy = catalog.countDocuments(legacyFilter);
    if (result.modifiedCount !== legacy || finalCorrect !== total || finalLegacy !== 0) {
        throw new Error("La corrección no quedó íntegra: " +
            JSON.stringify({ esperados: legacy, modificados: result.modifiedCount, finalCorrect, finalLegacy }));
    }
    printjson({ estado: "PASS", base: databaseName, total, corregidos: result.modifiedCount,
        ya_correctos: correct, inconsistencias: inconsistent, finalCorrect, finalLegacy,
        fecha_utc: new Date().toISOString() });
}
