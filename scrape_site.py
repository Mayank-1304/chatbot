import os
import json
import time
from dotenv import load_dotenv
from firecrawl import Firecrawl
from firecrawl.types import ScrapeOptions  # Import this for the new SDK

load_dotenv()
app = Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))

def deep_sync_knowledge():
    print("Starting Deep Crawl of The Meat Story...")
    
    # In the v1 SDK, crawl options are direct arguments, 
    # and scrape settings go inside ScrapeOptions.
    crawl_job = app.crawl(
        url="https://www.themeatstory.com/shop/",
        limit=20,  # Limits to 20 pages to save your credits
        scrape_options=ScrapeOptions(
            formats=["markdown"],
            only_main_content=True,
            wait_for=5000  # Give React time to load on each page
        )
    )
    
    # The crawl method in the new SDK automatically waits for completion
    # and returns the full result object.
    if crawl_job and hasattr(crawl_job, 'data'):
        combined_info = ""
        for doc in crawl_job.data:
            # Each 'doc' is a Document object with metadata and markdown
            title = getattr(doc.metadata, 'title', 'Untitled Page')
            content = getattr(doc, 'markdown', '')
            combined_info += f"\n\n--- SECTION: {title} ---\n{content}\n"

        with open("full_meat_knowledge.txt", "w", encoding="utf-8") as f:
            f.write(combined_info)
        
        print(f"Success! Saved data from {len(crawl_job.data)} pages to 'full_meat_knowledge.txt'")
    else:
        print("Crawl failed or returned no data.")

if __name__ == "__main__":
    deep_sync_knowledge()