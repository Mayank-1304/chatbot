# 🥩 The Meat Story | AI Butcher's Buddy

A high-end AI concierge and order-management system for **The Meat Story**, built with **LangGraph** and powered by **Google Gemini 2.0 Flash**. 

This isn't just a chatbot; it's a sophisticated "VIP Concierge" capable of handling complex butchery-specific business rules, dynamic pricing, and inventory-aware scheduling.

---

## ✨ Key Features

### 🤵 VIP Concierge Persona
Programmed with a **"Fast & Elegant"** personality. No conversational fluff—just hyper-efficient, polite service that gets the order locked in fast.

### 🧠 Intelligent Pricing Engine
- **Per-Item Customization**: Automatically detects when a user asks for non-standard pack sizes (e.g., 100g bags) and applies a ₹50.00 customization fee *per product*.
- **Automatic GST Calculation**: Calculates 18% GST specifically and exclusively on the customization fees.
- **Organ Meat Promo**: Proactively upsells a 50% discount on all Organ/Muscle meats if the user orders over 500g.

### 🚚 Dynamic Logistics
- **Same-Day & Next-Day Focus**: Prioritizes immediate delivery while remaining flexible for future custom dates.
- **Capacity Management**: Features a hard limit of **30 premium orders per day** to ensure quality control.

### 🌐 Scraper-Driven Knowledge Base
Uses **Playwright** to systematically crawl the Meat Story store, extracting real-time pricing and offers into a decoupled, offline-first `meat_catalog.json`.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- A Google Gemini API Key
- LangGraph CLI (optional, for dev)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-repo/meat-story-ai.git
cd meat-story-ai

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### 3. Configuration
Copy the `.env.example` file to `.env` and fill in your credentials:
```env
GOOGLE_API_KEY="your_key_here"
LANGSMITH_API_KEY="optional_for_tracing"
TEST_USER_ID="optional_mongo_user_id"
# ...etc
```

---

## 🛠️ Usage

### Sync the Catalog
To refresh the knowledge base from the live website:
```bash
python extract_prices.py
```

### Launch the UI
Start the interactive Streamlit chat interface:
```bash
streamlit run ui_streamlit.py
```

---

## 🏗️ Architecture

- **Core Logic**: `agent.py` (LangGraph State Machine)
- **Data Extraction**: `extract_prices.py` (Playwright Scraper)
- **Frontend**: `ui_streamlit.py` (Streamlit Chat)
- **Database**: `meat_catalog.json` (Local Storage)

---

## 🔒 Security
The project uses a strict `.gitignore` to protect sensitive environment variables. Always use `.env` for API keys and database credentials.

---
*Built with ❤️ for The Meat Story.*
