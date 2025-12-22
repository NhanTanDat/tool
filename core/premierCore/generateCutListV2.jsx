/**
 * generateCutListV2.jsx - OPTIMIZED VERSION
 *
 * TÍNH NĂNG:
 * 1. Smart matching - fuzzy match, partial match, word match
 * 2. Multi-clip support - nhiều video cho 1 marker
 * 3. Duration calculation - tự tính thời lượng cần thiết
 * 4. Caching - không scan folder nhiều lần
 * 5. JSON output chuẩn cho executeCutsV3.jsx
 */

var PERF_START = new Date().getTime();

function log(msg) {
    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(2);
    try { $.writeln('[generateCutListV2 ' + elapsed + 's] ' + msg); } catch (e) {}
}

// ================= PATH UTILITIES =================
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
    f.encoding = 'UTF-8';
    if (!f.exists || !f.open('r')) return '';
    var content = f.read();
    f.close();
    return content;
}

function writeFile(path, content) {
    var f = new File(path);
    f.encoding = 'UTF-8';
    if (!f.open('w')) {
        log('ERROR: Cannot write to ' + path);
        return false;
    }
    f.write(content);
    f.close();
    return true;
}

// ================= CONFIG =================
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
    try { return eval('(' + str + ')'); }
    catch (e) { log('ERROR parsing JSON: ' + e); return null; }
}

// ================= VIDEO FILES =================
var videoCache = null;

function getVideoFiles(folderPath) {
    // Return cached if available
    if (videoCache) return videoCache;

    var videos = [];
    var folder = new Folder(folderPath);

    if (!folder.exists) {
        log('ERROR: Folder not found: ' + folderPath);
        return videos;
    }

    var extensions = ['*.mp4', '*.mov', '*.avi', '*.mkv', '*.webm', '*.MP4', '*.MOV', '*.AVI'];

    for (var e = 0; e < extensions.length; e++) {
        var files = folder.getFiles(extensions[e]);
        for (var f = 0; f < files.length; f++) {
            var fileName = files[f].name;
            var nameNoExt = fileName.replace(/\.[^.]+$/, '');

            // Pre-compute for faster matching
            var nameLower = nameNoExt.toLowerCase();
            var nameWords = nameLower.split(/[\s_\-\.]+/);

            videos.push({
                path: normalizePath(files[f].fsName),
                name: fileName,
                nameNoExt: nameNoExt,
                nameLower: nameLower,
                nameWords: nameWords
            });
        }
    }

    videoCache = videos;
    log('Cached ' + videos.length + ' videos');
    return videos;
}

// ================= SMART MATCHING =================
function normalizeKeyword(kw) {
    if (!kw) return '';
    return kw.toLowerCase()
        .replace(/^\s+|\s+$/g, '')
        .replace(/[^\w\s]/g, ' ')
        .replace(/\s+/g, ' ');
}

function getKeywordWords(kw) {
    return normalizeKeyword(kw).split(' ').filter(function(w) { return w.length > 0; });
}

function countMatchingWords(kwWords, videoWords) {
    var count = 0;
    for (var i = 0; i < kwWords.length; i++) {
        for (var j = 0; j < videoWords.length; j++) {
            if (videoWords[j].indexOf(kwWords[i]) !== -1 || kwWords[i].indexOf(videoWords[j]) !== -1) {
                count++;
                break;
            }
        }
    }
    return count;
}

