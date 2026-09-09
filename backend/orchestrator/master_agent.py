import os
import logging
from typing import List, Dict, Any, Optional
from google.genai import types
from ocr_engine import _get_gemini_client, get_all_api_keys

logger = logging.getLogger("master_agent")

def qa_security_scan(source_code: str, language: str = "auto", standard: str = "OWASP Top 10 (2021)") -> str:
    """
    Scans the provided source code or github URL for security vulnerabilities.
    Always pass the full source code or github url to this function.
    """
    logger.info(f"Tool called: qa_security_scan (lang={language}, std={standard})")
    
    if source_code.startswith("http://") or source_code.startswith("https://"):
        try:
            from app import _fetch_github_code
            source_code = _fetch_github_code(source_code)
            language = "auto (GitHub Repo)"
        except Exception as e:
            return f"Failed to fetch GitHub repo: {str(e)}"
            
    from orchestrator.state import QASecurityState
    from orchestrator.pipeline import run_qa_security
    state = QASecurityState(source_code=source_code, language=language, standard=standard)
    res = run_qa_security(state)
    return res.report or res.error or "No report generated."

def qa_consult(project_id: str, instruction: str) -> str:
    """
    Consults the QA system to review documents or generate QA insights for a specific project.
    project_id must be an existing project code or id.
    """
    logger.info(f"Tool called: qa_consult (project_id={project_id})")
    from orchestrator.state import QAState
    from orchestrator.pipeline import run_qa_consult
    state = QAState(project_id=project_id, instruction=instruction)
    res = run_qa_consult(state)
    return res.report or res.error or "No report generated."

def qa_research(project_id: str, question: str) -> str:
    """
    Asks the QA Research assistant a question about a specific project to retrieve knowledge or summarize documents.
    project_id must be an existing project code or id.
    """
    logger.info(f"Tool called: qa_research (project_id={project_id})")
    from orchestrator.state import QAState
    from orchestrator.pipeline import run_qa_research
    state = QAState(project_id=project_id, instruction=question)
    res = run_qa_research(state)
    return res.report or res.error or "No report generated."

def get_projects() -> str:
    """
    Retrieves the list of all available projects and their project_ids.
    Use this if you don't know the project_id.
    """
    from db_ingestion import get_all_projects
    projects = get_all_projects()
    if not projects:
        return "No projects found."
    lines = [f"- {p['project_code']}: {p['name']} (ID: {p['id']})" for p in projects]
    return "\n".join(lines)


class MasterAgent:
    @staticmethod
    def run(chat_history: List[Dict[str, str]]) -> str:
        """
        Runs the Master Agent using the Chats feature of google.genai
        which can automatically handle function calling loops!
        """
        logger.info("Running MasterAgent...")
        
        keys = get_all_api_keys()
        if not keys:
            return "Error: No API keys available."
            
        client = _get_gemini_client(0)
        gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3.1-pro')
        
        system_instruction = """You are the Supreme QA Master Agent orchestrating a comprehensive Quality Assurance system.
Your goal is to help the user by routing their requests to the appropriate specialized QA Agents (Tools).
Available Tools:
1. qa_security_scan: Analyzes source code or github URLs for vulnerabilities.
2. qa_consult: Reviews documents or generates QA tests/guidelines for a specific project.
3. qa_research: Answers questions about a project based on its documents.
4. get_projects: Lists all available projects and their IDs.

Always try to use a tool if the user asks for something that falls into these categories.
If the user asks for a project-specific task but doesn't specify the project ID, ask them or use get_projects() to find it.
If the tool returns a long report, summarize it or present it beautifully to the user.
Always respond in Thai."""

        tools = [qa_security_scan, qa_consult, qa_research, get_projects]
        
        try:
            # We use client.chats.create to handle automatic function calling
            chat = client.chats.create(
                model=gemini_model,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
                    tools=tools
                )
            )
            
            # Replay history into the chat object? 
            # The SDK's chat object doesn't easily accept history initialization with automatic tool handling unless we construct it.
            # Instead, we will construct the contents array and use generate_content manually, OR we can just pass the history as strings.
            # Actually, `client.chats.create(history=...)` is supported in some versions.
            # Let's do manual loop.
            contents = []
            for msg in chat_history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
            
            # Pop the last message to be the active prompt
            active_prompt = contents.pop() if contents else types.Content(role="user", parts=[types.Part.from_text(text="Hello")])
            
            response = client.models.generate_content(
                model=gemini_model,
                contents=contents + [active_prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.4,
                    tools=tools
                )
            )
            
            # Manual function calling loop (simplified)
            MAX_LOOPS = 3
            loops = 0
            while response.function_calls and loops < MAX_LOOPS:
                loops += 1
                contents.append(response.candidates[0].content)
                function_responses = []
                for call in response.function_calls:
                    logger.info(f"MasterAgent invoking {call.name}")
                    result = "Unknown function."
                    if call.name == "qa_security_scan":
                        result = qa_security_scan(**call.args)
                    elif call.name == "qa_consult":
                        result = qa_consult(**call.args)
                    elif call.name == "qa_research":
                        result = qa_research(**call.args)
                    elif call.name == "get_projects":
                        result = get_projects()
                        
                    function_responses.append(types.Part.from_function_response(
                        name=call.name,
                        response={"result": result}
                    ))
                
                contents.append(types.Content(role="user", parts=function_responses))
                response = client.models.generate_content(
                    model=gemini_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.4,
                        tools=tools
                    )
                )
                
            return response.text
            
        except Exception as e:
            logger.error(f"MasterAgent error: {e}")
            return f"เกิดข้อผิดพลาดในการทำงานของ Master Agent: {str(e)}"
