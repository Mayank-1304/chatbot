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

        # Handle "X packs of Y kg" or "X packs of Yg" patterns first
        # e.g. "2 packs of 1kg" = 2 * 1000g = 2000g, pack_size_gm = 1000
        pack_of_match = re.search(r"(\d+)\s*packs?\s*of\s*(\d+\.?\d*)\s*(kg|g|gm|gms)", requested_qty_str, re.IGNORECASE)
        if pack_of_match and unit_type == "gms":
            num_packs = float(pack_of_match.group(1))
            pack_size = float(pack_of_match.group(2))
            pack_unit = pack_of_match.group(3).lower()
            if "kg" in pack_unit:
                pack_size *= 1000  # Convert kg to grams
            qty_val = num_packs * pack_size
            # Override requested_pack_size with the user's explicit pack size
            req["pack_size_gm"] = pack_size
        else:
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", requested_qty_str)
            if nums:
                qty_val = float(nums[0])
                if "kg" in requested_qty_str:
                    qty_val *= 1000  # Convert kg to grams
                elif "pack" in requested_qty_str and unit_type == "gms":
                    # "2 packs" with no size specified -> 2 * standard pack size
                    qty_val = qty_val * units_in_pack
                elif unit_type == "gms" and qty_val <= 10 and "g" not in requested_qty_str:
                    # Bare small numbers like "1" or "2" for gms items are almost certainly kg
                    qty_val *= 1000
            else:
                qty_val = units_in_pack  # Default to 1 standard pack


        # Calculate customized pricing vs standard pack pricing
        is_customized = False
        requested_pack_size = req.get("pack_size_gm")
        
        if unit_type == "gms":
            price_ratio = qty_val / units_in_pack  # Used for price calculation (prorated)
            import math
            packs = math.ceil(price_ratio)  # Always whole number — you can't give 0.086 of a pack
            # Enforce minimum order of 5g
            if qty_val < 5:
                results.append({"error": f"Minimum order is 5g. You requested {qty_val}g of {item.get('title')}. Please order at least 5g."})
                continue
            # Custom packing applies when quantity is less than one standard pack
            if requested_pack_size and float(requested_pack_size) < units_in_pack:
                is_customized = True
            elif qty_val < units_in_pack:
                is_customized = True
        else:
            # Pieces (Quail, Rabbit, etc)
            price_ratio = qty_val
            packs = int(qty_val) if qty_val >= 1 else 1
            if qty_val < 1:
                is_customized = True

        item_total = price_ratio * price_per_pack  # Price based on actual grams, not rounded packs

        # --- Organ Meats 50% Discount Rules ---
        discount_eligibility_list = [
            # Organ Meats
            "mutton brain", "buff brain",
            "chicken liver", "mutton liver", "buff liver", "pork liver", "duck liver",
            "mutton kidney", "buff kidney", "pork kidney",
            "mutton spleen", "buff spleen",
            "cleaned intestines", "tripe (unbleached)", "mutton lungs", "buff lungs", "buff tongue",
            # Muscle Organs
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
            # Human-readable: for custom orders show actual pack count × individual size, for standard orders show standard pack size
            "packsDisplay": (
                f"{max(1, round(qty_val / float(requested_pack_size)))} pack{'s' if round(qty_val / float(requested_pack_size)) != 1 else ''} of {int(float(requested_pack_size))}g each"
                if (is_customized and requested_pack_size)
                else f"1 pack of {int(qty_val)}g" if is_customized
                else f"{packs} pack{'s' if packs != 1 else ''} of {int(units_in_pack)}g each"
            ),
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
    # TODO: Replace with real API call: GET /api/v1/orders/count?date={date}
    # For now, always return available for demo purposes.
    return {"date": date, "full": False, "count": 12, "message": "Capacity available."}

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

tools = [calculate_order_details, create_meat_order, get_payment_link, verify_and_confirm_payment]
tool_node = ToolNode(tools)

# --- 3. KNOWLEDGE BASE SYNC ---

def get_complete_knowledge():
    """Reads the catalog file once and returns both product data and website info."""
    cache_file = "meat_catalog.json"
    if not os.path.exists(cache_file):
        return "Catalog offline.", "No website info available."
        
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            products = json.load(f).get("data", [])
            if not products:
                return "Catalog empty.", "No website info found."

            import re
            
            # 1. Process Product Catalog
            kb_catalog = "--- LIVE CATALOG ---\n"
            for item in products:
                offer = item.get('offers', '')
                offer_text = f"Offers: {offer} | " if offer else ""
                desc = item.get('shortDescription', '')
                desc_text = f"Description: {desc} | " if desc else ""
                
                scraped = item.get('scraped_page_text', '')
                if scraped:
                    clean_scraped = re.sub(r'HOME ABOUT SHOP BUILD YOUR MEAL PLAN CONTACT Go Back.*?(?=₹|\b[A-Z])', '', scraped, flags=re.IGNORECASE)
                    clean_scraped = re.sub(r'Quantity \(in Grams\).*', '', clean_scraped, flags=re.IGNORECASE).strip()
                    scraped_text = f"Features: {clean_scraped} | " 
                else:
                    scraped_text = ""
                    
                kb_catalog += (f"Item: {item.get('title')} | "
                              f"Price: {item.get('price')} per {item.get('units_in_pack')}{item.get('unit')} | "
                              f"{offer_text}{desc_text}{scraped_text}"
                              f"Category: {item.get('parentCategory')}\n")

            # 2. Extract Website Info (FAQs/Footer) from the first entry
            website_kb = "No additional info found."
            first_scraped = products[0].get("scraped_page_text", "")
            footer_match = re.search(r"(NAVIGATE.*)", first_scraped, re.IGNORECASE | re.DOTALL)
            if footer_match:
                website_kb = footer_match.group(1).strip()
            
            return kb_catalog, website_kb

    except Exception as e:
        return f"Error loading catalog: {str(e)}", "Website info error."
# --- 4. BUTCHER'S BUDDY BRAIN (The Agent Node) ---

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0).bind_tools(tools)

