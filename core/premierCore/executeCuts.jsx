/**
 * executeCuts.jsx
 *
 * STEP 3: Đọc cut_list.json và cắt/đổ clip vào V4 theo timeline_pos
 * - Hỗ trợ mỗi marker có N clips (multi-clip fill)
 * - Ưu tiên overwriteClip (KHÔNG push timeline)
 * - Set inPoint/outPoint đúng theo clip_start/clip_end (hoặc duration)
 *
 * YÊU CẦU:
 * - Có file: data/path.txt  (chứa data_folder=... )
 * - Có file: <data_folder>/cut_list.json
 * - Sequence đang mở trong Premiere
 */

var PERF_START = new Date().getTime();

function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[executeCuts ' + elapsed + 's] ' + msg); } catch (e) {}
}

// ============== PATH UTILITIES ==============
function normalizePath(p) {
    if (!p) return '';
    return ('' + p).replace(/\\/g, '/').replace(/\/+/g, '/');
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
function parseJSON(str) {
    try {
        return eval('(' + str + ')'); // ExtendScript ES3
    } catch (e) {
        log('ERROR parsing JSON: ' + e);
        return null;
    }
}

// ============== CONFIG ==============
var ROOT_DIR = (function () {
    try {
        // .../core/premierCore/executeCuts.jsx -> parent.parent.parent = project root
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

// ============== TICKS / TIME ==============
var TICKS_PER_SECOND = 254016000000;

function secondsToTicks(seconds) {
    // round để giảm sai số tích lũy
    return Math.round((seconds || 0) * TICKS_PER_SECOND);
}

function _setTimeTicks(timeObj, ticks) {
    // Premiere thường là Time object: timeObj.ticks
    try {
        if (timeObj && timeObj.ticks !== undefined) {
            timeObj.ticks = ticks;
            return true;
        }
    } catch (e1) {}
    // fallback: set trực tiếp string (một số bản vẫn nhận)
    try {
        timeObj = ticks.toString();
        return true;
    } catch (e2) {}
    return false;
}

function _getTimeTicks(timeObj) {
    try {
        if (timeObj && timeObj.ticks !== undefined) return timeObj.ticks;
    } catch (e) {}
    return 0;
}

// ============== PROJECT ITEMS ==============
var importedCache = {}; // normalizedPath -> ProjectItem

function findOrCreateBin(binName) {
    var rootItem = app.project.rootItem;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var item = rootItem.children[i];
        try {
            if (item && item.type === ProjectItemType.BIN && item.name === binName) {
                return item;
            }
        } catch (e) {}
    }
    log('Creating bin: ' + binName);
    return rootItem.createBin(binName);
}

function searchBin(bin, videoPathNorm) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var item = bin.children[i];
        if (!item) continue;

        // File/Clip
        try {
            if (item.type !== ProjectItemType.BIN) {
                var mp = '';
                try { mp = normalizePath(item.getMediaPath()); } catch (e1) { mp = ''; }
                if (mp && mp === videoPathNorm) return item;
            }
        } catch (e2) {}

        // Sub-bin
        try {
            if (item.type === ProjectItemType.BIN) {
                var found = searchBin(item, videoPathNorm);
                if (found) return found;
            }
        } catch (e3) {}
    }
    return null;
}

function findVideoInProject(videoPath) {
    var videoPathNorm = normalizePath(videoPath);

    if (importedCache[videoPathNorm]) return importedCache[videoPathNorm];

    var rootItem = app.project.rootItem;

    // Scan root children (ngược, ưu tiên mới)
    for (var i = rootItem.children.numItems - 1; i >= 0; i--) {
        var item = rootItem.children[i];
        if (!item) continue;

        try {
            if (item.type === ProjectItemType.BIN) {
                var found = searchBin(item, videoPathNorm);
                if (found) {
                    importedCache[videoPathNorm] = found;
                    return found;
                }
            } else {
                var mp = '';
                try { mp = normalizePath(item.getMediaPath()); } catch (e1) { mp = ''; }
                if (mp && mp === videoPathNorm) {
                    importedCache[videoPathNorm] = item;
                    return item;
                }
            }
        } catch (e2) {}
    }

    return null;
}

function importVideo(videoPath, targetBin) {
    var videoPathNorm = normalizePath(videoPath);

    if (!fileExists(videoPathNorm)) {
        log('ERROR: File not found: ' + videoPathNorm);
        return null;
    }

    try {
        var before = targetBin ? targetBin.children.numItems : 0;

        app.project.importFiles([videoPathNorm], true, targetBin, false);

        // Lấy item mới nhất trong đúng bin (an toàn hơn rootItem)
        if (targetBin && targetBin.children.numItems > before) {
            var newItem = targetBin.children[targetBin.children.numItems - 1];
            if (newItem) {
                importedCache[videoPathNorm] = newItem;
                return newItem;
            }
        }

        // Fallback: search lại
        var found = findVideoInProject(videoPathNorm);
        if (found) {
            importedCache[videoPathNorm] = found;
            return found;
        }

    } catch (e) {
        log('ERROR importing: ' + e);
    }

    return null;
}

function getOrImportVideo(videoPath, targetBin) {
    var item = findVideoInProject(videoPath);
    if (item) {
        log('    Found in project');
        return item;
    }
    log('    Importing...');
    return importVideo(videoPath, targetBin);
}

// ============== INSERT / OVERWRITE CLIP ==============
function _findInsertedClipByStartTicks(vTrack, startTicks, clipCountBefore) {
    var best = null;
    var bestDiff = 999999999;

    // scan ngược (mới) để tìm clip có start gần với startTicks
    var n = vTrack.clips.numItems;
    for (var i = n - 1; i >= 0; i--) {
        var c = vTrack.clips[i];
        if (!c || !c.start) continue;

        var st = _getTimeTicks(c.start);
        var diff = Math.abs(st - startTicks);
        if (diff < bestDiff) {
            bestDiff = diff;
            best = c;
            if (diff <= 2) break; // quá sát thì lấy luôn
        }
    }
    return best;
}

function insertClipToV4(sequence, projectItem, cut) {
    if (!sequence || !projectItem) return false;

    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks < 4) {
        log('ERROR: Need at least 4 video tracks');
        return false;
    }

    var v4 = videoTracks[3];

    try {
        // Timeline position
        var timelinePos = 0;
        if (cut.timeline_pos !== undefined && cut.timeline_pos !== null) timelinePos = cut.timeline_pos;
        else if (cut.timeline_start !== undefined && cut.timeline_start !== null) timelinePos = cut.timeline_start;

        timelinePos = Number(timelinePos) || 0;
        var timelineStartTicks = secondsToTicks(timelinePos);

        // Source in/out
        var inSec = 0;
        if (cut.clip_start !== undefined && cut.clip_start !== null) inSec = cut.clip_start;
        inSec = Number(inSec) || 0;

        var outSec = 0;
        if (cut.clip_end !== undefined && cut.clip_end !== null && Number(cut.clip_end) > inSec) {
            outSec = Number(cut.clip_end);
        } else {
            var dur = 0;
            if (cut.duration !== undefined && cut.duration !== null) dur = cut.duration;
            else if (cut.timeline_duration !== undefined && cut.timeline_duration !== null) dur = cut.timeline_duration;
            dur = Number(dur) || 5;
            if (dur < 0.05) dur = 0.05;
            outSec = inSec + dur;
        }

        var durSec = outSec - inSec;
        if (durSec < 0.05) durSec = 0.05;

        var inTicks = secondsToTicks(inSec);
        var outTicks = secondsToTicks(outSec);

        var clipCountBefore = v4.clips.numItems;

        // Ưu tiên overwriteClip để không push timeline
        if (v4.overwriteClip && typeof v4.overwriteClip === 'function') {
            v4.overwriteClip(projectItem, timelineStartTicks.toString());
        } else {
            // fallback (có thể push)
            log('WARN: overwriteClip not available, fallback to insertClip (may push timeline).');
            v4.insertClip(projectItem, timelineStartTicks.toString());
        }

        // Tìm clip vừa đặt
        var insertedClip = _findInsertedClipByStartTicks(v4, timelineStartTicks, clipCountBefore);
        if (!insertedClip) {
            log('WARN: Could not locate inserted clip at ' + timelinePos.toFixed(2) + 's');
            return true; // đã đặt rồi nhưng không trim được
        }

        // Set source in/out
        try { _setTimeTicks(insertedClip.inPoint, inTicks); } catch (e1) {}
        try { _setTimeTicks(insertedClip.outPoint, outTicks); } catch (e2) {}

        // Đồng bộ end theo duration mong muốn trên timeline
        try {
            var startT = _getTimeTicks(insertedClip.start);
            var newEndTicks = startT + secondsToTicks(durSec);
            _setTimeTicks(insertedClip.end, newEndTicks);
        } catch (e3) {}

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
        alert('ERROR: data_folder chua duoc dinh nghia trong path.txt');
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
        alert('ERROR: Khong tim thay cut_list.json\n\nHay chay workflow Python de sinh cut_list.json truoc!');
        return;
    }

    var cutListJson = readFile(cutListPath);
    var cutListData = parseJSON(cutListJson);

    if (!cutListData || !cutListData.cuts) {
        alert('ERROR: Khong doc duoc cut_list.json');
        return;
    }

    var cuts = cutListData.cuts;
    log('Loaded ' + cuts.length + ' markers');

    // Create bin for imported videos
    var importBin = findOrCreateBin('CutVideos');

    // Stats
    var successCount = 0;
    var markerSkipCount = 0;
    var clipSkipCount = 0;
    var errorCount = 0;
    var totalClips = 0;

    log('');
    log('Processing markers...');

    for (var i = 0; i < cuts.length; i++) {
        var marker = cuts[i];
        var clips = marker.clips || [];

        log('');
        log('[' + (i + 1) + '/' + cuts.length + '] "' + (marker.keyword || '') + '" (' + clips.length + ' clips)');

        if (!clips || clips.length === 0) {
            log('  SKIP MARKER: No clips for this marker');
            markerSkipCount++;
            continue;
        }

        // Sort theo timeline_pos để đảm bảo đúng thứ tự
        try {
            clips.sort(function(a, b) {
                var ta = Number(a.timeline_pos || 0);
                var tb = Number(b.timeline_pos || 0);
                return ta - tb;
            });
        } catch (eSort) {}

        for (var j = 0; j < clips.length; j++) {
            var clip = clips[j];
            totalClips++;

            var vn = clip.video_name || '';
            log('  Clip ' + (j + 1) + '/' + clips.length + ': ' + vn);

            if (!clip.video_path) {
                log('    SKIP CLIP: No video_path');
                clipSkipCount++;
                continue;
            }

            // Get or import video
            var projectItem = getOrImportVideo(clip.video_path, importBin);
            if (!projectItem) {
                log('    ERROR: Could not get/import video');
                errorCount++;
                continue;
            }

            // Insert/Overwrite to V4
            var ok = insertClipToV4(seq, projectItem, clip);
            if (ok) {
                var tp = Number(clip.timeline_pos || clip.timeline_start || 0);
                var du = Number(clip.duration || 0);
                log('    OK: ' + tp.toFixed(2) + 's (' + du.toFixed(2) + 's)');
                successCount++;
            } else {
                log('    ERROR: Insert failed');
                errorCount++;
            }
        }
    }

    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);

    log('');
    log('========================================');
    log('  HOAN THANH!');
    log('========================================');
    log('  Markers:         ' + cuts.length);
    log('  Total clips:     ' + totalClips);
    log('  Success clips:   ' + successCount);
    log('  Skipped markers: ' + markerSkipCount);
    log('  Skipped clips:   ' + clipSkipCount);
    log('  Errors:          ' + errorCount);
    log('  Time:            ' + elapsed + 's');
    log('========================================');

    // Save project
    try {
        if (successCount > 0) {
            app.project.save();
            log('Project saved');
        }
    } catch (eSave) {
        log('WARN: Save failed: ' + eSave);
    }

    alert(
        'Hoan thanh!\n\n' +
        'Markers: ' + cuts.length + '\n' +
        'Total clips: ' + totalClips + '\n' +
        'Success: ' + successCount + '\n' +
        'Skipped markers: ' + markerSkipCount + '\n' +
        'Skipped clips: ' + clipSkipCount + '\n' +
        'Errors: ' + errorCount + '\n' +
        'Time: ' + elapsed + 's'
    );
}

// Run
main();

