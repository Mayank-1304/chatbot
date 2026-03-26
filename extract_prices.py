import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        page = await browser.new_page()
        
        print("🚀 Opening The Meat Story...")
        url = "https://www.themeatstory.com/shop"
        await page.goto(url, wait_until="networkidle")
        
        scraped_results = {}
        index = 0

        while True:
            # 1. CRITICAL: Wait for buttons to exist before checking the list
            # This prevents the script from quitting too early
            try:
                await page.wait_for_selector("button:has-text('Buy Now')", timeout=10000)
                buttons = await page.query_selector_all("button:has-text('Buy Now')")
            except Exception:
                print("🏁 No more buttons found or page failed to load.")
                break
            
            if index >= len(buttons):
                print(f"🏁 Finished all {len(buttons)} visible products.")
                break
                
            target_btn = buttons[index]

            try:
                # Scroll and grab the name
                await target_btn.scroll_into_view_if_needed()
                product_name = await page.evaluate(
                    "(btn) => btn.closest('div').parentElement.querySelector('h2').innerText", 
                    target_btn
                )

                if product_name in scraped_results:
                    index += 1
                    continue

                print(f"[{index+1}/{len(buttons)}] Extracting: {product_name}...")
                
                # 2. Enter Product View
                await target_btn.click(force=True)
                
                # 3. Wait for Price (The symbol '₹' is our anchor)
                price_xpath = "//*[contains(text(), '₹')]"
                await page.wait_for_selector(price_xpath, timeout=8000)
                
                # Grab the price text
                price_info = await page.locator(price_xpath).first.inner_text()
                scraped_results[product_name] = price_info
                print(f"   ✅ Price: {price_info}")

                # 4. Navigate Back
                # We use goto instead of back() if the site state gets messy
                await page.go_back(wait_until="networkidle")
                
                # Wait for the grid to re-appear so the next 'index' is valid
                await asyncio.sleep(2) 

            except Exception as e:
                print(f"   ⚠️ Error on item {index}: Refreshing shop...")
                await page.goto(url, wait_until="networkidle")
                await asyncio.sleep(3)

            index += 1

        # 5. Save final results
        with open("full_meat_knowledge.txt", "w", encoding="utf-8") as f:
            for name, price in scraped_results.items():
                f.write(f"Item: {name} | Price: {price}\n")
            
        print(f"\n🔥 Success! Saved {len(scraped_results)} items to full_meat_knowledge.txt")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())