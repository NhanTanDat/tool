/**
 * executeCuts.jsx
 *
 * STEP 3: Doc cut_list.json va thuc hien cat
 * Do clip vao V4 theo timeline
 *
 * FIX: Pack clip SAT NHAU theo end thật (frame-accurate) -> không gap, không bị băm.
 * NEW: DISABLE + CLEAR ALL AUDIO (xóa sạch toàn bộ âm thanh)
 *
 * FIX IMPORT:
 *  - normalize path + lowercase key (Windows safe)
 *  - import by File(fsName) to ensure correct OS path
 *  - poll after import to wait Premiere indexing
 *  - resolve data_folder relative -> ROOT/data/<folder>
 *
 * FIX TIME:
 *  - Premiere hay ignore inPoint/outPoint khi overwriteClip => nó lấy từ đầu clip
 *  - Giải pháp chắc ăn: createSubClip(start,end) rồi overwrite subclip
 */

var PERF_START = new Date().getTime();
function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[executeCuts ' + elapsed + 's] ' + msg); } catch (e) {}
}

// ================= CONFIG =================
var TARGET_VIDEO_TRACK_INDEX_1BASED = 4;   // V4
var CLEAR_TARGET_TRACK_BEFORE = true;     // dọn sạch V4 trước khi chạy
var PACK_CLIPS_WITHIN_MARKER = true;      // clip sát nhau theo end thật

// AUDIO CONTROL
var DISABLE_ALL_AUDIO_TRACKS_BEFORE = true;   // khóa/mute toàn bộ audio track để tránh bị chèn audio
var CLEAR_ALL_AUDIO_AT_END = true;            // xóa sạch toàn bộ audio clips sau khi chạy
var CLEAR_ALL_AUDIO_AT_START = false;         // nếu muốn xóa audio trước khi chạy thì bật true

// ================= PATH =================
function normalizePath(p) {
    if (!p) return '';
    return String(p).replace(/\\/g, '/').replace(/\/+/g, '/');
}
function normalizeKey(p) {
    // dùng để so sánh trên Windows (case-insensitive)
    return normalizePath(p).toLowerCase();
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

// ================= ROOT + DATA =================
var ROOT_DIR = (function () {
    try { return new File($.fileName).parent.parent.parent.fsName.replace(/\\/g, '/'); }
    catch (e) { return ''; }
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
function resolveDataFolder(cfg) {
    var df = normalizePath(cfg.data_folder || cfg.project_slug || '');
    if (!df) return '';
    // absolute Windows: "C:/..."
    if (df.indexOf(':') > 0) return df;
    // absolute unix: "/..."
    if (df.indexOf('/') === 0) return df;
    // relative -> ROOT/data/<df>
    return joinPath(DATA_DIR, df);
}
function parseJSON(str) {
    try { return eval('(' + str + ')'); }
    catch (e) { log('ERROR parsing JSON: ' + e); return null; }
}

// ================= TIME / TICKS =================
var TICKS_PER_SECOND = 254016000000;

function safeNum(v, def) {
    if (v === null || v === undefined) return def;
    var n = Number(v);
    return isNaN(n) ? def : n;
}
function secondsToTicks(seconds) {
    seconds = safeNum(seconds, 0);
    return Math.round(seconds * TICKS_PER_SECOND);
}
function makeTimeFromTicks(ticks) {
    var t = new Time();
    t.ticks = String(Math.round(Number(ticks)));
    return t;
}
function makeTimeFromSeconds(sec) {
    return makeTimeFromTicks(secondsToTicks(sec));
}
function setPropTicks(obj, propName, ticks) {
    try {
        if (obj[propName] && obj[propName].ticks !== undefined) {
            obj[propName].ticks = String(Math.round(Number(ticks)));
            return true;
        }
    } catch (e) {}
    try {
        obj[propName] = String(Math.round(Number(ticks)));
        return true;
    } catch (e2) {}
    return false;
}

// ================= IMPORT =================
var importedCache = {}; // key = normalizeKey(videoPath)

function findOrCreateBin(binName) {
    var rootItem = app.project.rootItem;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.BIN && item.name === binName) return item;
    }
    log('Creating bin: ' + binName);
    return rootItem.createBin(binName);
}

function searchBin(bin, videoKey) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var item = bin.children[i];

        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            try {
                var mp = item.getMediaPath ? item.getMediaPath() : '';
                if (normalizeKey(mp) === videoKey) return item;
            } catch (e) {}
        }
        if (item.type === ProjectItemType.BIN) {
            var found = searchBin(item, videoKey);
            if (found) return found;
        }
    }
    return null;
}

