const bootstrapPath = require("path");
const bootstrapFs = require("fs");
const commonPath = [
    bootstrapPath.join(process.cwd(), "scripts", "mongodb", "00_common.js"),
    bootstrapPath.join(process.cwd(), "fase3", "scripts", "mongodb", "00_common.js"),
    bootstrapPath.resolve(process.cwd(), "..", "fase3", "scripts", "mongodb", "00_common.js")
].find(candidate => bootstrapFs.existsSync(candidate));
if (!commonPath) throw new Error("No se encontró fase3/scripts/mongodb/00_common.js.");
load(commonPath);

const fs = olympMongo.fs;
const path = olympMongo.path;
const root = olympMongo.projectRoot();
const processed = path.join(root, "data", "processed");
const reportDir = path.join(olympMongo.phase3Root(), "docs", "mongodb");
const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const apply = process.env.OLIMPIADAS_MONGO_APPLY === "1";
const MAX_BSON = 16 * 1024 * 1024;
const BATCH_MAX_BYTES = 8 * 1024 * 1024;
const BATCH_MAX_DOCS = 500;
const expectedCounts = {
    entidad_geografica: 282,
    poblacion: 17024,
    noc: 236,
    atleta: 167295,
    sede: 42,
    edicion_olimpica: 61,
    deporte: 65,
    disciplina: 117,
    evento: 2069,
    participacion: 367793
};
const expectedFiles = Object.keys(expectedCounts).map(name => name + ".csv").sort();
const collectionNames = [
    "atletas", "entidades_geograficas", "participaciones_por_pais", "catalogo_olimpico"
];
const runStart = new Date();
const validations = [];
const metrics = [];

function check(name, expected, actual, detail, blocking) {
    const state = expected === actual ? "PASS" : (blocking ? "FAIL" : "WARN");
    validations.push({ validacion: name, esperado: expected, actual, estado: state, detalle: detail });
    if (state === "FAIL") throw new Error("Prevalidación fallida: " + name + " (" + actual + ")");
}

function readTable(name) {
    const started = new Date();
    const rows = olympMongo.parseCsv(path.join(processed, name + ".csv"));
    metrics.push({ etapa: "lectura_csv_" + name, filas: rows.length, inicio: started.toISOString(), fin: new Date().toISOString(), duracion_segundos: (Date.now() - started.getTime()) / 1000, estado: "PASS" });
    check("filas_csv." + name, expectedCounts[name], rows.length, "Filas del CSV procesado", true);
    return rows;
}

function mustText(value, label) {
    const result = olympMongo.stringValue(value);
    if (result === null) throw new Error(label + " obligatorio vacío.");
    return result;
}

function mapUnique(rows, field, label) {
    const result = new Map();
    rows.forEach(row => {
        const mapKey = olympMongo.key(row[field], label + "." + field);
        if (mapKey === null) throw new Error(label + "." + field + " nulo.");
        if (result.has(mapKey)) throw new Error("Clave duplicada " + label + "." + field + "=" + mapKey);
        result.set(mapKey, row);
    });
    return result;
}

function duplicateCount(values) {
    const seen = new Set();
    let duplicates = 0;
    values.forEach(value => {
        if (seen.has(value)) duplicates += 1;
        else seen.add(value);
    });
    return duplicates;
}

function requireReference(map, id, label, nullable) {
    if (id === null && nullable) return null;
    const k = id === null ? null : id.toString();
    if (k === null || !map.has(k)) throw new Error("FK inexistente " + label + "=" + k);
    return map.get(k);
}

function entityRef(entityId, entityRowsById) {
    if (entityId === null) return null;
    const row = requireReference(entityRowsById, entityId, "ENTIDAD_GEOGRAFICA", false);
    return { id_entidad: row.id_entidad, nombre: row.nombre, codigo_pais: row.codigo_pais };
}

function longSort(a, b) {
    const left = BigInt(a.toString());
    const right = BigInt(b.toString());
    return left < right ? -1 : left > right ? 1 : 0;
}

