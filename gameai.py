import json
import streamlit as st
from google import genai
from gtts import gTTS
import io
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials

# Cấu hình trang Streamlit
st.set_page_config(page_title="AI Trivia Learning App", page_icon="🧠", layout="centered")

# Lấy API Key an toàn từ st.secrets
api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Khởi tạo client Gemini
client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Lỗi khởi tạo Gemini Client: {e}")

# Hàm kết nối Google Sheets tự động (Đã chuẩn hóa private_key chống lỗi PEM)
def get_gcp_credentials():
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

def get_google_sheet_data():
    try:
        creds = get_gcp_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open("AI_Trivia_Database")
        worksheet = sh.worksheet("Questions")
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Lỗi đọc Google Sheets: {e}")
        return []

def append_to_google_sheet(new_rows):
    try:
        creds = get_gcp_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open("AI_Trivia_Database")
        worksheet = sh.worksheet("Questions")
        for row in new_rows:
            worksheet.append_row(row)
        st.toast("✨ Đã đồng bộ dữ liệu vào Google Sheets thành công!", icon="📊")
    except Exception as e:
        st.error(f"Lỗi ghi Google Sheets: {e}")

# Hàm chuyển văn bản thành giọng nói tiếng Việt
def speak_text(text):
    try:
        tts = gTTS(text=text, lang="vi")
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
    except Exception as e:
        pass

# Khởi tạo trạng thái game
if "questions" not in st.session_state:
    st.session_state.questions = []
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "answered" not in st.session_state:
    st.session_state.answered = False
if "selected_choice" not in st.session_state:
    st.session_state.selected_choice = None
if "is_correct" not in st.session_state:
    st.session_state.is_correct = None

# Giao diện tiêu đề
st.title("🧠 AI Trivia Learning App by TDQ")
st.markdown("Học kiến thức thông minh qua câu hỏi do AI tự động biên soạn, đồng bộ vĩnh viễn với Google Sheets!")

if not api_key:
    st.warning("⚠️ Chưa tìm thấy cấu hình trong Streamlit Secrets!")
    st.stop()

topic = st.text_input("Nhập chủ đề bạn muốn học:", placeholder="Ví dụ: Quốc kỳ các nước, Lịch sử Việt Nam, Tiếng Anh cơ bản...")

col_a, col_b = st.columns(2)
with col_a:
    difficulty = st.selectbox(
        "Chọn cấp độ khó:",
        ["Dễ (Cơ bản, phù hợp cho trẻ em/mới học)", "Trung bình (Hiểu biết chung)", "Khó (Nâng cao, chuyên sâu, đánh đố)"]
    )
with col_b:
    num_q = st.number_input("Số lượng câu hỏi:", min_value=1, value=5, step=1)

start_btn = st.button("🚀 Bắt đầu học", type="primary")

if start_btn and topic:
    target_topic = topic.strip().lower()
    
    # BƯỚC 1: Lục kho cũ từ Google Sheets
    with st.spinner("Đang kiểm tra kho dữ liệu trên Google Sheets..."):
        all_rows = get_google_sheet_data()
        cached_questions = []
        for r in all_rows:
            if str(r.get("Topic", "")).strip().lower() == target_topic and str(r.get("Difficulty", "")) == difficulty:
                try:
                    options_list = json.loads(r.get("Options", "[]"))
                except:
                    options_list = [r.get("Options", "")]
                
                cached_questions.append({
                    "question": r.get("Question"),
                    "options": options_list,
                    "answer": r.get("Answer"),
                    "explanation": r.get("Explanation"),
                    "keyword": r.get("Keyword", "")
                })
        
        if len(cached_questions) >= num_q:
            st.session_state.questions = cached_questions[:num_q]
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.game_started = True
            st.session_state.answered = False
            st.session_state.selected_choice = None
            st.session_state.is_correct = None
            st.success("⚡ Đã tìm thấy và tải nhanh bộ câu hỏi từ kho Google Sheets cá nhân!")
            st.rerun()

    # BƯỚC 2: Nếu chưa có, gọi AI tạo mới (dùng gemini-2.0-flash chuẩn xác)
    with st.spinner(f"AI đang soạn bộ {num_q} câu hỏi mức độ '{difficulty}' và tự động lưu vào Google Sheets..."):
        try:
            prompt = f"""
            Tạo {num_q} câu hỏi trắc nghiệm về chủ đề: '{topic}'.
            Cấp độ khó của câu hỏi: {difficulty}.
            Đầu ra phải là một mảng JSON thuần túy (không chứa markdown nào khác ngoài JSON, không bọc trong ```json), mỗi phần tử có cấu trúc:
            {{
              "question": "Nội dung câu hỏi?",
              "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
              "answer": "Đáp án chính xác hoàn toàn giống hệt một trong các options trên",
              "explanation": "Giải thích chi tiết vì sao đáp án này lại đúng.",
              "keyword": "Từ khóa tiếng Anh ngắn gọn nếu cần ảnh minh họa, nếu không để trống \"\"."
            }}
            """
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            new_questions = json.loads(raw_text.strip())
            
            if new_questions:
                rows_to_save = []
                for q in new_questions:
                    rows_to_save.append([
                        topic.strip(),
                        difficulty,
                        q["question"],
                        json.dumps(q["options"], ensure_ascii=False),
                        q["answer"],
                        q.get("explanation", ""),
                        q.get("keyword", "")
                    ])
                append_to_google_sheet(rows_to_save)
                
                st.session_state.questions = new_questions
                st.session_state.current_q = 0
                st.session_state.score = 0
                st.session_state.game_started = True
                st.session_state.answered = False
                st.session_state.selected_choice = None
                st.session_state.is_correct = None
                st.success("✨ Đã tạo mới câu hỏi và tự động đồng bộ thành công vào Google Sheets!")
                st.rerun()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                st.error("⚠️ Hết hạn mức API. Hãy chọn các chủ đề bạn đã từng học để lấy trực tiếp từ Google Sheets nhé!")
            else:
                st.error(f"Có lỗi xảy ra: {e}")

# Tiến hành chơi game
if st.session_state.game_started and st.session_state.questions:
    q_list = st.session_state.questions
    idx = st.session_state.current_q
    
    if idx < len(q_list):
        current_data = q_list[idx]
        
        st.divider()
        st.subheader(f"📌 Câu hỏi {idx + 1} / {len(q_list)}")
        
        question_text = current_data["question"]
        options = current_data["options"]
        explanation = current_data.get("explanation", "Không có phần giải thích.")
        keyword = current_data.get("keyword", "").strip()
        
        st.markdown(f"### {question_text}")
        
        if keyword:
            formatted_kw = keyword.replace(" ", ",")
            img_source = f"[https://source.unsplash.com/featured/800x400/](https://source.unsplash.com/featured/800x400/)?{formatted_kw}"
            try:
                st.image(img_source, caption=f"🖼️ Hình ảnh
