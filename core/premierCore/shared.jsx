/**
 * shared.jsx - Centralized utilities for all Premiere ExtendScript files
 *
 * USAGE: Include this file at the start of other JSX files:
 *   #include "shared.jsx"
 *
 * Or copy the needed functions to your script.
 *
 * Contains:
 * - Path utilities (normalizePath, joinPath, fileExists, etc.)
 * - Config management (readPathConfig, getDataFolder, etc.)
 * - Time/Ticks conversion (secondsToTicks, ticksToSeconds, etc.)
 * - Project items (findOrCreateBin, findVideoInProject, etc.)
 * - File I/O (readFile, writeFile, readJSON, writeJSON)
 * - Logging utilities
 */

// ============================================================
//                    CONSTANTS
// ============================================================

var SHARED_ENCODING = 'UTF-8';
var TICKS_PER_SECOND = 254016000000;

// Performance tracking
var _SHARED_PERF_START = new Date().getTime();


// ============================================================
//                    LOGGING
// ============================================================

/**
 * Log message with elapsed time
 * @param {string} prefix - Log prefix (e.g., script name)
 * @param {string} msg - Message to log
 */
function sharedLog(prefix, msg) {
    var elapsed = ((new Date().getTime() - _SHARED_PERF_START) / 1000).toFixed(2);
    try {
        $.writeln('[' + prefix + ' ' + elapsed + 's] ' + msg);
    } catch (e) {}
}

/**
 * Reset performance timer
 */
function resetPerfTimer() {
    _SHARED_PERF_START = new Date().getTime();
}


// ============================================================
//                    PATH UTILITIES
// ============================================================

/**
 * Normalize path separators (backslash to forward slash)
 * @param {string} p - Path to normalize
 * @returns {string} Normalized path
 */
function normalizePath(p) {
    if (!p) return '';
    return p.replace(/\\/g, '/').replace(/\/+/g, '/');
}

/**
 * Join two path segments
 * @param {string} a - First path segment
 * @param {string} b - Second path segment
 * @returns {string} Joined path
 */
function joinPath(a, b) {
    if (!a) return b || '';
    if (!b) return a || '';
    var s = a.charAt(a.length - 1);
    return (s === '/' || s === '\\') ? (a + b) : (a + '/' + b);
}

/**
 * Check if file exists
 * @param {string} p - File path
 * @returns {boolean} True if file exists
 */
function fileExists(p) {
    try {
        return (new File(p)).exists;
    } catch (e) {
        return false;
    }
}

/**
 * Check if folder exists
 * @param {string} p - Folder path
 * @returns {boolean} True if folder exists
 */
function folderExists(p) {
    try {
        return (new Folder(p)).exists;
    } catch (e) {
        return false;
    }
}

/**
 * Ensure folder exists (create if not)
 * @param {string} p - Folder path
 * @returns {boolean} True if folder exists or was created
 */
function ensureFolder(p) {
    try {
        var f = new Folder(p);
        if (!f.exists) return f.create();
        return true;
    } catch (e) {
        return false;
    }
}

/**
 * Get filename from path
 * @param {string} p - File path
 * @returns {string} Filename
 */
function getFileName(p) {
    if (!p) return '';
    var parts = normalizePath(p).split('/');
    return parts[parts.length - 1] || '';
}

/**
 * Get filename without extension
 * @param {string} p - File path
 * @returns {string} Filename without extension
 */
function getFileNameNoExt(p) {
    var name = getFileName(p);
    var idx = name.lastIndexOf('.');
    return idx > 0 ? name.substring(0, idx) : name;
}


// ============================================================
//                    FILE I/O
// ============================================================

/**
 * Read file contents
 * @param {string} p - File path
 * @returns {string} File contents
 */
function readFile(p) {
    var f = new File(p);
    f.encoding = SHARED_ENCODING;
    if (!f.exists || !f.open('r')) return '';
    var content = f.read();
    f.close();
    return content;
}

/**
 * Read file lines as array
 * @param {string} p - File path
 * @returns {Array} Array of lines
 */
