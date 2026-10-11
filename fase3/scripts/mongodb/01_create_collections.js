const path = require("path");
const fs = require("fs");
const commonPath = [
    path.join(process.cwd(), "scripts", "mongodb", "00_common.js"),
    path.join(process.cwd(), "fase3", "scripts", "mongodb", "00_common.js"),
    path.resolve(process.cwd(), "..", "fase3", "scripts", "mongodb", "00_common.js")
].find(candidate => fs.existsSync(candidate));
if (!commonPath) throw new Error("No se encontró fase3/scripts/mongodb/00_common.js.");
load(commonPath);

const databaseName = process.env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3";
const collectionDefinitions = [
    {
        name: "atletas",
        validator: {
            $jsonSchema: {
                bsonType: "object",
                required: ["id_atleta", "nombre", "participaciones", "origen_csv"],
                properties: {
                    id_atleta: { bsonType: "long" },
                    nombre: { bsonType: "string" },
                    participaciones: { bsonType: "array" },
                    origen_csv: { enum: ["atleta.csv"] }
                }
            }
        }
    },
    {
        name: "entidades_geograficas",
        validator: {
            $jsonSchema: {
                bsonType: "object",
                required: ["id_entidad", "nombre", "poblacion_anual", "origen_csv"],
                properties: {
                    id_entidad: { bsonType: "int" },
                    nombre: { bsonType: "string" },
                    poblacion_anual: { bsonType: "array" },
                    origen_csv: { enum: ["entidad_geografica.csv"] }
                }
            }
        }
    },
    {
        name: "participaciones_por_pais",
        validator: {
            $jsonSchema: {
                bsonType: "object",
                required: ["tipo_agrupacion", "id_edicion", "anio", "temporada", "participaciones"],
                properties: {
                    tipo_agrupacion: { enum: ["ENTIDAD_GEOGRAFICA", "NOC_SIN_ENTIDAD", "SIN_NOC_SIN_ENTIDAD"] },
                    id_edicion: { bsonType: "int" },
                    anio: { bsonType: "int" },
                    temporada: { bsonType: "string" },
                    participaciones: { bsonType: "array" }
                }
            }
        }
    },
    {
        name: "catalogo_olimpico",
        validator: {
            $jsonSchema: {
                bsonType: "object",
                required: ["tipo", "id", "origen_csv"],
                properties: {
                    tipo: { enum: ["DEPORTE", "DISCIPLINA", "EVENTO", "EDICION_OLIMPICA", "SEDE", "NOC"] },
                    origen_csv: { bsonType: "string" }
                }
            }
        }
    }
];

const target = db.getSiblingDB(databaseName);
const existing = target.getCollectionNames().filter(name => !name.startsWith("system."));
if (existing.length > 0) {
    throw new Error(
        "No se crean colecciones: " + databaseName + " ya contiene " + existing.join(", ") +
        ". No se borra ni reemplaza ninguna colección."
    );
}

collectionDefinitions.forEach(definition => {
    target.createCollection(definition.name, {
        validator: definition.validator,
        validationLevel: "strict",
        validationAction: "error"
    });
});

printjson({
    estado: "PASS",
    base: databaseName,
    colecciones_creadas: collectionDefinitions.map(item => item.name),
    hora_utc: new Date().toISOString()
});
