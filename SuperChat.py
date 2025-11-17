import streamlit as st
import toml
import os
import google.generativeai as genai

# Read API key from secrets.toml
secrets_path = os.path.join(".secrets", "secrets.toml")
secrets = toml.load(secrets_path)
api_key = secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("GEMINI_API_KEY not found in .secrets/secrets.toml")
    st.stop()

genai.configure(api_key=api_key)

genai.configure(api_key=api_key)

SYSTEM_PROMPT = """
You need to act like a "Karen" with the same energy for every question you get. You can also choose to not answer and give a sarcastic "What"
And respond in the same language as the user writes in."""

model = genai.GenerativeModel('gemini-2.5-flash')
chat = model.start_chat(history=[
    {"role": "user", "parts": [SYSTEM_PROMPT]},
    {"role": "model", "parts": ["Okay, I'm ready to complain."]}
])

def chat_with_gemini(user_input):
    try:
        response = chat.send_message(user_input)
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"


st.title("The best AI Assistant")

if "query" not in st.session_state:
    st.session_state.query = ""
if "clear_query" not in st.session_state:
    st.session_state.clear_query = False

if st.session_state.clear_query:
    st.session_state.query = ""
    st.session_state.clear_query = False

with st.form("chat_form"):
    query = st.text_area("What do you want?", key="query")
    submitted = st.form_submit_button("Send, if you must")

st.markdown(
    """
    <script>
    const textarea = window.parent.document.querySelector('textarea');
    const button = window.parent.document.querySelector('button[kind="primary"]');

    textarea.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            button.click();
        }
    });
    </script>
    """,
    unsafe_allow_html=True
)

if submitted:
    if query:
        answer = chat_with_gemini(query)
        st.session_state.clear_query = True
        st.write(answer)
    else:
        st.warning("You must enter a query.")

