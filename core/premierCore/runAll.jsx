/**
 * runAll.jsx (premRunner-style) - Bridge mỏng cho workflow Premiere
 *
 * Nhiệm vụ:
 *  - Đọc data/path.txt (đã được Python ghi trước).
 *  - Xác định project_slug, data_folder, timeline CSV.
 *  - Gọi importResource.jsx (import media theo path.txt).
 *  - Gọi cutAndPush.jsx với:
 *        RUNALL_TIMELINE_CSV_PATH  = đường dẫn CSV
 *        RUNALL_SEQUENCE_NAME      = tên sequence target (mặc định "Main")
 *
 * LƯU Ý:
 *  - KHÔNG app.quit() ở đây; việc đóng Premiere để Python xử lý.
 *  - Python có thể override:
 *        RUNALL_TIMELINE_CSV_PATH  (CSV khác)
 *        RUNALL_SEQUENCE_NAME      (sequence khác "Main")
 */

// ================== Config ==================
var DEFAULT_SEQUENCE_NAME = "Main"; // Sequence mặc định muốn tool đẩy clip vào

// ================== Utils ==================
function log(msg) {
    try { $.writeln('[runAll] ' + msg); } catch (e) {}
}

function joinPath(a, b) {
    if (!a || a === '') return b || '';
    if (!b || b === '') return a || '';
    var s = a.charAt(a.length - 1);
    return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

function normalizePath(p) {
    if (!p || p === '') return '';
    return p.replace(/\\/g, '/').replace(/\/+/g, '/');
}

function fileExists(p) {
    try { return (new File(p)).exists; } catch (e) { return false; }
}

function folderExists(p) {
    try { return (new Folder(p)).exists; } catch (e) { return false; }
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

// parse text file với key=value
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
        log("Lỗi đọc path.txt: " + e.message);
        return {};
    }
}

// ================== Resolve ROOT_DIR giống getTimeline/helper ==================
function getRootDir() {
    try {
        var scriptFile = new File($.fileName);      // .../core/premierCore/runAll.jsx
        var premierCoreDir = scriptFile.parent;     // premierCore
        var coreDir = premierCoreDir.parent;        // core
        var rootDir = coreDir.parent;               // project root (autotool)
        return rootDir;
    } catch (e) {
        return null;
    }
}

var ROOT_DIR = (function () {
    var r = getRootDir();
    if (!r) {
        log('Cannot resolve ROOT_DIR');
        return '';
    }
    var s = r.fsName;
    s = normalizePath(s);
    log('ROOT_DIR = ' + s);
    return s;
})();

var DATA_DIR = (function () {
    var p = joinPath(ROOT_DIR, 'data');
    ensureFolder(p);
    p = normalizePath(p);
    log('DATA_DIR = ' + p);
    return p;
})();

function readPathConfig() {
    var pathTxt = joinPath(DATA_DIR, 'path.txt');
    pathTxt = normalizePath(pathTxt);
    log('readPathConfig -> ' + pathTxt);
    if (!fileExists(pathTxt)) {
        log('path.txt not found: ' + pathTxt);
        return null;
    }
    return parsePathTxt(pathTxt);
}

// ================== Resolve CSV path ==================
function resolveTimelineCsv(cfg) {
    var projectSlug = cfg.project_slug || '';
    var dataFolder = cfg.data_folder || '';

    // Nếu cfg.data_folder đã chỉ rõ subfolder, ưu tiên luôn
    if (dataFolder && dataFolder !== '') {
        // nếu là relative path -> relative so với DATA_DIR
        if (!folderExists(dataFolder)) {
            dataFolder = normalizePath(joinPath(DATA_DIR, dataFolder));
        } else {
            dataFolder = normalizePath(dataFolder);
        }
    } else if (projectSlug && projectSlug !== '') {
        dataFolder = normalizePath(joinPath(DATA_DIR, projectSlug));
    } else {
        dataFolder = DATA_DIR;
    }

    var merged = normalizePath(joinPath(dataFolder, 'timeline_export_merged.csv'));
    if (fileExists(merged)) return merged;

    var raw = normalizePath(joinPath(dataFolder, 'timeline_export.csv'));
    if (fileExists(raw)) return raw;

    // fallback cuối cùng
    var merged2 = normalizePath(joinPath(DATA_DIR, 'timeline_export_merged.csv'));
    if (fileExists(merged2)) return merged2;

    var raw2 = normalizePath(joinPath(DATA_DIR, 'timeline_export.csv'));
    if (fileExists(raw2)) return raw2;

    return '';
}

// ================== Resolve sequence name ==================
function resolveSequenceName(cfg) {
    // 1) Python override global: RUNALL_SEQUENCE_NAME
    if (typeof RUNALL_SEQUENCE_NAME !== 'undefined' && RUNALL_SEQUENCE_NAME) {
        return RUNALL_SEQUENCE_NAME;
    }
    // 2) path.txt có khai báo sequence_name=mySeq
    if (cfg && cfg.sequence_name && cfg.sequence_name !== '') {
        return cfg.sequence_name;
    }
    // 3) Mặc định
    return DEFAULT_SEQUENCE_NAME;
}

