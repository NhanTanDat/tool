// NOTE: ExtendScript không hỗ trợ cú pháp ES6 import; bỏ dòng import và dùng hàm tự định nghĩa.
var ENABLE_ALERTS = false;
function notify(msg){
    $.writeln('[cutAndPush] ' + msg);
    if (ENABLE_ALERTS) { try { alert(msg); } catch(e){} }
}

// ===== Helpers for path + I/O =====
function _joinPath(a, b) {
    if (!a || a === '') return b || '';
    if (!b || b === '') return a || '';
    var s = a.charAt(a.length - 1);
    return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

function _fileExists(p) {
    try { var f = new File(p); return f.exists; } catch (e) { return false; }
}

function _folderExists(p) {
    try { var f = new Folder(p); return f.exists; } catch (e) { return false; }
}

function _ensureFolder(p) {
    try { var f = new Folder(p); if (!f.exists) return f.create(); return true; } catch (e) { return false; }
}

function _readTextFile(p) {
    try {
        var f = new File(p);
        if (!f.exists) return '';
        if (!f.open('r')) return '';
        var t = f.read();
        f.close();
        return t;
    } catch (e) { return ''; }
}

// parse text file with key=value format
function _parsePathTxt(path) {
    try {
        var content = _readTextFile(path);
        var lines = content.split('\n');
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
        $.writeln("Lỗi đọc file text: " + e.message);
        return {};
    }
}

// ===== Xác định thư mục data theo path.txt =====
var DATA_FOLDER = (function () {
    try {
        // 1) Tìm root (....../projectRoot)
        var scriptFile = new File($.fileName);      // .../core/premierCore/cutAndPush.jsx
        var premierCoreDir = scriptFile.parent;     // premierCore
        var coreDir = premierCoreDir.parent;        // core
        var rootDir = coreDir.parent;               // project root

        // 2) Root data folder (để tìm path.txt): <root>/data
        var rootDataPath = rootDir.fsName + '/data';
        _ensureFolder(rootDataPath);

        // 3) Đọc data/path.txt (nếu có) để lấy data_folder hoặc project_slug
        var pathTxt = _joinPath(rootDataPath, 'path.txt');
        var targetDataPath = rootDataPath; // fallback mặc định
        if (_fileExists(pathTxt)) {
            try {
                var cfg = _parsePathTxt(pathTxt);
                // Ưu tiên trường data_folder (có thể là tuyệt đối hoặc tương đối so với root/data)
                if (cfg && cfg.data_folder) {
                    var df = String(cfg.data_folder);
                    if (_folderExists(df)) {
                        targetDataPath = df;
                    } else {
                        targetDataPath = _joinPath(rootDataPath, df);
                    }
                } else if (cfg && cfg.project_slug) {
                    targetDataPath = _joinPath(rootDataPath, String(cfg.project_slug));
                }
            } catch (eCfg) {
                $.writeln('[DATA_FOLDER] Lỗi đọc path.txt, dùng fallback root/data. Error: ' + eCfg);
            }
        } else {
            $.writeln('[DATA_FOLDER] Không tìm thấy data/path.txt, dùng fallback root/data');
        }

        _ensureFolder(targetDataPath);
        var folder = new Folder(targetDataPath);
        $.writeln('[DATA_FOLDER] Using data folder: ' + folder.fsName);
        return folder.fsName.replace(/\\/g,'/');
    } catch (e2) {
        $.writeln('[DATA_FOLDER] Fallback to desktop due to error: ' + e2);
        return Folder.desktop.fsName.replace(/\\/g,'/');
    }
})();

// Helper tạo path chuẩn
function joinPath(base, name){
    if (!base) return name;
    if (base.charAt(base.length-1) === '/' || base.charAt(base.length-1) === '\\') return base + name;
    return base + '/' + name;
}

// ==================== CSV helpers ====================

// Simple CSV splitter respecting quotes
function splitCSVLine(line){
    var res = [];
    var cur = '';
    var inQ = false;
    for (var i=0;i<line.length;i++){
        var ch = line.charAt(i);
        if (inQ){
            if (ch === '"'){
                if (i+1 < line.length && line.charAt(i+1) === '"'){ cur += '"'; i++; }
                else inQ = false;
            } else cur += ch;
        } else {
            if (ch === ','){ res.push(cur); cur=''; }
            else if (ch === '"') inQ = true;
            else cur += ch;
        }
    }
    res.push(cur);
    return res;
}

// Parser CSV: hỗ trợ cả dạng getTimeline (startSeconds/endSeconds)
// và dạng AI (scene_index,keyword,character,duration_sec,search_query,voiceover)
// + mở rộng cho Genmini: src_start, src_end, bin_name, video_index
function readTimelineCSVFile(filePath){
    try {
        var f = new File(filePath);
        if (!f.exists) {
            $.writeln('[readTimelineCSVFile] File not found: ' + filePath);
            return [];
        }
        if (!f.open('r')) {
            $.writeln('[readTimelineCSVFile] Cannot open file: ' + filePath);
            return [];
        }

        var lines = [];
        while (!f.eof) {
            lines.push(f.readln());
        }
        f.close();
        if (!lines.length) return [];

        var headerLine = lines[0];
        var headerCols = splitCSVLine(headerLine);
        if (!headerCols || !headerCols.length) {
            $.writeln('[readTimelineCSVFile] Empty header line.');
            return [];
        }

        // map header -> index (normalized lowercase)
        var colMap = {};
        for (var i = 0; i < headerCols.length; i++) {
            var raw = headerCols[i];
            if (!raw) continue;
            var norm = raw.replace(/^\s+|\s+$/g, '').toLowerCase();
            if (!norm) continue;
            colMap[norm] = i;
        }

        function findIdx(possibleNames) {
            for (var k = 0; k < possibleNames.length; k++) {
                var key = possibleNames[k];
                if (!key) continue;
                var normKey = key.toLowerCase();
                if (typeof colMap[normKey] !== 'undefined') {
                    return colMap[normKey];
                }
            }
            return -1;
        }

        // cột thời gian (timeline)
        var idxStart = findIdx(['startseconds','start_seconds','start_sec','start']);
        var idxEnd   = findIdx(['endseconds','end_seconds','end_sec','end']);
        var idxDur   = findIdx(['duration_sec','durationseconds','duration','duration_s']);

        // cột tên/bin & text & character
        var idxName  = findIdx(['name','keyword','bin','bin_name']);
        var idxText  = findIdx(['textcontent','voiceover','text','subtitle']);
        var idxChar  = findIdx(['character','char','person','speaker']);

        // Genmini-specific: src_start, src_end, explicit bin_name, video_index
        var idxSrcStart = findIdx(['src_start','srcstart','source_start','video_start_sec','segment_src_start']);
        var idxSrcEnd   = findIdx(['src_end','srcend','source_end','video_end_sec','segment_src_end']);
        var idxBinName2 = findIdx(['bin_name','bin','binname']);
        var idxVideoIdx = findIdx(['video_index','videoidx','video_idx','clip_index']);

        var mode = '';
        if (idxStart >= 0 && idxEnd >= 0) {
            mode = 'start_end';      // file có sẵn startSeconds/endSeconds (timeline)
        } else if (idxDur >= 0) {
            mode = 'duration_only';  // chỉ có duration_sec -> tự tính start/end nối tiếp
        } else {
            $.writeln('[readTimelineCSVFile] Header không có cột start/end hoặc duration. Header: ' + headerLine);
            return [];
        }

        var out = [];
        var currentStart = 0;

        for (var r = 1; r < lines.length; r++) {
            var line = lines[r];
            if (!line) continue;
            var parts = splitCSVLine(line);
            if (!parts || !parts.length) continue;

            var s, e, d;

            if (mode === 'start_end') {
                if (idxStart < 0 || idxEnd < 0 ||
                    idxStart >= parts.length || idxEnd >= parts.length) {
                    continue;
                }
                s = parseFloat(parts[idxStart]);
                e = parseFloat(parts[idxEnd]);
                if (isNaN(s) || isNaN(e) || s < 0 || e <= s) {
                    continue;
                }
            } else { // duration_only
                if (idxDur < 0 || idxDur >= parts.length) continue;
                d = parseFloat(parts[idxDur]);
                if (isNaN(d) || d <= 0) continue;
                s = currentStart;
                e = s + d;
                currentStart = e;
            }

            var nm = 'Scene_' + (out.length + 1);
            if (idxName >= 0 && idxName < parts.length) {
                nm = parts[idxName];
            }

            var txt = '';
            if (idxText >= 0 && idxText < parts.length) {
                txt = parts[idxText];
            }

            var chName = '';
            if (idxChar >= 0 && idxChar < parts.length) {
                chName = parts[idxChar];
            }

            // Genmini fields
            var srcStart = null;
            var srcEnd   = null;
            var binExtra = '';
            var videoIdx = -1;

            if (idxSrcStart >= 0 && idxSrcStart < parts.length) {
                var tmpS = parseFloat(parts[idxSrcStart]);
                if (!isNaN(tmpS) && tmpS >= 0) srcStart = tmpS;
            }
            if (idxSrcEnd >= 0 && idxSrcEnd < parts.length) {
                var tmpE = parseFloat(parts[idxSrcEnd]);
                if (!isNaN(tmpE) && tmpE > 0) srcEnd = tmpE;
            }
            if (idxBinName2 >= 0 && idxBinName2 < parts.length) {
                binExtra = parts[idxBinName2];
            }
            if (idxVideoIdx >= 0 && idxVideoIdx < parts.length) {
                var tmpIdx = parseInt(parts[idxVideoIdx], 10);
                if (!isNaN(tmpIdx) && tmpIdx >= 0) videoIdx = tmpIdx;
            }

            out.push({
                index: out.length,
                startSeconds: s,
                endSeconds: e,
                name: nm,
                textContent: txt,
                character: chName,
                binName: binExtra,
                srcStart: srcStart,
                srcEnd: srcEnd,
                videoIndex: videoIdx
            });
        }

        if (out.length) {
            $.writeln('[readTimelineCSVFile] Parsed ' + out.length + ' clips from CSV (mode=' + mode + ').');
        } else {
            $.writeln('[readTimelineCSVFile] No valid row parsed from CSV.');
        }
        return out;
    } catch(e){
        $.writeln('[readTimelineCSVFile] Error: ' + e);
        return [];
    }
}

// Biến global dùng khắp file
var project = null;
var sequence = null;
var g_project = null;
var g_sequence = null;

// Lưu lại các khoảng (in,out) đã dùng ...
var _USED_INTERVALS = {};

// Cấu hình thuật toán tránh trùng (chỉ dùng cho chế độ random cũ)
var NON_OVERLAP_CONFIG = {
    maxRandomTries: 12,        // số lần thử random khác trước khi quét gap
    minSeparationFactor: 0.35, // yêu cầu đoạn mới không overlap hơn (factor * finalDuration)
    jitterFraction: 0.15       // khi chọn trong gap có thể dịch một chút
};

function _intervalKey(videoItem, srcPlayable){
    var nm = '';
    try { nm = (videoItem && videoItem.name) ? videoItem.name : 'CLIP'; } catch(e){}
    return nm + '_' + (srcPlayable||0).toFixed(3);
}

function _overlap(aStart, aEnd, bStart, bEnd){
    return (aStart < bEnd) && (bStart < aEnd);
}

function _upgradeOldIntervals(list){
    if (!list) return;
    for (var i=0;i<list.length;i++){
        var obj = list[i];
        if (typeof obj.start === 'undefined' && typeof obj.in !== 'undefined'){
            obj.start = obj.in; // migrate
            obj.end = obj.out;
            try { delete obj.in; delete obj.out; } catch(e){}
        }
    }
}

function _hasHeavyOverlap(newStart, newEnd, usedList, minAllowedOverlap){
    if (!usedList) return false;
    _upgradeOldIntervals(usedList);
    for (var i=0;i<usedList.length;i++){
        var u = usedList[i];
        if (_overlap(newStart, newEnd, u.start, u.end)){
            // tính phần overlap
            var ovStart = Math.max(newStart, u.start);
            var ovEnd   = Math.min(newEnd, u.end);
            var ov = ovEnd - ovStart;
            if (ov >= minAllowedOverlap) return true;
        }
    }
    return false;
}

function _registerInterval(key, s, e){
    if (!_USED_INTERVALS[key]) _USED_INTERVALS[key] = [];
    var list = _USED_INTERVALS[key];
    _upgradeOldIntervals(list);
    list.push({start: s, end: e});
}

function _pickNonOverlappingStart(srcInSec, srcOutSec, finalDuration, key){
    var list = _USED_INTERVALS[key] || [];
    var maxStart = srcOutSec - finalDuration;
    if (maxStart < srcInSec) return srcInSec; // clip ngắn
    var attempts = NON_OVERLAP_CONFIG.maxRandomTries;
    var minAllowedOverlap = NON_OVERLAP_CONFIG.minSeparationFactor * finalDuration;

    var t;
    for (t=0;t<attempts;t++){
        var cand = srcInSec + Math.random() * (maxStart - srcInSec);
        var candEnd = cand + finalDuration;
        if (!_hasHeavyOverlap(cand, candEnd, list, minAllowedOverlap)) {
            _registerInterval(key, cand, candEnd);
            return cand;
        }
    }

    // Nếu random thất bại, thử tìm gap tuyến tính (sort trước)
    if (list.length){
        _upgradeOldIntervals(list);
        // sao chép & sort theo start
        var arr = list.slice().sort(function(a,b){ return a.start - b.start; });
        // kiểm tra gap trước đoạn đầu
        if (arr[0].start - srcInSec >= finalDuration){
            var startGap = srcInSec;
            _registerInterval(key, startGap, startGap+finalDuration);
            return startGap;
        }
        // giữa các đoạn
        for (var i=0;i<arr.length-1;i++){
            var endPrev = arr[i].end;
            var startNext = arr[i+1].start;
            if (startNext - endPrev >= finalDuration){
                var gapStart = endPrev + NON_OVERLAP_CONFIG.jitterFraction * Math.min(finalDuration, (startNext - endPrev - finalDuration));
                _registerInterval(key, gapStart, gapStart+finalDuration);
                return gapStart;
            }
        }
        // gap cuối
        if (srcOutSec - arr[arr.length-1].end >= finalDuration){
            var tailStart = arr[arr.length-1].end;
            _registerInterval(key, tailStart, tailStart+finalDuration);
            return tailStart;
        }
    }
    // Bất đắc dĩ: lấy random bất kỳ (chấp nhận trùng)
    var fallback = srcInSec + Math.random() * (maxStart - srcInSec);
    _registerInterval(key, fallback, fallback+finalDuration);
    return fallback;
}

// =================== Time helpers ===================
var TICKS_PER_SECOND = 254016000000.0; // dùng chung cho seconds <-> ticks

// Premiere trả về Time object có .seconds; ta luôn làm việc bằng giây
function timeObjToSeconds(t){
    try {
        if (!t) return 0;
        if (typeof t.seconds === 'number') {
            return t.seconds;
        }
        // fallback nếu có ticks (hiếm khi cần)
        if (typeof t.ticks === 'number') {
            return t.ticks / TICKS_PER_SECOND;
        }
    } catch(e){}
    return 0;
}

// ======= CONFIG =======
var DEFAULT_SEQUENCE_NAME = "Main";

// Nếu muốn chỉ dùng 1 nhân vật duy nhất cho cả timeline (vd "Naruto"),
// thì set:
//    var ONLY_CHARACTER = "Naruto";
// Để chuỗi rỗng "" nghĩa là dùng tất cả character trong CSV.
var ONLY_CHARACTER = "";

// Cho phép runAll.jsx override tên sequence
// (trong runAll.jsx: RUNALL_SEQUENCE_NAME = "Main"; trước khi eval cutAndPush.jsx)
var TARGET_SEQUENCE_NAME = (typeof RUNALL_SEQUENCE_NAME !== 'undefined' && RUNALL_SEQUENCE_NAME)
    ? RUNALL_SEQUENCE_NAME
    : DEFAULT_SEQUENCE_NAME;

// ======= TÌM SEQUENCE THEO TÊN =======
function _findSequenceItemByName(rootItem, name) {
    if (!rootItem || !rootItem.children || !rootItem.children.numItems) return null;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var child = rootItem.children[i];
        if (!child) continue;

        // type 3 = sequence
        if (child.type === 3 && child.name === name) {
            return child;
        }
        var sub = _findSequenceItemByName(child, name);
        if (sub) return sub;
    }
    return null;
}

