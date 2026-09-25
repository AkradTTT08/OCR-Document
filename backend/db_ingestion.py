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
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {MODEL_NAME}")
            model = SentenceTransformer(MODEL_NAME)
        except Exception as e:
            logger.error(f"Failed to load sentence_transformers: {e}")
            return None
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

def semantic_markdown_chunking(text: str, filename: str = "", category: str = "", project_name: str = "", max_chunk_size: int = 1200) -> list[str]:
    """
    Advanced Heading-Aware Semantic Markdown Chunking:
    1. Parses Markdown line by line, tracking Heading hierarchy (# H1, ## H2, ### H3, #### H4).
    2. Keeps Markdown tables (| ... |) and Code fences (``` ... ```) intact without breaking them in half.
    3. Prepends Contextual Breadcrumbs ([โครงการ: ... | เอกสาร: ... | หมวดหมู่: ... | โครงสร้าง: H1 > H2 > H3]) to every chunk.
    4. Balances chunk size (~1,000-1,200 chars) for optimal dense vector embeddings.
    """
    if not text or not text.strip():
        return []

    lines = text.split('\n')
    sections = []
    
    current_h1 = ""
    current_h2 = ""
    current_h3 = ""
    
    current_block_lines = []
    current_breadcrumb = ""
    in_code_block = False
    
    def get_breadcrumb():
        parts = []
        if current_h1: parts.append(current_h1)
        if current_h2: parts.append(current_h2)
        if current_h3: parts.append(current_h3)
        return " > ".join(parts) if parts else "เนื้อหาทั่วไป"

    for line in lines:
        stripped = line.strip()
        
        # Check code block fence
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current_block_lines.append(line)
            continue
            
        if in_code_block:
            current_block_lines.append(line)
            continue

        # Check headings
        is_h1 = stripped.startswith("# ") and not stripped.startswith("## ")
        is_h2 = stripped.startswith("## ") and not stripped.startswith("### ")
        is_h3 = stripped.startswith("### ") or stripped.startswith("#### ")
        
        if is_h1 or is_h2 or is_h3:
            if current_block_lines:
                raw_block = "\n".join(current_block_lines).strip()
                if raw_block:
                    sections.append({
                        "breadcrumb": current_breadcrumb or get_breadcrumb(),
                        "text": raw_block
                    })
                current_block_lines = []
                
            if is_h1:
                current_h1 = stripped.lstrip("#").strip()
                current_h2 = ""
                current_h3 = ""
            elif is_h2:
                current_h2 = stripped.lstrip("#").strip()
                current_h3 = ""
            elif is_h3:
                current_h3 = stripped.lstrip("#").strip()
                
            current_breadcrumb = get_breadcrumb()
            current_block_lines.append(line)
            continue

        current_block_lines.append(line)

    if current_block_lines:
        raw_block = "\n".join(current_block_lines).strip()
        if raw_block:
            sections.append({
                "breadcrumb": current_breadcrumb or get_breadcrumb(),
                "text": raw_block
            })

    # Convert sections into final contextual chunks
    final_chunks = []
    
    for sec in sections:
        b_crumb = sec["breadcrumb"]
        sec_text = sec["text"]
        
        # Build contextual prefix
        prefix_parts = []
        if project_name:
            prefix_parts.append(f"โครงการ: {project_name}")
        if filename:
            prefix_parts.append(f"เอกสาร: {filename}")
        if category and category.upper() != 'OTHER':
            prefix_parts.append(f"หมวดหมู่: {category}")
        if b_crumb and b_crumb != "เนื้อหาทั่วไป":
            prefix_parts.append(f"ส่วน: {b_crumb}")
            
        prefix_header = f"[{' | '.join(prefix_parts)}]\n" if prefix_parts else ""
        
        # If section is within max_chunk_size, keep as single chunk
        if len(sec_text) <= max_chunk_size:
            final_chunks.append(f"{prefix_header}{sec_text}".strip())
        else:
            paragraphs = sec_text.split('\n\n')
            accumulated = ""
            for p in paragraphs:
                if len(accumulated) + len(p) + 2 <= max_chunk_size:
                    accumulated = f"{accumulated}\n\n{p}".strip() if accumulated else p
                else:
                    if accumulated:
                        final_chunks.append(f"{prefix_header}{accumulated}".strip())
                    accumulated = p
            if accumulated:
                final_chunks.append(f"{prefix_header}{accumulated}".strip())
                
    if not final_chunks and text:
        final_chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size - 200)]
        
    return final_chunks

def chunk_markdown(text: str, chunk_size: int = 1500, overlap: int = 200, filename: str = "", category: str = "", project_name: str = "") -> list[str]:
    """
    Splits markdown text into semantic chunks with contextual breadcrumb awareness.
    """
    return semantic_markdown_chunking(
        text=text,
        filename=filename,
        category=category,
        project_name=project_name,
        max_chunk_size=chunk_size
    )

# ===================================================================
# Projects CRUD — ตรงกับ schema:
#   projects(project_id SERIAL PK, project_code VARCHAR UNIQUE NOT NULL,
#            project_name VARCHAR NOT NULL, description TEXT,
#            status VARCHAR DEFAULT 'Active', created_at TIMESTAMP)
# ===================================================================

