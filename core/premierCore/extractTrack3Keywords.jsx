/**
 * extractTrack3Keywords.jsx
 *
 * Đọc Track 3 (Video Track 3) từ Premiere sequence
 * Lấy text clips với nội dung keywords + timecode (start, end)
 * Export ra JSON/CSV để Python xử lý tiếp
 */

function log(msg) {
    try { $.writeln('[extractTrack3] ' + msg); } catch (e) {}
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

function writeFile(path, content) {
    var f = new File(path);
    if (!f.open('w')) {
        log('ERROR: Cannot write to ' + path);
        return false;
    }
    f.write(content);
    f.close();
    return true;
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

/**
 * Chuyển đổi Ticks (Premiere internal time) sang giây
 */
function ticksToSeconds(ticks) {
    // Premiere uses Ticks: 254016000000 ticks = 1 second
    var TICKS_PER_SECOND = 254016000000;
    return parseFloat(ticks) / TICKS_PER_SECOND;
}

/**
 * Chuyển giây thành timecode string (HH:MM:SS.mmm)
 */
function secondsToTimecode(seconds) {
    var hrs = Math.floor(seconds / 3600);
    var mins = Math.floor((seconds % 3600) / 60);
    var secs = Math.floor(seconds % 60);
    var ms = Math.floor((seconds % 1) * 1000);

    var h = (hrs < 10 ? '0' : '') + hrs;
    var m = (mins < 10 ? '0' : '') + mins;
    var s = (secs < 10 ? '0' : '') + secs;
    var mil = (ms < 10 ? '00' : (ms < 100 ? '0' : '')) + ms;

    return h + ':' + m + ':' + s + '.' + mil;
}

/**
 * Lấy text content từ clip (nếu là text/title clip)
 * Ưu tiên: Essential Graphics text > Clip name > ProjectItem name
 */
function getClipText(clipItem) {
    try {
        // Method 1: Try to get Essential Graphics text content
        // Check if this is a Motion Graphics Template (MOGRT)
        if (clipItem.projectItem && clipItem.projectItem.type === ProjectItemType.CLIP) {
            try {
                // Try to access the source text from the clip
                // For Essential Graphics, the text might be in the clip's name after user edits it
                var clipName = clipItem.name || '';

                // If clip name is NOT "Graphic" or empty, use it
                if (clipName && clipName !== 'Graphic' && clipName.length > 0) {
                    log('Using clip name: ' + clipName);
                    return clipName;
                }
            } catch (e) {
                // Continue to fallback
            }
        }

        // Method 2: Check clip name (works if user renamed the clip)
        var name = clipItem.name || '';
        if (name && name !== 'Graphic' && name.length > 0) {
            log('Using clip name: ' + name);
            return name;
        }

        // Method 3: Try projectItem name
        if (clipItem.projectItem && clipItem.projectItem.name) {
            var piName = clipItem.projectItem.name;
            if (piName && piName !== 'Graphic' && piName.length > 0) {
                log('Using projectItem name: ' + piName);
                return piName;
            }
        }

        // Method 4: Try to get text from MoGRT parameters (Advanced)
        // This requires accessing the MOGRT's text parameters
        // Unfortunately, ExtendScript API doesn't provide direct access to MOGRT text params

        // Fallback: Return "Graphic" with warning
        log('WARN: Could not extract text, clip name is default "Graphic"');
        log('      Please RENAME the clip in timeline to the keyword you want!');
        return name || 'Graphic';

    } catch (e) {
        log('ERROR in getClipText: ' + e);
        return '';
    }
}

/**
 * Đọc tất cả clips từ Track 3 (Video Track 3)
 * Track index: 0-based, nên Track 3 = index 2
 */
function extractTrack3Keywords(sequence) {
    if (!sequence) {
        log('ERROR: No sequence provided');
        return [];
    }

    var videoTracks = sequence.videoTracks;
    if (!videoTracks || videoTracks.numTracks < 3) {
        log('ERROR: Sequence không có đủ 3 video tracks');
        return [];
    }

    // Track 3 = index 2 (0-based)
    var track3 = videoTracks[2];
    log('Reading Track 3: ' + track3.name);
    log('Number of clips in Track 3: ' + track3.clips.numItems);

    var keywords = [];

    for (var i = 0; i < track3.clips.numItems; i++) {
        var clip = track3.clips[i];

        // Lấy timecode
        var startTicks = clip.start.ticks;
        var endTicks = clip.end.ticks;

        var startSec = ticksToSeconds(startTicks);
        var endSec = ticksToSeconds(endTicks);
        var durationSec = endSec - startSec;

        var startTC = secondsToTimecode(startSec);
        var endTC = secondsToTimecode(endSec);

        // Lấy text/keyword
        var keyword = getClipText(clip);

        if (!keyword || keyword.length === 0) {
            log('WARN: Clip ' + i + ' không có text, skip');
            continue;
        }

        log('Clip ' + i + ': "' + keyword + '" | ' + startTC + ' -> ' + endTC + ' (' + durationSec.toFixed(2) + 's)');

        keywords.push({
            index: i,
            keyword: keyword,
            start_seconds: startSec,
            end_seconds: endSec,
            duration_seconds: durationSec,
            start_timecode: startTC,
            end_timecode: endTC
        });
    }

    return keywords;
}

/**
 * Export keywords ra JSON
 */
function exportKeywordsToJSON(keywords, outputPath) {
    var jsonObj = {
        version: '1.0',
        count: keywords.length,
        keywords: []
    };

    for (var i = 0; i < keywords.length; i++) {
        jsonObj.keywords.push(keywords[i]);
    }

    // Manual JSON stringify (ExtendScript không có JSON.stringify)
    var jsonStr = '{\n';
    jsonStr += '  "version": "' + jsonObj.version + '",\n';
    jsonStr += '  "count": ' + jsonObj.count + ',\n';
    jsonStr += '  "keywords": [\n';

    for (var i = 0; i < keywords.length; i++) {
        var kw = keywords[i];
        jsonStr += '    {\n';
        jsonStr += '      "index": ' + kw.index + ',\n';
        jsonStr += '      "keyword": "' + kw.keyword.replace(/"/g, '\\"') + '",\n';
        jsonStr += '      "start_seconds": ' + kw.start_seconds + ',\n';
        jsonStr += '      "end_seconds": ' + kw.end_seconds + ',\n';
        jsonStr += '      "duration_seconds": ' + kw.duration_seconds + ',\n';
        jsonStr += '      "start_timecode": "' + kw.start_timecode + '",\n';
        jsonStr += '      "end_timecode": "' + kw.end_timecode + '"\n';
        jsonStr += '    }';
        if (i < keywords.length - 1) jsonStr += ',';
        jsonStr += '\n';
    }

    jsonStr += '  ]\n';
    jsonStr += '}\n';

    return writeFile(outputPath, jsonStr);
}

/**
 * Export keywords ra CSV
 */
function exportKeywordsToCSV(keywords, outputPath) {
    var csvLines = [];
    csvLines.push('index,keyword,start_seconds,end_seconds,duration_seconds,start_timecode,end_timecode');

    for (var i = 0; i < keywords.length; i++) {
        var kw = keywords[i];
        var line = kw.index + ',"' + kw.keyword.replace(/"/g, '""') + '",' +
                   kw.start_seconds + ',' + kw.end_seconds + ',' + kw.duration_seconds + ',' +
                   '"' + kw.start_timecode + '","' + kw.end_timecode + '"';
        csvLines.push(line);
    }

    var csvContent = csvLines.join('\n');
    return writeFile(outputPath, csvContent);
}

/**
 * Main function
 */
function main() {
    log('=== START EXTRACT TRACK 3 KEYWORDS ===');

    // Đọc config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Không tìm thấy data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    var seqName = cfg.sequence_name || 'Main';

    if (!dataFolder) {
        alert('ERROR: data_folder không được định nghĩa trong path.txt');
        return;
    }

    log('Data folder: ' + dataFolder);
    log('Sequence name: ' + seqName);

    // Lấy active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Không có sequence nào được mở.\nHãy mở sequence trước khi chạy script.');
        return;
    }

    log('Active sequence: ' + seq.name);

    // Extract keywords từ Track 3
    var keywords = extractTrack3Keywords(seq);

    if (keywords.length === 0) {
        alert('WARNING: Không tìm thấy keywords nào trong Track 3');
        return;
    }

    log('Found ' + keywords.length + ' keywords');

    // Export ra JSON
    var jsonPath = joinPath(dataFolder, 'track3_keywords.json');
    if (exportKeywordsToJSON(keywords, jsonPath)) {
        log('Exported JSON: ' + jsonPath);
    } else {
        log('ERROR: Failed to export JSON');
    }

    // Export ra CSV
    var csvPath = joinPath(dataFolder, 'track3_keywords.csv');
    if (exportKeywordsToCSV(keywords, csvPath)) {
        log('Exported CSV: ' + csvPath);
    } else {
        log('ERROR: Failed to export CSV');
    }

    log('=== DONE ===');
    alert('Đã export ' + keywords.length + ' keywords từ Track 3\n\nJSON: ' + jsonPath + '\nCSV: ' + csvPath);
}

// Run
main();
