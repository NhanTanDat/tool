import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load key từ file .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ LỖI: Không tìm thấy GEMINI_API_KEY trong file .env")
else:
    genai.configure(api_key=api_key)
    print(f"✅ Đang kiểm tra các model khả dụng cho Key: {api_key[:5]}...")
    print("-" * 30)
    try:
        found_any = False
        for m in genai.list_models():
            # Chỉ lấy các model hỗ trợ tạo nội dung (generateContent)
            if 'generateContent' in m.supported_generation_methods:
                print(f"👉 {m.name}") # Ví dụ: models/gemini-1.5-flash
                found_any = True
        
        if not found_any:
            print("⚠️ Không tìm thấy model nào. Hãy kiểm tra lại API Key hoặc Billing.")
            
    except Exception as e:
        print(f"❌ Lỗi kết nối đến Google: {e}")