// Lấy sequence đầu tiên tìm thấy (fallback nếu không có tên cụ thể)
function _findFirstSequenceItem(rootItem) {
    if (!rootItem || !rootItem.children || !rootItem.children.numItems) return null;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var child = rootItem.children[i];
        if (!child) continue;
        if (child.type === 3) return child;
        var sub = _findFirstSequenceItem(child);
        if (sub) return sub;
    }
    return null;
}

function initializeProjectAndSequence() {
    if (typeof app === 'undefined' || !app.project) {
        $.writeln('[initializeProjectAndSequence] Không có app.project');
        return false;
    }

    // Dùng biến GLOBAL
    project = app.project;
    g_project = project;

    try {
        $.writeln('[initializeProjectAndSequence] Project: ' + project.name + ' | path=' + project.path);
    } catch (e0) {}

    var targetName = (typeof RUNALL_SEQUENCE_NAME !== 'undefined' && RUNALL_SEQUENCE_NAME)
        ? RUNALL_SEQUENCE_NAME
        : DEFAULT_SEQUENCE_NAME;

    $.writeln('[initializeProjectAndSequence] Target sequence name = ' + targetName);

    var seq = null;
    var seqs = project.sequences;
    var n = seqs ? seqs.numSequences : 0;

    // 1) Nếu activeSequence trùng tên target → dùng luôn
    if (project.activeSequence) {
        var active = project.activeSequence;
        $.writeln('[initializeProjectAndSequence] Active sequence hiện tại: ' + active.name);
        if (!targetName || active.name === targetName) {
            seq = active;
        }
    }

    // 2) Nếu chưa có, tìm sequence theo tên (vd "Main")
    if (!seq && targetName) {
        var seqItem = _findSequenceItemByName(project.rootItem, targetName);
        if (seqItem) {
            $.writeln('[initializeProjectAndSequence] Tìm thấy sequence tên "' + targetName + '", openInTimeline.');
            try {
                seqItem.openInTimeline();
                seq = project.activeSequence;
            } catch (e1) {
                $.writeln('[initializeProjectAndSequence] Lỗi openInTimeline: ' + e1);
            }
        } else {
            $.writeln('[initializeProjectAndSequence] Không tìm thấy sequence "' + targetName + '" trong project.');
        }
    }

    // 3) Fallback: sequence đầu tiên trong project
    if (!seq && n > 0) {
        var firstSeq = seqs[0];
        $.writeln('[initializeProjectAndSequence] Fallback dùng sequence đầu tiên: ' + firstSeq.name);
        try {
            firstSeq.openInTimeline();
            seq = project.activeSequence;
        } catch (e2) {
            $.writeln('[initializeProjectAndSequence] Lỗi openInTimeline fallback: ' + e2);
        }
    }

    // 4) Nếu vẫn chưa có, thử tạo mới từ clip đầu tiên (giữ nguyên logic cũ)
    if (!seq) {
        $.writeln('[initializeProjectAndSequence] Không có sequence nào, thử tạo sequence mới từ clip đầu tiên.');

        var root = project.rootItem;
        var firstClipItem = null;

        function _findFirstClip(item) {
            if (!item || !item.children || !item.children.numItems) return null;
            for (var i = 0; i < item.children.numItems; i++) {
                var child = item.children[i];
                if (child && child.type === 1) return child; // clip
                var sub = _findFirstClip(child);
                if (sub) return sub;
            }
            return null;
        }

        firstClipItem = _findFirstClip(root);

        if (!firstClipItem) {
            $.writeln('[initializeProjectAndSequence] Không tìm thấy clip nào trong project, không thể tạo sequence.');
            return false;
        }

        var newSeqName = targetName || 'AutoSequence';
        try {
            project.newSequenceFromClip(newSeqName, firstClipItem);
            seq = project.activeSequence;
            $.writeln('[initializeProjectAndSequence] Đã tạo sequence mới: ' + newSeqName);
        } catch (e3) {
            $.writeln('[initializeProjectAndSequence] Lỗi tạo sequence mới: ' + e3);
            return false;
        }
    }

    if (!seq) {
        $.writeln('[initializeProjectAndSequence] Không thể khởi tạo sequence.');
        return false;
    }

    // GÁN VÀO GLOBAL
    sequence   = seq;
    g_sequence = seq;
    app.project.activeSequence = seq;

    $.writeln('[initializeProjectAndSequence] Using sequence: ' + seq.name);
    return true;
}

