/**
 * executeCuts.jsx
 *
 * STEP 3: Doc cut_list.json va thuc hien cat
 * Do clip vao V4 theo timeline da dinh nghia
 *
 * CHAY RIENG - Khong phu thuoc step 1, 2
 */

var PERF_START = new Date().getTime();

function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[executeCuts ' + elapsed + 's] ' + msg); } catch (e) {}
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

function parseJSON(str) {
    try {
        return eval('(' + str + ')');
    } catch (e) {
        log('ERROR parsing JSON: ' + e);
        return null;
    }
}

// ============== TICKS ==============
var TICKS_PER_SECOND = 254016000000;

function secondsToTicks(seconds) {
    return Math.floor(seconds * TICKS_PER_SECOND);
}

// ============== PROJECT ITEMS ==============
var importedCache = {};

function findOrCreateBin(binName) {
    var rootItem = app.project.rootItem;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.BIN && item.name === binName) {
            return item;
        }
    }
    log('Creating bin: ' + binName);
    return rootItem.createBin(binName);
}

function findVideoInProject(videoPath) {
    videoPath = normalizePath(videoPath);

    // Check cache
    if (importedCache[videoPath]) {
        return importedCache[videoPath];
    }

    var rootItem = app.project.rootItem;

    // Search from end (newly imported items)
    for (var i = rootItem.children.numItems - 1; i >= 0; i--) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                importedCache[videoPath] = item;
                return item;
            }
        }
        // Search in bins
        if (item.type === ProjectItemType.BIN) {
            var found = searchBin(item, videoPath);
            if (found) {
                importedCache[videoPath] = found;
                return found;
            }
        }
    }

    return null;
}

function searchBin(bin, videoPath) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var item = bin.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                return item;
            }
        }
        if (item.type === ProjectItemType.BIN) {
            var found = searchBin(item, videoPath);
            if (found) return found;
        }
    }
    return null;
}

function importVideo(videoPath, targetBin) {
    videoPath = normalizePath(videoPath);

    if (!fileExists(videoPath)) {
        log('ERROR: File not found: ' + videoPath);
        return null;
    }

    try {
        app.project.importFiles([videoPath], true, targetBin, false);
        // Get the newly imported item
        var rootItem = app.project.rootItem;
        var newItem = rootItem.children[rootItem.children.numItems - 1];
        if (newItem) {
            importedCache[videoPath] = newItem;
            return newItem;
        }
    } catch (e) {
        log('ERROR importing: ' + e);
    }

    return null;
}

function getOrImportVideo(videoPath, targetBin) {
    var item = findVideoInProject(videoPath);
    if (item) {
        log('  Found in project');
        return item;
    }

    log('  Importing...');
    return importVideo(videoPath, targetBin);
}

// ============== INSERT CLIP ==============
function insertClipToV4(sequence, projectItem, cut) {
    if (!sequence || !projectItem) {
        return false;
    }

    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks < 4) {
        log('ERROR: Need at least 4 video tracks');
        return false;
    }

    var v4 = videoTracks[3];
    var clipCountBefore = v4.clips.numItems;

    try {
        // Timeline position (where to place on V4)
        var timelineStartTicks = secondsToTicks(cut.timeline_start);

        // Source in/out points (which segment of the video to use)
        var clipStartSec = cut.clip_start || 0;
        var timelineDuration = cut.timeline_duration || 5;

        var clipStartTicks = secondsToTicks(clipStartSec);

        log('    Timeline pos: ' + cut.timeline_start.toFixed(2) + 's');
        log('    Source start: ' + clipStartSec.toFixed(2) + 's');
        log('    Duration: ' + timelineDuration.toFixed(2) + 's (full marker)');

        // Use insertClip with ticks as string (more compatible)
        var inserted = v4.insertClip(projectItem, timelineStartTicks.toString());

        // Get the inserted clip (should be the last one added)
        if (v4.clips.numItems > clipCountBefore) {
            var insertedClip = v4.clips[v4.clips.numItems - 1];

            // Set source IN point using ticks string
            insertedClip.inPoint = clipStartTicks.toString();

            // Set clip END on timeline to fill FULL marker duration
            var newEndTicks = insertedClip.start.ticks + secondsToTicks(timelineDuration);
            insertedClip.end = newEndTicks.toString();

            log('    Clip placed: ' + (insertedClip.start.ticks / TICKS_PER_SECOND).toFixed(2) + 's - ' +
                (insertedClip.end.ticks / TICKS_PER_SECOND).toFixed(2) + 's');
        }

        return true;

    } catch (e) {
        log('ERROR inserting clip: ' + e);
        return false;
    }
}

// ============== MAIN ==============
function main() {
    log('');
    log('========================================');
    log('  EXECUTE CUTS - STEP 3');
    log('========================================');

    // Get config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Khong tim thay data/path.txt');
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
        alert('ERROR: Khong co sequence nao dang mo!');
        return;
    }

    log('Sequence: ' + seq.name);

    // Check V4
    if (seq.videoTracks.numTracks < 4) {
        alert('ERROR: Sequence can co it nhat 4 video tracks.\nHien tai: ' + seq.videoTracks.numTracks);
        return;
    }

    // Read cut_list.json
    var cutListPath = joinPath(dataFolder, 'cut_list.json');
    if (!fileExists(cutListPath)) {
        alert('ERROR: Khong tim thay cut_list.json\n\nChay STEP 2 (generateCutList.jsx) truoc!');
        return;
    }

    var cutListJson = readFile(cutListPath);
    var cutListData = parseJSON(cutListJson);

    if (!cutListData || !cutListData.cuts) {
        alert('ERROR: Khong doc duoc cut_list.json');
        return;
    }

    var cuts = cutListData.cuts;
    log('Loaded ' + cuts.length + ' cuts');

    // Create bin for imported videos
    var importBin = findOrCreateBin('CutVideos');

    // Process cuts
    var successCount = 0;
    var skipCount = 0;
    var errorCount = 0;

    log('');
    log('Processing cuts...');

    for (var i = 0; i < cuts.length; i++) {
        var cut = cuts[i];
        log('');
        log('[' + (i + 1) + '/' + cuts.length + '] "' + cut.keyword + '"');

        // Skip if no video
        if (!cut.video_path || cut.video_path === '') {
            log('  SKIP: No video matched');
            skipCount++;
            continue;
        }

        // Get or import video
        var projectItem = getOrImportVideo(cut.video_path, importBin);

        if (!projectItem) {
            log('  ERROR: Could not get video');
            errorCount++;
            continue;
        }

        // Insert to V4
        var success = insertClipToV4(seq, projectItem, cut);

        if (success) {
            log('  OK: Inserted at ' + cut.timeline_start.toFixed(2) + 's');
            successCount++;
        } else {
            log('  ERROR: Insert failed');
            errorCount++;
        }
    }

    // Summary
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);

    log('');
    log('========================================');
    log('  HOAN THANH!');
    log('========================================');
    log('  Total:   ' + cuts.length);
    log('  Success: ' + successCount);
    log('  Skipped: ' + skipCount);
    log('  Errors:  ' + errorCount);
    log('  Time:    ' + elapsed + 's');
    log('========================================');

    // Save project
    if (successCount > 0) {
        app.project.save();
        log('Project saved');
    }

    alert('Hoan thanh!\n\nTotal: ' + cuts.length + '\nSuccess: ' + successCount + '\nSkipped: ' + skipCount + '\nErrors: ' + errorCount);
}

// Run
main();