if (!fs.existsSync(processed)) throw new Error("No existe " + processed);
const csvFiles = fs.readdirSync(processed).filter(name => name.toLowerCase().endsWith(".csv")).sort();
if (JSON.stringify(csvFiles) !== JSON.stringify(expectedFiles)) {
    throw new Error("Se esperaba exactamente el conjunto oficial de 10 CSV. Encontrados: " + csvFiles.join(", "));
}
fs.mkdirSync(reportDir, { recursive: true });
const sourceHashesBefore = csvFiles.map(file => ({
    archivo: file,
    sha256_antes: olympMongo.sha256(path.join(processed, file))
}));

const raw = {};
Object.keys(expectedCounts).forEach(name => { raw[name] = readTable(name); });

const primaryKeys = {
    entidad_geografica: ["id_entidad"], noc: ["id_noc"], atleta: ["id_atleta"],
    sede: ["id_sede"], edicion_olimpica: ["id_edicion"], deporte: ["id_deporte"],
    disciplina: ["id_disciplina"], evento: ["id_evento"], participacion: ["id_participacion"]
};
let primaryKeyDuplicates = 0;
Object.keys(primaryKeys).forEach(table => primaryKeys[table].forEach(field => {
    const keys = raw[table].map(row => olympMongo.key(row[field], table + "." + field));
    primaryKeyDuplicates += duplicateCount(keys);
}));
const populationKeysSource = raw.poblacion.map(row =>
    olympMongo.key(row.id_entidad, "poblacion.id_entidad") + ":" + olympMongo.key(row.anio, "poblacion.anio")
);
const populationKeyDuplicates = duplicateCount(populationKeysSource);
check("claves_primarias_duplicadas", 0, primaryKeyDuplicates,
    "Se verifican las claves de las nueve tablas con clave simple.", true);
check("claves_compuestas_poblacion_duplicadas", 0, populationKeyDuplicates,
    "Clave compuesta (id_entidad, anio).", true);

const geoRows = raw.entidad_geografica.map(r => ({
    _id: olympMongo.int32(r.id_entidad, "entidad_geografica.id_entidad"),
    id_entidad: olympMongo.int32(r.id_entidad, "entidad_geografica.id_entidad"),
    nombre: mustText(r.nombre, "entidad_geografica.nombre"),
    codigo_pais: olympMongo.stringValue(r.codigo_pais),
    origen_csv: "entidad_geografica.csv"
}));
const geoById = mapUnique(geoRows, "id_entidad", "ENTIDAD_GEOGRAFICA");

const popRows = raw.poblacion.map(r => ({
    id_entidad: olympMongo.int32(r.id_entidad, "poblacion.id_entidad"),
    anio: olympMongo.int32(r.anio, "poblacion.anio"),
    poblacion: olympMongo.int64(r.poblacion, "poblacion.poblacion")
}));
const populationKeys = new Set();
const populationByEntity = new Map();
popRows.forEach(r => {
    requireReference(geoById, r.id_entidad, "POBLACION.id_entidad", false);
    const compound = r.id_entidad.toString() + ":" + r.anio.toString();
    if (populationKeys.has(compound)) throw new Error("Clave POBLACION duplicada: " + compound);
    populationKeys.add(compound);
    if (!populationByEntity.has(r.id_entidad.toString())) populationByEntity.set(r.id_entidad.toString(), []);
    populationByEntity.get(r.id_entidad.toString()).push({ anio: r.anio, poblacion: r.poblacion });
});
populationByEntity.forEach(items => items.sort((a, b) => Number(a.anio) - Number(b.anio)));

const nocRows = raw.noc.map(r => {
    const idEntity = olympMongo.int32(r.id_entidad, "noc.id_entidad");
    if (idEntity !== null) requireReference(geoById, idEntity, "NOC.id_entidad", false);
    return {
        _id: olympMongo.int32(r.id_noc, "noc.id_noc"),
        id_noc: olympMongo.int32(r.id_noc, "noc.id_noc"),
        codigo_noc: mustText(r.codigo_noc, "noc.codigo_noc"),
        nombre_noc: olympMongo.stringValue(r.nombre_noc),
        id_entidad: idEntity,
        id_entidad_csv: r.id_entidad,
        notas: olympMongo.stringValue(r.notas),
        origen_csv: "noc.csv"
    };
});
const nocById = mapUnique(nocRows, "id_noc", "NOC");
const nocsByEntity = new Map();
nocRows.forEach(noc => {
    if (noc.id_entidad === null) return;
    const key = noc.id_entidad.toString();
    if (!nocsByEntity.has(key)) nocsByEntity.set(key, []);
    nocsByEntity.get(key).push({ id_noc: noc.id_noc, codigo_noc: noc.codigo_noc, nombre_noc: noc.nombre_noc });
});

