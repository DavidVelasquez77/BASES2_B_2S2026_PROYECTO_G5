// Inciso c: consulta de un atleta por nombre.
// Parámetros por variables de entorno (los envoltorios consulta_atleta.ps1/.sh las asignan):
//   OLIMPIADAS_ATLETA     nombre del atleta (obligatorio, salvo que se use OLIMPIADAS_ATLETA_ID)
//   OLIMPIADAS_ATLETA_ID  id_atleta exacto, para elegir entre homónimos
//   OLIMPIADAS_DEPORTE    deporte o disciplina (parcial)
//   OLIMPIADAS_PAIS       código NOC/país exacto (JAM) o nombre parcial (Jamaica)
//   OLIMPIADAS_ANIO       año de la edición
//   OLIMPIADAS_TEMPORADA  verano | invierno | Summer | Winter | Summer Youth | ...
//   OLIMPIADAS_MEDALLA    oro | plata | bronce | cualquiera
//   OLIMPIADAS_FORMATO    texto (predeterminado) | json
//   OLIMPIADAS_MONGO_DB   base de datos (predeterminado OlimpiadasF3)

const inicio = Date.now();
const fechaEjecucion = new Date();
const env = process.env;
const database = db.getSiblingDB(env.OLIMPIADAS_MONGO_DB || "OlimpiadasF3");
const atletas = database.atletas;

const MAX_CANDIDATOS = 25;
const MAX_FILAS_PARCIAL = 1000;
const MAX_LONGITUD = 150;

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
const SEXOS = { Male: "Masculino", Female: "Femenino" };

// Parámetro inválido: mensaje legible y código de salida 1, sin traza técnica.
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

// Patrón insensible a mayúsculas y acentos. Una letra que el usuario escribió con acento
// se vuelve opcional, porque algunas fuentes perdieron esos caracteres ("Jos Gonzlez").
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

// ---------------------------------------------------------------- parámetros
const parametros = {
    atleta: texto(env.OLIMPIADAS_ATLETA),
    id: texto(env.OLIMPIADAS_ATLETA_ID),
    deporte: texto(env.OLIMPIADAS_DEPORTE),
    pais: texto(env.OLIMPIADAS_PAIS),
    anio: texto(env.OLIMPIADAS_ANIO),
    temporada: texto(env.OLIMPIADAS_TEMPORADA),
    medalla: texto(env.OLIMPIADAS_MEDALLA),
    formato: texto(env.OLIMPIADAS_FORMATO).toLowerCase() || "texto"
};
if (!parametros.atleta && !parametros.id) {
    fallar("Indique el nombre del atleta como primer parámetro.");
}
["atleta", "deporte", "pais", "temporada", "medalla"].forEach(nombre => {
    if (parametros[nombre].length > MAX_LONGITUD) fallar("El parámetro " + nombre + " supera " + MAX_LONGITUD + " caracteres.");
});
if (!parametros.id && parametros.atleta.replace(/[\s•\-]/g, "").length < 2) {
    fallar("Escriba al menos dos letras del nombre del atleta.");
}
if (parametros.id && !/^\d+$/.test(parametros.id)) fallar("El id del atleta debe ser numérico.");
if (parametros.anio && !/^\d{4}$/.test(parametros.anio)) fallar("El año debe tener cuatro dígitos.");
if (!["texto", "json"].includes(parametros.formato)) fallar("Formato no reconocido: " + parametros.formato);

