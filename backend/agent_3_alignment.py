import json
import logging
from db_ingestion import get_db_connection
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def run_alignment_analysis(project_id: str, web_state_file: str):
    """
    Agent 3: Discrepancy & Alignment Agent
    Compares structured requirements with live web state to find gaps.
    """
    try:
        # 1. Get Requirements from DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results, ui_elements
            FROM structured_requirements
            WHERE project_id = %s::uuid
        """, (project_id,))
        
        reqs = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not reqs:
            return False, "No structured requirements found for this project. Please complete Phase 1 first."
            
        formatted_reqs = []
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "description": req[2],
                "steps": req[3],
                "expected_results": req[4],
                "ui_elements": req[5]
            })
            
        # 2. Read Web State
        if not os.path.exists(web_state_file):
            return False, f"Web state file {web_state_file} not found. Please run Phase 2 first."
            
        with open(web_state_file, 'r', encoding='utf-8') as f:
            web_state = json.load(f)
            
        # 3. Call Gemini to analyze gaps
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
You are an expert QA Automation Engineer and System Analyst.
Your task is to compare the 'Structured Requirements' of a project with the 'Live Web State' captured by a web explorer agent.
Identify any discrepancies, missing elements, or mismatches between what is required and what is actually present on the web page.

### Structured Requirements (Expected):
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}

### Live Web State (Actual):
{json.dumps(web_state, ensure_ascii=False, indent=2)}

Please provide a detailed Gap Analysis Report. Format your response strictly in JSON format as follows:
{{
    "analysis_summary": "Overall summary of the comparison",
    "matched_elements": [
        "List of UI elements or features that correctly match the requirements"
    ],
    "discrepancies": [
        {{
            "req_code": "Requirement code",
            "issue": "Description of the gap (e.g. 'Submit button missing on live web')",
            "severity": "High/Medium/Low"
        }}
    ],
    "recommendation": "Next steps for automation or development"
}}
"""
        response = model.generate_content(prompt)
        text_response = response.text
        
        # Clean up markdown JSON block if present
        if text_response.startswith('```json'):
            text_response = text_response.strip('```json').strip('```').strip()
            
        analysis_result = json.loads(text_response)
        
        return True, analysis_result
        
    except Exception as e:
        logger.error(f"Error in Agent 3 Alignment Analysis: {e}", exc_info=True)
        return False, str(e)
