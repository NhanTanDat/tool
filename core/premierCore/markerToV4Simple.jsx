/**
 * markerToV4Simple.jsx
 *
 * Workflow don gian:
 * 1. Doc sequence markers
 * 2. Tim video trong resource folder khop voi keyword (ten file)
 * 3. Do clip vao V4 tai vi tri marker
 *
 * Khong can AI - chi dua vao ten file video match voi keyword trong marker
 */

var PERF_START = new Date().getTime();

function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[markerToV4 ' + elapsed + 's] ' + msg); } catch (e) {}
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

// ============== TICKS CONVERSION ==============
var TICKS_PER_SECOND = 254016000000;

function secondsToTicks(seconds) {
    return Math.floor(seconds * TICKS_PER_SECOND);
}

function ticksToSeconds(ticks) {
    return ticks / TICKS_PER_SECOND;
}

// ============== READ MARKERS ==============
function getMarkersFromSequence(sequence) {
    var markers = [];

    if (!sequence || !sequence.markers) {
        log('ERROR: No sequence or markers');
        return markers;
    }

    var seqMarkers = sequence.markers;
    log('Reading sequence markers...');
    log('Markers object: ' + typeof seqMarkers);

    // Method 1: numMarkers property
    if (typeof seqMarkers.numMarkers !== 'undefined' && seqMarkers.numMarkers > 0) {
        log('Using numMarkers: ' + seqMarkers.numMarkers);
        for (var i = 0; i < seqMarkers.numMarkers; i++) {
            var m = seqMarkers[i];
            if (m) {
                var markerData = extractMarkerData(m, i);
                if (markerData) markers.push(markerData);
            }
        }
    }

    // Method 2: Try iteration if no markers found
    if (markers.length === 0) {
        log('Trying iteration method...');
        try {
            for (var j = 0; j < 100; j++) {
                var m2 = null;
                try { m2 = seqMarkers[j]; } catch (e) { break; }
                if (!m2) break;
                var markerData2 = extractMarkerData(m2, j);
                if (markerData2) markers.push(markerData2);
            }
        } catch (e) {
            log('Iteration error: ' + e);
        }
    }

    log('Found ' + markers.length + ' markers');
    return markers;
}

function extractMarkerData(marker, index) {
    if (!marker) return null;

    try {
        var keyword = marker.name || marker.comments || '';
        keyword = keyword.replace(/^\s+|\s+$/g, '');

        if (!keyword || keyword.length === 0) {
            log('Marker ' + index + ': empty name, skip');
            return null;
        }

        // Get timing
        var startTicks = 0;
        var endTicks = 0;

        if (marker.start && marker.start.ticks) {
            startTicks = marker.start.ticks;
        } else if (typeof marker.start === 'number') {
            startTicks = marker.start;
        }

        if (marker.end && marker.end.ticks) {
            endTicks = marker.end.ticks;
        } else if (typeof marker.end === 'number') {
            endTicks = marker.end;
        }

        var startSec = ticksToSeconds(startTicks);
        var endSec = ticksToSeconds(endTicks);

        // Default duration 5 seconds if no end
        if (endSec <= startSec) {
            endSec = startSec + 5.0;
        }

        log('Marker ' + index + ': "' + keyword + '" at ' + startSec.toFixed(2) + 's - ' + endSec.toFixed(2) + 's');

        return {
            index: index,
            keyword: keyword,
            startSeconds: startSec,
            endSeconds: endSec,
            durationSeconds: endSec - startSec
        };
    } catch (e) {
        log('ERROR extracting marker ' + index + ': ' + e);
        return null;
    }
}

// ============== FIND VIDEO FILES ==============
function getVideoFilesFromFolder(folderPath) {
    var videos = [];
    var folder = new Folder(folderPath);

    if (!folder.exists) {
        log('ERROR: Folder not found: ' + folderPath);
        return videos;
    }

    // Get all video files
    var extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.webm', '*.MP4', '*.MOV'];

    for (var e = 0; e < extensions.length; e++) {
        var files = folder.getFiles(extensions[e]);
        for (var f = 0; f < files.length; f++) {
            videos.push({
                path: normalizePath(files[f].fsName),
                name: files[f].name,
                nameNoExt: files[f].name.replace(/\.[^.]+$/, '').toLowerCase()
            });
        }
    }

    log('Found ' + videos.length + ' videos in folder');
    return videos;
}

function findVideoForKeyword(keyword, videoFiles) {
    keyword = keyword.toLowerCase().replace(/^\s+|\s+$/g, '');

    // 1. Exact match (filename without extension)
    for (var i = 0; i < videoFiles.length; i++) {
        if (videoFiles[i].nameNoExt === keyword) {
            log('  Exact match: ' + videoFiles[i].name);
            return videoFiles[i];
        }
    }

    // 2. Keyword contained in filename
    for (var j = 0; j < videoFiles.length; j++) {
        if (videoFiles[j].nameNoExt.indexOf(keyword) !== -1) {
            log('  Partial match: ' + videoFiles[j].name);
            return videoFiles[j];
        }
    }

    // 3. Filename contained in keyword
    for (var k = 0; k < videoFiles.length; k++) {
        if (keyword.indexOf(videoFiles[k].nameNoExt) !== -1) {
            log('  Reverse match: ' + videoFiles[k].name);
            return videoFiles[k];
        }
    }

    log('  No match found for: ' + keyword);
    return null;
}

// ============== PROJECT ITEMS ==============
var importedCache = {};