def meat_story_agent(state: MessagesState):
    catalog, website_kb = get_complete_knowledge()
    current_date = datetime.now().strftime("%Y-%m-%d")
    system_message = SystemMessage(content=f"""
    You are Butcher's Buddy, the VIP Concierge for 'The Meat Story'.
    Your style is "Sophisticated & Proactive." You are hyper-efficient but warm. 
    Avoid robotic repetition. Never use the exact same closing phrase twice in a row.

    Today's date is {current_date}.
    CATALOG DATA: {catalog}
    ADDITIONAL INFO: {website_kb}

    --- THE SALESMAN'S GOLDEN RULES ---
    1. THE "IMMEDIATE" PROMO: If a user mentions ANY Organ Meat (Kidney, Liver, etc.), your VERY FIRST response MUST include BOTH the price,how much pack the customer wants and the discount offer if any. Never make the customer ask for the price separately.
       - Bad: "Great choice! How much would you like?or how much pack do you want? Remember the 50% discount!"
       - Good: "Great choice! Pork Liver is ₹100 per 100g. And if you order 500g or more, you get a 50% discount — bringing it down to just ₹50/100g! How much would you like to add or how many packs do you want?"
       - For non-organ meats, still always mention the price per pack in your first response. and ask how much pack they want.

    2 whenver someone is asking like what options are available for the product just list the few options available for the product say many more options are available.

    3. PROACTIVE UPSELLING: When suggesting "more products," be specific based on their cart. If they bought Chicken, suggest a Mutton cut or an Organ meat. 
    
    4. PACK LOGIC: Understand what customers mean by "packs":
       - "2 packs" (no size) = 2 × standard pack size (500g) = 1kg total , always ask for confirmation.
       - "2 packs of 1kg" = 2 separate packages, each 1kg = 2kg total custom fees if the order is less than standard packaging 
       - "1kg" = 1000g total (2 standard packs of 500g)
       Always confirm with the customer before calculating: "Just to confirm — 2 packs of 1kg each, so 2kg total. Correct?"


    5. ⚠️ NEVER HALLUCINATE PRICES: You MUST NEVER quote a subtotal, total, or calculated cost from memory or estimation. ONLY quote numbers that came directly from a 'calculate_order_details' tool call. If you haven't called the tool yet, do NOT say things like "that will be ₹520". Wait until the tool runs, then use those exact numbers.

    6. ✅ ALWAYS ACCEPT SMALL ORDERS (Custom Packing Rule):
       - Minimum order is 5g. NEVER reject any order of 5g or more.
       - If a customer asks for LESS than the standard pack size (e.g. 50g when standard is 500g), ALWAYS accept it. Inform them: "A Custom Packing Fee of ₹50 + 18% GST (₹9) = ₹59 total will be added."
       - NEVER say "I don't have that option" or "that size is not available" for any quantity >= 5g.
       - Bad: "I don't have an option for 50gm. The pack is 500gm."
       - Good: "Absolutely! 50g of Chicken Wings is possible. Since it's less than our standard 500g pack, a custom packing fee of ₹50 + ₹9 GST applies. how many packs you want to add to your cart?"

    --- ORDER WORKFLOW ---
    1. SELECTION & DISCOUNT TRIGGER: Acknowledge the item. If it's an Organ/Muscle meat, lead with the 50% bulk discount offer immediately.
       Then ALWAYS ask: "How many grams (or how many packs) would you like?"
       - Never assume a quantity. Always ask this question first.

    2. CONFIRM PACKS (ALWAYS — NO EXCEPTIONS — THIS IS THE MOST CRITICAL RULE):
       - ⚠️ WHENEVER the customer mentions ANY gram/kg quantity, you MUST ALWAYS ask:
         "How many packs of [Xg] would you like?"
         NEVER assume 1 pack. NEVER skip this. NEVER proceed to calculate without this answer.
       
       - If the customer gives GRAMS (e.g., "500g", "200g", "1kg"):
         → ALWAYS respond: "Got it! How many packs of [Xg] would you like?"
         Example: Customer says "500g" → Agent says: "How many packs of 500g would you like — 1 pack, 2 packs, or more?"
         Example: Customer says "200g" → Agent says: "How many packs of 200g would you like?
           Also, just so you know — our standard pack is 500g. If you go for 500g packs, the custom packing fee of ₹59 won't apply. Shall I keep it as 200g packs or switch to 500g?"
         Example: Customer says "1kg" → Agent says: "How many packs of 1kg would you like — 1 pack, 2 packs, or more?"
       
       - If the customer gives PACKS with no size (e.g., "2 packs"):
         → Confirm the size: "That's 2 packs of our standard 500g each (1kg total). Correct?"
       
       - If the customer gives PACKS with a size (e.g., "3 packs of 200g"):
         → Confirm: "3 packs of 200g each (600g total). Correct? Note: since 200g is less than our standard 500g pack, a custom packing fee of ₹50 + ₹9 GST applies per custom item."
       
       - NEVER skip this step. NEVER call calculate_order_details until you have BOTH the pack size AND the number of packs confirmed by the customer.

    3. MORE ITEMS?: After confirmation, ask ONE short question:
       "Would you like to add anything else to your order?"
       
       - Good: "Anything else to add? 🛒"
       - Good: "Would you like to add anything else to your cart?"
       - Good: "Shall I add anything else, or shall we wrap up?"
       - Good: "Before I finalize, would you be interested in other items? We have a wide variety of cuts and organ meats available. Perhaps some Mutton Ribs or Chicken Heart to complement your selection?"
       - If YES → repeat steps 1 & 2 for the new item.  
       - If NO → go to step 4.

    4. THE SUMMARY: Use 'calculate_order_details'. ALWAYS format the summary using markdown bullet points — NEVER as a single line.
       Use the 'packsDisplay' field from the tool result for each item's quantity — NEVER calculate packs yourself.
       Each price line MUST be on its own separate line. Example:

       🛒 **Your Order Summary:**
       • 🍖 Chicken Wings | 6 packs of 50gm each | ₹72
       • 🥩 Mutton Ribs | 2 packs of 500gm each | ₹900  

       **Subtotal:** ₹972
       **Custom Packing Fee:** ₹50(if applicable)
       **GST:** ₹9(if applicable)
       **Final Total: ₹1,031**

       Does this look correct?

    5. SCHEDULING: Once confirmed, ask: "Would you prefer Same-Day or Next-Day delivery?"
       Then call 'create_meat_order' → get_payment_link.

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

