// =============================================================
// SCRIPT: MAGNETIC CUT + FORCE DELETE ALL AUDIO
// =============================================================

var ENABLE_ALERTS = true; 

function notify(msg) {
    $.writeln('[Script] ' + msg);
    if (ENABLE_ALERTS) { try { alert(msg); } catch(e){} }
}

// =============================================================
// 1. CONFIG & HELPERS
// =============================================================
var INDEX_PAD = 4; 

function _joinPath(a, b) {
    if (!a) return b || '';
    if (!b) return a || '';
    var s = a.charAt(a.length - 1);
    return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

function _fileExists(p) {
    try { return new File(p).exists; } catch (e) { return false; }
}

function _readTextFile(p) {
    try {
        var f = new File(p);
        if (!f.exists || !f.open('r')) return '';
        var t = f.read();
        f.close();
        return t;
    } catch (e) { return ''; }
}

function getDataFolderSafe() {
    try {
        var scriptFile = new File($.fileName);
        var rootDir = scriptFile.parent.parent.parent; 
        var rootDataPath = _joinPath(rootDir.fsName, 'data');
        var pathTxt = _joinPath(rootDataPath, 'path.txt');
        
        if (_fileExists(pathTxt)) {
            var content = _readTextFile(pathTxt);
            var lines = content.split('\n');
            var dataFolder = "";
            var projectSlug = "";
            for (var i = 0; i < lines.length; i++) {
                var parts = lines[i].split('=');
                if (parts.length >= 2) {
                    var k = parts[0].replace(/^\s+|\s+$/g, '');
                    var v = parts.slice(1).join('=').replace(/^\s+|\s+$/g, '');
                    if (k === 'data_folder') dataFolder = v;
                    if (k === 'project_slug') projectSlug = v;
                }
            }
            var subFolder = dataFolder || projectSlug;
            if (subFolder) {
                if (subFolder.indexOf(':') > 0 || subFolder.indexOf('/') === 0) {
                    if (new Folder(subFolder).exists) return subFolder;
                } else {
                    var fullPath = _joinPath(rootDataPath, subFolder);
                    if (new Folder(fullPath).exists) return fullPath;
                }
            }
        }
        return rootDataPath;
    } catch (e) { return Folder.desktop.fsName; }
}

// =============================================================
// 2. CSV PARSER
// =============================================================
function splitCSVLine(line) {
    var res = [];
    var cur = '';
    var inQ = false;
    for (var i = 0; i < line.length; i++) {
        var ch = line.charAt(i);
        if (inQ) {
            if (ch === '"') {
                if (i + 1 < line.length && line.charAt(i + 1) === '"') { cur += '"'; i++; } 
                else { inQ = false; }
            } else { cur += ch; }
        } else {
            if (ch === ',') { res.push(cur); cur = ''; } 
            else if (ch === '"') { inQ = true; } 
            else { cur += ch; }
        }
    }
    res.push(cur);
    return res;
}

function readTimelineCSVFile(filePath) {
    try {
        var f = new File(filePath);
        if (!f.exists || !f.open('r')) return [];
        var lines = [];
        while (!f.eof) {
            var l = f.readln();
            if (l.length > 0) lines.push(l);
        }
        f.close();
        if (lines.length < 2) return []; 
        if (lines[0].charCodeAt(0) === 65279) lines[0] = lines[0].substring(1);

        var headerCols = splitCSVLine(lines[0]);
        var headerMap = {};
        for (var i = 0; i < headerCols.length; i++) headerMap[headerCols[i].toLowerCase().replace(/^\s+|\s+$/g, '')] = i;

        function getCol(names) {
            for (var k = 0; k < names.length; k++) if (headerMap.hasOwnProperty(names[k])) return headerMap[names[k]];
            return -1;
        }

        var idxSrcS = getCol(['src_start', 'source_start', 'start_sec']);
        var idxSrcE = getCol(['src_end', 'source_end', 'end_sec']);
        var idxDur = getCol(['duration', 'duration_sec']);
        var idxVidIx = getCol(['video_index', 'videoidx']);
        var idxBin = getCol(['bin_name', 'keyword', 'name']);
        var idxChar = getCol(['character', 'char']);

        var out = [];
        for (var r = 1; r < lines.length; r++) {
            var cols = splitCSVLine(lines[r]);
            if (cols.length < 2) continue;

            var srcS = (idxSrcS >= 0) ? parseFloat(cols[idxSrcS]) : 0;
            var srcE = (idxSrcE >= 0) ? parseFloat(cols[idxSrcE]) : 0;
            var duration = 0;
            if (srcE > srcS) duration = srcE - srcS;
            else if (idxDur >= 0) duration = parseFloat(cols[idxDur]);

            if (duration <= 0.1) continue; 

            var bName = (idxBin >= 0) ? cols[idxBin] : '';
            var cName = (idxChar >= 0) ? cols[idxChar] : '';
            var vIdx = (idxVidIx >= 0) ? parseInt(cols[idxVidIx], 10) : 0;
            if (isNaN(vIdx)) vIdx = 0;

            out.push({
                binName: bName,
                character: cName,
                srcStart: srcS,
                srcEnd: srcE,
                duration: duration,
                videoIndex: vIdx
            });
        }
        return out;
    } catch(e) { $.writeln('[CSV ERROR] ' + e); return []; }
}

// =============================================================
// 3. ITEM FINDER
// =============================================================
function isVideoFile(item) {
    if (!item) return false;
    var name = String(item.name).toLowerCase();
    if (name.match(/\.(jpg|jpeg|png|gif|bmp|tiff|psd|ai)$/i)) return false;
    if (item.type === 3) return false;
    return true;
}

function binHasVideo(binItem) {
    if (!binItem || !binItem.children) return false;
    for (var i = 0; i < binItem.children.numItems; i++) {
        var it = binItem.children[i];
        if (it.type === 1 && isVideoFile(it)) return true;
    }
    return false;
}

function normalizeName(name) {
    if (!name) return "";
    return String(name).toLowerCase().replace(/^\d+[_\-\.]/, '').replace(/[_\-\.]/g, ' ').replace(/^\s+|\s+$/g, '');
}

function _findBinByNameOrAlias(binName) {
    if (!app.project || !app.project.rootItem) return null;
    if (!binName) return null;
    var reqNorm = normalizeName(binName);
    var candidates = [];
    findBinsRecursive(app.project.rootItem, reqNorm, candidates);
    if (candidates.length === 0) return null;
    
    for (var i = 0; i < candidates.length; i++) {
        if (candidates[i].name.toLowerCase().indexOf("img_") === -1 && binHasVideo(candidates[i])) return candidates[i];
    }
    for (var j = 0; j < candidates.length; j++) if (binHasVideo(candidates[j])) return candidates[j];
    return candidates[0];
}

function findBinsRecursive(folder, reqNorm, results) {
    if (!folder.children) return;
    for (var i = 0; i < folder.children.numItems; i++) {
        var it = folder.children[i];
        if (it.type === 2) { 
            var itNorm = normalizeName(it.name);
            if (itNorm.indexOf(reqNorm) >= 0 || reqNorm.indexOf(itNorm) >= 0) results.push(it);
            findBinsRecursive(it, reqNorm, results);
        }
    }
}

function padNumber(num, size) {
    var s = num + "";
    while (s.length < size) s = "0" + s;
    return s;
}

function resolveClipFromBin(binItem, idx) {
    if (!binItem || idx < 0) return null;
    var clips = [];
    for (var i = 0; i < binItem.children.numItems; i++) {
        var it = binItem.children[i];
        if (it && it.type === 1 && isVideoFile(it)) clips.push(it);
    }
    if (clips.length === 0) return null;
    var searchKey = padNumber(idx, INDEX_PAD); 
    for (var j = 0; j < clips.length; j++) if (clips[j].name.indexOf(searchKey) === 0) return clips[j];
    return clips[idx % clips.length];
}

// =============================================================
// 4. CLEANUP (DELETE ALL AUDIO & CLOSE GAPS)
// =============================================================

function deleteAllAudioTracks(seq) {
    if (!seq) return;
    // Duyet qua tat ca Audio Tracks
    for (var i = 0; i < seq.audioTracks.numTracks; i++) {
        var track = seq.audioTracks[i];
        // Xoa sach clip tren track nay
        if (track.clips.numItems > 0) {
            // Duyet nguoc va xoa
            for (var j = track.clips.numItems - 1; j >= 0; j--) {
                try {
                    track.clips[j].remove(0, 0); // Xoa thang tay
                } catch(e) {}
            }
        }
    }
}

function closeGaps(track) {
    // Ham don gian: Don tat ca clip ve phia truoc neu co khoang den
    if (!track || track.clips.numItems < 2) return;
    
    var previousEnd = 0;
    for (var i = 0; i < track.clips.numItems; i++) {
        var clip = track.clips[i];
        var currentStart = clip.start.seconds;
        
        // Neu co khoang den > 0.05s
        if (currentStart > previousEnd + 0.05) {
            // Move clip ve previousEnd
            var duration = clip.end.seconds - clip.start.seconds;
            clip.start = previousEnd;
            clip.end = previousEnd + duration;
        }
        previousEnd = clip.end.seconds;
    }
}

// =============================================================
// 5. MAIN PROCESS
// =============================================================

function processTimeline(csvPath) {
    var proj = app.project;
    if (!proj) return;
    var seq = proj.activeSequence;
    if (!seq) { alert("Vui long mo Sequence truoc!"); return; }
    
    var trackV1 = seq.videoTracks[0]; 
    var trackV2 = (seq.videoTracks.numTracks > 1) ? seq.videoTracks[1] : null; 

    var entries = readTimelineCSVFile(csvPath);
    if (entries.length === 0) { alert("File CSV rong!"); return; }

    $.writeln('=== BAT DAU CAT (MAGNETIC MODE) ===');
    var successCount = 0;
    var cursorTime = 0;

    for (var i = 0; i < entries.length; i++) {
        var item = entries[i];
        
        var binItem = _findBinByNameOrAlias(item.binName);
        if (!binItem && item.character) binItem = _findBinByNameOrAlias(item.character);
        if (!binItem) { $.writeln('[SKIP] Line '+(i+1)+': Bin not found'); continue; }
        
        var clipItem = resolveClipFromBin(binItem, item.videoIndex);
        if (!clipItem) { $.writeln('[SKIP] Line '+(i+1)+': Clip not found'); continue; }

        var inPoint = item.srcStart;
        var outPoint = item.srcEnd;
        var duration = outPoint - inPoint;
        
        if (duration <= 0.1) {
             inPoint = 0;
             duration = item.duration;
             outPoint = duration;
        }

        try {
            // Set In/Out
            try { clipItem.clearInPoint(4); clipItem.clearOutPoint(4); } catch(e){}
            try { clipItem.setInPoint(inPoint, 4); clipItem.setOutPoint(outPoint, 4); } catch(e){}

            // === INSERT LOGIC (MAGNETIC) ===
            // Luon chen tai cursorTime hien tai
            trackV1.overwriteClip(clipItem, cursorTime);
            
            // Track 2 (Label)
            if (trackV2) {
                trackV2.overwriteClip(clipItem, cursorTime);
                
                // Tim clip vua chen de chinh sua
                var checkT = cursorTime + 0.01;
                for (var k=0; k<trackV2.clips.numItems; k++){
                    var c = trackV2.clips[k];
                    if (c.start.seconds <= checkT && c.end.seconds > checkT) {
                        c.name = item.binName; // Doi ten
                        c.disabled = true;     // Tat mat
                        break;
                    }
                }
            }

            $.writeln('[OK] ' + item.binName + ' inserted at ' + cursorTime.toFixed(2) + 's');
            
            // CAP NHAT CON TRO: Nhay den cuoi clip vua chen
            cursorTime += duration; 
            successCount++;

        } catch (e) {
            $.writeln('[ERR] ' + e);
        }
    }
    
    // === FINAL CLEANUP: DELETE ALL AUDIO & CLOSE GAPS ===
    $.writeln('[INFO] Deleting ALL Audio Tracks...');
    deleteAllAudioTracks(seq);
    
    $.writeln('[INFO] Cleaning up visual gaps...');
    closeGaps(trackV1);
    if (trackV2) closeGaps(trackV2);

    notify("Hoan tat: " + successCount + " clips. Audio da xoa sach se.");
}

// =============================================================
// RUN
// =============================================================
var csvToRun = "";
if (typeof RUNALL_TIMELINE_CSV_PATH !== 'undefined' && RUNALL_TIMELINE_CSV_PATH) {
    csvToRun = RUNALL_TIMELINE_CSV_PATH;
} else {
    var safeDataDir = getDataFolderSafe();
    var f1 = _joinPath(safeDataDir, 'timeline_export_merged.csv');
    var f2 = _joinPath(safeDataDir, 'timeline_export.csv');
    if (_fileExists(f1)) csvToRun = f1; else if (_fileExists(f2)) csvToRun = f2;
}

if (csvToRun && _fileExists(csvToRun)) {
    processTimeline(csvToRun);
} else {
    alert("Khong tim thay CSV!");
}