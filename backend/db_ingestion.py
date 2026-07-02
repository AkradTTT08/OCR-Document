import os
import psycopg2
import logging
from sentence_transformers import SentenceTransformer
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
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)
    return model

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "qa_agent_db"),
        user=os.environ.get("DB_USER", "qa_admin"),
        password=os.environ.get("DB_PASS", "qa_password")
    )

def chunk_markdown(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """
    Splits markdown text into smaller chunks based on paragraphs or line breaks.
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < chunk_size:
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    # If no valid chunks (e.g. extremely long paragraph), fallback to raw slice
    if not chunks and text:
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size - overlap)]
        
    return chunks

def get_projects():
    """Fetch all projects from the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Assume projects table has 'id' and 'name' (or title)
        try:
            cursor.execute("SELECT id, name FROM projects ORDER BY id DESC;")
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            cursor.execute("SELECT id, title as name FROM projects ORDER BY id DESC;")
            
        projects = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return projects
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return []

def add_project(name: str):
    """Add a new project to the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO projects (name) VALUES (%s) RETURNING id;", (name,))
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            cursor.execute("INSERT INTO projects (title) VALUES (%s) RETURNING id;", (name,))
            
        project_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return {"id": project_id, "name": name}
    except Exception as e:
        logger.error(f"Error adding project: {e}")
        return None

def ingest_markdown_document(filename: str, markdown_text: str, project_id: int = None):

    """
    Ingests a markdown document into the pgvector database.
    1. Chunks the text
    2. Embeds the chunks using SentenceTransformers
    3. Inserts document and chunks into DB
    """
    if not markdown_text.strip():
        logger.warning("Empty markdown text provided. Skipping ingestion.")
        return False
        
    try:
        logger.info(f"Starting database ingestion for document: {filename}")
        
        # 1. Chunking
        chunks = chunk_markdown(markdown_text)
        logger.info(f"Generated {len(chunks)} chunks.")
        
        # 2. Embedding
        embedder = get_model()
        embeddings = embedder.encode(chunks)
        
        # 3. DB Insertion
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Attempt to insert document.
        # This uses try-except blocks to gracefully handle potential schema variations
        # (e.g. if the table expects 'title' instead of 'filename' or requires 'project_id').
        try:
            if project_id is not None:
                cursor.execute(
                    "INSERT INTO documents (project_id, filename, content) VALUES (%s, %s, %s) RETURNING id;",
                    (project_id, filename, markdown_text)
                )
            else:
                cursor.execute(
                    "INSERT INTO documents (filename, content) VALUES (%s, %s) RETURNING id;",
                    (filename, markdown_text)
                )
        except psycopg2.errors.UndefinedColumn:
            conn.rollback()
            try:
                if project_id is not None:
                    cursor.execute(
                        "INSERT INTO documents (project_id, title, content) VALUES (%s, %s, %s) RETURNING id;",
                        (project_id, filename, markdown_text)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO documents (title, content) VALUES (%s, %s) RETURNING id;",
                        (filename, markdown_text)
                    )
            except psycopg2.errors.NotNullViolation as e:
                conn.rollback()
                if 'project_id' in str(e):
                    cursor.execute(
                        "INSERT INTO documents (project_id, filename, content) VALUES (%s, %s, %s) RETURNING id;",
                        (project_id or 1, filename, markdown_text)
                    )
                else:
                    raise e
        except psycopg2.errors.NotNullViolation as e:
            conn.rollback()
            if 'project_id' in str(e):
                cursor.execute(
                    "INSERT INTO documents (project_id, filename, content) VALUES (%s, %s, %s) RETURNING id;",
                    (project_id or 1, filename, markdown_text)
                )
            else:
                raise e

            
        document_id = cursor.fetchone()[0]
        
        # Insert chunks to 'document_chunks' table
        for chunk, emb in zip(chunks, embeddings):
            cursor.execute(
                "INSERT INTO document_chunks (document_id, chunk_text, embedding) VALUES (%s, %s, %s);",
                (document_id, chunk, emb.tolist())
            )
            
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully ingested '{filename}' (ID: {document_id}) into database.")
        return True
        
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}")
        return False
