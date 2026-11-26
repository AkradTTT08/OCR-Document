import base64
import json
import logging
import os
import re
import time
import uuid
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
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


def _is_blocked_metadata_url(url_str: str) -> bool:
    """Blocks cloud instance metadata SSRF targets while allowing legitimate project/staging/local test URLs."""
    try:
        parsed = urlparse(url_str)
        host = (parsed.hostname or "").lower().strip()
        if host in ("169.254.169.254", "metadata.google.internal", "100.100.100.200", "fd00:ec2::254"):
            return True
        if parsed.scheme not in ("http", "https"):
            return True
        return False
    except Exception:
        return True


def _normalize_endpoint_entry(ep: dict, idx: int = 1) -> dict:
    """Normalizes an endpoint dict so every collection format exposes consistent keys for the UI & Test Runner."""
    if not isinstance(ep, dict):
        return {
            "id": f"ep-{idx}",
            "method": "GET",
            "path": f"/endpoint_{idx}",
            "url": f"/endpoint_{idx}",
            "summary": f"Endpoint {idx}",
            "category": "General",
            "headers": {},
            "query_params": [],
            "auth_config": {"type": "none"},
            "body": "",
            "responses": []
        }

    method = str(ep.get("method") or "GET").strip().upper()
    raw_path = str(ep.get("path") or ep.get("url") or f"/endpoint_{idx}").strip()
    summary = str(ep.get("summary") or ep.get("name") or f"{method} {raw_path}").strip()
    category = str(ep.get("category") or ep.get("folder") or (ep.get("tags", [None])[0] if isinstance(ep.get("tags"), list) and ep.get("tags") else "") or "General").strip()

    raw_headers = ep.get("headers")
    norm_headers = {}
    if isinstance(raw_headers, dict):
        norm_headers = raw_headers
    elif isinstance(raw_headers, str) and raw_headers.strip():
        try:
            parsed_h = json.loads(raw_headers)
            if isinstance(parsed_h, dict):
                norm_headers = parsed_h
        except Exception:
            norm_headers = {}
    elif isinstance(raw_headers, list):
        for h_it in raw_headers:
            if isinstance(h_it, dict) and h_it.get("key"):
                if not h_it.get("disabled", False) and h_it.get("enabled", True):
                    norm_headers[str(h_it["key"]).strip()] = str(h_it.get("value") or "")

    raw_body = ep.get("body")
    norm_body = ""
    if isinstance(raw_body, str):
        norm_body = raw_body
    elif isinstance(raw_body, dict):
        if "raw" in raw_body and isinstance(raw_body["raw"], str):
            norm_body = raw_body["raw"]
        elif raw_body:
            norm_body = json.dumps(raw_body, ensure_ascii=False, indent=2)
    elif isinstance(raw_body, list):
        norm_body = json.dumps(raw_body, ensure_ascii=False, indent=2)

    return {
        "id": str(ep.get("id") or f"ep-{idx}-{uuid.uuid4().hex[:6]}"),
        "method": method,
        "path": raw_path,
        "url": str(ep.get("url") or raw_path),
        "summary": summary,
        "name": summary,
        "description": str(ep.get("description") or ""),
        "category": category,
        "folder": category,
        "operation_id": str(ep.get("operation_id") or ""),
        "tags": ep.get("tags") if isinstance(ep.get("tags"), list) else ([category] if category else []),
        "parameters": ep.get("parameters") if isinstance(ep.get("parameters"), list) else [],
        "query_params": ep.get("query_params") if isinstance(ep.get("query_params"), list) else [],
        "auth_config": ep.get("auth_config") if isinstance(ep.get("auth_config"), dict) else {"type": "none"},
        "headers": norm_headers,
        "body": norm_body,
        "curl": str(ep.get("curl") or ""),
        "responseBody": str(ep.get("responseBody") or ep.get("expected_response") or ""),
        "responses": ep.get("responses") if isinstance(ep.get("responses"), list) else []
    }


