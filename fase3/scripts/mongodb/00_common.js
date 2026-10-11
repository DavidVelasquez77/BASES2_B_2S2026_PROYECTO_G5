var olympMongo = (function () {
    const fs = require("fs");
    const path = require("path");
    const crypto = require("crypto");
    let conversionErrors = 0;

    function conversionFailure(message) {
        conversionErrors += 1;
        throw new Error(message);
    }

    function projectRoot() {
        const cwd = process.cwd();
        const candidates = [
            cwd,
            path.join(cwd, "OlimpiadasF1"),
            path.resolve(cwd, "..", "OlimpiadasF1")
        ];
        const root = candidates.find(candidate =>
            fs.existsSync(path.join(candidate, "data", "processed"))
        );
        if (root) return root;
        throw new Error("No se encontró OlimpiadasF1/data/processed desde la carpeta actual.");
    }

    function phase3Root() {
        const cwd = process.cwd();
        const candidates = [
            cwd,
            path.join(cwd, "fase3"),
            path.resolve(cwd, "..", "fase3")
        ];
        const root = candidates.find(candidate =>
            fs.existsSync(path.join(candidate, "scripts", "mongodb", "00_common.js"))
        );
        if (root) return root;
        throw new Error("No se encontró la carpeta fase3 desde la carpeta actual.");
    }

    function parseCsv(filePath) {
        let input = fs.readFileSync(filePath, "utf8");
        if (input.charCodeAt(0) === 0xFEFF) input = input.slice(1);
        const records = [];
        let row = [];
        let field = "";
        let quoted = false;

        for (let i = 0; i < input.length; i += 1) {
            const ch = input[i];
            if (quoted) {
                if (ch === '"') {
                    if (input[i + 1] === '"') {
                        field += '"';
                        i += 1;
                    } else {
                        quoted = false;
                    }
                } else {
                    field += ch;
                }
                continue;
            }

            if (ch === '"' && field.length === 0) {
                quoted = true;
            } else if (ch === ",") {
                row.push(field);
                field = "";
            } else if (ch === "\n") {
                row.push(field);
                if (!(row.length === 1 && row[0] === "")) records.push(row);
                row = [];
                field = "";
            } else if (ch === "\r") {
                if (input[i + 1] !== "\n") field += ch;
            } else {
                field += ch;
            }
        }
        if (quoted) throw new Error("CSV con comillas sin cerrar: " + filePath);
        if (row.length > 0 || field.length > 0) {
            row.push(field);
            records.push(row);
        }
        if (records.length === 0) throw new Error("CSV vacío: " + filePath);

        const headers = records.shift();
        if (new Set(headers).size !== headers.length) {
            throw new Error("Encabezados duplicados en " + filePath);
        }
        return records.map((values, index) => {
            if (values.length !== headers.length) {
                throw new Error(
                    "Fila CSV " + (index + 2) + " con " + values.length +
                    " campos; se esperaban " + headers.length + " en " + filePath
                );
            }
            const result = {};
            headers.forEach((header, column) => { result[header] = values[column]; });
            return result;
        });
    }

    function stringValue(value) {
        return value === "" ? null : value;
    }

    function integerText(value, label) {
        if (value === "" || value === null || value === undefined) return null;
        let normalized = String(value);
        if (/^[+-]?\d+\.0+$/.test(normalized)) normalized = normalized.replace(/\.0+$/, "");
        if (!/^[+-]?\d+$/.test(normalized)) {
            conversionFailure(label + " no es un entero válido: " + JSON.stringify(value));
        }
        return BigInt(normalized).toString();
    }

    function int32(value, label) {
        const normalized = integerText(value, label);
        if (normalized === null) return null;
        const number = Number(normalized);
        if (!Number.isSafeInteger(number) || number < -2147483648 || number > 2147483647) {
            conversionFailure(label + " excede INT32: " + value);
        }
        return NumberInt(number);
    }

    function int64(value, label) {
        const normalized = integerText(value, label);
        return normalized === null ? null : NumberLong(normalized);
    }

    function key(value, label) {
        const normalized = integerText(value, label);
        return normalized === null ? null : normalized;
    }

    function decimal(value, label) {
        if (value === "") return null;
        try {
            return Decimal128.fromString(value);
        } catch (error) {
            conversionFailure(label + " no es decimal válido: " + JSON.stringify(value));
        }
    }

    function date(value, label) {
        if (value === "") return null;
        if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            conversionFailure(label + " no tiene formato ISO YYYY-MM-DD: " + value);
        }
        const parsed = new Date(value + "T00:00:00.000Z");
        if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) {
            conversionFailure(label + " no es una fecha real: " + value);
        }
        return parsed;
    }

    function boolean(value, label) {
        if (value === "") return null;
        const normalized = value.toLowerCase();
        if (["true", "1"].includes(normalized)) return true;
        if (["false", "0"].includes(normalized)) return false;
        conversionFailure(label + " no es booleano válido: " + value);
    }

    function sha256(filePath) {
        return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
    }

    function csvEscape(value) {
        const text = value === null || value === undefined ? "" : String(value);
        return '"' + text.replace(/"/g, '""') + '"';
    }

    function writeCsv(filePath, headers, rows) {
        const lines = [headers.map(csvEscape).join(",")];
        rows.forEach(row => lines.push(headers.map(header => csvEscape(row[header])).join(",")));
        fs.writeFileSync(filePath, "\uFEFF" + lines.join("\r\n") + "\r\n", "utf8");
    }

    return {
        fs, path, projectRoot, phase3Root, parseCsv, stringValue, int32, int64, key,
        decimal, date, boolean, sha256, writeCsv,
        conversionErrorCount: () => conversionErrors
    };
})();