const sportRows = raw.deporte.map(r => ({
    id_deporte: olympMongo.int32(r.id_deporte, "deporte.id_deporte"),
    nombre: mustText(r.nombre, "deporte.nombre")
}));
const sportById = mapUnique(sportRows, "id_deporte", "DEPORTE");
const disciplineRows = raw.disciplina.map(r => ({
    id_disciplina: olympMongo.int32(r.id_disciplina, "disciplina.id_disciplina"),
    id_deporte: olympMongo.int32(r.id_deporte, "disciplina.id_deporte"),
    nombre: mustText(r.nombre, "disciplina.nombre")
}));
const disciplineById = mapUnique(disciplineRows, "id_disciplina", "DISCIPLINA");
disciplineRows.forEach(r => requireReference(sportById, r.id_deporte, "DISCIPLINA.id_deporte", false));
const eventRows = raw.evento.map(r => ({
    id_evento: olympMongo.int64(r.id_evento, "evento.id_evento"),
    id_disciplina: olympMongo.int32(r.id_disciplina, "evento.id_disciplina"),
    nombre: mustText(r.nombre, "evento.nombre")
}));
const eventById = mapUnique(eventRows, "id_evento", "EVENTO");
eventRows.forEach(r => requireReference(disciplineById, r.id_disciplina, "EVENTO.id_disciplina", false));

const venueRows = raw.sede.map(r => ({
    id_sede: olympMongo.int32(r.id_sede, "sede.id_sede"),
    nombre: mustText(r.nombre, "sede.nombre"),
    id_pais: olympMongo.int32(r.id_pais, "sede.id_pais")
}));
const venueById = mapUnique(venueRows, "id_sede", "SEDE");
venueRows.forEach(r => requireReference(geoById, r.id_pais, "SEDE.id_pais", false));
const editionRows = raw.edicion_olimpica.map(r => ({
    id_edicion: olympMongo.int32(r.id_edicion, "edicion_olimpica.id_edicion"),
    anio: olympMongo.int32(r.anio, "edicion_olimpica.anio"),
    temporada: mustText(r.temporada, "edicion_olimpica.temporada"),
    id_sede: olympMongo.int32(r.id_sede, "edicion_olimpica.id_sede")
}));
const editionById = mapUnique(editionRows, "id_edicion", "EDICION_OLIMPICA");
const allowedSeasons = new Set(["Summer", "Winter", "Intercalated Games", "Summer Youth", "Winter Youth"]);
editionRows.forEach(r => {
    if (!allowedSeasons.has(r.temporada)) throw new Error("Temporada fuera del dominio: " + r.temporada);
    if (r.id_sede !== null) requireReference(venueById, r.id_sede, "EDICION_OLIMPICA.id_sede", false);
});

function editionView(edition) {
    const venue = edition.id_sede === null ? null : requireReference(venueById, edition.id_sede, "EDICION_OLIMPICA.id_sede", false);
    return {
        id_edicion: edition.id_edicion,
        anio: edition.anio,
        temporada: edition.temporada,
        id_sede: edition.id_sede,
        sede: venue === null ? null : {
            id_sede: venue.id_sede,
            nombre: venue.nombre,
            id_pais: venue.id_pais,
            pais: entityRef(venue.id_pais, geoById)
        }
    };
}

function eventView(event) {
    const discipline = requireReference(disciplineById, event.id_disciplina, "EVENTO.id_disciplina", false);
    const sport = requireReference(sportById, discipline.id_deporte, "DISCIPLINA.id_deporte", false);
    return {
        id_evento: event.id_evento,
        nombre: event.nombre,
        id_disciplina: discipline.id_disciplina,
        disciplina: {
            id_disciplina: discipline.id_disciplina,
            nombre: discipline.nombre,
            id_deporte: sport.id_deporte,
            deporte: { id_deporte: sport.id_deporte, nombre: sport.nombre }
        }
    };
}

function nocView(noc) {
    if (noc === null) return null;
    return {
        id_noc: noc.id_noc,
        codigo_noc: noc.codigo_noc,
        nombre_noc: noc.nombre_noc,
        id_entidad: noc.id_entidad,
        entidad: entityRef(noc.id_entidad, geoById),
        notas: noc.notas
    };
}

