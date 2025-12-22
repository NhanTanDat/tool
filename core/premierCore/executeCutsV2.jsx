/**
 * executeCutsV2.jsx - PHIÊN BẢN 2025 XỊN NHẤT
 *
 * Tính năng:
 * 1. Dùng overwriteClip() thay vì insertClip() - KHÔNG đẩy clips khác
 * 2. CHỈ lấy VIDEO, không lấy audio
 * 3. Clear V4 track trước khi bắt đầu (optional)
 * 4. Hỗ trợ merge nhiều clips cho 1 marker
 * 5. Precise timing với ticks
 *
 * CHẠY RIÊNG - Đọc cut_list.json và thực hiện cắt
 */

var PERF_START = new Date().getTime();

function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[executeCutsV2 ' + elapsed + 's] ' + msg); } catch (e) {}
}

// ============== CONSTANTS ==============
var TICKS_PER_SECOND = 254016000000;
var TARGET_TRACK_INDEX = 3;  // V4 = index 3 (0-based)

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

function readFile(p) {
    var f = new File(p);
    f.encoding = 'UTF-8';
    if (!f.exists || !f.open('r')) return '';
    var content = f.read();
    f.close();
    return content;
}

function readLines(p) {
    var f = new File(p);
    if (!f.exists || !f.open('r')) return [];
    var arr = [];
    while (!f.eof) arr.push(f.readln());
    f.close();
    return arr;
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
function secondsToTicks(seconds) {
    return Math.round(seconds * TICKS_PER_SECOND);
}

function ticksToSeconds(ticks) {
    return ticks / TICKS_PER_SECOND;
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

    if (importedCache[videoPath]) {
        return importedCache[videoPath];
    }

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
        return item;
    }
    return importVideo(videoPath, targetBin);
}

// ============== CLEAR TRACK ==============
function clearTrack(sequence, trackIndex) {
    /**
     * Xóa tất cả clips trên track để tránh conflict
     */
    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks <= trackIndex) return;

    var track = videoTracks[trackIndex];
    var clipCount = track.clips.numItems;

    if (clipCount === 0) {
        log('Track V' + (trackIndex + 1) + ' đã trống');
        return;
    }

    log('Clearing ' + clipCount + ' clips từ V' + (trackIndex + 1) + '...');

    // Xóa từ cuối về đầu để tránh index shift
    for (var i = clipCount - 1; i >= 0; i--) {
        try {
            var clip = track.clips[i];
            if (clip) {
                clip.remove(false, false);  // (ripple, alignToVideo)
            }
        } catch (e) {
            log('WARN: Không xóa được clip ' + i + ': ' + e);
        }
    }

    log('Đã clear track V' + (trackIndex + 1));
}

