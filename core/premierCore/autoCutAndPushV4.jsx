/**
 * autoCutAndPushV4.jsx
 *
 * Đọc genmini_map.json (đã có sẵn keyword-to-video mappings)
 * Tự động tìm video files và đẩy vào V4 theo đúng timeline
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
 * Tìm video file trong resource folder theo tên
 */
function findVideoByName(resourceFolder, videoName) {
    // videoName có thể là: "1_Tony_Dow_best_moments"
    // Cần tìm file video có tên tương tự trong resource folder

    var folder = new Folder(resourceFolder);
    if (!folder.exists) {
        log('ERROR: Resource folder not found: ' + resourceFolder);
        return null;
    }

    // Các extension video phổ biến
    var videoExts = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.flv', '.wmv', '.webm'];

    // Thử tìm file trực tiếp với từng extension
    for (var i = 0; i < videoExts.length; i++) {
        var filePath = joinPath(resourceFolder, videoName + videoExts[i]);
        if (fileExists(filePath)) {
            log('Found video: ' + filePath);
            return filePath;
        }
    }

    // Nếu không tìm thấy, thử tìm file có chứa videoName
    var files = folder.getFiles();
    for (var i = 0; i < files.length; i++) {
        var file = files[i];
        if (file instanceof File) {
            var fileName = file.name.toLowerCase();
            var searchName = videoName.toLowerCase();

            // Check nếu là video file và tên chứa searchName
            var isVideo = false;
            for (var j = 0; j < videoExts.length; j++) {
                if (fileName.indexOf(videoExts[j]) !== -1) {
                    isVideo = true;
                    break;
                }
            }

            if (isVideo && fileName.indexOf(searchName) !== -1) {
                log('Found video (partial match): ' + file.fsName);
                return normalizePath(file.fsName);
            }
        }
    }

    log('ERROR: Video not found for name: ' + videoName);
    return null;
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
 * Nếu sceneStart và sceneEnd = 0, sẽ dùng toàn bộ video
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

    // Nếu không có scene timing, dùng toàn bộ video
    var useFullVideo = (sceneStart === 0 && sceneEnd === 0);

    if (useFullVideo) {
        log('Using full video (no scene timing specified)');
        log('Push to V4 at: ' + timelineStart + 's (duration: ' + timelineDuration + 's)');
    } else {
        log('Cut scene: ' + sceneStart + 's - ' + sceneEnd + 's');
        log('Push to V4 at: ' + timelineStart + 's (duration: ' + timelineDuration + 's)');
    }

    // Chuyển sang ticks
    var timelineStartTicks = secondsToTicks(timelineStart);
    var requiredDurationTicks = secondsToTicks(timelineDuration);

    var inPoint, outPoint, sceneDurationTicks;

    if (useFullVideo) {
        // Dùng toàn bộ video, crop theo required duration
        inPoint = new Time();
        inPoint.ticks = 0;

        outPoint = new Time();
        outPoint.ticks = requiredDurationTicks;

        sceneDurationTicks = requiredDurationTicks;
    } else {
        // Dùng scene timing
        var sceneStartTicks = secondsToTicks(sceneStart);
        var sceneEndTicks = secondsToTicks(sceneEnd);
        sceneDurationTicks = sceneEndTicks - sceneStartTicks;

        inPoint = new Time();
        inPoint.ticks = sceneStartTicks;

        outPoint = new Time();
        outPoint.ticks = sceneEndTicks;
    }

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
 * Main processing - Đọc từ genmini_map.json
 */
function processGenminiMap(genminiMapPath, resourceFolder, sequence) {
    log('Loading genmini map: ' + genminiMapPath);

    if (!fileExists(genminiMapPath)) {
        log('ERROR: Genmini map file not found: ' + genminiMapPath);
        return 0;
    }

    var jsonContent = readFile(genminiMapPath);
    var data = parseJSON(jsonContent);

    if (!data) {
        log('ERROR: Cannot parse genmini_map.json');
        return 0;
    }

    var items = data.items || [];

    if (items.length === 0) {
        log('ERROR: No items found in genmini_map.json');
        return 0;
    }

    log('Processing ' + items.length + ' items');

    var resourceBin = findOrCreateBin('Genmini_Videos', app.project.rootItem);
    var successCount = 0;

    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var videoName = item.text || '';
        var startSec = parseFloat(item.startSeconds) || 0;
        var endSec = parseFloat(item.endSeconds) || 0;
        var durationSec = parseFloat(item.durationSeconds) || 0;
        var indexInTrack = item.indexInTrack || i;

        log('\n--- Item ' + (i + 1) + '/' + items.length + ': "' + videoName + '" ---');
        log('Timeline position: ' + startSec + 's - ' + endSec + 's (duration: ' + durationSec + 's)');

        if (!videoName || videoName.length === 0) {
            log('WARN: Empty video name, skipping');
            continue;
        }

        // Tìm video file trong resource folder
        var videoPath = findVideoByName(resourceFolder, videoName);
        if (!videoPath) {
            log('ERROR: Cannot find video file for: ' + videoName);
            continue;
        }

        // Import video
        var projectItem = findOrImportVideo(videoPath, resourceBin);
        if (!projectItem) {
            log('ERROR: Cannot import video: ' + videoPath);
            continue;
        }

        // Push to V4 (không có scene timing, dùng toàn bộ video)
        // sceneStart = 0, sceneEnd = 0 → cutAndPushToV4 sẽ dùng full video
        var success = cutAndPushToV4(
            sequence,
            projectItem,
            0, // sceneStart = 0 (use full video)
            0, // sceneEnd = 0 (use full video)
            startSec,
            durationSec
        );

        if (success) {
            successCount++;
        }
    }

    log('\n=== SUMMARY ===');
    log('Processed: ' + items.length + ' items');
    log('Success: ' + successCount);
    log('Failed: ' + (items.length - successCount));

    return successCount;
}

/**
 * Main function
 */
function main() {
    log('=== AUTO CUT AND PUSH TO V4 (từ genmini_map.json) ===');

    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Không tìm thấy data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    var resourceFolder = normalizePath(cfg.resource_folder || '');

    if (!dataFolder) {
        alert('ERROR: data_folder not defined in path.txt');
        return;
    }

    if (!resourceFolder) {
        alert('ERROR: resource_folder not defined in path.txt');
        return;
    }

    log('Data folder: ' + dataFolder);
    log('Resource folder: ' + resourceFolder);

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

    // Load genmini map
    var genminiMapPath = joinPath(dataFolder, 'genmini_map.json');

    var count = processGenminiMap(genminiMapPath, resourceFolder, seq);

    if (count > 0) {
        app.project.save();
        log('Project saved');
        alert('Đã xử lý thành công ' + count + ' videos và đẩy vào V4!');
    } else {
        alert('Không có video nào được xử lý. Xem log để biết chi tiết.');
    }

    log('=== DONE ===');
}

// Run
main();