const athleteRows = raw.atleta.map(r => {
    const doc = {
        _id: olympMongo.int64(r.id_atleta, "atleta.id_atleta"),
        id_atleta: olympMongo.int64(r.id_atleta, "atleta.id_atleta"),
        nombre: mustText(r.nombre, "atleta.nombre"),
        nombre_completo: olympMongo.stringValue(r.nombre_completo),
        nombre_usado: olympMongo.stringValue(r.nombre_usado),
        nombre_original: olympMongo.stringValue(r.nombre_original),
        otros_nombres: olympMongo.stringValue(r.otros_nombres),
        apodos: olympMongo.stringValue(r.apodos),
        orden_nombre: olympMongo.stringValue(r.orden_nombre),
        sexo: olympMongo.stringValue(r.sexo),
        fecha_nacimiento: olympMongo.date(r.fecha_nacimiento, "atleta.fecha_nacimiento"),
        ciudad_nacimiento: olympMongo.stringValue(r.ciudad_nacimiento),
        region_nacimiento: olympMongo.stringValue(r.region_nacimiento),
        id_pais_nacimiento: olympMongo.int32(r.id_pais_nacimiento, "atleta.id_pais_nacimiento"),
        fecha_fallecimiento: olympMongo.date(r.fecha_fallecimiento, "atleta.fecha_fallecimiento"),
        ciudad_fallecimiento: olympMongo.stringValue(r.ciudad_fallecimiento),
        region_fallecimiento: olympMongo.stringValue(r.region_fallecimiento),
        id_pais_fallecimiento: olympMongo.int32(r.id_pais_fallecimiento, "atleta.id_pais_fallecimiento"),
        id_pais_nacionalidad: olympMongo.int32(r.id_pais_nacionalidad, "atleta.id_pais_nacionalidad"),
        altura_cm: olympMongo.decimal(r.altura_cm, "atleta.altura_cm"),
        peso_kg: olympMongo.decimal(r.peso_kg, "atleta.peso_kg"),
        roles: olympMongo.stringValue(r.roles),
        afiliaciones: olympMongo.stringValue(r.afiliaciones),
        titulos: olympMongo.stringValue(r.titulos),
        latitud: olympMongo.decimal(r.latitud, "atleta.latitud"),
        longitud: olympMongo.decimal(r.longitud, "atleta.longitud"),
        pais_nacimiento: entityRef(olympMongo.int32(r.id_pais_nacimiento, "atleta.id_pais_nacimiento"), geoById),
        pais_nacionalidad: entityRef(olympMongo.int32(r.id_pais_nacionalidad, "atleta.id_pais_nacionalidad"), geoById),
        pais_fallecimiento: entityRef(olympMongo.int32(r.id_pais_fallecimiento, "atleta.id_pais_fallecimiento"), geoById),
        participaciones: [],
        origen_csv: "atleta.csv"
    };
    [doc.id_pais_nacimiento, doc.id_pais_nacionalidad, doc.id_pais_fallecimiento].forEach(id => {
        if (id !== null) requireReference(geoById, id, "ATLETA.país", false);
    });
    return doc;
});
const athletes = mapUnique(athleteRows, "id_atleta", "ATLETA");

function countOrphans(rows, field, referenceMap, nullable, label) {
    let count = 0;
    rows.forEach(row => {
        const k = olympMongo.key(row[field], label + "." + field);
        if (k === null && nullable) return;
        if (k === null || !referenceMap.has(k)) count += 1;
    });
    return count;
}
const foreignKeyOrphans =
    countOrphans(raw.poblacion, "id_entidad", geoById, false, "POBLACION") +
    countOrphans(raw.noc, "id_entidad", geoById, true, "NOC") +
    countOrphans(raw.sede, "id_pais", geoById, false, "SEDE") +
    countOrphans(raw.edicion_olimpica, "id_sede", venueById, true, "EDICION_OLIMPICA") +
    countOrphans(raw.disciplina, "id_deporte", sportById, false, "DISCIPLINA") +
    countOrphans(raw.evento, "id_disciplina", disciplineById, false, "EVENTO") +
    ["id_pais_nacimiento", "id_pais_nacionalidad", "id_pais_fallecimiento"].reduce((sum, field) =>
        sum + countOrphans(raw.atleta, field, geoById, true, "ATLETA"), 0) +
    countOrphans(raw.participacion, "id_atleta", athletes, false, "PARTICIPACION") +
    countOrphans(raw.participacion, "id_edicion", editionById, false, "PARTICIPACION") +
    countOrphans(raw.participacion, "id_evento", eventById, false, "PARTICIPACION") +
    countOrphans(raw.participacion, "id_noc", nocById, true, "PARTICIPACION") +
    countOrphans(raw.participacion, "id_pais_nacionalidad", geoById, true, "PARTICIPACION");