function findVideoInProject(videoPath) {
    var key = normalizeKey(videoPath);
    if (importedCache[key]) return importedCache[key];

    var rootItem = app.project.rootItem;

    // scan root level
    for (var i = rootItem.children.numItems - 1; i >= 0; i--) {
        var item = rootItem.children[i];

        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            try {
                var mp = item.getMediaPath ? item.getMediaPath() : '';
                if (normalizeKey(mp) === key) {
                    importedCache[key] = item;
                    return item;
                }
            } catch (e1) {}
        }

        if (item.type === ProjectItemType.BIN) {
            var found = searchBin(item, key);
            if (found) {
                importedCache[key] = found;
                return found;
            }
        }
    }
    return null;
}

function importVideo(videoPath, targetBin) {
    var key = normalizeKey(videoPath);
    if (!fileExists(videoPath)) { log('ERROR: File not found: ' + videoPath); return null; }

    try {
        // use fsName (OS-native path) for import reliability
        var f = new File(videoPath);
        var toImport = f.fsName;

        log('Importing: ' + toImport);
        app.project.importFiles([toImport], true, targetBin, false);

        // poll to let Premiere index
        for (var k = 0; k < 30; k++) { // ~3s
            try { $.sleep(100); } catch (eS) {}
            var item = findVideoInProject(videoPath);
            if (item) {
                importedCache[key] = item;
                log('Imported OK: ' + normalizePath(item.getMediaPath ? item.getMediaPath() : videoPath));
                return item;
            }
        }
        log('WARN: Imported but not found yet (index slow): ' + videoPath);
    } catch (e2) {
        log('ERROR importing: ' + e2);
    }
    return null;
}

function getOrImportVideo(videoPath, targetBin) {
    videoPath = normalizePath(videoPath);
    var found = findVideoInProject(videoPath);
    if (found) return found;
    return importVideo(videoPath, targetBin);
}

// ================= TRACK HELPERS =================
function unlockTrackIfNeeded(track) {
    try { if (track.isLocked && track.isLocked()) track.setLocked(false); } catch (e) {}
}
function clearTrackClips(track) {
    try {
        for (var i = track.clips.numItems - 1; i >= 0; i--) {
            try { track.clips[i].remove(false, false); } catch (e1) {}
        }
    } catch (e2) {}
}
function getTrackItemMediaPath(trackItem) {
    try {
        if (trackItem && trackItem.projectItem && trackItem.projectItem.getMediaPath) {
            return normalizePath(trackItem.projectItem.getMediaPath());
        }
    } catch (e) {}
    return '';
}
function findClipByStart(track, startTicks, videoPath, toleranceTicks) {
    var videoKey = normalizeKey(videoPath);
    toleranceTicks = safeNum(toleranceTicks, secondsToTicks(0.2)); // nhỏ hơn để tránh bắt nhầm
    var best = null;
    var bestDelta = 999999999999;

    try {
        for (var i = track.clips.numItems - 1; i >= 0; i--) {
            var it = track.clips[i];
            var st = 0;
            try { st = Number(it.start.ticks); } catch (e1) { st = 0; }
            var delta = Math.abs(st - startTicks);
            if (delta <= toleranceTicks) {
                var mp = getTrackItemMediaPath(it);
                if (normalizeKey(mp) === videoKey) {
                    if (delta < bestDelta) { best = it; bestDelta = delta; }
                }
            }
        }
    } catch (e2) {}

    return best;
}

