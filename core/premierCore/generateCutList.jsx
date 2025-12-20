/**
 * generateCutList.jsx
 *
 * STEP 2: Doc markers.json + Tim video matching
 * Tao cut_list.json de step 3 thuc hien cat
 *
 * Logic: Tim video trong resource folder co ten trung voi keyword
 */

function log(msg) {
    try { $.writeln('[generateCutList] ' + msg); } catch (e) {}
}

// ============== PATH UTILITIES ==============
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

function readFile(p) {
    var f = new File(p);
    f.encoding = 'UTF-8';
    if (!f.exists || !f.open('r')) return '';
    var content = f.read();
    f.close();
    return content;
}

function writeFile(path, content) {
    var f = new File(path);
    f.encoding = 'UTF-8';
    if (!f.open('w')) {
        log('ERROR: Cannot write to ' + path);
        return false;
    }
    f.write(content);
    f.close();
    log('Saved: ' + path);
    return true;
}

// ============== CONFIG ==============
var ROOT_DIR = (function () {
    try {
        return new File($.fileName).parent.parent.parent.fsName.replace(/\\/g, '/');
    } catch (e) { return ''; }
})();

var DATA_DIR = joinPath(ROOT_DIR, 'data');

function readPathConfig() {
    var pathTxt = joinPath(DATA_DIR, 'path.txt');
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

// ============== PARSE JSON ==============
function parseJSON(str) {
    try {
        return eval('(' + str + ')');
    } catch (e) {
        log('ERROR parsing JSON: ' + e);
        return null;
    }
}

// ============== GET VIDEO FILES ==============
function getVideoFiles(folderPath) {
    var videos = [];
    var folder = new Folder(folderPath);

    if (!folder.exists) {
        log('ERROR: Folder not found: ' + folderPath);
        return videos;
    }

    var extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.webm', '*.MP4', '*.MOV', '*.AVI'];

    for (var e = 0; e < extensions.length; e++) {
        var files = folder.getFiles(extensions[e]);
        for (var f = 0; f < files.length; f++) {
            var fileName = files[f].name;
            var nameNoExt = fileName.replace(/\.[^.]+$/, '');
            videos.push({
                path: normalizePath(files[f].fsName),
                name: fileName,
                nameNoExt: nameNoExt,
                nameLower: nameNoExt.toLowerCase()
            });
        }
    }

    log('Found ' + videos.length + ' videos in: ' + folderPath);
    return videos;
}

// ============== MATCH VIDEO ==============
function findVideoForKeyword(keyword, videoFiles) {
    var kw = keyword.toLowerCase().replace(/^\s+|\s+$/g, '');

    // 1. Exact match
    for (var i = 0; i < videoFiles.length; i++) {
        if (videoFiles[i].nameLower === kw) {
            log('  Match (exact): ' + videoFiles[i].name);
            return videoFiles[i];
        }
    }

    // 2. Keyword in filename
    for (var j = 0; j < videoFiles.length; j++) {
        if (videoFiles[j].nameLower.indexOf(kw) !== -1) {
            log('  Match (contains): ' + videoFiles[j].name);
            return videoFiles[j];
        }
    }

    // 3. Filename in keyword
    for (var k = 0; k < videoFiles.length; k++) {
        if (kw.indexOf(videoFiles[k].nameLower) !== -1) {
            log('  Match (reverse): ' + videoFiles[k].name);
            return videoFiles[k];
        }
    }

    log('  No match for: ' + keyword);
    return null;
}

// ============== GENERATE CUT LIST ==============
function escapeJSON(s) {
    if (!s) return '';
    return String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r');
}

function safeNumber(v) {
    var n = parseFloat(v);
    if (isNaN(n) || !isFinite(n)) return 0;
    return n;
}

function generateCutList(markers, videoFiles, outputPath) {
    var cuts = [];

    log('');
    log('Generating cut list...');

    for (var i = 0; i < markers.length; i++) {
        var m = markers[i];
        log('[' + (i + 1) + '/' + markers.length + '] "' + m.keyword + '"');

        var video = findVideoForKeyword(m.keyword, videoFiles);

        if (video) {
            cuts.push({
                index: m.index,
                keyword: m.keyword,
                video_path: video.path,
                video_name: video.name,
                timeline_start: m.start_seconds,
                timeline_end: m.end_seconds,
                timeline_duration: m.duration_seconds,
                clip_start: 0,  // Start from beginning of video
                clip_end: m.duration_seconds  // Use marker duration
            });
        } else {
            cuts.push({
                index: m.index,
                keyword: m.keyword,
                video_path: '',
                video_name: 'NOT_FOUND',
                timeline_start: m.start_seconds,
                timeline_end: m.end_seconds,
                timeline_duration: m.duration_seconds,
                clip_start: 0,
                clip_end: 0,
                error: 'No matching video'
            });
        }
    }

    // Build JSON
    var lines = [];
    lines.push('{');
    lines.push('  "count": ' + cuts.length + ',');
    lines.push('  "matched": ' + cuts.filter(function(c) { return c.video_path; }).length + ',');
    lines.push('  "cuts": [');

    for (var j = 0; j < cuts.length; j++) {
        var c = cuts[j];
        var obj = [];
        obj.push('    {');
        obj.push('      "index": ' + safeNumber(c.index) + ',');
        obj.push('      "keyword": "' + escapeJSON(c.keyword) + '",');
        obj.push('      "video_path": "' + escapeJSON(c.video_path) + '",');
        obj.push('      "video_name": "' + escapeJSON(c.video_name) + '",');
        obj.push('      "timeline_start": ' + safeNumber(c.timeline_start) + ',');
        obj.push('      "timeline_end": ' + safeNumber(c.timeline_end) + ',');
        obj.push('      "timeline_duration": ' + safeNumber(c.timeline_duration) + ',');
        obj.push('      "clip_start": ' + safeNumber(c.clip_start) + ',');
        obj.push('      "clip_end": ' + safeNumber(c.clip_end));
        if (c.error) {
            obj[obj.length - 1] += ',';
            obj.push('      "error": "' + escapeJSON(c.error) + '"');
        }
        obj.push('    }' + (j < cuts.length - 1 ? ',' : ''));
        lines.push(obj.join('\n'));
    }

    lines.push('  ]');
    lines.push('}');

    return writeFile(outputPath, lines.join('\n'));
}

// ============== MAIN ==============
function main() {
    log('');
    log('========================================');
    log('  GENERATE CUT LIST - STEP 2');
    log('========================================');

    // Get config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Khong tim thay data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    var resourceFolder = normalizePath(cfg.resource_folder || '');

    if (!dataFolder) {
        alert('ERROR: data_folder chua duoc dinh nghia');
        return;
    }

    if (!resourceFolder) {
        alert('ERROR: resource_folder chua duoc dinh nghia');
        return;
    }

    log('Data folder: ' + dataFolder);
    log('Resource folder: ' + resourceFolder);

    // Read markers.json
    var markersPath = joinPath(dataFolder, 'markers.json');
    if (!fileExists(markersPath)) {
        alert('ERROR: Khong tim thay markers.json\n\nChay STEP 1 (readMarkers.jsx) truoc!');
        return;
    }

    var markersJson = readFile(markersPath);
    var markersData = parseJSON(markersJson);

    if (!markersData || !markersData.markers) {
        alert('ERROR: Khong doc duoc markers.json');
        return;
    }

    var markers = markersData.markers;
    log('Loaded ' + markers.length + ' markers');

    // Get video files
    var videoFiles = getVideoFiles(resourceFolder);

    if (videoFiles.length === 0) {
        alert('ERROR: Khong tim thay video nao trong:\n' + resourceFolder);
        return;
    }

    // Generate cut list
    var cutListPath = joinPath(dataFolder, 'cut_list.json');
    var success = generateCutList(markers, videoFiles, cutListPath);

    if (success) {
        var matched = 0;
        for (var i = 0; i < markers.length; i++) {
            if (findVideoForKeyword(markers[i].keyword, videoFiles)) matched++;
        }

        log('');
        log('========================================');
        log('  HOAN THANH!');
        log('  Markers: ' + markers.length);
        log('  Matched: ' + matched);
        log('  -> cut_list.json');
        log('========================================');

        alert('Da tao cut list!\n\nMarkers: ' + markers.length + '\nMatched: ' + matched + '\n\nFile: ' + cutListPath);
    } else {
        alert('ERROR: Khong the ghi cut_list.json');
    }
}

// Run
main();
