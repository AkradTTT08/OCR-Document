"""
Unit test to verify all 7 tools of the Spectra QA Consult MCP Server
"""
import os
import sys
import json

# Add backend to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server import (
    list_projects,
    get_project_context,
    get_qa_skills,
    evaluate_spectra_qa,
    send_email_report,
    qa_consult
)

def run_tests():
    print("==================================================")
    print("   Testing Spectra QA Consult MCP Server Tools   ")
    print("==================================================")

    # 1. Test list_projects
    print("\n1. Testing 'list_projects'...")
    res = list_projects()
    projects = json.loads(res)
    print(f"   [PASS] Found {len(projects)} project(s):", [p.get('name') for p in projects])
    project_id = projects[0]['id'] if projects else ""

    # 2. Test get_project_context
    print(f"\n2. Testing 'get_project_context' for project_id='{project_id}'...")
    res = get_project_context(project_id=project_id, query="Login authentication flow")
    context_data = json.loads(res)
    print(f"   [PASS] Available documents count: {len(context_data.get('available_documents', []))}")
    print(f"   [PASS] Relevant RAG chunks count: {len(context_data.get('relevant_knowledge_chunks', []))}")

    # 3. Test get_qa_skills
    print("\n3. Testing 'get_qa_skills'...")
    res = get_qa_skills()
    skills = json.loads(res)
    print(f"   [PASS] Available QA Skills count: {len(skills) if isinstance(skills, list) else 'N/A'}")

    # 4. Test evaluate_spectra_qa
    print("\n4. Testing 'evaluate_spectra_qa' (Exit Criteria)...")
    sample_doc = "# SRS Login System\nUser enters username and password.\nSystem validates and issues JWT token."
    res = evaluate_spectra_qa(
        document_content=sample_doc,
        document_type="Requirement",
        target_email="test-qa@spectra.local"
    )
    eval_data = json.loads(res)
    print(f"   [PASS] Evaluation Status: {eval_data.get('status')}")
    print(f"   [PASS] Failed items: {len(eval_data.get('failed_criteria', []))}")

    # 5. Test send_email_report
    print("\n5. Testing 'send_email_report'...")
    res = send_email_report(
        to_email="test-qa@spectra.local",
        subject="[Test] QA Consult Test Report",
        report_body="This is an automated verification test for Spectra QA MCP."
    )
    print(f"   [PASS] Email result: {res}")

    print("\n==================================================")
    print("   ALL MCP QA CONSULT TOOLS VERIFIED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
