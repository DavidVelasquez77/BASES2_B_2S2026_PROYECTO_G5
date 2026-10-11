const bootstrapPath = require("path");
const bootstrapFs = require("fs");
const commonPath = [
    bootstrapPath.join(process.cwd(), "scripts", "mongodb", "00_common.js"),
    bootstrapPath.join(process.cwd(), "fase3", "scripts", "mongodb", "00_common.js"),
    bootstrapPath.resolve(process.cwd(), "..", "fase3", "scripts", "mongodb", "00_common.js")
].find(candidate => bootstrapFs.existsSync(candidate));
if (!commonPath) throw new Error("No se encontró fase3/scripts/mongodb/00_common.js.");
load(commonPath);

const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const target = db.getSiblingDB(databaseName);
const expected = ["atletas", "entidades_geograficas", "participaciones_por_pais", "catalogo_olimpico"];
const existing = target.getCollectionNames().filter(name => !name.startsWith("system.")).sort();
if (JSON.stringify(existing) !== JSON.stringify(expected.slice().sort())) {
    throw new Error("No se crean índices: las cuatro colecciones esperadas no están presentes.");
}
if (target.atletas.countDocuments({}) === 0 || target.participaciones_por_pais.countDocuments({}) === 0) {
    throw new Error("No se crean índices: primero cargue los datos procesados.");
}

const definitions = [
    { collection: "atletas", key: { nombre: 1 }, name: "ix_atletas_nombre", reason: "Búsqueda principal por nombre recibido en el inciso c." },
    { collection: "atletas", key: { nombre_completo: 1 }, name: "ix_atletas_nombre_completo", reason: "Búsqueda por nombre completo alternativo sin reemplazar el nombre original." },
    { collection: "atletas", key: { nombre_usado: 1 }, name: "ix_atletas_nombre_usado", reason: "Búsqueda por la forma de nombre usada en las fuentes." },
    { collection: "atletas", key: { "participaciones.id_edicion": 1 }, name: "ix_atletas_participaciones_edicion", reason: "Filtrar el historial ya embebido por edición/año." },
    { collection: "entidades_geograficas", key: { nombre: 1 }, name: "ix_entidades_nombre", reason: "Localizar el documento geográfico o agregado por su nombre literal." },
    { collection: "entidades_geograficas", key: { codigo_pais: 1 }, options: { partialFilterExpression: { codigo_pais: { $type: "string" } } }, name: "ix_entidades_codigo_pais", reason: "Localizar entidades con código; excluye códigos nulos y no etiqueta agregados como países." },
    { collection: "entidades_geograficas", key: { "poblacion_anual.anio": 1 }, name: "ix_entidades_poblacion_anio", reason: "Consulta de la serie de población por año dentro del documento geográfico." },
    { collection: "participaciones_por_pais", key: { id_entidad: 1, anio: 1, temporada: 1 }, name: "ix_part_pais_edicion", reason: "Acceso por entidad geográfica y edición, eje principal del inciso d." },
    { collection: "participaciones_por_pais", key: { id_entidad: 1, "participaciones.medalla": 1 }, name: "ix_part_pais_medalla", reason: "Filtrar resultados/medallas de una entidad sin escanear todas las ediciones." },
    { collection: "catalogo_olimpico", key: { tipo: 1, id: 1 }, name: "ix_catalogo_tipo_id", reason: "Resolver referencias tipadas a NOC, sede, edición, deporte, disciplina o evento." },
    { collection: "catalogo_olimpico", key: { tipo: 1, nombre: 1 }, name: "ix_catalogo_tipo_nombre", reason: "Buscar por nombre dentro del tipo de catálogo correspondiente." }
];

const started = new Date();
const results = definitions.map(definition => {
    const options = Object.assign({}, definition.options || {}, { name: definition.name });
    const start = new Date();
    const collection = target.getCollection(definition.collection);
    const result = collection.createIndex(definition.key, options);
    const stored = collection.getIndexes().find(index => index.name === definition.name);
    if (result !== definition.name || !stored || JSON.stringify(stored.key) !== JSON.stringify(definition.key)) {
        throw new Error("El índice no quedó con la definición esperada: " + definition.name);
    }
    return {
        indice: definition.name,
        coleccion: definition.collection,
        columnas: JSON.stringify(definition.key),
        motivo: definition.reason,
        inicio_utc: start.toISOString(),
        fin_utc: new Date().toISOString(),
        estado: "PASS"
    };
});

const fs = olympMongo.fs;
const path = olympMongo.path;
const reportPath = path.join(olympMongo.phase3Root(), "docs", "mongodb", "indexes_created.csv");
fs.mkdirSync(path.dirname(reportPath), { recursive: true });
function q(value) { return '"' + String(value).replace(/"/g, '""') + '"'; }
const headers = ["indice", "coleccion", "columnas", "motivo", "inicio_utc", "fin_utc", "estado"];
const content = [headers.map(q).join(",")].concat(results.map(row => headers.map(key => q(row[key])).join(",")));
fs.writeFileSync(reportPath, "\uFEFF" + content.join("\r\n") + "\r\n", "utf8");

printjson({
    estado: "PASS",
    base: databaseName,
    indices_adicionales_creados_o_verificados: results.length,
    duracion_segundos: (Date.now() - started.getTime()) / 1000,
    indices: target.getCollectionNames().map(name => ({ coleccion: name, indices: target.getCollection(name).getIndexes().map(index => index.name) }))
});
