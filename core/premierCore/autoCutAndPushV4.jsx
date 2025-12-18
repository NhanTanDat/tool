/**
 * autoCutAndPushV4.jsx
 *
 * Đọc scene matches từ Python AI analysis
 * Tự động cắt video scenes và đẩy vào V4 theo đúng timeline của keywords trên V3
 */

function log(msg) {
    try { $.writeln('[autoCutV4] ' + msg); } catch (e) {}
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

function readFile(p) {
    var f = new File(p);
    if (!f.exists || !f.open('r')) return '';
    var content = f.read();
    f.close();
    return content;
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
 * Parse JSON (manual, vì ExtendScript không có JSON.parse)
 */
function parseJSON(jsonStr) {
    try {
        // Sử dụng eval (unsafe nhưng OK trong môi trường controlled)
        return eval('(' + jsonStr + ')');
    } catch (e) {
        log('ERROR parsing JSON: ' + e);
        return null;
    }
}

/**
 * Chuyển giây thành Ticks
 */
function secondsToTicks(seconds) {
    var TICKS_PER_SECOND = 254016000000;
    return Math.floor(seconds * TICKS_PER_SECOND);
}

/**
 * Tìm hoặc import video vào project
 */
function findOrImportVideo(videoPath, resourceBin) {
    videoPath = normalizePath(videoPath);

    // Tìm trong project items
    var rootItem = app.project.rootItem;
    for (var i = 0; i < rootItem.children.numItems; i++) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            var itemPath = normalizePath(item.getMediaPath());
            if (itemPath === videoPath) {
                log('Video already in project: ' + videoPath);
                return item;
            }
        }
    }

    // Nếu chưa có, import
    log('Importing video: ' + videoPath);
    if (!fileExists(videoPath)) {
        log('ERROR: Video file not found: ' + videoPath);
        return null;
    }

    try {
        var imported = app.project.importFiles([videoPath], true, resourceBin, false);
        if (imported && imported.length > 0) {
            log('Imported successfully');
            return app.project.rootItem.children[app.project.rootItem.children.numItems - 1];
        }
    } catch (e) {
        log('ERROR importing: ' + e);
    }

    return null;
}

/**
 * Tìm hoặc tạo bin
 */
function findOrCreateBin(binName, parentBin) {
    if (!parentBin) parentBin = app.project.rootItem;

    // Tìm bin
    for (var i = 0; i < parentBin.children.numItems; i++) {
        var item = parentBin.children[i];
        if (item.type === ProjectItemType.BIN && item.name === binName) {
            return item;
        }
    }

    // Tạo mới
    log('Creating bin: ' + binName);
    return parentBin.createBin(binName);
}

/**
 * Cắt và đẩy scene vào V4
 */
function cutAndPushToV4(
    sequence,
    projectItem,
    sceneStart,
    sceneEnd,
    timelineStart,
    timelineDuration
) {
    if (!sequence || !projectItem) {
        log('ERROR: Invalid sequence or projectItem');
        return false;
    }

    log('Cut scene: ' + sceneStart + 's - ' + sceneEnd + 's');
    log('Push to V4 at: ' + timelineStart + 's (duration: ' + timelineDuration + 's)');

    // Chuyển sang ticks
    var sceneStartTicks = secondsToTicks(sceneStart);
    var sceneEndTicks = secondsToTicks(sceneEnd);
    var timelineStartTicks = secondsToTicks(timelineStart);
    var sceneDurationTicks = sceneEndTicks - sceneStartTicks;
    var requiredDurationTicks = secondsToTicks(timelineDuration);

    // Tạo Time object
    var inPoint = new Time();
    inPoint.ticks = sceneStartTicks;

    var outPoint = new Time();
    outPoint.ticks = sceneEndTicks;

    // Nếu scene ngắn hơn required duration, lấy hết
    // Nếu dài hơn, có thể crop hoặc scale (ở đây ta lấy đúng scene duration)

    // Video track 4 = index 3 (0-based)
    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks < 4) {
        log('ERROR: Sequence không có Video Track 4');
        return false;
    }

    var v4 = videoTracks[3]; // Track 4 = index 3

    // Insert clip
    try {
        var timelinePos = new Time();
        timelinePos.ticks = timelineStartTicks;

        // overwriteClip: (clip, trackIndex, time)
        // Hoặc insertClip để không overwrite

        // Set in/out points trên projectItem (nếu API hỗ trợ)
        // Với Premiere API, cách chính xác là:
        v4.insertClip(projectItem, timelinePos);

        // Lấy clip vừa insert
        var insertedClip = null;
        for (var i = v4.clips.numItems - 1; i >= 0; i--) {
            var clip = v4.clips[i];
            if (Math.abs(clip.start.ticks - timelineStartTicks) < 1000000) { // tolerance
                insertedClip = clip;
                break;
            }
        }

        if (insertedClip) {
            // Set in/out point của clip
            insertedClip.inPoint = inPoint;
            insertedClip.outPoint = outPoint;

            // Điều chỉnh duration nếu cần (crop/extend)
            if (sceneDurationTicks > requiredDurationTicks) {
                // Scene dài hơn → crop
                log('Scene longer than required, cropping');
                var newOut = new Time();
                newOut.ticks = sceneStartTicks + requiredDurationTicks;
                insertedClip.outPoint = newOut;
            } else if (sceneDurationTicks < requiredDurationTicks) {
                // Scene ngắn hơn → có thể speed up hoặc repeat (advanced)
                log('WARN: Scene shorter than required (' + (sceneEnd - sceneStart) + 's vs ' + timelineDuration + 's)');
            }

            log('SUCCESS: Inserted and configured clip on V4');
            return true;
        } else {
            log('WARN: Could not find inserted clip to configure');
            return true; // Vẫn insert được, chỉ không config được
        }

    } catch (e) {
        log('ERROR inserting clip: ' + e);
        return false;
    }
}

