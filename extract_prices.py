import requests
import json
import time
import re
from playwright.sync_api import sync_playwright

def fetch_meat_catalog():
    print("Loading base data entirely from local meat_catalog.json...")
    try:
        with open('meat_catalog.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading local data: {e}. Please make sure 'meat_catalog.json' exists.")
        return None

def extract_offers_from_text(text):
    """Attempt to find offer texts in the product page using regex and keywords."""
    offers = []
    patterns = [
        r'\b\d+%\s*(?:OFF|off|Discount|discount)\b',
        r'(?i)\bbuy\s*\d+\s*get\s*\d+\b',
        r'(?i)flat\s*(?:rs\.?|₹|inr)\s*\d+\s*off',
        r'(?i)save\s*(?:rs\.?|₹|inr)?\s*\d+'
    ]
    for p in patterns:
        matches = re.findall(p, text)
        offers.extend(matches)
    
    for line in text.split('\n'):
        if 'offer' in line.lower() and len(line) < 100:
            if line.strip() not in offers:
                offers.append(line.strip())
                
    return " | ".join(list(set(offers))) if offers else None

def scrape_with_playwright():
    products_json = fetch_meat_catalog()
    if not products_json:
        print("Failed to get base API data. Exiting.")
        return
        
    products_list = products_json.get("data", [])
    
    # Create a dictionary for easy merging based on title
    catalog_map = {p['title'].strip().lower(): p for p in products_list if 'title' in p}

    print("Launching Playwright to scrape full page details from https://www.themeatstory.com/shop...")
    with sync_playwright() as p:
        # Run in headed mode so the user can visually see the scraping process
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto("https://www.themeatstory.com/shop", timeout=60000)
            page.wait_for_load_state("networkidle")
            time.sleep(5) 
        except Exception as e:
            print(f"Error loading main page: {e}")
            browser.close()
            return
            
        buy_buttons = page.locator("button.btn.bg-themecolor:has-text('Buy Now')")
        # Handle case variations
        if buy_buttons.count() == 0:
            buy_buttons = page.locator("button.btn:has-text('BUY NOW')")
        if buy_buttons.count() == 0:
            buy_buttons = page.locator("button:has-text('Buy')")
            
        count = buy_buttons.count()
        print(f"Found {count} 'Buy Now' buttons.")
        
        for i in range(count):
            try:
                # Wait for the grid to reload before continuing
                page.wait_for_timeout(3000)
                    
                # Re-locate buttons dynamically based on user's exact button snippet
                buttons = page.locator("button.btn.bg-themecolor:has-text('Buy Now')")
                if buttons.count() == 0:
                    buttons = page.locator("button.btn:has-text('BUY NOW')")
                if buttons.count() == 0:
                    buttons = page.locator("button:has-text('Buy')")
                    
                if i >= buttons.count():
                    print(f"  -> Index {i} exceeded button count {buttons.count()}. Attempting to recover by refreshing...")
                    page.goto("https://www.themeatstory.com/shop", timeout=30000)
                    page.wait_for_timeout(4000)
                    buttons = page.locator("button.btn.bg-themecolor:has-text('Buy Now')")
                    if buttons.count() == 0:
                        buttons = page.locator("button.btn:has-text('BUY NOW')")
                    if buttons.count() == 0:
                        buttons = page.locator("button:has-text('Buy')")
                    if i >= buttons.count():
                        break
                    
                btn = buttons.nth(i)
                btn.scroll_into_view_if_needed()
                time.sleep(1)
                btn.click()
                
                page.wait_for_timeout(2000)
                
                # We are now on the product detail page, get entire text
                page_text = page.locator("body").inner_text()
                
                # Match it with our API catalog
                matched_title = None
                for title in catalog_map.keys():
                    if title in page_text.lower():
                        matched_title = title
                        break
                        
                if matched_title:
                    offer_str = extract_offers_from_text(page_text)
                    if offer_str:
                        print(f"[{catalog_map[matched_title]['title']}] Extracted Offers: {offer_str}")
                        catalog_map[matched_title]["offers"] = offer_str
                    else:
                        print(f"[{catalog_map[matched_title]['title']}] Processed raw data (No specific offers).")
                        
                    # Save all text from the page per user request, removing noisy empty newlines
                    clean_text = " ".join([line.strip() for line in page_text.splitlines() if line.strip()])
                    catalog_map[matched_title]["scraped_page_text"] = clean_text
                else:
                    print(f"Item #{i} - Could not match page to API catalog.")
                
                # Click Go Back using the exact span class
                go_back_span = page.locator("span.leading-\\[0px\\].mt-\\[3px\\]:visible")
                if go_back_span.count() == 0:
                    go_back_span = page.locator("span:has-text('Go Back'):visible")
                    
                if go_back_span.count() > 0:
                    try:
                        go_back_span.first.click(timeout=5000)
                    except Exception:
                        # Fallback to forcing the click if Playwright thinks it's strictly not visible
                        go_back_span.first.click(timeout=5000, force=True)
                        
                    page.wait_for_timeout(1000)
                    # The user noted it sometimes requires 2 clicks
                    if go_back_span.is_visible():
                        print("  -> First click didn't navigate, clicking Go Back a second time...")
                        try:
                            go_back_span.first.click(timeout=5000)
                        except Exception:
                            go_back_span.first.click(timeout=5000, force=True)
                else:
                    page.go_back()
                    
                page.wait_for_timeout(2000)
                
            except Exception as e:
                print(f"Error processing item #{i}: {e}")
                try:
                    # Recover back to shop
                    page.goto("https://www.themeatstory.com/shop", timeout=30000)
                    page.wait_for_timeout(3000)
                except:
                    pass
                    
        browser.close()
        
    products_json["data"] = list(catalog_map.values())
    
    with open('meat_catalog.json', 'w', encoding='utf-8') as f:
        json.dump(products_json, f, indent=4)
        
    print(f"Successfully merged offers and saved to meat_catalog.json")

if __name__ == "__main__":
    scrape_with_playwright()