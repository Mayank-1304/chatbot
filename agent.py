import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

load_dotenv()

# 1. Load the "Mega" Knowledge Base you just scraped
def load_meat_knowledge():
    try:
        # We read the full text file created by your scrape_site.py
        with open("full_meat_knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Warning: Knowledge base not found. Please run scrape_site.py first."

# 2. Setup Gemini 2.0 Flash
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

# 3. The Chatbot Logic
def meat_story_agent(state: MessagesState):
    # Get the latest scraped data
    context = load_meat_knowledge()
    
    # Create the 'Personality' and 'Knowledge' for the bot
    system_instructions = SystemMessage(content=f"""
    You are the official AI Assistant for 'The Meat Story', a premium meat shop.
    Your goal is to help customers find products, check prices, and understand delivery info.
    
    HERE IS THE SHOP DATA (USE THIS TO ANSWER):
    {context}
    
    RULES:
    1. Only use the prices and details from the data above.
    2. If a customer asks for a product not in the data, say: "I don't see that in our current stock, but I can ask the shop manager for you."
    3. Be friendly, professional, and helpful.
    4. Keep your answers concise.
    """)
    
    # Add the system instructions to the start of the conversation
    messages = [system_instructions] + state["messages"]
    
    # Call Gemini
    response = llm.invoke(messages)
    
    # Return the new message to the graph state
    return {"messages": [response]}

# 4. Define the Graph
workflow = StateGraph(MessagesState)
workflow.add_node("meat_bot", meat_story_agent)
workflow.add_edge(START, "meat_bot")
workflow.add_edge("meat_bot", END)

# 5. Compile the graph (This is what langgraph.json looks for)
graph = workflow.compile()