def parse_spec_content(content_str: str, filename: str = "api_spec.json"):
    """
    Parses OpenAPI 2/3 (Swagger), Postman Collection v2/v2.1, or generic JSON/YAML API specifications.
    Extracts endpoints list, version, title, base_url, and schema structure.
    """
    data = None
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
    base_url = ""

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

        # Extract servers / host base_url if defined in spec
        if isinstance(data.get("servers"), list) and data["servers"]:
            first_srv = data["servers"][0]
            if isinstance(first_srv, dict) and first_srv.get("url"):
                base_url = str(first_srv["url"]).strip().rstrip("/")
        elif data.get("host"):
            scheme = (data.get("schemes") or ["https"])[0]
            bp = str(data.get("basePath") or "").rstrip("/")
            base_url = f"{scheme}://{data['host']}{bp}"

        paths = data.get("paths", {})
        ep_counter = 0
        for path_key, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
                if method in path_item:
                    op = path_item[method]
                    if isinstance(op, dict):
                        ep_counter += 1
                        sample_body = ""
                        req_body_spec = op.get("requestBody")
                        if isinstance(req_body_spec, dict):
                            content_map = req_body_spec.get("content", {})
                            json_media = content_map.get("application/json", {}) if isinstance(content_map, dict) else {}
                            if isinstance(json_media, dict):
                                ex = json_media.get("example")
                                if ex is not None:
                                    sample_body = json.dumps(ex, ensure_ascii=False, indent=2) if not isinstance(ex, str) else ex

                        tags_list = op.get("tags", [])
                        cat = tags_list[0] if isinstance(tags_list, list) and tags_list else "General"
                        endpoints.append(_normalize_endpoint_entry({
                            "id": f"ep-{ep_counter}",
                            "method": method.upper(),
                            "path": path_key,
                            "url": f"{base_url}{path_key}" if (base_url and str(path_key).startswith("/")) else path_key,
                            "summary": op.get("summary") or op.get("description") or f"{method.upper()} {path_key}",
                            "description": op.get("description") or "",
                            "category": cat,
                            "operation_id": op.get("operationId", ""),
                            "tags": tags_list,
                            "parameters": op.get("parameters", []),
                            "body": sample_body,
                            "responses": list(op.get("responses", {}).keys())
                        }, ep_counter))

    # Case 2: Postman Collection (v2 / v2.1)
    elif isinstance(data, dict) and ("info" in data and ("schema" in data.get("info", {}) or "_postman_id" in data.get("info", {}))):
        format_type = "Postman Collection"
        info = data.get("info", {})
        title = info.get("name", filename)
        version = info.get("version", "1.0") if isinstance(info.get("version"), str) else "2.1"

        # Check collection variables for baseUrl / base_url
        if isinstance(data.get("variable"), list):
            for v in data["variable"]:
                if isinstance(v, dict) and str(v.get("key") or "").lower() in ("baseurl", "base_url", "host", "url"):
                    val = str(v.get("value") or "").strip().rstrip("/")
                    if val.startswith("http"):
                        base_url = val
                        break

        def extract_postman_items(items, folder_name=""):
            for it in items:
                if not isinstance(it, dict):
                    continue
                if "item" in it and isinstance(it["item"], list):
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

                    if base_url:
                        raw_url = re.sub(r"\{\{\s*(?:baseUrl|base_url|host|url)\s*\}\}", base_url, raw_url, flags=re.I)

                    idx_curr = len(endpoints) + 1
                    endpoints.append(_normalize_endpoint_entry({
                        "id": f"ep-{idx_curr}",
                        "method": method.upper(),
                        "path": raw_url or it.get("name", "Endpoint"),
                        "url": raw_url or it.get("name", "Endpoint"),
                        "summary": it.get("name") or raw_url,
                        "category": folder_name or "General",
                        "folder": folder_name or "General",
                        "headers": req.get("header", []) if isinstance(req, dict) else [],
                        "body": req.get("body", {}) if isinstance(req, dict) else {}
                    }, idx_curr))

        extract_postman_items(data.get("item", []))

    # Case 3: List of Endpoints or Generic JSON
    elif isinstance(data, list):
        format_type = "Endpoints List"
        title = filename
        for idx, item in enumerate(data, 1):
            if isinstance(item, dict):
                endpoints.append(_normalize_endpoint_entry(item, idx))
    elif isinstance(data, dict) and "endpoints" in data and isinstance(data["endpoints"], list):
        format_type = data.get("format") or "Custom API Spec"
        title = data.get("name", filename)
        version = data.get("version", "1.0")
        base_url = str(data.get("base_url") or "").strip().rstrip("/")
        endpoints = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(data["endpoints"], 1)]
    else:
        format_type = "JSON / YAML"
        title = filename
        endpoints.append(_normalize_endpoint_entry({
            "method": "GET",
            "path": filename,
            "summary": "Imported API Configuration",
            "body": json.dumps(data, ensure_ascii=False, indent=2)
        }, 1))

    content_obj = data if isinstance(data, dict) else {"endpoints": endpoints}
    content_obj["endpoints"] = endpoints
    if base_url and not content_obj.get("base_url"):
        content_obj["base_url"] = base_url

    return {
        "format": format_type,
        "version": str(version),
        "name": title,
        "base_url": base_url,
        "endpoints_count": len(endpoints),
        "endpoints": endpoints,
        "content_json": content_obj
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
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
        """, (project_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        collections = []
        for r in rows:
            content_data = r[10] if isinstance(r[10], dict) else {}
            raw_eps = content_data.get("endpoints") if isinstance(content_data, dict) else []
            norm_eps = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(raw_eps or [], 1)]
            ep_count = len(norm_eps) or r[6] or 0
            created_iso = r[8].isoformat() if r[8] else None
            updated_iso = r[9].isoformat() if r[9] else created_iso
            collections.append({
                "id": str(r[0]),
                "project_id": str(r[1]),
                "name": r[2],
                "format": r[3],
                "format_type": r[3],
                "version": r[4],
                "file_size": r[5],
                "endpoints_count": ep_count,
                "endpoint_count": ep_count,
                "status": r[7],
                "base_url": str(content_data.get("base_url") or ""),
                "uploaded_at": created_iso,
                "created_at": updated_iso or created_iso,
                "updated_at": updated_iso,
                "endpoints": norm_eps
            })
        return True, collections
    except Exception as e:
        logger.error(f"Error fetching API collections: {e}", exc_info=True)
        return False, str(e)


def get_api_collection_by_id(collection_id: str):
    """Fetches a single API collection by ID including raw_content and content_json for export/editing."""
    init_api_collections_table()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, project_id, name, format, version, file_size,
                   endpoints_count, status, created_at, updated_at, content_json, raw_content
            FROM project_api_collections
            WHERE id = %s::uuid
        """, (collection_id,))
        r = cursor.fetchone()
        cursor.close()
        conn.close()
        if not r:
            return False, "Collection not found"

        content_data = r[10] if isinstance(r[10], dict) else {}
        raw_eps = content_data.get("endpoints") if isinstance(content_data, dict) else []
        norm_eps = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(raw_eps or [], 1)]
        ep_count = len(norm_eps) or r[6] or 0
        created_iso = r[8].isoformat() if r[8] else None
        updated_iso = r[9].isoformat() if r[9] else created_iso
        return True, {
            "id": str(r[0]),
            "project_id": str(r[1]),
            "name": r[2],
            "format": r[3],
            "format_type": r[3],
            "version": r[4],
            "file_size": r[5],
            "endpoints_count": ep_count,
            "endpoint_count": ep_count,
            "status": r[7],
            "base_url": str(content_data.get("base_url") or ""),
            "uploaded_at": created_iso,
            "created_at": updated_iso or created_iso,
            "updated_at": updated_iso,
            "endpoints": norm_eps,
            "content_json": content_data,
            "raw_content": r[11]
        }
    except Exception as e:
        logger.error(f"Error fetching collection {collection_id}: {e}", exc_info=True)
        return False, str(e)


