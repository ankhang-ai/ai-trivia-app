import json
import streamlit as st
from google import genai
from gtts import gTTS
import io

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

# Giao diện tiêu đề
st.title("🧠 AI Trivia Learning App")
st.markdown("Học kiến thức thông minh qua câu hỏi do AI tự động biên soạn kèm âm thanh sinh động!")

# Kiểm tra API Key
if not api_key:
    st.warning("⚠️ Chưa tìm thấy `GEMINI_API_KEY` trong Streamlit Secrets. Vui lòng cấu hình trong phần Advanced settings!")
    st.stop()

# Nhập chủ đề học tập
topic = st.text_input("Nhập chủ đề bạn muốn học:", placeholder="Ví dụ: Lịch sử Việt Nam, Kinh tế vĩ mô, Ngữ pháp tiếng Nhật...")

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button("🚀 Bắt đầu học")

if start_btn and topic:
    with st.spinner("AI đang soạn bộ câu hỏi thú vị cho bạn..."):
        try:
            prompt = f"""
            Tạo 5 câu hỏi trắc nghiệm về chủ đề: '{topic}'.
            Đầu ra phải là một mảng JSON thuần túy (không chứa markdown nào khác ngoài JSON, không bọc trong ```json), mỗi phần tử có cấu trúc:
            {{
              "question": "Nội dung câu hỏi?",
              "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
              "answer": "Đáp án chính xác hoàn toàn giống hệt một trong các options trên"
            }}
            """
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            questions = json.loads(raw_text.strip())
            
            if questions:
                st.session_state.questions = questions
                st.session_state.current_q = 0
                st.session_state.score = 0
                st.session_state.game_started = True
                st.session_state.answered = False
                st.session_state.selected_choice = None
                st.rerun()
        except Exception as e:
            st.error(f"Có lỗi khi tạo câu hỏi từ AI: {e}")

# Tiến hành chơi game nếu đã có câu hỏi
if st.session_state.game_started and st.session_state.questions:
    q_list = st.session_state.questions
    idx = st.session_state.current_q
    
    if idx < len(q_list):
        current_data = q_list[idx]
        
        st.divider()
        st.subheader(f"📌 Câu hỏi {idx + 1} / {len(q_list)}")
        
        question_text = current_data["question"]
        options = current_data["options"]
        
        st.markdown(f"### {question_text}")
        
        full_doc_text = f"Câu hỏi {idx + 1}: {question_text}. Các đáp án là: A. {options[0]}, B. {options[1]}, C. {options[2]}, D. {options[3]}"
        if st.button("🔊 Nghe đọc câu hỏi & đáp án"):
            speak_text(full_doc_text)
            
        st.write("")
        
        selected = st.radio("Chọn đáp án của bạn:", options, key=f"q_{idx}", index=None if not st.session_state.answered else options.index(st.session_state.selected_choice) if st.session_state.selected_choice in options else 0)
        
        col_sub, col_next = st.columns([1, 1])
        
        with col_sub:
            if not st.session_state.answered:
                if st.button("✨ Xác nhận đáp án"):
                    if selected:
                        st.session_state.answered = True
                        st.session_state.selected_choice = selected
                        
                        if selected == current_data["answer"]:
                            st.session_state.score += 1
                            st.success("🎉 Chính xác tuyệt vời!")
                            # Phát âm thanh đúng bằng HTML audio
                            st.markdown('<audio autoplay><source src="[https://www.myinstants.com/media/sounds/success-1-6289.mp3](https://www.myinstants.com/media/sounds/success-1-6289.mp3)" type="audio/mp3"></audio>', unsafe_allow_html=True)
                        else:
                            st.error(f"❌ Chưa chính xác! Đáp án đúng là: **{current_data['answer']}**")
                            # Phát âm thanh sai bằng HTML audio
                            st.markdown('<audio autoplay><source src="[https://www.myinstants.com/media/sounds/error-8-206492.mp3](https://www.myinstants.com/media/sounds/error-8-206492.mp3)" type="audio/mp3"></audio>', unsafe_allow_html=True)
                        st.rerun()
                    else:
                        st.warning("Vui lòng chọn một đáp án trước khi xác nhận!")
        
        if st.session_state.answered:
            with col_next:
                if idx < len(q_list) - 1:
                    if st.button("➡️ Câu hỏi tiếp theo"):
                        st.session_state.current_q += 1
                        st.session_state.answered = False
                        st.session_state.selected_choice = None
                        st.rerun()
                else:
                    if st.button("🏆 Xem kết quả chung cuộc"):
                        st.session_state.current_q += 1
                        st.rerun()
    else:
        st.success("🎉 Chúc mừng bạn đã hoàn thành xong bộ câu hỏi!")
        st.balloons()
        st.metric(label="Tổng số điểm của bạn", value=f"{st.session_state.score} / {len(q_list)}")
        
        if st.button("🔄 Chơi lại chủ đề mới"):
            st.session_state.game_started = False
            st.session_state.questions = []
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.rerun()

# Nhạc nền nhẹ nhàng chạy ngầm
st.markdown("""
    <audio autoplay loop style="display:none;">
        <source src="[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3)" type="audio/mp3">
    </audio>
""", unsafe_allow_html=True)