// =================== MARKER helpers ===================
// Thêm marker để chú thích đoạn này thuộc keyword / character nào
function addKeywordMarkerForRange(seq, startSeconds, endSeconds, keyword, character) {
    try {
        if (!seq || !seq.markers) {
            $.writeln('[addKeywordMarkerForRange] No sequence or markers');
            return;
        }
        var t = startSeconds;
        if (t < 0) t = 0;

        var markers = seq.markers;
        var m = markers.createMarker(t); // time tính bằng giây

        var kw = keyword ? String(keyword) : '';
        var ch = character ? String(character) : '';

        var title = '';
        if (kw) title += kw;
        if (ch) title += (title ? ' [' + ch + ']' : '[' + ch + ']');
        if (!title) title = 'Scene at ' + t.toFixed(2) + 's';

        m.name = title;
        m.comments = 'keyword: ' + (kw || '(none)') + ' | character: ' + (ch || '(none)');

        if (endSeconds > startSeconds) {
            var endTicks = endSeconds * TICKS_PER_SECOND;
            m.end = endTicks;
        }

        $.writeln('[addKeywordMarkerForRange] Marker created at ' + t.toFixed(3) + 's with title: ' + title);
    } catch (e) {
        $.writeln('[addKeywordMarkerForRange] Error: ' + e);
    }
}

