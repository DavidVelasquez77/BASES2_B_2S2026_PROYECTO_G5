const bootstrapPath = require("path");
const bootstrapFs = require("fs");
const commonPath = [
    bootstrapPath.join(process.cwd(), "scripts", "mongodb", "00_common.js"),
    bootstrapPath.join(process.cwd(), "fase3", "scripts", "mongodb", "00_common.js"),
    bootstrapPath.resolve(process.cwd(), "..", "fase3", "scripts", "mongodb", "00_common.js")
].find(candidate => bootstrapFs.existsSync(candidate));
if (!commonPath) throw new Error("No se encontró fase3/scripts/mongodb/00_common.js.");
load(commonPath);

const root = olympMongo.projectRoot();
const processed = olympMongo.path.join(root, "data", "processed");
const reportDir = olympMongo.path.join(olympMongo.phase3Root(), "docs", "mongodb");
const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const target = db.getSiblingDB(databaseName);
const validation = [];
const expectedCounts = {
    entidad_geografica: 282, poblacion: 17024, noc: 236, atleta: 167295, sede: 42,
    edicion_olimpica: 61, deporte: 65, disciplina: 117, evento: 2069, participacion: 367793
};
const collectionNames = ["atletas", "entidades_geograficas", "participaciones_por_pais", "catalogo_olimpico"];
const allowedMedals = new Set(["Gold", "Silver", "Bronze"]);
const allowedSeasons = new Set(["Summer", "Winter", "Intercalated Games", "Summer Youth", "Winter Youth"]);
let validationFailed = false;

function record(name, expected, actual, detail) {
    const state = String(expected) === String(actual) ? "PASS" : "FAIL";
    validation.push({ validacion: name, esperado: expected, actual, estado: state, detalle: detail });
    if (state === "FAIL") validationFailed = true;
}
function sameText(raw, actual) { return olympMongo.stringValue(raw) === actual; }
function sameInt(raw, actual, label, longType) {
    const expected = longType ? olympMongo.int64(raw, label) : olympMongo.int32(raw, label);
    if (expected === null || actual === null || actual === undefined) return expected === actual;
    return String(expected) === String(actual);
}
function sameDecimal(raw, actual, label) {
    const expected = olympMongo.decimal(raw, label);
    if (expected === null || actual === null || actual === undefined) return expected === actual;
    return String(expected) === String(actual);
}
function sameDate(raw, actual, label) {
    const expected = olympMongo.date(raw, label);
    if (expected === null || actual === null || actual === undefined) return expected === actual;
    return expected.toISOString() === actual.toISOString();
}
function sameBoolean(raw, actual, label) { return olympMongo.boolean(raw, label) === actual; }
function sizeSummary(name) {
    return target.getCollection(name).aggregate([
        { $project: { bytes: { $bsonSize: "$$ROOT" } } },
        { $group: { _id: null, max: { $max: "$bytes" }, promedio: { $avg: "$bytes" }, documentos: { $sum: 1 } } }
    ], { allowDiskUse: true }).toArray()[0] || { max: 0, promedio: 0, documentos: 0 };
}

const names = olympMongo.fs.readdirSync(processed).filter(file => file.toLowerCase().endsWith(".csv")).sort();
record("csv_procesados", 10, names.length, "Se validan los diez CSV procesados esperados.");
const sourceManifest = olympMongo.parseCsv(olympMongo.path.join(reportDir, "processed_source_manifest.csv"));
const manifestByFile = new Map(sourceManifest.map(row => [row.archivo, row.sha256_antes]));
let hashMismatches = 0;
names.forEach(file => {
    const expectedHash = manifestByFile.get(file);
    if (!expectedHash || olympMongo.sha256(olympMongo.path.join(processed, file)) !== expectedHash) hashMismatches += 1;
});
record("hashes_csv_procesados", "10 MATCH", (10 - hashMismatches) + " MATCH", "SHA-256 comparado contra el manifiesto tomado al cargar.");

