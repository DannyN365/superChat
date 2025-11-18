import streamlit as st
import toml
import os
import google.generativeai as genai
import json


def speak_text(text: str):
    """Use the browser's built-in speech synthesis to read the text aloud."""
    if not text:
        return

    # Safely escape text for JS
    escaped = json.dumps(text)

    st.markdown(
        f"""
        <script>
        const msg = new SpeechSynthesisUtterance({escaped});
        msg.rate = 1;
        msg.pitch = 1;
        msg.volume = 1;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(msg);
        </script>
        """,
        unsafe_allow_html=True
    )

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

# Create model & chat only once
@st.cache_resource(show_spinner=False)
def get_chat():
    model = genai.GenerativeModel("gemini-2.5-flash")
    chat = model.start_chat(history=[
        {"role": "user", "parts": [SYSTEM_PROMPT]},
        {"role": "model", "parts": ["Okay, I'm ready to complain."]},
    ])
    return chat

chat = get_chat()

def chat_with_gemini_stream(user_input: str):
    """
    Stream response from Gemini and yield partial text
    so we can update the UI as tokens arrive.
    """
    try:
        response = chat.send_message(user_input, stream=True)
        full_text = ""
        for chunk in response:
            if chunk.text:
                full_text += chunk.text
                # Yield the accumulated text so far
                yield full_text
    except Exception as e:
        yield f"An error occurred: {e}"

st.title("The honest AI Assistant")

# ---------- SESSION STATE DEFAULTS ----------
if "query" not in st.session_state:
    st.session_state.query = ""
if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "submitted_flag" not in st.session_state:
    st.session_state.submitted_flag = False

# ---------- SUBMIT CALLBACK ----------
def handle_submit():
    """Runs when the form is submitted."""
    text = st.session_state.query.strip()
    if not text:
        return
    # Save query for this round
    st.session_state.last_query = text
    # Clear the text area for the next input
    st.session_state.query = ""
    # Mark that we submitted so main code can call the model
    st.session_state.submitted_flag = True

# ---------- FORM ----------
with st.form("chat_form"):
    st.text_area("What do you want?", key="query")
    st.form_submit_button("Send, if you must", on_click=handle_submit)

# ---------- CTRL+ENTER HANDLER (FRONTEND JS) ----------
st.markdown(
    """
    <script>
    // This runs inside Streamlit's iframe
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

# ---------- CALL MODEL (STREAMING) & DISPLAY ANSWER ----------
if st.session_state.submitted_flag:
    # Reset the flag so we don't resend on rerun
    st.session_state.submitted_flag = False

    # Show user's message
    if st.session_state.last_query:
        st.markdown(f"**You:** {st.session_state.last_query}")

    # Placeholder for streaming answer
    answer_placeholder = st.empty()

    full_answer = ""
    for partial in chat_with_gemini_stream(st.session_state.last_query):
        full_answer = partial
        # Update the placeholder as we receive more text
        answer_placeholder.write(full_answer)
        speak_text(full_answer)
    # Save final answer in session_state (e.g. if you want history later)
    st.session_state.last_answer = full_answer



# Show last answer after reruns too
if st.session_state.last_answer and not st.session_state.submitted_flag:
    # This will show the last full answer if there is one
    # (the placeholder will already contain it from the streaming step)
    pass
