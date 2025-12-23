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
 *
 * NEW (MIX):
 *  - Trộn clip trong cùng keyword theo round-robin giữa nhiều video
 *  - Tránh 2 clip liên tiếp cùng video (nếu còn video khác để chọn)
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

// ================= MIX CONFIG (TRỘN TRONG 1 KEY) =================
var MIX_WITHIN_KEYWORD = true;                 // ✅ bật để TRỘN clip trong cùng keyword
var MIX_AVOID_SAME_VIDEO_CONSECUTIVE = true;   // ✅ tránh 2 clip liên tiếp cùng video (nếu còn video khác)
var MIX_SHUFFLE_VIDEO_ORDER = false;           // shuffle thứ tự video trong keyword (tự nhiên hơn)
var MIX_PER_VIDEO_LIMIT = 0;                   // giới hạn số clip mỗi video trong keyword (0 = không giới hạn)
var MIX_MAX_CLIPS_PER_KEYWORD = 0;             // giới hạn tổng clip trong keyword (0 = không giới hạn)

// Nếu keyword xuất hiện nhiều markers: gộp lại thành 1 keyword rồi mới trộn
var MERGE_MARKERS_SAME_KEYWORD = false;        // ✅ nếu muốn "1 keyword = 1 block" thì bật true
// Nếu MERGE true: pack keyword blocks liên tục 1 dòng (bỏ timeline_start gốc)
var PACK_KEYWORD_BLOCKS_SEQUENTIALLY = false;  // bật true nếu muốn keyword nối tiếp nhau thành 1 video

