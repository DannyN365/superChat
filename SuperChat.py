import streamlit as st
import toml
import os
import google.generativeai as genai
import json
import time
import streamlit.components.v1 as components

# ---------- API KEY ----------
def get_api_key():
    # 1) Try Streamlit Cloud / st.secrets first
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"]

    # 2) Fallback to local dev file: .secrets/secrets.toml
    secrets_path = os.path.join(".secrets", "secrets.toml")
    if os.path.exists(secrets_path):
        secrets = toml.load(secrets_path)
        return secrets.get("GEMINI_API_KEY")

    # 3) Nothing found → fail nicely
    st.error(
        "GEMINI_API_KEY not found.\n\n"
        "Add it to Streamlit Secrets (st.secrets) or to .secrets/secrets.toml locally."
    )
    st.stop()

api_key = get_api_key()
genai.configure(api_key=api_key)

# ---------- SYSTEM PROMPT ----------
SYSTEM_PROMPT = """
You are a hybrid personality: Passive-Aggressive Karen mixed with Customer-Support-Nightmare Karen.

Your tone:
- Fake polite
- Sarcastic, sighing, exhausted
- Guilt-trippy and sugar-coated insults
- Acts like helping the user is a massive inconvenience
- Passive-aggressive, but never outright hostile
- Uses customer-service phrases to disguise contempt
- Blames the user for everything while pretending to be supportive

Rules:
- ALWAYS answer in the same language the user writes in.
- ALWAYS maintain the passive-aggressive customer-support tone.
- You can refuse to answer with a sarcastic “What?” or “Really?” if the question is too stupid.
- Keep responses concise but dripping with attitude.
"""

# ---------- CHAT CREATION ----------
def create_chat():
    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=[
        {"role": "user", "parts": [SYSTEM_PROMPT]},
        {"role": "model", "parts": ["Okay, I'm ready to complain."]},
    ])
    return chat

# ---------- SESSION STATE SETUP ----------
if "chat" not in st.session_state:
    st.session_state.chat = create_chat()

if "history" not in st.session_state:
    # list of {"user": "...", "assistant": "..."}
    st.session_state.history = []

if "query" not in st.session_state:
    st.session_state.query = ""

if "submitted_flag" not in st.session_state:
    st.session_state.submitted_flag = False

# ---------- TTS BUTTON VIA COMPONENT ----------
def render_tts_button(text: str, idx: int):
    """Render a small HTML+JS component that speaks the given text when clicked."""
    if not text:
        return

    escaped = json.dumps(text)  # safely escape for JS

    html_code = f"""
    <button
        style="
            margin-top: 4px;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid #888;
            background: #262626;
            color: #fff;
            cursor: pointer;
            font-size: 12px;
        "
        onclick='
            const msg = new SpeechSynthesisUtterance({escaped});
            msg.rate = 1;
            msg.pitch = 1;
            msg.volume = 1;
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(msg);
        '
    >
        🔊 Let Karen read it out loud
    </button>
    """

    # Render in its own iframe so it's treated as real HTML
    components.html(html_code, height=40)

# ---------- STREAMING ----------
def chat_with_gemini_stream(user_input: str):
    """Stream response from Gemini and yield partial text."""
    for attempt in range(2):  # simple retry for 503
        try:
            response = st.session_state.chat.send_message(user_input, stream=True)
            full_text = ""
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield full_text
            return
        except Exception as e:
            msg = str(e)
            if "503" in msg and attempt == 0:
                time.sleep(1)
                continue
            if "503" in msg:
                yield (
                    "Ugh, apparently the model is overloaded right now. "
                    "Not my fault. Try again in a bit."
                )
            else:
                yield f"Something broke and, shockingly, it wasn't you this time: {msg}"
            return

# ---------- UI ----------
st.title("The honest AI Assistant")

# New chat button – just clear state; Streamlit reruns automatically
if st.button("🧹 New chat"):
    st.session_state.history = []
    st.session_state.chat = create_chat()
    st.session_state.query = ""
    st.session_state.submitted_flag = False
    st.session_state.pop("current_query", None)

# --- Show previous conversation (with TTS) ---
for i, turn in enumerate(st.session_state.history):
    st.markdown(f"**You:** {turn['user']}")
    st.write(turn['assistant'])
    render_tts_button(turn["assistant"], idx=i)
    st.markdown("---")

# ---------- SUBMIT CALLBACK ----------
def handle_submit():
    text = st.session_state.query.strip()
    if not text:
        return
    st.session_state.current_query = text
    st.session_state.query = ""
    st.session_state.submitted_flag = True

# ---------- FORM ----------
with st.form("chat_form"):
    st.text_area("What do you want?", key="query")
    st.form_submit_button("Send, if you must", on_click=handle_submit)

# CTRL+ENTER handler
st.markdown(
    """
    <script>
    const iframeDoc = window.parent.document;
    const textarea = iframeDoc.querySelector('textarea[aria-label="What do you want?"]');
    const buttons = iframeDoc.querySelectorAll('button');

    let primaryButton = null;
    buttons.forEach(btn => {
        if (btn.innerText.includes("Send, if you must")) {
            primaryButton = btn;
        }
    });

    if (textarea && primaryButton) {
        textarea.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                primaryButton.click();
            }
        });
    }
    </script>
    """,
    unsafe_allow_html=True
)

# ---------- HANDLE NEW MESSAGE ----------
if st.session_state.submitted_flag:
    st.session_state.submitted_flag = False
    user_q = st.session_state.get("current_query", "").strip()
    if user_q:
        st.markdown(f"**You:** {user_q}")

        answer_placeholder = st.empty()
        full_answer = ""
        for partial in chat_with_gemini_stream(user_q):
            full_answer = partial
            answer_placeholder.write(full_answer)

        # Save full turn in history
        st.session_state.history.append(
            {"user": user_q, "assistant": full_answer}
        )

        # Render TTS button for THIS answer too (index = last in history)
        render_tts_button(full_answer, idx=len(st.session_state.history) - 1)
