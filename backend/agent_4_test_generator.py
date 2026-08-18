import json
import logging
from db_ingestion import get_db_connection
import google.generativeai as genai
import os
from dotenv import load_dotenv
import uuid

load_dotenv()
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_playwright_script(project_id: str, gap_analysis_data: dict, web_state_file: str):
    """
    Agent 4: Test Generator Agent
    Takes Requirements, Gap Analysis, and Web State to generate a Playwright TS script in POM pattern.
    """
    try:
        # 1. Fetch Requirements
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
        """, (project_id,))
        
        reqs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        formatted_reqs = []
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "steps": req[3],
                "expected_results": req[4]
            })
            
        # 2. Read Web State
        web_state = {}
        if os.path.exists(web_state_file):
            with open(web_state_file, 'r', encoding='utf-8') as f:
                web_state = json.load(f)
                
        # 3. Use LLM to generate the code
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
You are an expert QA Automation Engineer.
Your task is to generate Playwright (TypeScript) Test Scripts using the Page Object Model (POM) design pattern.

### Project Requirements (What to test):
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}

### Web Interactive Elements (Available Selectors from live page):
{json.dumps(web_state.get('interactive_elements', []), ensure_ascii=False, indent=2)}

### Gap Analysis (Known issues to handle or ignore):
{json.dumps(gap_analysis_data.get('discrepancies', []), ensure_ascii=False, indent=2)}

Instructions:
1. For EACH requirement provided, create a separate Playwright test file.
2. Each test file should use the Page Object Model (POM) mapping the interactive elements.
3. Write test cases covering the steps in the Project Requirements.
4. Add assertions based on expected_results.

You MUST respond strictly in JSON format matching this schema:
{{
  "suites": [
    {{
      "menu_name": "Title of the requirement (e.g., Login Page)",
      "req_code": "The requirement code (e.g., REQ-001)",
      "test_count": "Number of test cases (it blocks) generated in this script",
      "file_name": "A suitable filename ending with .spec.ts (e.g., req001_login.spec.ts)",
      "code": "The complete TypeScript code for this test file"
    }}
  ]
}}
"""
        # Call Gemini (we might need to increase timeout or use a model with larger output)
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        
        # Clean up markdown if model still included it
        if text_response.startswith('```json'):
            text_response = text_response.strip('```json').strip('```').strip()
            
        result_data = json.loads(text_response)
        
        # Save generated codes to a project-specific folder
        project_tests_dir = os.path.join(os.getcwd(), "tests", project_id)
        os.makedirs(project_tests_dir, exist_ok=True)
        
        saved_suites = []
        for suite in result_data.get('suites', []):
            file_name = suite.get('file_name', f"{uuid.uuid4().hex[:8]}.spec.ts")
            file_path = os.path.join(project_tests_dir, file_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(suite.get('code', ''))
            
            # Keep track of saved path relative to tests directory
            suite['saved_path'] = f"{project_id}/{file_name}"
            saved_suites.append(suite)
            
        return True, {
            "suites": saved_suites,
            "project_id": project_id,
            "message": "Playwright scripts generated successfully."
        }
        
    except Exception as e:
        logger.error(f"Error in Agent 4 Test Generator: {e}", exc_info=True)
        return False, str(e)