check("referencias_fk_huerfanas", 0, foreignKeyOrphans,
    "Relaciones explícitas disponibles en los diez CSV; referencias opcionales vacías se conservan como null.", true);

const countryGroups = new Map();
const medalDomain = new Set(["Gold", "Silver", "Bronze"]);
let directNocNationalityConflicts = 0;
let mappedByNoc = 0;
let unassignedNocRows = 0;
const partRows = raw.participacion;
partRows.forEach(r => {
    const athleteId = olympMongo.int64(r.id_atleta, "participacion.id_atleta");
    const athlete = requireReference(athletes, athleteId, "PARTICIPACION.id_atleta", false);
    const editionId = olympMongo.int32(r.id_edicion, "participacion.id_edicion");
    const edition = requireReference(editionById, editionId, "PARTICIPACION.id_edicion", false);
    const eventId = olympMongo.int64(r.id_evento, "participacion.id_evento");
    const event = requireReference(eventById, eventId, "PARTICIPACION.id_evento", false);
    const nocId = olympMongo.int32(r.id_noc, "participacion.id_noc");
    const noc = nocId === null ? null : requireReference(nocById, nocId, "PARTICIPACION.id_noc", false);
    const nationalityId = olympMongo.int32(r.id_pais_nacionalidad, "participacion.id_pais_nacionalidad");
    if (nationalityId !== null) requireReference(geoById, nationalityId, "PARTICIPACION.id_pais_nacionalidad", false);
    const medal = olympMongo.stringValue(r.medalla);
    if (medal !== null && !medalDomain.has(medal)) throw new Error("Medalla fuera del dominio: " + medal);

    if (nationalityId !== null && noc !== null && noc.id_entidad !== null && nationalityId.toString() !== noc.id_entidad.toString()) {
        directNocNationalityConflicts += 1;
    }

    const participation = {
        id_participacion: olympMongo.int64(r.id_participacion, "participacion.id_participacion"),
        id_atleta: athleteId,
        id_edicion: editionId,
        edicion: editionView(edition),
        id_evento: eventId,
        evento: eventView(event),
        id_noc: nocId,
        noc: nocView(noc),
        id_pais_nacionalidad: nationalityId,
        pais_nacionalidad: entityRef(nationalityId, geoById),
        equipo: olympMongo.stringValue(r.equipo),
        nombre_competencia: olympMongo.stringValue(r.nombre_competencia),
        edad: olympMongo.decimal(r.edad, "participacion.edad"),
        altura_cm_registrada: olympMongo.decimal(r.altura_cm_registrada, "participacion.altura_cm_registrada"),
        peso_kg_registrado: olympMongo.decimal(r.peso_kg_registrado, "participacion.peso_kg_registrado"),
        posicion: olympMongo.int32(r.posicion, "participacion.posicion"),
        empatado: olympMongo.boolean(r.empatado, "participacion.empatado"),
        estado_resultado: olympMongo.stringValue(r.estado_resultado),
        medalla: medal,
        origen_csv: "participacion.csv"
    };
    athlete.participaciones.push(participation);

    let groupType;
    let groupId;
    let entityId = null;
    let method;
    if (noc !== null && noc.id_entidad !== null) {
        entityId = noc.id_entidad;
        groupType = "ENTIDAD_GEOGRAFICA";
        groupId = "ENTIDAD:" + entityId.toString();
        method = "NOC.id_entidad";
        mappedByNoc += 1;
    } else if (noc !== null) {
        groupType = "NOC_SIN_ENTIDAD";
        groupId = "NOC:" + noc.id_noc.toString();
        method = "NOC_SIN_ENTIDAD";
        unassignedNocRows += 1;
    } else {
        groupType = "SIN_NOC_SIN_ENTIDAD";
        groupId = "SIN_NOC";
        method = "SIN_NOC_SIN_ENTIDAD";
        unassignedNocRows += 1;
    }
    const groupKey = groupId + ":EDICION:" + editionId.toString();
    if (!countryGroups.has(groupKey)) {
        countryGroups.set(groupKey, {
            _id: groupKey,
            tipo_agrupacion: groupType,
            id_entidad: entityId,
            entidad: entityRef(entityId, geoById),
            id_noc: groupType === "NOC_SIN_ENTIDAD" ? noc.id_noc : null,
            noc: groupType === "NOC_SIN_ENTIDAD" ? nocView(noc) : null,
            id_edicion: editionId,
            anio: edition.anio,
            temporada: edition.temporada,
            edicion: editionView(edition),
            metodo_asociacion: method,
            participaciones: [],
            origen_csv: "participacion.csv"
        });
    }
    const group = countryGroups.get(groupKey);
    group.participaciones.push({
        id_participacion: participation.id_participacion,
        id_atleta: athlete.id_atleta,
        atleta: {
            nombre: athlete.nombre,
            nombre_completo: athlete.nombre_completo,
            nombre_usado: athlete.nombre_usado,
            sexo: athlete.sexo,
            fecha_nacimiento: athlete.fecha_nacimiento
        },
        id_evento: eventId,
        evento: participation.evento,
        id_noc: nocId,
        noc: participation.noc,
        id_pais_nacionalidad: nationalityId,
        medalla: medal,
        posicion: participation.posicion,
        empatado: participation.empatado,
        estado_resultado: participation.estado_resultado,
        equipo: participation.equipo,
        nombre_competencia: participation.nombre_competencia,
        edad: participation.edad,
        altura_cm_registrada: participation.altura_cm_registrada,
        peso_kg_registrado: participation.peso_kg_registrado
    });
});
raw.participacion.length = 0;

