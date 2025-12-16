/**
 * runAll.jsx (ES3 Safe - Sync with cutAndPush)
 */

function log(msg) {
    try { $.writeln('[runAll] ' + msg); } catch (e) {}
}

function normalizePath(p) {
    if (!p) return '';
    return p.replace(/\\/g, '/').replace(/\/+/g, '/');
}

function joinPath(a, b) {
    if (!a) return b || '';
    
    if (!b) return a || '';
    var s = a.charAt(a.length - 1);
    return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

function fileExists(p) {
    try { return (new File(p)).exists; } catch (e) { return false; }
}

function readLines(p) {
    var f = new File(p);
    if (!f.exists || !f.open('r')) return [];
    var arr = [];
    while (!f.eof) arr.push(f.readln());
    f.close();
    return arr;
}

var ROOT_DIR = (function () {
    try {
        return new File($.fileName).parent.parent.parent.fsName.replace(/\\/g, '/');
    } catch (e) { return ''; }
})();

var DATA_DIR = joinPath(ROOT_DIR, 'data');

function readPathConfig() {
    var pathTxt = joinPath(DATA_DIR, 'path.txt');
    log('Reading config: ' + pathTxt);
    if (!fileExists(pathTxt)) return null;

    var lines = readLines(pathTxt);
    var cfg = {};
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (!line) continue;
        var parts = line.split('=');
        if (parts.length >= 2) {
            var key = parts[0].replace(/^\s+|\s+$/g, ''); 
            var val = parts.slice(1).join('=').replace(/^\s+|\s+$/g, '');
            cfg[key] = val;
        }
    }
    return cfg;
}

function runAll() {
    var cfg = readPathConfig();
    if (!cfg) {
        alert('LOI: Khong tim thay data/path.txt');
        return;
    }

    var projectPath = normalizePath(cfg.project_path || '');
    var dataFolder  = normalizePath(cfg.data_folder || '');
    var seqName     = cfg.sequence_name || "Main";

    if (projectPath && fileExists(projectPath)) {
        if (app.project.path && normalizePath(app.project.path) !== projectPath) {
            log('Opening project: ' + projectPath);
            app.openDocument(projectPath);
        } else {
            log('Project already opened.');
        }
    } else {
        alert('Loi: Duong dan Project sai: ' + projectPath);
        return;
    }

    var importScript = joinPath(ROOT_DIR, 'core/premierCore/importResource.jsx');
    if (fileExists(importScript)) {
        try {
            $.writeln('[runAll] Running importResource...');
            $.evalFile(new File(importScript));
        } catch(e) {
            log('Import Error: ' + e);
        }
    }

    var csvPath = joinPath(dataFolder, 'timeline_export_merged.csv');
    if (!fileExists(csvPath)) {
        csvPath = joinPath(dataFolder, 'timeline_export.csv');
    }

    if (!fileExists(csvPath)) {
        alert('LOI: Khong tim thay CSV tai ' + dataFolder);
        return;
    }

    log('TARGET CSV: ' + csvPath);

    RUNALL_TIMELINE_CSV_PATH = csvPath;
    RUNALL_SEQUENCE_NAME = seqName;

    var cutScript = joinPath(ROOT_DIR, 'core/premierCore/cutAndPush.jsx');
    if (fileExists(cutScript)) {
        try {
            $.writeln('[runAll] Executing cutAndPush...');
            $.evalFile(new File(cutScript));
        } catch(e) {
            alert('Loi cutAndPush: ' + e);
            
        }
    } else {
        alert('Khong tim thay cutAndPush.jsx');
    }

    if (app.project) {
        app.project.save();
        log('Project Saved.');
    }
    
    
    
    
    log('DONE.');
}

runAll();


