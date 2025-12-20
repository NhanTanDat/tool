/**
 * readMarkers.jsx
 *
 * STEP 1: Doc markers tu timeline dang mo
 * Xuat ra file JSON don gian
 *
 * Premiere Pro 2022+ compatible
 */

function log(msg) {
    try { $.writeln('[readMarkers] ' + msg); } catch (e) {}
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

// Write file WITHOUT BOM (clean JSON)
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

// ============== TICKS CONVERSION ==============
var TICKS_PER_SECOND = 254016000000;

function ticksToSeconds(ticks) {
    return parseFloat(ticks) / TICKS_PER_SECOND;
}

function secondsToTimecode(seconds) {
    var hrs = Math.floor(seconds / 3600);
    var mins = Math.floor((seconds % 3600) / 60);
    var secs = Math.floor(seconds % 60);
    var ms = Math.floor((seconds % 1) * 1000);

    function pad(n, len) {
        var s = String(n);
        while (s.length < len) s = '0' + s;
        return s;
    }

    return pad(hrs, 2) + ':' + pad(mins, 2) + ':' + pad(secs, 2) + '.' + pad(ms, 3);
}

// ============== READ MARKERS ==============
function getMarkersFromSequence(sequence) {
    var results = [];

    if (!sequence) {
        log('ERROR: No sequence');
        return results;
    }

    var markers = sequence.markers;
    if (!markers) {
        log('ERROR: No markers object');
        return results;
    }

    log('Sequence: ' + sequence.name);
    log('Reading markers...');

    // Try multiple methods to access markers
    var markerList = [];

    // Method 1: numMarkers (Premiere 2022+)
    if (typeof markers.numMarkers !== 'undefined') {
        log('Method: numMarkers = ' + markers.numMarkers);
        for (var i = 0; i < markers.numMarkers; i++) {
            try {
                var m = markers[i];
                if (m) markerList.push(m);
            } catch (e) {}
        }
    }

    // Method 2: Iteration fallback
    if (markerList.length === 0) {
        log('Method: iteration');
        for (var j = 0; j < 200; j++) {
            try {
                var m2 = markers[j];
                if (!m2) break;
                markerList.push(m2);
            } catch (e) {
                break;
            }
        }
    }

    log('Found ' + markerList.length + ' markers');

    // Process each marker
    for (var k = 0; k < markerList.length; k++) {
        var marker = markerList[k];
        var data = extractMarkerData(marker, k);
        if (data) {
            results.push(data);
        }
    }

    return results;
}

function extractMarkerData(marker, index) {
    if (!marker) return null;

    try {
        // Get name/comment
        var keyword = '';
        if (marker.name) keyword = marker.name;
        else if (marker.comments) keyword = marker.comments;

        keyword = String(keyword).replace(/^\s+|\s+$/g, '');

        if (!keyword) {
            log('  Marker ' + index + ': empty, skip');
            return null;
        }

        // Get timing
        var startTicks = 0;
        var endTicks = 0;

        if (marker.start && marker.start.ticks) {
            startTicks = marker.start.ticks;
        } else if (typeof marker.start === 'object' && marker.start.seconds) {
            startTicks = marker.start.seconds * TICKS_PER_SECOND;
        }

        if (marker.end && marker.end.ticks) {
            endTicks = marker.end.ticks;
        } else if (typeof marker.end === 'object' && marker.end.seconds) {
            endTicks = marker.end.seconds * TICKS_PER_SECOND;
        }

        var startSec = ticksToSeconds(startTicks);
        var endSec = ticksToSeconds(endTicks);

        // Default duration if marker has no end
        if (endSec <= startSec) {
            endSec = startSec + 5.0;
        }

        var durationSec = endSec - startSec;

        log('  [' + index + '] "' + keyword + '" @ ' + secondsToTimecode(startSec) + ' (' + durationSec.toFixed(2) + 's)');

        return {
            index: index,
            keyword: keyword,
            start_seconds: startSec,
            end_seconds: endSec,
            duration_seconds: durationSec,
            start_timecode: secondsToTimecode(startSec),
            end_timecode: secondsToTimecode(endSec)
        };

    } catch (e) {
        log('  ERROR marker ' + index + ': ' + e);
        return null;
    }
}

// ============== EXPORT JSON ==============
function escapeJSON(s) {
    if (!s) return '';
    return String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r')
        .replace(/\t/g, '\\t');
}

function safeNumber(v) {
    if (typeof v === 'undefined' || v === null) return 0;
    var n = parseFloat(v);
    if (isNaN(n) || !isFinite(n)) return 0;
    return n;
}

function exportToJSON(markers, outputPath) {
    var lines = [];
    lines.push('{');
    lines.push('  "count": ' + markers.length + ',');
    lines.push('  "markers": [');

    for (var i = 0; i < markers.length; i++) {
        var m = markers[i];
        var obj = [];
        obj.push('    {');
        obj.push('      "index": ' + safeNumber(m.index) + ',');
        obj.push('      "keyword": "' + escapeJSON(m.keyword) + '",');
        obj.push('      "start_seconds": ' + safeNumber(m.start_seconds) + ',');
        obj.push('      "end_seconds": ' + safeNumber(m.end_seconds) + ',');
        obj.push('      "duration_seconds": ' + safeNumber(m.duration_seconds) + ',');
        obj.push('      "start_timecode": "' + escapeJSON(m.start_timecode) + '",');
        obj.push('      "end_timecode": "' + escapeJSON(m.end_timecode) + '"');
        obj.push('    }' + (i < markers.length - 1 ? ',' : ''));
        lines.push(obj.join('\n'));
    }

    lines.push('  ]');
    lines.push('}');

    var json = lines.join('\n');
    return writeFile(outputPath, json);
}

// ============== MAIN ==============
function main() {
    log('');
    log('========================================');
    log('  READ MARKERS - STEP 1');
    log('========================================');

    // Get config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Khong tim thay data/path.txt\n\nChay workflow tu GUI truoc!');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    if (!dataFolder) {
        alert('ERROR: data_folder chua duoc dinh nghia');
        return;
    }

    log('Data folder: ' + dataFolder);

    // Get active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Khong co sequence nao dang mo!\n\nHay mo sequence truoc khi chay script.');
        return;
    }

    // Read markers
    var markers = getMarkersFromSequence(seq);

    if (markers.length === 0) {
        log('');
        log('KHONG TIM THAY MARKER!');
        log('');
        log('Huong dan tao Sequence Marker:');
        log('1. Click vao vung trong tren timeline (bo chon clips)');
        log('2. Di chuyen playhead den vi tri can danh dau');
        log('3. Nhan phim M');
        log('4. Double-click vao marker (icon mau vang)');
        log('5. Nhap keyword vao truong Name');
        log('');
        alert('Khong tim thay marker nao!\n\nXem console de biet huong dan tao marker.');
        return;
    }

    // Export JSON
    var outputPath = joinPath(dataFolder, 'markers.json');
    var success = exportToJSON(markers, outputPath);

    if (success) {
        log('');
        log('========================================');
        log('  HOAN THANH!');
        log('  ' + markers.length + ' markers -> markers.json');
        log('========================================');
        alert('Da doc ' + markers.length + ' markers!\n\nFile: ' + outputPath);
    } else {
        alert('ERROR: Khong the ghi file JSON');
    }
}

// Run
main();