const sourceAthletes = olympMongo.parseCsv(olympMongo.path.join(processed, "atleta.csv"));
const sourceAthleteById = new Map(sourceAthletes.map(row => [olympMongo.key(row.id_atleta, "atleta.id_atleta"), row]));
const sourceParticipations = olympMongo.parseCsv(olympMongo.path.join(processed, "participacion.csv"));
const sourceParticipationById = new Map(sourceParticipations.map(row => [olympMongo.key(row.id_participacion, "participacion.id_participacion"), row]));
const otherSources = {};
["entidad_geografica", "poblacion", "noc", "sede", "edicion_olimpica", "deporte", "disciplina", "evento"].forEach(name => {
    otherSources[name] = olympMongo.parseCsv(olympMongo.path.join(processed, name + ".csv"));
});

const collectionExpected = {
    atletas: expectedCounts.atleta,
    entidades_geograficas: expectedCounts.entidad_geografica,
    participaciones_por_pais: 4856,
    catalogo_olimpico: 2590
};
collectionNames.forEach(name => record("documentos." + name, collectionExpected[name], target.getCollection(name).countDocuments({}), "Conteo de documentos persistidos."));
record("filas_poblacion_embebidas", expectedCounts.poblacion,
    target.entidades_geograficas.aggregate([{ $unwind: "$poblacion_anual" }, { $count: "total" }]).toArray()[0]?.total || 0,
    "Cada fila (entidad, año) se conserva en la serie temporal.");

let athleteTextComparisons = 0;
let athleteTextDifferences = 0;
let nonAsciiNames = 0;
let athleteFieldComparisons = 0;
let athleteFieldDifferences = 0;
let participationFieldComparisons = 0;
let participationFieldDifferences = 0;
let participationCopiesInAthletes = 0;
let athleteParticipationDuplicateIds = 0;
const seenParticipationIds = new Set();
const athleteTextFields = ["nombre", "nombre_completo", "nombre_usado", "nombre_original", "otros_nombres", "apodos", "orden_nombre", "sexo", "ciudad_nacimiento", "region_nacimiento", "ciudad_fallecimiento", "region_fallecimiento", "roles", "afiliaciones", "titulos"];
const athleteIdFields = ["id_pais_nacimiento", "id_pais_nacionalidad", "id_pais_fallecimiento"];
const athleteDecimalFields = ["altura_cm", "peso_kg", "latitud", "longitud"];
const participationTextFields = ["equipo", "nombre_competencia", "estado_resultado", "medalla"];
const participationIdFields64 = ["id_participacion", "id_atleta", "id_evento"];
const participationIdFields32 = ["id_edicion", "id_noc", "id_pais_nacionalidad", "posicion"];
const participationDecimalFields = ["edad", "altura_cm_registrada", "peso_kg_registrado"];