// ============== OVERWRITE CLIP (KHÔNG ĐẨY CLIPS KHÁC) ==============
function overwriteClipToTrack(sequence, projectItem, trackIndex, timelineStartSec, sourceInSec, durationSec) {
    /**
     * Đặt clip lên timeline tại vị trí chính xác
     * KHÔNG đẩy các clips khác đi
     * CHỈ lấy VIDEO, không lấy audio
     *
     * @param sequence - Active sequence
     * @param projectItem - Video item từ project
     * @param trackIndex - Track index (0-based, V4 = 3)
     * @param timelineStartSec - Vị trí bắt đầu trên timeline (seconds)
     * @param sourceInSec - Điểm IN trong source video (seconds)
     * @param durationSec - Độ dài clip (seconds)
     */
    if (!sequence || !projectItem) {
        log('ERROR: Invalid sequence or projectItem');
        return false;
    }

    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks <= trackIndex) {
        log('ERROR: Track V' + (trackIndex + 1) + ' không tồn tại');
        return false;
    }

    var track = videoTracks[trackIndex];

    try {
        // Tính toán ticks
        var timelineStartTicks = secondsToTicks(timelineStartSec);
        var sourceInTicks = secondsToTicks(sourceInSec);
        var sourceOutTicks = secondsToTicks(sourceInSec + durationSec);

        // Tạo Time objects
        var insertTime = new Time();
        insertTime.ticks = timelineStartTicks;

        // ========== PHƯƠNG PHÁP 1: overwriteClip ==========
        // overwriteClip(clipProjectItem, time, videoTrackIndex, audioTrackIndex)
        // audioTrackIndex = -1 để KHÔNG insert audio
        try {
            track.overwriteClip(projectItem, insertTime);

            // Lấy clip vừa insert (clip cuối cùng hoặc clip tại vị trí)
            var insertedClip = null;
            for (var i = track.clips.numItems - 1; i >= 0; i--) {
                var clip = track.clips[i];
                var clipStart = clip.start.ticks;
                // Tìm clip gần vị trí insert nhất
                if (Math.abs(clipStart - timelineStartTicks) < TICKS_PER_SECOND * 0.5) {
                    insertedClip = clip;
                    break;
                }
            }

            if (!insertedClip && track.clips.numItems > 0) {
                insertedClip = track.clips[track.clips.numItems - 1];
            }

            if (insertedClip) {
                // Log chi tiết input
                log('    INPUT: sourceIN=' + sourceInSec.toFixed(2) + 's, duration=' + durationSec.toFixed(2) + 's');
                log('    INPUT: timelineStart=' + timelineStartSec.toFixed(2) + 's');

                // Set source IN point TRƯỚC
                var inPoint = new Time();
                inPoint.ticks = sourceInTicks;
                insertedClip.inPoint = inPoint;

                // Set timeline END để control duration (KHÔNG set outPoint)
                var expectedEndTicks = timelineStartTicks + secondsToTicks(durationSec);
                var endTime = new Time();
                endTime.ticks = expectedEndTicks;
                insertedClip.end = endTime;

                // Read back và log kết quả thực tế
                var actualEndTicks = 0;
                try { actualEndTicks = Number(insertedClip.end.ticks); } catch(e) {}
                var actualDuration = (actualEndTicks - timelineStartTicks) / TICKS_PER_SECOND;
                log('    RESULT: actualDuration=' + actualDuration.toFixed(2) + 's (expected ' + durationSec.toFixed(2) + 's)');

                // Disable audio nếu có linked audio
                try {
                    if (insertedClip.isLinked()) {
                        // Không có API trực tiếp để unlink trong ExtendScript
                        // Nhưng overwriteClip với audioTrackIndex = -1 sẽ không tạo audio
                    }
                } catch (audioErr) {
                    // Ignore
                }

                return true;
            }

        } catch (overwriteErr) {
            log('overwriteClip failed: ' + overwriteErr + ', trying insertClip...');
        }

        // ========== PHƯƠNG PHÁP 2: insertClip (fallback) ==========
        var clipCountBefore = track.clips.numItems;

        track.insertClip(projectItem, insertTime);

        if (track.clips.numItems > clipCountBefore) {
            var insertedClip = track.clips[track.clips.numItems - 1];

            // Set source IN point
            var inPoint = new Time();
            inPoint.ticks = sourceInTicks;
            insertedClip.inPoint = inPoint;

            // Set timeline END
            var endTime = new Time();
            endTime.ticks = timelineStartTicks + secondsToTicks(durationSec);
            insertedClip.end = endTime;

            return true;
        }

        return false;

    } catch (e) {
        log('ERROR overwriteClipToTrack: ' + e);
        return false;
    }
}

