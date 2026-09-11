import json
import streamlit as st
from google import genai
from gtts import gTTS
import io
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="AI Trivia Learning App", page_icon="🧠", layout="centered")

api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

client = None
if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        st.error("Loi khoi tao Gemini: " + str(e))

def get_gcp_credentials():
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"].strip()
        if "\\n" in pk and "\n" not in pk:
            pk = pk.replace("\\n", "\n")
        creds_dict["private_key"] = pk
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
        st.error("Loi doc Google Sheets: " + str(e))
        return []

def append_to_google_sheet(new_rows):
    try:
        creds = get_gcp_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open("AI_Trivia_Database")
        worksheet = sh.worksheet("Questions")
        for row in new_rows:
            worksheet.append_row(row)
        st.toast("Da dong bo du lieu vao Google Sheets!", icon="📊")
    except Exception as e:
        st.error("Loi ghi Google Sheets: " + str(e))

def speak_text(text):
    try:
        tts = gTTS(text=text, lang="vi")
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
    except Exception as e:
        pass

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

st.title("🧠 AI Trivia Learning App")
st.markdown("Học thông minh qua câu hỏi AI, đồng bộ với Google Sheets!")

if not api_key:
    st.warning("Chua tim thay GEMINI_API_KEY trong Streamlit Secrets!")
    st.stop()

topic = st.text_input("Nhap chu de ban muon hoc:", placeholder="Vi du: Lich su Viet Nam, Tieng Anh...")

col_a, col_b = st.columns(2)
with col_a:
    difficulty = st.selectbox(
        "Chon cap do kho:",
        ["De (Co ban)", "Trung binh (Hieu biet chung)", "Kho (Nang cao, chuyen sau)"]
    )
with col_b:
    num_q = st.number_input("So luong cau hoi:", min_value=1, value=5, step=1)

start_btn = st.button("Bat dau hoc", type="primary")

if start_btn and topic:
    target_topic = topic.strip().lower()
    
    with st.spinner("Dang kiem tra kho du lieu Google Sheets..."):
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
            st.success("Da tai nhanh bo cau hoi tu Google Sheets!")
            st.rerun()

    with st.spinner("AI dang soan bo cau hoi moi..."):
        try:
            prompt = (
                f"Tao {num_q} cau hoi trac nghiem ve chu de: '{topic}'. "
                f"Cap do: {difficulty}. "
                "Chi tra ve mang JSON thuan tuy (khong markdown, khong boc trong ```json), dung cau truc: "
                "["
                "{"
                '"question": "Cau hoi?", '
                '"options": ["A", "B", "C", "D"], '
                '"answer": "Dap an chinh xac giong het 1 option", '
                '"explanation": "Giai thich chi tiet", '
                '"keyword": "Tu khoa tieng Anh"'
                "}"
                "]"
            )
            response = client.models.generate_content(
                model="gemini-3.6-flash",
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
                st.success("Da tao va luu bo cau hoi vao Google Sheets!")
                st.rerun()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                st.warning("Da het han muc API. Vui long thu lai sau!")
            else:
