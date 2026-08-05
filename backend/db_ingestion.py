import os
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
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "qa_agent_db"),
        user=os.environ.get("DB_USER", "qa_admin"),
        password=os.environ.get("DB_PASS", "qa_password")
    )

def get_auth_db_connection():
    """Establish a connection to the Auth PostgreSQL database (Port 8124)."""
    return psycopg2.connect(
        host=os.environ.get("AUTH_DB_HOST", "localhost"),
        port=os.environ.get("AUTH_DB_PORT", "8124"),
        dbname=os.environ.get("AUTH_DB_NAME", "postgres"),
        user=os.environ.get("AUTH_DB_USER", "postgres"),
        password=os.environ.get("AUTH_DB_PASS", "postgres")
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

# ===================================================================
# Projects CRUD — ตรงกับ schema:
#   projects(project_id SERIAL PK, project_code VARCHAR UNIQUE NOT NULL,
#            project_name VARCHAR NOT NULL, description TEXT,
#            status VARCHAR DEFAULT 'Active', created_at TIMESTAMP)
# ===================================================================

def get_projects():
    """Fetch all projects from the database."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_id, project_name, project_code, description, status, created_at "
            "FROM projects ORDER BY project_id DESC;"
        )
        projects = [
            {
                "id": str(row[0]) if row[0] else None,
                "name": row[1],
                "project_code": row[2],
                "description": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None
            }
            for row in cursor.fetchall()
        ]
        return projects
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def add_project(name: str = None, project_code: str = None, project_name: str = None,
                description: str = '', status: str = 'Active'):
    """Add a new project to the database."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        p_name = project_name or name
        if not p_name:
            raise Exception("กรุณาระบุชื่อโครงการ")

        import uuid
        p_code = project_code if project_code else f"PRJ-{uuid.uuid4().hex[:6].upper()}"

        logger.info(f"Inserting project: code={p_code}, name={p_name}, status={status}")
        cursor.execute(
            "INSERT INTO projects (project_code, project_name, description, status) "
            "VALUES (%s, %s, %s, %s) RETURNING project_id;",
            (p_code, p_name, description, status)
        )
        project_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Project created successfully: id={project_id}")
        return {
            "id": project_id,
            "name": p_name,
            "project_code": p_code,
            "description": description,
            "status": status
        }
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise Exception(f"Project Code '{project_code}' ซ้ำกับโครงการที่มีอยู่แล้ว")
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error adding project: {e}", exc_info=True)
        raise
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_project(project_id: str):
    """Delete a project and all its associated documents (CASCADE)."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE project_id = %s::uuid;", (project_id,))
        if cursor.rowcount == 0:
            raise Exception("ไม่พบโครงการที่ต้องการลบ")
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error deleting project: {e}", exc_info=True)
        raise
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ===================================================================
# Document Ingestion — ตรงกับ schema:
#   documents(doc_id SERIAL PK, project_id INT FK, doc_category VARCHAR NOT NULL,
#             doc_type VARCHAR NOT NULL, original_filename VARCHAR,
#             full_markdown_content TEXT, is_golden_data BOOL, file_hash VARCHAR,
#             version INT, status VARCHAR, created_at TIMESTAMP)
#   document_chunks(chunk_id SERIAL PK, doc_id INT FK,
#                   chunk_text TEXT NOT NULL, embedding vector(384),
#                   created_at TIMESTAMP)
# ===================================================================

def ingest_markdown_document(filename: str, markdown_text: str, project_id: int = None,
                              doc_category: str = 'OCR', doc_type: str = 'PDF',
                              is_golden_data: bool = False):
    """
    Ingests a markdown document into the pgvector database.
    1. Chunks the text
    2. Embeds the chunks using SentenceTransformers
    3. Inserts document and chunks into DB
    """
    if not markdown_text.strip():
        logger.warning("Empty markdown text provided. Skipping ingestion.")
        return False

    conn = None
    cursor = None
    try:
        logger.info(f"Starting database ingestion for document: {filename}")

        # 1. Chunking
        chunks = chunk_markdown(markdown_text)
        logger.info(f"Generated {len(chunks)} chunks.")

        # 2. Embedding
        embedder = get_model()
        embeddings = embedder.encode(chunks)

        # 3. Compute file hash for duplicate detection
        file_hash = hashlib.sha256(markdown_text.encode('utf-8')).hexdigest()

        # 4. DB Insertion
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate by file_hash
        cursor.execute("SELECT doc_id FROM documents WHERE file_hash = %s AND status = 'Active';", (file_hash,))
        existing = cursor.fetchone()
        if existing:
            logger.info(f"Document with same hash already exists (doc_id={existing[0]}). Skipping ingestion.")
            return True, "already ingested"

        if project_id is None:
            raise ValueError("project_id is required and must be a valid UUID")
        effective_project_id = project_id

        cursor.execute(
            "INSERT INTO documents (project_id, doc_category, doc_type, original_filename, "
            "full_markdown_content, file_hash, is_golden_data) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING doc_id;",
            (effective_project_id, doc_category, doc_type, filename, markdown_text, file_hash, is_golden_data)
        )
        document_id = cursor.fetchone()[0]

        # Insert chunks
        for chunk_text, emb in zip(chunks, embeddings):
            cursor.execute(
                "INSERT INTO document_chunks (doc_id, chunk_text, embedding) VALUES (%s, %s, %s);",
                (document_id, chunk_text, emb.tolist())
            )

        conn.commit()
        logger.info(f"Successfully ingested '{filename}' (doc_id: {document_id}) with {len(chunks)} chunks.")
        return True, str(document_id)

    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def update_markdown_document(doc_id: str, new_markdown_text: str):
    """
    Updates the markdown content of an existing document, and re-generates its chunks and embeddings.
    """
    if not new_markdown_text.strip():
        return False, "Empty markdown text provided."

    conn = None
    cursor = None
    try:
        # 1. Chunking
        chunks = chunk_markdown(new_markdown_text)
        
        # 2. Embedding
        embedder = get_model()
        embeddings = embedder.encode(chunks)
        
        # 3. Compute file hash
        file_hash = hashlib.sha256(new_markdown_text.encode('utf-8')).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update document
        cursor.execute(
            "UPDATE documents SET full_markdown_content = %s, file_hash = %s WHERE doc_id = %s",
            (new_markdown_text, file_hash, doc_id)
        )
        if cursor.rowcount == 0:
            raise Exception("Document not found.")

        # Delete old chunks
        cursor.execute("DELETE FROM document_chunks WHERE doc_id = %s", (doc_id,))

        # Insert new chunks
        for chunk_text, emb in zip(chunks, embeddings):
            cursor.execute(
                "INSERT INTO document_chunks (doc_id, chunk_text, embedding) VALUES (%s, %s, %s);",
                (doc_id, chunk_text, emb.tolist())
            )

        conn.commit()
        logger.info(f"Successfully updated document '{doc_id}' with {len(chunks)} new chunks.")
        return True, "Update successful"

    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error updating document {doc_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def search_knowledge_base(query_text: str, doc_type: str = None, top_k: int = 5, project_id: str = None):
    """
    Searches the knowledge base for chunks most similar to the query text.
    Uses pgvector's <-> operator (L2 distance) or <=> (Cosine distance).
    Optionally filters by doc_type (e.g. 'Requirement', 'Design') and project_id.
    """
    if not query_text.strip():
        return []

    conn = None
    cursor = None
    try:
        embedder = get_model()
        # Encode query to vector
        query_embedding = embedder.encode([query_text])[0]
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query
        # Using cosine distance <=> for sentence embeddings is usually preferred
        sql = """
            SELECT 
                dc.chunk_text, 
                d.doc_category, 
                d.original_filename,
                1 - (dc.embedding <=> %s::vector) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.doc_id = d.doc_id
            WHERE (d.status = 'Active' OR d.status IS NULL)
        """
        params = [query_embedding.tolist()]

        if project_id:
            sql += " AND d.project_id = %s::uuid"
            params.append(project_id)

        if doc_type:
            if isinstance(doc_type, list) and len(doc_type) > 0:
                # exclude 'Other' or handle it if needed
                valid_types = [dt.upper() for dt in doc_type if dt.upper() != 'OTHER']
                if valid_types:
                    placeholders = ', '.join(['%s'] * len(valid_types))
                    sql += f" AND UPPER(TRIM(d.doc_category)) IN ({placeholders})"
                    params.extend(valid_types)
            elif isinstance(doc_type, str) and doc_type.upper() != "OTHER":
                sql += " AND UPPER(TRIM(d.doc_category)) = %s"
                params.append(doc_type.upper())

        sql += " ORDER BY dc.embedding <=> %s::vector LIMIT %s;"
        params.extend([query_embedding.tolist(), top_k])

        cursor.execute(sql, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "chunk_text": row[0],
                "doc_type": row[1],
                "filename": row[2],
                "similarity": float(row[3])
            })
            
        return results

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_qa_transactions():
    """Initializes the qa_transactions table in the database."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_transactions (
                transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255),
                group_type VARCHAR(100),
                filename VARCHAR(255) NOT NULL,
                doc_type VARCHAR(255),
                extracted_text TEXT,
                qa_report TEXT,
                total_pages INTEGER,
                email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN group_name VARCHAR(255);")
        except Exception:
            pass 
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN group_type VARCHAR(100);")
        except Exception:
            pass 
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN total_pages INTEGER;")
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN email VARCHAR(255);")
        except Exception:
            pass
            
        logger.info("Checked/Created qa_transactions table.")
    except Exception as e:
        logger.error(f"Error initializing qa_transactions table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_qa_transaction(project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages=None, email=None):
    """Saves a QA consult transaction to the database."""
    conn = None
    cursor = None
    try:
        if not project_id:
            logger.warning("No project_id provided, skipping saving QA transaction.")
            return False
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING transaction_id
        """, (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email))
        transaction_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Saved QA transaction for {filename} in project {project_id}.")
        return str(transaction_id)
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving QA transaction: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_latest_qa_transaction(project_id, filename):
    """Retrieves the latest QA transaction for a given project and filename."""
    conn = None
    cursor = None
    try:
        if not project_id:
            return None
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT extracted_text, qa_report, created_at
            FROM qa_transactions
            WHERE project_id = %s::uuid AND filename = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (project_id, filename))
        row = cursor.fetchone()
        if row:
            return {
                'extracted_text': row[0],
                'qa_report': row[1],
                'created_at': row[2].isoformat() if row[2] else None
            }
        return None
    except Exception as e:
        logger.error(f"Error retrieving latest QA transaction: {e}", exc_info=True)
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_qa_groups_table():
    """Initializes the qa_groups table in the database."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_groups (
                group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255) NOT NULL,
                group_type VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, group_name)
            );
        """)
        logger.info("Checked/Created qa_groups table.")
    except Exception as e:
        logger.error(f"Error initializing qa_groups table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_qa_group(project_id, group_name, group_type):
    """Saves a QA group to the database."""
    conn = None
    cursor = None
    try:
        if not project_id or not group_name:
            return False, "project_id and group_name are required"
            
        conn = get_db_connection()
        cursor = conn.cursor()
        # Insert or ignore (using ON CONFLICT DO NOTHING)
        cursor.execute("""
            INSERT INTO qa_groups (project_id, group_name, group_type)
            VALUES (%s::uuid, %s, %s)
            ON CONFLICT (project_id, group_name) DO NOTHING
            RETURNING group_id
        """, (project_id, group_name, group_type))
        conn.commit()
        return True, "Group saved"
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving QA group: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_qa_groups(project_id=None):
    """Retrieves all QA groups, optionally filtered by project."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT g.group_id, g.project_id, g.group_name, g.group_type, g.created_at, p.project_code
            FROM qa_groups g
            LEFT JOIN projects p ON g.project_id = p.project_id
        """
        params = []
        if project_id:
            sql += " WHERE g.project_id = %s::uuid"
            params.append(project_id)
            
        sql += " ORDER BY g.created_at DESC"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        groups = []
        for r in rows:
            groups.append({
                'group_id': str(r[0]),
                'project_id': str(r[1]),
                'group_name': r[2],
                'group_type': r[3],
                'created_at': r[4].isoformat() if r[4] else None,
                'project_code': r[5] or 'Unknown'
            })
        return groups
    except Exception as e:
        logger.error(f"Error retrieving QA groups: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
