import os
import json
from dotenv import load_dotenv
from firecrawl import Firecrawl
from firecrawl.types import ScrapeOptions

load_dotenv()
app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))

def deep_sync_knowledge():
    print("🚀 Starting Firecrawl to enhance 'meat_catalog.json'...")
    
    # 1. LOAD THE EXISTING PRICE DATA (From your Playwright script)
    try:
        with open("meat_catalog.json", "r", encoding="utf-8") as f:
            catalog = json.load(f)
        print(f"📂 Loaded {len(catalog)} items from existing catalog.")
    except FileNotFoundError:
        print("⚠️ meat_catalog.json not found! Creating a new one.")
        catalog = []

    # 2. RUN FIRECRAWL (For general knowledge/descriptions)
    crawl_job = app.crawl(
        url="https://www.themeatstory.com/shop/",
        limit=5, # Keep it small for section info
        scrape_options=ScrapeOptions(
            formats=["markdown"],
            only_main_content=True,
            wait_for=5000 
        )
    )
    
    if crawl_job and hasattr(crawl_job, 'data'):
        # 3. APPEND THE NEW MARKDOWN DATA TO THE JSON
        # We create a new key called 'page_knowledge' for the general info
        knowledge_base = ""
        for doc in crawl_job.data:
            content = getattr(doc, 'markdown', '')
            knowledge_base += f"\n{content}\n"

        # 4. STRUCTURE THE FINAL DATA
        # We keep the 'products' separate from 'general_info' inside the SAME file
        final_data = {
            "last_updated": "2026-03-28",
            "products": catalog, # Your 60+ prices from Playwright
            "general_info": knowledge_base # General shop info from Firecrawl
        }

        # 5. SAVE BACK TO THE SAME JSON
        with open("meat_catalog.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=4)
        
        print(f"✅ Success! Merged Firecrawl data into 'meat_catalog.json'.")
    else:
        print("❌ Firecrawl returned no data.")

if __name__ == "__main__":
    deep_sync_knowledge()