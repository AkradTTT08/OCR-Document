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

        # 3. Optional: Fetch QA Analysis Diagram / Flow Data if available
        diagram_context = ""
        try:
            from agent_7_flow_analyzer import get_project_flow_analysis
            flow_analysis = get_project_flow_analysis(project_id)
            if flow_analysis:
                diagram_parts = []
                if flow_analysis.get("sitemap"):
                    diagram_parts.append(f"- **Sitemap & Menu Structure:**\n{json.dumps(flow_analysis['sitemap'], ensure_ascii=False, indent=2)}")
                if flow_analysis.get("system_flowchart") or flow_analysis.get("activity_diagram"):
                    fc = flow_analysis.get("system_flowchart") or flow_analysis.get("activity_diagram")
                    diagram_parts.append(f"- **System Flowchart & Activity Decision Flow (Mermaid):**\n{fc}")
                if flow_analysis.get("usecase_diagram"):
                    diagram_parts.append(f"- **Use Case Architecture (Mermaid):**\n{flow_analysis['usecase_diagram']}")
                if flow_analysis.get("sequence_diagram"):
                    diagram_parts.append(f"- **Sequence Flow (Mermaid):**\n{flow_analysis['sequence_diagram']}")
                if flow_analysis.get("screen_mockups"):
                    screens = [{"screen_name": s.get("screen_name"), "route": s.get("route"), "key_elements": s.get("key_elements", [])} for s in flow_analysis["screen_mockups"] if isinstance(s, dict)]
                    if screens:
                        diagram_parts.append(f"- **Screen Mockups & Expected Components:**\n{json.dumps(screens, ensure_ascii=False, indent=2)}")
                
                if diagram_parts:
                    diagram_context = "\n\n### QA Analysis Diagram & Architecture Models (Domain Knowledge):\n" + "\n\n".join(diagram_parts)
                    logger.info(f"Incorporated QA Analysis Diagram into Alignment for project {project_id}")
        except Exception as diagram_err:
            logger.warning(f"Optional QA Analysis Diagram fetch skipped: {diagram_err}")
            
        # 4. Call Gemini to analyze gaps
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
You are an expert QA Automation Engineer and System Analyst.
Your task is to compare the 'Structured Requirements' and 'QA Analysis Architecture / Diagrams' (if provided) of a project with the 'Live Web State' captured by a web explorer agent.
Identify any discrepancies, missing elements, navigation breaks, or mismatches between what is required/modeled and what is actually present on the web page.

### Structured Requirements (Expected):
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}
{diagram_context}

### Live Web State (Actual):
{json.dumps(web_state, ensure_ascii=False, indent=2)}

Please provide a detailed Gap Analysis Report. Format your response strictly in JSON format as follows:
{{
    "analysis_summary": "Overall summary of the comparison",
    "matched_elements": [
        "List of UI elements or features that correctly match the requirements and flow models"
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
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_3_Alignment", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), response.usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 3: {log_err}")

        text_response = response.text
        
        # Clean up markdown JSON block if present
        if text_response.startswith('```json'):
            text_response = text_response.strip('```json').strip('```').strip()
            
        analysis_result = json.loads(text_response)
        
        return True, analysis_result
        
    except Exception as e:
        logger.error(f"Error in Agent 3 Alignment Analysis: {e}", exc_info=True)
        return False, str(e)