athleteRows.forEach(athlete => athlete.participaciones.sort((a, b) => longSort(a.id_participacion, b.id_participacion)));
countryGroups.forEach(group => group.participaciones.sort((a, b) => longSort(a.id_participacion, b.id_participacion)));

const geoDocuments = geoRows.map(geo => {
    const key = geo.id_entidad.toString();
    const hostedVenues = venueRows.filter(venue => venue.id_pais.toString() === key);
    const hostedEditions = editionRows.filter(edition => edition.id_sede !== null && hostedVenues.some(venue => venue.id_sede.toString() === edition.id_sede.toString()));
    return {
        _id: geo._id,
        id_entidad: geo.id_entidad,
        nombre: geo.nombre,
        codigo_pais: geo.codigo_pais,
        poblacion_anual: populationByEntity.get(key) || [],
        nocs: nocsByEntity.get(key) || [],
        sedes: hostedVenues.map(venue => ({ id_sede: venue.id_sede, nombre: venue.nombre })),
        ediciones_organizadas: hostedEditions.map(edition => ({
            id_edicion: edition.id_edicion,
            anio: edition.anio,
            temporada: edition.temporada,
            id_sede: edition.id_sede
        })).sort((a, b) => Number(a.anio) - Number(b.anio)),
        origen_csv: "entidad_geografica.csv"
    };
});