// Cada filtro se expresa una vez y se usa en dos lugares: dentro de $elemMatch para que
// MongoDB descarte atletas sin participaciones que cumplan, y como predicado para
// mostrar solo las participaciones que cumplen.
const filtros = [];
if (parametros.anio) {
    const anio = Number(parametros.anio);
    filtros.push({ consulta: { "edicion.anio": anio }, cumple: p => p.edicion && p.edicion.anio === anio });
}
if (parametros.temporada) {
    const temporada = leerTemporada(parametros.temporada);
    filtros.push({ consulta: { "edicion.temporada": temporada }, cumple: p => p.edicion && p.edicion.temporada === temporada });
}
if (parametros.deporte) {
    const re = regex(parametros.deporte, false);
    filtros.push({
        consulta: { $or: [{ "evento.disciplina.deporte.nombre": re }, { "evento.disciplina.nombre": re }] },
        cumple: p => {
            const disciplina = p.evento && p.evento.disciplina;
            return !!disciplina && (re.test(texto(disciplina.nombre)) || re.test(texto(disciplina.deporte && disciplina.deporte.nombre)));
        }
    });
}
if (parametros.pais) {
    const codigo = regex(parametros.pais, true);
    const nombre = regex(parametros.pais, false);
    filtros.push({
        consulta: { $or: [
            { "noc.codigo_noc": codigo }, { "noc.entidad.codigo_pais": codigo },
            { "noc.nombre_noc": nombre }, { "noc.entidad.nombre": nombre }
        ] },
        cumple: p => !!p.noc && (
            codigo.test(texto(p.noc.codigo_noc)) || codigo.test(texto(p.noc.entidad && p.noc.entidad.codigo_pais)) ||
            nombre.test(texto(p.noc.nombre_noc)) || nombre.test(texto(p.noc.entidad && p.noc.entidad.nombre))
        )
    });
}
if (parametros.medalla) {
    const medalla = leerMedalla(parametros.medalla);
    filtros.push({
        consulta: { medalla: medalla === "*" ? { $ne: null } : medalla },
        cumple: p => medalla === "*" ? p.medalla !== null && p.medalla !== undefined : p.medalla === medalla
    });
}
const hayFiltros = filtros.length > 0;
const filtroParticipaciones = hayFiltros
    ? { participaciones: { $elemMatch: { $and: filtros.map(f => f.consulta) } } }
    : {};

function conFiltros(condicion) {
    return hayFiltros ? { $and: [condicion, filtroParticipaciones] } : condicion;
}

// ---------------------------------------------------------------- búsqueda
// 1) id exacto, o nombre exacto con los índices de nombre: tal como se escribió, sin
//    acentos y sin las letras acentuadas (registros como "Jos Gonzlez").
// 2) Si no hay coincidencia exacta, una sola pasada que exige todas las palabras escritas
//    en algún campo de nombre. Solo trae nombres; el documento completo se lee después
//    para los atletas elegidos, primero los que coinciden con el nombre completo sin
//    distinguir mayúsculas ni acentos.
// Si queda más de un atleta no se escoge uno: se listan candidatos para elegir por id.
const CAMPOS_NOMBRE = ["nombre", "nombre_completo", "nombre_usado"];
const SOLO_NOMBRES = { nombre: 1, nombre_completo: 1, nombre_usado: 1 };
let filasEncontradas = [];
let criterio = "";
let hayMasFilas = false;

// Conserva el orden de las filas ya clasificadas.
function documentosCompletos(filas, limite) {
    const ids = filas.slice(0, limite).map(fila => fila._id);
    const porId = new Map(atletas.find({ _id: { $in: ids } }).toArray().map(doc => [String(doc._id), doc]));
    return ids.map(id => porId.get(String(id))).filter(Boolean);
}

function ordenar(filas, rango) {
    return filas.sort((a, b) => rango(a) - rango(b) || texto(a.nombre).localeCompare(texto(b.nombre)) || Number(a._id) - Number(b._id));
}

const formas = parametros.atleta ? unicos([
    parametros.atleta,
    sinAcentos(parametros.atleta),
    Array.from(parametros.atleta).filter(letra => sinAcentos(letra) === letra).join("")
]) : [];
const consultaBase = parametros.id
    ? { _id: NumberLong(parametros.id) }
    : { $or: CAMPOS_NOMBRE.map(campo => ({ [campo]: { $in: formas } })) };

