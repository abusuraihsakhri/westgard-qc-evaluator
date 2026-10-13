(function () {
    'use strict';
    var $ = function (id) { return document.getElementById(id); };
    var latest = null;
    var exampleObs = [
        'run,level,value',
        '1,Level1,100',
        '1,Level2,201',
        '2,Level1,112',
        '2,Level2,200',
        '3,Level1,112',
        '3,Level2,177',
        '4,Level1,107',
        '4,Level2,202',
        '5,Level1,107',
        '5,Level2,201',
        '6,Level1,106',
        '6,Level2,199',
        '7,Level1,108',
        '7,Level2,199'
    ].join('\n');
    var exampleStats = 'level,mean,sd\nLevel1,100,5\nLevel2,200,10';
    function setError(message) {
        $('error').textContent = message;
        $('error').hidden = !message;
    }
    function hideResult() {
        latest = null;
        $('results').hidden = true;
        $('empty').hidden = false;
    }
    function elt(tag, text, className) {
        var el = document.createElement(tag);
        if (text !== undefined) el.textContent = text;
        if (className) el.className = className;
        return el;
    }
    function addRow(result) {
        var tr = elt('tr');
        var run = elt('td', String(result.run), 'mono');
        var verdict = elt('td', result.verdict, result.verdict === 'REJECT' ? 'reject' :
            (result.verdict === 'WARNING' ? 'warn' : 'pass'));
        var rules = elt('td', result.violations.map(function (v) { return v.rule + ' (' + v.scope + ')'; }).join(', ') || '—');
        var scores = elt('td', Object.keys(result.z_scores).map(function (k) {
            return k + ': ' + result.z_scores[k].toFixed(2);
        }).join(' · '), 'mono');
        tr.append(run, verdict, rules, scores);
        return tr;
    }
    function svgEl(name, attributes, parent, label) {
        var el = document.createElementNS('http://www.w3.org/2000/svg', name);
        Object.keys(attributes).forEach(function (key) { el.setAttribute(key, String(attributes[key])); });
        if (label !== undefined) el.textContent = label;
        parent.appendChild(el);
        return el;
    }
    function drawPlot() {
        var svg = $('plot');
        svg.replaceChildren();
        if (!latest) return;
        var level = $('level').value, data = latest.results.filter(function (r) {
            return Object.prototype.hasOwnProperty.call(r.z_scores, level);
        });
        if (!data.length) return;
        var width = 600, height = 330, left = 57, right = 20, top = 24, bottom = 49;
        var x0 = left, x1 = width - right, y0 = top, y1 = height - bottom;
        var max = Math.max(3.5, data.reduce(function (v, r) { return Math.max(v, Math.abs(r.z_scores[level])); }, 0) + .4);
        var y = function (z) { return y0 + (max - z) / (2 * max) * (y1 - y0); };
        var x = function (i) { return x0 + (data.length === 1 ? .5 : i / (data.length - 1)) * (x1 - x0); };
        [-3, -2, -1, 0, 1, 2, 3].forEach(function (tick) {
            svgEl('line', {x1:x0,y1:y(tick),x2:x1,y2:y(tick),class:tick===0?'zero':'grid-line'}, svg);
            svgEl('text', {x:14,y:y(tick)+4},svg,(tick > 0 ? '+' : '') + tick + ' SD');
        });
        svgEl('line',{x1:x0,y1:y0,x2:x0,y2:y1,class:'axis'},svg);
        svgEl('line',{x1:x0,y1:y1,x2:x1,y2:y1,class:'axis'},svg);
        var points = data.map(function (r, i) { return x(i) + ',' + y(r.z_scores[level]); }).join(' ');
        svgEl('polyline',{points:points,class:'series'},svg);
        data.forEach(function (r, i) {
            var z = r.z_scores[level];
            var violations = r.violations.filter(function (v) { return v.levels.indexOf(level) >= 0; });
            var color = violations.some(function (v) { return v.is_rejection; }) ? '#ff8a9a' :
                (violations.length ? '#ffca78' : '#91dfbb');
            var dot = svgEl('circle',{cx:x(i),cy:y(z),r:data.length>120?2:4,fill:color},svg);
            svgEl('title',{},dot,'Run ' + r.run + ': z=' + z.toFixed(3) + ' · ' +
                (violations.map(function (v) { return v.rule; }).join(', ') || 'No rule'));
        });
        // Label a subset of runs to prevent unreadable axis text on larger datasets.
        var step = Math.max(1, Math.ceil(data.length / 9));
        for (var i = 0; i < data.length; i += step) {
            svgEl('text',{x:x(i),y:y1+19,'text-anchor':'middle'},svg,String(data[i].run));
        }
        svgEl('text',{x:width/2,y:height-8,'text-anchor':'middle'},svg,'Run');
    }
    function evaluate() {
        setError('');
        try {
            var observations = WestgardQC.parseObservations($('observations').value);
            var stats = WestgardQC.parseStats($('stats').value);
            var results = WestgardQC.evaluate(observations, stats);
            var count = function (status) { return results.filter(function (r) { return r.verdict === status; }).length; };
            latest = {results:results,stats:stats,observations:observations};
            $('total').textContent = String(results.length);
            $('passed').textContent = String(count('PASS'));
            $('warned').textContent = String(count('WARNING'));
            $('rejected').textContent = String(count('REJECT'));
            var tbody = $('result-rows');
            tbody.replaceChildren();
            results.forEach(function (r) { tbody.appendChild(addRow(r)); });
            var select = $('level');
            select.replaceChildren();
            var levelList = Array.from(new Set(observations.map(function (o) { return o.level; })));
            levelList.forEach(function (level) {
                var option = elt('option',level);
                option.value = level;
                select.appendChild(option);
            });
            $('empty').hidden = true;
            $('results').hidden = false;
            drawPlot();
        } catch (e) {
            hideResult();
            setError(e instanceof Error ? e.message : 'Could not evaluate the input.');
        }
    }
    function download(name, mime, content) {
        var blob = new Blob([content], {type:mime});
        var url = URL.createObjectURL(blob);
        var a = elt('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); },1000);
    }
    function encodeCsvCell(value) {
        var text = String(value);
        return /[,"\r\n]/.test(text) ? '"' + text.replace(/"/g,'""') + '"' : text;
    }
    function exportCsv() {
        if (!latest) return;
        var lines = ['run,verdict,violations,z_scores'];
        latest.results.forEach(function (r) {
            var cols = [r.run,r.verdict,r.violations.map(function (v) { return v.rule + '/' + v.scope; }).join(';'),JSON.stringify(r.z_scores)];
            lines.push(cols.map(encodeCsvCell).join(','));
        });
        download('westgard-results.csv','text/csv;charset=utf-8',lines.join('\r\n')+'\r\n');
    }
    function exportJson() {
        if (!latest) return;
        var stats = {};
        latest.stats.forEach(function (v,k) { Object.defineProperty(stats,k,{value:v,enumerable:true,configurable:true}); });
        download('westgard-results.json','application/json',JSON.stringify({
            rule_set:'Westgard 1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x; level-specific run histories',
            stats:stats,results:latest.results
        },null,2));
    }
    function loadFile(inputId, textareaId) {
        $(inputId).addEventListener('change',async function (e) {
            var file = e.target.files && e.target.files[0];
            if (!file) return;
            if (file.size > 1000000) { setError('CSV file exceeds 1 MB.'); return; }
            try { $(textareaId).value = await file.text(); setError(''); hideResult(); }
            catch (err) { setError('Unable to read the selected CSV file.'); }
        });
    }
    $('evaluate').addEventListener('click',evaluate);
    $('example').addEventListener('click',function () {
        $('observations').value=exampleObs;
        $('stats').value=exampleStats;
        evaluate();
    });
    $('clear').addEventListener('click',function () {
        $('observations').value='';
        $('stats').value='';
        $('observations-file').value='';
        $('stats-file').value='';
        setError('');
        hideResult();
    });
    ['observations','stats'].forEach(function (id) {
        $(id).addEventListener('input',function () { hideResult(); setError(''); });
    });
    $('level').addEventListener('change',drawPlot);
    $('export-json').addEventListener('click',exportJson);
    $('export-csv').addEventListener('click',exportCsv);
    loadFile('observations-file','observations');
    loadFile('stats-file','stats');
}());