/**
 * Main processing
 */
function processSceneMatches(sceneMatchesPath, sequence) {
    log('Loading scene matches: ' + sceneMatchesPath);

    if (!fileExists(sceneMatchesPath)) {
        log('ERROR: Scene matches file not found: ' + sceneMatchesPath);
        return 0;
    }

    var jsonContent = readFile(sceneMatchesPath);
    var data = parseJSON(jsonContent);

    if (!data) {
        log('ERROR: Cannot parse scene matches JSON');
        return 0;
    }

    var keywords = data.keywords || [];
    var matches = data.matches || {};

    log('Processing ' + keywords.length + ' keywords');

    var resourceBin = findOrCreateBin('AI_Matched_Scenes', app.project.rootItem);
    var successCount = 0;

    for (var i = 0; i < keywords.length; i++) {
        var kwItem = keywords[i];
        var keyword = kwItem.keyword;
        var startSec = kwItem.start_seconds;
        var endSec = kwItem.end_seconds;
        var durationSec = kwItem.duration_seconds;

        log('\n--- Keyword ' + (i + 1) + '/' + keywords.length + ': "' + keyword + '" ---');
        log('Timeline position: ' + startSec + 's - ' + endSec + 's');

        var keywordMatches = matches[keyword];
        if (!keywordMatches || keywordMatches.length === 0) {
            log('WARN: No matches found for keyword "' + keyword + '"');
            continue;
        }

        // Lấy best match (đầu tiên, đã sort by confidence)
        var bestMatch = keywordMatches[0];
        var videoPath = bestMatch.video_path;
        var suggestedScenes = bestMatch.suggested_scenes || [];

        if (suggestedScenes.length === 0) {
            log('WARN: No suggested scenes for "' + keyword + '"');
            continue;
        }

        // Lấy scene đầu tiên
        var scene = suggestedScenes[0];
        var sceneStart = parseFloat(scene.start_time) || 0;
        var sceneEnd = parseFloat(scene.end_time) || 0;

        log('Best match: ' + videoPath);
        log('Scene: ' + sceneStart + 's - ' + sceneEnd + 's');

        // Import video
        var projectItem = findOrImportVideo(videoPath, resourceBin);
        if (!projectItem) {
            log('ERROR: Cannot import video');
            continue;
        }

        // Cut and push to V4
        var success = cutAndPushToV4(
            sequence,
            projectItem,
            sceneStart,
            sceneEnd,
            startSec,
            durationSec
        );

        if (success) {
            successCount++;
        }
    }

    log('\n=== SUMMARY ===');
    log('Processed: ' + keywords.length + ' keywords');
    log('Success: ' + successCount);
    log('Failed: ' + (keywords.length - successCount));

    return successCount;
}

/**
 * Main function
 */
function main() {
    log('=== AUTO CUT AND PUSH TO V4 ===');

    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Không tìm thấy data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    if (!dataFolder) {
        alert('ERROR: data_folder not defined');
        return;
    }

    log('Data folder: ' + dataFolder);

    // Get active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Không có sequence nào được mở.\nHãy mở sequence trước.');
        return;
    }

    log('Active sequence: ' + seq.name);

    // Check if V4 exists
    if (seq.videoTracks.numTracks < 4) {
        alert('ERROR: Sequence cần có ít nhất 4 video tracks.\nHiện tại chỉ có ' + seq.videoTracks.numTracks + ' tracks.');
        return;
    }

    // Load scene matches
    var sceneMatchesPath = joinPath(dataFolder, 'scene_matches.json');

    var count = processSceneMatches(sceneMatchesPath, seq);

    if (count > 0) {
        app.project.save();
        log('Project saved');
        alert('Đã xử lý thành công ' + count + ' keywords và đẩy vào V4!');
    } else {
        alert('Không có keyword nào được xử lý. Xem log để biết chi tiết.');
    }

    log('=== DONE ===');
}

// Run
main();