if (parametros.id) {
    criterio = "id_atleta";
    filasEncontradas = atletas.find(conFiltros(consultaBase), SOLO_NOMBRES).toArray();
} else {
    // Primero quien coincide tal como se escribió; después las variantes sin acentos.
    filasEncontradas = ordenar(atletas.find(conFiltros(consultaBase), SOLO_NOMBRES).toArray(),
        fila => CAMPOS_NOMBRE.some(campo => fila[campo] === parametros.atleta) ? 0 : 1);
    criterio = "nombre exacto";

    // Si el nombre existe y solo los filtros lo descartan, no hace falta la búsqueda parcial.
    const existeSinFiltros = hayFiltros && filasEncontradas.length === 0 &&
        atletas.findOne(consultaBase, { _id: 1 }) !== null;

    if (filasEncontradas.length === 0 && !existeSinFiltros) {
        const textos = parametros.atleta.split(/[\s•\-]+/).filter(Boolean);
        const palabras = textos.map(p => regex(p, false));
        const inicios = textos.map(p => new RegExp("(?:^|[\\s•\\-])" + patron(p), "i"));
        const completo = regex(parametros.atleta, true);
        const parcial = { $or: CAMPOS_NOMBRE.map(campo => ({ $and: palabras.map(re => ({ [campo]: re })) })) };
        const filas = atletas.find(conFiltros(parcial), SOLO_NOMBRES).limit(MAX_FILAS_PARCIAL + 1).toArray();
        hayMasFilas = filas.length > MAX_FILAS_PARCIAL;
        const iguales = filas.filter(fila => CAMPOS_NOMBRE.some(campo => completo.test(texto(fila[campo]))));
        if (iguales.length > 0) {
            criterio = "nombre sin distinguir mayúsculas ni acentos";
            filasEncontradas = ordenar(iguales, () => 0);
            hayMasFilas = false;
        } else {
            // Primero donde lo escrito es inicio de palabra ("Luis" antes que "Sluis").
            criterio = "coincidencia parcial";
            filasEncontradas = ordenar(filas.slice(0, MAX_FILAS_PARCIAL), fila =>
                CAMPOS_NOMBRE.some(campo => inicios.every(re => re.test(texto(fila[campo])))) ? 0 : 1);
        }
    }
}
const atletasEncontrados = filasEncontradas.length === 1 ? documentosCompletos(filasEncontradas, 1) : [];
const candidatos = filasEncontradas.length > 1 ? documentosCompletos(filasEncontradas, MAX_CANDIDATOS) : [];
const totalCandidatos = filasEncontradas.length > 1 ? filasEncontradas.length : 0;

// Si el atleta existe pero los filtros dejaron todo fuera, se informa qué valores tiene
// para que la consulta se pueda corregir (los nombres de deportes están en inglés).
let valoresDisponibles = [];
if (hayFiltros && filasEncontradas.length === 0) {
    valoresDisponibles = atletas.find(consultaBase).limit(MAX_CANDIDATOS).toArray().map(doc => {
        const lista = doc.participaciones || [];
        const disciplina = p => (p.evento && p.evento.disciplina) || {};
        return {
            id_atleta: numero(doc._id),
            nombre: doc.nombre,
            anios: unicos(lista.map(p => p.edicion && p.edicion.anio)).sort(),
            temporadas: unicos(lista.map(p => p.edicion && p.edicion.temporada)),
            deportes: unicos(lista.flatMap(p => [disciplina(p).deporte && disciplina(p).deporte.nombre, disciplina(p).nombre])),
            paises: unicos(lista.map(p => p.noc && p.noc.codigo_noc)),
            medallas: unicos(lista.map(p => MEDALLAS[p.medalla]))
        };
    });
}

// ---------------------------------------------------------------- armado del resultado
function participacionPlana(p) {
    const edicion = p.edicion || {};
    const sede = edicion.sede || {};
    const evento = p.evento || {};
    const disciplina = evento.disciplina || {};
    const noc = p.noc || {};
    return {
        id_participacion: numero(p.id_participacion),
        id_edicion: edicion.id_edicion === undefined ? null : edicion.id_edicion,
        anio: edicion.anio === undefined ? null : edicion.anio,
        temporada: edicion.temporada || null,
        sede: sede.nombre || null,
        pais_sede: sede.pais ? sede.pais.nombre : null,
        evento: evento.nombre || null,
        disciplina: disciplina.nombre || null,
        deporte: disciplina.deporte ? disciplina.deporte.nombre : null,
        codigo_noc: noc.codigo_noc || null,
        nombre_noc: noc.nombre_noc || null,
        equipo: p.equipo || null,
        edad: numero(p.edad),
        posicion: p.posicion === undefined ? null : p.posicion,
        empatado: p.empatado === true,
        estado_resultado: p.estado_resultado || null,
        medalla: p.medalla || null
    };
}