target.atletas.find({}, {
        id_atleta: 1, nombre: 1, nombre_completo: 1, nombre_usado: 1, nombre_original: 1,
        otros_nombres: 1, apodos: 1, orden_nombre: 1, sexo: 1, fecha_nacimiento: 1,
        ciudad_nacimiento: 1, region_nacimiento: 1, id_pais_nacimiento: 1,
        id_pais_nacionalidad: 1, fecha_fallecimiento: 1, ciudad_fallecimiento: 1,
        region_fallecimiento: 1, id_pais_fallecimiento: 1, altura_cm: 1, peso_kg: 1,
        roles: 1, afiliaciones: 1, titulos: 1, latitud: 1, longitud: 1,
        participaciones: 1
}).forEach(doc => {
    const id = String(doc.id_atleta);
    const source = sourceAthleteById.get(id);
    if (!source) { athleteFieldDifferences += 1; return; }
    athleteTextComparisons += 1;
    if ([...doc.nombre].some(ch => ch.codePointAt(0) > 127)) nonAsciiNames += 1;
    if (source.nombre !== doc.nombre) athleteTextDifferences += 1;
    athleteTextFields.forEach(field => {
        athleteFieldComparisons += 1;
        if (!sameText(source[field], doc[field])) athleteFieldDifferences += 1;
    });
    ["id_atleta"].forEach(field => {
        athleteFieldComparisons += 1;
        if (!sameInt(source[field], doc[field], "atleta." + field, true)) athleteFieldDifferences += 1;
    });
    athleteIdFields.forEach(field => {
        athleteFieldComparisons += 1;
        if (!sameInt(source[field], doc[field], "atleta." + field, false)) athleteFieldDifferences += 1;
    });
    athleteDecimalFields.forEach(field => {
        athleteFieldComparisons += 1;
        if (!sameDecimal(source[field], doc[field], "atleta." + field)) athleteFieldDifferences += 1;
    });
    ["fecha_nacimiento", "fecha_fallecimiento"].forEach(field => {
        athleteFieldComparisons += 1;
        if (!sameDate(source[field], doc[field], "atleta." + field)) athleteFieldDifferences += 1;
    });

    doc.participaciones.forEach(part => {
        participationCopiesInAthletes += 1;
        const partId = String(part.id_participacion);
        if (seenParticipationIds.has(partId)) athleteParticipationDuplicateIds += 1;
        seenParticipationIds.add(partId);
        const sourcePart = sourceParticipationById.get(partId);
        if (!sourcePart) { participationFieldDifferences += 1; return; }
        participationIdFields64.forEach(field => {
            participationFieldComparisons += 1;
            if (!sameInt(sourcePart[field], part[field], "participacion." + field, true)) participationFieldDifferences += 1;
        });
        participationIdFields32.forEach(field => {
            participationFieldComparisons += 1;
            if (!sameInt(sourcePart[field], part[field], "participacion." + field, false)) participationFieldDifferences += 1;
        });
        participationTextFields.forEach(field => {
            participationFieldComparisons += 1;
            if (!sameText(sourcePart[field], part[field])) participationFieldDifferences += 1;
        });
        participationDecimalFields.forEach(field => {
            participationFieldComparisons += 1;
            if (!sameDecimal(sourcePart[field], part[field], "participacion." + field)) participationFieldDifferences += 1;
        });
        participationFieldComparisons += 1;
        if (!sameBoolean(sourcePart.empatado, part.empatado, "participacion.empatado")) participationFieldDifferences += 1;
    });
});

record("nombres_atleta_comparados", expectedCounts.atleta, athleteTextComparisons, "Todos los nombre exactos se comparan contra atleta.csv.");
record("nombres_no_ascii_csv", 25911, nonAsciiNames, "Nombres con caracteres no ASCII, medidos en la colección Mongo.");
record("diferencias_unicode_nombre", 0, athleteTextDifferences, "Comparación de nombre carácter por carácter CSV → MongoDB.");
record("campos_atleta_comparados", 0, athleteFieldDifferences, athleteFieldComparisons + " comparaciones de texto, fechas, identificadores y decimales contra atleta.csv.");
record("filas_participacion_en_atletas", expectedCounts.participacion, participationCopiesInAthletes, "Suma de participaciones embebidas por atleta.");
record("participaciones_unicas_en_atletas", 0, athleteParticipationDuplicateIds, "Repeticiones de id_participacion en la vista atleta.");
record("campos_participacion_comparados", 0, participationFieldDifferences, participationFieldComparisons + " comparaciones de campos contra participacion.csv.");
record("participaciones_faltantes_en_atletas", 0, sourceParticipationById.size - participationCopiesInAthletes, "Filas del CSV no encontradas bajo su atleta.");

