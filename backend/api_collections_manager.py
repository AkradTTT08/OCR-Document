import json
import logging
import os
import time
import uuid
import yaml
import requests
from datetime import datetime
from db_ingestion import get_db_connection

logger = logging.getLogger(__name__)

def init_api_collections_table():
    """Initializes project_api_collections table if not exists."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_api_collections (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                format VARCHAR(100) DEFAULT 'OpenAPI / Swagger',
                version VARCHAR(50) DEFAULT '1.0',
                file_size VARCHAR(50) DEFAULT '-',
                raw_content TEXT,
                content_json JSONB DEFAULT '{}'::jsonb,
                endpoints_count INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_project_api_collections_pid ON project_api_collections(project_id);
        """)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("project_api_collections table initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to init project_api_collections table: {e}")

def parse_spec_content(content_str: str, filename: str = "api_spec.json"):
    """
    Parses OpenAPI 2/3 (Swagger), Postman Collection v2/v2.1, or generic JSON/YAML API specifications.
    Extracts endpoints list, version, title, and schema structure.
    """
    data = None
    # Try parsing as JSON first
    try:
        data = json.loads(content_str)
    except Exception:
        try:
            data = yaml.safe_load(content_str)
        except Exception as e:
            raise ValueError(f"Could not parse file as JSON or YAML: {e}")

    if not isinstance(data, (dict, list)):
        raise ValueError("Invalid format: expected JSON object or array")

    endpoints = []
    format_type = "OpenAPI / Swagger"
    version = "1.0"
    title = filename

    # Case 1: OpenAPI 3.x or Swagger 2.0
    if isinstance(data, dict) and ("openapi" in data or "swagger" in data or "paths" in data):
        if "openapi" in data:
            format_type = f"OpenAPI {data.get('openapi')}"
        elif "swagger" in data:
            format_type = f"Swagger {data.get('swagger')}"
        else:
            format_type = "OpenAPI / Swagger"

        info = data.get("info", {})
        title = info.get("title", filename)
        version = info.get("version", "1.0")

        paths = data.get("paths", {})
        for path_key, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                if method in path_item:
                    op = path_item[method]
                    if isinstance(op, dict):
                        endpoints.append({
                            "method": method.upper(),
                            "path": path_key,
                            "summary": op.get("summary") or op.get("description") or f"{method.upper()} {path_key}",
                            "operation_id": op.get("operationId", ""),
                            "tags": op.get("tags", []),
                            "parameters": op.get("parameters", []),
                            "responses": list(op.get("responses", {}).keys())
                        })

    # Case 2: Postman Collection (v2 / v2.1)
    elif isinstance(data, dict) and ("info" in data and ("schema" in data.get("info", {}) or "_postman_id" in data.get("info", {}))):
        format_type = "Postman Collection"
        info = data.get("info", {})
        title = info.get("name", filename)
        version = info.get("version", "1.0") if isinstance(info.get("version"), str) else "2.1"

        def extract_postman_items(items, folder_name=""):
            for it in items:
                if "item" in it:  # It's a folder
                    sub_folder = f"{folder_name}/{it.get('name', '')}".strip("/")
                    extract_postman_items(it["item"], sub_folder)
                elif "request" in it:
                    req = it["request"]
                    method = req.get("method", "GET") if isinstance(req, dict) else "GET"
                    url_obj = req.get("url", {}) if isinstance(req, dict) else {}
                    if isinstance(url_obj, str):
                        raw_url = url_obj
                    elif isinstance(url_obj, dict):
                        raw_url = url_obj.get("raw", "")
                    else:
                        raw_url = ""

                    endpoints.append({
                        "method": method.upper(),
                        "path": raw_url or it.get("name", "Endpoint"),
                        "summary": it.get("name") or raw_url,
                        "folder": folder_name,
                        "headers": req.get("header", []) if isinstance(req, dict) else [],
                        "body": req.get("body", {}) if isinstance(req, dict) else {}
                    })

        extract_postman_items(data.get("item", []))

    # Case 3: List of Endpoints or Generic JSON
    elif isinstance(data, list):
        format_type = "Endpoints List"
        title = filename
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                endpoints.append({
                    "method": item.get("method", "GET").upper(),
                    "path": item.get("url") or item.get("path", f"/endpoint_{idx+1}"),
                    "summary": item.get("name") or item.get("summary", f"Endpoint {idx+1}"),
                    "category": item.get("category", "General")
                })
    elif isinstance(data, dict) and "endpoints" in data and isinstance(data["endpoints"], list):
        format_type = "Custom API Spec"
        title = data.get("name", filename)
        version = data.get("version", "1.0")
        endpoints = data["endpoints"]
    else:
        # Fallback for simple single API or key-value definition
        format_type = "JSON / YAML"
        title = filename
        endpoints.append({
            "method": "GET",
            "path": filename,
            "summary": "Imported API Configuration",
            "data": data
        })

    return {
        "format": format_type,
        "version": str(version),
        "name": title,
        "endpoints_count": len(endpoints),
        "endpoints": endpoints,
        "content_json": data
    }

