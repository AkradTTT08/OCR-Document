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

def get_ocr_db_connection():
    """Establish a connection to the OCR PostgreSQL database."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("OCR_DB_NAME", "qa_agent_db"),
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
            "SELECT p.project_id, p.project_name, p.project_code, p.description, p.status, p.created_at, COUNT(d.doc_id) as doc_count "
            "FROM projects p LEFT JOIN documents d ON p.project_id = d.project_id GROUP BY p.project_id ORDER BY p.project_id DESC;"
        )
        projects = [
            {
                "id": str(row[0]) if row[0] else None,
                "name": row[1],
                "project_code": row[2],
                "description": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "doc_count": int(row[6]) if row[6] else 0
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

def update_project(project_id: str, name: str = None, project_name: str = None, project_code: str = None, description: str = None, status: str = None):
    """Update an existing project in the knowledge base."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use name if project_name is not provided
        p_name = project_name or name
        
        update_fields = []
        params = []
        if p_name is not None:
            update_fields.append("name = %s")
            update_fields.append("project_name = %s")
            params.extend([p_name, p_name])
        if project_code is not None:
            update_fields.append("project_code = %s")
            params.append(project_code)
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)
        if status is not None:
            update_fields.append("status = %s")
            params.append(status)
            
        if not update_fields:
            return None
            
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        params.append(project_id)
        
        query = f"UPDATE projects SET {', '.join(update_fields)} WHERE project_id = %s::uuid RETURNING project_id, project_code, name, description, status, created_at, updated_at;"
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            raise Exception("ไม่พบโครงการที่ต้องการอัปเดต")
            
        conn.commit()
        return {
            'id': str(row[0]),
            'project_id': str(row[0]),
            'project_code': row[1],
            'name': row[2],
            'project_name': row[2],
            'description': row[3],
            'status': row[4],
            'created_at': row[5].isoformat() if row[5] else None,
            'updated_at': row[6].isoformat() if row[6] else None
        }
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise Exception(f"Project Code '{project_code}' ซ้ำกับโครงการที่มีอยู่แล้ว")
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error updating project: {e}", exc_info=True)
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
        
        # --- Trigger Agent 1 Requirement Extraction in background ---
        try:
            import threading
            from agent_1_ingestion import extract_requirements_from_text
            def background_extraction(text, pid, did):
                try:
                    success, msg = extract_requirements_from_text(text, pid, did)
                    if not success:
                        logger.error(f"Background extraction failed for doc {did}: {msg}")
                    else:
                        logger.info(f"Background extraction complete for doc {did}: {msg}")
                except Exception as ex:
                    logger.error(f"Background extraction exception for doc {did}: {ex}")

            # Run in a background thread so it doesn't block the OCR/Upload response
            t = threading.Thread(target=background_extraction, args=(markdown_text, str(effective_project_id), document_id))
            t.daemon = True
            t.start()
        except Exception as e:
            logger.error(f"Failed to start Agent 1 extraction thread: {e}")
        # -----------------------------------------------------------

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
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN qa_findings JSONB;")
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN exit_criteria_eval JSONB;")
        except Exception:
            pass
            
        logger.info("Checked/Created qa_transactions table.")
    except Exception as e:
        logger.error(f"Error initializing qa_transactions table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_qa_transaction(project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages=None, email=None, qa_findings=None, exit_criteria_eval=None):
    """Saves a QA consult transaction to the database."""
    import json
    conn = None
    cursor = None
    try:
        if not project_id:
            logger.warning("No project_id provided, skipping saving QA transaction.")
            return False
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        qf_json = json.dumps(qa_findings) if qa_findings is not None else None
        ece_json = json.dumps(exit_criteria_eval) if exit_criteria_eval is not None else None
        
        cursor.execute("""
            INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qa_findings, exit_criteria_eval)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING transaction_id
        """, (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qf_json, ece_json))
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

def update_qa_transaction_results(transaction_id, qa_findings, exit_criteria_eval):
    """Updates the JSON columns of an existing QA transaction."""
    import json
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        qf_json = json.dumps(qa_findings) if qa_findings is not None else None
        ece_json = json.dumps(exit_criteria_eval) if exit_criteria_eval is not None else None
        
        cursor.execute("""
            UPDATE qa_transactions
            SET qa_findings = %s::jsonb, exit_criteria_eval = %s::jsonb
            WHERE transaction_id = %s::uuid
        """, (qf_json, ece_json, transaction_id))
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error updating QA transaction results: {e}", exc_info=True)
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
                group_name VARCHAR(255) NOT NULL,
                group_type VARCHAR(100) NOT NULL,
                filename VARCHAR(255),
                doc_type VARCHAR(100),
                extracted_text TEXT,
                qa_report TEXT,
                total_pages INTEGER,
                email VARCHAR(255),
                qa_findings JSONB,
                exit_criteria_eval JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN qa_findings JSONB;")
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN exit_criteria_eval JSONB;")
        except Exception:
            pass
            
        logger.info("Checked/Created qa_transactions table.")
    except Exception as e:
        logger.error(f"Error initializing qa_transactions table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_api_usage_logs():
    """Initializes the api_usage_logs table for tracking Gemini token usage."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                endpoint VARCHAR(255) NOT NULL,
                model_name VARCHAR(255) NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd NUMERIC(10, 6) DEFAULT 0,
                filename VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        try:
            cursor.execute("ALTER TABLE api_usage_logs ADD COLUMN filename VARCHAR(255);")
        except Exception:
            pass
            
        logger.info("Checked/Created api_usage_logs table.")
    except Exception as e:
        logger.error(f"Error initializing api_usage_logs table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_qa_transaction(project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages=None, email=None, qa_findings=None, exit_criteria_eval=None):
    """Saves a QA consult transaction to the database."""
    import json
    conn = None
    cursor = None
    try:
        if not project_id:
            logger.warning("No project_id provided, skipping saving QA transaction.")
            return False
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        qf_json = json.dumps(qa_findings) if qa_findings is not None else None
        ece_json = json.dumps(exit_criteria_eval) if exit_criteria_eval is not None else None
        
        cursor.execute("""
            INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qa_findings, exit_criteria_eval)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING transaction_id
        """, (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qf_json, ece_json))
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

def update_qa_transaction_results(transaction_id, qa_findings, exit_criteria_eval):
    """Updates the JSON columns of an existing QA transaction."""
    import json
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        qf_json = json.dumps(qa_findings) if qa_findings is not None else None
        ece_json = json.dumps(exit_criteria_eval) if exit_criteria_eval is not None else None
        
        cursor.execute("""
            UPDATE qa_transactions
            SET qa_findings = %s::jsonb, exit_criteria_eval = %s::jsonb
            WHERE transaction_id = %s::uuid
        """, (qf_json, ece_json, transaction_id))
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error updating QA transaction results: {e}", exc_info=True)
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

def init_api_usage_logs():
    """Initializes the api_usage_logs table for tracking Gemini token usage."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                endpoint_name VARCHAR(100),
                model_name VARCHAR(100),
                filename VARCHAR(255),
                prompt_tokens INT DEFAULT 0,
                completion_tokens INT DEFAULT 0,
                total_tokens INT DEFAULT 0,
                estimated_cost_usd DECIMAL(10, 6) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Add filename column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS filename VARCHAR(255);")
        except Exception:
            pass
        logger.info("Checked/Created api_usage_logs table.")
    except Exception as e:
        logger.error(f"Error initializing api_usage_logs table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def log_api_usage(endpoint_name, model_name, usage_metadata, filename=None):
    """Logs API token usage and calculates estimated cost."""
    if not usage_metadata:
        return
        
    prompt_tokens = getattr(usage_metadata, 'prompt_token_count', 0)
    completion_tokens = getattr(usage_metadata, 'candidates_token_count', 0)
    total_tokens = getattr(usage_metadata, 'total_token_count', 0)
    
    # Simple cost estimation (approximate Gemini 3.1 Pro/Flash pricing in USD)
    cost_usd = 0.0
    model_lower = model_name.lower()
    
    # 2.5-flash is currently billed at the Pro tier in Google Cloud
    if 'pro' in model_lower or ('2.5-flash' in model_lower and 'lite' not in model_lower):
        cost_usd = (prompt_tokens / 1_000_000 * 1.25) + (completion_tokens / 1_000_000 * 3.75)
    # Flash Lite or 1.5 Flash
    elif 'flash' in model_lower:
        cost_usd = (prompt_tokens / 1_000_000 * 0.075) + (completion_tokens / 1_000_000 * 0.30)

    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO api_usage_logs (endpoint_name, model_name, filename, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (endpoint_name, model_name, filename, prompt_tokens, completion_tokens, total_tokens, cost_usd))
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error logging API usage: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_api_usage_stats(time_filter='all'):
    """Retrieves aggregated API usage statistics with optional time filtering."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause based on time filter
        where_clause = ""
        if time_filter == 'daily':
            where_clause = "WHERE created_at >= CURRENT_DATE"
        elif time_filter == 'monthly':
            where_clause = "WHERE created_at >= date_trunc('month', CURRENT_DATE)"
        elif time_filter == 'yearly':
            where_clause = "WHERE created_at >= date_trunc('year', CURRENT_DATE)"
            
        stats = {}
        
        # Total cost and tokens
        cursor.execute(f"SELECT SUM(total_tokens), SUM(estimated_cost_usd) FROM api_usage_logs {where_clause}")
        row = cursor.fetchone()
        stats['total_tokens'] = row[0] or 0
        stats['total_cost_usd'] = float(row[1] or 0)
        
        # Usage by model
        cursor.execute(f"SELECT model_name, COUNT(*), SUM(total_tokens), SUM(estimated_cost_usd) FROM api_usage_logs {where_clause} GROUP BY model_name")
        stats['by_model'] = [
            {'model': r[0], 'requests': r[1], 'tokens': r[2], 'cost_usd': float(r[3] or 0)}
            for r in cursor.fetchall()
        ]
        
        # Usage by endpoint
        cursor.execute(f"SELECT endpoint_name, COUNT(*), SUM(total_tokens), SUM(estimated_cost_usd) FROM api_usage_logs {where_clause} GROUP BY endpoint_name")
        stats['by_endpoint'] = [
            {'endpoint': r[0], 'requests': r[1], 'tokens': r[2], 'cost_usd': float(r[3] or 0)}
            for r in cursor.fetchall()
        ]
        
        # Document History (Grouped by Document and Day)
        cursor.execute(f"""
            SELECT 
                filename, 
                MAX(created_at) as latest_date,
                STRING_AGG(DISTINCT endpoint_name, ', ') as endpoints,
                STRING_AGG(DISTINCT model_name, ', ') as models,
                SUM(total_tokens) as total_tokens,
                SUM(estimated_cost_usd) as total_cost,
                date_trunc('day', created_at) as scan_day
            FROM api_usage_logs 
            {where_clause} 
            GROUP BY filename, scan_day
            ORDER BY latest_date DESC 
            LIMIT 100
        """)
        stats['document_history'] = [
            {
                'filename': r[0] or 'Unknown Document',
                'date': r[1].isoformat() if r[1] else None,
                'endpoint': r[2],
                'model': r[3],
                'tokens': r[4],
                'cost_usd': float(r[5] or 0)
            }
            for r in cursor.fetchall()
        ]
        
        # Chart Data (Grouped by time interval)
        if time_filter == 'yearly':
            date_trunc_expr = "date_trunc('month', created_at)"
        elif time_filter == 'monthly':
            date_trunc_expr = "date_trunc('day', created_at)"
        elif time_filter == 'daily':
            date_trunc_expr = "date_trunc('hour', created_at)"
        else:
            date_trunc_expr = "date_trunc('day', created_at)" # default to daily groups
            
        cursor.execute(f"""
            SELECT {date_trunc_expr} as time_group, SUM(total_tokens), SUM(estimated_cost_usd)
            FROM api_usage_logs
            {where_clause}
            GROUP BY time_group
            ORDER BY time_group ASC
        """)
        stats['chart_data'] = [
            {
                'time_group': r[0].isoformat() if r[0] else None,
                'tokens': r[1],
                'cost_usd': float(r[2] or 0)
            }
            for r in cursor.fetchall()
        ]
        
        cursor.execute(f"""
            SELECT {date_trunc_expr} as time_group, model_name, SUM(prompt_tokens), SUM(completion_tokens), COUNT(*)
            FROM api_usage_logs
            {where_clause}
            GROUP BY time_group, model_name
            ORDER BY time_group ASC
        """)
        stats['model_chart_data'] = [
            {
                'time_group': r[0].isoformat() if r[0] else None,
                'model_name': r[1],
                'prompt_tokens': r[2],
                'completion_tokens': r[3],
                'requests': r[4]
            }
            for r in cursor.fetchall()
        ]
        
        return stats
    except Exception as e:
        logger.error(f"Error getting API usage stats: {e}", exc_info=True)
        return {}
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_billing_credit():
    """Initializes the billing_credit table."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_credit (
                id SERIAL PRIMARY KEY,
                total_credit_thb DECIMAL(12, 2) DEFAULT 0.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Insert initial row if empty
        cursor.execute("SELECT COUNT(*) FROM billing_credit")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO billing_credit (total_credit_thb) VALUES (0.00)")
            
        logger.info("Checked/Created billing_credit table.")
    except Exception as e:
        logger.error(f"Error initializing billing_credit table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_billing_credit():
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total_credit_thb FROM billing_credit ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0
    except Exception as e:
        logger.error(f"Error getting billing credit: {e}", exc_info=True)
        return 0.0
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def update_billing_credit(new_amount):
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("UPDATE billing_credit SET total_credit_thb = %s, updated_at = CURRENT_TIMESTAMP WHERE id = (SELECT id FROM billing_credit ORDER BY id DESC LIMIT 1)", (new_amount,))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO billing_credit (total_credit_thb) VALUES (%s)", (new_amount,))
        return True
    except Exception as e:
        logger.error(f"Error updating billing credit: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_ocr_history():
    """Initializes the ocr_history table for tracking simple OCR scans."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255),
                result_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Checked/Created ocr_history table.")
    except Exception as e:
        logger.error(f"Error initializing ocr_history table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_ocr_history(filename, result_json):
    """Saves a simple OCR scan history."""
    import json
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        
        rj = json.dumps(result_json) if result_json is not None else None
        
        cursor.execute("""
            INSERT INTO ocr_history (filename, result_json)
            VALUES (%s, %s::jsonb)
            RETURNING id, created_at
        """, (filename, rj))
        
        row = cursor.fetchone()
        conn.commit()
        return {'id': str(row[0]), 'created_at': row[1].isoformat()} if row else None
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving ocr history: {e}", exc_info=True)
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_ocr_history():
    """Retrieves top 50 recent OCR scans."""
    conn = None
    cursor = None
    try:
        from psycopg2.extras import RealDictCursor
        conn = get_ocr_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, filename, result_json, created_at
            FROM ocr_history
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        for row in rows:
            if 'id' in row: row['id'] = str(row['id'])
            if 'created_at' in row and row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
        return rows
    except Exception as e:
        logger.error(f"Error fetching ocr history: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_ocr_history(history_id):
    """Deletes an OCR scan history."""
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ocr_history WHERE id = %s::uuid", (history_id,))
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error deleting ocr history: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