// hàm gen thời gian duration ngẫu nhiên trong khoảng min và max (đơn vị giây)
function getRandomDuration(minSeconds, maxSeconds) {
    if (minSeconds < 0 || maxSeconds < 0 || minSeconds >= maxSeconds) {
        $.writeln('[getRandomDuration] Invalid min or max seconds');
        return 0;
    }
    var randomSeconds = Math.random() * (maxSeconds - minSeconds) + minSeconds;
    return randomSeconds;
}

// hàm tự tạo v track mới trên cùng (tạm chưa dùng, nhưng giữ lại)
function addVideoTrackOnTop() {
    var seq = app.project.activeSequence;
    if (!seq) {
        $.writeln("[addVideoTrackOnTop] No active sequence.");
        return null;
    }

    app.enableQE();
    var qeSeq = qe.project.getActiveSequence();
    if (!qeSeq) {
        $.writeln("[addVideoTrackOnTop] qe.project.getActiveSequence() failed.");
        return null;
    }

    var before = seq.videoTracks.numTracks;

    // Thêm track mới (luôn vào đáy = V1)
    qeSeq.addTracks(1, 0);

    var after = seq.videoTracks.numTracks;
    if (after <= before) {
        $.writeln("[addVideoTrackOnTop] Failed to add track.");
        return null;
    }

    // Track mới tạo sẽ nằm ở index 0 (V1), ta move nó lên top
    var newTrack = seq.videoTracks[0];
    var targetIndex = after - 1;

    try {
        newTrack.move(targetIndex);
        $.writeln("[addVideoTrackOnTop] Added new video track and moved to TOP index " + targetIndex);
        return seq.videoTracks[targetIndex];
    } catch (e) {
        $.writeln("[addVideoTrackOnTop] Move failed: " + e);
        return null;
    }
}