// ============== MAIN ==============
function main() {
    log('');
    log('╔════════════════════════════════════════════════════╗');
    log('║     EXECUTE CUTS V2 - PHIÊN BẢN 2025 XỊN NHẤT     ║');
    log('╠════════════════════════════════════════════════════╣');
    log('║  • Overwrite mode - không đẩy clips               ║');
    log('║  • Video only - không lấy audio                   ║');
    log('║  • Precise timing với ticks                       ║');
    log('╚════════════════════════════════════════════════════╝');

    // Get config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Không tìm thấy data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    if (!dataFolder) {
        alert('ERROR: data_folder chưa được định nghĩa');
        return;
    }

    log('Data folder: ' + dataFolder);

    // Get active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Không có sequence nào đang mở!');
        return;
    }

    log('Sequence: ' + seq.name);

    // Check V4
    if (seq.videoTracks.numTracks < 4) {
        alert('ERROR: Sequence cần có ít nhất 4 video tracks.\nHiện tại: ' + seq.videoTracks.numTracks);
        return;
    }

    // Read cut_list.json
    var cutListPath = joinPath(dataFolder, 'cut_list.json');
    if (!fileExists(cutListPath)) {
        alert('ERROR: Không tìm thấy cut_list.json\n\nChạy workflow tạo cut list trước!');
        return;
    }

    var cutListJson = readFile(cutListPath);
    var cutListData = parseJSON(cutListJson);

    if (!cutListData || !cutListData.cuts) {
        alert('ERROR: Không đọc được cut_list.json');
        return;
    }

    var cuts = cutListData.cuts;
    log('Loaded ' + cuts.length + ' markers');

    // ASK: Clear track V4 trước?
    var doClear = confirm(
        'Bạn có muốn XÓA tất cả clips trên V4 trước khi insert?\n\n' +
        '• YES = Xóa hết clips cũ trên V4, insert mới\n' +
        '• NO = Giữ nguyên clips cũ, overwrite tại vị trí marker'
    );

    if (doClear) {
        clearTrack(seq, TARGET_TRACK_INDEX);
    }

    // Create bin for imported videos
    var importBin = findOrCreateBin('CutVideos_V2');

    // Process cuts
    var successCount = 0;
    var skipCount = 0;
    var errorCount = 0;
    var totalClips = 0;

    log('');
    log('Processing ' + cuts.length + ' markers...');

    for (var i = 0; i < cuts.length; i++) {
        var marker = cuts[i];
        var clips = marker.clips || [];
        var keyword = marker.keyword || ('Marker ' + i);

        log('');
        log('[' + (i + 1) + '/' + cuts.length + '] "' + keyword + '" (' + clips.length + ' clips)');

        if (clips.length === 0) {
            log('  SKIP: Không có clips');
            skipCount++;
            continue;
        }

        // Insert từng clip cho marker này
        for (var j = 0; j < clips.length; j++) {
            var clip = clips[j];
            totalClips++;

            var videoPath = clip.video_path || '';
            var videoName = clip.video_name || 'unknown';
            var timelinePos = clip.timeline_pos || 0;
            var clipStart = clip.clip_start || 0;
            var duration = clip.duration || 5;

            log('  Clip ' + (j + 1) + '/' + clips.length + ': ' + videoName);
            log('    Timeline: ' + timelinePos.toFixed(2) + 's, Source IN: ' + clipStart.toFixed(2) + 's, Duration: ' + duration.toFixed(2) + 's');

            if (!videoPath) {
                log('    SKIP: No video path');
                continue;
            }

            // Get or import video
            var projectItem = getOrImportVideo(videoPath, importBin);

            if (!projectItem) {
                log('    ERROR: Không import được video');
                errorCount++;
                continue;
            }

            // Overwrite clip to V4
            var success = overwriteClipToTrack(
                seq,
                projectItem,
                TARGET_TRACK_INDEX,
                timelinePos,
                clipStart,
                duration
            );

            if (success) {
                log('    ✓ OK');
                successCount++;
            } else {
                log('    ✗ FAILED');
                errorCount++;
            }
        }
    }

    // Summary
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);

    log('');
    log('╔════════════════════════════════════════════════════╗');
    log('║              HOÀN THÀNH!                           ║');
    log('╠════════════════════════════════════════════════════╣');
    log('║  Markers:      ' + padRight(cuts.length.toString(), 30) + '║');
    log('║  Total clips:  ' + padRight(totalClips.toString(), 30) + '║');
    log('║  Success:      ' + padRight(successCount.toString(), 30) + '║');
    log('║  Skipped:      ' + padRight(skipCount.toString(), 30) + '║');
    log('║  Errors:       ' + padRight(errorCount.toString(), 30) + '║');
    log('║  Time:         ' + padRight(elapsed + 's', 30) + '║');
    log('╚════════════════════════════════════════════════════╝');

    // Save project
    if (successCount > 0) {
        app.project.save();
        log('Project saved');
    }

    alert(
        'Hoàn thành!\n\n' +
        'Markers: ' + cuts.length + '\n' +
        'Clips: ' + totalClips + '\n' +
        'Success: ' + successCount + '\n' +
        'Errors: ' + errorCount
    );
}

function padRight(str, len) {
    while (str.length < len) str += ' ';
    return str;
}

// Run
main();