function findOrImportVideo(videoPath, resourceBin) {
    videoPath = normalizePath(videoPath);

    // Check cache
    if (importedCache[videoPath]) {
        return importedCache[videoPath];
    }

    // Search in project
    var rootItem = app.project.rootItem;
    for (var i = rootItem.children.numItems - 1; i >= 0; i--) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                importedCache[videoPath] = item;
                return item;
            }
        }
        if (item.type === ProjectItemType.BIN) {
            var found = searchInBin(item, videoPath);
            if (found) {
                importedCache[videoPath] = found;
                return found;
            }
        }
    }

    // Import
    if (!fileExists(videoPath)) {
        log('ERROR: File not found: ' + videoPath);
        return null;
    }

    try {
        app.project.importFiles([videoPath], true, resourceBin, false);
        // Get last imported item
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

function searchInBin(bin, videoPath) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var item = bin.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                return item;
            }
        }
        if (item.type === ProjectItemType.BIN) {
            var found = searchInBin(item, videoPath);
            if (found) return found;
        }
    }
    return null;
}

function findOrCreateBin(binName) {
    var rootItem = app.project.rootItem;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.BIN && item.name === binName) {
            return item;
        }
    }
    return rootItem.createBin(binName);
}

// ============== INSERT CLIP TO V4 ==============
function insertClipToV4(sequence, projectItem, timelineStart, timelineDuration) {
    if (!sequence || !projectItem) {
        log('ERROR: Invalid sequence or projectItem');
        return false;
    }

    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks < 4) {
        log('ERROR: Need at least 4 video tracks, have ' + videoTracks.numTracks);
        return false;
    }

    var v4 = videoTracks[3]; // Video Track 4 = index 3
    var clipCountBefore = v4.clips.numItems;

    try {
        var timelineStartTicks = secondsToTicks(timelineStart);
        var timelinePos = new Time();
        timelinePos.ticks = timelineStartTicks;

        // Insert clip at timeline position
        v4.insertClip(projectItem, timelinePos);

        // Get the inserted clip
        var insertedClip = null;
        if (v4.clips.numItems > clipCountBefore) {
            insertedClip = v4.clips[v4.clips.numItems - 1];
        }

        if (insertedClip && timelineDuration > 0) {
            // Get source clip duration
            var clipDuration = ticksToSeconds(insertedClip.end.ticks - insertedClip.start.ticks);

            // Use smaller of clip duration or required duration
            var actualDuration = Math.min(clipDuration, timelineDuration);

            // Set timeline END position to control duration
            var newEnd = new Time();
            newEnd.ticks = timelineStartTicks + secondsToTicks(actualDuration);
            insertedClip.end = newEnd;

            if (clipDuration > timelineDuration) {
                log('  Trimmed to ' + timelineDuration.toFixed(2) + 's');
            }
        }

        log('  Inserted at ' + timelineStart.toFixed(2) + 's');
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
    log('   MARKER TO V4 - SIMPLE WORKFLOW');
    log('========================================');

    // Read config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Khong tim thay data/path.txt');
        return;
    }

    var resourceFolder = normalizePath(cfg.resource_folder || '');
    if (!resourceFolder) {
        alert('ERROR: resource_folder chua duoc dinh nghia trong path.txt');
        return;
    }

    log('Resource folder: ' + resourceFolder);

    // Get active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Hay mo mot sequence truoc!');
        return;
    }

    log('Sequence: ' + seq.name);

    // Check V4 track exists
    if (seq.videoTracks.numTracks < 4) {
        alert('ERROR: Sequence can co it nhat 4 video tracks.\nHien tai chi co ' + seq.videoTracks.numTracks + ' tracks.');
        return;
    }

    // Step 1: Read markers
    log('\n=== STEP 1: Doc Markers ===');
    var markers = getMarkersFromSequence(seq);

    if (markers.length === 0) {
        alert('Khong tim thay marker nao!\n\nHuong dan tao marker:\n1. Click vao vung trong tren timeline\n2. Di chuyen playhead den vi tri can danh dau\n3. Nhan M de tao marker\n4. Double-click marker, nhap ten (keyword)');
        return;
    }

    log('Tim thay ' + markers.length + ' markers');

    // Step 2: Get video files
    log('\n=== STEP 2: Doc Video Files ===');
    var videoFiles = getVideoFilesFromFolder(resourceFolder);

    if (videoFiles.length === 0) {
        alert('Khong tim thay video nao trong:\n' + resourceFolder);
        return;
    }

    // Step 3: Match and insert
    log('\n=== STEP 3: Match & Insert ===');
    var resourceBin = findOrCreateBin('MarkerVideos');
    var successCount = 0;
    var failedCount = 0;

    for (var i = 0; i < markers.length; i++) {
        var marker = markers[i];
        log('\n[' + (i + 1) + '/' + markers.length + '] "' + marker.keyword + '"');

        // Find matching video
        var matchedVideo = findVideoForKeyword(marker.keyword, videoFiles);

        if (!matchedVideo) {
            log('  SKIP: No matching video');
            failedCount++;
            continue;
        }

        // Import/find in project
        var projectItem = findOrImportVideo(matchedVideo.path, resourceBin);

        if (!projectItem) {
            log('  ERROR: Could not import video');
            failedCount++;
            continue;
        }

        // Insert to V4
        var success = insertClipToV4(
            seq,
            projectItem,
            marker.startSeconds,
            marker.durationSeconds
        );

        if (success) {
            successCount++;
        } else {
            failedCount++;
        }
    }

    // Summary
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);
    log('\n========================================');
    log('   HOAN THANH');
    log('========================================');
    log('Markers:   ' + markers.length);
    log('Success:   ' + successCount);
    log('Failed:    ' + failedCount);
    log('Time:      ' + elapsed + 's');
    log('========================================');

    // Save project
    if (successCount > 0) {
        app.project.save();
        log('Project saved');
    }

    alert('Hoan thanh!\n\nMarkers: ' + markers.length + '\nSuccess: ' + successCount + '\nFailed: ' + failedCount);
}

// Run
main();