function findVideosForKeyword(keyword, videoFiles, maxResults) {
    maxResults = maxResults || 3;
    var kw = normalizeKeyword(keyword);
    var kwWords = getKeywordWords(keyword);
    var results = [];

    // Pass 1: Exact match (highest priority)
    for (var i = 0; i < videoFiles.length; i++) {
        if (videoFiles[i].nameLower === kw) {
            results.push({ video: videoFiles[i], score: 100, matchType: 'exact' });
        }
    }
    if (results.length >= maxResults) return results.slice(0, maxResults);

    // Pass 2: Keyword in filename
    for (var j = 0; j < videoFiles.length; j++) {
        if (videoFiles[j].nameLower.indexOf(kw) !== -1) {
            var alreadyAdded = false;
            for (var r = 0; r < results.length; r++) {
                if (results[r].video.path === videoFiles[j].path) { alreadyAdded = true; break; }
            }
            if (!alreadyAdded) {
                results.push({ video: videoFiles[j], score: 80, matchType: 'contains' });
            }
        }
    }
    if (results.length >= maxResults) return results.slice(0, maxResults);

    // Pass 3: Filename in keyword
    for (var k = 0; k < videoFiles.length; k++) {
        if (kw.indexOf(videoFiles[k].nameLower) !== -1) {
            var alreadyAdded2 = false;
            for (var r2 = 0; r2 < results.length; r2++) {
                if (results[r2].video.path === videoFiles[k].path) { alreadyAdded2 = true; break; }
            }
            if (!alreadyAdded2) {
                results.push({ video: videoFiles[k], score: 70, matchType: 'reverse' });
            }
        }
    }
    if (results.length >= maxResults) return results.slice(0, maxResults);

    // Pass 4: Word matching
    if (kwWords.length > 0) {
        var wordMatches = [];
        for (var m = 0; m < videoFiles.length; m++) {
            var matchCount = countMatchingWords(kwWords, videoFiles[m].nameWords);
            if (matchCount > 0) {
                var alreadyAdded3 = false;
                for (var r3 = 0; r3 < results.length; r3++) {
                    if (results[r3].video.path === videoFiles[m].path) { alreadyAdded3 = true; break; }
                }
                if (!alreadyAdded3) {
                    var score = Math.round((matchCount / kwWords.length) * 60);
                    wordMatches.push({ video: videoFiles[m], score: score, matchType: 'word' });
                }
            }
        }

        // Sort by score descending
        for (var s1 = 0; s1 < wordMatches.length - 1; s1++) {
            for (var s2 = s1 + 1; s2 < wordMatches.length; s2++) {
                if (wordMatches[s2].score > wordMatches[s1].score) {
                    var tmp = wordMatches[s1];
                    wordMatches[s1] = wordMatches[s2];
                    wordMatches[s2] = tmp;
                }
            }
        }

        for (var w = 0; w < wordMatches.length && results.length < maxResults; w++) {
            results.push(wordMatches[w]);
        }
    }

    return results.slice(0, maxResults);
}

// ================= JSON HELPERS =================
function escapeJSON(s) {
    if (!s) return '';
    return String(s)
        .replace(/\\/g, '\\\\')
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r')
        .replace(/\t/g, '\\t');
}

function safeNumber(v) {
    var n = parseFloat(v);
    if (isNaN(n) || !isFinite(n)) return 0;
    return n;
}

