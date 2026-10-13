/* Browser and Node-compatible Westgard QC evaluator. No external dependencies. */
(function (root) {
    'use strict';

    function csvRows(text) {
        if (typeof text !== 'string' || text.length > 1000000) {
            throw new Error('CSV text must be no more than 1 MB.');
        }
        var input = text.replace(/^\uFEFF/, '');
        var rows = [], row = [], cell = '', quoted = false, afterQuote = false;
        for (var i = 0; i < input.length; i++) {
            var ch = input[i];
            if (quoted) {
                if (ch === '"') {
                    if (input[i + 1] === '"') { cell += '"'; i++; }
                    else { quoted = false; afterQuote = true; }
                } else { cell += ch; }
            } else if (afterQuote) {
                if (ch === ',') { row.push(cell); cell = ''; afterQuote = false; }
                else if (ch === '\n' || ch === '\r') {
                    row.push(cell); rows.push(row); row = []; cell = ''; afterQuote = false;
                    if (ch === '\r' && input[i + 1] === '\n') i++;
                } else if (ch !== ' ' && ch !== '\t') {
                    throw new Error('Invalid character after closing CSV quote.');
                }
            } else if (ch === '"') {
                if (cell.trim()) throw new Error('Unexpected CSV quote.');
                quoted = true;
            } else if (ch === ',') {
                row.push(cell); cell = '';
            } else if (ch === '\n' || ch === '\r') {
                row.push(cell); rows.push(row); row = []; cell = '';
                if (ch === '\r' && input[i + 1] === '\n') i++;
            } else { cell += ch; }
        }
        if (quoted) throw new Error('Unterminated quoted CSV field.');
        if (afterQuote || cell.length || row.length) { row.push(cell); rows.push(row); }
        return rows.filter(function (r) { return r.some(function (x) { return x.trim() !== ''; }); });
    }

    function parseTable(text, columns) {
        var rows = csvRows(text);
        if (!rows.length) throw new Error('CSV is empty.');
        var header = rows[0].map(function (s) { return s.trim().toLowerCase(); });
        if (new Set(header).size !== header.length) throw new Error('Duplicate CSV column names.');
        columns.forEach(function (name) {
            if (header.indexOf(name) < 0) throw new Error('Missing column: ' + name);
        });
        if (rows.length < 2) throw new Error('CSV contains no data rows.');
        if (rows.length > 10001) throw new Error('CSV exceeds 10,000 data rows.');
        return rows.slice(1).map(function (row, index) {
            if (row.length !== header.length) throw new Error('Incorrect column count at record ' + (index + 1));
            var obj = Object.create(null);
            header.forEach(function (h, j) { obj[h] = row[j].trim(); });
            return obj;
        });
    }

    function finiteNumber(value, label) {
        if (value === '') throw new Error(label + ' cannot be blank.');
        var n = Number(value);
        if (!Number.isFinite(n)) throw new Error(label + ' must be finite.');
        return n;
    }

    function parseObservations(text) {
        var seen = new Set();
        return parseTable(text, ['run', 'level', 'value']).map(function (r) {
            var run = finiteNumber(r.run, 'Run');
            if (!Number.isSafeInteger(run)) throw new Error('Run must be an integer.');
            if (!r.level) throw new Error('Control level cannot be blank.');
            var key = JSON.stringify([run, r.level]);
            if (seen.has(key)) throw new Error('Duplicate observation: run ' + run + ', level ' + r.level);
            seen.add(key);
            return { run: run, level: r.level, value: finiteNumber(r.value, 'Value') };
        });
    }

    function parseStats(text) {
        var stats = new Map();
        parseTable(text, ['level', 'mean', 'sd']).forEach(function (r) {
            if (!r.level) throw new Error('Statistics level cannot be blank.');
            if (stats.has(r.level)) throw new Error('Duplicate statistics for ' + r.level);
            var mean = finiteNumber(r.mean, 'Mean');
            var sd = finiteNumber(r.sd, 'SD');
            if (sd <= 0) throw new Error('SD must be positive for ' + r.level);
            stats.set(r.level, { mean: mean, sd: sd });
        });
        return stats;
    }

    function evaluate(observations, stats) {
        if (!observations.length) throw new Error('No observations.');
        var perRun = new Map(), seen = new Set();
        observations.forEach(function (obs) {
            if (!Number.isSafeInteger(obs.run) || typeof obs.level !== 'string' || !obs.level ||
                !Number.isFinite(obs.value)) throw new Error('Invalid observation.');
            var key = JSON.stringify([obs.run, obs.level]);
            if (seen.has(key)) throw new Error('Duplicate observation: ' + key);
            seen.add(key);
            if (!perRun.has(obs.run)) perRun.set(obs.run, new Map());
            perRun.get(obs.run).set(obs.level, obs.value);
        });
        var histories = new Map(), results = [];
        Array.from(perRun.keys()).sort(function (a, b) { return a - b; }).forEach(function (run) {
            var values = perRun.get(run), zScores = Object.create(null), violations = [];
            var levels = Array.from(values.keys());
            function flag(rule, scope, ls, reject, message) {
                violations.push({ rule: rule, scope: scope, levels: ls, is_rejection: reject, message: message });
            }
            levels.forEach(function (level) {
                var stat = stats.get(level);
                if (!stat || !Number.isFinite(stat.mean) || !Number.isFinite(stat.sd) || stat.sd <= 0) {
                    throw new Error('Valid mean and SD required for control level: ' + level);
                }
                var z = (values.get(level) - stat.mean) / stat.sd;
                if (!Number.isFinite(z)) throw new Error('Non-finite z-score for ' + level);
                zScores[level] = z;
                if (Math.abs(z) >= 3) flag('1-3s', 'single-point', [level], true, level + ': at least 3 SD from mean');
                else if (Math.abs(z) >= 2) flag('1-2s', 'single-point', [level], false, level + ': at least 2 SD from mean');
            });
            if (levels.length >= 2) {
                var max = levels.reduce(function (a, b) { return zScores[a] >= zScores[b] ? a : b; });
                var min = levels.reduce(function (a, b) { return zScores[a] <= zScores[b] ? a : b; });
                if (zScores[max] >= 2 && zScores[min] <= -2 && zScores[max] - zScores[min] >= 4) {
                    flag('R-4s', 'within-run', [max, min], true, 'Opposite control limits span at least 4 SD');
                }
                var pos = levels.filter(function (l) { return zScores[l] >= 2; });
                var neg = levels.filter(function (l) { return zScores[l] <= -2; });
                if (pos.length >= 2) flag('2-2s', 'within-run', pos, true, 'Two levels exceed +2 SD');
                if (neg.length >= 2) flag('2-2s', 'within-run', neg, true, 'Two levels exceed -2 SD');
            }
            histories.forEach(function (h, level) {
                if (!values.has(level)) histories.set(level, []);
            });
            levels.forEach(function (level) {
                var h = histories.get(level) || [];
                h.push(zScores[level]);
                if (h.length > 10) h.shift();
                histories.set(level, h);
                if (h.length >= 2 && h[h.length - 1] >= 2 && h[h.length - 2] >= 2) {
                    flag('2-2s', 'across-run', [level], true, level + ': two consecutive values above +2 SD');
                }
                if (h.length >= 2 && h[h.length - 1] <= -2 && h[h.length - 2] <= -2) {
                    flag('2-2s', 'across-run', [level], true, level + ': two consecutive values below -2 SD');
                }
                if (h.length >= 4 && h.slice(-4).every(function (z) { return z >= 1; })) {
                    flag('4-1s', 'across-run', [level], true, level + ': four consecutive values above +1 SD');
                }
                if (h.length >= 4 && h.slice(-4).every(function (z) { return z <= -1; })) {
                    flag('4-1s', 'across-run', [level], true, level + ': four consecutive values below -1 SD');
                }
                if (h.length >= 10 && h.slice(-10).every(function (z) { return z > 0; })) {
                    flag('10x', 'across-run', [level], true, level + ': ten consecutive values above mean');
                }
                if (h.length >= 10 && h.slice(-10).every(function (z) { return z < 0; })) {
                    flag('10x', 'across-run', [level], true, level + ': ten consecutive values below mean');
                }
            });
            var verdict = violations.some(function (v) { return v.is_rejection; }) ? 'REJECT' :
                (violations.length ? 'WARNING' : 'PASS');
            results.push({ run: run, verdict: verdict, z_scores: zScores, violations: violations });
        });
        return results;
    }

    var api = { csvRows: csvRows, parseObservations: parseObservations, parseStats: parseStats, evaluate: evaluate };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.WestgardQC = api;
}(typeof window !== 'undefined' ? window : this));
