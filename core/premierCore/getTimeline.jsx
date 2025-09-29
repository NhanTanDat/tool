/**
 * getTimeline.jsx
 * ------------------------------------------
 * Các hàm hỗ trợ lấy thông tin timeline cho Video Track trong Adobe Premiere Pro.
 * Yêu cầu chạy bên trong môi trường ExtendScript của Premiere.
 *
 * YÊU CẦU NGƯỜI DÙNG: "Thực hiện lấy timeline các phần tử của v track được chọn, tạo test là phần tử v track có số thứ tự lớn nhất (ở trên cùng)"
 * Diễn giải:
 *  - Xác định các video track có clip đang được chọn (clip.isSelected())
 *  - Chọn track có chỉ số lớn nhất trong số đó (top-most / ở trên cùng trong giao diện Premiere)
 *  - Lấy danh sách clip của track đó cùng metadata (name, start, end, inPoint, outPoint)
 *  - Tạo hàm test kiểm tra rằng track được chọn dùng để xuất chính là track có index lớn nhất trong danh sách track được chọn.
 *
 * Lưu ý API:
 *  - app.project.activeSequence : Sequence hiện tại
 *  - sequence.videoTracks[num] : truy cập từng VideoTrack (0..n-1)
 *  - track.clips : mảng clip
 *  - clip.isSelected() : clip có đang được chọn trên timeline hay không
 *  - clip.start / clip.end / clip.inPoint / clip.outPoint : đối tượng Time (có thể có thuộc tính ticks / seconds tuỳ phiên bản)
 */

