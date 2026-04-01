import streamlit as st
import json
from agent import graph, load_meat_knowledge

# Basic Page Config
st.set_page_config(page_title="The Meat Story Chatbot", page_icon="🥩")

st.title("The Meat Story Assistant")

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Sync catalog on start
    load_meat_knowledge()
    # Basic Welcome
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Hello! I am Butcher's Buddy from The Meat Story. How can I help you with your order today?"
    })

# --- CORE CHAT LOGIC ---
def process_chat():
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Convert to LangGraph format
        history = [(m["role"], m["content"]) for m in st.session_state.messages]
        
        # Stream from Agent
        for event in graph.stream({"messages": history}, stream_mode="values"):
            if event["messages"]:
                last_msg = event["messages"][-1]
                
                # Check for Razorpay ID in tool outputs for the success box
                if hasattr(last_msg, "type") and last_msg.type == "tool":
                    try:
                        res = json.loads(last_msg.content)
                        # Look for 'order_' prefix anywhere in response
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

                if hasattr(last_msg, "type") and last_msg.type == "ai" and last_msg.content:
                    full_response = last_msg.content
                    message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

# --- DISPLAY ---
# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Final Order Success Box
if "last_order_id" in st.session_state and st.session_state.last_order_id:
    st.success(f"Order Created! Razorpay ID: {st.session_state.last_order_id}")
    del st.session_state.last_order_id

# User Input
if prompt := st.chat_input("How can I help you?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Trigger processing
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    process_chat()
    st.rerun()