// ===== AUDIO: DISABLE TRACKS + CLEAR ALL AUDIO CLIPS =====
function disableAllAudioTracks(sequence) {
    if (!sequence || !sequence.audioTracks) return;
    var ats = sequence.audioTracks;
    log('Disabling all audio tracks (mute + lock if possible)...');
    for (var i = 0; i < ats.numTracks; i++) {
        var t = ats[i];
        try { if (t.setMute) t.setMute(true); } catch (e1) {}
        try { if (t.setLocked) t.setLocked(true); } catch (e2) {}
    }
}

function unlockAllAudioTracks(sequence) {
    if (!sequence || !sequence.audioTracks) return;
    var ats = sequence.audioTracks;
    for (var i = 0; i < ats.numTracks; i++) {
        var t = ats[i];
        try { if (t.setLocked) t.setLocked(false); } catch (e1) {}
        try { if (t.setMute) t.setMute(false); } catch (e2) {}
    }
}

function clearAllAudioClips(sequence) {
    if (!sequence || !sequence.audioTracks) return;
    log('Clearing ALL audio clips in sequence...');
    var ats = sequence.audioTracks;

    // unlock để remove được
    for (var i = 0; i < ats.numTracks; i++) {
        try { if (ats[i].setLocked) ats[i].setLocked(false); } catch (e0) {}
    }
    for (var tr = 0; tr < ats.numTracks; tr++) {
        var t = ats[tr];
        try {
            for (var j = t.clips.numItems - 1; j >= 0; j--) {
                try { t.clips[j].remove(false, false); } catch (e1) {}
            }
        } catch (e2) {}
    }
}

// ================= SUBCLIP FIX (FOR 정확 clip_start/clip_end) =================
var subclipCache = {}; // key = mediaPath|inSec|outSec

function _fmt3(n) {
    return (Math.round(Number(n) * 1000) / 1000).toFixed(3);
}
function getMediaPathSafe(projectItem) {
    try { return normalizePath(projectItem.getMediaPath ? projectItem.getMediaPath() : ''); } catch (e) {}
    return '';
}

/**
 * Tạo subclip để Premiere cắt đúng time.
 * Nếu fail -> fallback dùng original projectItem (nhưng có thể vẫn bị lấy từ đầu).
 */
function getOrCreateSubclip(baseItem, inSec, outSec) {
    if (!baseItem) return null;

    inSec = safeNum(inSec, 0);
    outSec = safeNum(outSec, inSec + 0.05);
    if (outSec <= inSec) outSec = inSec + 0.05;

    var mp = getMediaPathSafe(baseItem);
    var key = normalizeKey(mp) + '|' + _fmt3(inSec) + '|' + _fmt3(outSec);
    if (subclipCache[key]) return subclipCache[key];

    // tên đủ unique theo range
    var name = (baseItem.name || 'clip') + '_sub_' +
        _fmt3(inSec).replace('.', 'p') + '_' + _fmt3(outSec).replace('.', 'p');

    try {
        var st = makeTimeFromSeconds(inSec);
        var en = makeTimeFromSeconds(outSec);

        var hasHardBoundaries = 1;
        var takeVideo = 1;
        var takeAudio = 0; // IMPORTANT: không lấy audio

        // createSubClip(name, startTime, endTime, hasHardBoundaries, takeVideo, takeAudio)
        var sub = baseItem.createSubClip(name, st, en, hasHardBoundaries, takeVideo, takeAudio);
        if (sub) {
            subclipCache[key] = sub;
            return sub;
        }
    } catch (e) {
        log('WARN createSubClip failed: ' + e);
    }
    return null;
}