const catalogDocuments = [];
sportRows.forEach(row => catalogDocuments.push({
    _id: "DEPORTE:" + row.id_deporte.toString(), tipo: "DEPORTE", id: row.id_deporte,
    id_deporte: row.id_deporte, nombre: row.nombre, origen_csv: "deporte.csv"
}));
disciplineRows.forEach(row => {
    const sport = requireReference(sportById, row.id_deporte, "DISCIPLINA.id_deporte", false);
    catalogDocuments.push({
        _id: "DISCIPLINA:" + row.id_disciplina.toString(), tipo: "DISCIPLINA", id: row.id_disciplina,
        id_disciplina: row.id_disciplina, id_deporte: row.id_deporte, nombre: row.nombre,
        deporte: { id_deporte: sport.id_deporte, nombre: sport.nombre }, origen_csv: "disciplina.csv"
    });
});
eventRows.forEach(row => catalogDocuments.push({
    _id: "EVENTO:" + row.id_evento.toString(), tipo: "EVENTO", id: row.id_evento,
    id_evento: row.id_evento, id_disciplina: row.id_disciplina, nombre: row.nombre,
    disciplina: eventView(row), origen_csv: "evento.csv"
}));
editionRows.forEach(row => catalogDocuments.push({
    _id: "EDICION_OLIMPICA:" + row.id_edicion.toString(), tipo: "EDICION_OLIMPICA", id: row.id_edicion,
    id_edicion: row.id_edicion, anio: row.anio, temporada: row.temporada, id_sede: row.id_sede,
    sede: row.id_sede === null ? null : editionView(row).sede, origen_csv: "edicion_olimpica.csv"
}));
venueRows.forEach(row => catalogDocuments.push({
    _id: "SEDE:" + row.id_sede.toString(), tipo: "SEDE", id: row.id_sede,
    id_sede: row.id_sede, nombre: row.nombre, id_pais: row.id_pais,
    pais: entityRef(row.id_pais, geoById), origen_csv: "sede.csv"
}));
nocRows.forEach(row => catalogDocuments.push({
    _id: "NOC:" + row.id_noc.toString(), tipo: "NOC", id: row.id_noc,
    id_noc: row.id_noc, codigo_noc: row.codigo_noc, nombre_noc: row.nombre_noc,
    id_entidad: row.id_entidad, id_entidad_csv: row.id_entidad_csv,
    entidad: entityRef(row.id_entidad, geoById), notas: row.notas, origen_csv: "noc.csv"
}));

check("participaciones_asociadas_a_atleta", expectedCounts.participacion,
    athleteRows.reduce((sum, athlete) => sum + athlete.participaciones.length, 0),
    "Cada fila de participacion.csv se incorpora a su atleta", true);
check("participaciones_en_vista_geografica_y_noc", expectedCounts.participacion,
    Array.from(countryGroups.values()).reduce((sum, group) => sum + group.participaciones.length, 0),
    "Incluye entidades con NOC asociado y buckets explícitos sin entidad", true);
check("documentos_catalogo", 2590, catalogDocuments.length,
    "DEPORTE + DISCIPLINA + EVENTO + EDICION_OLIMPICA + SEDE + NOC", true);
check("temporadas_finales", 5, new Set(editionRows.map(row => row.temporada)).size,
    "Summer, Winter, Intercalated Games, Summer Youth, Winter Youth", true);
check("ediciones_sin_sede_informada", 8, editionRows.filter(row => row.id_sede === null).length,
    "Se conservan con sede null; no se infieren ciudades", true);
check("participaciones_sin_entidad_geografica", 1877, unassignedNocRows,
    "Se conservan agrupadas por NOC, fuera de países", true);
check("nacionalidad_distinta_de_entidad_NOC", 55, directNocNationalityConflicts,
    "Atributos distintos preservados; país de representación toma NOC.id_entidad", true);
check("conversiones_invalidas", 0, olympMongo.conversionErrorCount(),
    "Enteros, fechas, booleanos y Decimal128 deben convertirse sin pérdida; cualquier fallo detiene el proceso.", true);

const collections = {
    atletas: athleteRows,
    entidades_geograficas: geoDocuments,
    participaciones_por_pais: Array.from(countryGroups.values()),
    catalogo_olimpico: catalogDocuments
};
const bsonRows = [];
Object.keys(collections).forEach(name => {
    let max = 0;
    let maxId = "";
    let total = 0;
    collections[name].forEach(doc => {
        const size = bsonsize(doc);
        total += size;
        if (size > max) { max = size; maxId = String(doc._id); }
    });
    bsonRows.push({
        coleccion: name,
        documentos: collections[name].length,
        tamano_bson_maximo_bytes: max,
        documento_maximo_id: maxId,
        limite_bytes: MAX_BSON,
        estado: max < MAX_BSON ? "PASS" : "FAIL"
    });
    if (max >= MAX_BSON) throw new Error("Documento BSON excede el límite en " + name + ": " + max + " bytes");
});

const sourceHashesAfterBuild = csvFiles.map(file => ({
    archivo: file,
    sha256_antes: sourceHashesBefore.find(item => item.archivo === file).sha256_antes,
    sha256_despues: olympMongo.sha256(path.join(processed, file))
}));
sourceHashesAfterBuild.forEach(item => {
    if (item.sha256_antes !== item.sha256_despues) throw new Error("CSV cambió durante el proceso: " + item.archivo);
});