let countryParticipationCount = 0;
let countryParticipationDuplicateIds = 0;
let countryFieldComparisons = 0;
let countryFieldDifferences = 0;
const countrySeenIds = new Set();
let unassignedParticipationCount = 0;
target.participaciones_por_pais.find({}, { tipo_agrupacion: 1, id_edicion: 1, participaciones: 1 }).forEach(group => {
    if (group.tipo_agrupacion !== "ENTIDAD_GEOGRAFICA") unassignedParticipationCount += group.participaciones.length;
    group.participaciones.forEach(part => {
        countryParticipationCount += 1;
        const id = String(part.id_participacion);
        if (countrySeenIds.has(id)) countryParticipationDuplicateIds += 1;
        countrySeenIds.add(id);
        const source = sourceParticipationById.get(id);
        if (!source) { countryFieldDifferences += 1; return; }
        ["id_participacion", "id_atleta", "id_evento"].forEach(field => {
            countryFieldComparisons += 1;
            if (!sameInt(source[field], part[field], "participacion." + field, true)) countryFieldDifferences += 1;
        });
        ["id_noc", "id_pais_nacionalidad", "posicion"].forEach(field => {
            countryFieldComparisons += 1;
            if (!sameInt(source[field], part[field], "participacion." + field, false)) countryFieldDifferences += 1;
        });
        countryFieldComparisons += 1;
        if (!sameInt(source.id_edicion, group.id_edicion, "participacion.id_edicion", false)) countryFieldDifferences += 1;
        ["equipo", "nombre_competencia", "estado_resultado", "medalla"].forEach(field => {
            countryFieldComparisons += 1;
            if (!sameText(source[field], part[field])) countryFieldDifferences += 1;
        });
        ["edad", "altura_cm_registrada", "peso_kg_registrado"].forEach(field => {
            countryFieldComparisons += 1;
            if (!sameDecimal(source[field], part[field], "participacion." + field)) countryFieldDifferences += 1;
        });
        countryFieldComparisons += 1;
        if (!sameBoolean(source.empatado, part.empatado, "participacion.empatado")) countryFieldDifferences += 1;
    });
});
record("filas_participacion_vista_pais_noc", expectedCounts.participacion, countryParticipationCount, "Incluye particiones por entidad y buckets de NOC sin entidad.");
record("participaciones_unicas_vista_pais_noc", 0, countryParticipationDuplicateIds, "Repeticiones de id_participacion dentro de esta vista.");
record("campos_participacion_vista_pais_noc", 0, countryFieldDifferences,
    countryFieldComparisons + " comparaciones exactas de los 15 campos de participacion.csv contra la vista de país/NOC.");
record("participaciones_sin_entidad_geografica", 1877, unassignedParticipationCount, "Se guardan sin atribución de país, agrupadas por NOC.");

const geographyById = new Map();
const populationByKey = new Map();
let duplicatePopulationKeys = 0;
target.entidades_geograficas.find({}, { id_entidad: 1, nombre: 1, codigo_pais: 1, poblacion_anual: 1 }).forEach(doc => {
    geographyById.set(String(doc.id_entidad), doc);
    doc.poblacion_anual.forEach(item => {
        const key = String(doc.id_entidad) + ":" + String(item.anio);
        if (populationByKey.has(key)) duplicatePopulationKeys += 1;
        populationByKey.set(key, item);
    });
});
let geographyComparisons = 0;
let geographyDifferences = 0;
otherSources.entidad_geografica.forEach(row => {
    const doc = geographyById.get(row.id_entidad);
    if (!doc) { geographyDifferences += 1; return; }
    geographyComparisons += 3;
    if (!sameInt(row.id_entidad, doc.id_entidad, "entidad_geografica.id_entidad", false)) geographyDifferences += 1;
    if (!sameText(row.nombre, doc.nombre)) geographyDifferences += 1;
    if (!sameText(row.codigo_pais, doc.codigo_pais)) geographyDifferences += 1;
});
record("campos_entidad_geografica_exactos", 0, geographyDifferences, geographyComparisons + " campos comparados contra entidad_geografica.csv.");

let populationComparisons = 0;
let populationDifferences = 0;
otherSources.poblacion.forEach(row => {
    const item = populationByKey.get(row.id_entidad + ":" + row.anio);
    if (!item) { populationDifferences += 1; return; }
    populationComparisons += 2;
    if (!sameInt(row.anio, item.anio, "poblacion.anio", false)) populationDifferences += 1;
    if (!sameInt(row.poblacion, item.poblacion, "poblacion.poblacion", true)) populationDifferences += 1;
});
record("campos_poblacion_exactos", 0, populationDifferences, populationComparisons + " campos comparados contra poblacion.csv.");
record("claves_poblacion_duplicadas_en_mongo", 0, duplicatePopulationKeys, "Clave lógica (id_entidad, anio) en la serie anidada.");

