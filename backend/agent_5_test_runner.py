import subprocess
import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def initialize_playwright_env(tests_dir: str):
    """
    Ensure the tests directory has a package.json and playwright.config.ts
    so npx playwright test can run.
    """
    pkg_json_path = os.path.join(tests_dir, "package.json")
    if not os.path.exists(pkg_json_path):
        with open(pkg_json_path, 'w', encoding='utf-8') as f:
            f.write('{"name":"qa-tests","version":"1.0.0","dependencies":{"@playwright/test":"^1.41.0"}}')
            
    config_path = os.path.join(tests_dir, "playwright.config.ts")
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("""
import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: '.',
  use: {
    headless: true,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
""")

def run_playwright_test(filename: str):
    """
    Agent 5 (Part 1): Test Runner
    Executes the generated Playwright test script.
    """
    try:
        tests_dir = os.path.join(os.getcwd(), "tests")
        if not os.path.exists(tests_dir) or not os.path.exists(os.path.join(tests_dir, filename)):
            return False, f"Test file {filename} not found in {tests_dir}."
            
        initialize_playwright_env(tests_dir)
        
        # We run the specific test file using npx playwright test
        logger.info(f"Running test: {filename}")
        
        # Use shell=True for npx on Windows
        process = subprocess.run(
            ["npx", "playwright", "test", filename, "--reporter=list"],
            cwd=tests_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        
        output = process.stdout + "\n" + process.stderr
        success = process.returncode == 0
        
        return success, output
        
    except Exception as e:
        logger.error(f"Error running test {filename}: {e}", exc_info=True)
        return False, str(e)


def run_self_healing(filename: str, test_output: str, original_code: str):
    """
    Agent 5 (Part 2): Self-Healing Agent
    Analyzes test failures and suggests code fixes.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
You are an expert QA Automation Engineer and Self-Healing Test Agent.
A Playwright (TypeScript) test script has failed during execution.

### Test Filename:
{filename}

### Test Execution Output (Error Log):
{test_output}

### Original Test Code:
```typescript
{original_code}
```

Task:
1. Analyze the error log to determine why the test failed (e.g., Timeout, Locator not found, Assertion failed).
2. Propose a fixed version of the TypeScript code that resolves the issue.
3. Provide a brief explanation of what was fixed.

Respond strictly in JSON format as follows:
{{
    "analysis": "Brief explanation of why it failed",
    "fix_explanation": "What was changed to fix it",
    "fixed_code": "The complete revised TypeScript code (do not wrap in markdown code blocks, just raw code string)"
}}
"""
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        
        if text_response.startswith('```json'):
            text_response = text_response.strip('```json').strip('```').strip()
            
        healing_result = json.loads(text_response)
        
        # Clean up fixed code if needed
        fixed_code = healing_result.get('fixed_code', '')
        if fixed_code.startswith("```typescript"):
            fixed_code = fixed_code[len("```typescript"):].strip()
        if fixed_code.endswith("```"):
            fixed_code = fixed_code[:-3].strip()
            
        healing_result['fixed_code'] = fixed_code
        
        return True, healing_result
        
    except Exception as e:
        logger.error(f"Error in Agent 5 Self-Healing: {e}", exc_info=True)
        return False, str(e)
