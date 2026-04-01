import streamlit as st
import requests
import json
import os
import uuid

# Configuration
# This should be your ngrok URL (e.g., https://xyz.ngrok-free.app)
BACKEND_URL = os.getenv("BACKEND_URL")

st.set_page_config(page_title="Lena AI - The Meat Story", page_icon="🥩")
st.title("🥩 Chat with Lena")

# Ensure we have a consistent Thread ID for conversation memory
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I am Lena, your VIP Concierge for The Meat Story. How can I assist you today?"}]

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("I want 500g of Mutton Heart..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # LangGraph API expects a thread-based stream
            url = f"{BACKEND_URL}/threads/{st.session_state.thread_id}/runs/stream"
            payload = {
                "input": {"messages": [{"role": "user", "content": prompt}]},
                "stream_mode": "values"
            }
            
            with requests.post(url, json=payload, stream=True) as response:
                for line in response.iter_lines():
                    if line:
                        # LangGraph streams events in SSE format
                        event_data = line.decode('utf-8').replace('data: ', '')
                        try:
                            data = json.loads(event_data)
                            if "messages" in data and len(data["messages"]) > 0:
                                last_msg = data["messages"][-1]
                                if last_msg.get("type") == "ai" and last_msg.get("content"):
                                    full_response = last_msg["content"]
                                    message_placeholder.markdown(full_response + "▌")
                        except:
                            continue
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        except Exception as e:
            st.error(f"⚠️ Connection Error: Ensure your local backend and ngrok are running!")
            st.caption(f"Error details: {e}")
