/**
 * runAll.jsx - One-click runner for Premiere workflow
 * Steps:
 *  1) Export timeline (top-most selected video track) -> data/<projectName>/timeline_export.csv
 *     - getTimeline.jsx vẫn xuất ra data/timeline_export.csv; script này sẽ di chuyển vào data/<projectName>/
 *  2) Merge CSV với text từ data/<projectName>/list_name.txt -> data/<projectName>/timeline_export_merged.csv
 *  3) Import resources from resource_dir subfolders into bins
 *  4) Cut & push clips using merged CSV (via cutAndPush.jsx auto-run)
 *
 * Reads data/path.txt with structure:
 *   { "resource_dir": "C:/path/to/resource", "project_slug": "3571" }
 * You can also call runAll(projectName) to override project_slug and target subfolder under /data.
 * Alternatively, define global RUNALL_PROJECT_NAME before eval to override.
 */

// ===== JSON Polyfill =====
if (typeof JSON === 'undefined') {
    var JSON = {};
}

// if (typeof JSON.stringify !== 'function') {
//     JSON.stringify = (function () {
//         function esc(str) {
//             return (
//                 '"' +
//                 String(str)
//                     .replace(/\\/g, '\\\\')
//                     .replace(/"/g, '\\"')
//                     .replace(/\r/g, '\\r')
//                     .replace(/\n/g, '\\n')
//                     .replace(/\t/g, '\\t')
//                     .replace(/\f/g, '\\f')
//                     .replace(/\b/g, '') +
//                 '"'
//             );
//         }

//         function isArr(v) {
//             return Object.prototype.toString.call(v) === '[object Array]';
//         }

//         function stringify(v) {
//             var t = typeof v;
//             if (v === null) return 'null';
//             if (t === 'number' || t === 'boolean') return '' + v;
//             if (t === 'string') return esc(v);
//             if (t === 'undefined' || t === 'function') return 'null';
//             if (isArr(v)) {
//                 var a = [];
//                 for (var i = 0; i < v.length; i++) a.push(stringify(v[i]));
//                 return '[' + a.join(',') + ']';
//             }
//             var parts = [];
//             for (var k in v) if (v.hasOwnProperty(k)) parts.push(esc(k) + ':' + stringify(v[k]));
//             return '{' + parts.join(',') + '}';
//         }

//         return function (v) {
//             return stringify(v);
//         };
//     })();
// }

if (typeof JSON.parse !== 'function') {
    JSON.parse = function (txt) {
        return eval('(' + txt + ')');
    };
}

// ===== Utils =====
function log(msg) {
    try {
        $.writeln('[runAll] ' + msg);
    } catch (e) {}
}

function joinPath(a, b) {
    if (!a || a === '') return b || '';
    if (!b || b === '') return a || '';
    var s = a.charAt(a.length - 1);
    return s === '/' || s === '\\' ? a + b : a + '/' + b;
}

//hàm này trả về path chuẩn định dạng
function normalizePath(p) {
    if (!p || p === '') return '';
    return p.replace(/\\/g, '/').replace(/\/+/g, '/');
}

function fileExists(p) {
    try {
        var f = new File(p);
        return f.exists;
    } catch (e) {
        return false;
    }
}

function folderExists(p) {
    try {
        var f = new Folder(p);
        return f.exists;
    } catch (e) {
        return false;
    }
}

function ensureFolder(p) {
    try {
        var f = new Folder(p);
        if (!f.exists) return f.create();
        return true;
    } catch (e) {
        return false;
    }
}

function readJSONFile(path) {
    try {
        var file = new File(path);
        if (!file.exists) {
            alert("Không tìm thấy file JSON: " + path);
            return null;
        }

        file.encoding = "UTF-8";  // đảm bảo đọc đúng encoding
        if (!file.open("r")) {
            alert("Không thể mở file: " + path);
            return null;
        }

        var content = file.read();
        file.close();

        // loại bỏ các ký tự điều khiển ẩn (nếu có, do ExtendScript đôi khi bị)
        content = content.replace(/[\x00-\x1F]+/g, "");

        // parse JSON
        var data = JSON.parse(content);
        return data;

    } catch (e) {
        alert("Lỗi đọc hoặc parse file JSON: " + e.message);
        return null;
    }
}


function writeTextFile(path, content) {
    try {
        var f = new File(path);
        f.encoding = "UTF-8";
        if (!f.open("w")) return false;
        f.write(content);
        f.close();
        return true;
    } catch (e) {
        alert("Lỗi ghi file: " + e.message);
        return false;
    }
}

function sanitizeJSON(obj) {
    var json = JSON.stringify(obj, null, 4);
    // loại bỏ ký tự điều khiển ASCII 0–31 (trừ \t, \n, \r)
    json = json.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, "");
    return json;
}


function readLines(p, enc) {
    enc = enc || 'UTF-8';
    var f = new File(p);
    f.encoding = enc;
    if (!f.exists) return [];
    if (!f.open('r')) return [];
    var arr = [];
    while (!f.eof) arr.push(f.readln());
    f.close();
    return arr;
}

