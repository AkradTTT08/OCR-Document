import asyncio
import json
import logging
import os
from playwright.async_api import async_playwright
from db_ingestion import get_db_connection

logger = logging.getLogger(__name__)

async def explore_and_capture(url: str, project_id: str = None, username: str = None, password: str = None, output_path: str = "web_state.json"):
    """
    Agent 2: Autonomous Web Exploration
    Navigates to URL, handles login if provided, crawls internal pages, 
    and uses Gemini to analyze the system based on Phase 1 requirements.
    """
    logger.info(f"Agent 2 starting exploration of: {url}")
    
    formatted_reqs = []
    if project_id:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT req_code, title, description
                FROM structured_requirements
                WHERE project_id = %s::uuid
            """, (project_id,))
            reqs = cursor.fetchall()
            cursor.close()
            conn.close()
            
            for req in reqs:
                formatted_reqs.append({
                    "req_code": req[0],
                    "title": req[1],
                    "description": req[2]
                })
        except Exception as e:
            logger.error(f"Failed to fetch requirements for project {project_id}: {e}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            logger.info("Navigating...")
            await page.goto(url, wait_until='networkidle')
            
            if username and password:
                logger.info("Attempting auto-login...")
                # Robust heuristic for login forms
                user_input = page.locator('input[type="text"], input[type="email"], input[name*="user"], input[name*="email"], input[id*="user"], input[id*="email"], input[placeholder*="user" i], input[placeholder*="email" i]').first
                pass_input = page.locator('input[type="password"], input[name*="pass"], input[id*="pass"], input[placeholder*="pass" i]').first
                
                if await user_input.is_visible() and await pass_input.is_visible():
                    await user_input.fill(username)
                    await pass_input.fill(password)
                    
                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Submit"), button[class*="login" i], button[class*="signin" i]').first
                    if await submit_btn.is_visible():
                        await submit_btn.click()
                        logger.info("Login submitted via button click.")
                    else:
                        await pass_input.press('Enter')
                        logger.info("Login submitted via Enter key.")
                        
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(3000) # Wait for potential redirects
                else:
                    logger.warning("Auto-login fields not found or not visible.")

            async def extract_state(curr_page):
                title = await curr_page.title()
                curr_url = curr_page.url
                elements = await curr_page.evaluate('''() => {
                    const elements = [];
                    const selector = 'button, a, input, select, textarea, [role="button"], [role="menuitem"], .menu-item, nav a, .sidebar a';
                    document.querySelectorAll(selector).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if(rect.width > 0 && rect.height > 0) { 
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
                return {"url": curr_url, "title": title, "elements": elements}

            logger.info("Extracting initial/post-login page state...")
            pages_state = []
            initial_state = await extract_state(page)
            pages_state.append(initial_state)

            # Extract internal navigation links
            links = []
            try:
                base_url_parts = page.url.split('/')
                base_url = '/'.join(base_url_parts[:3]) if len(base_url_parts) >= 3 else page.url
            except Exception:
                base_url = url
                
            for el in initial_state['elements']:
                if el['tag'] == 'a' and el['href']:
                    href = el['href']
                    if (href.startswith(base_url) or href.startswith('/')) and not href.startswith('javascript:'):
                        full_href = href if href.startswith('http') else base_url + href
                        if full_href not in links and full_href != page.url and not full_href.endswith('#'):
                            links.append(full_href)

            # Deep Crawl limited to top 3 links to save time
            MAX_PAGES = 3
            visited = 0
            for link in links:
                if visited >= MAX_PAGES: break
                try:
                    logger.info(f"Crawling internal menu link: {link}")
                    await page.goto(link, wait_until='networkidle')
                    await page.wait_for_timeout(1000)
                    state = await extract_state(page)
                    pages_state.append(state)
                    visited += 1
                except Exception as e:
                    logger.warning(f"Failed to crawl {link}: {e}")
            
            await browser.close()
            
            # Aggregate navigation text for AI Analysis
            nav_elements = []
            for p_state in pages_state:
                for e in p_state['elements']:
                    if e['tag'] in ['a', 'button']:
                        txt = (e['text'] or '').strip()
                        if txt and txt not in nav_elements:
                            nav_elements.append(txt)
            
            # AI Semantic Analysis
            analysis = None
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                try:
                    logger.info("Sending aggregated data to Gemini for Semantic Analysis...")
                    import google.generativeai as genai
                    genai.configure(api_key=api_key)
                    
                    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
                    if "flash" in model_name: 
                        model_name = "gemini-2.5-pro" # Pro is better for complex structured JSON analysis
                        
                    model = genai.GenerativeModel(model_name)
                    prompt = f"""
                    You are an expert QA Automation Engineer and System Analyst.
                    I have crawled a web application and extracted its main navigation menus and structural elements.
                    
                    Phase 1 Business Requirements (Context):
                    {json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}
                    
                    Crawled Pages: {[p['title'] for p in pages_state]}
                    Extracted Menu/Button Labels: {json.dumps(nav_elements[:150], ensure_ascii=False)}
                    
                    Analyze this system and provide a JSON response explaining the system's structure.
                    Format the JSON exactly like this:
                    {{
                        "system_overview": "Summary of what this system does based on the menus found",
                        "identified_menus": [
                            {{
                                "menu_name": "Menu Label",
                                "purpose": "What this menu/page is used for",
                                "related_req_code": "Requirement Code from Phase 1 if it matches, else null"
                            }}
                        ],
                        "analysis_summary": "Summary of how well the discovered UI matches Phase 1 requirements"
                    }}
                    Return ONLY valid JSON. Do not use Markdown formatting blocks like ```json.
                    """
                    resp = model.generate_content(prompt)
                    text_val = resp.text.strip()
                    if text_val.startswith('```json'):
                        text_val = text_val.strip('```json').strip('```').strip()
                    if text_val.startswith('```'):
                        text_val = text_val.strip('```').strip()
                        
                    analysis = json.loads(text_val)
                    logger.info("Gemini Semantic Analysis completed.")
                except Exception as e:
                    logger.error(f"Gemini analysis failed: {e}")
                    analysis = {"error": "Gemini analysis failed", "details": str(e)}

            total_elements = sum(len(p['elements']) for p in pages_state)
            
            web_state = {
                "url": url,
                "title": pages_state[0]['title'] if pages_state else "Unknown",
                "interactive_elements": pages_state[0]['elements'] if pages_state else [], # Keep initial for backward compatibility
                "total_crawled_pages": len(pages_state),
                "total_interactive_elements_across_pages": total_elements,
                "ai_analysis": analysis,
                "pages": pages_state
            }
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(web_state, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Web State successfully captured and saved to {output_path}")
            return True, web_state
            
    except Exception as e:
        logger.error(f"Agent 2 failed to explore {url}: {e}", exc_info=True)
        return False, str(e)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    test_url = "https://example.com"
    asyncio.run(explore_and_capture(test_url, None, None, None, "test_output.json"))