const errorsInPreflight = validations.filter(item => item.estado === "FAIL");
if (errorsInPreflight.length) throw new Error("Preflight detenido: existen validaciones FAIL.");
olympMongo.writeCsv(path.join(reportDir, "preflight_validation.csv"),
    ["validacion", "esperado", "actual", "estado", "detalle"], validations);
olympMongo.writeCsv(path.join(reportDir, apply ? "bson_size_report.csv" : "bson_size_preflight.csv"),
    ["coleccion", "documentos", "tamano_bson_maximo_bytes", "documento_maximo_id", "limite_bytes", "estado"], bsonRows);
olympMongo.writeCsv(path.join(reportDir, "processed_source_manifest.csv"),
    ["archivo", "sha256_antes", "sha256_despues", "estado"],
    sourceHashesAfterBuild.map(item => ({ ...item, estado: item.sha256_antes === item.sha256_despues ? "MATCH" : "MISMATCH" })));

const target = db.getSiblingDB(databaseName);
if (apply) {
    const existing = target.getCollectionNames().filter(name => !name.startsWith("system.")).sort();
    const expectedCollections = collectionNames.slice().sort();
    if (JSON.stringify(existing) !== JSON.stringify(expectedCollections)) {
        throw new Error("La base destino no contiene exactamente las cuatro colecciones creadas. No se modifica nada.");
    }
    const nonEmpty = collectionNames.filter(name => target.getCollection(name).countDocuments({}) !== 0);
    if (nonEmpty.length) throw new Error("Carga abortada: colecciones con datos: " + nonEmpty.join(", ") + ". No se borra ni reemplaza nada.");

    Object.keys(collections).forEach(name => {
        const started = new Date();
        let batch = [];
        let batchBytes = 0;
        let inserted = 0;
        function flush() {
            if (batch.length === 0) return;
            const result = target.getCollection(name).insertMany(batch, { ordered: true });
            inserted += Object.keys(result.insertedIds).length;
            batch = [];
            batchBytes = 0;
        }
        collections[name].forEach(doc => {
            const size = bsonsize(doc);
            if (batch.length > 0 && (batch.length >= BATCH_MAX_DOCS || batchBytes + size > BATCH_MAX_BYTES)) flush();
            batch.push(doc);
            batchBytes += size;
        });
        flush();
        if (inserted !== collections[name].length) throw new Error("Insert incompleto en " + name + ": " + inserted);
        metrics.push({ etapa: "carga_" + name, filas: inserted, inicio: started.toISOString(), fin: new Date().toISOString(), duracion_segundos: (Date.now() - started.getTime()) / 1000, estado: "PASS" });
    });
    collectionNames.forEach(name => {
        const actual = target.getCollection(name).countDocuments({});
        if (actual !== collections[name].length) throw new Error("Conteo final incorrecto en " + name + ": " + actual);
    });
    print("Carga ejecutada; no se modificaron ni eliminaron datos existentes.");
} else {
    print("DRY RUN: no se escribió en MongoDB. Para aplicar, cree las colecciones y ejecute con OLIMPIADAS_MONGO_APPLY=1.");
}

metrics.push({ etapa: apply ? "carga_total" : "preflight_total", filas: expectedFiles.reduce((sum, file) => sum + expectedCounts[file.replace(".csv", "")], 0), inicio: runStart.toISOString(), fin: new Date().toISOString(), duracion_segundos: (Date.now() - runStart.getTime()) / 1000, estado: "PASS" });
olympMongo.writeCsv(path.join(reportDir, apply ? "load_metrics.csv" : "preflight_metrics.csv"),
    ["etapa", "filas", "inicio", "fin", "duracion_segundos", "estado"], metrics);

printjson({
    estado: apply ? "LOAD_PASS" : "PREFLIGHT_PASS",
    base: databaseName,
    csv: expectedCounts,
    total_filas_fuente: Object.values(expectedCounts).reduce((sum, count) => sum + count, 0),
    colecciones: bsonRows.map(row => ({ nombre: row.coleccion, documentos: row.documentos, bson_maximo: row.tamano_bson_maximo_bytes, estado: row.estado })),
    participaciones_por_noc: mappedByNoc,
    participaciones_sin_entidad: unassignedNocRows,
    fecha_utc: new Date().toISOString()
});