def get_projects():
    """Fetch all projects from the database including multi-environment site URLs."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure site_urls column exists
        try:
            cursor.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS site_urls JSONB DEFAULT '[]'::jsonb;")
            conn.commit()
        except Exception:
            if conn: conn.rollback()

        cursor.execute(
            "SELECT p.project_id, p.project_name, p.project_code, p.description, p.status, p.created_at, COUNT(d.doc_id) as doc_count, p.default_base_url, p.site_urls "
            "FROM projects p LEFT JOIN documents d ON p.project_id = d.project_id GROUP BY p.project_id, p.site_urls ORDER BY p.project_id DESC;"
        )
        import json
        projects = []
        for row in cursor.fetchall():
            raw_sites = row[8]
            site_urls = raw_sites if isinstance(raw_sites, list) else (json.loads(raw_sites) if raw_sites else [])
            default_url = row[7] or "http://localhost:5173"
            
            if not site_urls and default_url:
                site_urls = [{"env_type": "TEST", "url": default_url, "is_default": True}]
                
            projects.append({
                "id": str(row[0]) if row[0] else None,
                "name": row[1],
                "project_code": row[2],
                "description": row[3],
                "status": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "doc_count": int(row[6]) if row[6] else 0,
                "default_base_url": default_url,
                "site_urls": site_urls
            })
        return projects
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def add_project(name: str = None, project_code: str = None, project_name: str = None,
                description: str = '', status: str = 'Active', default_base_url: str = 'http://localhost:5173',
                site_urls: list = None):
    """Add a new project with support for multi-environment Base URLs (TEST, UAT, PRD)."""
    import json
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

        # Process site_urls & determine default_base_url
        if site_urls and isinstance(site_urls, list) and len(site_urls) > 0:
            has_default = any(s.get('is_default') for s in site_urls)
            if not has_default:
                site_urls[0]['is_default'] = True
            for s in site_urls:
                if s.get('is_default'):
                    default_base_url = s.get('url') or default_base_url
                    break
        else:
            site_urls = [{"env_type": "TEST", "url": default_base_url or 'http://localhost:5173', "is_default": True}]

        logger.info(f"Inserting project: code={p_code}, name={p_name}, status={status}, default_base_url={default_base_url}")
        cursor.execute(
            "INSERT INTO projects (project_code, project_name, description, status, default_base_url, site_urls) "
            "VALUES (%s, %s, %s, %s, %s, %s::jsonb) RETURNING project_id;",
            (p_code, p_name, description, status, default_base_url or 'http://localhost:5173', json.dumps(site_urls))
        )
        project_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Project created successfully: id={project_id}")
        return {
            "id": str(project_id),
            "name": p_name,
            "project_code": p_code,
            "description": description,
            "status": status,
            "default_base_url": default_base_url or 'http://localhost:5173',
            "site_urls": site_urls
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

def update_project(project_id: str, name: str = None, project_name: str = None, project_code: str = None, 
                   description: str = None, status: str = None, default_base_url: str = None, site_urls: list = None):
    """Update an existing project including multi-environment site URLs."""
    import json
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
            update_fields.append("project_name = %s")
            params.append(p_name)
        if project_code is not None:
            update_fields.append("project_code = %s")
            params.append(project_code)
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)
        if status is not None:
            update_fields.append("status = %s")
            params.append(status)
            
        if site_urls is not None and isinstance(site_urls, list):
            has_default = any(s.get('is_default') for s in site_urls)
            if not has_default and len(site_urls) > 0:
                site_urls[0]['is_default'] = True
            for s in site_urls:
                if s.get('is_default'):
                    default_base_url = s.get('url') or default_base_url
                    break
            update_fields.append("site_urls = %s::jsonb")
            params.append(json.dumps(site_urls))

        if default_base_url is not None:
            update_fields.append("default_base_url = %s")
            params.append(default_base_url)
            
        if not update_fields:
            return None
            
        params.append(project_id)
        
        query = f"UPDATE projects SET {', '.join(update_fields)} WHERE project_id = %s::uuid RETURNING project_id, project_code, project_name, description, status, created_at, default_base_url, site_urls;"
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            raise Exception("ไม่พบโครงการที่ต้องการอัปเดต")
            
        conn.commit()
        raw_sites = row[7]
        processed_sites = raw_sites if isinstance(raw_sites, list) else (json.loads(raw_sites) if raw_sites else [])
        if not processed_sites and row[6]:
            processed_sites = [{"env_type": "TEST", "url": row[6], "is_default": True}]
            
        return {
            'id': str(row[0]),
            'project_id': str(row[0]),
            'project_code': row[1],
            'name': row[2],
            'project_name': row[2],
            'description': row[3],
            'status': row[4],
            'created_at': row[5].isoformat() if row[5] else None,
            'default_base_url': row[6] or 'http://localhost:5173',
            'site_urls': processed_sites
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

        if project_id is None:
            raise ValueError("project_id is required and must be a valid UUID")
        effective_project_id = project_id

        # 1. Fetch project name for breadcrumb context
        conn = get_db_connection()
        cursor = conn.cursor()
        proj_name = ""
        try:
            cursor.execute("SELECT project_name FROM projects WHERE project_id = %s::uuid", (effective_project_id,))
            p_row = cursor.fetchone()
            if p_row:
                proj_name = p_row[0] or ""
        except Exception as p_err:
            logger.warning(f"Could not fetch project name for breadcrumbs: {p_err}")

        # 2. Semantic Heading-Aware Chunking with Contextual Breadcrumbs
        chunks = semantic_markdown_chunking(
            text=markdown_text,
            filename=filename,
            category=doc_category,
            project_name=proj_name,
            max_chunk_size=1200
        )
        logger.info(f"Generated {len(chunks)} contextual chunks for '{filename}'.")

        # 3. Embedding
        embedder = get_model()
        if embedder is not None:
            try:
                embeddings = [emb.tolist() for emb in embedder.encode(chunks)]
            except Exception as emb_err:
                logger.error(f"Error generating embeddings: {emb_err}")
                embeddings = [[0.0] * 384 for _ in chunks]
        else:
            embeddings = [[0.0] * 384 for _ in chunks]

        # 4. Compute file hash for duplicate detection
        file_hash = hashlib.sha256(markdown_text.encode('utf-8')).hexdigest()

        # 5. DB Insertion
        # Check for duplicate by file_hash
        cursor.execute("SELECT doc_id FROM documents WHERE file_hash = %s AND status = 'Active';", (file_hash,))
        existing = cursor.fetchone()
        if existing:
            logger.info(f"Document with same hash already exists (doc_id={existing[0]}). Skipping ingestion.")
            return True, str(existing[0])

        cursor.execute(
            "INSERT INTO documents (project_id, doc_category, doc_type, original_filename, "
            "full_markdown_content, file_hash, is_golden_data) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING doc_id;",
            (effective_project_id, doc_category, doc_type, filename, markdown_text, file_hash, is_golden_data)
        )
        document_id = cursor.fetchone()[0]

        # Insert chunks
        for chunk_text, emb in zip(chunks, embeddings):
            emb_list = emb if isinstance(emb, list) else emb.tolist()
            cursor.execute(
                "INSERT INTO document_chunks (doc_id, chunk_text, embedding) VALUES (%s, %s, %s);",
                (document_id, chunk_text, emb_list)
            )

        conn.commit()
        logger.info(f"Successfully ingested '{filename}' (doc_id: {document_id}) with {len(chunks)} contextual chunks.")
        
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


def update_markdown_document(
    doc_id: str, 
    new_markdown_text: str = None, 
    new_category: str = None, 
    new_filename: str = None, 
    new_is_golden: bool = None
):
    """
    Updates the document properties (category, filename, golden status, and/or markdown content).
    If markdown content or category/filename changes, re-generates its chunks and embeddings
    using Semantic Markdown Chunking and Contextual Breadcrumbs.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch doc info and project name for breadcrumb context
        cursor.execute("""
            SELECT d.original_filename, d.doc_category, d.project_id, p.project_name, d.full_markdown_content, d.is_golden_data
            FROM documents d
            LEFT JOIN projects p ON d.project_id = p.project_id
            WHERE d.doc_id = %s
        """, (doc_id,))
        doc_row = cursor.fetchone()
        if not doc_row:
            return False, "Document not found."

        cur_filename = doc_row[0] or ""
        cur_category = doc_row[1] or "Reference"
        proj_name = doc_row[3] if (len(doc_row) > 3 and doc_row[3]) else ""
        cur_content = doc_row[4] or ""
        cur_golden = doc_row[5] if (len(doc_row) > 5 and doc_row[5] is not None) else False

        final_filename = new_filename.strip() if (new_filename is not None and new_filename.strip()) else cur_filename
        final_category = new_category.strip() if (new_category is not None and new_category.strip()) else cur_category
        final_golden = new_is_golden if new_is_golden is not None else cur_golden
        final_content = new_markdown_text if (new_markdown_text is not None and new_markdown_text.strip()) else cur_content

        need_rechunk = (
            (new_markdown_text is not None and new_markdown_text.strip() != cur_content) or
            (new_category is not None and new_category.strip() != cur_category) or
            (new_filename is not None and new_filename.strip() != cur_filename)
        )

        file_hash = hashlib.sha256(final_content.encode('utf-8')).hexdigest() if final_content else ""

        # Update document record
        cursor.execute("""
            UPDATE documents 
            SET doc_category = %s,
                original_filename = %s,
                is_golden_data = %s,
                full_markdown_content = %s,
                file_hash = %s
            WHERE doc_id = %s
        """, (final_category, final_filename, final_golden, final_content, file_hash, doc_id))

        if cursor.rowcount == 0:
            raise Exception("Document update affected 0 rows.")

        # If content, category or filename changed, re-chunk and re-embed
        if need_rechunk and final_content.strip():
            # 1. Semantic Chunking
            chunks = semantic_markdown_chunking(
                text=final_content,
                filename=final_filename,
                category=final_category,
                project_name=proj_name,
                max_chunk_size=1200
            )
            
            # 2. Embedding
            embedder = get_model()
            if embedder is not None:
                embeddings = [emb.tolist() for emb in embedder.encode(chunks)]
            else:
                embeddings = [[0.0] * 384 for _ in chunks]

            # Delete old chunks
            cursor.execute("DELETE FROM document_chunks WHERE doc_id = %s", (doc_id,))

            # Insert new chunks
            for chunk_text, emb in zip(chunks, embeddings):
                cursor.execute(
                    "INSERT INTO document_chunks (doc_id, chunk_text, embedding) VALUES (%s, %s, %s);",
                    (doc_id, chunk_text, emb)
                )

        conn.commit()
        logger.info(f"Successfully updated document '{doc_id}' (Category: '{final_category}', Filename: '{final_filename}').")
        return True, "Update successful"

    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error updating document {doc_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_project_markdown_documents_summary(project_id: str, limit: int = 20):
    """
    Retrieves all Markdown / KB documents available for a project,
    returning basic metadata and a preview so the AI Agent knows
    which MD documents exist in the project to cross-examine.
    """
    if not project_id:
        return []
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, doc_type, is_golden_data,
                   SUBSTRING(full_markdown_content FROM 1 FOR 400) as preview
            FROM documents
            WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
            ORDER BY is_golden_data DESC, doc_id DESC
            LIMIT %s;
        """, (project_id, limit))
        rows = cursor.fetchall()
        docs = []
        for r in rows:
            docs.append({
                'doc_id': str(r[0]),
                'filename': r[1] or 'Untitled',
                'category': r[2] or 'General',
                'doc_type': r[3] or 'MD',
                'is_golden_data': bool(r[4]),
                'preview': (r[5] or '').replace('\n', ' ').strip()
            })
        return docs
    except Exception as e:
        logger.error(f"Error fetching project markdown documents summary: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def search_knowledge_base(query_text: str, doc_type: str = None, top_k: int = 5, project_id: str = None, hybrid: bool = True):
    """
    Enhanced Hybrid Knowledge Base Search (Semantic Vector Distance + Keyword Exact Match Ranking):
    - Uses pgvector's <=> Cosine distance for deep semantic relevance.
    - Applies keyword match boost for technical terms, IDs, or endpoints (e.g. REQ-001, /api/v1/..., HTTP codes).
    - Supports category filtering (Requirement, SRS, API_Spec, Architecture, Test_Standard, etc.).
    """
    if not query_text or not query_text.strip():
        return []

    conn = None
    cursor = None
    try:
        embedder = get_model()
        query_embedding = embedder.encode([query_text])[0] if embedder is not None else [0.0] * 384
        
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT 
                dc.chunk_text, 
                d.doc_category, 
                d.original_filename,
                1 - (dc.embedding <=> %s::vector) as similarity,
                d.doc_id
            FROM document_chunks dc
            JOIN documents d ON dc.doc_id = d.doc_id
            WHERE (d.status = 'Active' OR d.status IS NULL)
        """
        params = [query_embedding.tolist() if hasattr(query_embedding, 'tolist') else query_embedding]

        if project_id:
            sql += " AND d.project_id = %s::uuid"
            params.append(project_id)

        if doc_type:
            if isinstance(doc_type, list) and len(doc_type) > 0:
                valid_types = [dt.upper() for dt in doc_type if dt and dt.upper() != 'OTHER']
                if valid_types:
                    placeholders = ', '.join(['%s'] * len(valid_types))
                    sql += f" AND UPPER(TRIM(d.doc_category)) IN ({placeholders})"
                    params.extend(valid_types)
            elif isinstance(doc_type, str) and doc_type.upper() != "OTHER":
                sql += " AND UPPER(TRIM(d.doc_category)) = %s"
                params.append(doc_type.upper())

        # Retrieve more candidates if hybrid search is enabled
        fetch_limit = top_k * 3 if hybrid else top_k
        sql += " ORDER BY dc.embedding <=> %s::vector LIMIT %s;"
        params.extend([query_embedding.tolist() if hasattr(query_embedding, 'tolist') else query_embedding, fetch_limit])

        cursor.execute(sql, params)
        raw_results = cursor.fetchall()
        
        results = []
        # Keyword extraction for hybrid boosting
        import re
        q_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9_\-\.\/]{3,}|[\u0E00-\u0E7F]{3,}', query_text) if len(w) >= 3]
        
        for row in raw_results:
            chunk_txt = row[0] or ""
            doc_cat = row[1] or "Reference"
            doc_fn = row[2] or "Untitled"
            base_sim = float(row[3]) if row[3] is not None else 0.0
            
            # Hybrid Keyword Score Calculation
            keyword_score = 0.0
            if hybrid and q_words:
                matched_count = sum(1 for w in q_words if w in chunk_txt.lower())
                keyword_score = (matched_count / len(q_words)) * 0.25 # Up to +0.25 bonus score
                
            combined_score = round(min(1.0, base_sim + keyword_score), 4)
            
            results.append({
                "chunk_text": chunk_txt,
                "doc_type": doc_cat,
                "filename": doc_fn,
                "doc_id": str(row[4]) if len(row) > 4 else None,
                "similarity": combined_score,
                "raw_vector_sim": round(base_sim, 4)
            })
            
        # Re-sort by combined hybrid score
        if hybrid:
            results.sort(key=lambda x: x["similarity"], reverse=True)
            
        return results[:top_k]

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}", exc_info=True)
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def reindex_project_documents(project_id: str):
    """
    Re-indexes all active documents in a project using Semantic Markdown Chunking & Contextual Breadcrumbs.
    """
    if not project_id:
        return False, "project_id is required"
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch project name
        cursor.execute("SELECT project_name FROM projects WHERE project_id = %s::uuid", (project_id,))
        p_row = cursor.fetchone()
        proj_name = p_row[0] if p_row else ""
        
        # Fetch all active documents
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, full_markdown_content
            FROM documents
            WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
        """, (project_id,))
        docs = cursor.fetchall()
        
        embedder = get_model()
        total_chunks = 0
        
        for doc_id, filename, category, content in docs:
            if not content:
                continue
            chunks = semantic_markdown_chunking(
                text=content,
                filename=filename or "",
                category=category or "",
                project_name=proj_name,
                max_chunk_size=1200
            )
            if not chunks:
                continue
                
            if embedder is not None:
                embeddings = [emb.tolist() for emb in embedder.encode(chunks)]
            else:
                embeddings = [[0.0] * 384 for _ in chunks]
                
            cursor.execute("DELETE FROM document_chunks WHERE doc_id = %s", (doc_id,))
            for chunk_text, emb in zip(chunks, embeddings):
                cursor.execute(
                    "INSERT INTO document_chunks (doc_id, chunk_text, embedding) VALUES (%s, %s, %s)",
                    (doc_id, chunk_text, emb)
                )
            total_chunks += len(chunks)
            
        conn.commit()
        logger.info(f"Re-indexed project {project_id}: {len(docs)} documents, {total_chunks} total contextual chunks.")
        return True, {"documents_count": len(docs), "total_chunks": total_chunks}
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error reindexing project {project_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def retrieve_comprehensive_qa_context(project_id: str, query: str, history: list = None) -> dict:
    """
    Assembles high-density, multi-layered knowledge context for QA Research:
    1. Project Metadata (Code, Name, Description)
    2. Document Catalog & Summaries (all uploaded docs)
    3. Complete or targeted Document Markdown Texts
    4. Structured Requirements (Phase 1 extracted requirements)
    5. Semantic Vector Search Chunks (Top similar chunks)
    6. Keyword / Exact Match Chunks (Full-text matching for technical terms/codes)
    7. Generated QA Artifacts (SRS, Test Cases from QA Doc Creator)
    """
    import re
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Project Info
        project_info = {}
        if project_id:
            try:
                cursor.execute("SELECT project_id, project_name, project_code, description, default_base_url FROM projects WHERE project_id = %s::uuid;", (project_id,))
                p_row = cursor.fetchone()
                if p_row:
                    project_info = {
                        "id": str(p_row[0]),
                        "name": p_row[1],
                        "code": p_row[2],
                        "description": p_row[3] or "",
                        "base_url": p_row[4] or ""
                    }
            except Exception as pe:
                logger.warning(f"Failed to fetch project info for {project_id}: {pe}")
                if conn: conn.rollback()
                
        # 2. Uploaded Documents
        doc_rows = []
        if project_id:
            try:
                cursor.execute("""
                    SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content, created_at
                    FROM documents
                    WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
                    ORDER BY doc_id ASC;
                """, (project_id,))
                doc_rows = cursor.fetchall()
            except Exception as de:
                logger.warning(f"Failed to fetch documents for {project_id}: {de}")
                if conn: conn.rollback()
            
        docs_catalog = []
        total_markdown_len = 0
        docs_content_map = {}
        for d in doc_rows:
            doc_id = str(d[0])
            fname = d[1] or "Unknown"
            cat = d[2] or "General"
            dtype = d[3] or "Document"
            content = d[4] or ""
            total_markdown_len += len(content)
            docs_catalog.append({
                "doc_id": doc_id,
                "filename": fname,
                "category": cat,
                "type": dtype,
                "length": len(content)
            })
            docs_content_map[fname] = {
                "category": cat,
                "type": dtype,
                "content": content
            }
            
        # 3. Structured Requirements
        req_rows = []
        if project_id:
            try:
                cursor.execute("""
                    SELECT req_code, title, description, steps, expected_results
                    FROM structured_requirements
                    WHERE project_id = %s::uuid
                    ORDER BY req_code ASC;
                """, (project_id,))
                req_rows = cursor.fetchall()
            except Exception as re_err:
                logger.warning(f"Failed to fetch structured requirements for {project_id}: {re_err}")
                if conn: conn.rollback()
            
        structured_reqs = []
        for r in req_rows:
            structured_reqs.append({
                "code": r[0],
                "title": r[1],
                "description": r[2],
                "steps": r[3] or [],
                "expected": r[4] or []
            })
            
        # 4. QA Generated Documents (SRS, Test Cases, etc.)
        qa_doc_rows = []
        if project_id:
            try:
                cursor.execute("""
                    SELECT doc_name, doc_type, markdown_content
                    FROM qa_generated_documents
                    WHERE project_id = %s::uuid AND status = 'Completed'
                    ORDER BY created_at DESC LIMIT 5;
                """, (project_id,))
                qa_doc_rows = cursor.fetchall()
            except Exception:
                if conn: conn.rollback()
                
        qa_generated = []
        for q in qa_doc_rows:
            qa_generated.append({
                "name": q[0],
                "type": q[1],
                "content": (q[2] or "")[:4000]
            })
            
        # 5. Semantic Vector Search
        vector_chunks = search_knowledge_base(query, top_k=20, project_id=project_id)
        
        # 6. Keyword / Exact Matches on chunks (for technical IDs like REQ-, TC-, error codes, endpoints)
        keyword_chunks = []
        words = [w for w in re.findall(r'[\w\-\/]{3,}', query) if len(w) >= 3][:5]
        if words and project_id:
            try:
                like_clauses = " OR ".join(["dc.chunk_text ILIKE %s"] * len(words))
                kw_sql = f"""
                    SELECT dc.chunk_text, d.doc_category, d.original_filename
                    FROM document_chunks dc
                    JOIN documents d ON dc.doc_id = d.doc_id
                    WHERE d.project_id = %s::uuid AND (d.status = 'Active' OR d.status IS NULL)
                    AND ({like_clauses})
                    LIMIT 15;
                """
                kw_params = [project_id] + [f"%{w}%" for w in words]
                cursor.execute(kw_sql, kw_params)
                for kr in cursor.fetchall():
                    keyword_chunks.append({
                        "chunk_text": kr[0],
                        "doc_type": kr[1],
                        "filename": kr[2],
                        "similarity": 0.99
                    })
            except Exception as kwe:
                logger.warning(f"Keyword search error: {kwe}")
                if conn: conn.rollback()
                
        cursor.close()
        conn.close()
        conn = None
        
        # --- Build Unified Context String ---
        context_parts = []
        
        # Section 1: Project Overview
        if project_info:
            context_parts.append(
                f"### [PROJECT METADATA]\n"
                f"- Project Code: {project_info.get('code')}\n"
                f"- Project Name: {project_info.get('name')}\n"
                f"- Description: {project_info.get('description') or 'None'}\n"
                f"- Total Uploaded Documents: {len(docs_catalog)}\n"
            )
            
        # Section 2: Document Catalog
        if docs_catalog:
            catalog_lines = ["### [PROJECT DOCUMENTS CATALOGUE]"]
            for dc in docs_catalog:
                catalog_lines.append(f"- Document: {dc['filename']} | Category: {dc['category']} | Type: {dc['type']} | Size: {dc['length']} chars")
            context_parts.append("\n".join(catalog_lines))
            
        # Section 3: Structured Requirements
        if structured_reqs:
            req_lines = [f"### [STRUCTURED REQUIREMENTS ({len(structured_reqs)} items)]"]
            for req in structured_reqs:
                req_lines.append(f"• **[{req['code']}] {req['title']}** (Category: {req['category']})")
                if req['description']:
                    req_lines.append(f"  Description: {req['description']}")
                if req['steps']:
                    req_lines.append(f"  Steps: {req['steps']}")
                if req['expected']:
                    req_lines.append(f"  Expected Results: {req['expected']}")
            context_parts.append("\n".join(req_lines))
            
        # Section 4: Full Document Texts (if moderate total size < 80k chars) OR High-Priority Sections
        if 0 < total_markdown_len <= 80000:
            doc_text_lines = ["### [AUTHORITATIVE FULL DOCUMENT CONTENTS]"]
            for fname, dinfo in docs_content_map.items():
                doc_text_lines.append(f"\n--- BEGIN DOCUMENT: {fname} (Category: {dinfo['category']}) ---\n{dinfo['content']}\n--- END DOCUMENT: {fname} ---\n")
            context_parts.append("\n".join(doc_text_lines))
        elif total_markdown_len > 80000:
            # Include comprehensive chunks & summaries
            doc_text_lines = ["### [KEY DOCUMENT EXCERPTS & SUMMARIES]"]
            for fname, dinfo in docs_content_map.items():
                snippet = dinfo['content'][:3000]
                doc_text_lines.append(f"\n--- DOCUMENT OVERVIEW: {fname} ---\n{snippet}\n...")
            context_parts.append("\n".join(doc_text_lines))
            
        # Section 5: Relevant Semantic Chunks & Keyword Matches
        all_chunks = vector_chunks + keyword_chunks
        seen_chunks = set()
        unique_chunks = []
        for c in all_chunks:
            c_key = c.get('chunk_text', '')[:80].strip()
            if c_key and c_key not in seen_chunks:
                seen_chunks.add(c_key)
                unique_chunks.append(c)
                
        if unique_chunks:
            chunk_lines = [f"### [HIGHLY RELEVANT EXCERPTS (Semantic & Keyword Search)]"]
            for idx, c in enumerate(unique_chunks[:25]):
                chunk_lines.append(f"[Excerpt {idx+1} from {c.get('filename', 'Doc')} - Relevance: {c.get('similarity', 0):.2f}]:\n{c.get('chunk_text', '')}\n")
            context_parts.append("\n".join(chunk_lines))
            
        # Section 6: QA Generated Artifacts
        if qa_generated:
            qa_lines = ["### [GENERATED QA SPECIFICATIONS & TEST SUITES]"]
            for qa in qa_generated:
                qa_lines.append(f"- **{qa['name']}** ({qa['type']}):\n{qa['content']}\n")
            context_parts.append("\n".join(qa_lines))
            
        return {
            "project_name": project_info.get('name', ''),
            "project_code": project_info.get('code', ''),
            "context_str": "\n\n".join(context_parts),
            "docs_count": len(docs_catalog),
            "reqs_count": len(structured_reqs)
        }
        
    except Exception as e:
        logger.error(f"Error in retrieve_comprehensive_qa_context: {e}", exc_info=True)
        return {
            "project_name": "",
            "project_code": "",
            "context_str": f"Error retrieving context: {e}",
            "docs_count": 0,
            "reqs_count": 0
        }
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_qa_transactions():
    """Initializes the qa_transactions table and all required columns in the database."""
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
                qa_findings JSONB,
                exit_criteria_eval JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS group_type VARCHAR(100);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS doc_type VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS extracted_text TEXT;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS qa_report TEXT;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS total_pages INTEGER;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS email VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS qa_findings JSONB;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS exit_criteria_eval JSONB;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
        logger.info("Checked/Created qa_transactions table.")
    except Exception as e:
        logger.error(f"Error initializing qa_transactions table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def resolve_project_id_uuid(conn, project_id):
    """Safely resolves project_id to a valid UUID string, or None."""
    if not project_id or str(project_id).lower() in ['none', 'null', 'undefined', '']:
        return None
    import uuid
    pid_str = str(project_id).strip()
    try:
        return str(uuid.UUID(pid_str))
    except (ValueError, TypeError):
        pass
    
    # Try looking up by project_code or project_name
    try:
        cur = conn.cursor()
        cur.execute("SELECT project_id FROM projects WHERE project_code = %s OR project_name = %s LIMIT 1", (pid_str, pid_str))
        row = cur.fetchone()
        cur.close()
        if row and row[0]:
            return str(row[0])
    except Exception as e:
        logger.warning(f"Could not resolve project_id UUID for '{project_id}': {e}")
    return None

def save_qa_transaction(project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages=None, email=None, qa_findings=None, exit_criteria_eval=None):
    """Saves a QA consult transaction to the database."""
    import json, re
    conn = None
    cursor = None
    try:
        if group_name:
            group_name = re.sub(r'^\[.*?\]\s*', '', str(group_name)).strip()
        if not group_name:
            group_name = 'General'

        conn = get_db_connection()
        cursor = conn.cursor()

        # Resolve project_id safely
        resolved_pid = resolve_project_id_uuid(conn, project_id)

        # Automatically ensure group exists in qa_groups table
        if resolved_pid:
            try:
                save_qa_group(resolved_pid, group_name, group_type or 'Project Plan')
            except Exception as g_err:
                logger.warning(f"Note: auto save_qa_group in save_qa_transaction: {g_err}")

        qf_json = json.dumps(qa_findings) if qa_findings is not None else None
        ece_json = json.dumps(exit_criteria_eval) if exit_criteria_eval is not None else None
        
        if resolved_pid:
            cursor.execute("""
                INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qa_findings, exit_criteria_eval)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING transaction_id
            """, (resolved_pid, group_name, group_type or 'Project Plan', filename, doc_type, extracted_text, qa_report, total_pages, email, qf_json, ece_json))
        else:
            cursor.execute("""
                INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email, qa_findings, exit_criteria_eval)
                VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING transaction_id
            """, (group_name, group_type or 'Project Plan', filename, doc_type, extracted_text, qa_report, total_pages, email, qf_json, ece_json))

        transaction_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Saved QA transaction {transaction_id} for {filename} (project: {resolved_pid}).")
        return str(transaction_id)
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving QA transaction for {filename}: {e}", exc_info=True)
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
        
        cursor.execute(r"""
            CREATE TABLE IF NOT EXISTS qa_groups (
                group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255) NOT NULL,
                group_type VARCHAR(100) NOT NULL DEFAULT 'Project Plan',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE;
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_type VARCHAR(100) DEFAULT 'Project Plan';
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'qa_groups_project_group_unique'
                ) THEN
                    ALTER TABLE qa_groups ADD CONSTRAINT qa_groups_project_group_unique UNIQUE(project_id, group_name);
                END IF;
            EXCEPTION WHEN OTHERS THEN
                NULL;
            END $$;

            -- Auto-sync/recover any existing groups from qa_transactions into qa_groups
            INSERT INTO qa_groups (project_id, group_name, group_type, created_at)
            SELECT t.project_id, REGEXP_REPLACE(t.group_name, '^\[.*?\]\s*', ''), COALESCE(NULLIF(t.group_type, ''), 'Project Plan'), MIN(t.created_at)
            FROM qa_transactions t
            WHERE t.project_id IS NOT NULL AND t.group_name IS NOT NULL AND TRIM(t.group_name) != ''
            GROUP BY t.project_id, REGEXP_REPLACE(t.group_name, '^\[.*?\]\s*', ''), t.group_type
            ON CONFLICT (project_id, group_name) DO NOTHING;
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
            
        init_qa_groups_table()
        conn = get_db_connection()
        cursor = conn.cursor()
        resolved_pid = resolve_project_id_uuid(conn, project_id)
        if not resolved_pid:
            return False, f"Invalid project_id: {project_id}"
            
        # Insert or ignore (using ON CONFLICT DO NOTHING)
        cursor.execute("""
            INSERT INTO qa_groups (project_id, group_name, group_type)
            VALUES (%s::uuid, %s, %s)
            ON CONFLICT (project_id, group_name) DO NOTHING
            RETURNING group_id
        """, (resolved_pid, group_name, group_type or 'Project Plan'))
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
        init_qa_groups_table()
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

