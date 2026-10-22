// Inciso d: consulta de un país por nombre o código.
// Parámetros por variables de entorno (los envoltorios consulta_pais.ps1/.sh las asignan):
//   OLIMPIADAS_PAIS       nombre del país o código NOC/ISO (obligatorio)
//   OLIMPIADAS_ANIO       año de la edición (opcional)
//   OLIMPIADAS_TEMPORADA  verano | invierno | Summer | Winter | ... (opcional)
//   OLIMPIADAS_DEPORTE    deporte o disciplina (parcial) (opcional)
//   OLIMPIADAS_MEDALLA    oro | plata | bronce | cualquiera (opcional)
//   OLIMPIADAS_LIMITE     límite de filas de detalle a mostrar (predeterminado 100, 0 o "todos" para ilimitado)
//   OLIMPIADAS_FORMATO    texto (predeterminado) | json
//   OLIMPIADAS_MONGO_DB   base de datos (predeterminado OlimpiadasF3)

const inicio = Date.now();
const fechaEjecucion = new Date();
const env = process.env;
const database = db.getSiblingDB(env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3");
const entidades = database.entidades_geograficas;
const bucketsPais = database.participaciones_por_pais;
const catalogos = database.catalogo_olimpico;

const MAX_CANDIDATOS = 20;
const MAX_LONGITUD = 150;
const LIMITE_DETALLE_DEFAULT = 100;

const MEDALLAS = { Gold: "Oro", Silver: "Plata", Bronze: "Bronce" };
const ORDEN_MEDALLA = { Gold: 1, Silver: 2, Bronze: 3 };
const ESTADOS = { DNF: "No terminó", DNS: "No se presentó", DQ: "Descalificado" };
const TEMPORADAS = {
    "Summer": "Verano",
    "Winter": "Invierno",
    "Summer Youth": "Juventud de verano",
    "Winter Youth": "Juventud de invierno",
    "Intercalated Games": "Juegos Intercalados"
};

function fallar(mensaje) {
    print("  Parámetro inválido: " + mensaje);
    quit(1);
}

function texto(valor) {
    return valor === undefined || valor === null ? "" : String(valor).trim();
}

function numero(valor) {
    return valor === undefined || valor === null ? null : Number(valor.toString());
}

function sinAcentos(valor) {
    return valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

const ACENTOS = {
    a: "áàâäãåăąā", e: "éèêëěęēė", i: "íìîïīįı", o: "óòôöõøőō", u: "úùûüůűūų", y: "ýÿ",
    n: "ñńň", c: "çćč", s: "šśşș", z: "žźż", r: "ř", g: "ğ", l: "łľ", t: "ţťț", d: "ďđ"
};
const VARIANTES = {};
Object.keys(ACENTOS).forEach(base => {
    VARIANTES[base] = Array.from(new Set(Array.from(base + ACENTOS[base] + (base + ACENTOS[base]).toUpperCase()))).join("");
});

function patron(valor) {
    const separador = "[\\s•\\-]+";
    return valor.trim().split(/[\s•\-]+/).map(palabra =>
        Array.from(palabra).map(letra => {
            const base = sinAcentos(letra).toLowerCase();
            if (VARIANTES[base]) {
                const clase = "[" + VARIANTES[base] + "]";
                return base !== letra.toLowerCase() ? "(?:" + clase + ")?" : clase;
            }
            return letra.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }).join("")
    ).join(separador);
}

function regex(valor, completo) {
    const cuerpo = patron(valor);
    return new RegExp(completo ? "^" + cuerpo + "$" : cuerpo, "i");
}

function leerMedalla(valor) {
    const clave = sinAcentos(valor).toLowerCase();
    const mapa = {
        oro: "Gold", gold: "Gold", plata: "Silver", silver: "Silver",
        bronce: "Bronze", bronze: "Bronze", cualquiera: "*", todas: "*", si: "*"
    };
    if (!mapa[clave]) fallar("Medalla no reconocida: " + valor + " (use oro, plata, bronce o cualquiera).");
    return mapa[clave];
}

function leerTemporada(valor) {
    const clave = sinAcentos(valor).toLowerCase();
    if (clave === "verano") return "Summer";
    if (clave === "invierno") return "Winter";
    const encontrada = Object.keys(TEMPORADAS).find(t =>
        t.toLowerCase() === clave || sinAcentos(TEMPORADAS[t]).toLowerCase() === clave
    );
    if (!encontrada) fallar("Temporada no reconocida: " + valor + " (use verano o invierno).");
    return encontrada;
}

// ---------------------------------------------------------------- Parámetros de entrada
const parametros = {
    pais: texto(env.OLIMPIADAS_PAIS),
    anio: texto(env.OLIMPIADAS_ANIO),
    temporada: texto(env.OLIMPIADAS_TEMPORADA),
    deporte: texto(env.OLIMPIADAS_DEPORTE),
    medalla: texto(env.OLIMPIADAS_MEDALLA),
    limite: texto(env.OLIMPIADAS_LIMITE),
    formato: texto(env.OLIMPIADAS_FORMATO).toLowerCase() || "texto"
};

if (!parametros.pais) {
    fallar("Indique el país o código NOC/ISO como parámetro obligatorio.");
}
["pais", "deporte", "temporada", "medalla"].forEach(nombre => {
    if (parametros[nombre].length > MAX_LONGITUD) {
        fallar("El parámetro " + nombre + " supera " + MAX_LONGITUD + " caracteres.");
    }
});

if (parametros.pais.replace(/[\s•\-]/g, "").length < 2) {
    fallar("Escriba al menos dos caracteres para identificar el país.");
}
if (parametros.anio && !/^\d{4}$/.test(parametros.anio)) {
    fallar("El año debe tener cuatro dígitos.");
}
if (!["texto", "json"].includes(parametros.formato)) {
    fallar("Formato no reconocido: " + parametros.formato + " (use texto o json).");
}

let limiteDetalle = LIMITE_DETALLE_DEFAULT;
if (parametros.limite) {
    const lLower = parametros.limite.toLowerCase();
    if (lLower === "todos" || lLower === "todas" || lLower === "all" || lLower === "0") {
        limiteDetalle = 0; // Sin límite
    } else if (/^\d+$/.test(parametros.limite)) {
        limiteDetalle = parseInt(parametros.limite, 10);
    } else {
        fallar("Límite no reconocido: " + parametros.limite + " (use un número o 'todos').");
    }
}

// ---------------------------------------------------------------- Búsqueda de la Entidad Geográfica
// Estrategia indexada:
// 1. Coincidencia exacta por código NOC (ej. "GUA", "ARG", "FRA") en `nocs.codigo_noc`
// 2. Coincidencia exacta por código ISO3 / `codigo_pais` (ej. "GTM", "ARG", "FRA")
// 3. Coincidencia exacta por nombre en `entidades_geograficas`
// 4. Coincidencia sin acentos ni mayúsculas en `nombre`
// 5. Coincidencia parcial con lista de candidatos
const busquedaTexto = parametros.pais.trim();
const esCodigo3 = /^[a-zA-Z]{3}$/.test(busquedaTexto);
let entidadEncontrada = null;
let candidatos = [];
let metodoBusqueda = "";

if (esCodigo3) {
    const codigoUpper = busquedaTexto.toUpperCase();
    // 1. Por código NOC
    entidadEncontrada = entidades.findOne({ "nocs.codigo_noc": codigoUpper });
    if (entidadEncontrada) {
        metodoBusqueda = "código NOC [" + codigoUpper + "]";
    } else {
        // 2. Por código de país ISO3
        entidadEncontrada = entidades.findOne({ codigo_pais: codigoUpper });
        if (entidadEncontrada) {
            metodoBusqueda = "código ISO3 [" + codigoUpper + "]";
        }
    }
}

if (!entidadEncontrada) {
    // 3. Por nombre exacto
    entidadEncontrada = entidades.findOne({ nombre: busquedaTexto });
    if (entidadEncontrada) {
        metodoBusqueda = "nombre exacto";
    }
}

if (!entidadEncontrada) {
    // 4. Búsqueda sin acentos / mayúsculas
    const reCompleto = regex(busquedaTexto, true);
    entidadEncontrada = entidades.findOne({ nombre: reCompleto });
    if (entidadEncontrada) {
        metodoBusqueda = "nombre insensible a acentos/mayúsculas";
    }
}

if (!entidadEncontrada) {
    // 5. Búsqueda parcial
    const reParcial = regex(busquedaTexto, false);
    candidatos = entidades.find({ nombre: reParcial }).limit(MAX_CANDIDATOS + 1).toArray();
    if (candidatos.length === 1) {
        entidadEncontrada = candidatos[0];
        candidatos = [];
        metodoBusqueda = "coincidencia parcial única";
    } else if (candidatos.length > 1) {
        metodoBusqueda = "múltiples candidatos";
    }
}

// Si no se encontró entidad geográfica, verificar si coincide con un NOC_SIN_ENTIDAD en participaciones_por_pais
let nocSinEntidad = null;
if (!entidadEncontrada && candidatos.length === 0 && esCodigo3) {
    const codigoUpper = busquedaTexto.toUpperCase();
    const bucketNoc = bucketsPais.findOne({
        tipo_agrupacion: "NOC_SIN_ENTIDAD",
        "noc.codigo_noc": codigoUpper
    });
    if (bucketNoc) {
        nocSinEntidad = codigoUpper;
        metodoBusqueda = "NOC sin entidad territorial [" + codigoUpper + "]";
    }
}

// ---------------------------------------------------------------- Manejo de No Encontrado o Ambigüedad
if (!entidadEncontrada && !nocSinEntidad) {
    if (candidatos.length > 1) {
        if (parametros.formato === "json") {
            printjson({
                estado: "AMBIGUO",
                mensaje: "Se encontraron múltiples entidades para el término ingresado.",
                total_candidatos: candidatos.length,
                candidatos: candidatos.slice(0, MAX_CANDIDATOS).map(c => ({
                    id_entidad: c.id_entidad,
                    nombre: c.nombre,
                    codigo_pais: c.codigo_pais,
                    nocs: (c.nocs || []).map(n => n.codigo_noc)
                }))
            });
        } else {
            print("\n" + "=".repeat(78));
            print("  SE ENCONTRARON MÚLTIPLES ENTIDADES PARA: " + parametros.pais);
            print("=".repeat(78));
            print("  Especifique el código NOC/ISO exacto o el nombre completo:");
            print("");
            candidatos.slice(0, MAX_CANDIDATOS).forEach(c => {
                const codNocs = (c.nocs && c.nocs.length > 0) ? c.nocs.map(n => n.codigo_noc).join(", ") : "Sin NOC";
                const iso = c.codigo_pais || "Sin ISO";
                print("  • " + c.nombre.padEnd(36) + " | NOC: " + codNocs.padEnd(12) + " | ISO: " + iso);
            });
            if (candidatos.length > MAX_CANDIDATOS) {
                print("  ... (más resultados no mostrados)");
            }
            print("\n------------------------------------------------------------------------------");
        }
        quit(0);
    } else {
        if (parametros.formato === "json") {
            printjson({
                estado: "NO_ENCONTRADO",
                mensaje: "No se encontró ningún país, entidad geográfica ni código NOC con ese valor: " + parametros.pais
            });
        } else {
            print("\n  No se encontró ningún país, entidad geográfica ni código NOC para: " + parametros.pais);
            print("  Verifique la ortografía o intente con el código NOC (ej. GUA, FRA, USA, ARG).");
        }
        quit(0);
    }
}

// ---------------------------------------------------------------- Resolver Sedes de la Entidad
// Mapa de sedes para enriquecer las ediciones organizadas
const sedesMap = new Map();
if (entidadEncontrada && Array.isArray(entidadEncontrada.sedes)) {
    entidadEncontrada.sedes.forEach(s => {
        sedesMap.set(s.id_sede, s.nombre);
    });
}

// Si la entidad tiene ediciones_organizadas pero no tiene el nombre en su array de sedes,
// podemos complementar buscando el nombre de la sede en catalogo_olimpico (tipo: "SEDE")
const edicionesOrganizadasList = [];
if (entidadEncontrada && Array.isArray(entidadEncontrada.ediciones_organizadas)) {
    entidadEncontrada.ediciones_organizadas.forEach(eo => {
        let nombreSede = sedesMap.get(eo.id_sede);
        if (!nombreSede && eo.id_sede) {
            const catSede = catalogos.findOne({ tipo: "SEDE", id: eo.id_sede });
            if (catSede) nombreSede = catSede.nombre;
        }
        edicionesOrganizadasList.push({
            id_edicion: eo.id_edicion,
            anio: eo.anio,
            temporada: eo.temporada,
            temporada_es: TEMPORADAS[eo.temporada] || eo.temporada,
            id_sede: eo.id_sede,
            sede: nombreSede || "Sede no informada"
        });
    });
    // Ordenar cronológicamente
    edicionesOrganizadasList.sort((a, b) => a.anio - b.anio || a.temporada.localeCompare(b.temporada));
}

// ---------------------------------------------------------------- Búsqueda de Buckets de Participación
// Filtros aplicables a nivel de documento de bucket y a nivel de participaciones individuales
const filtrosBuckets = {};
if (entidadEncontrada) {
    filtrosBuckets.tipo_agrupacion = "ENTIDAD_GEOGRAFICA";
    filtrosBuckets.id_entidad = entidadEncontrada.id_entidad;
} else if (nocSinEntidad) {
    filtrosBuckets.tipo_agrupacion = "NOC_SIN_ENTIDAD";
    filtrosBuckets["noc.codigo_noc"] = nocSinEntidad;
}

if (parametros.anio) {
    filtrosBuckets.anio = Number(parametros.anio);
}
if (parametros.temporada) {
    filtrosBuckets.temporada = leerTemporada(parametros.temporada);
}
if (parametros.medalla) {
    const med = leerMedalla(parametros.medalla);
    filtrosBuckets["participaciones.medalla"] = med === "*"
        ? { $in: ["Gold", "Silver", "Bronze"] }
        : med;
}

// Predicados para filtrar las filas de participaciones dentro de cada bucket
const predicadosPart = [];
if (parametros.anio) {
    const anioNum = Number(parametros.anio);
    predicadosPart.push((p, b) => b.anio === anioNum);
}
if (parametros.temporada) {
    const tempVal = leerTemporada(parametros.temporada);
    predicadosPart.push((p, b) => b.temporada === tempVal);
}
if (parametros.deporte) {
    const reDep = regex(parametros.deporte, false);
    predicadosPart.push(p => {
        const ev = p.evento;
        const disc = ev && ev.disciplina;
        const dep = disc && disc.deporte;
        return (disc && reDep.test(texto(disc.nombre))) || (dep && reDep.test(texto(dep.nombre)));
    });
}
if (parametros.medalla) {
    const medVal = leerMedalla(parametros.medalla);
    predicadosPart.push(p => {
        if (medVal === "*") return p.medalla === "Gold" || p.medalla === "Silver" || p.medalla === "Bronze";
        return p.medalla === medVal;
    });
}

// Ejecutar consulta indexada sobre participaciones_por_pais
const buckets = bucketsPais.find(filtrosBuckets)
    .sort({ anio: 1, temporada: 1 })
    .toArray();

// ---------------------------------------------------------------- Procesamiento y Métricas
// 1. Atletas únicos
const idsAtletasUnicos = new Set();
// 2. Ediciones disputadas
const edicionesDisputadas = new Map(); // key: anio_temporada -> info
// 3. Deportes disputados
const deportesSet = new Set();
// 4. Medallero Oficial del País (por prueba/evento)
//    Regla de oro: En eventos colectivos/por equipo, si el país gana podio suma 1 medalla oficial por prueba
const medallasOficialesPais = { Gold: 0, Silver: 0, Bronze: 0, Total: 0 };
const eventosMedallasPaisVistos = new Set();
// 5. Medallas Físicas de Atletas (todos los atletas que recibieron medalla en podio)
const medallasAtletas = { Gold: 0, Silver: 0, Bronze: 0, Total: 0 };

let totalParticipacionesFiltradas = 0;
const participacionesPorEdicion = [];

buckets.forEach(bucket => {
    const edicionKey = bucket.anio + " " + bucket.temporada;
    const ciudadSede = (bucket.edicion && bucket.edicion.sede && bucket.edicion.sede.ciudad)
        || (bucket.edicion && bucket.edicion.sede && bucket.edicion.sede.nombre)
        || "Sede no informada";

    const partsFiltradasEnBucket = [];

    (bucket.participaciones || []).forEach(p => {
        // Evaluar si cumple con los filtros específicos
        if (predicadosPart.every(fn => fn(p, bucket))) {
            partsFiltradasEnBucket.push(p);
            totalParticipacionesFiltradas++;

            if (p.id_atleta !== null && p.id_atleta !== undefined) {
                idsAtletasUnicos.add(String(p.id_atleta));
            }

            // Deporte
            const depNombre = p.evento && p.evento.disciplina && p.evento.disciplina.deporte && p.evento.disciplina.deporte.nombre;
            if (depNombre) deportesSet.add(depNombre);

            // Medallas
            if (p.medalla && MEDALLAS[p.medalla]) {
                // Medalla física de atleta
                medallasAtletas[p.medalla]++;
                medallasAtletas.Total++;

                // Medalla oficial de país por evento
                const claveEventoMedalla = String(bucket.id_edicion) + ":" + String(p.id_evento || ("PART_" + p.id_participacion)) + ":" + p.medalla;
                if (!eventosMedallasPaisVistos.has(claveEventoMedalla)) {
                    eventosMedallasPaisVistos.add(claveEventoMedalla);
                    medallasOficialesPais[p.medalla]++;
                    medallasOficialesPais.Total++;
                }
            }
        }
    });

    if (partsFiltradasEnBucket.length > 0) {
        if (!edicionesDisputadas.has(edicionKey)) {
            edicionesDisputadas.set(edicionKey, {
                id_edicion: bucket.id_edicion,
                anio: bucket.anio,
                temporada: bucket.temporada,
                temporada_es: TEMPORADAS[bucket.temporada] || bucket.temporada,
                sede: ciudadSede,
                total_participaciones: 0,
                atletas_en_edicion: new Set(),
                medallas: { Gold: 0, Silver: 0, Bronze: 0, Total: 0 }
            });
        }
        const edInfo = edicionesDisputadas.get(edicionKey);
        edInfo.total_participaciones += partsFiltradasEnBucket.length;
        partsFiltradasEnBucket.forEach(p => {
            if (p.id_atleta) edInfo.atletas_en_edicion.add(String(p.id_atleta));
            if (p.medalla && MEDALLAS[p.medalla]) {
                edInfo.medallas[p.medalla]++;
                edInfo.medallas.Total++;
            }
        });

        // Ordenar participaciones determinísticamente por evento e id_participacion
        partsFiltradasEnBucket.sort((a, b) => {
            const nomA = (a.evento && a.evento.nombre) || "";
            const nomB = (b.evento && b.evento.nombre) || "";
            return nomA.localeCompare(nomB) || (Number(a.id_participacion) - Number(b.id_participacion));
        });

        participacionesPorEdicion.push({
            id_edicion: bucket.id_edicion,
            anio: bucket.anio,
            temporada: bucket.temporada,
            temporada_es: TEMPORADAS[bucket.temporada] || bucket.temporada,
            sede: ciudadSede,
            participaciones: partsFiltradasEnBucket
        });
    }
});

// Ordenar ediciones cronológicamente
participacionesPorEdicion.sort((a, b) => a.anio - b.anio || a.temporada.localeCompare(b.temporada));

// Datos de Población de la Entidad
let resumenPoblacion = "No registrada en las fuentes";
let seriePoblacion = [];
if (entidadEncontrada && Array.isArray(entidadEncontrada.poblacion_anual) && entidadEncontrada.poblacion_anual.length > 0) {
    seriePoblacion = entidadEncontrada.poblacion_anual.slice().sort((a, b) => a.anio - b.anio);
    const ultima = seriePoblacion[seriePoblacion.length - 1];
    const primera = seriePoblacion[0];
    const poblacionFormateada = Number(ultima.poblacion).toLocaleString("es-GT");
    resumenPoblacion = poblacionFormateada + " hab. (año " + ultima.anio + ") · Serie histórica: " +
        primera.anio + "–" + ultima.anio + " (" + seriePoblacion.length + " años registrados)";
}

// NOCs vinculados a la entidad
const nocsTexto = (entidadEncontrada && Array.isArray(entidadEncontrada.nocs) && entidadEncontrada.nocs.length > 0)
    ? entidadEncontrada.nocs.map(n => n.codigo_noc + (n.nombre_noc ? " (" + n.nombre_noc + ")" : "")).join(", ")
    : (nocSinEntidad ? nocSinEntidad + " (sin entidad geográfica)" : "Ninguno registrado");

const esAgregadoEstadistico = entidadEncontrada && (!entidadEncontrada.nocs || entidadEncontrada.nocs.length === 0);

// Resumen de filtros aplicados
const filtrosAplicados = [];
if (parametros.anio) filtrosAplicados.push("Año=" + parametros.anio);
if (parametros.temporada) filtrosAplicados.push("Temporada=" + parametros.temporada);
if (parametros.deporte) filtrosAplicados.push("Deporte=" + parametros.deporte);
if (parametros.medalla) filtrosAplicados.push("Medalla=" + parametros.medalla);
if (limiteDetalle > 0) filtrosAplicados.push("Límite=" + limiteDetalle);

const duracionMs = Date.now() - inicio;

// ---------------------------------------------------------------- SALIDA JSON
if (parametros.formato === "json") {
    printjson({
        estado: "PASS",
        entidad: entidadEncontrada ? {
            id_entidad: entidadEncontrada.id_entidad,
            nombre: entidadEncontrada.nombre,
            codigo_pais: entidadEncontrada.codigo_pais,
            nocs: entidadEncontrada.nocs || [],
            es_agregado_estadistico: esAgregadoEstadistico
        } : {
            id_entidad: null,
            nombre: "NOC " + nocSinEntidad,
            codigo_pais: null,
            nocs: [{ codigo_noc: nocSinEntidad }],
            es_agregado_estadistico: false
        },
        poblacion: {
            resumen: resumenPoblacion,
            total_registros_serie: seriePoblacion.length,
            ultima_disponible: seriePoblacion.length > 0 ? seriePoblacion[seriePoblacion.length - 1] : null
        },
        sedes_y_ediciones_organizadas: edicionesOrganizadasList,
        resumen_olimpico: {
            total_participaciones: totalParticipacionesFiltradas,
            atletas_unicos: idsAtletasUnicos.size,
            ediciones_con_participacion: edicionesDisputadas.size,
            deportes_disputados: Array.from(deportesSet).sort(),
            medallero_oficial_pais: {
                oro: medallasOficialesPais.Gold,
                plata: medallasOficialesPais.Silver,
                bronce: medallasOficialesPais.Bronze,
                total: medallasOficialesPais.Total
            },
            medallas_fisicas_atletas: {
                oro: medallasAtletas.Gold,
                plata: medallasAtletas.Silver,
                bronce: medallasAtletas.Bronze,
                total: medallasAtletas.Total
            }
        },
        ediciones: participacionesPorEdicion.map(e => ({
            anio: e.anio,
            temporada: e.temporada,
            sede: e.sede,
            participaciones: e.participaciones.map(p => ({
                id_participacion: p.id_participacion,
                atleta: {
                    id_atleta: p.id_atleta,
                    nombre: p.atleta ? (p.atleta.nombre_completo || p.atleta.nombre) : "No informado",
                    sexo: p.atleta ? p.atleta.sexo : null
                },
                evento: p.evento ? p.evento.nombre : "No informado",
                disciplina: p.evento && p.evento.disciplina ? p.evento.disciplina.nombre : null,
                deporte: p.evento && p.evento.disciplina && p.evento.disciplina.deporte ? p.evento.disciplina.deporte.nombre : null,
                posicion: p.posicion,
                empatado: p.empatado,
                estado_resultado: p.estado_resultado,
                medalla: p.medalla
            }))
        })),
        metadatos: {
            tiempo_ms: duracionMs,
            metodo_busqueda: metodoBusqueda,
            filtros_aplicados: filtrosAplicados,
            base: database.getName(),
            fecha_utc: fechaEjecucion.toISOString()
        }
    });
    quit(0);
}

// ---------------------------------------------------------------- SALIDA TEXTO
const nombreCabecera = entidadEncontrada ? entidadEncontrada.nombre : ("NOC " + nocSinEntidad);
const codigoCabecera = entidadEncontrada ? (entidadEncontrada.codigo_pais || "Sin ISO") : nocSinEntidad;

print("\n" + "=".repeat(78));
print("  CONSULTA HISTÓRICA POR PAÍS · " + nombreCabecera.toUpperCase() + " (" + codigoCabecera + ")");
print("=".repeat(78));

print("\n  DATOS GENERALES Y GEOGRÁFICOS");
print("  Nombre oficial:       " + (entidadEncontrada ? entidadEncontrada.nombre : ("NOC independiente " + nocSinEntidad)));
print("  Código de país (ISO): " + (entidadEncontrada && entidadEncontrada.codigo_pais ? entidadEncontrada.codigo_pais : "No registrado / no aplica"));
print("  NOCs asociados:       " + nocsTexto);
print("  Población:            " + resumenPoblacion);
if (esAgregadoEstadistico) {
    print("  ⚠️ AVISO: Esta entidad es un agregado estadístico/regional. No posee comités olímpicos ni delegaciones.");
}

print("\n  HISTORIAL COMO SEDE / ANFITRIÓN OLÍMPICO");
if (edicionesOrganizadasList.length > 0) {
    print("  Ha sido sede de " + edicionesOrganizadasList.length + " edición(es) olímpica(s):");
    edicionesOrganizadasList.forEach(eo => {
        print("  • " + String(eo.anio).padEnd(6) + "· " + eo.temporada_es.padEnd(12) + "· Sede: " + eo.sede);
    });
} else {
    print("  Sedes y ediciones organizadas: Ninguna (el país no ha sido sede en las ediciones registradas).");
}

print("\n  RESUMEN HISTÓRICO OLÍMPICO");
if (filtrosAplicados.length > 0) {
    print("  Filtros aplicados:    " + filtrosAplicados.join(" · "));
}
print("  Participaciones:      " + totalParticipacionesFiltradas.toLocaleString("es-GT") +
    (totalParticipacionesFiltradas === 0 ? " (sin registros con los filtros indicados)" : ""));
print("  Atletas únicos:       " + idsAtletasUnicos.size.toLocaleString("es-GT"));
print("  Ediciones disputadas: " + edicionesDisputadas.size +
    (edicionesDisputadas.size > 0 ? " · Años: " + Array.from(edicionesDisputadas.values()).map(e => e.anio).filter((v, i, a) => a.indexOf(v) === i).join(", ") : ""));
print("  Deportes con registro:" + (deportesSet.size > 0 ? " " + deportesSet.size + " (" + Array.from(deportesSet).slice(0, 8).join(", ") + (deportesSet.size > 8 ? "..." : "") + ")" : " Ninguno"));

print("\n  MEDALLERO OLÍMPICO");
print("  • Medallero oficial del país (por prueba):");
print("      Total: " + String(medallasOficialesPais.Total).padEnd(4) +
    "| Oro: " + String(medallasOficialesPais.Gold).padEnd(4) +
    "| Plata: " + String(medallasOficialesPais.Silver).padEnd(4) +
    "| Bronce: " + String(medallasOficialesPais.Bronze));
print("  • Medallas físicas acumuladas por atletas:");
print("      Total: " + String(medallasAtletas.Total).padEnd(4) +
    "| Oro: " + String(medallasAtletas.Gold).padEnd(4) +
    "| Plata: " + String(medallasAtletas.Silver).padEnd(4) +
    "| Bronce: " + String(medallasAtletas.Bronze));
if (medallasAtletas.Total !== medallasOficialesPais.Total) {
    print("    Nota: La diferencia corresponde a eventos colectivos/por equipo (donde cada atleta recibe medalla física");
    print("          pero cuenta como 1 única medalla oficial para el medallero del país).");
}

print("\n  PARTICIPACIONES Y RESULTADOS POR EDICIÓN");
if (participacionesPorEdicion.length === 0) {
    print("  (No se encontraron participaciones con los criterios especificados)");
} else {
    let filasImpresas = 0;
    let limiteAlcanzado = false;

    for (let i = 0; i < participacionesPorEdicion.length; i++) {
        if (limiteDetalle > 0 && filasImpresas >= limiteDetalle) {
            limiteAlcanzado = true;
            break;
        }

        const ed = participacionesPorEdicion[i];
        print("\n  ■ " + ed.anio + " · " + ed.temporada_es + " · " + ed.sede +
            "   (Participaciones: " + ed.participaciones.length + ")");

        for (let j = 0; j < ed.participaciones.length; j++) {
            if (limiteDetalle > 0 && filasImpresas >= limiteDetalle) {
                limiteAlcanzado = true;
                break;
            }

            const p = ed.participaciones[j];
            filasImpresas++;

            // Etiqueta de medalla
            let tagMedalla = "        ";
            if (p.medalla === "Gold") tagMedalla = "  [ORO]  ";
            else if (p.medalla === "Silver") tagMedalla = " [PLATA] ";
            else if (p.medalla === "Bronze") tagMedalla = "[BRONCE] ";

            // Nombre del evento
            const evNombre = p.evento ? p.evento.nombre : "Evento no especificado";
            print(tagMedalla + evNombre);

            // Deporte y disciplina
            const depNombre = (p.evento && p.evento.disciplina && p.evento.disciplina.deporte && p.evento.disciplina.deporte.nombre) || "";
            const discNombre = (p.evento && p.evento.disciplina && p.evento.disciplina.nombre) || "";
            const depLinea = (depNombre && discNombre && depNombre !== discNombre)
                ? (depNombre + " · " + discNombre)
                : (depNombre || discNombre || "Deporte no especificado");

            // Atleta
            const atlNombre = p.atleta ? (p.atleta.nombre_completo || p.atleta.nombre) : "Atleta no especificado";
            const idAtlStr = p.id_atleta ? (" (id " + p.id_atleta + ")") : "";

            // Resultado / Posición
            let resStr = "";
            if (p.estado_resultado && ESTADOS[p.estado_resultado]) {
                resStr = ESTADOS[p.estado_resultado] + " (" + p.estado_resultado + ")";
            } else if (p.posicion !== null && p.posicion !== undefined) {
                resStr = "Posición " + p.posicion + (p.empatado ? " (empate)" : "");
            } else {
                resStr = "Sin posición registrada";
            }

            print("           " + depLinea + " · " + atlNombre + idAtlStr + " · " + resStr);
        }
    }

    if (limiteAlcanzado) {
        print("\n  ... Se alcanzó el límite de visualización de " + limiteDetalle + " filas (de " + totalParticipacionesFiltradas + " totales).");
        print("      Para ver todo use -Limite todos, o aplique filtros (-Anio, -Deporte, -Medalla).");
    }
}

print("\n" + "-".repeat(78));
print("  Consulta resuelta en " + duracionMs + " ms · búsqueda por " + metodoBusqueda + " · base " + database.getName());
print("  Ejecutada el " + fechaEjecucion.toISOString().replace("T", " ").replace(/\..+/, "") + " UTC");
print("");
