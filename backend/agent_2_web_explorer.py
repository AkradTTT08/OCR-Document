import asyncio
import json
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

async def explore_and_capture(url: str, output_path: str = "web_state.json"):
    """
    Agent 2: Autonomous Web Exploration
    Navigates to the given URL, waits for the page to load, and extracts structural data.
    """
    logger.info(f"Agent 2 starting exploration of: {url}")
    try:
        async with async_playwright() as p:
            # Launch chromium (headless by default, but we can make it visible for debugging)
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            # Navigate to the URL
            logger.info("Navigating...")
            await page.goto(url, wait_until='networkidle')
            
            # Extract basic page info
            title = await page.title()
            
            # Extract all interactive elements (buttons, links, inputs)
            logger.info("Extracting Interactive Elements...")
            interactive_elements = await page.evaluate('''() => {
                const elements = [];
                const selector = 'button, a, input, select, textarea, [role="button"]';
                document.querySelectorAll(selector).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if(rect.width > 0 && rect.height > 0) { // Only visible elements
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText || el.value || el.placeholder || '',
                            id: el.id || null,
                            name: el.name || null,
                            type: el.type || null,
                            href: el.href || null,
                            className: el.className || null
                        });
                    }
                });
                return elements;
            }''')
            
            web_state = {
                "url": url,
                "title": title,
                "interactive_elements": interactive_elements
            }
            
            # Save to JSON file
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(web_state, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Web State successfully captured and saved to {output_path}")
            
            await browser.close()
            return True, web_state
            
    except Exception as e:
        logger.error(f"Agent 2 failed to explore {url}: {e}")
        return False, str(e)

if __name__ == "__main__":
    # Test script execution
    logging.basicConfig(level=logging.INFO)
    test_url = "https://example.com"
    asyncio.run(explore_and_capture(test_url, "test_output.json"))
