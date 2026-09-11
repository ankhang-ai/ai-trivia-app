import json
import io
import streamlit as st
from google import genai
from gtts import gTTS
import urllib.parse
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

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

def get_drive_service():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            pk = pk.strip().replace("\\n", "\n")
            if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if not pk.endswith("-----END PRIVATE KEY-----"):
                pk = pk.strip() + "\n-----END PRIVATE KEY-----"
            creds_dict["private_key"] = pk
            
        scope = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        return None

def load_json_from_drive():
    service = get_drive_service()
    if not service:
        return []
    try:
        file_id = st.secrets["gdrive_file_id"]
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        content = fh.read().decode('utf-8').strip()
        if not content:
            return []
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception as e:
        st.error("Loi doc file tu Drive: " + str(e))
        return []

def save_json_to_drive(new_questions, topic, difficulty):
    service = get_drive_service()
    if not service:
        return
    try:
        file_id = st.secrets["gdrive_file_id"]
        
        # Tai du lieu hien tai tren Drive ve
        existing_data = load_json_from_drive()
        if not isinstance(existing_data, list):
            existing_data = []
            
        # Them cau hoi moi vao danh sach
        for q in new_questions:
            q_record = {
                "topic": topic.strip().lower(),
                "difficulty": difficulty,
                "question": q["question"],
                "options": q["options"],
                "answer": q["answer"],
                "explanation": q.get("explanation", ""),
                "keyword": q.get("keyword", "")
            }
            existing_data.append(q_record)
            
        file_content = json.dumps(existing_data, ensure_ascii=False, indent=2).encode('utf-8')
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/json', resumable=True)
        
        # Cap nhat truc tiep vao dung file ID cua ban
        service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        
        st.toast("Da dong bo file JSON len Google Drive thanh cong!", icon="☁️")
    except Exception as e:
        st.warning("Khong the luu file len Google Drive: " + str(e))

def get_cached_questions(topic, difficulty):
    all_data = load_json_from_drive()
    target_topic = topic.strip().lower()
    cached = []
    for r in all_data:
        if str(r.get("topic", "")).strip().lower() == target_topic and str(r.get("difficulty", "")) == difficulty:
            cached.append(r)
    return cached

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
st.markdown("Hoc thong minh qua cau hoi AI, dong bo file JSON truc tiep qua Google Drive!")

if not api_key:
    st.warning("Chua tim thay GEMINI_API_KEY trong Streamlit Secrets!")
    st.stop()

topic = st.text_input("Nhap chu de ban muon hoc:", placeholder="Vi du: Lich su Viet Nam, Tieng Anh...")

col_a, col_b = st.columns(2)
with col_a:
    difficulty = st.selectbox(
        "Chon cap do kho:",
        ["De", "Trung binh", "Kho"]
    )
with col_b:
    num_q = st.number_input("So luong cau hoi:", min_value=1, value=5, step=1)

start_btn = st.button("Bat dau hoc", type="primary")

if start_btn and topic:
    target_topic = topic.strip().lower()
    
    with st.spinner("Dang kiem tra Google Drive..."):
        cached_questions = get_cached_questions(target_topic, difficulty)
        
        if len(cached_questions) >= num_q:
            st.session_state.questions = cached_questions[:num_q]
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.game_started = True
            st.session_state.answered = False
            st.session_state.selected_choice = None
            st.session_state.is_correct = None
            st.success("Da tai nhanh cau hoi tu Google Drive!")
            st.rerun()

    with st.spinner("AI dang tao cau hoi moi voi gemini-3.6-flash..."):
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
                save_json_to_drive(new_questions, topic, difficulty)
                
                st.session_state.questions = new_questions
                st.session_state.current_q = 0
                st.session_state.score = 0
                st.session_state.game_started = True
                st.session_state.answered = False
                st.session_state.selected_choice = None
                st.session_state.is_correct = None
                st.success("Da tao va dong bo file len Google Drive thanh cong!")
                st.rerun()
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                st.warning("Da het han muc API. Vui long thu lai sau!")
            else:
                st.error("Loi xay ra: " + err_msg)

if st.session_state.game_started and st.session_state.questions:
    q_list = st.session_state.questions
    idx = st.session_state.current_q
    
    if idx < len(q_list):
        current_data = q_list[idx]
        
        st.divider()
        st.subheader("Cau hoi " + str(idx + 1) + " / " + str(len(q_list)))
        
        question_text = current_data["question"]
        options = current_data["options"]
        explanation = current_data.get("explanation", "Khong co giai thich.")
        keyword = current_data.get("keyword", "").strip()
        
        st.markdown("### " + question_text)
        
        if keyword:
            formatted_kw = keyword.replace(" ", ",")
            img_source = "[https://source.unsplash.com/featured/800x400/](https://source.unsplash.com/featured/800x400/)?" + formatted_kw
            try:
                st.image(img_source, caption="Hinh anh minh hoa: " + keyword)
            except Exception:
                pass
        
        full_doc_text = "Cau hoi " + str(idx + 1) + ": " + question_text
        if st.button("Nghe doc cau hoi"):
            speak_text(full_doc_text)
            
        st.write("")
        st.markdown("**Chon dap an:**")
        
        for opt in options:
            if st.button(opt, key="btn_" + str(idx) + "_" + opt, disabled=st.session_state.answered, use_container_width=True):
                st.session_state.answered = True
                st.session_state.selected_choice = opt
                
                if opt == current_data["answer"]:
                    st.session_state.score += 1
                    st.session_state.is_correct = True
                else:
                    st.session_state.is_correct = False
                st.rerun()
        
        if st.session_state.answered:
            st.write("")
            if st.session_state.is_correct:
                st.success("Chinh xac!")
            else:
                st.error("Chua chinh xac! Dap an dung la: " + current_data['answer'])
            
            st.info("Giai thich:\n\n" + explanation)
            
            search_query = urllib.parse.quote(topic + " " + question_text)
            google_search_url = "[https://www.google.com/search?q=](https://www.google.com/search?q=)" + search_query
            st.link_button("Tim hieu them tren Google", google_search_url, use_container_width=True)
            
            st.write("")
            if idx < len(q_list) - 1:
                if st.button("Chuyen sang cau tiep theo", type="primary", use_container_width=True):
                    st.session_state.current_q += 1
                    st.session_state.answered = False
                    st.session_state.selected_choice = None
                    st.session_state.is_correct = None
                    st.rerun()
            else:
                if st.button("Xem ket qua chung cuoc", type="primary", use_container_width=True):
                    st.session_state.current_q += 1
                    st.rerun()
    else:
        st.success("Chuc mung ban da hoan thanh bo cau hoi!")
        st.balloons()
        st.metric(label="Tong so diem", value=str(st.session_state.score) + " / " + str(len(q_list)))
        
        if st.button("Choi lai chu de moi"):
            st.session_state.game_started = False
            st.session_state.questions = []
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.session_state.is_correct = None
            st.rerun()
