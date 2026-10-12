const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const existing = db.getSiblingDB(databaseName).getCollectionNames().filter(name => !name.startsWith("system."));
if (existing.length !== 0) {
    throw new Error("Base no vacía: no se sobrescriben datos. Colecciones: " + existing.join(", "));
}
print("BASE_VACIA_PASS " + databaseName + " " + new Date().toISOString());