def delete_qa_transaction(transaction_id: str):
    """Deletes a QA transaction by ID."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM qa_transactions WHERE transaction_id = %s::uuid;", (transaction_id,))
        conn.commit()
        return True, "Transaction deleted successfully"
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error deleting QA transaction {transaction_id}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_qa_group(project_id: str, group_name: str, delete_history: bool = True):
    """
    Deletes a QA group and optionally all associated transactions.
    Matches both original name and stripped name.
    """
    conn = None
    cursor = None
    try:
        init_qa_groups_table()
        init_qa_transactions()
        import re
        clean_name = re.sub(r'^\[.*?\]\s*', '', str(group_name)).strip()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete from qa_groups
        cursor.execute("""
            DELETE FROM qa_groups
            WHERE (project_id = %s::uuid OR project_id IS NULL)
              AND (group_name = %s OR group_name = %s OR TRIM(LOWER(group_name)) = TRIM(LOWER(%s)));
        """, (project_id, group_name, clean_name, clean_name))
        
        # Delete from qa_transactions if requested
        if delete_history:
            try:
                cursor.execute("""
                    DELETE FROM qa_transactions
                    WHERE (project_id = %s::uuid OR project_id IS NULL)
                      AND (group_name = %s OR group_name = %s OR TRIM(LOWER(group_name)) = TRIM(LOWER(%s)));
                """, (project_id, group_name, clean_name, clean_name))
            except Exception as te:
                logger.warning(f"Note on deleting qa_transactions: {te}")
            
        conn.commit()
        return True, "Group deleted successfully"
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error deleting QA group {group_name}: {e}", exc_info=True)
        return False, str(e)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_api_usage_logs():
    """Initializes the api_usage_logs table for tracking Gemini token usage and migrates schema if needed."""
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
            
            -- Ensure all modern columns exist for backward-compatibility
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS log_id UUID DEFAULT gen_random_uuid();
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS endpoint_name VARCHAR(100);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS prompt_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS completion_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS total_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS estimated_cost_usd DECIMAL(10, 6) DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
        
        # Migrate legacy column data if present
        try:
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='api_usage_logs' AND column_name='service_name') THEN
                        UPDATE api_usage_logs SET endpoint_name = service_name WHERE endpoint_name IS NULL;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='api_usage_logs' AND column_name='input_tokens') THEN
                        UPDATE api_usage_logs SET prompt_tokens = input_tokens WHERE prompt_tokens IS NULL OR prompt_tokens = 0;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='api_usage_logs' AND column_name='output_tokens') THEN
                        UPDATE api_usage_logs SET completion_tokens = output_tokens WHERE completion_tokens IS NULL OR completion_tokens = 0;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='api_usage_logs' AND column_name='cost_usd') THEN
                        UPDATE api_usage_logs SET estimated_cost_usd = cost_usd WHERE estimated_cost_usd IS NULL OR estimated_cost_usd = 0;
                    END IF;
                END $$;
            """)
        except Exception as mig_err:
            logger.warning(f"Legacy data sync error (non-fatal): {mig_err}")

        logger.info("Checked/Created api_usage_logs table.")
    except Exception as e:
        logger.error(f"Error initializing api_usage_logs table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def log_api_usage(endpoint_name, model_name, usage_metadata, filename=None):
    """Logs API token usage and calculates estimated cost across all agents and endpoints."""
    if not usage_metadata:
        return
        
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    
    if isinstance(usage_metadata, dict):
        prompt_tokens = int(usage_metadata.get('prompt_token_count') or usage_metadata.get('prompt_tokens') or 0)
        completion_tokens = int(usage_metadata.get('candidates_token_count') or usage_metadata.get('completion_tokens') or 0)
        total_tokens = int(usage_metadata.get('total_token_count') or usage_metadata.get('total_tokens') or (prompt_tokens + completion_tokens))
    else:
        prompt_tokens = int(getattr(usage_metadata, 'prompt_token_count', 0) or 0)
        completion_tokens = int(getattr(usage_metadata, 'candidates_token_count', 0) or 0)
        total_tokens = int(getattr(usage_metadata, 'total_token_count', 0) or (prompt_tokens + completion_tokens))
        
    if total_tokens == 0 and prompt_tokens == 0 and completion_tokens == 0:
        return

    # Approximate Gemini pricing in USD
    cost_usd = 0.0
    model_str = str(model_name or 'gemini-2.5-flash').lower()
    
    if 'pro' in model_str:
        cost_usd = (prompt_tokens / 1_000_000 * 1.25) + (completion_tokens / 1_000_000 * 5.00)
    elif '2.5-flash' in model_str:
        cost_usd = (prompt_tokens / 1_000_000 * 0.15) + (completion_tokens / 1_000_000 * 0.60)
    elif 'flash' in model_str:
        cost_usd = (prompt_tokens / 1_000_000 * 0.075) + (completion_tokens / 1_000_000 * 0.30)
    else:
        cost_usd = (prompt_tokens / 1_000_000 * 0.10) + (completion_tokens / 1_000_000 * 0.40)

    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO api_usage_logs (endpoint_name, model_name, filename, prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (endpoint_name or 'AI_Agent', model_name or 'gemini-2.5-flash', filename, prompt_tokens, completion_tokens, total_tokens, cost_usd)
        
        try:
            cursor.execute(insert_query, params)
            conn.commit()
            logger.info(f"Logged API usage for {endpoint_name} ({model_name}): {total_tokens} tokens, ${cost_usd:.6f}")
        except Exception as insert_err:
            conn.rollback()
            # If columns missing, perform self-healing migration and retry
            logger.warning(f"Initial insert into api_usage_logs failed ({insert_err}), self-healing schema...")
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
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS endpoint_name VARCHAR(100);
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS prompt_tokens INT DEFAULT 0;
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS completion_tokens INT DEFAULT 0;
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS total_tokens INT DEFAULT 0;
                ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS estimated_cost_usd DECIMAL(10, 6) DEFAULT 0;
            """)
            conn.commit()
            cursor.execute(insert_query, params)
            conn.commit()
            logger.info(f"Self-healed and logged API usage for {endpoint_name} ({model_name}): {total_tokens} tokens")
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error logging API usage: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_api_usage_stats(time_filter='all'):
    """Retrieves aggregated API usage statistics with optional time filtering."""
    default_stats = {
        'total_tokens': 0,
        'total_cost_usd': 0.0,
        'by_model': [],
        'by_endpoint': [],
        'document_history': [],
        'chart_data': [],
        'model_chart_data': []
    }
    conn = None
    cursor = None
    try:
        conn = get_ocr_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists and has necessary columns
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
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS endpoint_name VARCHAR(100);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS prompt_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS completion_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS total_tokens INT DEFAULT 0;
            ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS estimated_cost_usd DECIMAL(10, 6) DEFAULT 0;
        """)
        conn.commit()
        
        # Build WHERE clause based on time filter
        where_clause = ""
        if time_filter == 'daily':
            where_clause = "WHERE created_at >= CURRENT_DATE"
        elif time_filter == 'monthly':
            where_clause = "WHERE created_at >= date_trunc('month', CURRENT_DATE)"
        elif time_filter == 'yearly':
            where_clause = "WHERE created_at >= date_trunc('year', CURRENT_DATE)"
            
        stats = dict(default_stats)
        
        # Total cost and tokens
        cursor.execute(f"SELECT COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost_usd), 0) FROM api_usage_logs {where_clause}")
        row = cursor.fetchone()
        if row:
            stats['total_tokens'] = int(row[0] or 0)
            stats['total_cost_usd'] = float(row[1] or 0.0)
        
        # Usage by model
        cursor.execute(f"SELECT COALESCE(model_name, 'gemini-2.5-flash'), COUNT(*), COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost_usd), 0) FROM api_usage_logs {where_clause} GROUP BY model_name")
        stats['by_model'] = [
            {'model': r[0], 'requests': r[1], 'tokens': int(r[2] or 0), 'cost_usd': float(r[3] or 0.0)}
            for r in cursor.fetchall()
        ]
        
        # Usage by endpoint
        cursor.execute(f"SELECT COALESCE(endpoint_name, 'AI_Agent'), COUNT(*), COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost_usd), 0) FROM api_usage_logs {where_clause} GROUP BY endpoint_name")
        stats['by_endpoint'] = [
            {'endpoint': r[0], 'requests': r[1], 'tokens': int(r[2] or 0), 'cost_usd': float(r[3] or 0.0)}
            for r in cursor.fetchall()
        ]
        
        # Document History (Grouped by Document and Day)
        cursor.execute(f"""
            SELECT 
                COALESCE(filename, 'Unknown Document') as fname, 
                MAX(created_at) as latest_date,
                STRING_AGG(DISTINCT COALESCE(endpoint_name, 'AI_Agent'), ', ') as endpoints,
                STRING_AGG(DISTINCT COALESCE(model_name, 'gemini-2.5-flash'), ', ') as models,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) as total_cost,
                date_trunc('day', created_at) as scan_day
            FROM api_usage_logs 
            {where_clause} 
            GROUP BY fname, scan_day
            ORDER BY latest_date DESC 
            LIMIT 100
        """)
        stats['document_history'] = [
            {
                'filename': r[0] or 'Unknown Document',
                'date': r[1].isoformat() if r[1] else None,
                'endpoint': r[2],
                'model': r[3],
                'tokens': int(r[4] or 0),
                'cost_usd': float(r[5] or 0.0)
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
            SELECT {date_trunc_expr} as time_group, COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost_usd), 0)
            FROM api_usage_logs
            {where_clause}
            GROUP BY time_group
            ORDER BY time_group ASC
        """)
        stats['chart_data'] = [
            {
                'time_group': r[0].isoformat() if r[0] else None,
                'tokens': int(r[1] or 0),
                'cost_usd': float(r[2] or 0.0)
            }
            for r in cursor.fetchall()
        ]
        
        cursor.execute(f"""
            SELECT {date_trunc_expr} as time_group, COALESCE(model_name, 'gemini-2.5-flash'), COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0), COUNT(*)
            FROM api_usage_logs
            {where_clause}
            GROUP BY time_group, model_name
            ORDER BY time_group ASC
        """)
        stats['model_chart_data'] = [
            {
                'time_group': r[0].isoformat() if r[0] else None,
                'model_name': r[1],
                'prompt_tokens': int(r[2] or 0),
                'completion_tokens': int(r[3] or 0),
                'requests': r[4]
            }
            for r in cursor.fetchall()
        ]
        
        return stats
    except Exception as e:
        logger.error(f"Error getting API usage stats: {e}", exc_info=True)
        return default_stats
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def init_billing_credit():
    """Initializes the billing_credit table and migrates schema if needed."""
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
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS total_credit_thb DECIMAL(12, 2) DEFAULT 0.00;
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
        
        # Check if legacy balance column exists
        try:
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='billing_credit' AND column_name='balance') THEN
                        UPDATE billing_credit SET total_credit_thb = balance WHERE total_credit_thb = 0.00;
                    END IF;
                END $$;
            """)
        except Exception:
            pass
        
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_credit (
                id SERIAL PRIMARY KEY,
                total_credit_thb DECIMAL(12, 2) DEFAULT 0.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS total_credit_thb DECIMAL(12, 2) DEFAULT 0.00;
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
        conn.commit()
        cursor.execute("SELECT total_credit_thb FROM billing_credit ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_credit (
                id SERIAL PRIMARY KEY,
                total_credit_thb DECIMAL(12, 2) DEFAULT 0.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS total_credit_thb DECIMAL(12, 2) DEFAULT 0.00;
            ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        """)
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
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255),
                result_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        rj = json.dumps(result_json) if result_json is not None else None
        
        cursor.execute("""
            INSERT INTO ocr_history (filename, result_json)
            VALUES (%s, %s::jsonb)
            RETURNING id, created_at
        """, (filename, rj))
        
        row = cursor.fetchone()
        return {'id': str(row[0]), 'created_at': row[1].isoformat()} if row else None
    except Exception as e:
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
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255),
                result_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
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
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ocr_history WHERE id = %s::uuid", (history_id,))
        return True
    except Exception as e:
        logger.error(f"Error deleting ocr history: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
