import comtypes.client

# Đường dẫn tới file JSX (sửa lại theo nơi bạn lưu)
jsx_path = "export_text.jsx"

# Kết nối tới Premiere qua ExtendScript engine
premiere = comtypes.client.CreateObject("ExtendScript.ScriptingHost")

# Đọc nội dung script JSX
with open(jsx_path, "r", encoding="utf-8") as f:
    jsx_code = f.read()

# Gửi JSX vào Premiere và lấy kết quả trả về
result = premiere.EvalScript(jsx_code)
print("Premiere trả về:", result)
