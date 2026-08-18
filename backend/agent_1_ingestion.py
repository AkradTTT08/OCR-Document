import os
import json
import logging
import google.generativeai as genai
from db_ingestion import get_db_connection

logger = logging.getLogger(__name__)

def init_requirements_table():
    """Initializes the structured_requirements table in AIAgentQA."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS structured_requirements (
                req_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                doc_id INTEGER REFERENCES documents(doc_id) ON DELETE CASCADE,
                req_code VARCHAR(100),
                title VARCHAR(255),
                description TEXT,
                actors VARCHAR(255),
                preconditions TEXT,
                steps JSONB,
                expected_results JSONB,
                ui_elements JSONB,
                api_endpoints JSONB,
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Checked/Created structured_requirements table.")
    except Exception as e:
        logger.error(f"Error initializing structured_requirements table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def extract_requirements_from_text(text: str, project_id: str, doc_id: int):
    """
    Uses Gemini to extract structured requirements from raw document text.
    """
    if not text or not text.strip():
        return False, "Empty text provided"

    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    
    # We use Gemini 3.1 Pro (simulated via gemini-2.5-pro or gemini-2.5-flash as default)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if "flash" in model_name: 
        model_name = "gemini-2.5-pro" # For complex structured extraction, Pro is better

    model = genai.GenerativeModel(model_name)
    
    prompt = f"""
    Analyze the following project requirement document and extract ALL distinct business requirements, user stories, or test scenarios.
    
    For EACH requirement, output a JSON object matching this schema:
    {{
        "req_code": "REQ-001 (or auto-generate one)",
        "title": "Short descriptive title",
        "description": "Full description of what this requirement entails",
        "actors": "Who interacts with this? (e.g. User, Admin, System)",
        "preconditions": "What must be true before this starts?",
        "steps": ["Step 1", "Step 2", ...],
        "expected_results": ["Result 1", "Result 2", ...],
        "ui_elements": ["List of buttons, inputs, modals mentioned, e.g., 'Submit Button', 'Email Field'"],
        "api_endpoints": ["List of any API paths mentioned, e.g., 'POST /api/login'"]
    }}
    
    Return a JSON array containing these objects. DO NOT include markdown blocks like ```json, just output the raw JSON array.
    
    Document Text:
    {text[:30000]} # Limit to 30k chars for context window
    """

    try:
        response = model.generate_content(prompt)
        raw_json = response.text.strip()
        
        # Clean up markdown if AI added it
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
            
        requirements = json.loads(raw_json)
        
        # Save to DB
        conn = get_db_connection()
        cursor = conn.cursor()
        
        saved_ids = []
        for req in requirements:
            cursor.execute("""
                INSERT INTO structured_requirements 
                (project_id, doc_id, req_code, title, description, actors, preconditions, steps, expected_results, ui_elements, api_endpoints)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
                RETURNING req_id
            """, (
                project_id, 
                doc_id,
                req.get('req_code', 'REQ-AUTO'),
                req.get('title', ''),
                req.get('description', ''),
                req.get('actors', ''),
                req.get('preconditions', ''),
                json.dumps(req.get('steps', [])),
                json.dumps(req.get('expected_results', [])),
                json.dumps(req.get('ui_elements', [])),
                json.dumps(req.get('api_endpoints', []))
            ))
            saved_ids.append(str(cursor.fetchone()[0]))
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, f"Successfully extracted and saved {len(saved_ids)} requirements."
        
    except Exception as e:
        logger.error(f"Failed to extract requirements: {e}")
        return False, str(e)