// Orden determinístico: año, edición, evento e id_participacion.
function ordenarParticipaciones(a, b) {
    return (a.anio || 0) - (b.anio || 0) ||
        (a.id_edicion || 0) - (b.id_edicion || 0) ||
        texto(a.evento).localeCompare(texto(b.evento)) ||
        (a.id_participacion || 0) - (b.id_participacion || 0);
}

function contarMedallas(lista) {
    const conteo = { oro: 0, plata: 0, bronce: 0, total: 0 };
    lista.forEach(p => {
        if (p.medalla === "Gold") conteo.oro += 1;
        if (p.medalla === "Silver") conteo.plata += 1;
        if (p.medalla === "Bronze") conteo.bronce += 1;
    });
    conteo.total = conteo.oro + conteo.plata + conteo.bronce;
    return conteo;
}

function unicos(lista) {
    return Array.from(new Set(lista.filter(v => v !== null && v !== undefined && v !== "")));
}

function mejorResultado(lista) {
    const conMedalla = lista.filter(p => ORDEN_MEDALLA[p.medalla])
        .sort((a, b) => ORDEN_MEDALLA[a.medalla] - ORDEN_MEDALLA[b.medalla] || a.anio - b.anio);
    if (conMedalla.length > 0) {
        const p = conMedalla[0];
        return "Medalla de " + MEDALLAS[p.medalla].toLowerCase() + " · " + p.evento + " · " + p.anio;
    }
    const conPosicion = lista.filter(p => Number.isInteger(p.posicion)).sort((a, b) => a.posicion - b.posicion || a.anio - b.anio);
    if (conPosicion.length > 0) {
        const p = conPosicion[0];
        return "Posición " + p.posicion + " · " + p.evento + " · " + p.anio;
    }
    return null;
}

function fecha(valor) {
    return valor instanceof Date ? valor.toISOString().slice(0, 10) : null;
}

function lugar(ciudad, region, pais) {
    return unicos([ciudad, region, pais && pais.nombre]).join(", ") || null;
}

function armarAtleta(doc) {
    const todas = (doc.participaciones || []).map(participacionPlana).sort(ordenarParticipaciones);
    const visibles = hayFiltros
        ? (doc.participaciones || []).filter(p => filtros.every(f => f.cumple(p))).map(participacionPlana).sort(ordenarParticipaciones)
        : todas;
    const ediciones = unicos(visibles.map(p => p.anio + " " + texto(p.temporada)));
    return {
        id_atleta: numero(doc._id),
        nombre: doc.nombre,
        nombre_completo: doc.nombre_completo,
        otros_nombres: doc.otros_nombres,
        apodos: doc.apodos,
        sexo: doc.sexo,
        fecha_nacimiento: fecha(doc.fecha_nacimiento),
        lugar_nacimiento: lugar(doc.ciudad_nacimiento, doc.region_nacimiento, doc.pais_nacimiento),
        fecha_fallecimiento: fecha(doc.fecha_fallecimiento),
        lugar_fallecimiento: lugar(doc.ciudad_fallecimiento, doc.region_fallecimiento, doc.pais_fallecimiento),
        nacionalidad: doc.pais_nacionalidad ? doc.pais_nacionalidad.nombre : null,
        altura_cm: numero(doc.altura_cm),
        peso_kg: numero(doc.peso_kg),
        roles: doc.roles,
        afiliaciones: doc.afiliaciones,
        titulos: doc.titulos,
        resumen: {
            participaciones_totales: todas.length,
            participaciones_mostradas: visibles.length,
            ediciones: ediciones.length,
            anios: unicos(visibles.map(p => p.anio)),
            deportes: unicos(visibles.map(p => p.deporte)),
            paises_representados: unicos(visibles.map(p => p.codigo_noc && (p.codigo_noc + " (" + p.nombre_noc + ")"))),
            medallas: contarMedallas(visibles),
            mejor_resultado: mejorResultado(visibles)
        },
        participaciones: visibles
    };
}

