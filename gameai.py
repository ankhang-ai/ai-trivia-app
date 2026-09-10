import json
import streamlit as st
from google import genai

# Cấu hình trang Streamlit
st.set_page_config(page_title="AI Trivia Learning", page_icon="🧠")

# Lấy API Key an toàn: Tự động đọc từ đám mây hoặc cho phép nhập
api_key = None
try:
  if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
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
if "selected_option" not in st.session_state:
  st.session_state.selected_option = None


def fetch_questions_from_ai(topic, key):
  try:
    client = genai.Client(api_key=key)
    prompt = (
        "Hãy tạo 5 câu hỏi trắc nghiệm về chủ đề: "
        + topic
        + ". "
        "Yêu cầu trả về định dạng JSON thuần túy (không kèm markdown như ```json), là một mảng gồm các đối tượng với cấu trúc: "
        '[{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..."}]'
        " Trong đó correct_index là số từ 0 đến 3 ứng với đáp án đúng."
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash", contents=prompt
    )

    raw_text = response.text.strip()
    if raw_text.startswith("```"):
      raw_text = raw_text.split("```")[1]
      if raw_text.startswith("json"):
        raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    return json.loads(raw_text)
  except Exception as e:
    st.error(f"Lỗi: {e}")
    return []


st.title("🧠 AI Trivia Learning App")
st.write("Học kiến thức thông minh qua câu hỏi do AI tự động biên soạn!")

# Nếu chưa có khóa ngầm trên mây thì hiện ô cho phép nhập
if not api_key:
  api_key = st.text_input("Nhập Gemini API Key của bạn:", type="password")

if not api_key:
  st.warning("⚠️ Vui lòng cung cấp API Key để tiếp tục!")
else:
  if not st.session_state.game_started:
    topic_input = st.text_input(
        "Nhập chủ đề bạn muốn học:",
        placeholder=(
            "Ví dụ: Lịch sử Việt Nam, Kinh tế vĩ mô, Ngữ pháp tiếng Nhật..."
        ),
    )

    if st.button("🚀 Bắt đầu học"):
      if not topic_input:
        st.warning("Vui lòng nhập chủ đề!")
      else:
        with st.spinner("AI đang tìm kiếm và biên soạn câu hỏi..."):
          questions = fetch_questions_from_ai(topic_input, api_key)
          if questions:
            st.session_state.questions = questions
            st.session_state.current_q = 0
            st.session_state.score = 0
            st.session_state.game_started = True
            st.session_state.answered = False
            st.rerun()
  else:
    questions = st.session_state.questions
    current_idx = st.session_state.current_q

    if current_idx >= len(questions):
      st.success(
          f"🎉 Hoàn thành! Số điểm của bạn: {st.session_state.score} /"
          f" {len(questions)}"
      )
      if st.button("🔄 Chơi chủ đề mới"):
        st.session_state.game_started = False
        st.session_state.questions = []
        st.rerun()
    else:
      q_data = questions[current_idx]
      st.write(
          f"**Câu hỏi {current_idx + 1} / {len(questions)}** (Điểm hiện tại:"
          f" {st.session_state.score})"
      )
      st.subheader(q_data["question"])

      correct_idx = q_data["correct_index"]
      options = q_data["options"]

      for i, opt in enumerate(options):
        label = f"{['A', 'B', 'C', 'D'][i]}. {opt}"
        if not st.session_state.answered:
          if st.button(label, key=f"opt_{current_idx}_{i}"):
            st.session_state.answered = True
            st.session_state.selected_option = i
            if i == correct_idx:
              st.session_state.score += 1
            st.rerun()
        else:
          if i == correct_idx:
            st.success(f"✅ ĐÚNG: {label}")
          elif i == st.session_state.selected_option:
            st.error(f"❌ BẠN CHỌN: {label}")
          else:
            st.write(label)

      if st.session_state.answered:
        st.info(f"💡 **Giải thích & Mở rộng kiến thức:** {q_data['explanation']}")
        if st.button("➡️ Câu tiếp theo"):
          st.session_state.answered = False
          st.session_state.selected_option = None
          st.session_state.current_q += 1
          st.rerun()