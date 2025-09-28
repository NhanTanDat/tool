/**
 * importFolderToBin(folderPath)
 *  - Nhận vào absolute folder path trên hệ thống.
 *  - Tạo (hoặc tái sử dụng) một Bin trong Project Panel có tên đúng bằng tên thư mục.
 *  - Import tất cả file trực tiếp bên trong thư mục (không duyệt đệ quy) vào bin đó.
 *  - Bỏ qua file đã tồn tại (trùng tên) trong bin để tránh import lặp.
 *  - Trả về số lượng file mới được import.
 *
 *  Yêu cầu chạy trong môi trường ExtendScript của Premiere Pro.
 *  Gọi ví dụ ( ExtendScript Toolkit / CEP panel ): importFolderToBin("C:/media/topicA");
 */

var ENABLE_ALERTS = false; // chuyển true nếu vẫn muốn popup
function notify(msg){
	$.writeln('[import_resources] ' + msg);
	if (ENABLE_ALERTS) { try { alert(msg); } catch(e) {} }
}

// ================== SILENT IMPORT UTILITIES ==================
// Mục tiêu: giảm tối đa popup lỗi khi import (file hỏng, codec không hỗ trợ...).
// LƯU Ý GIỚI HẠN: Một số popup nội bộ của Premiere (ví dụ Missing Codec) là dialog của host, ExtendScript
// không thể chặn 100%. Ta xử lý bằng cách:
//  1. Lọc trước các file với whitelist extension (tùy chọn)
//  2. Dùng importFiles với suppressUI = true
//  3. Nếu vẫn lỗi: fallback sang import từng file trong try/catch để bỏ qua file lỗi mà không dừng toàn bộ batch
//  4. (Tùy chọn nâng cao) Nếu có QE API: dùng qe.project.importFiles (đôi khi ít popup hơn).

var SILENT_IMPORT_OPTIONS = {
	enableExtensionFilter: false,        // bật nếu muốn lọc extension an toàn
	allowedExtensions: ['.mp4','.mov','.mxf','.wav','.mp3','.jpg','.png'],
	useQEFallback: true                  // thử dùng QE nếu batch import lỗi
};

function hasAllowedExtension(path){
	if (!SILENT_IMPORT_OPTIONS.enableExtensionFilter) return true;
	var lower = path.toLowerCase();
	for (var i=0;i<SILENT_IMPORT_OPTIONS.allowedExtensions.length;i++) {
		if (lower.indexOf(SILENT_IMPORT_OPTIONS.allowedExtensions[i]) === lower.length - SILENT_IMPORT_OPTIONS.allowedExtensions[i].length) {
			return true;
		}
	}
	return false;
}

function safeBatchImport(paths, targetBin) {
	if (!paths.length) return 0;
	var suppressUI = true;
	var importAsNumberedStills = false;
	try {
		app.project.importFiles(paths, suppressUI, targetBin, importAsNumberedStills);
		notify('Batch import OK (' + paths.length + ' files).');
		return paths.length;
	} catch(e) {
		notify('Batch import failed, fallback per-file. Error: ' + e);
	}
	var imported = 0;
	for (var i=0;i<paths.length;i++) {
		try {
			app.project.importFiles([paths[i]], suppressUI, targetBin, importAsNumberedStills);
			imported++;
		} catch(e2) {
			notify('Skip file (error): ' + paths[i] + ' -> ' + e2);
		}
	}
	return imported;
}

function qeImportFallback(paths) {
	if (!SILENT_IMPORT_OPTIONS.useQEFallback) return 0;
	try {
		if (typeof app.enableQE === 'function') { app.enableQE(); }
		if (typeof qe === 'undefined' || !qe || !qe.project) return 0;
		var count = 0;
		for (var i=0;i<paths.length;i++) {
			try { qe.project.importFiles(paths[i]); count++; } catch(e) { notify('QE skip: ' + paths[i] + ' -> ' + e); }
		}
		if (count) notify('QE fallback imported ' + count + ' file(s).');
		return count;
	} catch(ex) {
		notify('QE fallback error: ' + ex);
		return 0;
	}
}

