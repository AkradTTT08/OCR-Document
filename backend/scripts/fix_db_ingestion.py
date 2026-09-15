import os

def fix_db():
    with open('db_ingestion.py', 'r', encoding='utf-8') as f:
        content = f.read()

    prefix = """import os
import hashlib
import psycopg2
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# We initialize the model at the module level so it loads only once.
# "paraphrase-multilingual-MiniLM-L12-v2" is a lightweight model suitable for multi-lingual text (Thai/English).
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
model = None

def get_model():
    global model
    if model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)
    return model

def get_db_connection():
    \"\"\"Establish a connection to the PostgreSQL database.\"\"\"
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "qa_agent_db"),
        user=os.environ.get("DB_USER", "qa_admin"),
        password=os.environ.get("DB_PASS", "qa_password")
    )

def get_auth_db_connection():
    \"\"\"Establish a connection to the Auth PostgreSQL database (Port 8124).\"\"\"
    return psycopg2.connect(
        host=os.environ.get("AUTH_DB_HOST", "localhost"),
        port=os.environ.get("AUTH_DB_PORT", "8124"),
        dbname=os.environ.get("AUTH_DB_NAME", "postgres"),
        user=os.environ.get("AUTH_DB_USER", "postgres"),
        password=os.environ.get("AUTH_DB_PASS", "postgres")
    )

def get_ocr_db_connection():
    \"\"\"Establish a connection to the OCR PostgreSQL database.\"\"\"
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("OCR_DB_NAME", "qa_agent_db"),
        user=os.environ.get("DB_USER", "qa_admin"),
        password=os.environ.get("DB_PASS", "qa_password")
    )

def chunk_markdown(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    \"\"\"
    Splits markdown text into smaller chunks based on paragraphs or line breaks.
    \"\"\"
    paragraphs = text.split('\\n\\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < chunk_size:
            current_chunk += p + "\\n\\n"
        else:
            if current_chunk:
"""

    idx = content.find("                chunks.append(current_chunk.strip())")
    if idx == -1:
        print("Could not find the target string. The file might be corrupted differently.")
        return
        
    new_content = prefix + content[idx:]

    methods_to_replace = [
        "def init_api_usage_logs()",
        "def log_api_usage(",
        "def get_api_usage_stats(",
        "def init_billing_credit()",
        "def get_billing_credit()",
        "def update_billing_credit(",
        "def init_ocr_history()",
        "def save_ocr_history(",
        "def get_ocr_history()",
        "def delete_ocr_history("
    ]

    lines = new_content.split("\n")
    in_target_method = False

    for i in range(len(lines)):
        line = lines[i]
        if line.startswith("def "):
            in_target_method = False
            for m in methods_to_replace:
                if line.startswith(m):
                    in_target_method = True
                    break
                    
        if in_target_method and "conn = get_db_connection()" in line:
            lines[i] = line.replace("conn = get_db_connection()", "conn = get_ocr_db_connection()")

    with open('db_ingestion.py', 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
        
    print("db_ingestion.py has been successfully fixed and updated!")

if __name__ == "__main__":
    fix_db()