function readLines(p) {
    var f = new File(p);
    f.encoding = SHARED_ENCODING;
    if (!f.exists || !f.open('r')) return [];
    var arr = [];
    while (!f.eof) arr.push(f.readln());
    f.close();
    return arr;
}

/**
 * Write content to file
 * @param {string} p - File path
 * @param {string} content - Content to write
 * @returns {boolean} True if successful
 */
function writeFile(p, content) {
    var f = new File(p);
    f.encoding = SHARED_ENCODING;
    if (!f.open('w')) return false;
    f.write(content);
    f.close();
    return true;
}

/**
 * Parse JSON string (using eval for ExtendScript compatibility)
 * @param {string} jsonStr - JSON string
 * @returns {Object|null} Parsed object or null
 */
function parseJSON(jsonStr) {
    try {
        return eval('(' + jsonStr + ')');
    } catch (e) {
        return null;
    }
}

/**
 * Read and parse JSON file
 * @param {string} p - File path
 * @returns {Object|null} Parsed object or null
 */
function readJSON(p) {
    var content = readFile(p);
    if (!content) return null;
    return parseJSON(content);
}


// ============================================================
//                    CONFIG MANAGEMENT
// ============================================================

/**
 * Get root directory (2 levels up from premierCore)
 * @returns {string} Root directory path
 */
function getRootDir() {
    try {
        return new File($.fileName).parent.parent.parent.fsName.replace(/\\/g, '/');
    } catch (e) {
        return '';
    }
}

/**
 * Get data directory (ROOT/data)
 * @returns {string} Data directory path
 */
function getDefaultDataDir() {
    return joinPath(getRootDir(), 'data');
}

/**
 * Read path.txt config file
 * @param {string} pathTxtPath - Optional path to path.txt
 * @returns {Object} Config object with key-value pairs
 */
function readPathConfig(pathTxtPath) {
    if (!pathTxtPath) {
        pathTxtPath = joinPath(getDefaultDataDir(), 'path.txt');
    }

    if (!fileExists(pathTxtPath)) return {};

    var lines = readLines(pathTxtPath);
    var cfg = {};

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (!line) continue;

        var idx = line.indexOf('=');
        if (idx === -1) continue;

        var key = line.substring(0, idx).replace(/^\s+|\s+$/g, '');
        var val = line.substring(idx + 1).replace(/^\s+|\s+$/g, '');

        if (key) cfg[key] = val;
    }

    return cfg;
}

/**
 * Get data folder from config
 * @returns {string} Data folder path
 */
function getDataFolder() {
    var cfg = readPathConfig();
    var dataFolder = normalizePath(cfg.data_folder || '');
    if (dataFolder && folderExists(dataFolder)) {
        return dataFolder;
    }
    return getDefaultDataDir();
}

/**
 * Get resource folder from config
 * @returns {string} Resource folder path
 */
function getResourceFolder() {
    var cfg = readPathConfig();
    return normalizePath(cfg.resource_folder || '');
}


// ============================================================
//                    TIME / TICKS CONVERSION
// ============================================================

/**
 * Convert seconds to ticks
 * @param {number} seconds - Time in seconds
 * @returns {number} Time in ticks
 */
function secondsToTicks(seconds) {
    return Math.floor(seconds * TICKS_PER_SECOND);
}

/**
 * Convert ticks to seconds
 * @param {number} ticks - Time in ticks
 * @returns {number} Time in seconds
 */
function ticksToSeconds(ticks) {
    return ticks / TICKS_PER_SECOND;
}

/**
 * Format seconds as timecode HH:MM:SS:FF (30fps)
 * @param {number} seconds - Time in seconds
 * @param {number} fps - Frames per second (default 30)
 * @returns {string} Timecode string
 */
function secondsToTimecode(seconds, fps) {
    fps = fps || 30;
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = Math.floor(seconds % 60);
    var f = Math.floor((seconds % 1) * fps);

    return pad2(h) + ':' + pad2(m) + ':' + pad2(s) + ':' + pad2(f);
}

/**
 * Pad number to 2 digits
 * @param {number} n - Number to pad
 * @returns {string} Padded string
 */