// ================= PATH =================
function normalizePath(p) {
    if (!p) return '';
    return String(p).replace(/\\/g, '/').replace(/\/+/g, '/');
}
function normalizeKey(p) {
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
    if (df.indexOf(':') > 0) return df;      // absolute Windows
    if (df.indexOf('/') === 0) return df;    // absolute unix
    return joinPath(DATA_DIR, df);           // relative
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
        var f = new File(videoPath);
        var toImport = f.fsName;

        log('Importing: ' + toImport);
        app.project.importFiles([toImport], true, targetBin, false);

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
    toleranceTicks = safeNum(toleranceTicks, secondsToTicks(0.2));
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

// ================= SUBCLIP FIX =================
var subclipCache = {}; // key = mediaPath|inSec|outSec

function _fmt3(n) {
    return (Math.round(Number(n) * 1000) / 1000).toFixed(3);
}
function getMediaPathSafe(projectItem) {
    try { return normalizePath(projectItem.getMediaPath ? projectItem.getMediaPath() : ''); } catch (e) {}
    return '';
}
function getOrCreateSubclip(baseItem, inSec, outSec) {
    if (!baseItem) return null;

    inSec = safeNum(inSec, 0);
    outSec = safeNum(outSec, inSec + 0.05);
    if (outSec <= inSec) outSec = inSec + 0.05;

    var mp = getMediaPathSafe(baseItem);
    var key = normalizeKey(mp) + '|' + _fmt3(inSec) + '|' + _fmt3(outSec);
    if (subclipCache[key]) return subclipCache[key];

    var name = (baseItem.name || 'clip') + '_sub_' +
        _fmt3(inSec).replace('.', 'p') + '_' + _fmt3(outSec).replace('.', 'p');

    try {
        var st = makeTimeFromSeconds(inSec);
        var en = makeTimeFromSeconds(outSec);

        var hasHardBoundaries = 1;
        var takeVideo = 1;
        var takeAudio = 0;

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

    var subclipItem = getOrCreateSubclip(projectItem, srcInSec, srcOutSec);
    var itemToPlace = subclipItem || projectItem;

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

    var mp = '';
    try { mp = itemToPlace.getMediaPath ? itemToPlace.getMediaPath() : ''; } catch (eMP) {}
    var inserted = findClipByStart(track, timelineStartTicks, mp, secondsToTicks(0.2));
    if (!inserted) {
        try { inserted = track.clips[track.clips.numItems - 1]; } catch (eLast) {}
    }
    if (!inserted) return { ok:false, endTicks:0 };

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

// ================= MIX HELPERS =================
function _trimStr(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/^\s+|\s+$/g, '');
}
function _hashSeed(str) {
    // FNV-1a 32-bit
    str = String(str || '');
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) {
        h ^= str.charCodeAt(i);
        // h *= 16777619 (mod 2^32)
        h = (h + (h<<1) + (h<<4) + (h<<7) + (h<<8) + (h<<24)) >>> 0;
    }
    return h >>> 0;
}
function _makeRand(seed) {
    var s = (seed >>> 0);
    return function () {
        s = (s * 1664525 + 1013904223) >>> 0;
        return s / 4294967296;
    };
}
function _shuffle(arr, seed) {
    var rnd = _makeRand(seed);
    for (var i = arr.length - 1; i > 0; i--) {
        var j = Math.floor(rnd() * (i + 1));
        var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
}
function _clipVideoKey(clip) {
    return normalizeKey(normalizePath(clip && clip.video_path ? clip.video_path : ''));
}
function _hasOtherAvailable(orderKeys, groups, usedCount, perLimit, excludeKey) {
    for (var i = 0; i < orderKeys.length; i++) {
        var k = orderKeys[i];
        if (k === excludeKey) continue;
        var arr = groups[k];
        if (arr && arr.length > 0) {
            if (perLimit > 0 && usedCount[k] >= perLimit) continue;
            return true;
        }
    }
    return false;
}

/**
 * Trộn clip trong cùng keyword:
 * - group theo video_path
 * - round-robin lấy 1 clip mỗi video
 * - tránh 2 clip liên tiếp cùng video (nếu còn video khác)
 */
function mixClipsForKeyword(keyword, clipsIn) {
    if (!MIX_WITHIN_KEYWORD) return clipsIn;

    var clips = [];
    for (var i = 0; i < clipsIn.length; i++) {
        if (clipsIn[i] && clipsIn[i].video_path) clips.push(clipsIn[i]);
    }
    if (clips.length <= 1) return clipsIn;

    var groups = {};     // videoKey -> [clip,...]
    var orderKeys = [];  // giữ thứ tự video xuất hiện
    for (var c = 0; c < clips.length; c++) {
        var k = _clipVideoKey(clips[c]);
        if (!k) continue;
        if (!groups[k]) {
            groups[k] = [];
            orderKeys.push(k);
        }
        groups[k].push(clips[c]);
    }
    if (orderKeys.length <= 1) return clipsIn;

    if (MIX_SHUFFLE_VIDEO_ORDER) {
        _shuffle(orderKeys, _hashSeed(keyword || 'kw'));
    }

    var usedCount = {};
    for (var u = 0; u < orderKeys.length; u++) usedCount[orderKeys[u]] = 0;

    var out = [];
    var lastKey = null;

    while (true) {
        if (MIX_MAX_CLIPS_PER_KEYWORD > 0 && out.length >= MIX_MAX_CLIPS_PER_KEYWORD) break;

        var progressed = false;

        for (var i2 = 0; i2 < orderKeys.length; i2++) {
            if (MIX_MAX_CLIPS_PER_KEYWORD > 0 && out.length >= MIX_MAX_CLIPS_PER_KEYWORD) break;

            var key = orderKeys[i2];
            var arr = groups[key];
            if (!arr || arr.length <= 0) continue;

            if (MIX_PER_VIDEO_LIMIT > 0 && usedCount[key] >= MIX_PER_VIDEO_LIMIT) continue;

            if (MIX_AVOID_SAME_VIDEO_CONSECUTIVE && lastKey !== null && key === lastKey) {
                if (_hasOtherAvailable(orderKeys, groups, usedCount, MIX_PER_VIDEO_LIMIT, key)) {
                    continue;
                }
            }

            var clip = arr.shift(); // lấy clip đầu tiên của video đó
            out.push(clip);
            usedCount[key] = (usedCount[key] || 0) + 1;
            lastKey = key;
            progressed = true;
        }

        if (!progressed) break;
    }

    // Giữ những clip thiếu video_path (nếu có) ở cuối (an toàn)
    if (out.length < clipsIn.length) {
        for (var x = 0; x < clipsIn.length; x++) {
            if (!clipsIn[x] || !clipsIn[x].video_path) out.push(clipsIn[x]);
        }
    }

    return out;
}

// ================= MAIN =================
function main() {
    log('');
    log('========================================');
    log('  EXECUTE CUTS - STEP 3 (PACK + NO AUDIO + MIX)');
    log('========================================');

    var cfg = readPathConfig();
    if (!cfg) { alert('ERROR: Khong tim thay data/path.txt'); return; }

    var dataFolder = resolveDataFolder(cfg);
    if (!dataFolder) { alert('ERROR: data_folder chua duoc dinh nghia'); return; }
    log('Data folder: ' + dataFolder);

    var seq = app.project.activeSequence;
    if (!seq) { alert('ERROR: Khong co sequence nao dang mo!'); return; }
    log('Sequence: ' + seq.name);

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

    // ============================
    // MODE A: bình thường (mỗi marker chạy riêng) + MIX trong keyword
    // MODE B: MERGE markers cùng keyword thành 1 block
    // ============================
    if (!MERGE_MARKERS_SAME_KEYWORD) {
        for (var m = 0; m < cuts.length; m++) {
            var marker = cuts[m];
            var clips = marker.clips || [];
            if (!clips.length) { skipCount++; continue; }

            // sort trước rồi MIX
            sortClipsByTimelinePos(clips);
            var kw = _trimStr(marker.keyword || '');
            if (!kw) kw = 'UNKNOWN';
            if (MIX_WITHIN_KEYWORD) clips = mixClipsForKeyword(kw, clips);

            var cursorTicks = secondsToTicks(safeNum(marker.timeline_start, safeNum(clips[0].timeline_pos, 0)));

            log('');
            log('[' + (m + 1) + '/' + cuts.length + '] ' + kw + ' | clips=' + clips.length + (MIX_WITHIN_KEYWORD ? ' | MIX=ON' : ''));

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
    } else {
        // ============================
        // MERGE markers same keyword
        // ============================
        var groups = {};       // kw -> { kw, startSec, clips:[], order:int }
        var kwList = [];
        var orderCounter = 0;

        for (var i = 0; i < cuts.length; i++) {
            var mk = cuts[i];
            var kw2 = _trimStr(mk.keyword || '');
            if (!kw2) kw2 = 'UNKNOWN';

            var mkClips = mk.clips || [];
            if (!mkClips.length) continue;

            sortClipsByTimelinePos(mkClips);

            if (!groups[kw2]) {
                groups[kw2] = { kw: kw2, startSec: safeNum(mk.timeline_start, safeNum(mkClips[0].timeline_pos, 0)), clips: [], order: orderCounter++ };
                kwList.push(kw2);
            } else {
                var st2 = safeNum(mk.timeline_start, safeNum(mkClips[0].timeline_pos, 0));
                if (st2 < groups[kw2].startSec) groups[kw2].startSec = st2;
            }

            for (var k = 0; k < mkClips.length; k++) groups[kw2].clips.push(mkClips[k]);
        }

        // sort keyword theo startSec (nhìn giống timeline)
        for (var a = 0; a < kwList.length - 1; a++) {
            for (var b = a + 1; b < kwList.length; b++) {
                if (groups[kwList[a]].startSec > groups[kwList[b]].startSec) {
                    var tmp = kwList[a]; kwList[a] = kwList[b]; kwList[b] = tmp;
                }
            }
        }

        var globalCursorTicks = 0;
        if (PACK_KEYWORD_BLOCKS_SEQUENTIALLY) {
            // bắt đầu từ keyword sớm nhất
            if (kwList.length > 0) globalCursorTicks = secondsToTicks(groups[kwList[0]].startSec);
        }

        for (var g = 0; g < kwList.length; g++) {
            var kwName = kwList[g];
            var grp = groups[kwName];
            var grpClips = grp.clips || [];
            if (!grpClips.length) continue;

            // MIX toàn bộ clip của keyword sau khi merge
            if (MIX_WITHIN_KEYWORD) grpClips = mixClipsForKeyword(kwName, grpClips);

            var cursorTicks2 = PACK_KEYWORD_BLOCKS_SEQUENTIALLY
                ? globalCursorTicks
                : secondsToTicks(safeNum(grp.startSec, safeNum(grpClips[0].timeline_pos, 0)));

            log('');
            log('[KW ' + (g + 1) + '/' + kwList.length + '] ' + kwName + ' | clips=' + grpClips.length + ' | MERGE=ON' + (MIX_WITHIN_KEYWORD ? ' | MIX=ON' : ''));

            for (var cc = 0; cc < grpClips.length; cc++) {
                var clip2 = grpClips[cc];
                totalClips++;

                if (!clip2 || !clip2.video_path) { skipCount++; continue; }

                var vp2 = normalizePath(clip2.video_path);
                var projectItem2 = getOrImportVideo(vp2, importBin);
                if (!projectItem2) { errorCount++; continue; }

                var startTicks2 = PACK_CLIPS_WITHIN_MARKER ? cursorTicks2 : secondsToTicks(safeNum(clip2.timeline_pos, 0));

                var res2 = placeAndTrim(seq, vTrack, projectItem2, clip2, startTicks2);
                if (res2.ok) {
                    successCount++;
                    if (PACK_CLIPS_WITHIN_MARKER) cursorTicks2 = res2.endTicks;
                } else {
                    errorCount++;
                }
            }

            if (PACK_KEYWORD_BLOCKS_SEQUENTIALLY) {
                globalCursorTicks = cursorTicks2; // nối keyword tiếp theo vào ngay sau keyword này
            }
        }
    }

    // HARD CLEAN: remove ALL audio clips
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