// =============================================================
// CUT VÀ PUSH CLIP VÀO TIMELINE
// =============================================================
// THAY ĐỔI QUAN TRỌNG:
// - Nếu có srcStartOverride/srcEndOverride (Genmini) → dùng chính xác đoạn đó.
// - Nếu không có → giữ logic random cũ (getRandomDuration + _pickNonOverlappingStart).
// =============================================================
function cutAndPushClipToTimeline(
    binName,
    idxBinVd,
    startTime,
    endTime,
    sequence,
    targetVideoTrack,
    srcStartOverride,
    srcEndOverride
) {
    if (!project || !sequence || !targetVideoTrack) {
        $.writeln('[cutAndPushClipToTimeline] project, sequence, or targetVideoTrack is null or undefined');
        return startTime;
    }
    var rootItem = project.rootItem;
    if (!rootItem) {
        $.writeln('[cutAndPushClipToTimeline] project.rootItem is null or undefined');
        return startTime;
    }

    // Tìm bin theo tên
    var targetBin = null;
    var i;
    for (i = 0; i < rootItem.children.numItems; i++) {
        var child = rootItem.children[i];
        if (child && child.type === 2 && child.name === binName) { // 2 = Bin
            targetBin = child;
            break;
        }
    }
    if (!targetBin) {
        $.writeln('[cutAndPushClipToTimeline] Bin not found: ' + binName);
        return startTime;
    }

    // lấy ra video thứ idxBinVd trong bin
    if (idxBinVd < 0 || idxBinVd >= targetBin.children.numItems) {
        $.writeln('[cutAndPushClipToTimeline] idxBinVd out of range: ' + idxBinVd);
        return startTime;
    }
    var videoItem = targetBin.children[idxBinVd];
    if (!videoItem || videoItem.type !== 1) { // 1 = Clip
        $.writeln('[cutAndPushClipToTimeline] Item at idxBinVd is not a clip: ' + idxBinVd);
        return startTime;
    }
    $.writeln('[cutAndPushClipToTimeline] Found clip: ' + videoItem.name + ' in bin: ' + binName);

    // Kiểm tra thời gian slot trên timeline
    var inputDuration = endTime - startTime;
    if (startTime < 0 || inputDuration <= 0) {
        $.writeln('[cutAndPushClipToTimeline] Invalid startTime or endTime');
        return startTime;
    }

    // Lấy thời gian in/out gốc của clip nguồn (giây)
    var srcInSec = timeObjToSeconds(videoItem.getInPoint());
    var srcOutSec = timeObjToSeconds(videoItem.getOutPoint());
    var srcPlayable = srcOutSec - srcInSec;
    if (srcPlayable <= 0) {
        $.writeln('[cutAndPushClipToTimeline] Source clip has non-positive duration');
        return startTime;
    }

    var hasOverride = false;
    var newInSec, newOutSec, finalDuration;

    // ==================================================
    // CASE 1: Có dữ liệu Genmini -> dùng chính xác [src_start, src_end]
    // ==================================================
    if (typeof srcStartOverride === 'number' &&
        typeof srcEndOverride === 'number' &&
        srcEndOverride > srcStartOverride) {

        hasOverride = true;
        newInSec = srcStartOverride;
        newOutSec = srcEndOverride;

        // Clamp vào khoảng playable của clip
        if (newInSec < srcInSec) newInSec = srcInSec;
        if (newOutSec > srcOutSec) newOutSec = srcOutSec;

        finalDuration = newOutSec - newInSec;
        if (finalDuration <= 0) {
            $.writeln('[cutAndPushClipToTimeline] Override range invalid after clamp, skip.');
            return startTime;
        }

        $.writeln('[cutAndPushClipToTimeline] Using Genmini segment [' +
                  newInSec.toFixed(3) + 's -> ' + newOutSec.toFixed(3) +
                  's], duration=' + finalDuration.toFixed(3) + 's');
    }
    // ==================================================
    // CASE 2: Không có override -> random như cũ
    // ==================================================
    if (!hasOverride) {
        var randomDuration = getRandomDuration(2, 4); // độ dài đoạn lấy
        if (inputDuration <= randomDuration) finalDuration = inputDuration;
        else finalDuration = randomDuration;

        var key = _intervalKey(videoItem, srcPlayable);
        newInSec = _pickNonOverlappingStart(srcInSec, srcOutSec, finalDuration, key);
        newOutSec = newInSec + finalDuration;
        if (newOutSec > srcOutSec) newOutSec = srcOutSec; // đảm bảo không vượt quá

        finalDuration = newOutSec - newInSec;
        if (finalDuration <= 0) {
            $.writeln('[cutAndPushClipToTimeline] Random segment invalid, skip.');
            return startTime;
        }

        $.writeln('[cutAndPushClipToTimeline] RANDOM segment [' +
                  newInSec.toFixed(3) + 's -> ' + newOutSec.toFixed(3) +
                  's], duration=' + finalDuration.toFixed(3) + 's, key=' + key);
    }

    // Tạo subclip từ videoItem
    var newClip = null;
    try {
        newClip = videoItem.createSubClip(
            videoItem.name + '_subclip_' + startTime.toFixed(3) + '_' + endTime.toFixed(3),
            newInSec,
            newOutSec,
            0,   // hasHardBoundaries
            1,   // takeVideo
            1    // takeAudio (nếu không muốn audio thì để 0)
        );
    } catch(eCreate) {
        $.writeln('[cutAndPushClipToTimeline] createSubClip failed: ' + eCreate);
        return startTime;
    }

    if (!newClip) {
        $.writeln('[cutAndPushClipToTimeline] Failed to create subclip from: ' + videoItem.name);
        return startTime;
    }
    $.writeln('[cutAndPushClipToTimeline] Created subclip: ' +
              newClip.name + ' from ' + newInSec.toFixed(3) +
              's to ' + newOutSec.toFixed(3) + 's (duration: ' +
              finalDuration.toFixed(3) + 's)');

    // Đẩy đoạn clip mới vào timeline tại vị trí startTime (seconds)
    try {
        targetVideoTrack.insertClip(newClip, startTime);
    } catch(insErr) {
        $.writeln('[cutAndPushClipToTimeline] insertClip failed -> ' + insErr);
    }

    $.writeln('[cutAndPushClipToTimeline] Inserted subclip into timeline at ' + startTime + ' seconds on track.');

    return startTime + finalDuration; // tiến thời gian trên timeline
}