const catalogByKey = new Map();
target.catalogo_olimpico.find({}).forEach(doc => catalogByKey.set(doc.tipo + ":" + String(doc.id), doc));
const catalogSpecs = [
    { csv: "noc", tipo: "NOC", key: "id_noc", fields: [["id_noc", "int"], ["codigo_noc", "text"], ["nombre_noc", "text"], ["id_entidad", "int"], ["notas", "text"]] },
    { csv: "sede", tipo: "SEDE", key: "id_sede", fields: [["id_sede", "int"], ["nombre", "text"], ["id_pais", "int"]] },
    { csv: "edicion_olimpica", tipo: "EDICION_OLIMPICA", key: "id_edicion", fields: [["id_edicion", "int"], ["anio", "int"], ["temporada", "text"], ["id_sede", "int"]] },
    { csv: "deporte", tipo: "DEPORTE", key: "id_deporte", fields: [["id_deporte", "int"], ["nombre", "text"]] },
    { csv: "disciplina", tipo: "DISCIPLINA", key: "id_disciplina", fields: [["id_disciplina", "int"], ["id_deporte", "int"], ["nombre", "text"]] },
    { csv: "evento", tipo: "EVENTO", key: "id_evento", fields: [["id_evento", "long"], ["id_disciplina", "int"], ["nombre", "text"]] }
];
catalogSpecs.forEach(spec => {
    let comparisons = 0;
    let differences = 0;
    otherSources[spec.csv].forEach(row => {
        const doc = catalogByKey.get(spec.tipo + ":" + row[spec.key]);
        if (!doc) { differences += 1; return; }
        spec.fields.forEach(([field, kind]) => {
            comparisons += 1;
            const same = kind === "text" ? sameText(row[field], doc[field]) :
                sameInt(row[field], doc[field], spec.csv + "." + field, kind === "long");
            if (!same) differences += 1;
        });
    });
    record("campos_catalogo_" + spec.csv + "_exactos", 0, differences,
        comparisons + " campos comparados contra " + spec.csv + ".csv.");
});

const disciplineSourceById = new Map(otherSources.disciplina.map(row => [row.id_disciplina, row]));
const sportSourceById = new Map(otherSources.deporte.map(row => [row.id_deporte, row]));
let eventHierarchyDifferences = 0;
otherSources.evento.forEach(row => {
    const doc = catalogByKey.get("EVENTO:" + row.id_evento);
    const sourceDiscipline = disciplineSourceById.get(row.id_disciplina);
    const sourceSport = sourceDiscipline && sportSourceById.get(sourceDiscipline.id_deporte);
    const nested = doc && doc.disciplina;
    if (!sourceDiscipline || !sourceSport || !nested || nested.id_evento !== undefined ||
        String(nested.id_disciplina) !== sourceDiscipline.id_disciplina ||
        nested.nombre !== sourceDiscipline.nombre ||
        String(nested.id_deporte) !== sourceSport.id_deporte ||
        !nested.deporte || nested.deporte.nombre !== sourceSport.nombre ||
        String(nested.deporte.id_deporte) !== sourceSport.id_deporte) eventHierarchyDifferences += 1;
});
record("jerarquia_evento_disciplina_deporte", 0, eventHierarchyDifferences,
    "Cada EVENTO anida su DISCIPLINA y DEPORTE sin envolver de nuevo el EVENTO.");

let invalidMedals = 0;
let invalidSeasons = 0;
target.atletas.find({}, { participaciones: 1 }).forEach(doc => doc.participaciones.forEach(part => {
    if (part.medalla !== null && !allowedMedals.has(part.medalla)) invalidMedals += 1;
}));
target.catalogo_olimpico.find({ tipo: "EDICION_OLIMPICA" }, { temporada: 1 }).forEach(doc => {
    if (!allowedSeasons.has(doc.temporada)) invalidSeasons += 1;
});
record("medallas_fuera_de_dominio", 0, invalidMedals, "Solo Gold, Silver, Bronze o null.");
record("temporadas_fuera_de_dominio", 0, invalidSeasons, "Se conservan las cinco categorías presentes en processed.");