// ================= GENERATE CUT LIST =================
function generateCutList(markers, videoFiles, outputPath) {
    var cuts = [];

    log('');
    log('Generating cut list with smart matching...');

    for (var i = 0; i < markers.length; i++) {
        var m = markers[i];
        log('[' + (i + 1) + '/' + markers.length + '] "' + m.keyword + '"');

        var matchResults = findVideosForKeyword(m.keyword, videoFiles, 3);

        if (matchResults.length > 0) {
            // Build clips array
            var clips = [];
            var timeRemaining = safeNumber(m.duration_seconds);
            var timelinePos = safeNumber(m.start_seconds);

            for (var v = 0; v < matchResults.length && timeRemaining > 0; v++) {
                var match = matchResults[v];
                var clipDuration = Math.min(timeRemaining, safeNumber(m.duration_seconds));

                clips.push({
                    video_path: match.video.path,
                    video_name: match.video.name,
                    timeline_pos: timelinePos,
                    clip_start: 0,
                    clip_end: clipDuration,
                    duration: clipDuration,
                    match_score: match.score,
                    match_type: match.matchType
                });

                timelinePos += clipDuration;
                timeRemaining -= clipDuration;

                log('  + ' + match.video.name + ' (score: ' + match.score + ', type: ' + match.matchType + ')');
            }

            cuts.push({
                index: safeNumber(m.index),
                keyword: m.keyword,
                timeline_start: safeNumber(m.start_seconds),
                timeline_end: safeNumber(m.end_seconds),
                timeline_duration: safeNumber(m.duration_seconds),
                clips: clips
            });
        } else {
            log('  No match found');
            cuts.push({
                index: safeNumber(m.index),
                keyword: m.keyword,
                timeline_start: safeNumber(m.start_seconds),
                timeline_end: safeNumber(m.end_seconds),
                timeline_duration: safeNumber(m.duration_seconds),
                clips: [],
                error: 'No matching video'
            });
        }
    }

    // Build JSON output
    var json = [];
    json.push('{');
    json.push('  "version": 2,');
    json.push('  "count": ' + cuts.length + ',');
    json.push('  "matched": ' + cuts.filter(function(c) { return c.clips && c.clips.length > 0; }).length + ',');
    json.push('  "cuts": [');

    for (var j = 0; j < cuts.length; j++) {
        var c = cuts[j];
        var cutLines = [];
        cutLines.push('    {');
        cutLines.push('      "index": ' + c.index + ',');
        cutLines.push('      "keyword": "' + escapeJSON(c.keyword) + '",');
        cutLines.push('      "timeline_start": ' + c.timeline_start + ',');
        cutLines.push('      "timeline_end": ' + c.timeline_end + ',');
        cutLines.push('      "timeline_duration": ' + c.timeline_duration + ',');

        // Clips array
        cutLines.push('      "clips": [');
        for (var k = 0; k < c.clips.length; k++) {
            var clip = c.clips[k];
            var clipJson = [];
            clipJson.push('        {');
            clipJson.push('          "video_path": "' + escapeJSON(clip.video_path) + '",');
            clipJson.push('          "video_name": "' + escapeJSON(clip.video_name) + '",');
            clipJson.push('          "timeline_pos": ' + clip.timeline_pos + ',');
            clipJson.push('          "clip_start": ' + clip.clip_start + ',');
            clipJson.push('          "clip_end": ' + clip.clip_end + ',');
            clipJson.push('          "duration": ' + clip.duration + ',');
            clipJson.push('          "match_score": ' + clip.match_score + ',');
            clipJson.push('          "match_type": "' + clip.match_type + '"');
            clipJson.push('        }' + (k < c.clips.length - 1 ? ',' : ''));
            cutLines.push(clipJson.join('\n'));
        }
        cutLines.push('      ]');

        if (c.error) {
            cutLines[cutLines.length - 1] += ',';
            cutLines.push('      "error": "' + escapeJSON(c.error) + '"');
        }

        cutLines.push('    }' + (j < cuts.length - 1 ? ',' : ''));
        json.push(cutLines.join('\n'));
    }

    json.push('  ]');
    json.push('}');

    return writeFile(outputPath, json.join('\n'));
}

// ================= MAIN =================
function main() {
    log('');
    log('========================================');
    log('  GENERATE CUT LIST V2 - SMART MATCH');
    log('========================================');

    var cfg = readPathConfig();
    if (!cfg) {
        alert('ERROR: Khong tim thay data/path.txt');
        return;
    }

    var dataFolder = normalizePath(cfg.data_folder || '');
    var resourceFolder = normalizePath(cfg.resource_folder || '');

    if (!dataFolder) {
        alert('ERROR: data_folder chua duoc dinh nghia');
        return;
    }

    if (!resourceFolder) {
        alert('ERROR: resource_folder chua duoc dinh nghia');
        return;
    }

    log('Data folder: ' + dataFolder);
    log('Resource folder: ' + resourceFolder);

    // Read markers.json
    var markersPath = joinPath(dataFolder, 'markers.json');
    if (!fileExists(markersPath)) {
        alert('ERROR: Khong tim thay markers.json');
        return;
    }

    var markersData = parseJSON(readFile(markersPath));
    if (!markersData || !markersData.markers) {
        alert('ERROR: Khong doc duoc markers.json');
        return;
    }

    var markers = markersData.markers;
    log('Loaded ' + markers.length + ' markers');

    // Get video files
    var videoFiles = getVideoFiles(resourceFolder);
    if (videoFiles.length === 0) {
        alert('ERROR: Khong tim thay video nao');
        return;
    }

    // Generate cut list
    var cutListPath = joinPath(dataFolder, 'cut_list.json');
    var success = generateCutList(markers, videoFiles, cutListPath);

    var elapsed = ((new Date().getTime() - PERF_START) / 1000).toFixed(1);

    if (success) {
        log('');
        log('========================================');
        log('  HOAN THANH!');
        log('  Time: ' + elapsed + 's');
        log('========================================');

        alert('Da tao cut_list.json!\n\nMarkers: ' + markers.length + '\nVideos: ' + videoFiles.length + '\nTime: ' + elapsed + 's');
    } else {
        alert('ERROR: Khong the ghi cut_list.json');
    }
}

main();
