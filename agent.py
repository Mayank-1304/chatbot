import os
import json
import requests
import uuid
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Union
from dotenv import load_dotenv
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

load_dotenv()

# --- 1. CONFIGURATION & TEST IDs ---
TEST_USER_ID = os.getenv("TEST_USER_ID")
TEST_ADDRESS_ID = os.getenv("TEST_ADDRESS_ID")
TEST_PET_ID = os.getenv("TEST_PET_ID")

# --- 2. ENHANCED TOOLS ---

# Bridge data between calculate and create tools to prevent LLM hallucinations
ORDER_CACHE = {}

@tool
def calculate_order_details(items_requested: List[Dict[str, Any]]):
    """
    Calculates precise quantities, pack counts, and pricing from the catalog.
    Input: items_requested = [{"name": "Chicken Breast", "quantity": "1kg", "pack_size_gm": 500}]
    NOTE: Provide 'pack_size_gm' explicitly if the user asks for smaller customized packets (e.g., "5 packs of 100g" -> pack_size_gm: 100).
    """
    global ORDER_CACHE
    cache_file = "meat_catalog.json"
    if not os.path.exists(cache_file):
        return "❌ Error: Catalog not found. Please sync knowledge base first."
        
    with open(cache_file, "r", encoding="utf-8") as f:
        catalog_data = json.load(f).get("data", [])

    results = []
    subtotal = 0

    for req in items_requested:
        name = req.get("name", "").lower()
        requested_qty_str = str(req.get("quantity", "1")).lower()
        
        # Simple name matching
        item = next((i for i in catalog_data if name in i.get("title", "").lower()), None)
        if not item:
            continue

        units_in_pack = item.get("units_in_pack", 500)
        unit_type = item.get("unit", "gms").lower()
        price_per_pack = item.get("price", 0)

        # Parse requested quantity using regex for robustness
        qty_val = 1.0
        import re
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", requested_qty_str)
        if nums:
            qty_val = float(nums[0])
            if "kg" in requested_qty_str: qty_val *= 1000
        else:
            qty_val = 1.0

        # Calculate customized pricing vs standard pack pricing
        is_customized = False
        requested_pack_size = req.get("pack_size_gm")
        
        if unit_type == "gms":
            packs = qty_val / units_in_pack  # Support exact fractional calculations for any weight
            if requested_pack_size and float(requested_pack_size) < units_in_pack:
                is_customized = True
            elif qty_val < units_in_pack:
                is_customized = True
        else:
            # Pieces (Quail, Rabbit, etc)
            packs = qty_val
            if qty_val < 1:
                is_customized = True

        item_total = packs * price_per_pack

        # --- Organ Meats 50% Discount Rules ---
        discount_eligibility_list = [
            "mutton brain", "buff brain",
            "chicken liver", "mutton liver", "buff liver", "pork liver", "duck liver",
            "mutton kidney", "buff kidney", "pork kidney",
            "mutton spleen", "buff spleen",
            "cleaned intestines", "tripe (unbleached)", "mutton lungs", "buff lungs", "buff tongue",
            "chicken heart", "mutton heart", "buff heart",
            "chicken gizzard"
        ]
        
        item_title_lower = item.get("title", "").lower()
        is_organ_meat = any(d in item_title_lower for d in discount_eligibility_list)
        
        applied_discount = "No"
        if is_organ_meat and unit_type == "gms" and qty_val > 500:
            item_total *= 0.5
            applied_discount = "50% Off (Organ Meat > 500g)"
            
        subtotal += item_total

        results.append({
            "itemId": item.get("_id"),
            "itemTitle": item.get("title"),
            "itemPrice": price_per_pack,
            "quantity": qty_val, 
            "packs": packs,
            "unitsInPack": units_in_pack,
            "unit": unit_type,
            "parentCategory": item.get("parentCategory", "Protiens"),
            "isCustomized": is_customized,
            "appliedDiscount": applied_discount,
            "itemTotal": item_total
        })

    if not results:
        return "❌ No matching items found in catalog."

    # Apply a 50 Rs fee PER customized item
    customized_count = sum(1 for item in results if item["isCustomized"])
    customization_fee = customized_count * 50
    gst_on_customization = round(customization_fee * 0.18, 2)  # 18% GST exclusively on the total customization fees

    order_summary = {
        "items": results,
        "subtotal": subtotal,
        "customizationFee": customization_fee,
        "gst": gst_on_customization,
        "finalCost": subtotal + customization_fee + gst_on_customization,
        "currency": "₹"
    }
    
    # Store for Direct Handover to create_meat_order
    ORDER_CACHE["last_calculated"] = order_summary
    return order_summary

