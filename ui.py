import chainlit as cl
from agent import graph # Import your compiled LangGraph

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="What are the best cuts?",
            message="What are the best cuts of meat you have available right now?",
        ),
        cl.Starter(
            label="Check a Price",
            message="How much is the Chicken Breast?",
        ),
        cl.Starter(
            label="Delivery Details",
            message="How does the delivery work and what are the charges?",
        )
    ]

@cl.on_chat_start
async def start():
    cl.user_session.set("message_history", [])
    
    # 2. Rich Welcome Message
    welcome_text = """
### 🥩 Welcome to **The Meat Story**! 
I am your personal AI Shop Assistant. 

Whether you're looking for fresh cuts, marinades, or checking our latest prices—I have our entire store catalog ready to help you.

**How can I help you today?**
"""
    await cl.Message(content=welcome_text, author="The Meat Story").send()

@cl.on_message
async def main(message: cl.Message):
    history = cl.user_session.get("message_history")
    history.append(("user", message.content))

    msg = cl.Message(content="", author="The Meat Story")
    await msg.send()

    # 3. Add a visual 'Thinking' loader so the user knows the AI is working
    async with cl.Step(name="Searching the Catalog...", type="tool") as step:
        step.output = "Consulting The Meat Story knowledge base..."
        
        # 4. Stream from LangGraph
        async for event in graph.astream({"messages": history}, stream_mode="values"):
            if event["messages"]:
                last_message = event["messages"][-1]
                if getattr(last_message, "type", "") == "ai" and last_message.content:
                    msg.content = last_message.content
                    await msg.update()
        
    # Remove the 'Thinking...' UI block completely once the generation is done
    await step.remove()

    history.append(("assistant", msg.content))
    cl.user_session.set("message_history", history)