// ================= CORE: PLACE (USING SUBCLIP) =================
// return: { ok:bool, endTicks:number }
function placeAndTrim(sequence, track, projectItem, clipObj, startTicksForced) {
    if (!sequence || !track || !projectItem || !clipObj) return { ok:false, endTicks:0 };

    unlockTrackIfNeeded(track);

    var timelineStartTicks = (startTicksForced !== null && startTicksForced !== undefined)
        ? Math.round(Number(startTicksForced))
        : secondsToTicks(safeNum(clipObj.timeline_pos, safeNum(clipObj.timeline_start, 0)));

    var srcInSec  = safeNum(clipObj.clip_start, 0);
    var srcOutSec = safeNum(clipObj.clip_end, -1);
    var durSec    = safeNum(clipObj.duration, -1);

    if (srcOutSec > srcInSec) durSec = (srcOutSec - srcInSec);
    else if (durSec > 0) srcOutSec = srcInSec + durSec;
    else { durSec = 2.0; srcOutSec = srcInSec + durSec; }

    if (durSec < 0.05) { durSec = 0.05; srcOutSec = srcInSec + durSec; }

    // ✅ FIX: tạo subclip đúng đoạn cần lấy
    var subclipItem = getOrCreateSubclip(projectItem, srcInSec, srcOutSec);
    var itemToPlace = subclipItem || projectItem;

    // PLACE (overwrite -> không ripple)
    try {
        if (typeof track.overwriteClip === 'function') {
            track.overwriteClip(itemToPlace, makeTimeFromTicks(timelineStartTicks));
        } else {
            log('ERROR: overwriteClip() not available.');
            return { ok:false, endTicks:0 };
        }
    } catch (ePlace) {
        log('ERROR placing: ' + ePlace);
        return { ok:false, endTicks:0 };
    }

    // FIND inserted (by start + mediapath)
    var mp = '';
    try { mp = itemToPlace.getMediaPath ? itemToPlace.getMediaPath() : ''; } catch (eMP) {}
    var inserted = findClipByStart(track, timelineStartTicks, mp, secondsToTicks(0.2));
    if (!inserted) {
        try { inserted = track.clips[track.clips.numItems - 1]; } catch (eLast) {}
    }
    if (!inserted) return { ok:false, endTicks:0 };

    // Với subclip thì không cần set in/out nữa (Premiere hay ignore) -> chỉ lấy end thật để pack
    var realEnd = 0;
    try { realEnd = Number(inserted.end.ticks); } catch (eR) { realEnd = 0; }
    if (!realEnd || isNaN(realEnd)) realEnd = timelineStartTicks + secondsToTicks(durSec);

    return { ok:true, endTicks: realEnd };
}

// ================= SORT (ES3) =================
function sortClipsByTimelinePos(clips) {
    for (var i = 0; i < clips.length - 1; i++) {
        for (var j = i + 1; j < clips.length; j++) {
            var a = safeNum(clips[i].timeline_pos, 0);
            var b = safeNum(clips[j].timeline_pos, 0);
            if (a > b) {
                var tmp = clips[i]; clips[i] = clips[j]; clips[j] = tmp;
            }
        }
    }
    return clips;
}

