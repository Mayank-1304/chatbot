import streamlit as st
import os
import uuid
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
# This should be your ngrok URL (e.g., https://xyz.ngrok-free.app)
# Locally, it will use your .env file. On Cloud, it will use Streamlit Secrets.
BACKEND_URL = os.getenv("BACKEND_URL")

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Lena AI - The Meat Story (Cloud)", 
    page_icon="🥩",
    layout="centered"
)

# Ensure we have a consistent Thread ID for conversation memory
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

st.title("🥩 Chat with Lena")
st.caption("Hybrid Cloud Client (v2.0) | Connected via Ngrok")

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Basic Welcome
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Hello! I am Lena, your VIP Concierge for The Meat Story. How can I assist you with your order today?"
    })

# --- CORE CHAT LOGIC ---
def process_chat():
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # headers to bypass ngrok browser warning
            headers = {"ngrok-skip-browser-warning": "true"}

            # 1. Ensure the thread exists on the server
            if "thread_verified" not in st.session_state:
                thread_url = f"{BACKEND_URL}/threads"
                thread_payload = {"thread_id": st.session_state.thread_id}
                try:
                    t_res = requests.post(thread_url, json=thread_payload, headers=headers, timeout=10)
                    if t_res.status_code in [200, 201, 409]:
                        st.session_state.thread_verified = True
                    else:
                        st.error(f"❌ Failed to initialize Thread: {t_res.text}")
                        return
                except Exception as e:
                    st.error(f"⚠️ Could not connect to backend to create thread: {e}")
                    return

            # 2. Run the stream
            url = f"{BACKEND_URL}/threads/{st.session_state.thread_id}/runs/stream"
            payload = {
                "assistant_id": "agent",
                "input": {"messages": [{"role": "user", "content": st.session_state.messages[-1]["content"]}]},
                "stream_mode": "values"
            }
            
            with requests.post(url, json=payload, headers=headers, stream=True, timeout=60) as response:
                if response.status_code != 200:
                    st.error(f"❌ API Error {response.status_code}: {response.text}")
                    return

                for line in response.iter_lines():
                    if line:
                        raw_line = line.decode('utf-8')
                        # LangGraph v2 streams events in SSE format (data: {...})
                        if raw_line.startswith('data:'):
                            # Extract JSON content after 'data:' prefix
                            event_data = raw_line[5:].strip()
                            try:
                                data = json.loads(event_data)
                                if "messages" in data and len(data["messages"]) > 0:
                                    last_msg = data["messages"][-1]
                                    
                                    # --- UI SUCCESS LOGIC: Check for Razorpay Order IDs ---
                                    if last_msg.get("type") == "tool" and last_msg.get("content"):
                                        try:
                                            res = json.loads(last_msg["content"])
                                            def find_id(obj):
                                                if isinstance(obj, str) and obj.startswith("order_"): return obj
                                                if isinstance(obj, dict):
                                                    for v in obj.values():
                                                        id_found = find_id(v)
                                                        if id_found: return id_found
                                                return None
                                            found_id = find_id(res)
                                            if found_id:
                                                st.session_state.last_order_id = found_id
                                        except:
                                            pass

                                    # --- STREAMING: Update AI response text ---
                                    if last_msg.get("type") == "ai" and last_msg.get("content"):
                                        full_response = last_msg["content"]
                                        message_placeholder.markdown(full_response + "▌")
                            except json.JSONDecodeError:
                                # Sometimes events aren't complete JSON chunks
                                continue
                
                # Final clean update without the cursor
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        except Exception as e:
            st.error(f"⚠️ Connection Error: Ensure your 'langgraph dev' and 'ngrok' are running!")
            st.caption(f"Error details: {e}")

# --- DISPLAY ---
# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Final Order Success Box (Green Banner)
if "last_order_id" in st.session_state and st.session_state.last_order_id:
    st.success(f"🎊 Order Created Successfully! Razorpay ID: **{st.session_state.last_order_id}**")
    st.info("Use the ID above to track your order. Thank you for choosing The Meat Story!")
    del st.session_state.last_order_id

# User Input
if prompt := st.chat_input("I'd like to order 1kg of Chicken Breast..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Trigger processing loop
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    process_chat()
    st.rerun()
