import json
import streamlit as st
from google import genai
from gtts import gTTS
import io
import urllib.parse

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

# Khởi tạo trạng thái game và kho lưu trữ đệm (Cache) câu hỏi trong session
if "question_cache" not in st.session_state:
    st.session_state.question_cache = {}
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
st.markdown("Học kiến thức thông minh qua câu hỏi do AI tự động biên soạn kèm âm thanh, hình ảnh và giải thích chi tiết!")

# Kiểm tra API Key
if not api_key:
    st.warning("⚠️ Chưa tìm thấy `GEMINI_API_KEY` trong Streamlit Secrets. Vui lòng cấu hình trong phần Advanced settings!")
    st.stop()

# Nhập chủ đề học tập
topic = st.text_input("Nhập chủ đề bạn muốn học:", placeholder="Ví dụ: Quốc kỳ các nước, Lịch sử Việt Nam, Tiếng Anh cơ bản...")

# Tùy chọn cấp độ khó dễ và số lượng câu hỏi
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
    cache_key = f"{topic.strip().lower()}_{difficulty}_{num_q}"
    
    if cache_key in st.session_state.question_cache:
        st.session_state.questions = st.session_state.question_cache[cache_key]
        st.session_state.current_q = 0
        st.session_state.score = 0
        st.session_state.game_started = True
        st.session_state.answered = False
        st.session_state.selected_choice = None
        st.session_state.is_correct = None
        st.success("⚡ Tải nhanh bộ câu hỏi đã lưu từ bộ nhớ đệm (Không tốn lượt API)!")
        st.rerun()
    else:
        with st.spinner(f"AI đang soạn bộ {num_q} câu hỏi mức độ '{difficulty}' kèm giải thích chi tiết..."):
            try:
                prompt = f"""
                Tạo {num_q} câu hỏi trắc nghiệm về chủ đề: '{topic}'.
                Cấp độ khó của câu hỏi: {difficulty}.
                Đầu ra phải là một mảng JSON thuần túy (không chứa markdown nào khác ngoài JSON, không bọc trong ```json), mỗi phần tử có cấu trúc:
                {{
                  "question": "Nội dung câu hỏi?",
                  "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                  "answer": "Đáp án chính xác hoàn toàn giống hệt một trong các options trên",
                  "explanation": "Giải thích chi tiết vì sao đáp án này lại đúng và ý nghĩa kiến thức liên quan.",
                  "keyword": "Nếu câu hỏi này thực sự cần hình ảnh trực quan để minh họa (như quốc kỳ, danh lam, con vật, hiện tượng), hãy điền từ khóa tiếng Anh ngắn gọn. Nếu không cần ảnh, để trống \"\"."
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
                    st.session_state.question_cache[cache_key] = questions
                    st.session_state.questions = questions
                    st.session_state.current_q = 0
                    st.session_state.score = 0
                    st.session_state.game_started = True
                    st.session_state.answered = False
                    st.session_state.selected_choice = None
                    st.session_state.is_correct = None
                    st.rerun()
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    st.error("⚠️ Bạn đang gọi quá nhanh hoặc hết hạn mức. Hãy thử chọn lại chủ đề đã từng chơi để lấy từ bộ nhớ đệm nhé!")
                else:
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
        explanation = current_data.get("explanation", "Không có phần giải thích cho câu hỏi này.")
        keyword = current_data.get("keyword", "").strip()
        
        st.markdown(f"### {question_text}")
        
        # Hiển thị hình ảnh minh họa nếu có
        if keyword:
            formatted_kw = keyword.replace(" ", ",")
            img_source = f"[https://source.unsplash.com/featured/800x400/](https://source.unsplash.com/featured/800x400/)?{formatted_kw}"
            try:
                st.image(img_source, use_column_width=True, caption=f"🖼️ Hình ảnh minh họa cho: {keyword}")
            except Exception:
                pass
        
        full_doc_text = f"Câu hỏi {idx + 1}: {question_text}. Các đáp án là: A. {options[0]}, B. {options[1]}, C. {options[2]}, D. {options[3]}"
        if st.button("🔊 Nghe đọc câu hỏi & đáp án"):
            speak_text(full_doc_text)
            
        st.write("")
        st.markdown("**Chọn đáp án của bạn (Click trực tiếp vào đáp án):**")
        
        for opt in options:
            if st.button(opt, key=f"btn_{idx}_{opt}", disabled=st.session_state.answered, use_container_width=True):
                st.session_state.answered = True
                st.session_state.selected_choice = opt
                
                if opt == current_data["answer"]:
                    st.session_state.score += 1
                    st.session_state.is_correct = True
                else:
                    st.session_state.is_correct = False
                st.rerun()
        
        # Hiển thị kết quả đúng/sai kèm giải thích chi tiết và nút tìm kiếm Google
        if st.session_state.answered:
            st.write("")
            if st.session_state.is_correct:
                st.success(f"🎉 Chính xác tuyệt vời! Bạn đã chọn đúng: **{st.session_state.selected_choice}**")
                st.markdown('<audio autoplay><source src="[https://www.myinstants.com/media/sounds/success-1-6289.mp3](https://www.myinstants.com/media/sounds/success-1-6289.mp3)" type="audio/mp3"></audio>', unsafe_allow_html=True)
            else:
                st.error(f"❌ Chưa chính xác! Bạn chọn `{st.session_state.selected_choice}`, nhưng đáp án đúng là: **{current_data['answer']}**")
                st.markdown('<audio autoplay><source src="[https://www.myinstants.com/media/sounds/error-8-206492.mp3](https://www.myinstants.com/media/sounds/error-8-206492.mp3)" type="audio/mp3"></audio>', unsafe_allow_html=True)
            
            # Hiển thị phần giải thích chi tiết
            st.info(f"💡 **Giải thích chi tiết:**\n\n{explanation}")
            
            # Nút tự động mở Google Search tìm kiếm thêm thông tin về câu hỏi này
            search_query = urllib.parse.quote(f"{topic} {question_text}")
            google_search_url = f"[https://www.google.com/search?q=](https://www.google.com/search?q=){search_query}"
            st.link_button("🌐 Tìm hiểu thêm trên Google", google_search_url, use_container_width=True)
            
            st.write("")
            if idx < len(q_list) - 1:
                if st.button("➡️ Chuyển sang câu hỏi tiếp theo", type="primary", use_container_width=True):
                    st.session_state.current_q += 1
                    st.session_state.answered = False
                    st.session_state.selected_choice = None
                    st.session_state.is_correct = None
                    st.rerun()
            else:
                if st.button("🏆 Xem kết quả chung cuộc", type="primary", use_container_width=True):
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
            st.session_state.is_correct = None
            st.rerun()

# Nhạc nền nhẹ nhàng chạy ngầm
st.markdown("""
    <audio autoplay loop style="display:none;">
        <source src="[https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3](https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3)" type="audio/mp3">
    </audio>
""", unsafe_allow_html=True)
