from .state import DocumentState, QAState, QASecurityState
from .agents import SpellCheckerAgent, FormatCheckerAgent, FinalReviewerAgent

def run_document_pipeline(text: str) -> DocumentState:
    """
    Executes the deterministic Sequential Pipeline for document checking.
    """
    state = DocumentState(original_text=text)
    
    # Node 1: Spell Check
    state = SpellCheckerAgent.run(state)
    
    # Node 2: Format Check
    state = FormatCheckerAgent.run(state)
    
    # Node 3: Final Review (Supervisor/Reviewer)
    state = FinalReviewerAgent.run(state)
    
    state.status = "completed"
    return state

def run_qa_consult(state: QAState) -> QAState:
    """Executes the QA Consult Agent."""
    from .agents import QAConsultAgent
    return QAConsultAgent.run(state)

def run_qa_research(state: QAState) -> QAState:
    """Executes the QA Research Agent."""
    from .agents import QAResearchAgent
    return QAResearchAgent.run(state)

def run_qa_security(state: QASecurityState) -> QASecurityState:
    """Executes the QA Security Agent."""
    from .agents import QASecurityAgent
    return QASecurityAgent.run(state)
