"""Multi-agent automation endpoints: ecosystem status, Playwright/MCP web exploration, test generation/execution, master agent, and workflows."""
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
bp = Blueprint('automation_agents', __name__)

from core.config import BASE_DIR, UPLOAD_FOLDER

@bp.route('/api/agent/ecosystem-status', methods=['GET'])
def get_agent_ecosystem_status():
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400
    try:
        from agent_playwright_automation import get_cross_agent_ecosystem_status
        status = get_cross_agent_ecosystem_status(project_id)
        return jsonify({'success': True, 'ecosystem': status})
    except Exception as e:
        logger.error(f"Error getting ecosystem status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/automation-strategy', methods=['GET', 'POST'])
def handle_automation_strategy():
    try:
        from agent_playwright_automation import get_saved_automation_strategy, analyze_requirement_automation_strategy
        if request.method == 'GET':
            project_id = request.args.get('project_id')
            if not project_id:
                return jsonify({'error': 'Missing project_id'}), 400
            saved = get_saved_automation_strategy(project_id)
            return jsonify({'success': True, 'strategy': saved})

        data = request.get_json() or {}
        project_id = data.get('project_id')
        custom_focus = data.get('custom_focus', '')
        if not project_id:
            return jsonify({'error': 'Missing project_id'}), 400

        ok, result = analyze_requirement_automation_strategy(project_id, custom_focus=custom_focus)
        if ok:
            return jsonify({'success': True, 'strategy': result})
        return jsonify({'error': result}), 500
    except Exception as e:
        logger.error(f"Error in automation strategy endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/project-testcases', methods=['GET', 'POST'])
def handle_project_testcases():
    try:
        from agent_playwright_automation import get_or_extract_project_test_cases
        if request.method == 'GET':
            project_id = request.args.get('project_id')
            force = request.args.get('force_refresh', 'false').lower() == 'true'
        else:
            data = request.get_json() or {}
            project_id = data.get('project_id')
            force = bool(data.get('force_refresh', True))

        if not project_id:
            return jsonify({'error': 'Missing project_id'}), 400

        ok, result = get_or_extract_project_test_cases(project_id, force_refresh=force)
        if ok:
            return jsonify({'success': True, **result})
        return jsonify({'error': result}), 500
    except Exception as e:
        logger.error(f"Error in project testcases endpoint: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/mcp-play-web', methods=['POST'])
def mcp_play_web():
    data = request.get_json() or {}
    url = data.get('url')
    project_id = data.get('project_id')
    username = data.get('username', '')
    password = data.get('password', '')
    play_instructions = data.get('play_instructions', '')
    selected_test_cases = data.get('selected_test_cases', [])
    browser_type = data.get('browser_type', 'chromium')

    if not url:
        return jsonify({'error': 'กรุณาระบุ Target URL'}), 400

    try:
        from agent_playwright_automation import playwright_mcp_interactive_play
        success, result = playwright_mcp_interactive_play(
            project_id=project_id,
            url=url,
            username=username,
            password=password,
            play_instructions=play_instructions,
            selected_test_cases=selected_test_cases,
            browser_type=browser_type
        )
        if success:
            return jsonify({
                'success': True,
                'web_state': result['web_state'],
                'file_saved': result['file_saved']
            })
        else:
            return jsonify({'error': result}), 500
    except Exception as e:
        logger.error(f"Error in Playwright MCP web play: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/explore', methods=['POST'])
def explore_web():
    data = request.json or {}
    url = data.get('url')
    project_id = data.get('project_id')
    username = data.get('username', '')
    password = data.get('password', '')
    play_instructions = data.get('play_instructions', '')
    selected_test_cases = data.get('selected_test_cases', [])
    browser_type = data.get('browser_type', 'chromium')
    
    if not url:
        return jsonify({'error': 'Missing URL'}), 400
        
    try:
        from agent_playwright_automation import playwright_mcp_interactive_play
        success, result = playwright_mcp_interactive_play(
            project_id=project_id,
            url=url,
            username=username,
            password=password,
            play_instructions=play_instructions,
            selected_test_cases=selected_test_cases,
            browser_type=browser_type
        )
        if success:
            return jsonify({'success': True, 'web_state': result['web_state'], 'file_saved': result['file_saved']})
        else:
            return jsonify({'error': result}), 500
            
    except Exception as e:
        logger.error(f"Error in web exploration: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/align', methods=['POST'])
def align_requirements_and_web():
    data = request.json or {}
    project_id = data.get('project_id')
    web_state_file = data.get('web_state_file')
    
    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400
        
    try:
        from agent_3_alignment import run_alignment_analysis
        success, result = run_alignment_analysis(project_id, web_state_file)
        
        if success:
            return jsonify({'success': True, 'alignment_report': result})
        else:
            return jsonify({'error': result}), 500
            
    except Exception as e:
        logger.error(f"Error in alignment analysis: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/generate-test', methods=['POST'])
def generate_test_script():
    data = request.json or {}
    project_id = data.get('project_id')
    mode = data.get('mode', 'hybrid')
    selected_test_cases = data.get('selected_test_cases', [])
    selected_req_codes = data.get('selected_req_codes', [])
    web_state_file = data.get('web_state_file')
    recorded_actions = data.get('recorded_actions', [])
    gap_analysis_data = data.get('gap_analysis', {})
    target_url = data.get('target_url', '')
    
    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400
        
    try:
        from agent_playwright_automation import generate_accurate_playwright_scripts
        success, result = generate_accurate_playwright_scripts(
            project_id=project_id,
            mode=mode,
            selected_test_cases=selected_test_cases,
            selected_req_codes=selected_req_codes,
            web_state_file=web_state_file,
            recorded_actions=recorded_actions,
            gap_analysis_data=gap_analysis_data,
            target_url=target_url
        )
        
        if success:
            return jsonify({'success': True, 'test_script': result})
        else:
            return jsonify({'error': result}), 500
            
    except Exception as e:
        logger.error(f"Error in test generation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/save-test-code', methods=['POST'])
def save_test_code():
    data = request.get_json() or {}
    filename = data.get('file_name')
    code = data.get('code', '')
    if not filename:
        return jsonify({'error': 'Missing file_name'}), 400
    try:
        from agent_5_test_runner import save_playwright_test_code
        ok, msg = save_playwright_test_code(filename, code)
        if ok:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'error': msg}), 500
    except Exception as e:
        logger.error(f"Error saving test code: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/run-test', methods=['POST'])
def run_test():
    data = request.json or {}
    filename = data.get('file_name')
    project_id = data.get('project_id')
    code = data.get('code', '')
    selected_test_cases = data.get('selected_test_cases', [])
    recorded_actions = data.get('recorded_actions', [])
    evaluate_accuracy = bool(data.get('evaluate_accuracy', True))
    
    if not filename:
        return jsonify({'error': 'Missing file_name'}), 400
        
    try:
        from agent_5_test_runner import run_playwright_test, save_playwright_test_code
        if code and code.strip():
            save_playwright_test_code(filename, code)

        success, output = run_playwright_test(filename)

        accuracy_report = None
        if evaluate_accuracy and project_id:
            try:
                from agent_playwright_automation import evaluate_automation_business_and_flow_accuracy
                ok_acc, acc_res = evaluate_automation_business_and_flow_accuracy(
                    project_id=project_id,
                    file_name=filename,
                    code=code,
                    test_output=output,
                    run_passed=success,
                    selected_test_cases=selected_test_cases,
                    recorded_actions=recorded_actions
                )
                if ok_acc:
                    accuracy_report = acc_res
            except Exception as acc_err:
                logger.warning(f"Accuracy evaluation note: {acc_err}")
        
        return jsonify({
            'success': success,
            'output': output,
            'accuracy_report': accuracy_report
        })
            
    except Exception as e:
        logger.error(f"Error executing test: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/evaluate-automation-accuracy', methods=['POST'])
def evaluate_automation_accuracy():
    data = request.get_json() or {}
    project_id = data.get('project_id')
    filename = data.get('file_name', 'suite.spec.ts')
    code = data.get('code', '')
    test_output = data.get('test_output', '')
    run_passed = data.get('run_passed')
    selected_test_cases = data.get('selected_test_cases', [])
    recorded_actions = data.get('recorded_actions', [])

    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400

    try:
        from agent_playwright_automation import evaluate_automation_business_and_flow_accuracy
        ok, report = evaluate_automation_business_and_flow_accuracy(
            project_id=project_id,
            file_name=filename,
            code=code,
            test_output=test_output,
            run_passed=run_passed,
            selected_test_cases=selected_test_cases,
            recorded_actions=recorded_actions
        )
        if ok:
            return jsonify({'success': True, 'accuracy_report': report})
        return jsonify({'error': report}), 500
    except Exception as e:
        logger.error(f"Error evaluating automation accuracy: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/map_test_card', methods=['POST'])
def map_test_card():
    """
    Auto-maps a Trello card or sitemap screen to Target URL, matched Test Cases, and suggested Test Steps.
    """
    data = request.json or {}
    project_id = data.get('project_id')
    card_data = data.get('card_data') or {}
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from agent_card_tester import resolve_card_test_mapping
        result = resolve_card_test_mapping(project_id, card_data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error mapping test card: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/execute_test_card', methods=['POST'])
def execute_test_card():
    """
    Executes customized Playwright browser test run and AI Gap analysis with verified test cases.
    """
    data = request.json or {}
    project_id = data.get('project_id')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from agent_card_tester import execute_customized_test_run
        result = execute_customized_test_run(project_id, data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error executing test card: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/test_runs', methods=['GET'])
def get_test_runs():
    """
    Returns historical test runs for a project.
    """
    project_id = request.args.get('project_id')
    limit = int(request.args.get('limit', 50))
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from agent_card_tester import get_project_test_runs
        runs = get_project_test_runs(project_id, limit)
        return jsonify({'success': True, 'test_runs': runs})
    except Exception as e:
        logger.error(f"Error getting test runs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/heal-test', methods=['POST'])
def heal_test():
    data = request.json
    filename = data.get('file_name')
    test_output = data.get('test_output')
    original_code = data.get('original_code')
    
    if not filename or not test_output or not original_code:
        return jsonify({'error': 'Missing required fields for self-healing'}), 400
        
    try:
        from agent_5_test_runner import run_self_healing
        success, result = run_self_healing(filename, test_output, original_code)
        
        if success:
            return jsonify({'success': True, 'healing_result': result})
        else:
            return jsonify({'error': result}), 500
            
    except Exception as e:
        logger.error(f"Error in self-healing: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/download-tests/<project_id>', methods=['GET'])
def download_test_scripts(project_id):
    """
    Downloads all generated test scripts for a project as a ZIP file.
    """
    import zipfile
    import io
    
    try:
        project_tests_dir = os.path.join(os.getcwd(), "tests", project_id)
        if not os.path.exists(project_tests_dir):
            return jsonify({'error': 'No test scripts found for this project.'}), 404
            
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(project_tests_dir):
                for file in files:
                    if file.endswith('.ts'):
                        file_path = os.path.join(root, file)
                        # Archive path relative to project dir
                        archive_path = os.path.relpath(file_path, project_tests_dir)
                        zf.write(file_path, archive_path)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            download_name=f"test_automation_{project_id}.zip",
            as_attachment=True,
            mimetype='application/zip'
        )
    except Exception as e:
        logger.error(f"Error downloading tests: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/qa/master', methods=['POST'])
def api_qa_master():
    try:
        data = request.get_json()
        if not data or 'messages' not in data:
            return jsonify({'error': 'messages field is required'}), 400
        
        messages = data['messages']
        from orchestrator.master_agent import MasterAgent
        response_text = MasterAgent.run(messages)
        
        return jsonify({'success': True, 'response': response_text})
    except Exception as e:
        logger.error(f"Error in api_qa_master: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/workflow/execute', methods=['POST'])
def api_workflow_execute():
    try:
        data = request.get_json()
        if not data or 'nodes' not in data or 'edges' not in data:
            return jsonify({'error': 'Invalid workflow graph'}), 400
        
        from orchestrator.workflow_engine import run_workflow
        result = run_workflow(data['nodes'], data['edges'])
        
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in workflow execute: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


_WORKFLOWS_TABLE_ENSURED = False


def _ensure_workflows_table(cursor, conn):
    global _WORKFLOWS_TABLE_ENSURED
    if _WORKFLOWS_TABLE_ENSURED:
        return
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
            edges JSONB NOT NULL DEFAULT '[]'::jsonb,
            project_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE workflows ADD COLUMN IF NOT EXISTS project_id VARCHAR(255);
    """)
    conn.commit()
    _WORKFLOWS_TABLE_ENSURED = True


@bp.route('/api/workflows', methods=['GET', 'POST'])
def api_workflows():
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = conn.cursor()
        _ensure_workflows_table(cursor, conn)
        if request.method == 'GET':
            project_id = request.args.get('project_id')
            if project_id:
                cursor.execute("SELECT id, name, description, nodes, edges, updated_at FROM workflows WHERE project_id = %s ORDER BY updated_at DESC", (project_id,))
            else:
                cursor.execute("SELECT id, name, description, nodes, edges, updated_at FROM workflows ORDER BY updated_at DESC")
            workflows = [{"id": str(r[0]), "name": r[1], "description": r[2], "nodes": r[3], "edges": r[4], "updated_at": r[5].isoformat() if r[5] else None} for r in cursor.fetchall()]
            return jsonify({'success': True, 'workflows': workflows})
        elif request.method == 'POST':
            d = request.get_json()
            cursor.execute(
                "INSERT INTO workflows (name, description, nodes, edges, project_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (d.get('name', 'Untitled'), d.get('description', ''), json.dumps(d.get('nodes', [])), json.dumps(d.get('edges', [])), d.get('project_id'))
            )
            wf_id = cursor.fetchone()[0]
            conn.commit()
            return jsonify({'success': True, 'id': str(wf_id)})
    except Exception as e:
        logger.error(f"Error in api_workflows: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass


@bp.route('/api/workflows/<wf_id>', methods=['PUT', 'DELETE'])
def api_workflows_detail(wf_id):
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = conn.cursor()
        _ensure_workflows_table(cursor, conn)
        if request.method == 'PUT':
            d = request.get_json()
            cursor.execute(
                "UPDATE workflows SET name = %s, description = %s, nodes = %s, edges = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id",
                (d.get('name', 'Untitled'), d.get('description', ''), json.dumps(d.get('nodes', [])), json.dumps(d.get('edges', [])), wf_id)
            )
            if cursor.rowcount == 0:
                return jsonify({'error': 'Workflow not found'}), 404
            conn.commit()
            return jsonify({'success': True, 'id': wf_id})
        elif request.method == 'DELETE':
            cursor.execute("DELETE FROM workflows WHERE id = %s", (wf_id,))
            if cursor.rowcount == 0:
                return jsonify({'error': 'Workflow not found'}), 404
            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in api_workflows_detail: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            cursor.close()
            conn.close()
        except: pass