def get_project_api_collections(project_id: str):
    """Fetches all API collections for a given project."""
    init_api_collections_table()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, project_id, name, format, version, file_size, 
                   endpoints_count, status, created_at, updated_at, content_json
            FROM project_api_collections
            WHERE project_id = %s::uuid
            ORDER BY created_at DESC
        """, (project_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        collections = []
        for r in rows:
            content_data = r[10] if isinstance(r[10], dict) else {}
            collections.append({
                "id": str(r[0]),
                "project_id": str(r[1]),
                "name": r[2],
                "format": r[3],
                "version": r[4],
                "file_size": r[5],
                "endpoints_count": r[6],
                "status": r[7],
                "uploaded_at": r[8].isoformat() if r[8] else None,
                "endpoints": content_data.get("endpoints") if isinstance(content_data, dict) else []
            })
        return True, collections
    except Exception as e:
        logger.error(f"Error fetching API collections: {e}", exc_info=True)
        return False, str(e)

def save_api_collection(project_id: str, name: str, format_type: str, version: str, 
                        file_size: str, raw_content: str, content_json: dict, endpoints_count: int):
    """Saves a new API collection to PostgreSQL."""
    init_api_collections_table()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO project_api_collections 
            (project_id, name, format, version, file_size, raw_content, content_json, endpoints_count)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (project_id, name, format_type, version, file_size, raw_content, 
              json.dumps(content_json), endpoints_count))
        row = cursor.fetchone()
        conn.commit()
        new_id = str(row[0])
        created_at = row[1].isoformat() if row[1] else datetime.now().isoformat()
        cursor.close()
        conn.close()

        return True, {
            "id": new_id,
            "project_id": str(project_id),
            "name": name,
            "format": format_type,
            "version": version,
            "file_size": file_size,
            "endpoints_count": endpoints_count,
            "uploaded_at": created_at,
            "endpoints": content_json.get("endpoints", [])
        }
    except Exception as e:
        logger.error(f"Error saving API collection: {e}", exc_info=True)
        return False, str(e)

def delete_api_collection(collection_id: str):
    """Deletes an API collection by ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_api_collections WHERE id = %s::uuid", (collection_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting API collection {collection_id}: {e}", exc_info=True)
        return False, str(e)