const expectedCatalogTypes = { DEPORTE: 65, DISCIPLINA: 117, EVENTO: 2069, EDICION_OLIMPICA: 61, SEDE: 42, NOC: 236 };
Object.keys(expectedCatalogTypes).forEach(type => record("catalogo." + type, expectedCatalogTypes[type], target.catalogo_olimpico.countDocuments({ tipo: type }), "Registros conservados por tipo dentro del catálogo funcional."));

const expectedIndexes = {
    atletas: ["ix_atletas_nombre", "ix_atletas_nombre_completo", "ix_atletas_nombre_usado", "ix_atletas_participaciones_edicion"],
    entidades_geograficas: ["ix_entidades_nombre", "ix_entidades_codigo_pais", "ix_entidades_poblacion_anio"],
    participaciones_por_pais: ["ix_part_pais_edicion", "ix_part_pais_medalla"],
    catalogo_olimpico: ["ix_catalogo_tipo_id", "ix_catalogo_tipo_nombre"]
};
let missingIndexes = 0;
let actualIndexCount = 0;
collectionNames.forEach(name => {
    const indexes = target.getCollection(name).getIndexes().map(index => index.name);
    actualIndexCount += indexes.filter(index => index !== "_id_").length;
    expectedIndexes[name].forEach(index => { if (!indexes.includes(index)) missingIndexes += 1; });
});
record("indices_adicionales", 11, actualIndexCount, "No incluye los índices _id_ automáticos.");
record("indices_faltantes", 0, missingIndexes, "Índices funcionales declarados en 03_create_indexes.js.");

let validatorsActive = 0;
collectionNames.forEach(name => {
    const info = target.getCollectionInfos({ name })[0];
    if (info && info.options && info.options.validationLevel === "strict" && info.options.validationAction === "error" && info.options.validator) validatorsActive += 1;
});
record("validadores_json_schema_activos", 4, validatorsActive, "Validación estricta de documentos en las cuatro colecciones.");

const bsonRows = collectionNames.map(name => {
    const summary = sizeSummary(name);
    return { coleccion: name, documentos: summary.documentos, bson_maximo_bytes: summary.max, bson_promedio_bytes: Math.round(summary.promedio), limite_bytes: 16 * 1024 * 1024, estado: summary.max < 16 * 1024 * 1024 ? "PASS" : "FAIL" };
});
const bsonFailures = bsonRows.filter(row => row.estado !== "PASS").length;
record("documentos_bson_menores_a_16_mib", 0, bsonFailures, "Tamaño medido directamente en MongoDB mediante $bsonSize.");

const finalHashes = names.filter(file => olympMongo.sha256(olympMongo.path.join(processed, file)) !== manifestByFile.get(file)).length;
record("integridad_csv_procesados", 0, finalHashes, "Ningún CSV se modifica durante el proceso de lectura/carga.");

olympMongo.writeCsv(olympMongo.path.join(reportDir, "load_validation.csv"),
    ["validacion", "esperado", "actual", "estado", "detalle"], validation);
olympMongo.writeCsv(olympMongo.path.join(reportDir, "bson_size_report.csv"),
    ["coleccion", "documentos", "bson_maximo_bytes", "bson_promedio_bytes", "limite_bytes", "estado"], bsonRows);

printjson({
    estado: validationFailed ? "FAIL" : "PASS",
    base: databaseName,
    validaciones: validation.length,
    fallos: validation.filter(row => row.estado === "FAIL").map(row => row.validacion),
    nombres_no_ascii_csv: nonAsciiNames,
    diferencias_unicode: athleteTextDifferences,
    campos_atleta_comparados: athleteFieldComparisons,
    diferencias_atleta: athleteFieldDifferences,
    campos_participacion_comparados: participationFieldComparisons,
    diferencias_participacion: participationFieldDifferences,
    participaciones: { atleta: participationCopiesInAthletes, vista_pais_noc: countryParticipationCount, sin_entidad: unassignedParticipationCount },
    bson_maximo_bytes: bsonRows.reduce((max, row) => Math.max(max, row.bson_maximo_bytes), 0),
    fecha_utc: new Date().toISOString()
});
if (validationFailed) throw new Error("La validación posterior registró uno o más FAIL.");
