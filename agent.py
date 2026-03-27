import os
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

load_dotenv()

# 1. Load the Knowledge Base with "Safety Checks"
def load_meat_knowledge():
    try:
        if not os.path.exists("meat_catalog.json"):
            return "Warning: meat_catalog.json not found. Please run your scrapers."

        with open("meat_catalog.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
            # Handle both formats (if data is a list OR a dict with a 'products' key)
            if isinstance(data, dict):
                products = data.get("products", [])
                general_info = data.get("general_info", "No general info available.")
            else:
                products = data
                general_info = "General info not loaded."

            # Format product list safely
            product_list_str = "--- AVAILABLE PRODUCTS & PRICES ---\n"
            for item in products:
                # .get() prevents the 'KeyError' crash
                name = item.get("product", item.get("item", "Unknown Product"))
                
                # Check all possible keys where price/grams might be stored
                details = item.get("full_details", item.get("details", item.get("price", "Contact for price")))
                
                product_list_str += f"Product: {name} | Details: {details}\n"

            return f"{product_list_str}\n\n--- GENERAL SHOP INFO ---\n{general_info}"
            
    except Exception as e:
        return f"Error loading knowledge: {str(e)}"

# 2. Setup Gemini 2.0 Flash
# Ensure your GOOGLE_API_KEY is in your .env file
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

# 3. The Chatbot Node
def meat_story_agent(state: MessagesState):
    # Get the latest context from your JSON
    context = load_meat_knowledge()
    
    system_instructions = SystemMessage(content=f"""
    You are the official AI Assistant for 'The Meat Story', a premium meat shop.
    
    KNOWLEDGE BASE:
    {context}
    
    INSTRUCTIONS:
    1. Be the 'Meat Expert'. If a user asks for 'wings', look for 'Chicken Wings' in the data.
    2. Always quote the exact price and weight (e.g., 500g or 1kg) found in the data.
    3. If the user asks for delivery, refer to the 'GENERAL SHOP INFO' section.
    4. If the data says 'Buy Now' instead of a price, tell the user the price is visible upon checkout.
    5. Stay professional, friendly, and concise.
    """)
    
    # Combine system message with conversation history
    messages = [system_instructions] + state["messages"]
    
    # Generate response
    response = llm.invoke(messages)
    
    return {"messages": [response]}

# 4. Define the Graph Workflow
workflow = StateGraph(MessagesState)

# Add the chatbot node
workflow.add_node("meat_bot", meat_story_agent)

# Set the flow: Start -> Bot -> End
workflow.add_edge(START, "meat_bot")
workflow.add_edge("meat_bot", END)

# 5. Compile the graph
# This 'graph' variable is what LangGraph Studio / API looks for
graph = workflow.compile()