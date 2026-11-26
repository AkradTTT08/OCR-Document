"""Project Management CRUD endpoints and validation/RBAC helpers."""
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import requests
from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory
from flask_cors import cross_origin
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
bp = Blueprint('projects', __name__)

from core.auth import get_request_user_payload

@bp.route('/api/projects', methods=['GET'])
def list_projects():
    """List all projects for document ingestion, respecting user project permissions if token provided"""
    try:
        from db_ingestion import get_projects
        projects = get_projects()
        
        # If user token is passed, filter projects based on allowed_projects (except admin or 'all')
        req_payload = get_request_user_payload()
        if req_payload and req_payload.get('role') != 'admin':
            allowed = req_payload.get('allowed_projects') or ['all']
            if isinstance(allowed, list) and 'all' not in allowed:
                allowed_normalized = [str(a).strip().lower() for a in allowed]
                projects = [
                    p for p in projects
                    if str(p.get('id') or p.get('project_id') or '').strip().lower() in allowed_normalized
                    or str(p.get('project_code') or '').strip().lower() in allowed_normalized
                ]
                
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return jsonify({'error': str(e)}), 500


def _validate_project_uuid(project_id: str) -> bool:
    try:
        uuid.UUID(str(project_id))
        return True
    except Exception:
        return False


def _sanitize_project_site_urls(site_urls, default_base_url='http://localhost:5173'):
    """Validate and sanitize project site URLs (only http/https allowed, strip empty entries)."""
    allowed_envs = {'TEST', 'UAT', 'PRD', 'DEV', 'STAGING', 'CUSTOM'}
    cleaned = []
    if isinstance(site_urls, list):
        for item in site_urls:
            if not isinstance(item, dict):
                continue
            url = str(item.get('url') or '').strip()
            if not url:
                continue
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ValueError(f"URL ไม่ถูกต้อง (ต้องขึ้นต้นด้วย http:// หรือ https://): {url}")
            env = str(item.get('env_type') or 'TEST').strip().upper()
            if env not in allowed_envs:
                env = 'CUSTOM'
            cleaned.append({
                'env_type': env,
                'url': url,
                'is_default': bool(item.get('is_default', False))
            })

    def_url = str(default_base_url or '').strip()
    if def_url and not (def_url.startswith('http://') or def_url.startswith('https://')):
        raise ValueError(f"Default Base URL ไม่ถูกต้อง (ต้องขึ้นต้นด้วย http:// หรือ https://): {def_url}")

    if cleaned:
        if not any(s['is_default'] for s in cleaned):
            cleaned[0]['is_default'] = True
        for s in cleaned:
            if s['is_default']:
                def_url = s['url']
                break
    elif def_url:
        cleaned = [{'env_type': 'TEST', 'url': def_url, 'is_default': True}]
    else:
        def_url = 'http://localhost:5173'
        cleaned = [{'env_type': 'TEST', 'url': def_url, 'is_default': True}]

    return cleaned, def_url


def _check_project_write_permission(project_id: str = None):
    """Verify JWT authentication and Project Management write permission."""
    req_payload = get_request_user_payload()
    if not req_payload:
        return jsonify({'error': 'กรุณาเข้าสู่ระบบก่อนดำเนินการจัดการโครงการ'}), 401
    role = str(req_payload.get('role') or '').lower()
    if role == 'admin':
        return None
    allowed_menus = req_payload.get('allowed_menus') or []
    if isinstance(allowed_menus, list) and 'project_management' not in allowed_menus:
        return jsonify({'error': 'คุณไม่มีสิทธิ์จัดการโครงการ (Project Management)'}), 403
    if project_id:
        allowed_projects = req_payload.get('allowed_projects') or ['all']
        if isinstance(allowed_projects, list) and 'all' not in allowed_projects:
            norm = [str(a).strip().lower() for a in allowed_projects]
            if str(project_id).strip().lower() not in norm:
                return jsonify({'error': 'คุณไม่มีสิทธิ์แก้ไขหรือลบโครงการนี้'}), 403
    return None