def save_api_collection(project_id: str, name: str, format_type: str, version: str,
                        file_size: str, raw_content: str, content_json: dict, endpoints_count: int):
    """Saves a new API collection to PostgreSQL."""
    init_api_collections_table()
    try:
        c_dict = content_json if isinstance(content_json, dict) else {"endpoints": []}
        raw_eps = c_dict.get("endpoints") if isinstance(c_dict.get("endpoints"), list) else []
        norm_eps = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(raw_eps, 1)]
        c_dict["endpoints"] = norm_eps
        final_count = len(norm_eps) or endpoints_count or 0
        if not file_size or file_size == "-":
            raw_str = raw_content or json.dumps(c_dict, ensure_ascii=False)
            file_size = f"{max(0.1, len(raw_str.encode('utf-8')) / 1024):.1f} KB"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO project_api_collections 
            (project_id, name, format, version, file_size, raw_content, content_json, endpoints_count)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (project_id, name, format_type, version, file_size, raw_content,
              json.dumps(c_dict, ensure_ascii=False), final_count))
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
            "base_url": str(c_dict.get("base_url") or ""),
            "endpoints_count": final_count,
            "uploaded_at": created_at,
            "endpoints": norm_eps
        }
    except Exception as e:
        logger.error(f"Error saving API collection: {e}", exc_info=True)
        return False, str(e)