// hàm test cut và push clip vào timeline (dev)
function testCutAndPush() {
    initializeProjectAndSequence();
    if (!project || !sequence) return -1;

    var topIndex = sequence.videoTracks.numTracks - 1;
    if (topIndex < 0) { $.writeln('[testCutAndPush] No video track available'); return; }
    var targetVideoTrack = sequence.videoTracks[topIndex];
    if (!targetVideoTrack) { $.writeln('[testCutAndPush] Failed to get top video track'); return; }

    var startTime = 40.3333333333; // giây
    var endTime   = 48.9666666667; // giây

    while (startTime < endTime) {
        var prev = startTime;
        startTime = cutAndPushClipToTimeline("Amber_Portwood_tiktok", 0, startTime, endTime, sequence, targetVideoTrack, null, null);
        if (startTime === null || startTime === prev) { // không tiến lên -> dừng tránh vòng lặp vô hạn
            $.writeln('[testCutAndPush] Stop loop (no progress)');
            break;
        }
    }
    $.writeln('[testCutAndPush] Finished cutting and pushing clips to timeline.');
}

// ================== DEBUG: dump clips trong sequence ==================
function dumpSequenceClips() {
    if (!sequence) {
        $.writeln('[dumpSequenceClips] No sequence');
        return;
    }
    $.writeln('===== DUMP CLIPS OF SEQUENCE: ' + sequence.name + ' =====');
    var vt = sequence.videoTracks;
    for (var t = 0; t < vt.numTracks; t++) {
        var tr = vt[t];
        if (!tr) continue;
        var clips = tr.clips;
        $.writeln('Track V' + t + ' (' + tr.name + '): ' + clips.numItems + ' clips');
        for (var c = 0; c < clips.numItems; c++) {
            var item = clips[c];
            try {
                $.writeln(
                    '  [' + c + '] ' + item.name +
                    ' | start=' + item.start.seconds +
                    ' | end=' + item.end.seconds
                );
            } catch (e) {
                $.writeln('  [' + c + '] (error reading clip info) ' + e);
            }
        }
    }
    $.writeln('===== END DUMP =====');
}

