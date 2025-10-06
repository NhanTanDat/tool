// NOTE: ExtendScript không hỗ trợ cú pháp ES6 import; bỏ dòng import và dùng hàm tự định nghĩa.
// Helper notify giống các file khác (tùy chọn bật alert)
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


// Parser CSV xuất từ getTimeline (header linh hoạt có hoặc không có timecode)
function readTimelineCSVFile(filePath){
    try {
        var f = new File(filePath);
        if (!f.exists) return [];
        if (!f.open('r')) return [];
        var lines = [];
        while(!f.eof) lines.push(f.readln());
        f.close();
        if (!lines.length) return [];
        var header = lines[0];
        var cols = header.split(',');
        var map = {};
        for (var i=0;i<cols.length;i++){ map[cols[i]] = i; }
        // Xác định chỉ số cột
        var idxStart = map['startSeconds'];
        var idxEnd = map['endSeconds'];
        var idxName = map['name'];
        var idxText = map['textContent'];
        if (typeof idxStart === 'undefined' || typeof idxEnd === 'undefined') return [];
        var out = [];
        for (var r=1;r<lines.length;r++){
            var line = lines[r];
            if (!line) continue;
            var parts = splitCSVLine(line);
            if (parts.length < cols.length) continue;
            var s = parseFloat(parts[idxStart]);
            var e = parseFloat(parts[idxEnd]);
            if (isNaN(s) || isNaN(e) || s < 0 || e <= s) continue;
            var nm = idxName!=null ? parts[idxName] : 'Clip';
            var txt = idxText!=null ? parts[idxText] : '';
            out.push({ index: out.length, startSeconds: s, endSeconds: e, name: nm, textContent: txt });
        }
        if (out.length) $.writeln('[readTimelineCSVFile] Parsed ' + out.length + ' clips from CSV.');
        return out;
    } catch(e){
        $.writeln('[readTimelineCSVFile] Error: ' + e);
        return [];
    }
}

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
//file này chuyên thực hiện việc cắt và đẩy clip vào timeline theo data từ file JSON/CSV, đã có sẵn các bin và file media trong project
var project;
var sequence;
// Lưu lại các khoảng (in,out) đã dùng cho mỗi clip nguồn để tránh cắt trùng nhau quá nhiều
// Key: clipName + '_' + playableDurationRounded
// Lưu cấu trúc tránh trùng: dùng thuộc tính 'start' và 'end' thay vì 'in'/'out' để tránh xung đột từ khóa.
// Backward compatibility: nếu gặp object cũ có 'in'/'out' sẽ được chuyển đổi sang 'start'/'end'.
var _USED_INTERVALS = {}; // { key: [ {start: Number, end: Number} , ... ] }

