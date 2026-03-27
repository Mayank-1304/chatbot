import asyncio
import json # Changed to JSON for better Chatbot integration
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # headless=False lets you see the "Buy Now" clicks happening
        browser = await p.chromium.launch(headless=False) 
        page = await browser.new_page()
        
        print("🚀 Opening The Meat Story Shop...")
        url = "https://www.themeatstory.com/shop"
        await page.goto(url, wait_until="networkidle")
        
        scraped_results = []
        
        # 1. Get all buttons initially
        await page.wait_for_selector("button:has-text('Buy Now')", timeout=10000)
        buttons_count = await page.locator("button:has-text('Buy Now')").count()
        print(f"📦 Found {buttons_count} products to process.")

        for i in range(buttons_count):
            try:
                # Re-locate buttons each time to avoid "stale element" errors
                btn = page.locator("button:has-text('Buy Now')").nth(i)
                await btn.scroll_into_view_if_needed()
                
                # Get the product name from the main grid
                product_name = await page.evaluate(
                    "(btn) => btn.closest('div').parentElement.querySelector('h2').innerText", 
                    await btn.element_handle()
                )

                print(f"[{i+1}/{buttons_count}] Opening: {product_name}...")
                
                # 2. Click "Buy Now"
                await btn.click(force=True)
                
                # 3. Wait for the Modal/Popup to appear
                # We wait for the price symbol OR a common modal class
                await page.wait_for_selector("text=₹", timeout=8000)
                await asyncio.sleep(1) # Extra half-second for React to settle

                # 4. CAPTURE EVERYTHING: Grab the text of the entire modal
                # Usually, popups are in a 'role=dialog' or a specific div
                modal_text = await page.evaluate("""() => {
                    const modal = document.querySelector('.modal-content, [role="dialog"], .popup, .ProductView_root');
                    return modal ? modal.innerText : document.body.innerText;
                }""")

                # Clean up the text for our JSON
                clean_info = modal_text.replace('\n', ' | ').strip()
                
                scraped_results.append({
                    "product": product_name,
                    "full_details": clean_info
                })
                
                print(f"   ✅ Captured: {clean_info[:50]}...")

                # 5. Close Modal & Reset
                # Pressing 'Escape' is the safest way to close most React modals
                await page.keyboard.press("Escape")
                await asyncio.sleep(1.5) 

            except Exception as e:
                print(f"   ⚠️ Error on item {i}: Skipping...")
                await page.goto(url, wait_until="networkidle")
                await asyncio.sleep(2)

        # 6. Save as JSON (Much better for your LangGraph Agent)
        with open("meat_catalog.json", "w", encoding="utf-8") as f:
            json.dump(scraped_results, f, indent=4)
            
        print(f"\n🔥 Done! Saved {len(scraped_results)} items to meat_catalog.json")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())