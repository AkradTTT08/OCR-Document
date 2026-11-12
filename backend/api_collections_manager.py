import json
import logging
import os
import re
import time
import uuid
from urllib.parse import urlparse
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

    if collection_id:
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
                    if not target_url:
                        target_url = first_ep.get("path") or first_ep.get("url")
                    if not method or method == "GET":
                        target_method = (first_ep.get("method") or "GET").upper()
                    if not req_headers:
                        req_headers = first_ep.get("headers") or c_json.get("headers")
                    if not req_body:
                        req_body = first_ep.get("body") or c_json.get("body")
                elif c_json.get("url"):
                    if not target_url:
                        target_url = c_json.get("url")
                    if not method or method == "GET":
                        target_method = (c_json.get("method") or "GET").upper()
                    if not req_headers:
                        req_headers = c_json.get("headers")
                    if not req_body:
                        req_body = c_json.get("body")
        except Exception as e:
            logger.warning(f"Could not load collection {collection_id} for testing: {e}")

    if not target_url:
        return {
            "success": False,
            "reachable": False,
            "error": "No valid target URL found in this API Collection."
        }

    # Ensure req_headers is a dict
    if isinstance(req_headers, str):
        try:
            req_headers = json.loads(req_headers)
        except Exception:
            req_headers = {}
    elif not isinstance(req_headers, dict):
        req_headers = {}

    # If relative path, resolve against project's default_base_url or Origin/Referer
    if target_url.startswith("/"):
        base_host = None
        if collection_id:
            try:
                conn_p = get_db_connection()
                cur_p = conn_p.cursor()
                cur_p.execute("""
                    SELECT p.default_base_url 
                    FROM project_api_collections c
                    JOIN projects p ON c.project_id = p.project_id
                    WHERE c.id = %s::uuid
                """, (collection_id,))
                p_row = cur_p.fetchone()
                cur_p.close()
                conn_p.close()
                if p_row and p_row[0]:
                    base_host = p_row[0].strip().rstrip('/')
            except Exception:
                pass

        if not base_host:
            for hk, hv in req_headers.items():
                if hk.lower() in ['origin', 'referer'] and isinstance(hv, str) and hv.startswith('http'):
                    parsed_o = urlparse(hv)
                    base_host = f"{parsed_o.scheme}://{parsed_o.netloc}"
                    break

        if base_host:
            target_url = f"{base_host}{target_url}"
        else:
            target_url = f"http://127.0.0.1:5000{target_url}"

    # Ensure Content-Type is set if body is JSON
    if req_body and isinstance(req_body, str) and req_body.strip().startswith(("{", "[")):
        if not any(k.lower() == 'content-type' for k in req_headers):
            req_headers['Content-Type'] = 'application/json'

    start_time = time.time()
    try:
        resp = requests.request(
            method=target_method,
            url=target_url,
            headers=req_headers,
            data=req_body if target_method in ["POST", "PUT", "PATCH"] else None,
            timeout=8.0
        )
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Limit preview text
        preview = resp.text[:500] if resp.text else ""
        is_success = 200 <= resp.status_code < 400

        return {
            "success": is_success,
            "reachable": resp.status_code < 500,
            "is_success": is_success,
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

def get_project_all_endpoints(project_id: str):
    """
    Returns aggregated and deduplicated list of all API endpoints for a project from:
    1. project_api_collections (OpenAPI, Swagger, Postman, Manual, Extension)
    2. structured_requirements (Extracted requirement specifications with api_endpoints)
    """
    init_api_collections_table()
    endpoints = []
    seen = set()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch from project_api_collections
        cursor.execute("""
            SELECT id, name, content_json, format
            FROM project_api_collections
            WHERE project_id = %s::uuid
            ORDER BY created_at DESC
        """, (project_id,))
        collections = cursor.fetchall()

        for col_id, col_name, c_json, col_format in collections:
            content_data = c_json if isinstance(c_json, dict) else {}
            col_eps = content_data.get("endpoints") or []
            for ep in col_eps:
                if not isinstance(ep, dict):
                    continue
                method = (ep.get("method") or "GET").strip().upper()
                raw_path = (ep.get("path") or ep.get("url") or "").strip()
                if "://" in raw_path:
                    try:
                        p_obj = urlparse(raw_path)
                        path = p_obj.path or "/"
                        if p_obj.query:
                            path += f"?{p_obj.query}"
                    except Exception:
                        path = raw_path
                else:
                    path = raw_path if raw_path.startswith("/") else f"/{raw_path}"

                name = ep.get("summary") or ep.get("name") or path
                key = (method, path)
                if key not in seen and path:
                    seen.add(key)
                    endpoints.append({
                        "id": len(endpoints) + 1,
                        "method": method,
                        "path": path,
                        "name": name,
                        "source": f"Collection: {col_name}",
                        "collection_id": str(col_id)
                    })

        # 2. Fetch from structured_requirements
        cursor.execute("""
            SELECT req_id, req_code, title, api_endpoints
            FROM structured_requirements
            WHERE project_id = %s::uuid AND api_endpoints IS NOT NULL
            ORDER BY req_code ASC
        """, (project_id,))
        req_rows = cursor.fetchall()

        for req_id, req_code, title, api_list in req_rows:
            if not isinstance(api_list, list):
                continue
            for item in api_list:
                if isinstance(item, str):
                    s = item.strip()
                    m = re.match(r'^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(.+)$', s, re.I)
                    if m:
                        method = m.group(1).upper()
                        raw_path = m.group(2).strip()
                    elif s.startswith('/'):
                        method = "GET"
                        raw_path = s
                    else:
                        method = "POST"
                        clean_slug = re.sub(r'[^a-zA-Z0-9]+', '-', s.lower()).strip('-')
                        raw_path = f"/api/{clean_slug}"

                    if "://" in raw_path:
                        try:
                            p_obj = urlparse(raw_path)
                            path = p_obj.path or "/"
                            if p_obj.query:
                                path += f"?{p_obj.query}"
                        except Exception:
                            path = raw_path
                    else:
                        path = raw_path if raw_path.startswith("/") else f"/{raw_path}"

                    name = f"{title} ({req_code})" if title else s
                    key = (method, path)
                    if key not in seen and path:
                        seen.add(key)
                        endpoints.append({
                            "id": len(endpoints) + 1,
                            "method": method,
                            "path": path,
                            "name": name,
                            "source": f"Requirement: {req_code}",
                            "req_id": str(req_id)
                        })
                elif isinstance(item, dict):
                    method = (item.get("method") or "GET").strip().upper()
                    raw_path = (item.get("path") or item.get("url") or "").strip()
                    path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
                    name = item.get("name") or item.get("summary") or (f"{title} ({req_code})" if title else path)
                    key = (method, path)
                    if key not in seen and path:
                        seen.add(key)
                        endpoints.append({
                            "id": len(endpoints) + 1,
                            "method": method,
                            "path": path,
                            "name": name,
                            "source": f"Requirement: {req_code}",
                            "req_id": str(req_id)
                        })

        cursor.close()
        conn.close()
        return True, endpoints
    except Exception as e:
        logger.error(f"Error fetching all project endpoints: {e}", exc_info=True)
        return False, str(e)

def sniff_endpoints_from_system(project_id: str = None, target_url: str = "http://127.0.0.1:5000"):
    """
    Discovers real active API endpoints from current backend and project configuration.
    """
    base_target = (target_url or "http://127.0.0.1:5000").rstrip("/")
    results = []

    # If project_id provided, include project's actual APIs first
    if project_id:
        try:
            ok, proj_eps = get_project_all_endpoints(project_id)
            if ok and proj_eps:
                for ep in proj_eps:
                    results.append({
                        "id": ep["id"],
                        "method": ep["method"],
                        "url": f"{base_target}{ep['path']}",
                        "path": ep["path"],
                        "name": ep["name"],
                        "status": 200,
                        "category": ep.get("source", "Project API")
                    })
        except Exception as e:
            logger.warn(f"Could not load project endpoints for sniffer: {e}")

    # Standard system endpoints for discovery
    system_endpoints = [
        {"id": len(results) + 1, "method": "GET", "url": f"{base_target}/api/projects", "path": "/api/projects", "name": "Fetch Projects List", "status": 200, "category": "Project Core"},
        {"id": len(results) + 2, "method": "GET", "url": f"{base_target}/api/kb/documents", "path": "/api/kb/documents", "name": "Query Project Knowledge Base", "status": 200, "category": "Knowledge Base"},
        {"id": len(results) + 3, "method": "GET", "url": f"{base_target}/api/requirements", "path": "/api/requirements", "name": "Get Structured Requirements", "status": 200, "category": "Requirements"},
        {"id": len(results) + 4, "method": "POST", "url": f"{base_target}/api/agent/explore", "path": "/api/agent/explore", "name": "Agent Deep Web Exploration", "status": 200, "category": "Autonomous QA"},
        {"id": len(results) + 5, "method": "POST", "url": f"{base_target}/api/agent/align", "path": "/api/agent/align", "name": "Agent Semantic Gap Alignment", "status": 200, "category": "Autonomous QA"},
        {"id": len(results) + 6, "method": "POST", "url": f"{base_target}/api/agent/generate-test", "path": "/api/agent/generate-test", "name": "Agent Test Generator (Playwright)", "status": 200, "category": "Autonomous QA"},
        {"id": len(results) + 7, "method": "GET", "url": f"{base_target}/api/agent/flow_analysis", "path": "/api/agent/flow_analysis", "name": "QA Analysis Diagram & Flow", "status": 200, "category": "QA Architecture"},
        {"id": len(results) + 8, "method": "GET", "url": f"{base_target}/api/qa-groups", "path": "/api/qa-groups", "name": "QA Consultation Groups", "status": 200, "category": "QA Consult"},
        {"id": len(results) + 9, "method": "GET", "url": f"{base_target}/api/skills", "path": "/api/skills", "name": "Registered AI Skills Registry", "status": 200, "category": "Skills Registry"},
        {"id": len(results) + 10, "method": "POST", "url": f"{base_target}/api/upload", "path": "/api/upload", "name": "Document OCR Upload Engine", "status": 200, "category": "OCR Ingestion"}
    ]

    # Combine ensuring unique (method, path)
    seen = {(r["method"], r["path"]) for r in results if "path" in r}
    for sys_ep in system_endpoints:
        key = (sys_ep["method"], sys_ep["path"])
        if key not in seen:
            seen.add(key)
            results.append(sys_ep)

    return results