@tool
def check_delivery_capacity(date: str):
    """
    Checks if there is capacity for delivery on a specific date (YYYY-MM-DD).
    The daily limit is 30 orders.
    """
    # MOCK LOGIC for demo purposes:
    # In a real scenario, this would call an API like GET /api/v1/orders/count?date=...
    import random
    # Let's say tomorrow is sometimes full, other days are mostly free
    order_count = random.randint(15, 35)
    
    if order_count >= 30:
        return {"date": date, "full": True, "count": order_count, "message": "Capacity reached for this date."}
    else:
        return {"date": date, "full": False, "count": order_count, "message": "Capacity available."}

@tool
def create_meat_order(confirm: bool = True, delivery_date: str = None):
    """
    Creates the formal order in the system using the last calculated details.
    Call this only when the user confirms they want to proceed.
    delivery_date: ISO format string (e.g., '2026-03-31T10:00:00.000Z')
    """
    global ORDER_CACHE
    order_details = ORDER_CACHE.get("last_calculated")
    
    if not order_details:
        return "❌ Error: No calculated details found. Please ask me to check prices first."

    url = "https://api.bot.themeatstory.com/api/v1/orders"
    headers = {"Content-Type": "application/json"}
    unique_order_str = f"{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[4:8].upper()}-{uuid.uuid4().hex[8:14].upper()}"

    # Default delivery date to tomorrow if not provided
    if not delivery_date:
        tomorrow = datetime.now() + timedelta(days=1)
        delivery_date = tomorrow.strftime("%Y-%m-%dT10:00:00.000Z")

    items_to_buy = order_details.get("items", [])
    cleaned_items = []
    for item in items_to_buy:
        cleaned_items.append({
            "itemId": item.get("itemId"),
            "cartId": f"CART-{uuid.uuid4().hex[:8].upper()}",
            "quantity": item.get("quantity"),
            "totalQty": item.get("quantity"),
            "itemPrice": item.get("itemPrice"),
            "packs": item.get("packs"),
            "totalCost": item.get("itemTotal"),
            "itemTitle": item.get("itemTitle"),
            "shopType": "byp",
            "instructions": "",
            "unit": item.get("unit"),
            "unitsInPack": item.get("unitsInPack"),
            "parentCategory": item.get("parentCategory"),
            "isCustomized": item.get("isCustomized", False),
            "status": "pending"
        })

    payload = {
        "orderId": unique_order_str,
        "items": cleaned_items,
        "user": TEST_USER_ID,
        "address": TEST_ADDRESS_ID,
        "pet": TEST_PET_ID,
        "status": "pending",
        "isPaid": False,
        "deliveryDate": delivery_date,
        "totalCost": order_details.get("subtotal"),
        "customizationFee": order_details.get("customizationFee"),
        "gst": order_details.get("gst", 0),
        "finalCost": order_details.get("finalCost")
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        if response.status_code == 201:
            res_json = response.json()
            if "data" not in res_json: res_json["data"] = {}
            res_json["data"].update(payload)
            return res_json
        return f"❌ API Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"❌ Connection Error: {str(e)}"

@tool
def get_payment_link(order_id_human: str, final_amount: float):
    """
    Initializes a Razorpay payment. 
    Use the 'orderId' (human readable) and 'finalCost' from the create_meat_order response.
    """
    url = "https://api.bot.themeatstory.com/api/v1/payments/order"
    payload = {
        "amount": int(final_amount * 100), # Razorpay expects Paise
        "orderId": order_id_human
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        return response.json()
    except Exception as e:
        return f"❌ Payment API Error: {str(e)}"

@tool
def verify_and_confirm_payment(razorpay_payment_id: str, razorpay_order_id: str, razorpay_signature: str, mongodb_id: str):
    """
    Finalizes the payment by verifying the signature and confirming the order status.
    Call this when you receive a '/payment_success' message.
    """
    # 1. Verify Payment
    verify_url = "https://api.bot.themeatstory.com/api/v1/payments/verify"
    verify_payload = {
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature
    }
    
    # 2. Confirm Order
    confirm_url = f"https://api.bot.themeatstory.com/api/v1/orders/confirmpayment/{mongodb_id}"
    confirm_payload = {
        "isPaid": True,
        "paymentStatus": "paid",
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
        "razorpay": {
            "rzpOrderId": razorpay_order_id,
            "rzpPaymentId": razorpay_payment_id,
            "rzpSignature": razorpay_signature
        }
    }

    try:
        requests.post(verify_url, json=verify_payload, timeout=15)
        res = requests.post(confirm_url, json=confirm_payload, timeout=15)
        return res.json()
    except Exception as e:
        return f"❌ Error finalizing payment: {str(e)}"

tools = [calculate_order_details, check_delivery_capacity, create_meat_order, get_payment_link, verify_and_confirm_payment]
tool_node = ToolNode(tools)

# --- 3. KNOWLEDGE BASE SYNC ---

def load_website_knowledge():
    """Loads additional website info like FAQs, policies, etc."""
    kb_file = "website_knowledge.md"
    if os.path.exists(kb_file):
        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                return f.read()[:5000] # Limit to 5k chars to save context
        except:
            pass
    return "No additional website info available."

def load_meat_knowledge():
    """Reads product catalog from local file. (Updated by external scraper script)"""
    cache_file = "meat_catalog.json"
    
    if not os.path.exists(cache_file):
        return "Catalog currently offline."
    
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            products = json.load(f).get("data", [])
            kb = "--- LIVE CATALOG ---\n"
            for item in products:
                import re
                
                offer = item.get('offers', '')
                offer_text = f"Offers: {offer} | " if offer else ""
                
                desc = item.get('shortDescription', '')
                desc_text = f"Description: {desc} | " if desc else ""
                
                scraped = item.get('scraped_page_text', '')
                if scraped:
                    # Clean the raw scraped text by removing the repetitive website headers and footers
                    clean_scraped = re.sub(r'HOME ABOUT SHOP BUILD YOUR MEAL PLAN CONTACT Go Back.*?(?=₹|\b[A-Z])', '', scraped, flags=re.IGNORECASE)
                    clean_scraped = re.sub(r'Quantity \(in Grams\).*', '', clean_scraped, flags=re.IGNORECASE).strip()
                    scraped_text = f"Page Features: {clean_scraped} | " 
                else:
                    scraped_text = ""
                    
                kb += (f"Item: {item.get('title')} | "
                       f"Price: {item.get('price')} per {item.get('units_in_pack')}{item.get('unit')} | "
                       f"{offer_text}{desc_text}{scraped_text}"
                       f"Category: {item.get('parentCategory')}\n")
            return kb
    except Exception as e:
        return f"Error loading catalog: {str(e)}"
# --- 4. BUTCHER'S BUDDY BRAIN (The Agent Node) ---

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0).bind_tools(tools)

def meat_story_agent(state: MessagesState):
    catalog = load_meat_knowledge()
    website_kb = load_website_knowledge()
    current_date = datetime.now().strftime("%Y-%m-%d")
    system_message = SystemMessage(content=f"""
    You are Butcher's Buddy, the VIP Concierge for 'The Meat Story'.
    Your conversational style is "Fast & Elegant": extremely polite, hyper-efficient, and zero fluff.
    Provide precise, concise answers without overly long conversational filler. Serve the customer quickly and confirm details immediately.
    Today's date is {current_date}.
    CATALOG DATA:
    {catalog}
    ADDITIONAL WEBSITE INFO (FAQs, Policies):
    {website_kb}
    STRICT BUSINESS RULES:
    1. CAPACITY: We strictly limit operations to 30 premium orders per day.
    2. DELIVERY: We default to delivering orders on the Same-Day or Next-Day for maximum freshness. However, if a customer explicitly requests a specific preferable future date, we absolutely accept it.
    
    YOUR GUIDING PRINCIPLES:
    - If a user asks for a recommendation, suggest the best cuts based on their category.
    - LISTING ITEMS: If a user asks for available options in a broad category (like "chicken" or "mutton"), you don't have to list every single item. List 4 to 5 popular options and ALWAYS end the sentence with "...and many more! Let me know if you are looking for a specific cut." This ensures they know our huge catalog includes other items like wings or exotic cuts!
    - ORGAN PROMO UPSELL: Brains, Livers, Kidneys, Spleens, Intestines, Tripe, Lungs, Tongues, Hearts, and Gizzards (Chicken/Mutton/Buff/Pork/Duck) all receive a 50% DISCOUNT if the customer orders MORE THAN 500g. When a customer asks about one of these items, YOU MUST proactively upsell the deal immediately, but ONLY mention the specific item they asked about! Do NOT list the other organ meats. Example: "By the way, if you order more than 500g of Mutton Heart, you'll get a 50% discount on it!"
    - MINIMUM ORDER & CUSTOM PACKING: The absolute minimum order is 5gms. If a user asks for a total quantity less than the standard pack size OR if they specifically request their order to be broken into smaller custom packets (e.g., "5 separate packs of 100g each"), a customized packing charge of ₹50.00 will be applied PER INDIVIDUAL PRODUCT to their final bill. Never reject these custom requests.
    - Always provide the precise breakdown of packs and prices.
    - Be proactive but polite about the 30-order limit.
    
    ORDER WORKFLOW:
    1. QUANTITY CHECK: If the user asks for items but doesn't specify a weight/quantity, you MUST ask them how much they want of each item FIRST. Do not assume quantities.
    2. CALCULATE: Once all quantities are locked in, use 'calculate_order_details' to calculate the exact cost.
    3. ITEM SUMMARY: Display a completely itemized bulleted list of their cart (Product Name | Weight | Individual Price). Then, state the Subtotal, Custom Packing Fee (if any), GST (if any), and the Final Total.
    4. CONFIRM: Ask for explicit consent on this detailed summary ("Does this look correct?").
    5. SCHEDULE: Once confirmed, ask them if they prefer Same-Day or Next-Day delivery. If they bring up a specific future date they'd prefer, kindly accept it.
    6. CAPACITY CHECK: ALWAYS call 'check_delivery_capacity' for their chosen date. If that day is full (>= 30 orders), suggest the next available day.
    7. CREATE: Call 'create_meat_order' ONLY after confirming the available date.
    8. FINALIZE: Call 'get_payment_link' and provide the Razorpay ID.
    """)
    return {"messages": [llm.invoke([system_message] + state["messages"])]}

# --- 5. GRAPH ---

builder = StateGraph(MessagesState)
builder.add_node("meat_bot", meat_story_agent)
builder.add_node("tools", tool_node)
builder.add_edge(START, "meat_bot")
builder.add_conditional_edges("meat_bot", lambda x: "tools" if x["messages"][-1].tool_calls else END)
builder.add_edge("tools", "meat_bot")

graph = builder.compile()

