/**
 * extractTrack3Keywords.jsx
 *
 * Đọc Track 3 (Video Track 3) từ Premiere sequence
 * Lấy text clips với nội dung keywords + timecode (start, end)
 * Export ra JSON/CSV để Python xử lý tiếp
 *
 * FIXED: Properly extract text from Essential Graphics / Text layers
 */

function log(msg) {
    try { $.writeln('[extractTrack3] ' + msg); } catch (e) {}
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

function writeFile(path, content) {
    var f = new File(path);
    // Set encoding to UTF-8 for proper character support
    f.encoding = 'UTF-8';
    if (!f.open('w')) {
        log('ERROR: Cannot write to ' + path);
        return false;
    }
    // Write content directly without BOM
    f.write(content);
    f.close();
    return true;
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
 * Chuyển đổi Ticks (Premiere internal time) sang giây
 */
function ticksToSeconds(ticks) {
    // Premiere uses Ticks: 254016000000 ticks = 1 second
    var TICKS_PER_SECOND = 254016000000;
    return parseFloat(ticks) / TICKS_PER_SECOND;
}

/**
 * Chuyển giây thành timecode string (HH:MM:SS.mmm)
 */
function secondsToTimecode(seconds) {
    var hrs = Math.floor(seconds / 3600);
    var mins = Math.floor((seconds % 3600) / 60);
    var secs = Math.floor(seconds % 60);
    var ms = Math.floor((seconds % 1) * 1000);

    var h = (hrs < 10 ? '0' : '') + hrs;
    var m = (mins < 10 ? '0' : '') + mins;
    var s = (secs < 10 ? '0' : '') + secs;
    var mil = (ms < 10 ? '00' : (ms < 100 ? '0' : '')) + ms;

    return h + ':' + m + ':' + s + '.' + mil;
}

/**
 * Debug: Print all components and properties of a clip
 * Use this to understand the structure of graphics clips
 */
function debugClipStructure(clipItem, clipIndex) {
    log('=== DEBUG Clip ' + clipIndex + ' Structure ===');
    log('  Name: ' + (clipItem.name || 'N/A'));

    if (clipItem.projectItem) {
        log('  ProjectItem.name: ' + (clipItem.projectItem.name || 'N/A'));
        log('  ProjectItem.type: ' + clipItem.projectItem.type);
    }

    if (clipItem.components) {
        log('  Components count: ' + clipItem.components.numItems);
        for (var c = 0; c < clipItem.components.numItems; c++) {
            var comp = clipItem.components[c];
            log('    [' + c + '] Component: ' + (comp.displayName || comp.matchName || 'Unknown'));

            if (comp.properties) {
                log('      Properties count: ' + comp.properties.numItems);
                for (var p = 0; p < comp.properties.numItems; p++) {
                    var prop = comp.properties[p];
                    var propName = prop.displayName || prop.matchName || 'Unknown';
                    var propValue = '';
                    try {
                        propValue = prop.getValue();
                        if (typeof propValue === 'string' && propValue.length > 50) {
                            propValue = propValue.substring(0, 50) + '...';
                        }
                    } catch (e) {
                        propValue = '[cannot read]';
                    }
                    log('        [' + p + '] ' + propName + ' = ' + propValue);
                }
            }
        }
    }

    // Check for MGT component
    if (typeof clipItem.getMGTComponent === 'function') {
        try {
            var mgt = clipItem.getMGTComponent();
            if (mgt) {
                log('  Has MGT component');
                if (mgt.properties) {
                    for (var m = 0; m < mgt.properties.numItems; m++) {
                        var mgtProp = mgt.properties[m];
                        var mgtName = mgtProp.displayName || 'Unknown';
                        var mgtVal = '';
                        try { mgtVal = mgtProp.getValue(); } catch (e) { mgtVal = '[error]'; }
                        log('    MGT Property: ' + mgtName + ' = ' + mgtVal);
                    }
                }
            }
        } catch (e) {
            log('  MGT access error: ' + e);
        }
    }
    log('=== END DEBUG ===');
}

/**
 * Extract text from Essential Graphics / Motion Graphics Template
 * This handles the "Source Text" property in text layers
 *
 * IMPORTANT: Premiere ExtendScript has limited access to Essential Graphics text.
 * This function tries multiple approaches to extract text.
 */
function getTextFromComponents(clipItem) {
    try {
        // ========== Method 1: Access via clip.components ==========
        if (clipItem.components && clipItem.components.numItems > 0) {
            for (var c = 0; c < clipItem.components.numItems; c++) {
                var comp = clipItem.components[c];
                var compName = (comp.displayName || comp.matchName || '').toLowerCase();

                // Log component for debugging
                log('    Checking component: ' + (comp.displayName || comp.matchName || 'Unknown'));

                // Check component properties
                if (comp.properties && comp.properties.numItems > 0) {
                    for (var p = 0; p < comp.properties.numItems; p++) {
                        var prop = comp.properties[p];
                        var propName = (prop.displayName || prop.matchName || '').toLowerCase();

                        // Look for ANY text-related properties
                        if (propName.indexOf('text') !== -1 ||
                            propName.indexOf('source') !== -1 ||
                            propName.indexOf('string') !== -1 ||
                            propName.indexOf('content') !== -1 ||
                            propName.indexOf('caption') !== -1 ||
                            propName.indexOf('title') !== -1) {

                            log('      Found property: ' + (prop.displayName || prop.matchName));

                            // Try multiple ways to get value
                            var val = null;
                            try { val = prop.getValue(); } catch (e1) {}
                            if (!val) try { val = prop.getValueAtKey(0); } catch (e2) {}
                            if (!val) try { val = prop.getValueAtTime(0); } catch (e3) {}

                            if (val && typeof val === 'string' && val.length > 0) {
                                val = val.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
                                if (val.length > 0 && val.toLowerCase() !== 'graphic') {
                                    log('      => Text found: "' + val + '"');
                                    return val;
                                }
                            }
                        }
                    }
                }
            }
        }

        // ========== Method 2: Access via getMGTComponent (MOGRT) ==========
        if (typeof clipItem.getMGTComponent === 'function') {
            try {
                var mgtComp = clipItem.getMGTComponent();
                if (mgtComp) {
                    log('    Has MGT component');

                    // Try to get properties
                    if (mgtComp.properties && mgtComp.properties.numItems > 0) {
                        for (var m = 0; m < mgtComp.properties.numItems; m++) {
                            var mgtProp = mgtComp.properties[m];
                            var mgtName = (mgtProp.displayName || '').toLowerCase();

                            log('      MGT Property: ' + mgtProp.displayName);

                            // Check all properties for text content
                            var mgtVal = null;
                            try { mgtVal = mgtProp.getValue(); } catch (e) {}

                            if (mgtVal && typeof mgtVal === 'string' && mgtVal.length > 0) {
                                mgtVal = mgtVal.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
                                if (mgtVal.length > 0 && mgtVal.toLowerCase() !== 'graphic') {
                                    log('      => Text found in MGT: "' + mgtVal + '"');
                                    return mgtVal;
                                }
                            }
                        }
                    }
                }
            } catch (e) {
                log('    MGT access error: ' + e);
            }
        }

        // ========== Method 3: Try to access via projectItem metadata ==========
        if (clipItem.projectItem) {
            try {
                // Get XMP metadata
                var xmp = clipItem.projectItem.getXMPMetadata();
                if (xmp && xmp.length > 0) {
                    // Look for text content in XMP
                    var textMatch = xmp.match(/<dc:title[^>]*>([^<]+)</i) ||
                                   xmp.match(/<dc:description[^>]*>([^<]+)</i) ||
                                   xmp.match(/Text[^>]*>([^<]+)</i);
                    if (textMatch && textMatch[1]) {
                        var xmpText = textMatch[1].replace(/^\s+|\s+$/g, '');
                        if (xmpText.length > 0 && xmpText.toLowerCase() !== 'graphic') {
                            log('      => Text found in XMP: "' + xmpText + '"');
                            return xmpText;
                        }
                    }
                }
            } catch (e) {
                log('    XMP access error: ' + e);
            }
        }

        return null;
    } catch (e) {
        log('ERROR in getTextFromComponents: ' + e);
        return null;
    }
}

/**
 * Lấy text content từ clip (nếu là text/title clip)
 * Tries multiple methods to extract text from different clip types
 *
 * WORKAROUND for Essential Graphics limitation:
 * If USE_CLIP_NAME_AS_KEYWORD is true, user should rename clips in timeline
 * to the keyword they want (e.g., rename "Graphic" to "Tony Dow best moments")
 */
function getClipText(clipItem) {
    try {
        // WORKAROUND: Use clip name directly if enabled
        // User should rename clips in timeline to their keywords
        if (USE_CLIP_NAME_AS_KEYWORD) {
            var clipName = clipItem.name || '';
            // Clean up the name
            clipName = clipName.replace(/^\s+|\s+$/g, '');

            // Skip only very generic names
            if (clipName && clipName.length > 0 &&
                clipName.toLowerCase() !== 'graphic' &&
                clipName.toLowerCase() !== 'graphics' &&
                !clipName.match(/^graphic\s*\d*$/i) &&
                !clipName.match(/^clip\s*\d*$/i)) {
                log('  Using clip name as keyword: "' + clipName + '"');
                return clipName;
            }
        }

        // Method 1: Try to get text from Essential Graphics components
        var compText = getTextFromComponents(clipItem);
        if (compText && compText.length > 0) {
            return compText;
        }

        // Method 2: Check projectItem for source text (for MOGRT/text clips)
        if (clipItem.projectItem) {
            var projItem = clipItem.projectItem;

            // Try to get from project item metadata/properties
            if (typeof projItem.getProjectColumnsMetadata === 'function') {
                try {
                    var metadata = projItem.getProjectColumnsMetadata();
                    // Parse metadata for text content
                } catch (e) {}
            }

            // Check if it's a graphics clip with editable text
            if (projItem.type === ProjectItemType.CLIP) {
                // For graphics templates, the name might contain text info
                var projName = projItem.name || '';
                // Skip generic names
                if (projName && projName.length > 0 &&
                    projName.indexOf('Graphics') === -1 &&
                    projName.indexOf('Title') === -1 &&
                    projName.indexOf('Text') === -1 &&
                    projName.toLowerCase() !== 'graphic') {
                    return projName;
                }
            }
        }

        // Method 3: Fall back to clip name (may contain text for simple titles)
        var clipName = clipItem.name || '';
        if (clipName && clipName.length > 0) {
            // Skip generic/system names
            if (clipName.indexOf('Graphics') === -1 &&
                clipName.indexOf('Graphic ') === -1 &&
                clipName.toLowerCase() !== 'graphic' &&
                !clipName.match(/^Clip\s*\d*$/i)) {
                return clipName;
            }
        }

        return '';
    } catch (e) {
        log('ERROR in getClipText: ' + e);
        return '';
    }
}

// ============== CONFIGURATION ==============
// Enable debug mode to see clip structure (set to true for debugging)
var DEBUG_MODE = false;
// Debug only first N clips (set to 0 for all)
var DEBUG_LIMIT = 3;

// ===== SOURCE MODE =====
// Choose where to read keywords from:
// 'track3'   - Read from clips on Track 3 (Essential Graphics - limited)
// 'markers'  - Read from Sequence Markers (RECOMMENDED - full text access)
// 'captions' - Read from Captions track
var KEYWORD_SOURCE = 'markers';

// WORKAROUND: If true, use clip NAME as keyword (rename clips in timeline to keywords)
var USE_CLIP_NAME_AS_KEYWORD = true;

// Alternative: Read keywords from external file (one keyword per line, matching clip order)
// Set to empty string to disable
var EXTERNAL_KEYWORDS_FILE = ''; // e.g., 'keywords_list.txt'

/**
 * ============== EXTRACT FROM SEQUENCE MARKERS ==============
 * Đọc keywords từ Sequence Markers
 * Mỗi marker = 1 keyword, với:
 *   - Marker Name = keyword text
 *   - Marker Duration = thời lượng clip
 *
 * Cách tạo marker trong Premiere:
 *   1. Đặt playhead tại vị trí muốn đánh dấu
 *   2. Nhấn M để tạo marker
 *   3. Double-click marker để edit
 *   4. Nhập keyword vào Name field
 *   5. Set Duration nếu cần
 */
function extractFromMarkers(sequence) {
    if (!sequence) {
        log('ERROR: No sequence provided');
        return [];
    }

    var markers = sequence.markers;
    if (!markers) {
        log('ERROR: Cannot access sequence markers');
        return [];
    }

    log('Reading Sequence Markers...');
    log('Markers object type: ' + typeof markers);

    var keywords = [];
    var markerIndex = 0;
    var foundMethod = 'none';

    // Debug: List all properties of markers object
    log('Markers properties:');
    for (var prop in markers) {
        try {
            log('  - ' + prop + ': ' + typeof markers[prop]);
        } catch (e) {}
    }

    // Method 1: Premiere 2022+ uses numMarkers property
    if (typeof markers.numMarkers !== 'undefined' && markers.numMarkers > 0) {
        foundMethod = 'numMarkers';
        log('Using numMarkers method: ' + markers.numMarkers + ' markers');
        for (var i = 0; i < markers.numMarkers; i++) {
            var marker = markers[i];
            if (marker) {
                processMarker(marker, markerIndex++, keywords);
            }
        }
    }

    // Method 2: Try createMarker to check if markers exist, then iterate
    if (keywords.length === 0 && typeof markers.createMarker === 'function') {
        foundMethod = 'iteration with createMarker check';
        log('Trying iteration (createMarker exists)...');
        try {
            // Try to access markers by index
            for (var j = 0; j < 100; j++) {
                var m = null;
                try {
                    m = markers[j];
                } catch (e) {
                    break;
                }
                if (!m || typeof m === 'undefined') break;
                processMarker(m, markerIndex++, keywords);
            }
        } catch (e) {
            log('Iteration failed: ' + e);
        }
    }

    // Method 3: Try getFirstMarker/getNextMarker (some versions)
    if (keywords.length === 0 && typeof markers.getFirstMarker === 'function') {
        foundMethod = 'getFirstMarker';
        log('Using getFirstMarker/getNextMarker method');
        try {
            var marker = markers.getFirstMarker();
            while (marker) {
                processMarker(marker, markerIndex++, keywords);
                marker = markers.getNextMarker(marker);
            }
        } catch (e) {
            log('getFirstMarker failed: ' + e);
        }
    }

    // Method 4: For Premiere 2022 - try accessing via app.project.activeSequence.markers
    if (keywords.length === 0) {
        foundMethod = 'app.project.activeSequence.markers';
        log('Trying app.project.activeSequence.markers...');
        try {
            var seqMarkers = app.project.activeSequence.markers;
            if (seqMarkers) {
                log('seqMarkers.numMarkers: ' + seqMarkers.numMarkers);
                for (var k = 0; k < seqMarkers.numMarkers; k++) {
                    var sm = seqMarkers[k];
                    if (sm) {
                        processMarker(sm, markerIndex++, keywords);
                    }
                }
            }
        } catch (e) {
            log('app.project method failed: ' + e);
        }
    }

    log('\nMethod used: ' + foundMethod);
    log('Found ' + keywords.length + ' keywords from markers');

    if (keywords.length === 0) {
        log('');
        log('========================================');
        log('WARNING: No markers found!');
        log('');
        log('For Premiere Pro 2022:');
        log('1. Click on empty area in timeline (deselect all)');
        log('2. Move playhead to desired position');
        log('3. Press M to create a SEQUENCE marker');
        log('4. Double-click the marker (yellow icon on ruler)');
        log('5. Enter keyword in the "Name" field');
        log('6. Set Duration if needed');
        log('');
        log('NOTE: Clip markers (on clips) are different from');
        log('      Sequence markers (on the timeline ruler)');
        log('========================================');
    }

    return keywords;
}

/**
 * Process a single marker and add to keywords array
 */
function processMarker(marker, index, keywords) {
    if (!marker) return;

    try {
        // Get marker properties
        var markerName = marker.name || '';
        var markerComment = marker.comments || '';

        // Use name first, fall back to comment
        var keyword = markerName.replace(/^\s+|\s+$/g, '');
        if (!keyword || keyword.length === 0) {
            keyword = markerComment.replace(/^\s+|\s+$/g, '');
        }

        // Skip empty markers
        if (!keyword || keyword.length === 0) {
            log('WARN: Marker ' + index + ' has no name/comment, skip');
            return;
        }

        // Get timing - handle different marker API versions
        var startTicks = 0;
        var endTicks = 0;

        // Try different ways to get start time
        if (marker.start && marker.start.ticks) {
            startTicks = marker.start.ticks;
        } else if (typeof marker.start === 'number') {
            startTicks = marker.start;
        } else if (typeof marker.inPoint !== 'undefined') {
            startTicks = marker.inPoint.ticks || marker.inPoint;
        }

        // Try different ways to get end time
        if (marker.end && marker.end.ticks) {
            endTicks = marker.end.ticks;
        } else if (typeof marker.end === 'number') {
            endTicks = marker.end;
        } else if (typeof marker.outPoint !== 'undefined') {
            endTicks = marker.outPoint.ticks || marker.outPoint;
        }

        var startSec = ticksToSeconds(startTicks);
        var endSec = ticksToSeconds(endTicks);

        // If marker has no duration, use default (5 seconds)
        if (endSec <= startSec) {
            endSec = startSec + 5.0;
        }

        var durationSec = endSec - startSec;
        var startTC = secondsToTimecode(startSec);
        var endTC = secondsToTimecode(endSec);

        log('Marker ' + index + ': "' + keyword + '" | ' + startTC + ' -> ' + endTC + ' (' + durationSec.toFixed(2) + 's)');

        keywords.push({
            index: index,
            keyword: keyword,
            start_seconds: startSec,
            end_seconds: endSec,
            duration_seconds: durationSec,
            start_timecode: startTC,
            end_timecode: endTC
        });
    } catch (e) {
        log('ERROR processing marker ' + index + ': ' + e);
    }
}

/**
 * ============== EXTRACT FROM CAPTIONS ==============
 * Đọc keywords từ Captions track (nếu có)
 */
function extractFromCaptions(sequence) {
    if (!sequence) {
        log('ERROR: No sequence provided');
        return [];
    }

    // Try to access captions
    var captionTracks = null;
    try {
        captionTracks = sequence.captionTracks;
    } catch (e) {
        log('ERROR: Cannot access caption tracks: ' + e);
        return [];
    }

    if (!captionTracks || captionTracks.numTracks === 0) {
        log('ERROR: No caption tracks found');
        return [];
    }

    log('Reading Caption Tracks...');
    log('Number of caption tracks: ' + captionTracks.numTracks);

    var keywords = [];

    // Read from first caption track
    var track = captionTracks[0];
    if (track && track.clips) {
        for (var i = 0; i < track.clips.numItems; i++) {
            var clip = track.clips[i];

            // Get caption text
            var text = '';
            try {
                text = clip.name || '';
                // Try to get actual caption content
                if (clip.projectItem && clip.projectItem.name) {
                    text = clip.projectItem.name;
                }
            } catch (e) {}

            text = text.replace(/^\s+|\s+$/g, '');
            if (!text || text.length === 0) continue;

            var startSec = ticksToSeconds(clip.start.ticks);
            var endSec = ticksToSeconds(clip.end.ticks);
            var durationSec = endSec - startSec;

            keywords.push({
                index: i,
                keyword: text,
                start_seconds: startSec,
                end_seconds: endSec,
                duration_seconds: durationSec,
                start_timecode: secondsToTimecode(startSec),
                end_timecode: secondsToTimecode(endSec)
            });
        }
    }

    log('\nFound ' + keywords.length + ' keywords from captions');
    return keywords;
}

/**
 * Đọc tất cả clips từ Track 3 (Video Track 3)
 * Track index: 0-based, nên Track 3 = index 2
 */
function extractTrack3Keywords(sequence) {
    if (!sequence) {
        log('ERROR: No sequence provided');
        return [];
    }

    var videoTracks = sequence.videoTracks;
    if (!videoTracks || videoTracks.numTracks < 3) {
        log('ERROR: Sequence không có đủ 3 video tracks');
        return [];
    }

    // Track 3 = index 2 (0-based)
    var track3 = videoTracks[2];
    log('Reading Track 3: ' + track3.name);
    log('Number of clips in Track 3: ' + track3.clips.numItems);

    var keywords = [];
    var noTextClips = [];

    for (var i = 0; i < track3.clips.numItems; i++) {
        var clip = track3.clips[i];

        // Debug mode: show structure of first few clips
        if (DEBUG_MODE && (DEBUG_LIMIT === 0 || i < DEBUG_LIMIT)) {
            debugClipStructure(clip, i);
        }

        // Lấy timecode
        var startTicks = clip.start.ticks;
        var endTicks = clip.end.ticks;

        var startSec = ticksToSeconds(startTicks);
        var endSec = ticksToSeconds(endTicks);
        var durationSec = endSec - startSec;

        var startTC = secondsToTimecode(startSec);
        var endTC = secondsToTimecode(endSec);

        // Lấy text/keyword
        var keyword = getClipText(clip);

        if (!keyword || keyword.length === 0) {
            log('WARN: Clip ' + i + ' không có text');
            noTextClips.push({
                index: i,
                name: clip.name || 'N/A',
                start_timecode: startTC
            });
            continue;
        }

        log('Clip ' + i + ': "' + keyword + '" | ' + startTC + ' -> ' + endTC + ' (' + durationSec.toFixed(2) + 's)');

        keywords.push({
            index: i,
            keyword: keyword,
            start_seconds: startSec,
            end_seconds: endSec,
            duration_seconds: durationSec,
            start_timecode: startTC,
            end_timecode: endTC
        });
    }

    // Report clips without text
    if (noTextClips.length > 0) {
        log('\n=== CLIPS WITHOUT TEXT (' + noTextClips.length + ') ===');
        for (var j = 0; j < noTextClips.length; j++) {
            var ntc = noTextClips[j];
            log('  Clip ' + ntc.index + ': name="' + ntc.name + '" at ' + ntc.start_timecode);
        }

        // Auto-enable debug for first clip without text
        if (noTextClips.length > 0 && keywords.length === 0) {
            log('\nNo text found in any clip. Running debug on first clip...');
            var firstClip = track3.clips[noTextClips[0].index];
            debugClipStructure(firstClip, noTextClips[0].index);
        }
    }

    log('\nFound ' + keywords.length + ' keywords, ' + noTextClips.length + ' clips without text');

    return keywords;
}

/**
 * Export keywords ra JSON
 */
function exportKeywordsToJSON(keywords, outputPath) {
    var jsonObj = {
        version: '1.0',
        count: keywords.length,
        keywords: []
    };

    for (var i = 0; i < keywords.length; i++) {
        jsonObj.keywords.push(keywords[i]);
    }

    // Helper function to safely format number for JSON
    function safeNum(v) {
        if (typeof v === 'undefined' || v === null || isNaN(v)) return '0';
        if (!isFinite(v)) return '0';
        return String(v);
    }

    // Helper function to escape string for JSON
    function safeStr(s) {
        if (!s) return '';
        return String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r');
    }

    // Manual JSON stringify (ExtendScript không có JSON.stringify)
    var jsonStr = '{\n';
    jsonStr += '  "version": "' + jsonObj.version + '",\n';
    jsonStr += '  "count": ' + jsonObj.count + ',\n';
    jsonStr += '  "keywords": [\n';

    for (var i = 0; i < keywords.length; i++) {
        var kw = keywords[i];
        jsonStr += '    {\n';
        jsonStr += '      "index": ' + safeNum(kw.index) + ',\n';
        jsonStr += '      "keyword": "' + safeStr(kw.keyword) + '",\n';
        jsonStr += '      "start_seconds": ' + safeNum(kw.start_seconds) + ',\n';
        jsonStr += '      "end_seconds": ' + safeNum(kw.end_seconds) + ',\n';
        jsonStr += '      "duration_seconds": ' + safeNum(kw.duration_seconds) + ',\n';
        jsonStr += '      "start_timecode": "' + safeStr(kw.start_timecode) + '",\n';
        jsonStr += '      "end_timecode": "' + safeStr(kw.end_timecode) + '"\n';
        jsonStr += '    }';
        if (i < keywords.length - 1) jsonStr += ',';
        jsonStr += '\n';
    }

    jsonStr += '  ]\n';
    jsonStr += '}\n';

    return writeFile(outputPath, jsonStr);
}

/**
 * Export keywords ra CSV
 */
function exportKeywordsToCSV(keywords, outputPath) {
    var csvLines = [];
    csvLines.push('index,keyword,start_seconds,end_seconds,duration_seconds,start_timecode,end_timecode');

    for (var i = 0; i < keywords.length; i++) {
        var kw = keywords[i];
        var line = kw.index + ',"' + kw.keyword.replace(/"/g, '""') + '",' +
                   kw.start_seconds + ',' + kw.end_seconds + ',' + kw.duration_seconds + ',' +
                   '"' + kw.start_timecode + '","' + kw.end_timecode + '"';
        csvLines.push(line);
    }

    var csvContent = csvLines.join('\n');
    return writeFile(outputPath, csvContent);
}

/**
 * Main function
 */
function main() {
    log('=== START EXTRACT KEYWORDS ===');
    log('Source mode: ' + KEYWORD_SOURCE);

    // Đọc config
    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Không tìm thấy data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    var seqName = cfg.sequence_name || 'Main';

    if (!dataFolder) {
        alert('ERROR: data_folder không được định nghĩa trong path.txt');
        return;
    }

    log('Data folder: ' + dataFolder);
    log('Sequence name: ' + seqName);

    // Lấy active sequence
    var seq = app.project.activeSequence;
    if (!seq) {
        alert('ERROR: Không có sequence nào được mở.\nHãy mở sequence trước khi chạy script.');
        return;
    }

    log('Active sequence: ' + seq.name);

    // Extract keywords based on source mode
    var keywords = [];
    var sourceName = '';

    switch (KEYWORD_SOURCE.toLowerCase()) {
        case 'markers':
            keywords = extractFromMarkers(seq);
            sourceName = 'Sequence Markers';
            break;

        case 'captions':
            keywords = extractFromCaptions(seq);
            sourceName = 'Captions';
            break;

        case 'track3':
        default:
            keywords = extractTrack3Keywords(seq);
            sourceName = 'Track 3';
            break;
    }

    if (keywords.length === 0) {
        var helpMsg = '';
        if (KEYWORD_SOURCE === 'markers') {
            helpMsg = '\n\nĐể sử dụng Markers:\n' +
                      '1. Nhấn M để tạo marker\n' +
                      '2. Double-click marker\n' +
                      '3. Nhập keyword vào Name\n' +
                      '4. Set Duration';
        }
        alert('WARNING: Không tìm thấy keywords nào từ ' + sourceName + helpMsg);
        return;
    }

    log('Found ' + keywords.length + ' keywords from ' + sourceName);

    // Export ra JSON
    var jsonPath = joinPath(dataFolder, 'track3_keywords.json');
    if (exportKeywordsToJSON(keywords, jsonPath)) {
        log('Exported JSON: ' + jsonPath);
    } else {
        log('ERROR: Failed to export JSON');
    }

    // Export ra CSV
    var csvPath = joinPath(dataFolder, 'track3_keywords.csv');
    if (exportKeywordsToCSV(keywords, csvPath)) {
        log('Exported CSV: ' + csvPath);
    } else {
        log('ERROR: Failed to export CSV');
    }

    log('=== DONE ===');
    alert('Đã export ' + keywords.length + ' keywords từ ' + sourceName + '\n\nJSON: ' + jsonPath + '\nCSV: ' + csvPath);
}

// Run
main();
