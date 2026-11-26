import subprocess
import os
import re
import json
import logging
from gemini_utils import call_gemini, get_actual_model_for_usage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Deterministic Playwright test workspace (independent of process CWD)
PLAYWRIGHT_TESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_tests")


def _extract_json_object(raw_text: str) -> dict:
    s = (raw_text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", s)
    if fence:
        s = fence.group(1).strip()
    else:
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first:last + 1]
    return json.loads(s, strict=False)


def _resolve_test_file(filename: str):
    """Safely resolves a relative test filename inside PLAYWRIGHT_TESTS_DIR."""
    os.makedirs(PLAYWRIGHT_TESTS_DIR, exist_ok=True)
    clean_rel = (filename or "").replace("\\", "/").lstrip("/")
    target = os.path.abspath(os.path.join(PLAYWRIGHT_TESTS_DIR, clean_rel))
    base = os.path.abspath(PLAYWRIGHT_TESTS_DIR)
    if not target.startswith(base):
        raise ValueError("Invalid test file path")
    return base, target, clean_rel


def initialize_playwright_env(tests_dir: str):
    """
    Ensure the Playwright tests directory has a package.json and playwright.config.ts.
    """
    os.makedirs(tests_dir, exist_ok=True)
    pkg_json_path = os.path.join(tests_dir, "package.json")
    if not os.path.exists(pkg_json_path):
        with open(pkg_json_path, 'w', encoding='utf-8') as f:
            f.write('{"name":"spectra-playwright-tests","version":"1.0.0","devDependencies":{"@playwright/test":"^1.49.0"}}\n')

    config_path = os.path.join(tests_dir, "playwright.config.ts")
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write("""import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  timeout: 45_000,
  use: {
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
""")


def run_playwright_test(filename: str):
    """
    Agent 5 (Part 1): Test Runner
    Executes the generated Playwright test script from PLAYWRIGHT_TESTS_DIR.
    """
    try:
        tests_dir, target_file, clean_rel = _resolve_test_file(filename)
        if not os.path.exists(target_file):
            return False, f"ไม่พบไฟล์สคริปต์ทดสอบ '{clean_rel}' ใน {tests_dir}"

        initialize_playwright_env(tests_dir)

        local_pw_bin = os.path.join(
            tests_dir,
            "node_modules",
            ".bin",
            "playwright.cmd" if os.name == "nt" else "playwright"
        )
        if not os.path.exists(local_pw_bin):
            return False, (
                "ยังไม่ได้ติดตั้ง @playwright/test ในโฟลเดอร์รันทดสอบ\n"
                f"กรุณารันคำสั่งต่อไปนี้ครั้งเดียวใน Terminal:\n"
                f"  cd \"{tests_dir}\" && npm install && npx playwright install chromium"
            )

        logger.info(f"Running Playwright test: {clean_rel} in {tests_dir}")

        if os.name == "nt":
            cmd = f'"{local_pw_bin}" test "{clean_rel}" --reporter=list'
            process = subprocess.run(
                cmd,
                cwd=tests_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                timeout=120
            )
        else:
            process = subprocess.run(
                [local_pw_bin, "test", clean_rel, "--reporter=list"],
                cwd=tests_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120
            )

        output = ((process.stdout or "") + "\n" + (process.stderr or "")).strip()
        success = process.returncode == 0
        return success, output

    except subprocess.TimeoutExpired:
        return False, "การรันสคริปต์ Playwright หมดเวลา (Timeout เกิน 120 วินาที)"
    except Exception as e:
        logger.error(f"Error running test {filename}: {e}", exc_info=True)
        return False, str(e)


def run_self_healing(filename: str, test_output: str, original_code: str):
    """
    Agent 5 (Part 2): Self-Healing Agent
    Analyzes test failures and suggests code fixes.
    """
    try:
        prompt = f"""คุณคือ Expert QA Automation Engineer และ Self-Healing Test Agent
สคริปต์ Playwright (TypeScript) ด้านล่างรันไม่ผ่าน กรุณาวิเคราะห์ Error Log และแก้ไขโค้ดให้ทำงานได้ถูกต้อง

### Test Filename:
{filename}

### Test Execution Output (Error Log):
{(test_output or '')[:12000]}

### Original Test Code:
```typescript
{original_code}
```

กฎ: ตอบ `analysis` และ `fix_explanation` เป็นภาษาไทยที่เข้าใจง่าย และตอบกลับเป็น JSON เท่านั้น:
{{
    "analysis": "อธิบายสาเหตุที่เทสต์ไม่ผ่านอย่างชัดเจน (เช่น Timeout, Locator ไม่พบ, Assertion ไม่ตรง)",
    "fix_explanation": "สรุปสิ่งที่แก้ไขในโค้ด",
    "fixed_code": "โค้ด TypeScript ฉบับสมบูรณ์ที่แก้ไขแล้ว (ไม่ต้องครอบด้วย ```typescript)"
}}
"""
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        text_response, usage_metadata = call_gemini(prompt, model_name=model_name)

        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                actual_model = get_actual_model_for_usage(model_name)
                log_api_usage("Agent_5_Test_Runner", actual_model, usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 5: {log_err}")

        healing_result = _extract_json_object(text_response)

        fixed_code = (healing_result.get('fixed_code') or '').strip()
        fixed_code = re.sub(r'^```(?:typescript|ts)?\s*', '', fixed_code)
        fixed_code = re.sub(r'\s*```$', '', fixed_code).strip()
        healing_result['fixed_code'] = fixed_code

        # Persist the healed code back to PLAYWRIGHT_TESTS_DIR
        try:
            _, target_file, _ = _resolve_test_file(filename)
            if fixed_code:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(fixed_code)
                healing_result['saved_to_disk'] = True
        except Exception as save_err:
            logger.warning(f"Could not overwrite healed test file {filename}: {save_err}")

        return True, healing_result

    except Exception as e:
        logger.error(f"Error in Agent 5 Self-Healing: {e}", exc_info=True)
        return False, str(e)


def save_playwright_test_code(filename: str, code: str):
    """Saves user-edited Playwright TypeScript code directly to disk in PLAYWRIGHT_TESTS_DIR."""
    try:
        _, target_file, clean_rel = _resolve_test_file(filename)
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(code or '')
        return True, f"บันทึกสคริปต์ {clean_rel} เรียบร้อยแล้ว"
    except Exception as e:
        logger.error(f"Error saving test code {filename}: {e}", exc_info=True)
        return False, str(e)