// ================== Đảm bảo mở đúng project ==================
function ensureProjectOpened(projectPath) {
    projectPath = normalizePath(projectPath);
    var projFile = new File(projectPath);
    if (!projFile.exists) {
        alert('Project file không tồn tại: ' + projectPath);
        return false;
    }

    try {
        if (app && app.project && app.project.path) {
            var currentPath = normalizePath(app.project.path);
            if (currentPath === projectPath) {
                log('Đã mở đúng project: ' + currentPath);
                return true;
            } else {
                log('Project đang mở khác: ' + currentPath);
            }
        }
    } catch (e) {
        // ignore
    }

    // Mở đúng project theo path.txt
    log('Mở project: ' + projFile.fsName);
    try {
        app.openDocument(projFile.fsName);
        return true;
    } catch (e2) {
        alert('Không mở được project: ' + projFile.fsName + '\nError: ' + e2);
        return false;
    }
}

// ================== Gọi importResource.jsx ==================
function runImportResources() {
    var p = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
    var script = joinPath(p, 'importResource.jsx');
    script = normalizePath(script);
    var f = new File(script);
    if (!f.exists) {
        log('importResource.jsx not found: ' + script);
        return 0;
    }
    try {
        $.writeln('[runAll] Running importResource.jsx...');
        $.evalFile(f);
        var count = (typeof IMPORTED_FILE_COUNT !== 'undefined') ? IMPORTED_FILE_COUNT : 0;
        log('Imported files: ' + count);
        return count;
    } catch (e) {
        log('Error importResource.jsx: ' + e);
        return 0;
    }
}

// ================== Gọi cutAndPush.jsx ==================
function runCutAndPush(timelineCsv, sequenceName) {
    var cpScriptDir = joinPath(joinPath(ROOT_DIR, 'core'), 'premierCore');
    var cpScript = joinPath(cpScriptDir, 'cutAndPush.jsx');
    cpScript = normalizePath(cpScript);
    if (!fileExists(cpScript)) {
        alert('Không tìm thấy cutAndPush.jsx tại: ' + cpScript);
        return;
    }
    try {
        // 1) CSV path: nếu Python đã set RUNALL_TIMELINE_CSV_PATH thì ưu tiên
        if (typeof RUNALL_TIMELINE_CSV_PATH === 'undefined' || !RUNALL_TIMELINE_CSV_PATH) {
            RUNALL_TIMELINE_CSV_PATH = timelineCsv;
        }

        // 2) Sequence name: nếu Python chưa set RUNALL_SEQUENCE_NAME thì set ở đây
        if (typeof RUNALL_SEQUENCE_NAME === 'undefined' || !RUNALL_SEQUENCE_NAME) {
            RUNALL_SEQUENCE_NAME = sequenceName || DEFAULT_SEQUENCE_NAME;
        }

        $.writeln('[runAll] Using sequence name: ' + RUNALL_SEQUENCE_NAME);
        $.writeln('[runAll] Running cutAndPush.jsx với CSV: ' + RUNALL_TIMELINE_CSV_PATH);

        $.evalFile(new File(cpScript));
    } catch (e) {
        alert('Lỗi chạy cutAndPush.jsx: ' + e);
    }
}

// ================== Main ==================
function runAll() {
    var cfg = readPathConfig();
    if (!cfg) {
        alert('Không tìm thấy data/path.txt. Hãy để Python ghi path.txt trước khi gọi runAll.jsx.');
        return;
    }

    var projectPath = cfg.project_path || '';
    if (!projectPath || projectPath === '') {
        alert('Trong path.txt chưa có "project_path".');
        return;
    }
    projectPath = normalizePath(projectPath);
    log('project_path  = ' + projectPath);
    log('project_slug  = ' + (cfg.project_slug || ''));
    log('data_folder   = ' + (cfg.data_folder || ''));
    log('sequence_name = ' + (cfg.sequence_name || ''));

    // 🔴 Đảm bảo đang làm việc đúng project
    if (!ensureProjectOpened(projectPath)) {
        return;
    }

    // 1) Import resources theo path.txt
    var imported = runImportResources();
    $.writeln('[runAll] Imported files: ' + imported);

    // 2) Resolve CSV (nếu Python chưa override RUNALL_TIMELINE_CSV_PATH)
    var timelineCsv = (typeof RUNALL_TIMELINE_CSV_PATH !== 'undefined' && RUNALL_TIMELINE_CSV_PATH)
        ? RUNALL_TIMELINE_CSV_PATH
        : resolveTimelineCsv(cfg);

    if (!timelineCsv) {
        alert('Không tìm thấy timeline_export_merged.csv hoặc timeline_export.csv.');
        return;
    }
    log('Using timeline CSV: ' + timelineCsv);

    // 3) Resolve sequence name (default "Main") và run cut & push
    var seqName = resolveSequenceName(cfg);
    log('Target sequence = ' + seqName);
    runCutAndPush(timelineCsv, seqName);

    // 4) Save project, KHÔNG app.quit()
    try {
        if (app && app.project) {
            app.project.save();
            $.writeln('[runAll] Project saved.');
        } else {
            $.writeln('[runAll] app.project không tồn tại, bỏ qua save().');
        }
    } catch (e) {
        $.writeln('[runAll] Error saving project: ' + e);
    }

    $.writeln('[runAll] Done (không đóng Premiere ở đây).');
}

// Auto-execute
runAll();