def update_api_collection(collection_id: str, name: str = None, version: str = None,
                          base_url: str = None, endpoints: list = None, format_type: str = None):
    """Updates an existing API collection's metadata, base_url, and/or endpoints list."""
    init_api_collections_table()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT project_id, name, format, version, content_json, created_at
            FROM project_api_collections
            WHERE id = %s::uuid
        """, (collection_id,))
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return False, "Collection not found"

        project_id, cur_name, cur_format, cur_ver, cur_json, created_at = row
        c_dict = cur_json if isinstance(cur_json, dict) else {}

        next_name = (name.strip() if isinstance(name, str) and name.strip() else cur_name)
        next_ver = (version.strip() if isinstance(version, str) and version.strip() else cur_ver)
        next_format = (format_type.strip() if isinstance(format_type, str) and format_type.strip() else cur_format)

        if base_url is not None:
            c_dict["base_url"] = str(base_url).strip().rstrip("/")

        if isinstance(endpoints, list):
            norm_eps = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(endpoints, 1)]
            c_dict["endpoints"] = norm_eps
        else:
            raw_eps = c_dict.get("endpoints") if isinstance(c_dict.get("endpoints"), list) else []
            norm_eps = [_normalize_endpoint_entry(ep, idx) for idx, ep in enumerate(raw_eps, 1)]
            c_dict["endpoints"] = norm_eps

        c_dict["name"] = next_name
        c_dict["version"] = next_ver
        next_raw = json.dumps(c_dict, ensure_ascii=False, indent=2)
        next_size = f"{max(0.1, len(next_raw.encode('utf-8')) / 1024):.1f} KB"
        next_count = len(norm_eps)

        cursor.execute("""
            UPDATE project_api_collections
            SET name = %s,
                format = %s,
                version = %s,
                file_size = %s,
                raw_content = %s,
                content_json = %s,
                endpoints_count = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s::uuid
            RETURNING updated_at
        """, (next_name, next_format, next_ver, next_size, next_raw,
              json.dumps(c_dict, ensure_ascii=False), next_count, collection_id))
        u_row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return True, {
            "id": str(collection_id),
            "project_id": str(project_id),
            "name": next_name,
            "format": next_format,
            "version": next_ver,
            "file_size": next_size,
            "base_url": str(c_dict.get("base_url") or ""),
            "endpoints_count": next_count,
            "uploaded_at": created_at.isoformat() if created_at else None,
            "updated_at": u_row[0].isoformat() if (u_row and u_row[0]) else datetime.now().isoformat(),
            "endpoints": norm_eps
        }
    except Exception as e:
        logger.error(f"Error updating API collection {collection_id}: {e}", exc_info=True)
        return False, str(e)


def append_endpoints_to_collection(collection_id: str, new_endpoints: list):
    """Appends one or more endpoints to an existing collection."""
    ok, col = get_api_collection_by_id(collection_id)
    if not ok:
        return False, col
    existing_eps = col.get("endpoints") or []
    combined = list(existing_eps)
    for ep in (new_endpoints or []):
        combined.append(_normalize_endpoint_entry(ep, len(combined) + 1))
    return update_api_collection(collection_id, endpoints=combined)


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


def _apply_query_and_auth(target_url: str, req_headers: dict, query_params=None, auth_config=None):
    """Applies structured query_params and auth_config (Bearer, API Key, Basic Auth) to URL and headers."""
    extra_params = []
    if isinstance(query_params, list):
        for qp in query_params:
            if isinstance(qp, dict) and qp.get("key") and qp.get("enabled", True):
                extra_params.append((str(qp["key"]).strip(), str(qp.get("value") or "")))
    elif isinstance(query_params, dict):
        for k, v in query_params.items():
            if k:
                extra_params.append((str(k).strip(), str(v or "")))

    if isinstance(auth_config, dict):
        auth_type = str(auth_config.get("type") or "none").lower()
        if auth_type == "bearer" and auth_config.get("token"):
            tok = str(auth_config["token"]).strip()
            req_headers["Authorization"] = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"
        elif auth_type == "apikey" and auth_config.get("key"):
            k_name = str(auth_config["key"]).strip()
            k_val = str(auth_config.get("value") or "")
            if str(auth_config.get("in") or "header").lower() == "query":
                extra_params.append((k_name, k_val))
            else:
                req_headers[k_name] = k_val
        elif auth_type == "basic" and (auth_config.get("username") or auth_config.get("password")):
            u = str(auth_config.get("username") or "")
            p = str(auth_config.get("password") or "")
            b64 = base64.b64encode(f"{u}:{p}".encode("utf-8")).decode("ascii")
            req_headers["Authorization"] = f"Basic {b64}"

    if extra_params:
        try:
            parsed_u = urlparse(target_url)
            current_q = parse_qsl(parsed_u.query, keep_blank_values=True)
            existing_keys = {k for k, _ in extra_params}
            merged_q = [(k, v) for k, v in current_q if k not in existing_keys] + extra_params
            target_url = urlunparse(parsed_u._replace(query=urlencode(merged_q)))
        except Exception:
            pass

    return target_url, req_headers


def test_api_connection(collection_id: str = None, url: str = None, method: str = None,
                        headers=None, body: str = None, query_params=None,
                        auth_config=None, endpoint_index: int = 0, base_url_override: str = None):
    """
    Performs a real HTTP request against an API endpoint (either by collection_id + endpoint_index
    or direct URL/Method/Headers/Body from the API Studio) and returns full response telemetry.
    """
    target_url = (url or "").strip()
    target_method = (method or "").strip().upper()
    req_headers = headers
    req_body = body
    col_base_url = (base_url_override or "").strip().rstrip("/")
    ep_query_params = query_params
    ep_auth_config = auth_config

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
                if not col_base_url and c_json.get("base_url"):
                    col_base_url = str(c_json.get("base_url")).strip().rstrip("/")
                endpoints = c_json.get("endpoints", [])
                if endpoints:
                    safe_idx = max(0, min(int(endpoint_index or 0), len(endpoints) - 1))
                    chosen_ep = endpoints[safe_idx]
                    if not target_url:
                        target_url = chosen_ep.get("url") or chosen_ep.get("path") or ""
                    if not target_method:
                        target_method = (chosen_ep.get("method") or "GET").upper()
                    if req_headers is None:
                        req_headers = chosen_ep.get("headers") or c_json.get("headers")
                    if req_body is None:
                        req_body = chosen_ep.get("body") or c_json.get("body")
                    if ep_query_params is None:
                        ep_query_params = chosen_ep.get("query_params")
                    if ep_auth_config is None:
                        ep_auth_config = chosen_ep.get("auth_config")
                elif c_json.get("url"):
                    if not target_url:
                        target_url = c_json.get("url")
                    if not target_method:
                        target_method = (c_json.get("method") or "GET").upper()
                    if req_headers is None:
                        req_headers = c_json.get("headers")
                    if req_body is None:
                        req_body = c_json.get("body")
        except Exception as e:
            logger.warning(f"Could not load collection {collection_id} for testing: {e}")

    if not target_method:
        target_method = "GET"

    if not target_url:
        return {
            "success": False,
            "reachable": False,
            "error": "ไม่พบ URL ปลายทางสำหรับทดสอบ กรุณาระบุ Endpoint URL หรือตั้งค่า Base URL"
        }

    # Normalize headers into a clean dict
    norm_headers = {}
    if isinstance(req_headers, str) and req_headers.strip():
        try:
            parsed_h = json.loads(req_headers)
            if isinstance(parsed_h, dict):
                norm_headers = {str(k): str(v) for k, v in parsed_h.items() if k}
        except Exception:
            norm_headers = {}
    elif isinstance(req_headers, dict):
        norm_headers = {str(k): str(v) for k, v in req_headers.items() if k and v is not None}
    elif isinstance(req_headers, list):
        for h_item in req_headers:
            if isinstance(h_item, dict) and h_item.get("key") and h_item.get("enabled", True):
                norm_headers[str(h_item["key"]).strip()] = str(h_item.get("value") or "")

    # Resolve relative path against base_url_override -> collection base_url -> project.default_base_url -> Origin -> 127.0.0.1:5000
    if target_url.startswith("/"):
        base_host = col_base_url
        if not base_host and collection_id:
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
            for hk, hv in norm_headers.items():
                if hk.lower() in ['origin', 'referer'] and isinstance(hv, str) and hv.startswith('http'):
                    parsed_o = urlparse(hv)
                    base_host = f"{parsed_o.scheme}://{parsed_o.netloc}"
                    break

        if base_host:
            target_url = f"{base_host}{target_url}"
        else:
            target_url = f"http://127.0.0.1:5000{target_url}"
    elif not target_url.startswith(("http://", "https://")):
        if col_base_url:
            target_url = f"{col_base_url}/{target_url.lstrip('/')}"
        else:
            target_url = f"https://{target_url}"

    target_url, norm_headers = _apply_query_and_auth(
        target_url, norm_headers, query_params=ep_query_params, auth_config=ep_auth_config
    )

    if _is_blocked_metadata_url(target_url):
        return {
            "success": False,
            "reachable": False,
            "error": "URL ปลายทางถูกบล็อกตามนโยบายความปลอดภัย (SSRF Metadata Protection)",
            "url": target_url,
            "method": target_method
        }

    if isinstance(req_body, (dict, list)):
        req_body = json.dumps(req_body, ensure_ascii=False)

    if req_body and isinstance(req_body, str) and req_body.strip().startswith(("{", "[")):
        if not any(k.lower() == 'content-type' for k in norm_headers):
            norm_headers['Content-Type'] = 'application/json'

    start_time = time.time()
    try:
        send_data = req_body.encode("utf-8") if (req_body and isinstance(req_body, str) and target_method in ["POST", "PUT", "PATCH", "DELETE"]) else None
        resp = requests.request(
            method=target_method,
            url=target_url,
            headers=norm_headers,
            data=send_data,
            timeout=8.0
        )
        latency_ms = int((time.time() - start_time) * 1000)
        raw_text = resp.text or ""
        size_bytes = len(resp.content or b"")

        # Pretty-print JSON response if applicable
        formatted_body = raw_text[:50000]
        try:
            parsed_json = resp.json()
            formatted_body = json.dumps(parsed_json, ensure_ascii=False, indent=2)[:50000]
        except Exception:
            pass

        preview = raw_text[:500] if raw_text else ""
        is_success = 200 <= resp.status_code < 400
        resp_headers_dict = {str(k): str(v) for k, v in list(resp.headers.items())[:40]}

        return {
            "success": is_success,
            "reachable": resp.status_code < 500,
            "is_success": is_success,
            "status_code": resp.status_code,
            "status_text": resp.reason or ("OK" if is_success else "Error"),
            "latency_ms": latency_ms,
            "response_size_bytes": size_bytes,
            "url": target_url,
            "method": target_method,
            "response_headers": resp_headers_dict,
            "response_body": formatted_body,
            "preview": preview
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "reachable": False,
            "error": "หมดเวลาเชื่อมต่อ (Connection timed out หลังรอ 8 วินาที)",
            "url": target_url,
            "method": target_method,
            "latency_ms": 8000
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "reachable": False,
            "error": f"ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ปลายทางได้ ({target_url})",
            "url": target_url,
            "method": target_method
        }
    except Exception as e:
        return {
            "success": False,
            "reachable": False,
            "error": str(e),
            "url": target_url,
            "method": target_method
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
                        "url": ep.get("url") or path,
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
    Discovers API endpoints from target_url by probing standard OpenAPI/Swagger manifest paths
    (/openapi.json, /swagger.json, /api-docs, /v3/api-docs) and scanning page script references,
    plus including the project's registered endpoints when scanning the local workspace.
    """
    raw_target = (target_url or "http://127.0.0.1:5000").strip()
    if not raw_target.startswith(("http://", "https://")):
        raw_target = f"https://{raw_target}"

    parsed_t = urlparse(raw_target)
    base_origin = f"{parsed_t.scheme}://{parsed_t.netloc}".rstrip("/")
    base_target = raw_target.rstrip("/")
    results = []
    seen = set()

    def _add_ep(method: str, path_or_url: str, name: str, category: str = "Discovered API", status: int = 200):
        m = (method or "GET").upper()
        p_raw = (path_or_url or "").strip()
        if not p_raw:
            return
        if p_raw.startswith(("http://", "https://")):
            full_u = p_raw
            p_only = urlparse(p_raw).path or "/"
        else:
            p_only = p_raw if p_raw.startswith("/") else f"/{p_raw}"
            full_u = f"{base_origin}{p_only}"
        key = (m, p_only)
        if key not in seen:
            seen.add(key)
            results.append({
                "id": len(results) + 1,
                "method": m,
                "url": full_u,
                "path": p_only,
                "name": name or f"{m} {p_only}",
                "summary": name or f"{m} {p_only}",
                "status": status,
                "category": category
            })

    # 1. Probe target_url directly (and common OpenAPI/Swagger manifest paths) if not blocked by SSRF
    if not _is_blocked_metadata_url(base_target):
        probe_candidates = [base_target]
        for suffix in ["/openapi.json", "/swagger.json", "/v3/api-docs", "/api/openapi.json", "/api/swagger.json", "/api-docs"]:
            cand = f"{base_origin}{suffix}"
            if cand not in probe_candidates:
                probe_candidates.append(cand)

        for cand_url in probe_candidates:
            try:
                resp = requests.get(cand_url, timeout=3.5, headers={"Accept": "application/json, text/html, */*"})
                if resp.status_code >= 400 or not resp.text:
                    continue
                txt = resp.text.strip()
                # Check if response is an OpenAPI/Swagger/Postman JSON spec
                if txt.startswith(("{", "[")):
                    try:
                        parsed_spec = parse_spec_content(txt, urlparse(cand_url).path.lstrip("/") or "openapi.json")
                        for ep in parsed_spec.get("endpoints", []):
                            _add_ep(ep.get("method"), ep.get("path"), ep.get("summary"), ep.get("category") or "OpenAPI Spec", resp.status_code)
                        if results:
                            break
                    except Exception:
                        pass
                # Otherwise scan HTML/JS for /api/... or /v1/... endpoint patterns
                for match in re.findall(r'["\']((?:/api|/v[1-3])/[a-zA-Z0-9_\-/]+)["\']', txt):
                    _add_ep("GET", match, f"Discovered {match}", "HTML/Script Scan", 200)
            except Exception:
                continue

    # 2. Include existing project endpoints mapped to base_origin
    if project_id:
        try:
            ok, proj_eps = get_project_all_endpoints(project_id)
            if ok and proj_eps:
                for ep in proj_eps:
                    _add_ep(ep["method"], ep["path"], ep["name"], ep.get("source", "Project API"), 200)
        except Exception as e:
            logger.warning(f"Could not load project endpoints for sniffer: {e}")

    # 3. Only include Spectra QA internal endpoints if the user is scanning localhost / 127.0.0.1
    is_local_scan = any(h in (parsed_t.hostname or "").lower() for h in ("localhost", "127.0.0.1"))
    if is_local_scan or not results:
        system_endpoints = [
            ("GET", "/api/projects", "Fetch Projects List", "Project Core"),
            ("GET", "/api/kb/documents", "Query Project Knowledge Base", "Knowledge Base"),
            ("GET", "/api/requirements", "Get Structured Requirements", "Requirements"),
            ("GET", "/api/exit-criteria/templates", "Get Exit Criteria Templates", "Quality Gate"),
            ("GET", "/api/skills", "Registered AI Skills Registry", "Skills Registry"),
            ("POST", "/api/agent/explore", "Agent Deep Web Exploration", "Autonomous QA"),
            ("POST", "/api/agent/generate-test", "Agent Test Generator (Playwright)", "Autonomous QA"),
            ("GET", "/api/agent/flow_analysis", "QA Analysis Diagram & Flow", "QA Architecture")
        ]
        for m, p, n, c in system_endpoints:
            _add_ep(m, p, n, c, 200)

    return results