function copyFile(srcPath, destPath) {
    try {
        var src = new File(srcPath);
        if (!src.exists) return false;
        var dest = new File(destPath);
        var destFolder = new Folder(dest.parent.fsName);
        if (!destFolder.exists) destFolder.create();
        var ok = src.copy(destPath);
        return ok;
    } catch (e) {
        return false;
    }
}

function moveFile(srcPath, destPath) {
    var ok = copyFile(srcPath, destPath);
    if (ok) {
        try {
            var s = new File(srcPath);
            if (s.exists) s.remove();
        } catch (e) {}
    }
    return ok;
}

// parse text file with key=value format
function parsePathTxt(path) {
    try {
        var lines = readLines(path);
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
        alert("Lỗi đọc file text: " + e.message);
        return {};
    }
}

// serialize object to key=value format
function serializePathTxt(cfg) {
    var lines = [];
    for (var key in cfg) {
        if (cfg.hasOwnProperty(key)) {
            lines.push(key + "=" + cfg[key]);
        }
    }
    return lines.join("\n");
}

function getThisDir() {
    try {
        var f = new File($.fileName);
        return f.parent;
    } catch (e) {
        return null;
    }
}

function getRootDir() {
    var d = getThisDir();
    if (!d) return null;
    try {
        var pc = d.parent;
        var core = pc ? pc.parent : null;
        return core ? core : null;
    } catch (e) {
        return null;
    }
}

var ROOT_DIR = (function () {
    var r = getRootDir();
    if (!r) {
        log('Cannot resolve ROOT_DIR');
    }
    return r ? r.fsName : '';
})();

var DATA_DIR = (function () {
    var p = joinPath(ROOT_DIR, '/data');
    ensureFolder(p);
    return p;
})();

// ===== Step 1: getTimeline export =====
function runGetTimelineExport(cfg, projectName) {
    //add DATA_FOLDER vào path.txt, lưu lại, nếu chưa có thì tạo mới key là data_folder
    if (cfg && typeof cfg === 'object') {
        cfg['data_folder'] = joinPath(DATA_DIR, projectName);
        var pathCfg = joinPath(DATA_DIR, 'path.txt');
        pathCfg = normalizePath(pathCfg);
        writeTextFile(pathCfg, serializePathTxt(cfg));
    } else {
        log('Cảnh báo: cfg không hợp lệ để kiểm tra/thiết lập data_folder trong path.txt');
    }

    // Run getTimeline.jsx to export timeline to data/timeline_export.csv

    var p = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
    var script = joinPath(p, 'getTimeline.jsx');
    script = normalizePath(script);
    file = new File(script);
    if (!file.exists) {
        log('getTimeline.jsx not found: ' + script);
        return false;
    }
    try {
        $.writeln('[runAll] Running getTimeline.jsx...');
        $.evalFile(new File(script));
        return true;
    } catch (e) {
        log('Error getTimeline.jsx: ' + e);
        return false;
    }
}

// ===== Step 2: Merge CSV with TXT (using helper.jsx) =====
// function parseCSVLine(line) {
//     var res = [],
//         cur = '',
//         inQ = false;
//     for (var i = 0; i < line.length; i++) {
//         var ch = line.charAt(i);
//         if (inQ) {
//             if (ch === '"') {
//                 if (i + 1 < line.length && line.charAt(i + 1) === '"') {
//                     cur += '"';
//                     i++;
//                 } else {
//                     inQ = false;
//                 }
//             } else cur += ch;
//         } else {
//             if (ch === ',') {
//                 res.push(cur);
//                 cur = '';
//             } else if (ch === '"') {
//                 inQ = true;
//             } else cur += ch;
//         }
//     }
//     res.push(cur);
//     return res;
// }

// function escapeCSV(val) {
//     if (val === null || typeof val === 'undefined') return '';
//     var s = String(val);
//     var needs = /[",\n\r]/.test(s) || /^\s|\s$/.test(s);
//     return needs ? '"' + s.replace(/"/g, '""') + '"' : s;
// }

// function readCSV(path) {
//     var lines = readLines(path, 'UTF-8');
//     if (!lines.length) return { header: [], rows: [] };
//     var header = parseCSVLine(lines[0]);
//     var rows = [];
//     for (var i = 1; i < lines.length; i++) {
//         var ln = lines[i];
//         if (!ln) continue;
//         var cols = parseCSVLine(ln);
//         var obj = {};
//         for (var c = 0; c < header.length; c++) {
//             obj[header[c]] = c < cols.length ? cols[c] : '';
//         }
//         rows.push(obj);
//     }
//     return { header: header, rows: rows };
// }

// function writeCSV(path, header, rows) {
//     var parts = [header.join(',')];
//     for (var i = 0; i < rows.length; i++) {
//         var r = rows[i],
//             fields = [];
//         for (var h = 0; h < header.length; h++) {
//             fields.push(escapeCSV(r[header[h]]));
//         }
//         parts.push(fields.join(','));
//     }
//     return writeTextFile(path, parts.join('\n'));
// }

