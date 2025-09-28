

def merge_csv_with_txt(csv_in, txt_in, csv_out=None, encoding="utf-8"):
    import csv
    """
    Ghép text từ file txt vào cột 'textContent' của file csv.
    
    Args:
        csv_in (str): đường dẫn file CSV input
        txt_in (str): đường dẫn file TXT input
        csv_out (str|None): đường dẫn file CSV output (nếu None thì tạo cùng tên với _merged.csv)
        encoding (str): encoding file (default utf-8)
    
    Returns:
        str: đường dẫn file CSV đã được merge
    """
    if csv_out is None:
        if csv_in.lower().endswith(".csv"):
            csv_out = csv_in[:-4] + "_merged.csv"
        else:
            csv_out = csv_in + "_merged.csv"

    # đọc text lines (lazy)
    with open(txt_in, "r", encoding=encoding) as f:
        texts = (line.strip() for line in f)

        # đọc csv & ghi csv mới
        with open(csv_in, "r", encoding=encoding) as fin, \
             open(csv_out, "w", newline="", encoding=encoding) as fout:
            
            reader = csv.DictReader(fin)
            fieldnames = reader.fieldnames
            if "textContent" not in fieldnames:
                fieldnames.append("textContent")
            
            writer = csv.DictWriter(fout, fieldnames=fieldnames)
            writer.writeheader()
            
            for row, text in zip(reader, texts):
                row["textContent"] = text
                writer.writerow(row)

            # nếu còn dòng CSV mà hết text -> để trống
            for row in reader:
                row["textContent"] = ""
                writer.writerow(row)

    return csv_out


def merge_csv_with_txt_to_plain(txt_out, csv_in, txt_in=None, encoding="utf-8", include_header=False, joiner=" | "):
    """
    Tạo 1 file TXT thuần từ CSV (timeline) + optional file TXT chứa text content thô.
    - Nếu txt_in được cung cấp: ghép từng dòng text tương ứng vào cột textContent (không sửa file CSV gốc) trước khi xuất.
    - Mỗi dòng trong txt_out sẽ có dạng: indexInTrack | startSeconds-endSeconds | name | textContent
      (joiner có thể tùy chỉnh; mặc định dùng ' | ').

    Args:
        txt_out (str): đường dẫn file TXT output.
        csv_in (str): đường dẫn CSV nguồn (phải có cột: indexInTrack,name,startSeconds,endSeconds,durationSeconds,...)
        txt_in (str|None): file txt chứa text dòng theo dòng để override/điền vào textContent. Nếu None dùng giá trị trong CSV (nếu có).
        encoding (str): encoding đọc/ghi.
        include_header (bool): nếu True, dòng đầu file txt sẽ là header mô tả.
        joiner (str): chuỗi nối giữa các phần.

    Returns:
        str: đường dẫn file TXT xuất.
    """
    import csv, io
    # Đọc csv trước
    rows = []
    with open(csv_in, 'r', encoding=encoding) as fin:
        reader = csv.DictReader(fin)
        for r in reader:
            rows.append(r)
    # Nếu có txt_in: đọc các dòng text để map vào rows theo thứ tự
    override_texts = []
    if txt_in and os.path.isfile(txt_in):
        with open(txt_in, 'r', encoding=encoding) as ftxt:
            override_texts = [ln.rstrip('\n') for ln in ftxt]
    # Ghi file txt_out
    with open(txt_out, 'w', encoding=encoding) as fout:
        if include_header:
            fout.write('# index | start-end(seconds) | name | textContent\n')
        for i, r in enumerate(rows):
            var_text = ''
            if override_texts:
                if i < len(override_texts):
                    var_text = override_texts[i]
            else:
                var_text = r.get('textContent','') or ''
            seg = f"{r.get('startSeconds','')} - {r.get('endSeconds','')}"
            line = joiner.join([
                str(r.get('indexInTrack','')),
                seg,
                r.get('name',''),
                var_text
            ])
            fout.write(line + '\n')
    return txt_out


if __name__ == "__main__":
    import os
    THIS_DIR = os.path.abspath(os.path.dirname(__file__))
    ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
    DATA_DIR = os.path.join(ROOT_DIR, 'data')
    if not os.path.isdir(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception:
            pass
    csv_in = os.path.join(DATA_DIR, 'timeline_export.csv')  # điều chỉnh nếu cần
    txt_in = os.path.join(DATA_DIR, 'list_name.txt')
    csv_out = None
    out_path = merge_csv_with_txt(csv_in, txt_in, csv_out)
    print(f"Merged CSV saved to: {out_path}")
    # Xuất thêm bản TXT thuần
    plain_txt = os.path.join(DATA_DIR, 'timeline_merged.txt')
    txt_export = merge_csv_with_txt_to_plain(plain_txt, csv_in=csv_in, txt_in=txt_in, include_header=True)
    print(f"Plain text merged saved to: {txt_export}")