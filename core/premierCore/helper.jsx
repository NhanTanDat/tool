/**
 * ExtendScript (JSX) helpers converted from helper.py for Premiere workflows.
 * Functions:
 *  - mergeCsvWithTxt(csvIn, txtIn, csvOut)
 *  - mergeCsvWithTxtToPlain(txtOut, csvIn, txtIn, includeHeader, joiner)
 *
 * Notes:
 *  - Uses simple CSV parser supporting quotes and escaped quotes (") per RFC4180 basics.
 *  - File encoding is set to UTF-8 by default.
 */

var JSX_HELPER_ENCODING = 'UTF-8';

// ===== Helpers for path + I/O =====
function _joinPath(a, b) {
	if (!a || a === '') return b || '';
	if (!b || b === '') return a || '';
	var s = a.charAt(a.length - 1);
	return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

function _fileExists(path) {
    try { return (new File(path)).exists; } catch (e) { return false; }
}

function _folderExists(p) {
	try { var f = new Folder(p); return f.exists; } catch (e) { return false; }
}

function _ensureFolder(p) {
	try { var f = new Folder(p); if (!f.exists) return f.create(); return true; } catch (e) { return false; }
}

function _readTextFile(p) {
	try {
		var f = new File(p);
		if (!f.exists) return '';
		if (!f.open('r')) return '';
		var t = f.read();
		f.close();
		return t;
	} catch (e) { return ''; }
}

// parse text file with key=value format
function _parsePathTxt(path) {
	try {
		var content = _readTextFile(path);
		var lines = content.split('\n');
		var cfg = {};
		for (var i = 0; i < lines.length; i++) {
			var line = lines[i].replace(/^\s+|\s+$/g, '');
			if (line === "" || line.indexOf("=") === -1) continue;
			var parts = line.split("=");
			if (parts.length >= 2) {
				var key = parts[0].replace(/^\s+|\s+$/g, '');
				var value = parts.slice(1).join("=").replace(/^\s+|\s+$/g, '');
				cfg[key] = value;
			}
		}
		return cfg;
	} catch (e) {
		$.writeln("Lỗi đọc file text: " + e.message);
		return {};
	}
}

function _readAllLines(path, encoding) {
    var f = new File(path);
    f.encoding = encoding || JSX_HELPER_ENCODING;
    if (!f.exists) return [];
    if (!f.open('r')) return [];
    var lines = [];
    while (!f.eof) lines.push(f.readln());
    f.close();
    return lines;
}

function _writeAllText(path, content, encoding) {
    var f = new File(path);
    f.encoding = encoding || JSX_HELPER_ENCODING;
    if (!f.open('w')) return false;
    f.write(content);
    f.close();
    return true;
}

// Parse one CSV line -> array of fields (supports quotes and doubled quotes)
function _parseCSVLine(line) {
    var res = [];
    var cur = '';
    var inQ = false;
    for (var i = 0; i < line.length; i++) {
        var ch = line.charAt(i);
        if (inQ) {
            if (ch === '"') {
                if (i + 1 < line.length && line.charAt(i + 1) === '"') { cur += '"'; i++; }
                else { inQ = false; }
            } else { cur += ch; }
        } else {
            if (ch === ',') { res.push(cur); cur = ''; }
            else if (ch === '"') { inQ = true; }
            else { cur += ch; }
        }
    }
    res.push(cur);
    return res;
}

function _escapeCSVField(val) {
    if (val === null || typeof val === 'undefined') return '';
    var s = String(val);
    var needsQuote = /[",\n\r]/.test(s) || /^\s|\s$/.test(s);
    if (needsQuote) {
        s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
}

function _csvJoin(fields) {
    var out = [];
    for (var i = 0; i < fields.length; i++) out.push(_escapeCSVField(fields[i]));
    return out.join(',');
}

function _readCSV(path, encoding) {
    var lines = _readAllLines(path, encoding);
    if (!lines.length) return { header: [], rows: [] };
    var header = _parseCSVLine(lines[0]);
    var rows = [];
    for (var i = 1; i < lines.length; i++) {
        var ln = lines[i];
        if (!ln || ln === '') continue;
        var cols = _parseCSVLine(ln);
        var obj = {};
        for (var c = 0; c < header.length; c++) {
            obj[header[c]] = (c < cols.length) ? cols[c] : '';
        }
        rows.push(obj);
    }
    return { header: header, rows: rows };
}

function _writeCSV(path, header, rows, encoding) {
    var parts = [];
    parts.push(_csvJoin(header));
    for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var fields = [];
        for (var h = 0; h < header.length; h++) {
            fields.push(r.hasOwnProperty(header[h]) ? r[header[h]] : '');
        }
        parts.push(_csvJoin(fields));
    }
    return _writeAllText(path, parts.join('\n'), encoding);
}

// Public API
function mergeCsvWithTxt(csvIn, txtIn, csvOut, encoding) {
    encoding = encoding || JSX_HELPER_ENCODING;
    if (!csvOut) {
        if (csvIn.toLowerCase().match(/\.csv$/)) csvOut = csvIn.substr(0, csvIn.length - 4) + '_merged.csv';
        else csvOut = csvIn + '_merged.csv';
    }
    var texts = _readAllLines(txtIn, encoding);
    // build reader
    var data = _readCSV(csvIn, encoding);
    var header = data.header.slice(0);
    var rows = data.rows.slice(0);
    // ensure textContent column
    var hasText = false;
    for (var i = 0; i < header.length; i++) if (header[i] === 'textContent') { hasText = true; break; }
    if (!hasText) header.push('textContent');
    // merge line by line
    for (var r = 0; r < rows.length; r++) {
        var t = (r < texts.length) ? (texts[r] || '') : '';
        rows[r]['textContent'] = t;
    }
    _writeCSV(csvOut, header, rows, encoding);
    return csvOut;
}

function mergeCsvWithTxtToPlain(txtOut, csvIn, txtIn, includeHeader, joiner, encoding) {
    encoding = encoding || JSX_HELPER_ENCODING;
    includeHeader = includeHeader === true; // default false
    joiner = (typeof joiner === 'string') ? joiner : ' | ';

    var data = _readCSV(csvIn, encoding);
    var rows = data.rows;
    var overrideTexts = [];
    if (txtIn && _fileExists(txtIn)) {
        overrideTexts = _readAllLines(txtIn, encoding);
    }
    var outParts = [];
    if (includeHeader) outParts.push('# index | start-end(seconds) | name | textContent');
    for (var i = 0; i < rows.length; i++) {
        var r = rows[i];
        var idx = (r.hasOwnProperty('indexInTrack') ? r['indexInTrack'] : '');
        var seg = (r.hasOwnProperty('startSeconds') ? r['startSeconds'] : '') + ' - ' + (r.hasOwnProperty('endSeconds') ? r['endSeconds'] : '');
        var name = (r.hasOwnProperty('name') ? r['name'] : '');
        var t = '';
        if (overrideTexts.length) t = (i < overrideTexts.length) ? overrideTexts[i] : '';
        else t = (r.hasOwnProperty('textContent') ? (r['textContent'] || '') : '');
        outParts.push([idx, seg, name, t].join(joiner));
    }
    _writeAllText(txtOut, outParts.join('\n'), encoding);
    return txtOut;
}

// --------------------------------------------------------------
// Self-test runner (converted from Python __main__ block)
// --------------------------------------------------------------
function _pathJoin(a, b) {
    if (!a || a === '') return b || '';
    if (!b || b === '') return a || '';
    if (a.charAt(a.length - 1) === '/' || a.charAt(a.length - 1) === '\\') return a + b;
    return a + '/' + b;
}

function _getThisDir() {
    try {
        var f = new File($.fileName);
        return f.parent.fsName;
    } catch (e) {
        return '';
    }
}

function _getRootDir() {
    try {
        var thisDir = new Folder(_getThisDir());
        // this file is in core/premierCore/helper.jsx -> go up 2 levels to project root
        var parent1 = thisDir.parent; // premierCore
        var parent2 = parent1 ? parent1.parent : null; // core
        var parent3 = parent2 ? parent2.parent : null; // project root
        return parent3 ? parent3.fsName : '';
    } catch (e) {
        return '';
    }
}

function runHelperSelfTest() {
    // ===== Xác định thư mục data theo path.txt =====
    var DATA_DIR = (function () {
        try {
            // 1) Tìm root (....../projectRoot)
            var scriptFile = new File($.fileName);      // .../core/premierCore/helper.jsx
            var premierCoreDir = scriptFile.parent;     // premierCore
            var coreDir = premierCoreDir.parent;        // core
            var rootDir = coreDir.parent;               // project root

            // 2) Root data folder (để tìm path.txt): <root>/data
            var rootDataPath = rootDir.fsName + '/data';
            _ensureFolder(rootDataPath);

            // 3) Đọc data/path.txt (nếu có) để lấy data_folder hoặc project_slug
            var pathTxt = _joinPath(rootDataPath, 'path.txt');
            var targetDataPath = rootDataPath; // fallback mặc định
            if (_fileExists(pathTxt)) {
                try {
                    var cfg = _parsePathTxt(pathTxt);
                    // Ưu tiên trường data_folder (có thể là tuyệt đối hoặc tương đối so với root/data)
                    if (cfg && cfg.data_folder) {
                        var df = String(cfg.data_folder);
                        if (_folderExists(df)) {
                            targetDataPath = df;
                        } else {
                            targetDataPath = _joinPath(rootDataPath, df);
                        }
                    } else if (cfg && cfg.project_slug) {
                        targetDataPath = _joinPath(rootDataPath, String(cfg.project_slug));
                    }
                } catch (eCfg) {
                    $.writeln('[DATA_DIR] Lỗi đọc path.txt, dùng fallback root/data. Error: ' + eCfg);
                }
            } else {
                $.writeln('[DATA_DIR] Không tìm thấy data/path.txt, dùng fallback root/data');
            }

            _ensureFolder(targetDataPath);
            var folder = new Folder(targetDataPath);
            $.writeln('[DATA_DIR] Using data folder: ' + folder.fsName);
            return folder.fsName.replace(/\\/g,'/');
        } catch (e2) {
            $.writeln('[DATA_DIR] Fallback to desktop due to error: ' + e2);
            return Folder.desktop.fsName.replace(/\\/g,'/');
        }
    })();

    var csv_in = _pathJoin(DATA_DIR, 'timeline_export.csv');
    var txt_in = _pathJoin(DATA_DIR, 'list_name.txt');
    var csv_out = null;

    var out_path = mergeCsvWithTxt(csv_in, txt_in, csv_out);
    $.writeln('Merged CSV saved to: ' + out_path);

    // Export plain text
    var plain_txt = _pathJoin(DATA_DIR, 'timeline_merged.txt');
    var txt_export = mergeCsvWithTxtToPlain(plain_txt, csv_in, txt_in, true);
    $.writeln('Plain text merged saved to: ' + txt_export);
}

// To execute the self-test inside ExtendScript, set the flag below to true.
var RUN_SELF_TEST = true;
if (RUN_SELF_TEST) runHelperSelfTest();

// // Example usage (commented):
// var merged = mergeCsvWithTxt('P:/coddd/autotool/data/timeline_export.csv', 'P:/coddd/autotool/data/3571/list_name.txt', null);
// // var txt = mergeCsvWithTxtToPlain('P:/coddd/autotool/data/timeline_merged.txt', 'P:/coddd/autotool/data/timeline_export.csv', 'P:/coddd/autotool/data/3571/list_name.txt', true);