@bp.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    auth_err = _check_project_write_permission()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    logger.info(f"Create project request: {data}")
    if not data or ('name' not in data and 'project_name' not in data):
        return jsonify({'error': 'กรุณาระบุชื่อโครงการ (name หรือ project_name)'}), 400

    p_name = str(data.get('project_name') or data.get('name') or '').strip()
    if not p_name:
        return jsonify({'error': 'ชื่อโครงการห้ามเป็นค่าว่าง'}), 400
    if len(p_name) > 200:
        return jsonify({'error': 'ชื่อโครงการต้องไม่เกิน 200 ตัวอักษร'}), 400

    p_code = data.get('project_code')
    if p_code is not None:
        p_code = str(p_code).strip()
        if not p_code:
            p_code = None
        elif len(p_code) > 64:
            return jsonify({'error': 'รหัสโครงการต้องไม่เกิน 64 ตัวอักษร'}), 400

    desc = str(data.get('description') or '').strip()
    status = str(data.get('status') or 'Active').strip()
    if status not in ('Active', 'Inactive'):
        return jsonify({'error': 'สถานะโครงการต้องเป็น Active หรือ Inactive เท่านั้น'}), 400

    try:
        cleaned_sites, cleaned_default_url = _sanitize_project_site_urls(
            data.get('site_urls'),
            data.get('default_base_url', 'http://localhost:5173')
        )
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400

    try:
        from db_ingestion import add_project
        project = add_project(
            name=p_name,
            project_name=p_name,
            project_code=p_code,
            description=desc,
            status=status,
            default_base_url=cleaned_default_url,
            site_urls=cleaned_sites
        )
        return jsonify({'success': True, 'project': project})
    except Exception as e:
        err_str = str(e)
        status_code = 409 if 'ซ้ำ' in err_str else 500
        logger.error(f"Error creating project: {e}", exc_info=True)
        return jsonify({'error': f'สร้างโครงการไม่สำเร็จ: {err_str}'}), status_code


@bp.route('/api/projects/<string:project_id>', methods=['PUT'])
def update_project_api(project_id):
    """Update a project"""
    if not _validate_project_uuid(project_id):
        return jsonify({'error': 'รหัสโครงการ (UUID) ไม่ถูกต้อง'}), 400
    auth_err = _check_project_write_permission(project_id=project_id)
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'ไม่มีข้อมูลสำหรับอัปเดต'}), 400

    p_name = data.get('project_name') if 'project_name' in data else data.get('name')
    if p_name is not None:
        p_name = str(p_name).strip()
        if not p_name:
            return jsonify({'error': 'ชื่อโครงการห้ามเป็นค่าว่าง'}), 400
        if len(p_name) > 200:
            return jsonify({'error': 'ชื่อโครงการต้องไม่เกิน 200 ตัวอักษร'}), 400

    p_code = data.get('project_code')
    if p_code is not None:
        p_code = str(p_code).strip()
        if not p_code:
            p_code = None
        elif len(p_code) > 64:
            return jsonify({'error': 'รหัสโครงการต้องไม่เกิน 64 ตัวอักษร'}), 400

    desc = str(data.get('description')).strip() if data.get('description') is not None else None
    status = data.get('status')
    if status is not None:
        status = str(status).strip()
        if status not in ('Active', 'Inactive'):
            return jsonify({'error': 'สถานะโครงการต้องเป็น Active หรือ Inactive เท่านั้น'}), 400

    site_urls = data.get('site_urls')
    default_base_url = data.get('default_base_url')
    if site_urls is not None or default_base_url is not None:
        try:
            site_urls, default_base_url = _sanitize_project_site_urls(site_urls, default_base_url or '')
        except ValueError as ve:
            return jsonify({'error': str(ve)}), 400

    try:
        from db_ingestion import update_project
        project = update_project(
            project_id=project_id,
            name=p_name,
            project_code=p_code,
            description=desc,
            status=status,
            default_base_url=default_base_url,
            site_urls=site_urls
        )
        return jsonify({'success': True, 'project': project, 'message': 'อัปเดตโครงการเรียบร้อยแล้ว'})
    except Exception as e:
        err_str = str(e)
        status_code = 409 if 'ซ้ำ' in err_str else (404 if 'ไม่พบโครงการ' in err_str else 500)
        logger.error(f"Error updating project {project_id}: {e}", exc_info=True)
        return jsonify({'error': f'อัปเดตไม่สำเร็จ: {err_str}'}), status_code


@bp.route('/api/projects/<string:project_id>', methods=['DELETE'])
def delete_project_api(project_id):
    """Delete a project"""
    if not _validate_project_uuid(project_id):
        return jsonify({'error': 'รหัสโครงการ (UUID) ไม่ถูกต้อง'}), 400
    auth_err = _check_project_write_permission(project_id=project_id)
    if auth_err:
        return auth_err

    try:
        from db_ingestion import delete_project
        delete_project(project_id)
        return jsonify({'success': True, 'message': 'ลบโครงการเรียบร้อยแล้ว'})
    except Exception as e:
        err_str = str(e)
        status_code = 404 if 'ไม่พบโครงการ' in err_str else 500
        logger.error(f"Error deleting project {project_id}: {e}", exc_info=True)
        return jsonify({'error': err_str}), status_code

