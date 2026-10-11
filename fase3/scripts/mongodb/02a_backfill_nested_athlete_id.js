const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const target = db.getSiblingDB(databaseName);
const athletes = target.getCollection("atletas");
const started = new Date();

if (athletes.countDocuments({}) === 0) throw new Error("Base sin atletas cargados; no se aplica el ajuste.");
const missingBefore = athletes.countDocuments({
    "participaciones.0": { $exists: true },
    "participaciones.id_atleta": { $exists: false }
});
const participationRowsBefore = athletes.aggregate([
    { $unwind: "$participaciones" },
    { $match: { "participaciones.id_atleta": { $exists: false } } },
    { $count: "total" }
]).toArray()[0]?.total || 0;

if (missingBefore > 0) {
    athletes.updateMany(
        {
            "participaciones.0": { $exists: true },
            "participaciones.id_atleta": { $exists: false }
        },
        [
            {
                $set: {
                    participaciones: {
                        $map: {
                            input: "$participaciones",
                            as: "p",
                            in: { $mergeObjects: ["$$p", { id_atleta: "$id_atleta" }] }
                        }
                    }
                }
            }
        ]
    );
}

const missingAfter = athletes.countDocuments({
    "participaciones.0": { $exists: true },
    "participaciones.id_atleta": { $exists: false }
});
if (missingAfter !== 0) throw new Error("No se completó id_atleta en todos los subdocumentos.");

printjson({
    estado: "PASS",
    base: databaseName,
    documentos_ajustados: missingBefore,
    participaciones_afectadas: participationRowsBefore,
    ids_atleta_faltantes_despues: missingAfter,
    inicio_utc: started.toISOString(),
    fin_utc: new Date().toISOString()
});