function armarCandidato(doc) {
    const lista = (doc.participaciones || []).map(participacionPlana);
    return {
        id_atleta: numero(doc._id),
        nombre: doc.nombre,
        nombre_completo: doc.nombre_completo,
        nacimiento: fecha(doc.fecha_nacimiento),
        paises: unicos(lista.map(p => p.codigo_noc)),
        deportes: unicos(lista.map(p => p.deporte)),
        anios: unicos(lista.map(p => p.anio)).sort(),
        medallas: contarMedallas(lista).total
    };
}

const resultado = {
    consulta: {
        atleta: parametros.atleta || null,
        id_atleta: parametros.id || null,
        deporte: parametros.deporte || null,
        pais: parametros.pais || null,
        anio: parametros.anio ? Number(parametros.anio) : null,
        temporada: parametros.temporada || null,
        medalla: parametros.medalla || null,
        criterio
    },
    atletas: atletasEncontrados.map(armarAtleta),
    candidatos: candidatos.map(armarCandidato),
    total_candidatos: totalCandidatos,
    valores_sin_filtros: valoresDisponibles,
    candidatos_incompletos: hayMasFilas,
    fecha_ejecucion_utc: fechaEjecucion.toISOString(),
    tiempo_ms: Date.now() - inicio
};

// ---------------------------------------------------------------- salida
if (parametros.formato === "json") {
    print(JSON.stringify(resultado, null, 2));
} else {
    const linea = "=".repeat(78);
    const fina = "-".repeat(78);

    function campo(etiqueta, valor) {
        if (valor !== null && valor !== undefined && valor !== "") print("  " + (etiqueta + ":").padEnd(22) + valor);
    }

    function resultadoTexto(p) {
        if (p.estado_resultado) return ESTADOS[p.estado_resultado] ? ESTADOS[p.estado_resultado] + " (" + p.estado_resultado + ")" : p.estado_resultado;
        if (Number.isInteger(p.posicion)) return "Posición " + (p.empatado ? "=" : "") + p.posicion;
        return "Sin posición registrada";
    }

    const filtrosUsados = [
        parametros.deporte && "deporte = " + parametros.deporte,
        parametros.pais && "país representado (NOC) = " + parametros.pais,
        parametros.anio && "año = " + parametros.anio,
        parametros.temporada && "temporada = " + parametros.temporada,
        parametros.medalla && "medalla = " + parametros.medalla
    ].filter(Boolean);

    print(linea);
    print("  CONSULTA DE ATLETA · " + (parametros.atleta || "id " + parametros.id));
    if (filtrosUsados.length) print("  Filtros: " + filtrosUsados.join(" · "));
    print(linea);

    if (resultado.atletas.length === 0 && resultado.candidatos.length === 0) {
        print("");
        print("  No se encontró ningún atleta" + (hayFiltros ? " con participaciones que cumplan los filtros." : " con ese nombre."));
        resultado.valores_sin_filtros.forEach(v => {
            print("");
            print("  " + v.nombre + " (id " + v.id_atleta + ") sí existe. Valores disponibles para filtrar:");
            campo("Años", v.anios.join(", "));
            campo("Temporadas", v.temporadas.join(", "));
            campo("Deportes", v.deportes.join(", "));
            campo("Países (NOC)", v.paises.join(", "));
            campo("Medallas", v.medallas.join(", ") || "ninguna");
        });
        if (resultado.valores_sin_filtros.length) {
            print("");
            print("  Los deportes y temporadas están registrados en inglés, como en las fuentes.");
        }
    }

    if (resultado.candidatos.length > 0) {
        print("");
        const total = (hayMasFilas ? "más de " : "") + resultado.total_candidatos;
        print("  Hay " + total + (criterio === "coincidencia parcial"
            ? " atletas cuyo nombre contiene lo escrito"
            : " atletas con ese nombre (homónimos); no se escoge uno automáticamente") +
            (resultado.total_candidatos > resultado.candidatos.length ? ". Se muestran los primeros " + resultado.candidatos.length : "") + ".");
        print("  Repita la consulta con el id del atleta (-Id en Windows, --id en Linux), con el nombre");
        print("  completo o con filtros (país, deporte, año).");
        print("");
        print("  " + "ID".padEnd(8) + "NOMBRE".padEnd(32) + "NACIM.".padEnd(12) + "PAÍS".padEnd(10) + "AÑOS");
        print("  " + fina.slice(2));
        resultado.candidatos.forEach(c => {
            const anios = c.anios.length > 4 ? c.anios.slice(0, 4).join(", ") + "…" : c.anios.join(", ");
            print("  " + String(c.id_atleta).padEnd(8) + texto(c.nombre).slice(0, 30).padEnd(32) +
                texto(c.nacimiento).padEnd(12) + c.paises.join("/").slice(0, 9).padEnd(10) + anios +
                (c.medallas ? "  (" + c.medallas + " medallas)" : ""));
            print("  " + "".padEnd(8) + unicos([c.nombre_completo !== c.nombre ? c.nombre_completo : null, c.deportes.join(", ")]).join(" · "));
        });
    }

    resultado.atletas.forEach(a => {
        const r = a.resumen;
        print("");
        print(linea);
        print("  " + a.nombre + "   (id_atleta " + a.id_atleta + ")");
        print(linea);
        print("  DATOS PERSONALES");
        campo("Nombre completo", a.nombre_completo !== a.nombre ? a.nombre_completo : null);
        campo("Otros nombres", a.otros_nombres);
        campo("Apodos", a.apodos);
        campo("Sexo", SEXOS[a.sexo] || a.sexo);
        campo("Nacimiento", unicos([a.fecha_nacimiento, a.lugar_nacimiento]).join(" · "));
        campo("Fallecimiento", unicos([a.fecha_fallecimiento, a.lugar_fallecimiento]).join(" · "));
        campo("Nacionalidad", a.nacionalidad);
        campo("Altura", a.altura_cm !== null ? a.altura_cm + " cm" : null);
        campo("Peso", a.peso_kg !== null ? a.peso_kg + " kg" : null);
        campo("Afiliaciones", a.afiliaciones);
        campo("Títulos", a.titulos);

        print("");
        print("  RESUMEN" + (hayFiltros ? " (con filtros)" : ""));
        campo("Participaciones", hayFiltros
            ? r.participaciones_mostradas + " de " + r.participaciones_totales
            : r.participaciones_totales);
        campo("Ediciones", r.ediciones + (r.anios.length ? " · " + r.anios.join(", ") : ""));
        campo("Deportes", r.deportes.join(", "));
        campo("Representó a", r.paises_representados.join(", "));
        campo("Medallas", r.medallas.total === 0 ? "ninguna" :
            r.medallas.total + "  (oro " + r.medallas.oro + " · plata " + r.medallas.plata + " · bronce " + r.medallas.bronce + ")");
        campo("Mejor resultado", r.mejor_resultado);

        if (a.participaciones.length === 0) {
            print("");
            print("  Sin participaciones registradas" + (hayFiltros ? " con estos filtros." : "."));
            return;
        }

        print("");
        print("  PARTICIPACIONES Y RESULTADOS");
        let edicionActual = null;
        a.participaciones.forEach(p => {
            const edicion = p.anio + " " + texto(p.temporada);
            if (edicion !== edicionActual) {
                edicionActual = edicion;
                const sede = unicos([p.sede, p.pais_sede]).join(", ") || "sede no informada";
                print("");
                print("  ■ " + p.anio + " · " + (TEMPORADAS[p.temporada] || texto(p.temporada)) +
                    " · " + sede + (p.edad !== null ? "   (edad " + p.edad + ")" : ""));
            }
            const medalla = p.medalla ? "[" + (MEDALLAS[p.medalla] || p.medalla).toUpperCase() + "]" : "";
            print("      " + medalla.padEnd(9) + texto(p.evento));
            const detalle = [
                p.deporte === p.disciplina || !p.disciplina ? p.deporte : p.deporte + " / " + p.disciplina,
                p.codigo_noc && p.codigo_noc + " " + texto(p.nombre_noc),
                p.equipo && p.equipo !== p.nombre_noc ? "equipo " + p.equipo : null,
                resultadoTexto(p)
            ].filter(Boolean).join(" · ");
            print("      " + "".padEnd(9) + detalle);
        });
    });

    print("");
    print(fina);
    print("  Consulta resuelta en " + resultado.tiempo_ms + " ms · búsqueda por " + criterio + " · base " + database.getName());
    print("  Ejecutada el " + fechaEjecucion.toISOString().replace("T", " ").slice(0, 19) + " UTC");
}
