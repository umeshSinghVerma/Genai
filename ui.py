import streamlit as st
import requests

# Set page config for a wider layout
st.set_page_config(page_title="AI Knowledge Base Chatbot 🤖", layout="wide")

# Connect to your new Flask/FastAPI server
SERVER_URL = "http://localhost:8000/agent"

# Session state to store messages
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("AI Knowledge Base Chatbot 🤖")

# Custom CSS for chatbot width
st.markdown(
    """
    <style>
        .css-1v3fvcr { 
            width: 80% !important;
            max-width: 1000px; 
            margin: 0 auto;
        }
        .stChatMessage {
            font-size: 18px;
        }
    </style>
    """, unsafe_allow_html=True
)

# Display previous messages
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    with st.chat_message(role):
        st.markdown(content, unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Ask your question..."):
    # Store user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Call your new server
    with st.spinner("Thinking..."):
        try:
            # Notice we wrap the prompt in a list here []
            response = requests.post(SERVER_URL, json={"query": [prompt]})
            print("response ",response)
            response.raise_for_status()
            bot_response = response.json()
        except Exception as e:
            bot_response = f"Error: {e}"

    # Store assistant message
    st.session_state.messages.append({"role": "assistant", "content": bot_response})

    # Refresh page to show messages immediately
    st.rerun()