// ================= MAIN =================
function main() {
    log('');
    log('========================================');
    log('  EXECUTE CUTS - STEP 3 (PACK + NO AUDIO)');
    log('========================================');

    var cfg = readPathConfig();
    if (!cfg) { alert('ERROR: Khong tim thay data/path.txt'); return; }

    var dataFolder = resolveDataFolder(cfg);
    if (!dataFolder) { alert('ERROR: data_folder chua duoc dinh nghia'); return; }
    log('Data folder: ' + dataFolder);

    var seq = app.project.activeSequence;
    if (!seq) { alert('ERROR: Khong co sequence nao dang mo!'); return; }
    log('Sequence: ' + seq.name);

    // optional clear audio before
    if (CLEAR_ALL_AUDIO_AT_START) {
        clearAllAudioClips(seq);
    }

    if (DISABLE_ALL_AUDIO_TRACKS_BEFORE) {
        disableAllAudioTracks(seq);
    }

    var targetIdx0 = TARGET_VIDEO_TRACK_INDEX_1BASED - 1;
    if (seq.videoTracks.numTracks < (targetIdx0 + 1)) {
        alert('ERROR: Sequence can co it nhat ' + TARGET_VIDEO_TRACK_INDEX_1BASED + ' video tracks.\nHien tai: ' + seq.videoTracks.numTracks);
        return;
    }

    var vTrack = seq.videoTracks[targetIdx0];
    unlockTrackIfNeeded(vTrack);

    if (CLEAR_TARGET_TRACK_BEFORE) {
        log('Clearing V' + TARGET_VIDEO_TRACK_INDEX_1BASED + '...');
        clearTrackClips(vTrack);
    }

    var cutListPath = joinPath(dataFolder, 'cut_list.json');
    if (!fileExists(cutListPath)) {
        alert('ERROR: Khong tim thay cut_list.json\n\nChay STEP 2 truoc!');
        return;
    }

    var cutListData = parseJSON(readFile(cutListPath));
    if (!cutListData || !cutListData.cuts) { alert('ERROR: Khong doc duoc cut_list.json'); return; }

    var cuts = cutListData.cuts;
    log('Loaded ' + cuts.length + ' marker(s)');

    var importBin = findOrCreateBin('CutVideos');

    var successCount = 0, errorCount = 0, skipCount = 0, totalClips = 0;

    for (var m = 0; m < cuts.length; m++) {
        var marker = cuts[m];
        var clips = marker.clips || [];
        if (!clips.length) { skipCount++; continue; }

        sortClipsByTimelinePos(clips);

        var cursorTicks = secondsToTicks(safeNum(marker.timeline_start, safeNum(clips[0].timeline_pos, 0)));

        log('');
        log('[' + (m + 1) + '/' + cuts.length + '] ' + (marker.keyword || '') + ' | clips=' + clips.length);

        for (var c = 0; c < clips.length; c++) {
            var clip = clips[c];
            totalClips++;

            if (!clip || !clip.video_path) { skipCount++; continue; }

            var vp = normalizePath(clip.video_path);
            var projectItem = getOrImportVideo(vp, importBin);
            if (!projectItem) { errorCount++; continue; }

            var startTicks = PACK_CLIPS_WITHIN_MARKER ? cursorTicks : secondsToTicks(safeNum(clip.timeline_pos, 0));

            var res = placeAndTrim(seq, vTrack, projectItem, clip, startTicks);
            if (res.ok) {
                successCount++;
                if (PACK_CLIPS_WITHIN_MARKER) cursorTicks = res.endTicks;
            } else {
                errorCount++;
            }
        }
    }

    // HARD CLEAN: remove ALL audio clips (absolute)
    if (CLEAR_ALL_AUDIO_AT_END) {
        unlockAllAudioTracks(seq);
        clearAllAudioClips(seq);
        if (DISABLE_ALL_AUDIO_TRACKS_BEFORE) disableAllAudioTracks(seq);
    }

    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);

    log('');
    log('========================================');
    log('  HOAN THANH!');
    log('========================================');
    log('  Markers:     ' + cuts.length);
    log('  Total clips: ' + totalClips);
    log('  Success:     ' + successCount);
    log('  Skipped:     ' + skipCount);
    log('  Errors:      ' + errorCount);
    log('  Time:        ' + elapsed + 's');
    log('========================================');

    if (successCount > 0) {
        try { app.project.save(); } catch (eSave) {}
    }

    alert('Hoan thanh!\n\nMarkers: ' + cuts.length + '\nClips: ' + totalClips + '\nSuccess: ' + successCount + '\nErrors: ' + errorCount + '\n\nAudio: DA XOA SACH');
}

main();