// hàm chính: đọc timeline CSV và chèn lần lượt các đoạn vào track video trên cùng
function cutAndPushAllTimeline(tlFilePath) { 
    // Nếu không truyền vào, dùng file mặc định trong DATA_FOLDER
    if (!tlFilePath || tlFilePath === '') {
        var defaultPath = joinPath(DATA_FOLDER, 'timeline_export_merged.csv');
        tlFilePath = new File(defaultPath);
        $.writeln('[cutAndPushAllTimeline] Default CSV path: ' + defaultPath);
    } else if (typeof tlFilePath === 'string') {
        tlFilePath = new File(tlFilePath);
    }

    if (!(tlFilePath instanceof File)) {
        notify('tlFilePath phải là đường dẫn file hoặc File object');
        return -1;
    }

    initializeProjectAndSequence();
    if(!project || !sequence) return -1;

    var targetVideoTrack = sequence.videoTracks[sequence.videoTracks.numTracks - 1];
    if (!targetVideoTrack) {
        notify('Không thể lấy track video trên cùng.');
        return -1;
    }

    var tlEntries = [];
    if (tlFilePath.fsName.match(/\.csv$/)) {
        tlEntries = readTimelineCSVFile(tlFilePath.fsName);
    } else {
        notify('Chỉ hỗ trợ file CSV hiện tại: ' + tlFilePath.fsName);
        return -1;
    }
    if (!tlEntries.length) { 
        notify('Không có entry hợp lệ trong file: ' + tlFilePath.fsName); 
        return -1; 
    }

    $.writeln('[cutAndPushAllTimeline] Read ' + tlEntries.length + ' entries from timeline file.');
    var processedCount = 0;
    var sizeBin = {}; // cache bin sizes
    var binIdxMap = {}; // Map quản lý pool index cho từng bin: { binName: [idx... (đã shuffle)] }

    function shuffleInPlace(arr){
        for (var i = arr.length - 1; i > 0; i--){
            var j = Math.floor(Math.random() * (i + 1));
            var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
        }
        return arr;
    }

    function ensureBinPool(binName, binSize){
        var pool = binIdxMap[binName];
        if (!pool || pool.length === 0){
            var arr = [];
            for (var k=0; k<binSize; k++) arr.push(k);
            binIdxMap[binName] = shuffleInPlace(arr);
        }
    }

    function popIdxFromBin(binName, binSize){
        ensureBinPool(binName, binSize);
        return binIdxMap[binName].pop();
    }

    // Tìm bin theo tên, nhưng có hỗ trợ alias kiểu "1_naruto" -> "naruto"
    function _findBinByNameOrAlias(binName){
        if (!project || !project.rootItem) return null;
        var rootItem = project.rootItem;
        if (!binName) return null;

        var i, child;

        // 1) match chính xác
        for (i = 0; i < rootItem.children.numItems; i++) {
            child = rootItem.children[i];
            if (child && child.type === 2 && child.name === binName) {
                return child;
            }
        }

        var lowerName = String(binName).toLowerCase();
        var parts = binName.split('_');
        var lastToken = parts[parts.length - 1];
        var lastLower = lastToken.toLowerCase();

        // 2) match theo token cuối (vd: "1_naruto" -> "naruto")
        for (i = 0; i < rootItem.children.numItems; i++) {
            child = rootItem.children[i];
            if (child && child.type === 2) {
                var cnLower = String(child.name).toLowerCase();
                if (cnLower === lastLower) {
                    return child;
                }
            }
        }

        // 3) match kiểu chứa nhau (substring)
        for (i = 0; i < rootItem.children.numItems; i++) {
            child = rootItem.children[i];
            if (child && child.type === 2) {
                var cnLower2 = String(child.name).toLowerCase();
                if (lowerName.indexOf(cnLower2) >= 0 || cnLower2.indexOf(lowerName) >= 0) {
                    return child;
                }
            }
        }

        return null;
    }

    for (var i = 0; i < tlEntries.length; i++) {
        var entry = tlEntries[i];
        var startSeconds = entry.startSeconds;
        var endSeconds = entry.endSeconds;

        var nameField   = entry.name || '';
        var textContent = entry.textContent || '';
        var character   = entry.character || '';

        // OPTIONAL FILTER: chỉ giữ đúng một nhân vật duy nhất nếu ONLY_CHARACTER được set
        if (ONLY_CHARACTER && character) {
            var cf = String(character).replace(/\s+/g, ' ').toLowerCase();
            var of = String(ONLY_CHARACTER).replace(/\s+/g, ' ').toLowerCase();
            if (cf !== of) {
                $.writeln('[cutAndPushAllTimeline] Skip line ' + (i+1) +
                          ' vì character="' + character + '" khác ONLY_CHARACTER="' + ONLY_CHARACTER + '"');
                continue;
            }
        }

        // ƯU TIÊN character LÀM TÊN BIN, sau đó binName từ CSV, rồi name/text
        var binName = '';
        if (character) {
            binName = String(character);
        } else if (entry.binName) {
            binName = String(entry.binName);
        } else if (nameField) {
            binName = String(nameField);
        } else if (textContent) {
            binName = String(textContent);
        }
        binName = binName ? binName.replace(/\s+/g, '_') : '';

        if (!binName) {
            $.writeln('[cutAndPushAllTimeline] Skipping entry với empty bin name tại line ' + (i+1));
            continue;
        }

        // Thêm marker chú thích keyword/character cho đoạn timeline này
        addKeywordMarkerForRange(sequence, startSeconds, endSeconds, nameField, character);

        // Tìm bin
        var binSize = 0;
        if (sizeBin.hasOwnProperty(binName)) {
            binSize = sizeBin[binName];
        } else {
            var targetBin = _findBinByNameOrAlias(binName);
            if (!targetBin) {
                $.writeln('[cutAndPushAllTimeline] Bin not found: ' + binName + ' at line ' + (i+1));
                continue;
            }
            binSize = targetBin.children.numItems;
            if (binSize <= 0) {
                $.writeln('[cutAndPushAllTimeline] Bin is empty: ' + targetBin.name + ' at line ' + (i+1));
                continue;
            }
            sizeBin[targetBin.name] = binSize;
            binName = targetBin.name;
        }

        // Genmini segment (srcStart/srcEnd) + videoIndex
        var srcStartOverride = (entry.srcStart !== null && typeof entry.srcStart === 'number') ? entry.srcStart : null;
        var srcEndOverride   = (entry.srcEnd   !== null && typeof entry.srcEnd   === 'number') ? entry.srcEnd   : null;
        var hasFixedSegment = (srcStartOverride !== null && srcEndOverride !== null && srcEndOverride > srcStartOverride);

        var videoIdx = (typeof entry.videoIndex === 'number' && entry.videoIndex >= 0)
            ? entry.videoIndex
            : -1;
        if (videoIdx >= binSize) {
            videoIdx = binSize - 1;
        }

        // ===========================================
        // CASE A: Có segment Genmini -> dùng đúng 1 clip, đúng đoạn
        // ===========================================
        if (hasFixedSegment) {
            if (videoIdx < 0) {
                // nếu không có videoIndex, tạm dùng popIdxFromBin (random clip trong bin)
                videoIdx = popIdxFromBin(binName, binSize);
            }
            $.writeln('[cutAndPushAllTimeline] [Genmini] line ' + (i+1) +
                      ' bin=' + binName +
                      ' videoIdx=' + videoIdx +
                      ' src=[' + srcStartOverride + ' -> ' + srcEndOverride + ']');
            cutAndPushClipToTimeline(
                binName,
                videoIdx,
                startSeconds,
                endSeconds,
                sequence,
                targetVideoTrack,
                srcStartOverride,
                srcEndOverride
            );
            processedCount++;
            continue; // sang entry tiếp theo (mỗi dòng 1 segment)
        }

        // ===========================================
        // CASE B: Không có segment Genmini -> giữ logic random cũ
        // ===========================================
        while (true){
            var idxInBin = (videoIdx >= 0) ? videoIdx : popIdxFromBin(binName, binSize);
            var prevStart = startSeconds;
            startSeconds = cutAndPushClipToTimeline(
                binName,
                idxInBin,
                startSeconds,
                endSeconds,
                sequence,
                targetVideoTrack,
                null,
                null
            );
            if (startSeconds === null || startSeconds === prevStart) {
                $.writeln('[cutAndPushAllTimeline] Stop loop for entry at line ' + (i+1) + ' (no progress)');
                break;
            }
            if (startSeconds >= endSeconds) {
                $.writeln('[cutAndPushAllTimeline] Finished entry at line ' + (i+1));
                break;
            }
        }
        processedCount++;
    }

    // Debug: dump toàn bộ clips sau khi chèn
    dumpSequenceClips();

    notify('Hoàn thành chèn ' + processedCount + ' mục vào timeline từ file: ' + tlFilePath.fsName);
    return processedCount;
}

// Allow override from runAll.jsx: when RUNALL_TIMELINE_CSV_PATH is defined, prefer that.
var csvDef;

if (typeof RUNALL_TIMELINE_CSV_PATH !== 'undefined' && RUNALL_TIMELINE_CSV_PATH) {
    // runAll.jsx truyền đường dẫn cụ thể
    csvDef = RUNALL_TIMELINE_CSV_PATH;
} else {
    // fallback: dùng data_folder/timeline_export_merged.csv (AI đã sinh)
    csvDef = joinPath(DATA_FOLDER, 'timeline_export_merged.csv');
}

cutAndPushAllTimeline(csvDef);