// ===== Polyfill JSON (Một số phiên bản ExtendScript/Premiere cũ không có JSON) =====
if (typeof JSON === 'undefined') {
	var JSON = {};
}
if (typeof JSON.stringify !== 'function') {
	JSON.stringify = (function(){
		function esc(str){
			return ('"' + str
				.replace(/\\/g,'\\\\')
				.replace(/"/g,'\\"')
				.replace(/\r/g,'\\r')
				.replace(/\n/g,'\\n')
				.replace(/\t/g,'\\t')
				.replace(/\f/g,'\\f')
				.replace(/\b/g,'\\b') + '"');
		}
		function isArr(v){ return Object.prototype.toString.call(v)==='[object Array]'; }
		function stringify(v){
			var t = typeof v;
			if (v === null) return 'null';
			if (t === 'number' || t === 'boolean') return ''+v;
			if (t === 'string') return esc(v);
			if (t === 'undefined' || t === 'function') return 'null';
			if (isArr(v)) {
				var outA = [];
				for (var i=0;i<v.length;i++) outA.push(stringify(v[i]));
				return '[' + outA.join(',') + ']';
			}
			// object
			var parts = [];
			for (var k in v) if (v.hasOwnProperty(k)) {
				parts.push(esc(k)+ ':' + stringify(v[k]));
			}
			return '{' + parts.join(',') + '}';
		}
		return function(value/*, replacer, space*/){
			return stringify(value);
		};
	})();
}
if (typeof JSON.parse !== 'function') {
	JSON.parse = function(txt){
		// Cảnh báo: chỉ dùng nội bộ với dữ liệu tin cậy.
		return eval('(' + txt + ')');
	};
}

// ===== Xác định thư mục data động (dựa theo vị trí script) =====
var DATA_FOLDER = (function(){
	try {
		var scriptFile = new File($.fileName);              // .../core/premierCore/getTimeline.jsx
		var premierCoreDir = scriptFile.parent;             // premierCore
		var coreDir = premierCoreDir.parent;                // core
		var rootDir = coreDir.parent;                       // project root
		var dataDir = new Folder(rootDir.fsName + '/data');
		if (!dataDir.exists) { try { dataDir.create(); } catch(e){ $.writeln('[DATA_FOLDER] Cannot create data folder: ' + e); } }
		$.writeln('[DATA_FOLDER] Using data folder: ' + dataDir.fsName);
		return dataDir;
	} catch(e2) {
		$.writeln('[DATA_FOLDER] Fallback to desktop due to error: ' + e2);
		return Folder.desktop;
	}
})();

// --------- Utility Chuyển đổi Time ---------
function timeToSeconds(t) {
	try {
		if (!t) return 0;
		if (typeof t.seconds !== 'undefined') return t.seconds; // API mới
		if (typeof t.ticks !== 'undefined') { // fallback ticks -> seconds (Premiere: 254016000000 ticks = 1s) nếu cần chính xác hơn có thể điều chỉnh.
			var TICKS_PER_SECOND = 254016000000; // hằng số nội bộ Premiere (có thể thay đổi theo version; dùng xấp xỉ)
			return t.ticks / TICKS_PER_SECOND;
		}
	} catch (e) { /* ignore */ }
	return 0;
}

// --------- Lấy sequence hiện tại ---------
function getActiveSequence() {
	if (typeof app === 'undefined' || !app.project) {
		$.writeln('[getTimeline] Không ở trong Premiere.');
		return null;
	}
	var seq = app.project.activeSequence;
	if (!seq) {
		$.writeln('[getTimeline] Không có activeSequence.');
	}
	return seq;
}

// --------- Tìm các video track có ít nhất một clip được chọn ---------
function getSelectedVideoTrackIndices() {
	var seq = getActiveSequence();
	if (!seq) return [];
	var indices = [];
	if (!seq.videoTracks || seq.videoTracks.numTracks === 0) {
		$.writeln('[getTimeline] Không có video track.');
		return indices;
	}
	for (var i = 0; i < seq.videoTracks.numTracks; i++) {
		var vt = seq.videoTracks[i];
		if (!vt || !vt.clips || vt.clips.numItems === 0) continue;
		for (var c = 0; c < vt.clips.numItems; c++) {
			var clip = vt.clips[c];
			try {
				if (clip && typeof clip.isSelected === 'function' && clip.isSelected()) {
					indices.push(i);
					break; // sang track kế tiếp
				}
			} catch (e) { /* ignore */ }
		}
	}
	$.writeln('[getTimeline] Track được chọn: ' + indices.join(', '));
	return indices;
}

// --------- Lấy index track lớn nhất trong danh sách ---------
function getTopmostSelectedVideoTrackIndex() {
	var sel = getSelectedVideoTrackIndices();
	if (!sel.length) return -1;
	var maxIdx = sel[0];
	for (var i = 1; i < sel.length; i++) {
		if (sel[i] > maxIdx) maxIdx = sel[i];
	}
	return maxIdx;
}

// Fallback: tìm video track đầu tiên có ít nhất 1 clip (dùng cho option A)
function findFirstNonEmptyVideoTrackIndex() {
	var seq = getActiveSequence();
	if (!seq || !seq.videoTracks) return -1;
	for (var i = 0; i < seq.videoTracks.numTracks; i++) {
		var vt = seq.videoTracks[i];
		if (vt && vt.clips && vt.clips.numItems > 0) {
			return i;
		}
	}
	return -1;
}

// --------- Lấy metadata clip của một video track theo index ---------
function getVideoTrackClipsMetadata(trackIndex) {
	var seq = getActiveSequence();
	if (!seq) return [];
	if (trackIndex < 0 || trackIndex >= seq.videoTracks.numTracks) {
		$.writeln('[getTimeline] trackIndex không hợp lệ: ' + trackIndex);
		return [];
	}
	var vt = seq.videoTracks[trackIndex];
	if (!vt || !vt.clips) return [];
	function extractTextFromClip(clip) {
		if (!clip || !clip.projectItem) return '';
		try {
			if (typeof clip.projectItem.getComponents === 'function') {
				var comps = clip.projectItem.getComponents();
				if (comps && comps.numItems) {
					for (var ci = 0; ci < comps.numItems; ci++) {
						var comp = comps[ci];
						if (!comp || typeof comp.getParameters !== 'function') continue;
						var params = comp.getParameters();
						if (!params || !params.numItems) continue;
						for (var pi = 0; pi < params.numItems; pi++) {
							var p = params[pi];
							try {
								var dn = p.displayName || '';
								if (/text|source text|caption|contents/i.test(dn)) {
									if (typeof p.getValue === 'function') {
										var val = p.getValue();
										if (val && val.toString) {
											var s = val.toString();
											if (s) return s;
										}
									}
								}
							} catch(e1) { /* ignore param */ }
						}
					}
				}
			}
		} catch(e2) {}
		return '';
	}
	var list = [];
	for (var c = 0; c < vt.clips.numItems; c++) {
		var clip = vt.clips[c];
		if (!clip) continue;
		var item = {};
		try {
			item.name = clip.name || (clip.projectItem ? clip.projectItem.name : '');
			item.startSeconds = timeToSeconds(clip.start);
			item.endSeconds = timeToSeconds(clip.end);
			item.inPointSeconds = timeToSeconds(clip.inPoint);
			item.outPointSeconds = timeToSeconds(clip.outPoint);
			item.durationSeconds = item.endSeconds - item.startSeconds;
			item.indexInTrack = c;
			item.isSelected = (typeof clip.isSelected === 'function') ? clip.isSelected() : false;
			item.textContent = extractTextFromClip(clip);
		} catch (e) {
			item.error = '' + e;
		}
		list.push(item);
	}
	return list;
}

// --------- Lấy metadata của track video được chọn ở trên cùng ---------
function getTopmostSelectedVideoTrackClips() {
	var idx = getTopmostSelectedVideoTrackIndex();
	if (idx < 0) {
		$.writeln('[getTimeline] Không có video track nào đang được chọn.');
		return [];
	}
	$.writeln('[getTimeline] Topmost selected video track index = ' + idx);
	return getVideoTrackClipsMetadata(idx);
}

// --------- Test: Xác nhận track dùng để lấy clip là track có index lớn nhất ---------
function assertTopmostSelectedVideoTrackIsMax() {
	var sel = getSelectedVideoTrackIndices();
	if (!sel.length) {
		$.writeln('[getTimeline][TEST] FAIL: Không có track nào được chọn.');
		return false;
	}
	var top = getTopmostSelectedVideoTrackIndex();
	for (var i = 0; i < sel.length; i++) {
		if (sel[i] > top) {
			$.writeln('[getTimeline][TEST] FAIL: Tồn tại track cao hơn (' + sel[i] + ') > ' + top);
			return false;
		}
	}
	$.writeln('[getTimeline][TEST] PASS: Track ' + top + ' là lớn nhất trong các track đã chọn.');
	return true;
}

// --------- Helper: Xuất JSON (để panel / external đọc) ---------
function getTopmostSelectedTrackClipsJSON(pretty) {
	var clips = getTopmostSelectedVideoTrackClips();
	try {
		return JSON.stringify(clips, null, pretty ? 2 : 0);
	} catch (e) {
		return '[]';
	}
}

// --------- Example manual run (bỏ comment để test nhanh trong ExtendScript Toolkit) ---------
// (function(){
//     var ok = assertTopmostSelectedVideoTrackIsMax();
//     var json = getTopmostSelectedTrackClipsJSON(true);
//     $.writeln('Selected top track clips JSON:\n' + json);
// })();

// Expose hàm ra ngoài (để panel CEP hoặc evalScript có thể gọi)
// Các host cũ có thể không cần, nhưng gắn vào global cho chắc.
this.getTopmostSelectedVideoTrackClips = getTopmostSelectedVideoTrackClips;
this.getTopmostSelectedTrackClipsJSON = getTopmostSelectedTrackClipsJSON;
this.assertTopmostSelectedVideoTrackIsMax = assertTopmostSelectedVideoTrackIsMax;

// ====== BỔ SUNG: Lấy lần lượt start-end time của tất cả phần tử trong 1 track (giả định track là text) ======
/**
 * getSequenceFrameRate() -> số frame/second (float)
 */
function getSequenceFrameRate() {
	var seq = getActiveSequence();
	if (!seq || typeof seq.getSettings !== 'function') return 25; // fallback mặc định
	try {
		var s = seq.getSettings();
		if (s && s.videoFrameRate && s.videoFrameRate.numerator && s.videoFrameRate.denominator) {
			return s.videoFrameRate.numerator / s.videoFrameRate.denominator;
		}
	} catch (e) { /* ignore */ }
	return 25;
}

/**
 * Chuyển seconds -> timecode SMPTE đơn giản (HH:MM:SS:FF) theo frameRate.
 */
function secondsToTimecode(seconds, frameRate) {
	if (!frameRate) frameRate = getSequenceFrameRate();
	var totalFrames = Math.round(seconds * frameRate);
	if (totalFrames < 0) totalFrames = 0;
	var fps = Math.round(frameRate);
	var frames = totalFrames % fps;
	var totalSeconds = (totalFrames - frames) / fps;
	var s = totalSeconds % 60;
	var totalMinutes = (totalSeconds - s) / 60;
	var m = totalMinutes % 60;
	var h = (totalMinutes - m) / 60;
	function pad(n) { return (n < 10 ? '0' : '') + n; }
	function pad2(n) { return (n < 10 ? '0' : '') + n; }
	return pad2(h) + ':' + pad2(m) + ':' + pad2(s) + ':' + pad2(frames);
}

/**
 * getTrackClipRanges(trackIndex, opts)
 *  - Trả về danh sách clip (được sắp xếp theo startSeconds tăng dần) của một video track.
 *  - Mỗi phần tử gồm: {indexInTrack, name, startSeconds, endSeconds, durationSeconds, startTimecode, endTimecode}
 *  - opts.onlySelected (bool): chỉ lấy clip đang được chọn.
 *  - opts.filterRegex (string): chỉ giữ những clip có name match regex.
 *  - Vì track "toàn bộ là text" nên có thể không cần lọc, nhưng nếu muốn lọc theo tên (VD: bắt đầu bằng "TXT_"), dùng filterRegex.
 */
function getTrackClipRanges(trackIndex, opts) {
	opts = opts || {};
	var includeTC = !!opts.includeTimecode; // mặc định không xuất timecode nếu không cần
	var seq = getActiveSequence();
	if (!seq) return [];
	if (!seq.videoTracks || trackIndex < 0 || trackIndex >= seq.videoTracks.numTracks) {
		$.writeln('[getTimeline] getTrackClipRanges: trackIndex không hợp lệ ' + trackIndex);
		return [];
	}
	var vt = seq.videoTracks[trackIndex];
	if (!vt || !vt.clips) return [];
	var frameRate = getSequenceFrameRate();
	var list = [];
	var regex = null;
	if (opts.filterRegex) {
		try { regex = new RegExp(opts.filterRegex); } catch (e) { $.writeln('[getTimeline] Regex lỗi: ' + e); }
	}
	for (var c = 0; c < vt.clips.numItems; c++) {
		var clip = vt.clips[c];
		if (!clip) continue;
		if (opts.onlySelected && !(clip.isSelected && clip.isSelected())) continue;
		var name = '';
		try { name = clip.name || (clip.projectItem ? clip.projectItem.name : ''); } catch (e1) {}
		if (regex && !regex.test(name)) continue;
		var startS = timeToSeconds(clip.start);
		var endS = timeToSeconds(clip.end);
		var mediaPath = '';
		try { if (clip.projectItem && typeof clip.projectItem.getMediaPath === 'function') { mediaPath = clip.projectItem.getMediaPath(); } } catch(e2) {}
		var textContent = '';
		// tái sử dụng logic extract text (nhỏ gọn hơn):
		try {
			if (clip.projectItem && typeof clip.projectItem.getComponents === 'function') {
				var comps2 = clip.projectItem.getComponents();
				if (comps2 && comps2.numItems) {
					for (var ci2 = 0; ci2 < comps2.numItems && !textContent; ci2++) {
						var comp2 = comps2[ci2];
						if (!comp2 || typeof comp2.getParameters !== 'function') continue;
						var params2 = comp2.getParameters();
						if (!params2 || !params2.numItems) continue;
						for (var pi2 = 0; pi2 < params2.numItems; pi2++) {
							var p2 = params2[pi2];
							try {
								var dn2 = p2.displayName || '';
								if (/text|source text|caption|contents/i.test(dn2) && typeof p2.getValue === 'function') {
									var val2 = p2.getValue();
									if (val2 && val2.toString) {
										var s2 = val2.toString();
										if (s2) { textContent = s2; break; }
									}
								}
							} catch(ee){}
						}
					}
				}
			}
		} catch(eTxt){}
		var obj = {
			indexInTrack: c,
			name: name,
			startSeconds: startS,
			endSeconds: endS,
			durationSeconds: endS - startS,
			mediaPath: mediaPath,
			textContent: textContent
		};
		if (includeTC) {
			obj.startTimecode = secondsToTimecode(startS, frameRate);
			obj.endTimecode = secondsToTimecode(endS, frameRate);
		}
		list.push(obj);
	}
	// Sắp xếp theo startSeconds
	list.sort(function(a, b){ return a.startSeconds - b.startSeconds; });
	return list;
}

/**
 * getTopmostSelectedTrackClipRanges(opts)
 *  - Lấy ranges của video track được chọn ở trên cùng.
 */
function getTopmostSelectedTrackClipRanges(opts) {
	var idx = getTopmostSelectedVideoTrackIndex();
	if (idx < 0) return [];
	return getTrackClipRanges(idx, opts);
}

/**
 * getTrackClipRangesJSON(trackIndex, opts, pretty)
 */
function getTrackClipRangesJSON(trackIndex, opts, pretty) {
	try { return JSON.stringify(getTrackClipRanges(trackIndex, opts), null, pretty ? 2 : 0); } catch (e) { return '[]'; }
}

/**
 * getTopmostSelectedTrackClipRangesJSON(opts, pretty)
 */
function getTopmostSelectedTrackClipRangesJSON(opts, pretty) {
	try { return JSON.stringify(getTopmostSelectedTrackClipRanges(opts), null, pretty ? 2 : 0); } catch (e) { return '[]'; }
}

// Expose các hàm mới
this.getTrackClipRanges = getTrackClipRanges;
this.getTopmostSelectedTrackClipRanges = getTopmostSelectedTrackClipRanges;
this.getTrackClipRangesJSON = getTrackClipRangesJSON;
this.getTopmostSelectedTrackClipRangesJSON = getTopmostSelectedTrackClipRangesJSON;

// ========= QUICK TEST WITH ALERT =========
/**
 * runQuickTimelineTest(opts)
 *  - opts.trackIndex: số index track muốn test (nếu bỏ qua sẽ dùng topmost selected).
 *  - opts.onlySelected: chỉ lấy clip selected.
 *  - Thực hiện:
 *      + Xác định track
 *      + Lấy ranges
 *      + Chạy assertTopmostSelectedVideoTrackIsMax (nếu dùng chế độ auto chọn)
 *      + Alert tổng kết (PASS/FAIL, clip count, khoảng thời gian đầu/cuối)
 *  - Trả về object kết quả.
 */
function runQuickTimelineTest(opts) {
	// Đảm bảo không bị typo (trước đó dùng 'ops')
	opts = opts || {};
	var usedProvidedTrack = (typeof opts.trackIndex === 'number');
	var trackIndex = usedProvidedTrack ? opts.trackIndex : getTopmostSelectedVideoTrackIndex();
	var fallbackUsed = false;
	var allowFallback = (opts.allowFallback !== false); // mặc định true
	if (trackIndex < 0 && !usedProvidedTrack && allowFallback) {
		trackIndex = findFirstNonEmptyVideoTrackIndex();
		if (trackIndex >= 0) {
			fallbackUsed = true;
			$.writeln('[runQuickTimelineTest] Fallback dùng track đầu tiên có clip: ' + trackIndex);
		}
	}
	if (trackIndex < 0) {
		if (typeof alert === 'function') alert('Không xác định được video track (không có clip nào được chọn hay timeline rỗng).');
		return { ok:false, reason:'NO_TRACK', fallbackTried: allowFallback };
	}
	var ranges = getTrackClipRanges(trackIndex, { onlySelected: !!opts.onlySelected, includeTimecode: !!opts.includeTimecode });
	var pass = true;
	if (!usedProvidedTrack && !fallbackUsed) {
		pass = assertTopmostSelectedVideoTrackIsMax();
	}
	var clipCount = ranges.length;
	// Fallback: nếu không có startTimecode/endTimecode (do includeTimecode = false) thì dùng số giây raw
	var firstStartStr = 'N/A';
	var lastEndStr = 'N/A';
	if (clipCount) {
		var firstClip = ranges[0];
		var lastClip = ranges[clipCount - 1];
		firstStartStr = firstClip.startTimecode ? firstClip.startTimecode : (firstClip.startSeconds + 's');
		lastEndStr = lastClip.endTimecode ? lastClip.endTimecode : (lastClip.endSeconds + 's');
	}
	var summary = 'Track #' + trackIndex + ' | Clips: ' + clipCount + '\n' +
				  'Start: ' + firstStartStr + ' -> End: ' + lastEndStr + '\n' +
				  (usedProvidedTrack ? '(Track do người dùng chỉ định)\n' : (fallbackUsed ? 'Fallback First Non-Empty Track\n' : 'Topmost Selected Track\n')) +
				  'Assertion (topmost is max): ' + (pass ? 'PASS' : 'FAIL');
	$.writeln('[runQuickTimelineTest]\n' + summary);
	if (typeof alert === 'function') {
		try { alert(summary); } catch (e) { /* ignore */ }
	}
	// ===== Option D: Export JSON / CSV nếu được yêu cầu =====
	var exportResults = {};
	if (ranges.length && (opts.exportJSONPath || opts.exportCSVPath)) {
		function writeFile(path, content) {
			try {
				var f = new File(path);
				if (f.exists) { try { f.remove(); } catch (e5) {} }
				if (f.open('w')) {
					f.write(content);
					f.close();
					return true;
				}
			} catch (e) {
				$.writeln('[runQuickTimelineTest][EXPORT] Lỗi ghi file ' + path + ': ' + e);
			}
			return false;
		}
		if (opts.exportJSONPath) {
			var jsonContent = JSON.stringify({ trackIndex: trackIndex, clips: ranges }, null, 2);
			exportResults.json = writeFile(opts.exportJSONPath, jsonContent);
			$.writeln('[runQuickTimelineTest][EXPORT] JSON -> ' + opts.exportJSONPath + ' : ' + exportResults.json);
			if (!exportResults.json && typeof alert === 'function') {
				try { alert('JSON export FAILED: ' + opts.exportJSONPath + '\nHãy kiểm tra quyền ghi thư mục này.'); } catch(ea) {}
			}
		}
		if (opts.exportCSVPath) {
			var header;
			var haveTC = !!opts.includeTimecode;
			if (haveTC) {
				header = 'indexInTrack,name,startSeconds,endSeconds,durationSeconds,startTimecode,endTimecode,mediaPath,textContent';
			} else {
				header = 'indexInTrack,name,startSeconds,endSeconds,durationSeconds,mediaPath,textContent';
			}
			var lines = [header];
			for (var i = 0; i < ranges.length; i++) {
				var r = ranges[i];
				var name = (r.name||'').replace(/"/g,'""');
				if (name.indexOf(',') >= 0) name = '"' + name + '"';
				var media = (r.mediaPath||'').replace(/"/g,'""');
				if (media.indexOf(',') >= 0) media = '"' + media + '"';
				var txt = (r.textContent||'').replace(/"/g,'""');
				if (txt.indexOf(',') >= 0) txt = '"' + txt + '"';
				if (haveTC) {
					lines.push([r.indexInTrack, name, r.startSeconds, r.endSeconds, r.durationSeconds, r.startTimecode||'', r.endTimecode||'', media, txt].join(','));
				} else {
					lines.push([r.indexInTrack, name, r.startSeconds, r.endSeconds, r.durationSeconds, media, txt].join(','));
				}
			}
			exportResults.csv = writeFile(opts.exportCSVPath, lines.join('\n'));
			$.writeln('[runQuickTimelineTest][EXPORT] CSV -> ' + opts.exportCSVPath + ' : ' + exportResults.csv);
			if (!exportResults.csv && typeof alert === 'function') {
				try { alert('CSV export FAILED: ' + opts.exportCSVPath + '\nHãy kiểm tra quyền ghi thư mục này.'); } catch(ec) {}
			}
		}
	}
	return {
		ok: pass,
		trackIndex: trackIndex,
		clipCount: clipCount,
		firstTimecode: firstStartStr,
		lastTimecode: lastEndStr,
		usedProvidedTrack: usedProvidedTrack,
		fallbackUsed: fallbackUsed,
		ranges: ranges,
		exports: exportResults
	};
}

this.runQuickTimelineTest = runQuickTimelineTest;

// Auto-run quick test when script loaded (comment out if not desired)
// Lưu file JSON/CSV ngay trong cùng thư mục code (thư mục chứa script này) để dễ tìm.
(function(){
	try {
		var jsonPath = DATA_FOLDER.fsName + '/timeline_export.json';
		var csvPath  = DATA_FOLDER.fsName + '/timeline_export.csv';
		$.writeln('[auto-run] Xuất timeline ra: ' + jsonPath + ' và ' + csvPath);
		runQuickTimelineTest({
			onlySelected: false,
			exportJSONPath: jsonPath,
			exportCSVPath: csvPath
		});
	} catch(e) {
		$.writeln('[auto-run] Lỗi auto export: ' + e);
	}
})();

// Helper để kiểm tra nhanh đường dẫn script & thử ghi 1 file test
function debugCheckScriptPath() {
    try {
        var f = new File($.fileName);
        $.writeln('[debugCheckScriptPath] Script path: ' + f.fsName);
        var testFile = new File(f.path + '/_write_test.txt');
        if (testFile.open('w')) { testFile.write('test'); testFile.close(); $.writeln('[debugCheckScriptPath] Ghi test OK: ' + testFile.fsName); }
        else $.writeln('[debugCheckScriptPath] Không mở được file test để ghi');
    } catch(e) { $.writeln('[debugCheckScriptPath] Lỗi: ' + e); }
}
this.debugCheckScriptPath = debugCheckScriptPath;