// // Load helper.jsx functions
// (function() {
//     try {
//         var helperPath = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
//         helperPath = joinPath(helperPath, 'helper.jsx');
//         if (fileExists(helperPath)) {
//             $.writeln('[runAll] Loading helper.jsx...');
//             $.evalFile(new File(helperPath));
//         } else {
//             $.writeln('[runAll] Warning: helper.jsx not found at ' + helperPath);
//         }
//     } catch (e) {
//         $.writeln('[runAll] Error loading helper.jsx: ' + e);
//     }
// })();

function mergeCsvWithTxt() {
    try {
        var helperPath = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
        helperPath = joinPath(helperPath, 'helper.jsx');
        helperPath = normalizePath(helperPath);
        file = new File(helperPath);
        if (file.exists) {
            $.writeln('[runAll] Loading helper.jsx...');
            $.evalFile(file);
            return true;
        } else {
            $.writeln('[runAll] Warning: helper.jsx not found at ' + helperPath);
            return false;
        }
    } catch (e) {
        $.writeln('[runAll] Error in mergeCsvWithTxt: ' + e);
        return false;
    }
}

// ===== Step 3: Import resources (bins per subfolder) =====
//chỉ cần chạy eval file imortResource.jsx
// --- IGNORE ---
function importMultipleFolders() {
    var p = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
    var script = joinPath(p, 'importResource.jsx');
    script = normalizePath(script);
    file = new File(script);
    if (!file.exists) {
        log('importResource.jsx not found: ' + script);
        return 0;
    }
    try {
        $.writeln('[runAll] Running importResource.jsx...');
        $.evalFile(new File(script));
        // Assume importResource.jsx sets global IMPORTED_FILE_COUNT
        var count = typeof IMPORTED_FILE_COUNT !== 'undefined' ? IMPORTED_FILE_COUNT : 0;
        return count;
    } catch (e) {
        log('Error importResource.jsx: ' + e);
        return 0;
    }
}
// --- IGNORE ---

function readPathConfig() {
    var pathTxt = joinPath(DATA_DIR, 'path.txt');
    if (!fileExists(pathTxt)) {
        log('path.txt not found: ' + pathTxt);
        return null;
    }
    return parsePathTxt(pathTxt);
}

// ===== Orchestrate =====
function runAll(projectPath) {
    var cfg = readPathConfig();
    if (!cfg) return;
    
    // Add project_path to config
    cfg['project_path'] = projectPath;
    
    projectName = projectPath.split('/').pop();
    parentPath = projectPath.substr(0, projectPath.length - projectName.length - 1); 
    projectName = projectName.replace(/\.prproj$/i, '');
    var projectSlug = (projectName && String(projectName)) || (typeof RUNALL_PROJECT_NAME !== 'undefined' && RUNALL_PROJECT_NAME) || cfg.project_slug;
    if (!projectSlug || projectSlug === '') {
        alert('Thiếu projectName/project_slug. Hãy truyền runAll(projectName) hoặc đặt trong data/path.txt');
        return;
    }
    var SUB_DIR = joinPath(DATA_DIR, projectSlug);
    ensureFolder(SUB_DIR);

    var resourceDir = parentPath + '/resource';
    if (!folderExists(resourceDir)) {
        alert('Thư mục resource không tồn tại: ' + resourceDir);
        return;
    }

    // 1) Export timeline
    if (!runGetTimelineExport(cfg, projectName)) {
        alert('Xuất timeline thất bại.');
        return;
    }
    // getTimeline.jsx auto-exports to data/timeline_export.csv -> move into project subfolder
    var mergedCsv = mergeCsvWithTxt();
    if (!mergedCsv || mergedCsv === '') {
        alert('Gộp CSV thất bại.');
        return;
    }
    $.writeln('[runAll] Merged CSV -> ' + mergedCsv);

    // 3) Import resources into bins
    var imported = importMultipleFolders(resourceDir);
    $.writeln('[runAll] Imported files: ' + imported);

    // 4) Cut & Push: evaluate cutAndPush.jsx (it auto-runs using data/timeline_export_merged.csv)
    var cpScript = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
    cpScript = joinPath(cpScript, 'cutAndPush.jsx');
    if (!fileExists(cpScript)) {
        alert('Không tìm thấy cutAndPush.jsx');
        return;
    }
    try {
        // Provide override path for cutAndPush.jsx to use project subfolder merged CSV.
        RUNALL_TIMELINE_CSV_PATH = mergedCsv;
        $.writeln('[runAll] Running cutAndPush.jsx with override path: ' + RUNALL_TIMELINE_CSV_PATH);
        $.evalFile(new File(cpScript));
    } catch (e) {
        alert('Lỗi chạy cutAndPush.jsx: ' + e);
    }
}

// Execute
runAll("C:/Users/phamp/Downloads/Copied_3638/Copied_3638/3638.prproj");
