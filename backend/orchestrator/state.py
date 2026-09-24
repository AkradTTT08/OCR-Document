from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class DocumentState(BaseModel):
    """
    Shared State / Context for the Multi-Agent Document Checking Pipeline
    """
    original_text: str
    spell_errors: List[Dict[str, Any]] = Field(default_factory=list)
    format_errors: List[Dict[str, Any]] = Field(default_factory=list)
    tokens: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    final_review_summary: Optional[str] = None
    corrected_text: Optional[str] = None
    iteration_count: int = 0
    status: str = "pending" # pending, spellcheck, formatcheck, review, completed, failed

class QAState(BaseModel):
    """
    Shared State / Context for QA Consult and QA Research Agents
    """
    project_id: str
    original_text: str = ""
    instruction: str = ""
    kb_context: str = ""
    prev_report_context: str = ""
    skill_instructions: str = ""
    doc_type: str = "general"
    project_name: str = "Unknown"
    project_code: str = ""
    
    # Execution details
    report: Optional[str] = None
    final_report: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.report and not self.final_report:
            self.final_report = self.report
        elif self.final_report and not self.report:
            self.report = self.final_report

class QASecurityState(BaseModel):
    """
    Shared State for QA Security Agent (Code Scanning)
    """
    source_code: str
    language: str = "auto"
    standard: str = "OWASP Top 10 (2021)"
    report: Optional[str] = None
    vulnerability_count: int = 0
    status: str = "pending"
    error: Optional[str] = None
