
// NOTE: ExtendScript không hỗ trợ cú pháp ES6 import; bỏ dòng import và dùng hàm tự định nghĩa.
// Helper notify giống các file khác (tùy chọn bật alert)
var ENABLE_ALERTS = false;
function notify(msg){
    $.writeln('[cutAndPush] ' + msg);
    if (ENABLE_ALERTS) { try { alert(msg); } catch(e){} }
}

// ================== DYNAMIC DATA FOLDER RESOLUTION ==================
// Tìm thư mục 'data' đi ngược lên tối đa maxLevels từ vị trí script.
// Nếu không thấy sẽ tạo mới ở cùng cấp script.
var DATA_FOLDER = (function(){
    try {
        var scriptFile = ($.fileName) ? new File($.fileName) : null;
        var dir = scriptFile ? scriptFile.parent : null; // premierCore
        if (!dir) throw 'no script dir';
        var coreDir = dir.parent; // core
        var rootDir = coreDir.parent; // project root
        var baseData = new Folder(rootDir.fsName + '/data');
        if (!baseData.exists) { try { baseData.create(); } catch(e1) { $.writeln('[DATA_FOLDER] Cannot create base data folder: ' + e1); } }
        var projectName = null;
        try { if (typeof PROJECT_NAME !== 'undefined' && PROJECT_NAME) projectName = ''+PROJECT_NAME; } catch(_ign){}
        if (!projectName) {
            try {
                var marker = new File(baseData.fsName + '/_current_project.txt');
                if (marker.exists && marker.open('r')) { projectName = marker.read().replace(/\r/g,'').replace(/\n/g,'').trim(); marker.close(); }
            } catch(_e2){}
        }
        var finalDir = baseData;
        if (projectName) {
            projectName = projectName.replace(/[^A-Za-z0-9_\-]/g,'_');
            var sub = new Folder(baseData.fsName + '/' + projectName);
            if (!sub.exists) { try { sub.create(); } catch(e3){ $.writeln('[DATA_FOLDER] Cannot create project subfolder: ' + e3); } }
            if (sub.exists) finalDir = sub;
            $.writeln('[DATA_FOLDER] Using project subfolder: ' + finalDir.fsName);
        } else {
            $.writeln('[DATA_FOLDER] Using base data folder (no project marker): ' + finalDir.fsName);
        }
        return finalDir.fsName.replace(/\\/g,'/');
    } catch(e){
        $.writeln('[DATA_FOLDER] Resolution error: ' + e);
        var fallback2 = new Folder(Folder.current.fsName + '/data');
        if (!fallback2.exists) fallback2.create();
        return fallback2.fsName.replace(/\\/g,'/');
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
    var randomDuration = getRandomDuration(3, 4); // khoảng trừ ngẫu nhiên (giây)
    var finalDuration;
    if (inputDuration <= 2 * randomDuration) finalDuration = inputDuration; // đoạn quá ngắn, lấy hết
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
    var available = srcPlayable - finalDuration;
    if (available < 0) available = 0; // nếu finalDuration > playable => sẽ bị cắt tại biên
    var randomStartOffsetSec = available > 0 ? Math.random() * available : 0;
    var newInSec = srcInSec + randomStartOffsetSec;
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
    $.writeln('[cutAndPushClipToTimeline] Created subclip: ' + newClip.name + ' from ' + newInSec.toFixed(3) + 's to ' + newOutSec.toFixed(3) + 's (duration: ' + finalDuration.toFixed(3) + 's)');

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
        tlFilePath = joinPath(DATA_FOLDER, 'timeline_merged.txt');
        $.writeln('[cutAndPushAllTimeline] Default primary path: ' + tlFilePath);
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
    // Chọn parser dựa vào phần mở rộng nếu người dùng truyền đích danh
    if (tlFilePath.match(/\.csv$/i)) {
        tlEntries = readTimelineCSVFile(tlFilePath);
    } else {
        return notify('Chỉ hỗ trợ file CSV hiện tại: ' + tlFilePath), -1;
    }
    if (!tlEntries.length) { notify('Không có entry hợp lệ trong file: ' + tlFilePath); return -1; }

    $.writeln('[cutAndPushAllTimeline] Read ' + tlEntries.length + ' entries from timeline file.');
    var processedCount = 0;
    var sizeBin = {}; // cache bin sizes

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
        //chọn lần lượt các video trong bin
        var idxInBin = 0;
        while (true){
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
            idxInBin = (idxInBin + 1) % binSize; // chuyển sang video tiếp theo trong bin
        }
        processedCount++;
    }
    notify('Hoàn thành chèn ' + processedCount + ' mục vào timeline từ file: ' + tlFilePath);
    return processedCount;
}

//test

var csvDef = joinPath(DATA_FOLDER, 'timeline_export_merged.csv'); // sẽ lấy trong subfolder nếu PROJECT_NAME / marker tồn tại
cutAndPushAllTimeline(csvDef);