// Cấu hình thuật toán tránh trùng
var NON_OVERLAP_CONFIG = {
    maxRandomTries: 12,      // số lần thử random khác trước khi quét gap
    minSeparationFactor: 0.35, // yêu cầu đoạn mới không overlap hơn (factor * finalDuration)
    jitterFraction: 0.15     // khi chọn trong gap có thể dịch một chút
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
    for (var t=0;t<attempts;t++){
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

// =================== THAO TÁC THUẦN GIÂY ===================
// Sử dụng trực tiếp thuộc tính .seconds của time object; bỏ toàn bộ xử lý ticks.
function timeObjToSeconds(t){
    try { return (t && typeof t.seconds !== 'undefined') ? t.seconds : 0; } catch(e){ return 0; }
}


//hàm initialize Premiere Pro project và sequence
function initializeProjectAndSequence() {
    if (typeof app === 'undefined' || !app.project) {
        alert('Script phải chạy bên trong Adobe Premiere Pro.');

    }
    project = app.project;
    if (!project) {
        alert('Không thể truy cập project hiện tại.');

    }
    sequence = project.activeSequence;
    if (!sequence) {
        alert('Không có sequence nào đang mở.');

    }
    $.writeln('[initializeProjectAndSequence] Project and active sequence initialized.');

}

//hàm gen thời gian duration ngẫu nhiên trong khoảng min và max (đơn vị giây)
function getRandomDuration(minSeconds, maxSeconds) {
    if (minSeconds < 0 || maxSeconds < 0 || minSeconds >= maxSeconds) {
        $.writeln('[getRandomDuration] Invalid min or max seconds');
        return 0;
    }
    var randomSeconds = Math.random() * (maxSeconds - minSeconds) + minSeconds;
    return randomSeconds;
}

//hàm tự tạo v track mới trên cùng
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




//hàm thực hiện lấy 1 video item từ project theo tên bin, chọn ngẫu nhiên 1 video trong bin đó, sau đó thực hiện cắt và đẩy vào timeline trong v track được chọn
function cutAndPushClipToTimeline(binName, idxBinVd, startTime, endTime, sequence, targetVideoTrack) {
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
    for (var i = 0; i < rootItem.children.numItems; i++) {
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

    //lấy ra video thứ idxBinVd trong bin
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

    // Kiểm tra thời gian startTime và endTime
    if (startTime < 0 || endTime <= startTime) {
        $.writeln('[cutAndPushClipToTimeline] Invalid startTime or endTime');
        return startTime;
    }

    // Tạo đoạn clip mới từ videoItem
    var inputDuration = endTime - startTime; // tổng thời lượng cần lấp trên timeline
    var randomDuration = getRandomDuration(2, 4); // độ dài đoạn lấy
    var finalDuration;
    if (inputDuration <= randomDuration) finalDuration = inputDuration; // đoạn quá ngắn, lấy hết
    else finalDuration = randomDuration; // giữ phần lớn thời gian, trừ 1 đoạn ngẫu nhiên

    // Lấy thời gian in/out gốc của clip nguồn (giây) trực tiếp
    var srcInSec = timeObjToSeconds(videoItem.getInPoint());
    var srcOutSec = timeObjToSeconds(videoItem.getOutPoint());
    var srcPlayable = srcOutSec - srcInSec;
    if (srcPlayable <= 0) {
        $.writeln('[cutAndPushClipToTimeline] Source clip has non-positive duration');
        return startTime;
    }
    // Phạm vi còn lại để chọn vị trí bắt đầu ngẫu nhiên bên trong clip nguồn
    var key = _intervalKey(videoItem, srcPlayable);
    var newInSec = _pickNonOverlappingStart(srcInSec, srcOutSec, finalDuration, key);
    var newOutSec = newInSec + finalDuration;
    if (newOutSec > srcOutSec) newOutSec = srcOutSec; // đảm bảo không vượt quá

    // Gọi createSubClip với giá trị giây (Premiere sẽ tự nội suy nếu hỗ trợ; nếu version yêu cầu ticks thì cần phục hồi logic cũ)
    var newClip = null;
    try {
        newClip = videoItem.createSubClip(
            videoItem.name + '_subclip_' + startTime.toFixed(3) + '_' + endTime.toFixed(3),
            newInSec,
            newOutSec,
            0,
            true,
            0
        );
    } catch(eCreate) {
        $.writeln('[cutAndPushClipToTimeline] createSubClip failed with seconds: ' + eCreate);
        return startTime; // không fallback ticks theo yêu cầu bỏ hẳn ticks
    }

    if (!newClip) {
        $.writeln('[cutAndPushClipToTimeline] Failed to create subclip from: ' + videoItem.name);
        return startTime;
    }
    $.writeln('[cutAndPushClipToTimeline] Created subclip: ' + newClip.name + ' from ' + newInSec.toFixed(3) + 's to ' + newOutSec.toFixed(3) + 's (duration: ' + finalDuration.toFixed(3) + 's) key=' + key);

    // Đẩy đoạn clip mới vào timeline tại vị trí startTime (giây)
    try {
        var videoIndex = sequence.videoTracks.numTracks - 1; // track video cao nhất
        var audioIndex = sequence.audioTracks.numTracks - 1; // track audio cao nhất
        targetVideoTrack.insertClip(newClip, startTime, videoIndex, audioIndex);
    } catch(insErr) {
        $.writeln('[cutAndPushClipToTimeline] insertClip failed (seconds) -> ' + insErr);
    }

    $.writeln('[cutAndPushClipToTimeline] Inserted subclip into timeline at ' + startTime + ' seconds on track.');

    return startTime + finalDuration; // Trả về thời gian kết thúc của clip vừa chèn, để lần sau chèn tiếp từ đó
}


//hàm test cut và push clip vào timeline
function testCutAndPush() {
    initializeProjectAndSequence();
    if(!project || !sequence) return;

    var topIndex = sequence.videoTracks.numTracks - 1;
    if (topIndex < 0) { $.writeln('[testCutAndPush] No video track available'); return; }
    var targetVideoTrack = sequence.videoTracks[topIndex];
    if (!targetVideoTrack) { $.writeln('[testCutAndPush] Failed to get top video track'); return; }

    var startTime = 40.3333333333; // giây
    var endTime   = 48.9666666667; // giây

    while (startTime < endTime) {
        var prev = startTime;
        startTime = cutAndPushClipToTimeline("Amber_Portwood_tiktok", 0, startTime, endTime, sequence, targetVideoTrack);
        if (startTime === null || startTime === prev) { // không tiến lên -> dừng tránh vòng lặp vô hạn
            $.writeln('[testCutAndPush] Stop loop (no progress)');
            break;
        }
    }
    $.writeln('[testCutAndPush] Finished cutting and pushing clips to timeline.');
}

// Uncomment the line below to run the test function directly
// testCutAndPush();

function cutAndPushAllTimeline(tlFilePath) { 
    // Nếu không truyền vào, dùng file mặc định timeline_merged.txt trong DATA_FOLDER
    if (!tlFilePath || tlFilePath === '') {
        // Ưu tiên plaintext merge; nếu chưa có sẽ thử JSON rồi CSV sau.
        var defaultPath = joinPath(DATA_FOLDER, 'timeline_merged.txt');
        tlFilePath = new File(defaultPath);
        $.writeln('[cutAndPushAllTimeline] Default primary path: ' + defaultPath);
    } else if (typeof tlFilePath === 'string') {
        // Nếu truyền string, convert thành File object
        tlFilePath = new File(tlFilePath);
    }
    // Đảm bảo tlFilePath là File object
    if (!(tlFilePath instanceof File)) {
        notify('tlFilePath phải là đường dẫn file hoặc File object');
        return -1;
    }
    initializeProjectAndSequence();
    if(!project || !sequence) return -1;

    // var topIndex = sequence.videoTracks.numTracks - 1;
    // //nếu toplayer không trống, tạo track mới
    // if (topIndex >= 0) {
    //     var topTrack = sequence.videoTracks[topIndex];
    //     if (topTrack.clips && topTrack.clips.numItems > 0) {
    //         $.writeln('[cutAndPushAllTimeline] Top video track is not empty, adding a new track.');
    //         topTrack = addVideoTrackAtTop(sequence);
    //         if (!topTrack) {
    //             notify('Không thể tạo track video mới trên cùng.');
    //             return -1;
    //         }
    //     }
    // }
    var targetVideoTrack = sequence.videoTracks[sequence.videoTracks.numTracks - 1];
    if (!targetVideoTrack) {
        notify('Không thể lấy track video trên cùng.');
        return -1;
    }

    // đọc file timeline (plain text)
    var tlEntries = [];
    //nếu file là csv thì dùng hàm đọc csv, không dùng endWith, match để tránh lỗi
    if (tlFilePath.fsName.match(/\.csv$/)) {
        tlEntries = readTimelineCSVFile(tlFilePath);
    } else {
        return notify('Chỉ hỗ trợ file CSV hiện tại: ' + tlFilePath.fsName), -1;
    }
    if (!tlEntries.length) { notify('Không có entry hợp lệ trong file: ' + tlFilePath.fsName); return -1; }

    $.writeln('[cutAndPushAllTimeline] Read ' + tlEntries.length + ' entries from timeline file.');
    var processedCount = 0;
    var sizeBin = {}; // cache bin sizes
    // Map quản lý pool index cho từng bin: { binName: [idx... (đã shuffle)] }
    var binIdxMap = {};

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
        // pop 1 phần tử cuối cùng
        return binIdxMap[binName].pop();
    }

    for (var i = 0; i < tlEntries.length; i++) {
        var entry = tlEntries[i];
        var startSeconds = entry.startSeconds;
        var endSeconds = entry.endSeconds;
        var textContent = entry.textContent || '';
        //đổi ten bin theo textContent thay " " thành "_"
        var binName = textContent ? textContent.replace(/\s+/g, '_') : '';
        if (!binName) {
            $.writeln('[cutAndPushAllTimeline] Skipping entry with empty bin name at line ' + (i+1));
            continue;
        }
        //lấy size bin, đặt thành các giá trị key: binName - value: size integer
        var binSize = 0;
        if (sizeBin.hasOwnProperty(binName)) {
            binSize = sizeBin[binName];
        } else {
            //lấy size bin từ project
            var rootItem = project.rootItem;
            if (!rootItem) {
                $.writeln('[cutAndPushAllTimeline] project.rootItem is null or undefined');
                continue;
            }
            var targetBin = null;
            for (var j = 0; j < rootItem.children.numItems; j++) {
                var child = rootItem.children[j];
                if (child && child.type === 2 && child.name === binName) { // 2 = Bin
                    targetBin = child;
                    break;
                }
            }
            if (!targetBin) {
                $.writeln('[cutAndPushAllTimeline] Bin not found: ' + binName + ' at line ' + (i+1));
                continue;
            }
            binSize = targetBin.children.numItems;
            if (binSize <= 0) {
                $.writeln('[cutAndPushAllTimeline] Bin is empty: ' + binName + ' at line ' + (i+1));
                continue;
            }
            sizeBin[binName] = binSize; // lưu lại size bin
        }
        // Lựa chọn idx theo pool đã shuffle/popup cho từng binName
        while (true){
            var idxInBin = popIdxFromBin(binName, binSize);
            var prevStart = startSeconds;
            startSeconds = cutAndPushClipToTimeline(binName, idxInBin, startSeconds, endSeconds, sequence, targetVideoTrack);
            if (startSeconds === null || startSeconds === prevStart) { // không tiến lên -> dừng tránh vòng lặp vô hạn
                $.writeln('[cutAndPushAllTimeline] Stop loop for entry at line ' + (i+1) + ' (no progress)');
                break;
            }
            if (startSeconds >= endSeconds) {
                $.writeln('[cutAndPushAllTimeline] Finished entry at line ' + (i+1));
                break; // hoàn thành mục này
            }
            // Khi pool rỗng, lần gọi popIdxFromBin tiếp theo sẽ tự tái tạo pool với shuffle ngẫu nhiên
        }
        processedCount++;
    }
    notify('Hoàn thành chèn ' + processedCount + ' mục vào timeline từ file: ' + tlFilePath.fsName);
    return processedCount;
}

//test

// Allow override from runAll.jsx: when RUNALL_TIMELINE_CSV_PATH is defined, prefer that.
var csvDef = joinPath(DATA_FOLDER, 'timeline_export_merged.csv');
cutAndPushAllTimeline(csvDef);