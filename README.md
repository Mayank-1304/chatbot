# The Meat Story AI Bot

An AI assistant for "The Meat Story" utilizing a LangGraph workflow and Google's Gemini 2.0 Flash model. It answers customer queries regarding products and prices after dynamically scraping the data from the website.

## Features
- **Site Scraping Tooling:** Uses Firecrawl (`scrape_site.py`) and Playwright (`extract_prices.py`) to systematically extract product details and pricing into a central knowledge base.
- **LangGraph Agent:** `agent.py` establishes a Google GenAI integration representing the shop manager/agent to answer user text inputs.

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
   playwright install chromium
   ```
4. **Environment Variables:**
   - Copy `.env.example` to `.env`
   - Fill in your `LANGSMITH_API_KEY`, `GOOGLE_API_KEY`, and `FIRECRAWL_API_KEY`.

## Usage

1. **Update Data:** 
   Run either `scrape_site.py` or `extract_prices.py` to generate/update the `full_meat_knowledge.txt`.
   ```bash
   python extract_prices.py
   # OR
   python scrape_site.py
   ```
2. **Run Agent:**
   The `agent.py` file exposes a compiled LangGraph workflow. Integrate it into your application logic by importing the `graph` or interact with it via LangGraph Studio using the `langgraph.json` configuration.

## Note on Security
Please ensure that your `.env` file is never committed or pushed to source control (it exists in `.gitignore` already). The `.env.example` file is safe to push.