function pad2(n) {
    return (n < 10 ? '0' : '') + n;
}


// ============================================================
//                    PROJECT ITEMS
// ============================================================

/**
 * Find or create bin in project
 * @param {string} binName - Bin name
 * @param {Object} parentBin - Optional parent bin (default: root)
 * @returns {Object} Bin item
 */
function findOrCreateBin(binName, parentBin) {
    if (!parentBin) parentBin = app.project.rootItem;

    // Search for existing bin
    for (var i = 0; i < parentBin.children.numItems; i++) {
        var item = parentBin.children[i];
        if (item.type === ProjectItemType.BIN && item.name === binName) {
            return item;
        }
    }

    // Create new bin
    return parentBin.createBin(binName);
}

/**
 * Find video in project by path
 * @param {string} videoPath - Video file path
 * @returns {Object|null} Project item or null
 */
function findVideoInProject(videoPath) {
    videoPath = normalizePath(videoPath);
    var rootItem = app.project.rootItem;

    // Search from end (newly imported items)
    for (var i = rootItem.children.numItems - 1; i >= 0; i--) {
        var item = rootItem.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                return item;
            }
        }
        // Search in bins
        if (item.type === ProjectItemType.BIN) {
            var found = findVideoInBin(item, videoPath);
            if (found) return found;
        }
    }

    return null;
}

/**
 * Find video in bin recursively
 * @param {Object} bin - Bin to search
 * @param {string} videoPath - Video file path
 * @returns {Object|null} Project item or null
 */
function findVideoInBin(bin, videoPath) {
    for (var i = bin.children.numItems - 1; i >= 0; i--) {
        var item = bin.children[i];
        if (item.type === ProjectItemType.CLIP || item.type === ProjectItemType.FILE) {
            if (normalizePath(item.getMediaPath()) === videoPath) {
                return item;
            }
        }
        if (item.type === ProjectItemType.BIN) {
            var found = findVideoInBin(item, videoPath);
            if (found) return found;
        }
    }
    return null;
}

/**
 * Import video file to project
 * @param {string} videoPath - Video file path
 * @param {Object} targetBin - Target bin for import
 * @returns {Object|null} Imported project item or null
 */
function importVideo(videoPath, targetBin) {
    videoPath = normalizePath(videoPath);

    if (!fileExists(videoPath)) {
        return null;
    }

    try {
        app.project.importFiles([videoPath], true, targetBin, false);
        // Get the newly imported item
        var rootItem = app.project.rootItem;
        return rootItem.children[rootItem.children.numItems - 1];
    } catch (e) {
        return null;
    }
}

/**
 * Get or import video (with caching)
 * @param {string} videoPath - Video file path
 * @param {Object} targetBin - Target bin for import
 * @param {Object} cache - Optional cache object
 * @returns {Object|null} Project item or null
 */
function getOrImportVideo(videoPath, targetBin, cache) {
    videoPath = normalizePath(videoPath);

    // Check cache
    if (cache && cache[videoPath]) {
        return cache[videoPath];
    }

    // Find in project
    var item = findVideoInProject(videoPath);
    if (item) {
        if (cache) cache[videoPath] = item;
        return item;
    }

    // Import
    item = importVideo(videoPath, targetBin);
    if (item && cache) {
        cache[videoPath] = item;
    }

    return item;
}


// ============================================================
//                    VIDEO FILES
// ============================================================

/**
 * Get all video files from folder
 * @param {string} folderPath - Folder path
 * @returns {Array} Array of video file objects {path, name, nameNoExt, nameLower}
 */
function getVideoFilesFromFolder(folderPath) {
    var videos = [];
    var folder = new Folder(folderPath);

    if (!folder.exists) {
        return videos;
    }

    var extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.webm', '*.MP4', '*.MOV', '*.AVI'];

    for (var e = 0; e < extensions.length; e++) {
        var files = folder.getFiles(extensions[e]);
        for (var f = 0; f < files.length; f++) {
            var fileName = files[f].name;
            var nameNoExt = fileName.replace(/\.[^.]+$/, '');
            videos.push({
                path: normalizePath(files[f].fsName),
                name: fileName,
                nameNoExt: nameNoExt,
                nameLower: nameNoExt.toLowerCase()
            });
        }
    }

    return videos;
}

