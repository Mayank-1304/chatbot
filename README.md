# The Meat Story AI Bot

An AI assistant for "The Meat Story" utilizing a LangGraph workflow and Google's Gemini 2.0 Flash model. It answers customer queries regarding products and prices after dynamically scraping the data from the website.

## Features
- **Site Scraping Tooling**: 
  - `extract_prices.py` uses Playwright to systematically extract product details and pricing into a central knowledge base.
  - `scrape_site.py` uses Firecrawl to extract general shop information and merges it with the price data.
- **LangGraph Agent**: `agent.py` establishes a Google GenAI integration representing the shop manager/agent to answer user text inputs.
- **Interactive UI**: `ui.py` provides a beautiful chat interface powered by Chainlit.

## Setup Instructions

1. **Clone the repository.**
2. **Setup virtual environment** (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install chainlit # Note: required for the UI
   playwright install chromium
   ```
4. **Environment Variables:**
   - Copy `.env.example` to `.env`
   - Fill in your `LANGSMITH_API_KEY`, `GOOGLE_API_KEY`, and `FIRECRAWL_API_KEY`.

## Usage

1. **Update Data (Scraping):** 
   You must run these scripts to generate and populate `meat_catalog.json`:
   ```bash
   # Step 1: Extract real-time product pricing and details
   python extract_prices.py
   
   # Step 2: Extract general shop information and merge with catalog
   python scrape_site.py
   ```

2. **Run the Interactive Chatbot:**
   Launch the Chainlit UI to interact with "The Meat Story" AI on your browser:
   ```bash
   chainlit run ui.py -w
   ```
   
3. **Use the Agent API:**
   Alternatively, the `agent.py` file exposes a compiled LangGraph workflow. You can integrate it into your application logic by importing the `graph` or interact with it via LangGraph Studio using the `langgraph.json` configuration.

## Note on Security
Please ensure that your `.env` file is never committed or pushed to source control (it exists in `.gitignore` already). The `.env.example` file is safe to push.