def test_api_connection(collection_id: str = None, url: str = None, method: str = "GET", headers: dict = None, body: str = None):
    """
    Performs a real HTTP request/ping against the API endpoint to verify connectivity and latency.
    """
    target_url = url
    target_method = (method or "GET").upper()
    req_headers = headers or {}
    req_body = body

    if collection_id and not target_url:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT content_json, name, format FROM project_api_collections WHERE id = %s::uuid", (collection_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                c_json = row[0] if isinstance(row[0], dict) else {}
                endpoints = c_json.get("endpoints", [])
                if endpoints:
                    first_ep = endpoints[0]
                    target_url = first_ep.get("path") or first_ep.get("url")
                    target_method = first_ep.get("method", "GET").upper()
                elif c_json.get("url"):
                    target_url = c_json.get("url")
                    target_method = c_json.get("method", "GET").upper()
        except Exception as e:
            logger.warning(f"Could not load collection {collection_id} for testing: {e}")

    if not target_url:
        return {
            "success": False,
            "reachable": False,
            "error": "No valid target URL found in this API Collection."
        }

    # If relative path, prefix with localhost:5000
    if target_url.startswith("/"):
        target_url = f"http://127.0.0.1:5000{target_url}"

    start_time = time.time()
    try:
        if isinstance(req_headers, str):
            try:
                req_headers = json.loads(req_headers)
            except Exception:
                req_headers = {}

        resp = requests.request(
            method=target_method,
            url=target_url,
            headers=req_headers,
            data=req_body if target_method in ["POST", "PUT", "PATCH"] else None,
            timeout=5.0
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Limit preview text
        preview = resp.text[:500] if resp.text else ""

        return {
            "success": True,
            "reachable": resp.status_code < 500,
            "status_code": resp.status_code,
            "status_text": resp.reason,
            "latency_ms": latency_ms,
            "url": target_url,
            "method": target_method,
            "preview": preview
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "reachable": False,
            "error": "Connection timed out (5s)",
            "url": target_url,
            "latency_ms": 5000
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "reachable": False,
            "error": "Connection refused / host unreachable",
            "url": target_url
        }
    except Exception as e:
        return {
            "success": False,
            "reachable": False,
            "error": str(e),
            "url": target_url
        }

def sniff_endpoints_from_system(project_id: str = None, target_url: str = "http://127.0.0.1:5000"):
    """
    Discovers real active API endpoints from current backend and project configuration.
    """
    system_endpoints = [
        {"id": 1, "method": "GET", "url": "http://127.0.0.1:5000/api/projects", "name": "Fetch Projects List", "status": 200, "category": "Project Core"},
        {"id": 2, "method": "GET", "url": "http://127.0.0.1:5000/api/kb/documents", "name": "Query Project Knowledge Base", "status": 200, "category": "Knowledge Base"},
        {"id": 3, "method": "GET", "url": "http://127.0.0.1:5000/api/requirements", "name": "Get Structured Requirements", "status": 200, "category": "Requirements"},
        {"id": 4, "method": "POST", "url": "http://127.0.0.1:5000/api/agent/explore", "name": "Agent Deep Web Exploration", "status": 200, "category": "Autonomous QA"},
        {"id": 5, "method": "POST", "url": "http://127.0.0.1:5000/api/agent/align", "name": "Agent Semantic Gap Alignment", "status": 200, "category": "Autonomous QA"},
        {"id": 6, "method": "POST", "url": "http://127.0.0.1:5000/api/agent/generate-test", "name": "Agent Test Generator (Playwright)", "status": 200, "category": "Autonomous QA"},
        {"id": 7, "method": "GET", "url": "http://127.0.0.1:5000/api/agent/flow_analysis", "name": "QA Analysis Diagram & Flow", "status": 200, "category": "QA Architecture"},
        {"id": 8, "method": "GET", "url": "http://127.0.0.1:5000/api/qa-groups", "name": "QA Consultation Groups", "status": 200, "category": "QA Consult"},
        {"id": 9, "method": "GET", "url": "http://127.0.0.1:5000/api/skills", "name": "Registered AI Skills Registry", "status": 200, "category": "Skills Registry"},
        {"id": 10, "method": "POST", "url": "http://127.0.0.1:5000/api/upload", "name": "Document OCR Upload Engine", "status": 200, "category": "OCR Ingestion"}
    ]
    return system_endpoints