/**
 * Find video matching keyword
 * @param {string} keyword - Keyword to match
 * @param {Array} videoFiles - Array of video file objects
 * @returns {Object|null} Matched video file or null
 */
function findVideoForKeyword(keyword, videoFiles) {
    var kw = keyword.toLowerCase().replace(/^\s+|\s+$/g, '');

    // 1. Exact match
    for (var i = 0; i < videoFiles.length; i++) {
        if (videoFiles[i].nameLower === kw) {
            return videoFiles[i];
        }
    }

    // 2. Keyword in filename
    for (var j = 0; j < videoFiles.length; j++) {
        if (videoFiles[j].nameLower.indexOf(kw) !== -1) {
            return videoFiles[j];
        }
    }

    // 3. Filename in keyword
    for (var k = 0; k < videoFiles.length; k++) {
        if (kw.indexOf(videoFiles[k].nameLower) !== -1) {
            return videoFiles[k];
        }
    }

    return null;
}


// ============================================================
//                    CLIP OPERATIONS
// ============================================================

/**
 * Insert clip to video track
 * @param {Object} sequence - Premiere sequence
 * @param {Object} projectItem - Project item to insert
 * @param {number} trackIndex - Video track index (0-based)
 * @param {number} timelineStart - Start position in seconds
 * @param {number} sourceIn - Source IN point in seconds (optional)
 * @param {number} duration - Duration in seconds (optional)
 * @returns {Object|null} Inserted clip or null
 */
function insertClipToTrack(sequence, projectItem, trackIndex, timelineStart, sourceIn, duration) {
    if (!sequence || !projectItem) return null;

    var videoTracks = sequence.videoTracks;
    if (videoTracks.numTracks <= trackIndex) return null;

    var track = videoTracks[trackIndex];
    var clipCountBefore = track.clips.numItems;

    try {
        var timelineStartTicks = secondsToTicks(timelineStart);

        // Insert clip
        track.insertClip(projectItem, timelineStartTicks.toString());

        // Get inserted clip
        if (track.clips.numItems > clipCountBefore) {
            var insertedClip = track.clips[track.clips.numItems - 1];

            // Set source IN point if specified
            if (typeof sourceIn === 'number' && sourceIn > 0) {
                insertedClip.inPoint = secondsToTicks(sourceIn).toString();
            }

            // Set duration if specified
            if (typeof duration === 'number' && duration > 0) {
                var endTicks = timelineStartTicks + secondsToTicks(duration);
                insertedClip.end = endTicks.toString();
            }

            return insertedClip;
        }
    } catch (e) {
        // Error inserting clip
    }

    return null;
}


// ============================================================
//                    SEQUENCE UTILITIES
// ============================================================

/**
 * Get active sequence
 * @returns {Object|null} Active sequence or null
 */
function getActiveSequence() {
    try {
        return app.project.activeSequence;
    } catch (e) {
        return null;
    }
}

/**
 * Check if sequence has enough video tracks
 * @param {Object} sequence - Sequence to check
 * @param {number} minTracks - Minimum required tracks
 * @returns {boolean} True if has enough tracks
 */
function hasVideoTracks(sequence, minTracks) {
    if (!sequence) return false;
    try {
        return sequence.videoTracks.numTracks >= minTracks;
    } catch (e) {
        return false;
    }
}


// ============================================================
//                    JSON SERIALIZATION
// ============================================================

/**
 * Escape string for JSON
 * @param {string} s - String to escape
 * @returns {string} Escaped string
 */
function escapeJSONString(s) {
    if (!s) return '';
    return String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r')
        .replace(/\t/g, '\\t');
}

/**
 * Convert value to safe number
 * @param {*} v - Value to convert
 * @returns {number} Safe number (0 if invalid)
 */
function safeNumber(v) {
    var n = parseFloat(v);
    if (isNaN(n) || !isFinite(n)) return 0;
    return n;
}
