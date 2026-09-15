#!/usr/bin/env python3
"""
Spectra CLI (`spectra-cli`)
Automated Command Line Interface for GitHub Actions, GitLab CI/CD, and Jenkins pipelines.
"""

import sys
import argparse
import requests
import json
import os

DEFAULT_BACKEND = os.environ.get("SPECTRA_HOST", "http://localhost:5000")

def main():
    parser = argparse.ArgumentParser(prog="spectra-cli", description="Spectra QA Automation CLI Runner for CI/CD")
    parser.add_argument("--host", default=DEFAULT_BACKEND, help="Spectra QA API Host URL")
    parser.add_argument("--project-id", required=True, help="Target Project ID")
    parser.add_argument("--action", choices=["security-scan", "perf-test", "workflow-run", "full-audit"], default="full-audit", help="Action to execute")
    parser.add_argument("--notify", action="store_true", help="Send notification to webhooks upon completion")
    
    args = parser.parse_args()
    
    print(f"🚀 [Spectra CLI] Triggering '{args.action}' for Project ID: {args.project_id}...")
    print(f"📡 Connecting to Spectra Host: {args.host}")
    
    try:
        payload = {
            "project_id": args.project_id,
            "action": args.action,
            "notify": args.notify,
            "triggered_by": "CI/CD Pipeline (spectra-cli)"
        }
        
        url = f"{args.host}/api/webhooks/ci-cd"
        res = requests.post(url, json=payload, timeout=30)
        
        if res.status_code == 200:
            data = res.json()
            print("✅ [Spectra CLI] Execution Completed Successfully!")
            print(f"📊 Summary Status: {data.get('status', 'OK')}")
            print(f"📝 Summary Message: {data.get('message', '')}")
            if data.get('results'):
                print("📋 Detailed Results:", json.dumps(data['results'], indent=2))
            sys.exit(0)
        else:
            print(f"❌ [Spectra CLI] Execution Failed with HTTP Status {res.status_code}")
            print(res.text)
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ [Spectra CLI] Network Connection Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
