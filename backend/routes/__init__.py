"""Blueprint registration hub for Spectra QA backend."""
from routes.auth_users import bp as auth_users_bp
from routes.projects import bp as projects_bp
from routes.ocr_dictionary import bp as ocr_dictionary_bp
from routes.knowledge_base import bp as knowledge_base_bp
from routes.skills import bp as skills_bp
from routes.qa_consult import bp as qa_consult_bp
from routes.exit_criteria import bp as exit_criteria_bp
from routes.research_requirements import bp as research_requirements_bp
from routes.automation_agents import bp as automation_agents_bp
from routes.doc_creator_flow import bp as doc_creator_flow_bp
from routes.api_collections import bp as api_collections_bp
from routes.board_cards import bp as board_cards_bp

ALL_BLUEPRINTS = [
    auth_users_bp,
    projects_bp,
    ocr_dictionary_bp,
    knowledge_base_bp,
    skills_bp,
    qa_consult_bp,
    exit_criteria_bp,
    research_requirements_bp,
    automation_agents_bp,
    doc_creator_flow_bp,
    api_collections_bp,
    board_cards_bp,
]


def register_blueprints(app):
    """Register all domain blueprints on the Flask app in deterministic order."""
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