function importFolderToBin(folderPath) {
	if (typeof app === 'undefined' || !app.project) {
		notify('Script phải chạy bên trong Adobe Premiere Pro.');
		return -1;
	}
	if (!folderPath) {
		notify('Thiếu folderPath');
		return -1;
	}

	var f = new Folder(folderPath);
	if (!f.exists) {
		notify('Thư mục không tồn tại: ' + folderPath);
		return -1;
	}

	var project = app.project;
	var rootItem = project.rootItem;

	function findOrCreateBin(parentItem, name) {
		for (var i = 0; i < parentItem.children.numItems; i++) {
			var child = parentItem.children[i];
			if (child && child.type === 2 && child.name === name) { // 2 = Bin
				return child;
			}
		}
		return parentItem.createBin(name);
	}

	function itemNameExists(binItem, name) {
		for (var i = 0; i < binItem.children.numItems; i++) {
			var child = binItem.children[i];
			if (child && child.name === name) {
				return true;
			}
		}
		return false;
	}

	var binName = f.name; // tên bin bằng tên thư mục
	var targetBin = findOrCreateBin(rootItem, binName);

	var fileEntries = f.getFiles();
	var pathsToImport = [];
	for (var i = 0; i < fileEntries.length; i++) {
		var entry = fileEntries[i];
		if (entry instanceof File) {
			// Bỏ qua file ẩn / rỗng
			if (!entry.exists) continue;
			// Nếu đã có item cùng tên trong bin thì bỏ qua
			if (itemNameExists(targetBin, entry.name)) {
				$.writeln('[importFolderToBin] Skip trùng: ' + entry.name);
				continue;
			}
			pathsToImport.push(entry.fsName);
		}
	}

	if (!pathsToImport.length) {
		$.writeln('[importFolderToBin] Không có file mới để import trong: ' + folderPath);
		return 0;
	}

	// Lọc extension nếu cấu hình
	var filtered = [];
	for (var fi=0; fi<pathsToImport.length; fi++) {
		if (hasAllowedExtension(pathsToImport[fi])) filtered.push(pathsToImport[fi]);
		else notify('Bỏ qua do extension không nằm trong whitelist: ' + pathsToImport[fi]);
	}
	if (!filtered.length) { notify('Không còn file hợp lệ sau khi lọc.'); return 0; }
	var importedCount = safeBatchImport(filtered, targetBin);
	if (importedCount === 0) {
		var qeCount = qeImportFallback(filtered);
		if (qeCount > 0) return qeCount;
	}
	return importedCount;
}

// Nếu muốn test nhanh khi chạy trực tiếp, bỏ comment 2 dòng dưới và chỉnh đường dẫn:
// (function(){ importFolderToBin("C:/temp/mediaTopic"); })();

/**
 * importMultipleFolders(parentFolderPath)
 *  - Nhận vào đường dẫn tuyệt đối tới THƯ MỤC CHA.
 *  - Duyệt tất cả các thư mục con trực tiếp (không đệ quy sâu hơn) bên trong.
 *  - Gọi importFolderToBin cho mỗi thư mục con tìm được.
 *  - Trả về tổng số file mới được import từ tất cả các thư mục con.
 */
function importMultipleFolders(parentFolderPath) {
	if (!parentFolderPath) {
		notify('Thiếu parentFolderPath');
		return -1;
	}
	var parent = new Folder(parentFolderPath);
	if (!parent.exists) {
		notify('Thư mục không tồn tại: ' + parentFolderPath);
		return -1;
	}

	var entries = parent.getFiles(); // lấy tất cả file + folder bên trong
	var totalImported = 0;
	var subfolderCount = 0;
	for (var i = 0; i < entries.length; i++) {
		var entry = entries[i];
		if (entry instanceof Folder) {
			subfolderCount++;
			$.writeln('[importMultipleFolders] Xử lý thư mục con: ' + entry.fsName);
			var count = importFolderToBin(entry.fsName);
			if (count > 0) {
				totalImported += count;
			}
		}
	}
	if (subfolderCount === 0) {
		$.writeln('[importMultipleFolders] Không tìm thấy thư mục con trong: ' + parentFolderPath);
	}
	$.writeln('[importMultipleFolders] Tổng số file mới import: ' + totalImported);
	return totalImported;
}

// Example usage (bỏ comment để test):
importMultipleFolders("C:/Users/phamp/OneDrive/Máy tính/test");