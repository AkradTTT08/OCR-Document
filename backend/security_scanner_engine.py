"""
Spectra QA — Universal Web (DAST), API Collection, and Source Code (SAST) Security Scanner Engine.
Supports all web architectures:
  1. Static / SSR / Traditional Multi-Page Websites
  2. Single Page Applications (React, Vue, Svelte, Angular, Next.js) via HTTP+JS bundle analysis & optional Playwright Headless Chromium
  3. Authenticated Web Applications (Bearer Token, Session Cookies, Basic Auth, Custom Headers)
  4. REST / GraphQL API Collections from project repository
  5. Source Code, Uploaded Files, and GitHub Repositories (Deterministic SAST + Optional Gemini AI Enrichment)
"""

import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {
    "Critical": 22,
    "High": 12,
    "Medium": 6,
    "Low": 2,
    "Info": 0,
}

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}


def init_security_scans_table() -> None:
    """Ensures the qa_security_scans table exists in PostgreSQL for scan history."""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS qa_security_scans (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id VARCHAR(120),
                scan_mode VARCHAR(50) NOT NULL,
                target_label TEXT NOT NULL,
                standard VARCHAR(120) DEFAULT 'OWASP Top 10 (2021)',
                security_score INTEGER DEFAULT 100,
                grade VARCHAR(8) DEFAULT 'A',
                vulnerabilities_found INTEGER DEFAULT 0,
                severity_counts JSONB DEFAULT '{}'::jsonb,
                summary_json JSONB DEFAULT '{}'::jsonb,
                findings_json JSONB DEFAULT '[]'::jsonb,
                report_markdown TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not init qa_security_scans table: {e}")


def save_security_scan_record(
    project_id: Optional[str],
    scan_mode: str,
    target_label: str,
    standard: str,
    result_payload: Dict[str, Any],
) -> Optional[str]:
    """Persists a completed security scan into qa_security_scans."""
    init_security_scans_table()
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        scan_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO qa_security_scans
            (id, project_id, scan_mode, target_label, standard, security_score, grade,
             vulnerabilities_found, severity_counts, summary_json, findings_json, report_markdown)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
            RETURNING id;
            """,
            (
                scan_id,
                str(project_id or ""),
                scan_mode,
                target_label[:500],
                standard,
                int(result_payload.get("security_score", 100)),
                str(result_payload.get("grade", "A")),
                int(result_payload.get("vulnerabilities_found", 0)),
                json.dumps(result_payload.get("severity_counts") or {}, ensure_ascii=False),
                json.dumps(
                    {
                        "header_checks": result_payload.get("header_checks") or [],
                        "attack_surface": result_payload.get("attack_surface") or {},
                        "scan_meta": result_payload.get("scan_meta") or {},
                    },
                    ensure_ascii=False,
                ),
                json.dumps(result_payload.get("findings") or [], ensure_ascii=False),
                str(result_payload.get("report") or ""),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return str(row[0]) if row else scan_id
    except Exception as e:
        logger.warning(f"Failed to save security scan record: {e}")
        return None


def get_security_scan_history(project_id: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    """Returns recent security scans for a project (or all if project_id omitted)."""
    init_security_scans_table()
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        if project_id:
            cur.execute(
                """
                SELECT id, project_id, scan_mode, target_label, standard, security_score, grade,
                       vulnerabilities_found, severity_counts, summary_json, findings_json, report_markdown, created_at
                FROM qa_security_scans
                WHERE project_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (str(project_id), int(limit)),
            )
        else:
            cur.execute(
                """
                SELECT id, project_id, scan_mode, target_label, standard, security_score, grade,
                       vulnerabilities_found, severity_counts, summary_json, findings_json, report_markdown, created_at
                FROM qa_security_scans
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (int(limit),),
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        items = []
        for r in rows:
            summary_obj = r[9] if isinstance(r[9], dict) else {}
            items.append(
                {
                    "id": str(r[0]),
                    "project_id": r[1],
                    "scan_mode": r[2],
                    "target_label": r[3],
                    "standard": r[4],
                    "security_score": r[5],
                    "grade": r[6],
                    "vulnerabilities_found": r[7],
                    "severity_counts": r[8] if isinstance(r[8], dict) else {},
                    "header_checks": summary_obj.get("header_checks") or [],
                    "attack_surface": summary_obj.get("attack_surface") or {},
                    "scan_meta": summary_obj.get("scan_meta") or {},
                    "findings": r[10] if isinstance(r[10], list) else [],
                    "report": r[11] or "",
                    "created_at": r[12].isoformat() if r[12] else None,
                }
            )
        return items
    except Exception as e:
        logger.warning(f"Error fetching security scan history: {e}")
        return []


def delete_security_scan_record(scan_id: str) -> bool:
    """Deletes a security scan record by ID."""
    init_security_scans_table()
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM qa_security_scans WHERE id = %s::uuid;", (scan_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted
    except Exception as e:
        logger.warning(f"Failed deleting security scan record {scan_id}: {e}")
        return False


def _is_blocked_metadata_target(url: str) -> bool:
    """Blocks cloud instance metadata endpoints (169.254.169.254) while allowing localhost/staging/public web apps."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return True
        if host in ("169.254.169.254", "metadata.google.internal", "100.100.100.200"):
            return True
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_link_local:
                return True
        except ValueError:
            pass
        return False
    except Exception:
        return True


def _build_auth_session(auth_config: Optional[Dict[str, Any]] = None) -> Tuple[requests.Session, Dict[str, str]]:
    """Configures a requests.Session with user-specified authentication (Bearer, Cookie, Basic, Custom Headers)."""
    session = requests.Session()
    extra_headers: Dict[str, str] = {
        "User-Agent": "Spectra-QA-Security-Scanner/2.0 (OWASP-Audit; +https://spectra-qa.local)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    }
    if not isinstance(auth_config, dict):
        session.headers.update(extra_headers)
        return session, extra_headers

    auth_type = str(auth_config.get("type") or "none").lower().strip()
    if auth_type == "bearer":
        token = str(auth_config.get("token") or "").strip()
        if token:
            extra_headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    elif auth_type == "cookie":
        cookie_str = str(auth_config.get("cookie") or "").strip()
        if cookie_str:
            extra_headers["Cookie"] = cookie_str
    elif auth_type == "basic":
        user = str(auth_config.get("username") or "")
        pwd = str(auth_config.get("password") or "")
        if user or pwd:
            session.auth = (user, pwd)
    elif auth_type == "apikey":
        k = str(auth_config.get("key") or "X-API-Key").strip()
        v = str(auth_config.get("value") or "").strip()
        if k and v:
            extra_headers[k] = v

    custom_headers = auth_config.get("custom_headers")
    if isinstance(custom_headers, dict):
        for k, v in custom_headers.items():
            if k and str(k).strip():
                extra_headers[str(k).strip()] = str(v)
    elif isinstance(custom_headers, list):
        for row in custom_headers:
            if isinstance(row, dict) and row.get("enabled", True) is not False:
                k = str(row.get("key") or "").strip()
                v = str(row.get("value") or "").strip()
                if k:
                    extra_headers[k] = v

    session.headers.update(extra_headers)
    return session, extra_headers


def _compute_score_and_grade(findings: List[Dict[str, Any]], standard: str = "") -> Tuple[int, str, Dict[str, int]]:
    """Calculates a 0-100 Security Posture Score, Letter Grade, and severity counts, remapping tags to the chosen standard."""
    std_upper = (standard or "").upper()
    asvs_map = {
        "CWE-89": "ASVS V5.3.4 (SQL Injection)",
        "CWE-78": "ASVS V5.3.8 (OS Command Injection)",
        "CWE-79": "ASVS V5.3.3 (Output Encoding / XSS)",
        "CWE-95": "ASVS V5.2.4 (Dynamic Code Execution)",
        "CWE-798": "ASVS V2.10.4 / V6.4.1 (Secret Management)",
        "CWE-502": "ASVS V5.5.3 (Deserialization)",
        "CWE-328": "ASVS V6.2.2 (Approved Cryptography)",
        "CWE-295": "ASVS V9.2.1 (TLS Certificate Validation)",
        "CWE-319": "ASVS V9.1.1 (TLS Everywhere)",
        "CWE-693": "ASVS V14.4.3 (Content-Security-Policy)",
        "CWE-1021": "ASVS V14.4.4 (Clickjacking X-Frame-Options)",
        "CWE-16": "ASVS V14.4.1 (X-Content-Type-Options)",
        "CWE-942": "ASVS V14.5.3 (CORS Origin Validation)",
        "CWE-614": "ASVS V3.4.1 (Cookie Secure/HttpOnly/SameSite)",
        "CWE-352": "ASVS V4.2.2 (Anti-CSRF Protection)",
        "CWE-22": "ASVS V12.3.1 (Path Traversal Protection)",
        "CWE-918": "ASVS V12.6.1 (SSRF Protection)",
        "CWE-434": "ASVS V12.1.1 (File Upload Validation)",
        "CWE-601": "ASVS V5.1.5 (Safe URL Redirects)",
    }
    api_map = {
        "CWE-639": "API1:2023 Broken Object Level Authorization",
        "CWE-798": "API2:2023 Broken Authentication",
        "CWE-598": "API2:2023 Broken Authentication",
        "CWE-614": "API2:2023 Broken Authentication",
        "CWE-213": "API3:2023 Broken Object Property Level Authorization",
        "CWE-770": "API4:2023 Unrestricted Resource Consumption",
        "CWE-918": "API7:2023 Server Side Request Forgery",
        "CWE-942": "API8:2023 Security Misconfiguration (CORS)",
        "CWE-693": "API8:2023 Security Misconfiguration (Headers)",
        "CWE-209": "API8:2023 Security Misconfiguration (Error Leak)",
        "CWE-319": "API8:2023 Security Misconfiguration (TLS)",
        "CWE-89": "API8:2023 / Injection in API Parameter",
        "CWE-78": "API8:2023 / Command Injection in API",
    }
    cwe_top25_map = {
        "CWE-79": "CWE Top 25 #2 — Cross-site Scripting (XSS)",
        "CWE-89": "CWE Top 25 #3 — SQL Injection",
        "CWE-352": "CWE Top 25 #4 — Cross-Site Request Forgery (CSRF)",
        "CWE-22": "CWE Top 25 #5 — Path Traversal",
        "CWE-78": "CWE Top 25 #7 — OS Command Injection",
        "CWE-434": "CWE Top 25 #10 — Unrestricted File Upload",
        "CWE-502": "CWE Top 25 #15 — Deserialization of Untrusted Data",
        "CWE-798": "CWE Top 25 #18 — Hard-coded Credentials",
        "CWE-918": "CWE Top 25 #19 — Server-Side Request Forgery (SSRF)",
        "CWE-306": "CWE Top 25 #20 — Missing Authentication",
    }

    for f in findings:
        cwe_code = str(f.get("cwe") or "")
        if "ASVS" in std_upper and cwe_code in asvs_map:
            f["owasp"] = asvs_map[cwe_code]
        elif "API" in std_upper and cwe_code in api_map:
            f["owasp"] = api_map[cwe_code]
        elif "CWE" in std_upper and cwe_code in cwe_top25_map:
            f["owasp"] = cwe_top25_map[cwe_code]

    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    penalty = 0
    # ASVS Level 2 applies stricter scoring on Medium/Low misconfigurations
    asvs_strict = "ASVS" in std_upper
    for f in findings:
        sev = f.get("severity", "Info")
        if sev not in counts:
            sev = "Info"
        counts[sev] += 1
        base_w = SEVERITY_WEIGHTS.get(sev, 0)
        if asvs_strict and sev in ("Medium", "Low"):
            base_w += 2
        penalty += base_w

    score = max(0, min(100, 100 - penalty))
    if counts["Critical"] > 0:
        score = min(score, 68)

    if score >= 90 and counts["Critical"] == 0 and counts["High"] == 0:
        grade = "A"
    elif score >= 78 and counts["Critical"] == 0:
        grade = "B"
    elif score >= 62:
        grade = "C"
    elif score >= 45:
        grade = "D"
    else:
        grade = "F"

    return score, grade, counts


def _format_findings_to_markdown(
    target_label: str,
    scan_mode_label: str,
    standard: str,
    score: int,
    grade: str,
    counts: Dict[str, int],
    findings: List[Dict[str, Any]],
    header_checks: Optional[List[Dict[str, Any]]] = None,
    ai_summary: Optional[str] = None,
) -> str:
    """Generates a comprehensive Thai Markdown report from structured findings."""
    total_vulns = counts["Critical"] + counts["High"] + counts["Medium"] + counts["Low"]
    lines = [
        f"# รายงานผลการตรวจสอบความปลอดภัย (Spectra QA Security Report)",
        f"- **เป้าหมายการตรวจสอบ (Target)**: `{target_label}`",
        f"- **รูปแบบการสแกน (Scan Mode)**: {scan_mode_label}",
        f"- **มาตรฐานอ้างอิง (Standard)**: {standard}",
        f"- **คะแนนความปลอดภัย (Security Score)**: **{score}/100 (Grade {grade})**",
        f"- **ช่องโหว่ที่พบทั้งหมด**: **{total_vulns} รายการ** (Critical: {counts['Critical']}, High: {counts['High']}, Medium: {counts['Medium']}, Low: {counts['Low']}, Info: {counts['Info']})",
        "",
    ]

    if ai_summary:
        lines.extend([
            "## บทวิเคราะห์เชิงลึกโดย AI (AI Security Architect Insights)",
            ai_summary.strip(),
            "",
        ])

    if not findings:
        lines.extend([
            "## สรุปผลการตรวจสอบ",
            "- ไม่พบช่องโหว่ความเสี่ยงสูงในขอบเขตที่ตรวจสอบ ระบบมีการป้องกันพื้นฐานตามเกณฑ์มาตรฐาน",
        ])
        return "\n".join(lines)

    lines.append("## รายละเอียดช่องโหว่และแนวทางแก้ไข (Vulnerability Findings & Remediation)")
    for idx, f in enumerate(findings, 1):
        lines.extend([
            f"### {idx}. [{f.get('severity', 'Info').upper()}] {f.get('title', 'พบประเด็นความปลอดภัย')}",
            f"- **หมวดหมู่ / มาตรฐาน**: `{f.get('owasp', 'OWASP')}` • `{f.get('cwe', 'CWE')}` ({f.get('category', 'Security')})",
            f"- **ตำแหน่งที่พบ (Target / Location)**: `{f.get('target', target_label)}`",
            f"- **รายละเอียดความเสี่ยง**: {f.get('description', '')}",
        ])
        if f.get("evidence"):
            lines.append(f"- **หลักฐานที่ตรวจพบ (Evidence)**: `{str(f['evidence'])[:300]}`")
        if f.get("remediation"):
            lines.append(f"- **แนวทางแก้ไข (Remediation)**: {f.get('remediation')}")
        if f.get("code_snippet"):
            lines.extend([
                "```",
                str(f["code_snippet"]).strip(),
                "```",
            ])
        lines.append("")

    return "\n".join(lines)


# =========================================================================
# 1. UNIVERSAL WEB SECURITY SCANNER (DAST FOR ALL WEB TYPES)
# =========================================================================

SECRET_PATTERNS = [
    ("Google API Key", r"AIza[0-9A-Za-z\-_]{35}", "CWE-798", "Critical"),
    ("AWS Access Key ID", r"AKIA[0-9A-Z]{16}", "CWE-798", "Critical"),
    ("OpenAI / Secret API Key", r"sk-[A-Za-z0-9]{32,}", "CWE-798", "Critical"),
    ("Slack Token", r"xox[baprs]-[0-9A-Za-z\-]{10,48}", "CWE-798", "High"),
    ("Private RSA/SSH Key", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "CWE-321", "Critical"),
    ("Stripe Live Secret Key", r"sk_live_[0-9a-zA-Z]{24,}", "CWE-798", "Critical"),
    ("GitHub Personal Access Token", r"ghp_[0-9a-zA-Z]{36}", "CWE-798", "Critical"),
    ("Hardcoded Bearer JWT in JS", r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", "CWE-798", "High"),
]


def _try_headless_spa_capture(
    target_url: str,
    extra_headers: Dict[str, str],
    timeout_ms: int = 12000,
) -> Dict[str, Any]:
    """
    Uses Playwright Headless Chromium to render SPAs (React/Vue/Svelte/Next.js/Angular),
    capturing post-hydration DOM, runtime XHR/Fetch API calls, browser cookies, and storage keys.
    Gracefully returns {'rendered': False} if Playwright browser binary is unavailable.
    """
    capture: Dict[str, Any] = {
        "rendered": False,
        "html": "",
        "xhr_urls": [],
        "console_errors": [],
        "cookies": [],
        "local_storage_keys": [],
        "framework_detected": "",
    }
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                ignore_https_errors=True,
                extra_http_headers={k: v for k, v in extra_headers.items() if k.lower() != "host"},
            )
            page = context.new_page()
            xhr_set = set()

            def _on_request(req):
                if req.resource_type in ("xhr", "fetch") or "/api/" in req.url or "/graphql" in req.url:
                    xhr_set.add(f"{req.method} {req.url}")

            def _on_console(msg):
                if msg.type == "error":
                    capture["console_errors"].append(msg.text[:250])

            page.on("request", _on_request)
            page.on("console", _on_console)

            page.goto(target_url, wait_until="networkidle", timeout=timeout_ms)
            capture["html"] = page.content()
            capture["cookies"] = context.cookies()
            capture["xhr_urls"] = sorted(list(xhr_set))[:40]

            try:
                storage_info = page.evaluate("""() => {
                    const lsKeys = Object.keys(window.localStorage || {});
                    const ssKeys = Object.keys(window.sessionStorage || {});
                    let fw = '';
                    if (window.__NEXT_DATA__) fw = 'Next.js';
                    else if (window.__NUXT__) fw = 'Nuxt / Vue';
                    else if (document.querySelector('[data-reactroot], #__next, #root')) fw = 'React / SPA';
                    else if (document.querySelector('#app, [data-v-]')) fw = 'Vue / Vite SPA';
                    else if (document.querySelector('[class*="svelte-"]')) fw = 'Svelte SPA';
                    return { lsKeys, ssKeys, fw };
                }""")
                capture["local_storage_keys"] = (storage_info.get("lsKeys") or []) + (storage_info.get("ssKeys") or [])
                capture["framework_detected"] = storage_info.get("fw") or ""
            except Exception:
                pass

            capture["rendered"] = True
            context.close()
            browser.close()
    except Exception as e:
        logger.info(f"Headless SPA capture skipped/fallback to HTTP parser: {e}")
    return capture


def scan_web_application(
    target_url: str,
    standard: str = "OWASP Top 10 (2021)",
    scan_profile: str = "full_web",  # 'quick' | 'full_web' | 'spa_headless'
    max_pages: int = 5,
    auth_config: Optional[Dict[str, Any]] = None,
    use_ai: bool = False,
) -> Dict[str, Any]:
    """
    Universal Web Application Security Scanner (DAST).
    Works across traditional SSR sites, SPAs, local dev servers, and authenticated staging/production portals.
    """
    t0 = time.time()
    raw_url = (target_url or "").strip()
    if not raw_url:
        raise ValueError("กรุณาระบุ URL ของเว็บไซต์ที่ต้องการตรวจสอบ")
    if not re.match(r"^https?://", raw_url, re.I):
        raw_url = "https://" + raw_url

    if _is_blocked_metadata_target(raw_url):
        raise ValueError("ไม่อนุญาตให้สแกน IP ของ Cloud Metadata Service")

    parsed_root = urlparse(raw_url)
    base_origin = f"{parsed_root.scheme}://{parsed_root.netloc}"

    session, extra_headers = _build_auth_session(auth_config)
    findings: List[Dict[str, Any]] = []
    header_checks: List[Dict[str, Any]] = []
    crawled_pages: List[Dict[str, Any]] = []
    discovered_apis: List[str] = []
    discovered_forms: List[Dict[str, Any]] = []
    scripts_analyzed: List[str] = []

    def add_finding(
        severity: str,
        category: str,
        owasp: str,
        cwe: str,
        title: str,
        description: str,
        remediation: str,
        target: str = raw_url,
        evidence: str = "",
        code_snippet: str = "",
    ):
        findings.append(
            {
                "id": f"SEC-{len(findings) + 1:03d}",
                "severity": severity,
                "category": category,
                "owasp": owasp,
                "cwe": cwe,
                "title": title,
                "target": target,
                "description": description,
                "evidence": evidence,
                "remediation": remediation,
                "code_snippet": code_snippet,
            }
        )

    # --- 1. Fetch Primary Target URL (with SSL fallback inspection) ---
    ssl_valid = True
    ssl_error_detail = ""
    resp = None
    req_start = time.time()
    try:
        resp = session.get(raw_url, timeout=12, allow_redirects=True, verify=True)
    except requests.exceptions.SSLError as ssl_err:
        ssl_valid = False
        ssl_error_detail = str(ssl_err)
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp = session.get(raw_url, timeout=12, allow_redirects=True, verify=False)
        except Exception as inner_err:
            raise ValueError(f"ไม่สามารถเชื่อมต่อกับ {raw_url} ได้: {inner_err}")
    except Exception as req_err:
        # If https:// failed on localhost, automatically try http://
        if raw_url.startswith("https://") and ("localhost" in raw_url or "127.0.0.1" in raw_url):
            raw_url = "http://" + raw_url[len("https://"):]
            parsed_root = urlparse(raw_url)
            base_origin = f"{parsed_root.scheme}://{parsed_root.netloc}"
            resp = session.get(raw_url, timeout=12, allow_redirects=True, verify=False)
        else:
            raise ValueError(f"ไม่สามารถเชื่อมต่อกับเว็บไซต์เป้าหมาย ({raw_url}): {req_err}")

    primary_latency_ms = int((time.time() - req_start) * 1000)
    final_url = resp.url or raw_url
    final_parsed = urlparse(final_url)
    headers_lower = {k.lower(): v for k, v in resp.headers.items()}
    html_body = resp.text or ""

    crawled_pages.append(
        {
            "url": final_url,
            "status_code": resp.status_code,
            "latency_ms": primary_latency_ms,
            "content_type": headers_lower.get("content-type", ""),
            "size_bytes": len(resp.content or b""),
        }
    )

    # --- 2. Optional Headless Chromium SPA Render (for React/Vue/Svelte/Next.js) ---
    spa_info = {"rendered": False, "framework_detected": ""}
    if scan_profile == "spa_headless" or (
        "<div id=\"app\"></div>" in html_body
        or "<div id=\"root\"></div>" in html_body
        or "__NEXT_DATA__" in html_body
    ):
        if scan_profile in ("spa_headless", "full_web"):
            spa_info = _try_headless_spa_capture(final_url, extra_headers)
            if spa_info.get("rendered") and spa_info.get("html"):
                html_body = spa_info["html"]
                for xurl in spa_info.get("xhr_urls") or []:
                    if xurl not in discovered_apis:
                        discovered_apis.append(xurl)

    # --- 3. Transport & TLS / HTTPS Checks ---
    if final_parsed.scheme != "https":
        header_checks.append(
            {
                "header": "HTTPS / TLS Encryption",
                "status": "fail",
                "value": f"ใช้โปรโตคอล {final_parsed.scheme.upper()} (ไม่เข้ารหัส)",
                "recommendation": "เปิดใช้งาน HTTPS (TLS 1.2/1.3) และบังคับ Redirect HTTP -> HTTPS",
            }
        )
        add_finding(
            severity="High",
            category="Transport Security",
            owasp="A02:2021 Cryptographic Failures",
            cwe="CWE-319",
            title="เว็บไซต์ไม่ได้ใช้งาน HTTPS (Cleartext HTTP Transmission)",
            description="การรับส่งข้อมูลผ่าน HTTP ปกติทำให้ข้อมูลสำคัญ เช่น รหัสผ่าน, Session Cookie หรือ Token เสี่ยงต่อการถูกดักฟัง (Man-in-the-Middle)",
            remediation="ติดตั้งใบรับรอง SSL/TLS (เช่น Let's Encrypt หรือ Cloudflare) และตั้งค่า HTTP 301 Redirect ไปยัง HTTPS ทุกเส้นทาง",
            target=final_url,
            evidence=f"Scheme: {final_parsed.scheme}://",
        )
    elif not ssl_valid:
        header_checks.append(
            {
                "header": "SSL/TLS Certificate",
                "status": "fail",
                "value": "ใบรับรอง SSL ไม่ถูกต้องหรือหมดอายุ",
                "recommendation": "ตรวจสอบใบรับรอง SSL/TLS ให้ตรงกับโดเมนและยังไม่หมดอายุ",
            }
        )
        add_finding(
            severity="High",
            category="Transport Security",
            owasp="A02:2021 Cryptographic Failures",
            cwe="CWE-295",
            title="ใบรับรอง SSL/TLS ไม่ผ่านการตรวจสอบ (Invalid / Self-Signed Certificate)",
            description="ใบรับรอง SSL ของเซิร์ฟเวอร์ไม่ถูกต้อง หมดอายุ หรือเป็น Self-Signed ทำให้เบราว์เซอร์แจ้งเตือนและเสี่ยงต่อการถูกปลอมแปลงเซิร์ฟเวอร์",
            remediation="ต่ออายุหรือติดตั้งใบรับรอง SSL จาก Certificate Authority (CA) ที่เชื่อถือได้ และตรวจสอบ Intermediate Chain ให้ครบถ้วน",
            target=final_url,
            evidence=ssl_error_detail[:220],
        )
    else:
        header_checks.append(
            {
                "header": "HTTPS / TLS Encryption",
                "status": "pass",
                "value": "HTTPS Enabled (Valid TLS)",
                "recommendation": "เข้ารหัสการเชื่อมต่อด้วย HTTPS เรียบร้อยแล้ว",
            }
        )

    # --- 4. HTTP Security Headers Audit ---
    # 4.1 CSP
    csp = headers_lower.get("content-security-policy", "")
    if not csp:
        header_checks.append(
            {
                "header": "Content-Security-Policy (CSP)",
                "status": "fail",
                "value": "ไม่พบ Header นี้",
                "recommendation": "กำหนด Content-Security-Policy เพื่อจำกัดแหล่งที่มาของ Script และป้องกัน XSS",
            }
        )
        add_finding(
            severity="Medium",
            category="Security Headers",
            owasp="A05:2021 Security Misconfiguration",
            cwe="CWE-693",
            title="ไม่พบการกำหนด Content-Security-Policy (CSP) Header",
            description="การไม่ระบุ Content-Security-Policy ทำให้เบราว์เซอร์อนุญาตให้รัน Inline Script หรือโหลด Script จากโดเมนภายนอกได้หากเกิดช่องโหว่ XSS",
            remediation="เพิ่ม HTTP Response Header `Content-Security-Policy: default-src 'self'; object-src 'none'; frame-ancestors 'self'; base-uri 'self'`",
            target=final_url,
            evidence="Missing response header: Content-Security-Policy",
        )
    elif "'unsafe-inline'" in csp or "'unsafe-eval'" in csp or " *" in csp:
        header_checks.append(
            {
                "header": "Content-Security-Policy (CSP)",
                "status": "warn",
                "value": csp[:120],
                "recommendation": "หลีกเลี่ยงการใช้ 'unsafe-inline', 'unsafe-eval' หรือ Wildcard (*) ใน CSP",
            }
        )
        add_finding(
            severity="Low",
            category="Security Headers",
            owasp="A05:2021 Security Misconfiguration",
            cwe="CWE-693",
            title="นโยบาย Content-Security-Policy (CSP) อนุญาต 'unsafe-inline' หรือ 'unsafe-eval'",
            description="พบการตั้งค่า CSP ที่ยังมีคำสั่ง `'unsafe-inline'` หรือ `'unsafe-eval'` ซึ่งลดทอนประสิทธิภาพในการป้องกัน Cross-Site Scripting (XSS)",
            remediation="เปลี่ยนไปใช้ CSP Nonce หรือ Hash สำหรับ Inline Script และนำ `'unsafe-eval'` ออก",
            target=final_url,
            evidence=csp[:200],
        )
    else:
        header_checks.append(
            {
                "header": "Content-Security-Policy (CSP)",
                "status": "pass",
                "value": csp[:120],
                "recommendation": "ตั้งค่า CSP อย่างรัดกุมแล้ว",
            }
        )

    # 4.2 HSTS
    hsts = headers_lower.get("strict-transport-security", "")
    if final_parsed.scheme == "https":
        if not hsts:
            header_checks.append(
                {
                    "header": "Strict-Transport-Security (HSTS)",
                    "status": "warn",
                    "value": "ไม่พบ Header นี้",
                    "recommendation": "เพิ่ม Strict-Transport-Security: max-age=31536000; includeSubDomains",
                }
            )
            add_finding(
                severity="Low",
                category="Security Headers",
                owasp="A05:2021 Security Misconfiguration",
                cwe="CWE-319",
                title="ไม่พบ Strict-Transport-Security (HSTS) Header บน HTTPS",
                description="เว็บไซต์ใช้ HTTPS แต่ไม่ได้ส่ง HSTS Header ทำให้ผู้ใช้ที่เข้าผ่านลิงก์ HTTP ครั้งแรกยังเสี่ยงต่อ SSL Stripping",
                remediation="ตั้งค่า Header `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`",
                target=final_url,
                evidence="Missing response header: Strict-Transport-Security",
            )
        else:
            header_checks.append(
                {
                    "header": "Strict-Transport-Security (HSTS)",
                    "status": "pass",
                    "value": hsts[:100],
                    "recommendation": "เปิดใช้งาน HSTS เรียบร้อยแล้ว",
                }
            )

    # 4.3 Clickjacking (X-Frame-Options / frame-ancestors)
    xfo = headers_lower.get("x-frame-options", "")
    has_frame_ancestors = "frame-ancestors" in csp.lower()
    if not xfo and not has_frame_ancestors:
        header_checks.append(
            {
                "header": "X-Frame-Options / frame-ancestors",
                "status": "fail",
                "value": "ไม่พบการป้องกัน Clickjacking",
                "recommendation": "กำหนด X-Frame-Options: DENY หรือ SAMEORIGIN",
            }
        )
        add_finding(
            severity="Medium",
            category="Security Headers",
            owasp="A05:2021 Security Misconfiguration",
            cwe="CWE-1021",
            title="ขาดการป้องกัน Clickjacking (ไม่พบ X-Frame-Options หรือ CSP frame-ancestors)",
            description="หน้าเว็บสามารถถูกนำไปฝังใน `<iframe>` บนเว็บไซต์ของผู้โจมตีเพื่อหลอกให้ผู้ใช้คลิกทำรายการโดยไม่รู้ตัว (Clickjacking)",
            remediation="เพิ่ม Header `X-Frame-Options: SAMEORIGIN` (หรือ `DENY`) และกำหนด `frame-ancestors 'self'` ใน CSP",
            target=final_url,
            evidence="Missing X-Frame-Options and CSP frame-ancestors",
        )
    else:
        header_checks.append(
            {
                "header": "X-Frame-Options / frame-ancestors",
                "status": "pass",
                "value": xfo or "CSP frame-ancestors",
                "recommendation": "มีการป้องกันการฝัง Iframe (Clickjacking) แล้ว",
            }
        )

    # 4.4 X-Content-Type-Options
    xcto = headers_lower.get("x-content-type-options", "")
    if xcto.lower() != "nosniff":
        header_checks.append(
            {
                "header": "X-Content-Type-Options",
                "status": "warn",
                "value": xcto or "ไม่พบ Header นี้",
                "recommendation": "ตั้งค่า X-Content-Type-Options: nosniff",
            }
        )
        add_finding(
            severity="Low",
            category="Security Headers",
            owasp="A05:2021 Security Misconfiguration",
            cwe="CWE-16",
            title="ไม่พบ Header X-Content-Type-Options: nosniff",
            description="เบราว์เซอร์อาจพยายามเดาประเภทไฟล์เอง (MIME-Sniffing) ซึ่งอาจนำไปสู่การรันโค้ดจากไฟล์ที่อัปโหลด",
            remediation="เพิ่ม HTTP Response Header `X-Content-Type-Options: nosniff`",
            target=final_url,
            evidence="Missing X-Content-Type-Options: nosniff",
        )
    else:
        header_checks.append(
            {
                "header": "X-Content-Type-Options",
                "status": "pass",
                "value": "nosniff",
                "recommendation": "ป้องกัน MIME-Sniffing เรียบร้อยแล้ว",
            }
        )

    # 4.5 Referrer-Policy & Permissions-Policy
    ref_pol = headers_lower.get("referrer-policy", "")
    perm_pol = headers_lower.get("permissions-policy", "")
    header_checks.append(
        {
            "header": "Referrer-Policy",
            "status": "pass" if ref_pol else "warn",
            "value": ref_pol or "ไม่พบ Header นี้",
            "recommendation": "แนะนำ strict-origin-when-cross-origin หรือ no-referrer",
        }
    )
    header_checks.append(
        {
            "header": "Permissions-Policy",
            "status": "pass" if perm_pol else "warn",
            "value": (perm_pol[:90] if perm_pol else "ไม่พบ Header นี้"),
            "recommendation": "แนะนำจำกัดสิทธิ์ Browser API เช่น camera=(), microphone=(), geolocation=()",
        }
    )

    # 4.6 Server Version / Technology Fingerprint Disclosure
    leaked_tech = []
    for h_name in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator"):
        val = headers_lower.get(h_name, "")
        if val and re.search(r"\d+\.\d+", val):
            leaked_tech.append(f"{h_name}: {val}")
    if leaked_tech:
        add_finding(
            severity="Low",
            category="Information Disclosure",
            owasp="A05:2021 Security Misconfiguration",
            cwe="CWE-200",
            title="เซิร์ฟเวอร์เปิดเผยหมายเลขเวอร์ชันของซอฟต์แวร์ใน HTTP Headers",
            description="การเปิดเผยชื่อและหมายเลขเวอร์ชันของ Web Server หรือ Framework ช่วยให้ผู้โจมตีค้นหา CVE ที่จำเพาะเจาะจงกับเวอร์ชันนั้นได้ง่ายขึ้น",
            remediation="ปิดการแสดงเลขเวอร์ชันใน Web Server (เช่น `server_tokens off;` ใน Nginx หรือ `app.disable('x-powered-by')` ใน Express)",
            target=final_url,
            evidence="; ".join(leaked_tech),
        )

    # --- 5. CORS Misconfiguration Probe ---
    try:
        evil_origin = "https://evil.scanner.invalid"
        cors_resp = session.get(
            final_url,
            headers={**extra_headers, "Origin": evil_origin},
            timeout=6,
            verify=False,
        )
        acao = (cors_resp.headers.get("Access-Control-Allow-Origin") or "").strip()
        acac = (cors_resp.headers.get("Access-Control-Allow-Credentials") or "").strip().lower()
        if acao == evil_origin and acac == "true":
            header_checks.append(
                {
                    "header": "CORS Policy",
                    "status": "fail",
                    "value": f"Allow-Origin สะท้อน {evil_origin} + Allow-Credentials: true",
                    "recommendation": "ตรวจสอบ Origin กับ Whitelist ที่อนุญาตเท่านั้น",
                }
            )
            add_finding(
                severity="Critical",
                category="CORS Misconfiguration",
                owasp="A01:2021 Broken Access Control",
                cwe="CWE-942",
                title="ตั้งค่า CORS อันตราย: สะท้อน Origin แปลกปลอมพร้อมอนุญาต Credentials",
                description="เซิร์ฟเวอร์ตอบกลับ `Access-Control-Allow-Origin` ตาม Origin ใดๆ ที่ส่งเข้าไป พร้อมกับ `Access-Control-Allow-Credentials: true` ทำให้เว็บไซต์ภายนอกสามารถขโมยข้อมูลผู้ใช้ที่ล็อกอินอยู่ได้ทันที",
                remediation="กำหนด Whitelist ของโดเมนที่อนุญาตอย่างชัดเจน และห้ามสะท้อนค่า `Origin` จาก Request Header โดยไม่ตรวจสอบ",
                target=final_url,
                evidence=f"Access-Control-Allow-Origin: {acao}, Access-Control-Allow-Credentials: {acac}",
            )
        elif acao == "*":
            header_checks.append(
                {
                    "header": "CORS Policy",
                    "status": "warn",
                    "value": "Access-Control-Allow-Origin: *",
                    "recommendation": "หากเป็น API ภายใน ควรจำกัดเฉพาะโดเมนของ Frontend ที่ใช้งานจริง",
                }
            )
        else:
            header_checks.append(
                {
                    "header": "CORS Policy",
                    "status": "pass",
                    "value": acao or "Restricted (Same-Origin)",
                    "recommendation": "ไม่พบการเปิด CORS แบบไม่ปลอดภัย",
                }
            )
    except Exception:
        pass

    # --- 6. Cookie & Session Security Audit ---
    raw_set_cookies = []
    if hasattr(resp.raw, "headers") and hasattr(resp.raw.headers, "getlist"):
        raw_set_cookies = resp.raw.headers.getlist("Set-Cookie")
    elif resp.headers.get("Set-Cookie"):
        raw_set_cookies = [resp.headers.get("Set-Cookie")]

    for sc in raw_set_cookies:
        if not sc:
            continue
        cookie_name = sc.split("=", 1)[0].strip()
        sc_lower = sc.lower()
        missing_flags = []
        if "httponly" not in sc_lower:
            missing_flags.append("HttpOnly")
        if final_parsed.scheme == "https" and "secure" not in sc_lower:
            missing_flags.append("Secure")
        if "samesite" not in sc_lower:
            missing_flags.append("SameSite")

        if missing_flags:
            is_session_like = any(k in cookie_name.lower() for k in ("sess", "token", "jwt", "auth", "sid", "user"))
            add_finding(
                severity="Medium" if is_session_like else "Low",
                category="Cookie & Session Security",
                owasp="A07:2021 Identification and Authentication Failures",
                cwe="CWE-614",
                title=f"คุกกี้ `{cookie_name}` ขาดคุณสมบัติความปลอดภัย ({', '.join(missing_flags)})",
                description=f"คุกกี้ `{cookie_name}` ถูกตั้งค่าโดยไม่มีแฟล็ก {', '.join(missing_flags)} ทำให้เสี่ยงต่อการถูกอ่านด้วย JavaScript (XSS) หรือถูกส่งผ่านช่องทางที่ไม่ปลอดภัย",
                remediation=f"ตั้งค่าคุกกี้โดยระบุ `HttpOnly; Secure; SameSite=Lax` (หรือ `Strict` สำหรับ Session Cookie)",
                target=final_url,
                evidence=sc[:180],
            )

    # --- 7. DOM, Forms, Mixed Content, SRI & Client-Side JS Bundle Audit ---
    soup = BeautifulSoup(html_body, "html.parser")

    # 7.1 Mixed Content on HTTPS page
    if final_parsed.scheme == "https":
        mixed_resources = []
        for tag, attr in (("script", "src"), ("iframe", "src"), ("link", "href"), ("img", "src")):
            for el in soup.find_all(tag):
                val = (el.get(attr) or "").strip()
                if val.startswith("http://"):
                    mixed_resources.append(f"<{tag} {attr}=\"{val}\">")
        if mixed_resources:
            add_finding(
                severity="Medium",
                category="Transport Security",
                owasp="A02:2021 Cryptographic Failures",
                cwe="CWE-311",
                title="ตรวจพบ Mixed Content (โหลดทรัพยากรผ่าน HTTP บนหน้าเว็บ HTTPS)",
                description="หน้าเว็บ HTTPS มีการเรียกโหลด Script, Iframe หรือทรัพยากรผ่าน `http://` ซึ่งอาจถูกบล็อกโดยเบราว์เซอร์หรือถูกดัดแปลงระหว่างทาง",
                remediation="เปลี่ยน URL ของทรัพยากรทั้งหมดให้เป็น `https://`",
                target=final_url,
                evidence=", ".join(mixed_resources[:3]),
            )

    # 7.2 External Scripts without Subresource Integrity (SRI)
    external_no_sri = []
    script_urls_to_fetch = []
    for s_tag in soup.find_all("script"):
        src = (s_tag.get("src") or "").strip()
        if not src:
            continue
        full_src = urljoin(final_url, src)
        src_parsed = urlparse(full_src)
        if src_parsed.netloc and src_parsed.netloc != final_parsed.netloc:
            if not s_tag.get("integrity"):
                external_no_sri.append(full_src)
        elif src_parsed.netloc == final_parsed.netloc and len(script_urls_to_fetch) < 6:
            script_urls_to_fetch.append(full_src)

    if external_no_sri:
        add_finding(
            severity="Low",
            category="Supply Chain & Client Integrity",
            owasp="A08:2021 Software and Data Integrity Failures",
            cwe="CWE-829",
            title=f"โหลด JavaScript จากภายนอก ({len(external_no_sri)} ไฟล์) โดยไม่ระบุ Subresource Integrity (SRI)",
            description="การโหลดสคริปต์จาก CDN หรือโดเมนภายนอกโดยไม่มีแอตทริบิวต์ `integrity` ทำให้หาก CDN ถูกเจาะ ผู้โจมตีจะสามารถรันโค้ดอันตรายบนเว็บได้ทันที",
            remediation="เพิ่ม `integrity=\"sha384-...\" crossorigin=\"anonymous\"` ให้กับ `<script>` ที่โหลดจาก CDN ภายนอก",
            target=final_url,
            evidence=external_no_sri[0],
        )

    # 7.3 Forms Security (Insecure HTTP action, missing CSRF on POST, password autocomplete)
    for idx, form in enumerate(soup.find_all("form"), 1):
        action = (form.get("action") or "").strip()
        method = (form.get("method") or "GET").upper().strip()
        full_action = urljoin(final_url, action) if action else final_url
        inputs = form.find_all(["input", "textarea", "select"])
        input_names = [(inp.get("name") or inp.get("id") or "").lower() for inp in inputs]
        has_password = any((inp.get("type") or "").lower() == "password" for inp in inputs)
        has_csrf = any(any(k in nm for k in ("csrf", "xsrf", "token", "_token", "authenticity")) for nm in input_names)

        discovered_forms.append(
            {
                "action": full_action,
                "method": method,
                "inputs_count": len(inputs),
                "has_password": has_password,
                "has_csrf_field": has_csrf,
            }
        )

        if full_action.startswith("http://") and final_parsed.scheme == "https":
            add_finding(
                severity="High",
                category="Form & Authentication Security",
                owasp="A02:2021 Cryptographic Failures",
                cwe="CWE-319",
                title="พบฟอร์มที่ส่งข้อมูลไปยังปลายทาง HTTP ที่ไม่เข้ารหัส",
                description="ฟอร์มบนหน้า HTTPS มีการตั้งค่า `action` ส่งข้อมูลออกไปที่ `http://` ทำให้ข้อมูลที่ผู้ใช้กรอกถูกส่งแบบไม่เข้ารหัส",
                remediation="แก้ไข `action` ของ `<form>` ให้ชี้ไปยัง `https://` เสมอ",
                target=final_url,
                evidence=f"<form method=\"{method}\" action=\"{full_action}\">",
            )

        if has_password and method == "GET":
            add_finding(
                severity="Critical",
                category="Form & Authentication Security",
                owasp="A07:2021 Identification and Authentication Failures",
                cwe="CWE-598",
                title="ฟอร์มรหัสผ่านใช้ HTTP GET ทำให้รหัสผ่านหลุดไปอยู่ใน URL Query String",
                description="พบช่องกรอกรหัสผ่าน (`type=\"password\"`) อยู่ใน `<form method=\"GET\">` ซึ่งจะทำให้รหัสผ่านปรากฏใน URL, Browser History และ Server Access Logs",
                remediation="เปลี่ยน `<form method=\"POST\">` สำหรับฟอร์มเข้าสู่ระบบหรือฟอร์มที่มีข้อมูลสำคัญทั้งหมด",
                target=final_url,
                evidence=f"Form #{idx} action={full_action} method=GET with password input",
            )

        if method == "POST" and not has_csrf and not spa_info.get("framework_detected"):
            add_finding(
                severity="Low",
                category="CSRF Protection",
                owasp="A01:2021 Broken Access Control",
                cwe="CWE-352",
                title="พบฟอร์ม POST ที่ไม่มีฟิลด์ Anti-CSRF Token ใน HTML",
                description="ฟอร์มแบบ `<form method=\"POST\">` ไม่มีฟิลด์ซ่อนสำหรับตรวจสอบ CSRF Token ซึ่งอาจเสี่ยงต่อ Cross-Site Request Forgery หากใช้ Cookie-based Session",
                remediation="เพิ่ม Anti-CSRF Token ในฟอร์ม หรือใช้ `SameSite=Strict/Lax` คู่กับการส่ง Custom Headerผ่าน Fetch/XHR",
                target=final_url,
                evidence=f"<form method=\"POST\" action=\"{full_action}\">",
            )

    # 7.4 Scan HTML & Same-Origin JS Bundles for Hardcoded Secrets & API Routes
    js_blobs_to_scan: List[Tuple[str, str]] = [(final_url, html_body)]
    for js_url in script_urls_to_fetch:
        try:
            js_res = session.get(js_url, timeout=6, verify=False)
            if js_res.status_code == 200 and len(js_res.text) < 2_500_000:
                scripts_analyzed.append(js_url)
                js_blobs_to_scan.append((js_url, js_res.text))
                # Check if source map (.map) is publicly exposed
                if scan_profile in ("full_web", "spa_headless"):
                    map_url = js_url + ".map"
                    map_res = session.head(map_url, timeout=4, verify=False)
                    if map_res.status_code == 200 and "html" not in (map_res.headers.get("Content-Type") or "").lower():
                        add_finding(
                            severity="Low",
                            category="Information Disclosure",
                            owasp="A05:2021 Security Misconfiguration",
                            cwe="CWE-540",
                            title="เปิดเผยไฟล์ JavaScript Source Map (.js.map) บน Production",
                            description="ไฟล์ `.js.map` สามารถเข้าถึงได้จากภายนอก ทำให้ผู้โจมตีสามารถถอดรหัสโครงสร้าง Source Code ต้นฉบับของ Frontend ได้ทั้งหมด",
                            remediation="ปิดการสร้างหรือบล็อกการเข้าถึงไฟล์ `*.map` บน Production Web Server",
                            target=map_url,
                            evidence=f"HTTP 200 on {map_url}",
                        )
        except Exception:
            pass

    api_route_regex = re.compile(r"""['"`](/(?:api|v1|v2|v3|graphql|auth|admin|users|orders)[a-zA-Z0-9_\-/]*?)['"`]""")
    for src_label, content_blob in js_blobs_to_scan:
        # Extract API routes referenced in frontend code
        for m in api_route_regex.finditer(content_blob):
            route_path = m.group(1)
            if len(route_path) > 3 and not route_path.endswith((".png", ".jpg", ".svg", ".css", ".js")):
                entry = f"GET {urljoin(base_origin, route_path)}"
                if entry not in discovered_apis and len(discovered_apis) < 50:
                    discovered_apis.append(entry)

        # Scan for hardcoded secrets
        for sec_name, pattern, cwe_id, sev in SECRET_PATTERNS:
            m = re.search(pattern, content_blob)
            if m:
                matched_val = m.group(0)
                masked = matched_val[:8] + "..." + matched_val[-4:] if len(matched_val) > 14 else matched_val
                add_finding(
                    severity=sev,
                    category="Secret & Credential Exposure",
                    owasp="A02:2021 Cryptographic Failures",
                    cwe=cwe_id,
                    title=f"ตรวจพบ {sec_name} ฝังอยู่ในโค้ดฝั่ง Client / HTML",
                    description=f"พบกุญแจความลับหรือ Token ({sec_name}) ถูกส่งมาในไฟล์ HTML หรือ JavaScript Bundle ซึ่งผู้ใช้ทุกคนสามารถเปิดดูผ่าน DevTools ได้",
                    remediation="ทำการ Revoke กุญแจดังกล่าวทันที และย้ายการเรียก API ที่ต้องใช้ Secret Key ไปไว้ที่ฝั่ง Backend Server เท่านั้น",
                    target=src_label,
                    evidence=masked,
                )

    # --- 8. Sensitive Path & Manifest Probing (with Soft-404 Baseline Detection) ---
    if scan_profile in ("full_web", "spa_headless"):
        baseline_404_len = -1
        baseline_404_text = ""
        try:
            b404 = session.get(urljoin(base_origin, f"/__spectra_nonexistent_{uuid.uuid4().hex[:8]}__"), timeout=5, verify=False)
            baseline_404_len = len(b404.text or "")
            baseline_404_text = (b404.text or "")[:300]
        except Exception:
            pass

        sensitive_probes = [
            ("/.env", "Critical", "CWE-538", "ไฟล์ตัวแปรสภาพแวดล้อม (/.env) เปิดให้เข้าถึงจากภายนอก", "DB_PASSWORD", "บล็อกการเข้าถึงไฟล์ที่ขึ้นต้นด้วยจุด (`.env`, `.git`) ใน Web Server ทันที"),
            ("/.git/config", "Critical", "CWE-538", "โฟลเดอร์ Git Repository (/.git/config) เปิดให้ดาวน์โหลดจากภายนอก", "[core]", "บล็อกการเข้าถึง `/.git` ใน Nginx/Apache และลบโฟลเดอร์ `.git` ออกจาก Production"),
            ("/swagger.json", "Info", "CWE-200", "ตรวจพบเอกสาร OpenAPI / Swagger Specification เปิดสาธารณะ (/swagger.json)", "\"paths\"", "หากไม่ใช่ Public API ควรจำกัดสิทธิ์การเข้าถึงหน้า Swagger/OpenAPI เฉพาะเครือข่ายภายใน"),
            ("/openapi.json", "Info", "CWE-200", "ตรวจพบเอกสาร OpenAPI Specification เปิดสาธารณะ (/openapi.json)", "\"openapi\"", "หากไม่ใช่ Public API ควรจำกัดสิทธิ์การเข้าถึงหน้า OpenAPI เฉพาะผู้ดูแลระบบ"),
            ("/actuator/env", "Critical", "CWE-200", "Spring Boot Actuator (/actuator/env) เปิดเผยข้อมูล Environment สู่สาธารณะ", "propertySources", "ปิด Spring Boot Actuator Endpoints บน Production หรือบังคับ Authentication"),
            ("/phpinfo.php", "High", "CWE-200", "ตรวจพบหน้า phpinfo.php เปิดเผยโครงสร้างเซิร์ฟเวอร์", "phpinfo()", "ลบไฟล์ `phpinfo.php` ออกจากเซิร์ฟเวอร์ Production"),
        ]

        for probe_path, sev, cwe_id, title_th, must_contain, remed_th in sensitive_probes:
            probe_url = urljoin(base_origin, probe_path)
            try:
                p_res = session.get(probe_url, timeout=4, allow_redirects=False, verify=False)
                body_sample = p_res.text or ""
                is_soft_404 = (
                    baseline_404_len > 0
                    and abs(len(body_sample) - baseline_404_len) < 60
                    and body_sample[:120] == baseline_404_text[:120]
                )
                if p_res.status_code == 200 and not is_soft_404 and must_contain.lower() in body_sample.lower():
                    add_finding(
                        severity=sev,
                        category="Sensitive File & Endpoint Exposure",
                        owasp="A05:2021 Security Misconfiguration",
                        cwe=cwe_id,
                        title=title_th,
                        description=f"สามารถเข้าถึง `{probe_path}` ได้โดยไม่ต้องยืนยันตัวตน (HTTP 200) และพบเนื้อหาสำคัญภายในไฟล์",
                        remediation=remed_th,
                        target=probe_url,
                        evidence=f"HTTP 200 OK on {probe_url} (matched '{must_contain}')",
                    )
            except Exception:
                pass

    # --- 9. Same-Origin Multi-Page Crawl & Active Safe OWASP Probe ---
    if scan_profile in ("full_web", "spa_headless") and max_pages > 1:
        internal_links = []
        for a_tag in soup.find_all("a", href=True):
            href = (a_tag.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            full_link = urljoin(final_url, href)
            lp = urlparse(full_link)
            if lp.netloc == final_parsed.netloc and full_link not in [p["url"] for p in crawled_pages]:
                if full_link not in internal_links:
                    internal_links.append(full_link)

        for link_url in internal_links[: max(0, int(max_pages) - 1)]:
            try:
                t_link = time.time()
                l_res = session.get(link_url, timeout=6, verify=False)
                crawled_pages.append(
                    {
                        "url": link_url,
                        "status_code": l_res.status_code,
                        "latency_ms": int((time.time() - t_link) * 1000),
                        "content_type": l_res.headers.get("Content-Type", ""),
                        "size_bytes": len(l_res.content or b""),
                    }
                )
            except Exception:
                pass

        # Safe Reflection & Open Redirect Probe on query parameters
        query_pairs = parse_qsl(final_parsed.query, keep_blank_values=True)
        redirect_param_names = {"next", "redirect", "url", "return", "returnurl", "return_to", "goto", "dest", "continue"}
        canary = f"SpectraProbe{uuid.uuid4().hex[:6]}"
        for q_key, _ in query_pairs[:4]:
            if q_key.lower() in redirect_param_names:
                test_q = dict(query_pairs)
                test_q[q_key] = "https://evil.scanner.invalid"
                probe_u = urlunparse(final_parsed._replace(query=urlencode(test_q)))
                try:
                    r_res = session.get(probe_u, timeout=5, allow_redirects=False, verify=False)
                    loc = (r_res.headers.get("Location") or "").strip()
                    if r_res.status_code in (301, 302, 303, 307, 308) and loc.startswith("https://evil.scanner.invalid"):
                        add_finding(
                            severity="High",
                            category="Open Redirect",
                            owasp="A01:2021 Broken Access Control",
                            cwe="CWE-601",
                            title=f"ตรวจพบช่องโหว่ Open Redirect ที่พารามิเตอร์ `{q_key}`",
                            description=f"พารามิเตอร์ `{q_key}` ยอมให้ Redirect ผู้ใช้ไปยังโดเมนภายนอกใดๆ ได้โดยไม่ตรวจสอบ ทำให้เสี่ยงต่อการถูกใช้ทำ Phishing",
                            remediation="ตรวจสอบค่า URL ปลายทางให้เป็น Relative Path ภายในระบบ หรือเทียบกับรายการโดเมนที่อนุญาตเท่านั้น",
                            target=probe_u,
                            evidence=f"HTTP {r_res.status_code} Location: {loc}",
                        )
                except Exception:
                    pass

            # Safe XSS reflection context probe using harmless alphanumeric canary + symbol check
            test_q = dict(query_pairs)
            test_q[q_key] = f"{canary}<\"'>"
            probe_u = urlunparse(final_parsed._replace(query=urlencode(test_q)))
            try:
                x_res = session.get(probe_u, timeout=5, verify=False)
                if f"{canary}<\"'>" in (x_res.text or ""):
                    add_finding(
                        severity="High",
                        category="Cross-Site Scripting (XSS)",
                        owasp="A03:2021 Injection",
                        cwe="CWE-79",
                        title=f"พารามิเตอร์ `{q_key}` สะท้อนอักขระพิเศษ `<\"'>` กลับใน HTML โดยไม่ทำ HTML Encoding",
                        description=f"ค่าที่ส่งผ่าน Query Parameter `{q_key}` ถูกแสดงผลกลับในหน้าเว็บโดยตรงโดยไม่แปลงอักขระพิเศษ (`<`, `>`, `\"`, `'`) ทำให้มีความเสี่ยงสูงต่อ Reflected XSS",
                        remediation="ทำ Contextual Output Encoding (HTML Entity Encoding) ทุกครั้งก่อนนำค่าจาก Request ไปแสดงผลใน HTML",
                        target=probe_u,
                        evidence=f"Unescaped reflection of {canary}<\"'> in response body",
                    )
            except Exception:
                pass

    # Sort findings by severity
    # --- 10. Standard-Specific Deep Verification Modules ---
    std_key = (standard or "").upper()

    if "ASVS" in std_key:
        # OWASP ASVS 4.0.3 (Level 2) Specific Checks
        cc_val = headers_lower.get("cache-control", "")
        if "no-store" not in cc_val.lower():
            header_checks.append(
                {
                    "header": "Cache-Control (ASVS V8.3.4)",
                    "status": "warn",
                    "value": cc_val or "ไม่พบ Header นี้",
                    "recommendation": "กำหนด Cache-Control: no-store, max-age=0 สำหรับหน้าเว็บหรือ API ที่มีข้อมูลผู้ใช้",
                }
            )
            add_finding(
                severity="Low",
                category="ASVS V8 Data Protection",
                owasp="ASVS V8.3.4 / V14.4.7",
                cwe="CWE-525",
                title="ไม่ได้กำหนด Cache-Control: no-store ตามเกณฑ์ OWASP ASVS 4.0.3",
                description="การไม่ระบุ `Cache-Control: no-store` อาจทำให้เบราว์เซอร์หรือ Shared Proxy บันทึกหน้าเว็บที่มีข้อมูลสำคัญไว้ใน Local Cache",
                remediation="ตั้งค่า Header `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`",
                target=final_url,
                evidence=f"Cache-Control: {cc_val or 'Missing'}",
            )
        else:
            header_checks.append(
                {
                    "header": "Cache-Control (ASVS V8.3.4)",
                    "status": "pass",
                    "value": cc_val,
                    "recommendation": "ป้องกันการแคชข้อมูลสำคัญตามเกณฑ์ ASVS แล้ว",
                }
            )

        coop_val = headers_lower.get("cross-origin-opener-policy", "")
        corp_val = headers_lower.get("cross-origin-resource-policy", "")
        if not coop_val or not corp_val:
            header_checks.append(
                {
                    "header": "COOP / CORP Isolation (ASVS V14.4)",
                    "status": "warn",
                    "value": f"COOP: {coop_val or 'Missing'}, CORP: {corp_val or 'Missing'}",
                    "recommendation": "กำหนด Cross-Origin-Opener-Policy: same-origin และ Cross-Origin-Resource-Policy: same-origin",
                }
            )
            add_finding(
                severity="Low",
                category="ASVS V14 Configuration",
                owasp="ASVS V14.4.5 / V14.4.6",
                cwe="CWE-693",
                title="ขาด Cross-Origin Isolation Headers (COOP / CORP) ตามเกณฑ์เชิงลึก ASVS 4.0.3",
                description="ไม่พบ `Cross-Origin-Opener-Policy` หรือ `Cross-Origin-Resource-Policy` ซึ่งช่วยป้องกันการโจมตีระดับโปรเซสของเบราว์เซอร์ (Spectre / Cross-Window Leaks)",
                remediation="เพิ่ม Header `Cross-Origin-Opener-Policy: same-origin` และ `Cross-Origin-Resource-Policy: same-origin`",
                target=final_url,
                evidence=f"COOP={coop_val or 'none'}, CORP={corp_val or 'none'}",
            )

        unsafe_blank_links = []
        for a_el in soup.find_all("a", target="_blank"):
            rel_val = " ".join(a_el.get("rel") or []) if isinstance(a_el.get("rel"), list) else str(a_el.get("rel") or "")
            if "noopener" not in rel_val.lower() and "noreferrer" not in rel_val.lower():
                unsafe_blank_links.append(a_el.get("href") or "target=_blank")
        if unsafe_blank_links:
            add_finding(
                severity="Low",
                category="ASVS V14 Client Integrity",
                owasp="ASVS V14.2.2",
                cwe="CWE-1022",
                title=f"พบลิงก์ `target=\"_blank\"` ({len(unsafe_blank_links)} จุด) ที่ไม่ระบุ `rel=\"noopener\"` (Reverse Tabnabbing)",
                description="การเปิดแท็บใหม่ด้วย `target=\"_blank\"` โดยไม่มี `rel=\"noopener noreferrer\"` อาจทำให้หน้าเว็บปลายทางเข้าถึง `window.opener` ได้บนเบราว์เซอร์รุ่นเก่า",
                remediation="เพิ่ม `rel=\"noopener noreferrer\"` ให้กับลิงก์ที่เปิดแท็บใหม่ทั้งหมด",
                target=final_url,
                evidence=str(unsafe_blank_links[0])[:160],
            )

    if "API" in std_key:
        # OWASP API Security Top 10 (2023) Specific Checks
        rl_headers = [k for k in headers_lower if "ratelimit" in k or k in ("retry-after", "x-rate-limit-limit")]
        if not rl_headers:
            header_checks.append(
                {
                    "header": "Rate Limiting Headers (API4:2023)",
                    "status": "warn",
                    "value": "ไม่พบ X-RateLimit-Limit / RateLimit-Limit",
                    "recommendation": "กำหนด Rate Limiting และส่ง Header X-RateLimit-Limit, X-RateLimit-Remaining",
                }
            )
            add_finding(
                severity="Medium",
                category="API Resource Consumption",
                owasp="API4:2023 Unrestricted Resource Consumption",
                cwe="CWE-770",
                title="ไม่พบการกำหนด Rate Limiting Headers ป้องกันการยิงคำขอรัว (API4:2023)",
                description="เป้าหมายไม่มีการส่ง Rate Limit Headers (`X-RateLimit-Limit`, `RateLimit-Remaining`) ซึ่งอาจเสี่ยงต่อการถูกยิง Brute-force, Credential Stuffing หรือ DoS",
                remediation="ติดตั้ง Rate Limiter (เช่น Flask-Limiter, Nginx `limit_req_zone` หรือ API Gateway) และส่ง RateLimit Headers กลับเสมอ",
                target=final_url,
                evidence="Missing RateLimit / X-RateLimit-* response headers",
            )

        # Probe HTTP OPTIONS for overly permissive HTTP verbs (API8:2023)
        try:
            opt_res = session.options(final_url, timeout=5, verify=False)
            allow_hdr = (opt_res.headers.get("Allow") or opt_res.headers.get("Access-Control-Allow-Methods") or "").upper()
            risky_verbs = [v for v in ("TRACE", "TRACK", "DELETE", "PUT") if v in allow_hdr]
            if "TRACE" in risky_verbs:
                add_finding(
                    severity="Medium",
                    category="HTTP Verb Exposure",
                    owasp="API8:2023 Security Misconfiguration",
                    cwe="CWE-749",
                    title="เปิดใช้งาน HTTP TRACE Method บนเซิร์ฟเวอร์ (Cross-Site Tracing Risk)",
                    description="เซิร์ฟเวอร์อนุญาตให้เรียกใช้ HTTP `TRACE` ซึ่งจะสะท้อน Request Headers ทั้งหมดกลับไปยังผู้เรียก",
                    remediation="ปิด HTTP `TRACE` Method ในการตั้งค่า Web Server",
                    target=final_url,
                    evidence=f"Allow: {allow_hdr}",
                )
        except Exception:
            pass

        # BOLA / IDOR pattern detection in discovered API routes or URL
        bola_candidates = [
            u for u in ([final_url] + discovered_apis)
            if re.search(r"/(?:users|accounts|orders|invoices|profiles|documents|items)/\d+\b|[?&](?:user_id|account_id|order_id|doc_id|id)=\d+", u, re.I)
        ]
        if bola_candidates:
            add_finding(
                severity="Medium",
                category="Object Level Authorization",
                owasp="API1:2023 Broken Object Level Authorization",
                cwe="CWE-639",
                title="พบโครงสร้าง API/URL ที่อ้างอิง Object ID แบบตัวเลขเรียงลำดับ (BOLA / IDOR Surface)",
                description="ตรวจพบเส้นทางหรือพารามิเตอร์ที่ระบุหมายเลข ID โดยตรง ซึ่งต้องตรวจสอบที่ฝั่ง Backend ว่าผู้ใช้ที่ล็อกอินมีสิทธิ์เป็นเจ้าของ Object นั้นจริงหรือไม่",
                remediation="ตรวจสอบ Ownership (`resource.owner_id == current_user.id`) ในทุก Endpoint ที่รับ Object ID และพิจารณาใช้ UUID แทนตัวเลขเรียงลำดับ",
                target=final_url,
                evidence=bola_candidates[0][:180],
            )

    if "CWE" in std_key:
        # CWE Top 25 Specific Web & DOM Checks
        unrestricted_file_inputs = []
        for f_inp in soup.find_all("input", {"type": "file"}):
            if not (f_inp.get("accept") or "").strip():
                unrestricted_file_inputs.append(f_inp.get("name") or f_inp.get("id") or "<input type='file'>")
        if unrestricted_file_inputs:
            add_finding(
                severity="Medium",
                category="File Upload Validation",
                owasp="CWE Top 25 (#10 CWE-434)",
                cwe="CWE-434",
                title="พบช่องอัปโหลดไฟล์ `<input type=\"file\">` ที่ไม่จำกัดนามสกุลไฟล์ (`accept` attribute)",
                description="ฟอร์มอัปโหลดไฟล์ไม่ได้กำหนดแอตทริบิวต์ `accept` เพื่อจำกัดประเภทไฟล์ฝั่ง Client และต้องตรวจสอบ Magic Bytes / Whitelist นามสกุลไฟล์ที่ฝั่ง Server เพื่อป้องกันการอัปโหลด Web Shell",
                remediation="กำหนด `accept=\".pdf,.png,.jpg\"` ที่ฝั่ง Frontend และตรวจสอบ MIME Type + นามสกุลไฟล์ด้วย Whitelist ที่ฝั่ง Backend เสมอ",
                target=final_url,
                evidence=f"Unrestricted file input: {', '.join(unrestricted_file_inputs[:3])}",
            )

        ssrf_or_traversal_params = []
        for qk, _ in parse_qsl(final_parsed.query, keep_blank_values=True):
            if any(p in qk.lower() for p in ("file", "path", "doc", "template", "dir", "folder")):
                ssrf_or_traversal_params.append(("CWE-22 Path Traversal", "CWE-22", qk))
            elif any(p in qk.lower() for p in ("url", "uri", "webhook", "callback", "proxy", "fetch", "target")):
                ssrf_or_traversal_params.append(("CWE-918 SSRF", "CWE-918", qk))
        for cat_lbl, cwe_code, param_nm in ssrf_or_traversal_params:
            add_finding(
                severity="Medium",
                category=cat_lbl,
                owasp=f"CWE Top 25 ({cwe_code})",
                cwe=cwe_code,
                title=f"พบพารามิเตอร์ `{param_nm}` ที่เป็นจุดรับค่าไฟล์หรือ URL ({cat_lbl} Attack Surface)",
                description=f"พารามิเตอร์ `{param_nm}` บน URL มีลักษณะใช้ระบุตำแหน่งไฟล์หรือ URL ปลายทาง ซึ่งติดอันดับ CWE Top 25 ที่ต้องมีการกรอง Path Traversal (`../`) และ SSRF Internal IP",
                remediation="ห้ามนำค่าจากพารามิเตอร์ไปเปิดไฟล์หรือยิง HTTP Request โดยตรง ให้ใช้ ID อ้างอิงจากฐานข้อมูล หรือตรวจสอบด้วย Whitelist อย่างเข้มงวด",
                target=final_url,
                evidence=f"Query parameter: ?{param_nm}=...",
            )

    findings.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "Info"), 99))
    score, grade, counts = _compute_score_and_grade(findings, standard)

    # Optional AI Security Architect Summary
    ai_summary = None
    if use_ai:
        ai_summary = _run_optional_ai_web_summary(final_url, standard, score, grade, findings, header_checks)

    duration_sec = round(time.time() - t0, 2)
    scan_mode_label = (
        "Web DAST + Headless SPA Browser" if spa_info.get("rendered") else f"Web DAST ({scan_profile})"
    )
    report_md = _format_findings_to_markdown(
        target_label=final_url,
        scan_mode_label=scan_mode_label,
        standard=standard,
        score=score,
        grade=grade,
        counts=counts,
        findings=findings,
        header_checks=header_checks,
        ai_summary=ai_summary,
    )

    return {
        "success": True,
        "scan_mode": "web_url",
        "target": final_url,
        "standard": standard,
        "security_score": score,
        "grade": grade,
        "vulnerabilities_found": counts["Critical"] + counts["High"] + counts["Medium"] + counts["Low"],
        "severity_counts": counts,
        "findings": findings,
        "header_checks": header_checks,
        "attack_surface": {
            "crawled_pages": crawled_pages,
            "discovered_apis": discovered_apis,
            "forms": discovered_forms,
            "scripts_analyzed": scripts_analyzed,
            "spa_rendered": spa_info.get("rendered", False),
            "framework_detected": spa_info.get("framework_detected") or "Standard Web / HTML",
        },
        "scan_meta": {
            "duration_sec": duration_sec,
            "profile": scan_profile,
            "pages_scanned": len(crawled_pages),
            "timestamp": datetime.now().isoformat(),
        },
        "report": report_md,
    }


# =========================================================================
# 2. PROJECT API COLLECTION SECURITY AUDITOR
# =========================================================================

def scan_project_api_collection(
    project_id: str,
    collection_id: Optional[str] = None,
    base_url_override: str = "",
    auth_config: Optional[Dict[str, Any]] = None,
    standard: str = "OWASP API Security Top 10 (2023)",
    use_ai: bool = False,
) -> Dict[str, Any]:
    """
    Audits saved API endpoints from the project's API Collections for:
    - Broken Authentication / Unauthenticated access
    - Missing API Security Headers (nosniff,Cache-Control, CORS wildcard)
    - Verbose Stack Traces / SQL error leakage
    - Sensitive PII/credential keys exposed in JSON response payloads
    - Unsafe HTTP methods / cleartext transport
    """
    t0 = time.time()
    from api_collections_manager import get_api_collection_by_id, get_project_all_endpoints

    endpoints: List[Dict[str, Any]] = []
    target_label = f"Project APIs ({project_id})"
    col_base_url = (base_url_override or "").strip().rstrip("/")

    if collection_id and collection_id != "ALL":
        ok, col = get_api_collection_by_id(collection_id)
        if not ok or not isinstance(col, dict):
            raise ValueError(f"ไม่พบ API Collection ที่เลือก: {col}")
        endpoints = col.get("endpoints") or []
        target_label = f"API Collection: {col.get('name')}"
        if not col_base_url:
            col_base_url = str(col.get("base_url") or "").strip().rstrip("/")
    else:
        ok, eps = get_project_all_endpoints(project_id)
        if not ok:
            raise ValueError(f"ไม่สามารถดึงรายการ API ของโครงการได้: {eps}")
        endpoints = eps or []

    if not endpoints:
        raise ValueError("ไม่พบรายการ API Endpoint ในชุดข้อมูลที่เลือก กรุณาเพิ่ม API ในเมนู API Collection ก่อน")

    session, extra_headers = _build_auth_session(auth_config)
    findings: List[Dict[str, Any]] = []
    probed_endpoints: List[Dict[str, Any]] = []

    def add_finding(severity, category, owasp, cwe, title, description, remediation, target, evidence=""):
        findings.append(
            {
                "id": f"API-SEC-{len(findings) + 1:03d}",
                "severity": severity,
                "category": category,
                "owasp": owasp,
                "cwe": cwe,
                "title": title,
                "target": target,
                "description": description,
                "evidence": evidence,
                "remediation": remediation,
                "code_snippet": "",
            }
        )

    sensitive_json_keys = {"password", "passwd", "pwd", "secret", "private_key", "credit_card", "cvv", "ssn", "api_key"}

    for ep in endpoints[:30]:
        method = str(ep.get("method") or "GET").upper()
        raw_path = str(ep.get("url") or ep.get("path") or "").strip()
        if not raw_path:
            continue

        if re.match(r"^https?://", raw_path, re.I):
            full_url = raw_path
        elif col_base_url:
            full_url = f"{col_base_url}/{raw_path.lstrip('/')}"
        else:
            # Static specification check when no base_url is configured
            probed_endpoints.append(
                {
                    "method": method,
                    "url": raw_path,
                    "status_code": 0,
                    "latency_ms": 0,
                    "note": "Static Spec Audit (ไม่ได้ระบุ Base URL)",
                }
            )
            if any(k in raw_path.lower() for k in ("password", "token", "secret", "apikey", "api_key")):
                add_finding(
                    severity="Medium",
                    category="API Design & Sensitive Data in URL",
                    owasp="API3:2023 Broken Object Property Level Authorization",
                    cwe="CWE-598",
                    title=f"พารามิเตอร์ที่มีความอ่อนไหวปรากฏใน Path/URL ของ `{method} {raw_path}`",
                    description="การส่ง Token, API Key หรือรหัสผ่านทาง URL Query String ทำให้ข้อมูลถูกบันทึกใน Access Logs และ Proxy Logs",
                    remediation="ย้ายการส่งข้อมูลลับไปไว้ใน HTTP Authorization Header หรือ Request Body (POST)",
                    target=f"{method} {raw_path}",
                    evidence=raw_path,
                )
            continue

        if _is_blocked_metadata_target(full_url):
            continue

        # Live probe of the API endpoint (safe read or configured payload)
        t_ep = time.time()
        try:
            ep_headers = dict(extra_headers)
            if isinstance(ep.get("headers"), dict):
                for hk, hv in ep["headers"].items():
                    if hk and str(hk).lower() not in ("host", "content-length"):
                        ep_headers[str(hk)] = str(hv)

            body_payload = ep.get("body") if method in ("POST", "PUT", "PATCH") else None
            res = session.request(
                method=method,
                url=full_url,
                headers=ep_headers,
                data=body_payload.encode("utf-8") if isinstance(body_payload, str) and body_payload else None,
                timeout=7,
                verify=False,
            )
            lat_ms = int((time.time() - t_ep) * 1000)
            probed_endpoints.append(
                {
                    "method": method,
                    "url": full_url,
                    "status_code": res.status_code,
                    "latency_ms": lat_ms,
                    "content_type": res.headers.get("Content-Type", ""),
                }
            )

            # Check 1: Server 500 / Stack trace disclosure
            body_txt = res.text or ""
            if res.status_code >= 500 or any(
                sig in body_txt for sig in ("Traceback (most recent call last)", "SyntaxError:", "psycopg2.errors", "SQLSTATE[", "at Object.<anonymous>")
            ):
                add_finding(
                    severity="Medium",
                    category="API Error & Stack Trace Leakage",
                    owasp="API8:2023 Security Misconfiguration",
                    cwe="CWE-209",
                    title=f"Endpoint `{method} {raw_path}` เปิดเผยรายละเอียดข้อผิดพลาดภายใน (HTTP {res.status_code})",
                    description="API ตอบกลับสถานะ 5xx หรือแสดง Stack Trace / Database Error ซึ่งช่วยให้ผู้โจมตีทราบโครงสร้างฐานข้อมูลและไลบรารีที่ใช้",
                    remediation="ดักจับ Exception ที่ฝั่ง Backend และส่งกลับเฉพาะข้อความแจ้งเตือนมาตรฐาน (Generic Error Response) โดยเก็บ Stack Trace ไว้ใน Server Log เท่านั้น",
                    target=f"{method} {full_url}",
                    evidence=body_txt[:220],
                )

            # Check 2: Sensitive fields in JSON response
            if "json" in (res.headers.get("Content-Type") or "").lower():
                try:
                    j_data = res.json()
                    raw_j_str = json.dumps(j_data).lower()
                    leaked_fields = [k for k in sensitive_json_keys if f'"{k}"' in raw_j_str]
                    if leaked_fields:
                        add_finding(
                            severity="High",
                            category="Excessive Data Exposure",
                            owasp="API3:2023 Broken Object Property Level Authorization",
                            cwe="CWE-213",
                            title=f"API `{method} {raw_path}` ส่งฟิลด์ข้อมูลความลับกลับมาใน JSON Response ({', '.join(leaked_fields)})",
                            description="ตรวจพบคีย์ที่เกี่ยวข้องกับรหัสผ่านหรือกุญแจความลับถูกส่งกลับมาใน JSON Payload ของ API",
                            remediation="ใช้ DTO / Response Serializer เพื่อคัดกรองฟิลด์ความลับออกก่อนส่ง JSON กลับไปยัง Client",
                            target=f"{method} {full_url}",
                            evidence=f"Exposed JSON keys: {', '.join(leaked_fields)}",
                        )
                except Exception:
                    pass

            # Check 3: Missing X-Content-Type-Options on API response
            if (res.headers.get("X-Content-Type-Options") or "").lower() != "nosniff":
                add_finding(
                    severity="Low",
                    category="API Security Headers",
                    owasp="API8:2023 Security Misconfiguration",
                    cwe="CWE-16",
                    title=f"API `{method} {raw_path}` ไม่ได้กำหนด `X-Content-Type-Options: nosniff`",
                    description="การตอบกลับของ API ไม่มี Header ป้องกันการตีความ MIME Type ผิดพลาด",
                    remediation="กำหนด `X-Content-Type-Options: nosniff` ใน Middleware ของ API ทุกเส้นทาง",
                    target=f"{method} {full_url}",
                    evidence="Missing X-Content-Type-Options: nosniff",
                )
        except Exception as ep_err:
            probed_endpoints.append(
                {
                    "method": method,
                    "url": full_url,
                    "status_code": 0,
                    "latency_ms": int((time.time() - t_ep) * 1000),
                    "error": str(ep_err)[:140],
                }
            )

    findings.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "Info"), 99))
    score, grade, counts = _compute_score_and_grade(findings, standard)
    duration_sec = round(time.time() - t0, 2)

    report_md = _format_findings_to_markdown(
        target_label=target_label,
        scan_mode_label="API Collection Security Audit",
        standard=standard,
        score=score,
        grade=grade,
        counts=counts,
        findings=findings,
    )

    return {
        "success": True,
        "scan_mode": "api_collection",
        "target": target_label,
        "standard": standard,
        "security_score": score,
        "grade": grade,
        "vulnerabilities_found": counts["Critical"] + counts["High"] + counts["Medium"] + counts["Low"],
        "severity_counts": counts,
        "findings": findings,
        "header_checks": [],
        "attack_surface": {
            "crawled_pages": probed_endpoints,
            "discovered_apis": [f"{e.get('method')} {e.get('url')}" for e in probed_endpoints],
            "forms": [],
            "scripts_analyzed": [],
            "spa_rendered": False,
            "framework_detected": "REST / HTTP API Collection",
        },
        "scan_meta": {
            "duration_sec": duration_sec,
            "profile": "api_audit",
            "pages_scanned": len(probed_endpoints),
            "timestamp": datetime.now().isoformat(),
        },
        "report": report_md,
    }


# =========================================================================
# 3. SOURCE CODE, UPLOADED FILES & GITHUB REPOSITORY SCANNER (SAST + AI)
# =========================================================================

SAST_RULES = [
    {
        "title": "ความเสี่ยง SQL Injection จากการต่อสตริงในคำสั่ง SQL โดยตรง",
        "severity": "Critical",
        "category": "SQL Injection (SQLi)",
        "owasp": "A03:2021 Injection",
        "cwe": "CWE-89",
        "pattern": r"""(?i)(?:execute|query|raw|cursor\.execute)\s*\(\s*(?:f['"]|['"][^'"]*(?:SELECT|INSERT|UPDATE|DELETE)[^'"]*['"]\s*(?:\+|%|\.format\())""",
        "description": "พบการสร้างคำสั่ง SQL ด้วยการต่อสตริง (`+`, `%`, `.format()`, หรือ `f-string`) โดยนำตัวแปรไปแทรกใน Query โดยตรง ทำให้ผู้โจมตีสามารถแทรกคำสั่ง SQL เพื่อดึงหรือแก้ไขฐานข้อมูลได้",
        "remediation": "เปลี่ยนไปใช้ Parameterized Queries / Prepared Statements เสมอ เช่น `cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))`",
    },
    {
        "title": "ความเสี่ยง OS Command Injection จากการรันคำสั่งระบบด้วย shell=True หรือ os.system",
        "severity": "Critical",
        "category": "Command Injection",
        "owasp": "A03:2021 Injection",
        "cwe": "CWE-78",
        "pattern": r"""(?i)(?:os\.system|os\.popen|child_process\.exec)\s*\(|subprocess\.(?:Popen|run|call|check_output)\s*\([^)]*shell\s*=\s*True""",
        "description": "การเรียกใช้คำสั่ง Shell (`os.system`, `child_process.exec`, หรือ `subprocess` พร้อม `shell=True`) เสี่ยงต่อการถูกแทรกคำสั่งระบบ (`; rm -rf`, `&& whoami`) หากมีข้อมูลจากผู้ใช้ปะปน",
        "remediation": "ใช้ `subprocess.run(['cmd', 'arg1'], shell=False)` โดยส่งอาร์กิวเมนต์เป็น List และตรวจสอบค่า Input ด้วย Whitelist",
    },
    {
        "title": "การใช้ฟังก์ชันประมวลผลโค้ดแบบไดนามิก (eval / exec / Function)",
        "severity": "High",
        "category": "Code Injection",
        "owasp": "A03:2021 Injection",
        "cwe": "CWE-95",
        "pattern": r"""\b(?:eval|exec)\s*\(|new\s+Function\s*\(""",
        "description": "การใช้ `eval()` หรือ `exec()` เปิดช่องให้รันโค้ดใดๆ ก็ได้ (Remote Code Execution / DOM XSS) หากข้อมูลที่ส่งเข้าไปสามารถถูกควบคุมโดยผู้ใช้งาน",
        "remediation": "หลีกเลี่ยงการใช้ `eval()`/`exec()` โดยสิ้นเชิง หากต้องการแปลงข้อมูล JSON ให้ใช้ `json.loads()` หรือ `JSON.parse()` แทน",
    },
    {
        "title": "ความเสี่ยง Cross-Site Scripting (XSS) จากการเรนเดอร์ HTML ดิบโดยไม่ผ่าน Sanitizer",
        "severity": "High",
        "category": "Cross-Site Scripting (XSS)",
        "owasp": "A03:2021 Injection",
        "cwe": "CWE-79",
        "pattern": r"""(?:\{\s*@html\s+|dangerouslySetInnerHTML|v-html\s*=|\.innerHTML\s*=|document\.write\s*\()""",
        "description": "พบการนำข้อความไปเรนเดอร์เป็น HTML ดิบ (`{@html}`, `dangerouslySetInnerHTML`, `v-html`, `innerHTML`) ซึ่งหากข้อมูลมาจากผู้ใช้หรือ AI โดยไม่ผ่านการกรอง `<script>` หรือ `onerror=` จะเกิด XSS ทันที",
        "remediation": "ใช้ DOMPurify หรือ HTML Sanitizer กรองแท็กและแอตทริบิวต์อันตรายออกก่อนเรนเดอร์ หรือใช้ Text Binding ปกติแทน",
    },
    {
        "title": "การฝังรหัสผ่านหรือ Secret Key ไว้ใน Source Code (Hardcoded Credentials)",
        "severity": "Critical",
        "category": "Hardcoded Secrets",
        "owasp": "A07:2021 Identification and Authentication Failures",
        "cwe": "CWE-798",
        "pattern": r"""(?i)\b(?:password|passwd|secret_key|api_key|jwt_secret|private_key|access_token)\s*[:=]\s*['"][A-Za-z0-9_\-\.!@#$%^&*]{8,}['"]""",
        "description": "ตรวจพบการกำหนดรหัสผ่านหรือกุญแจความลับแบบตายตัว (Hardcoded) ใน Source Code ซึ่งเสี่ยงต่อการรั่วไหลผ่าน Git Repository",
        "remediation": "ย้ายค่าความลับทั้งหมดไปอ่านจาก Environment Variables (`os.environ.get(...)` หรือ `process.env...`) หรือระบบ Secret Manager",
    },
    {
        "title": "ความเสี่ยง Insecure Deserialization (pickle / yaml.load แบบไม่ระบุ SafeLoader)",
        "severity": "Critical",
        "category": "Insecure Deserialization",
        "owasp": "A08:2021 Software and Data Integrity Failures",
        "cwe": "CWE-502",
        "pattern": r"""\bpickle\.loads?\s*\(|yaml\.load\s*\([^)]*(?!SafeLoader)""",
        "description": "การใช้ `pickle.loads()` หรือ `yaml.load()` กับข้อมูลภายนอกทำให้ผู้โจมตีสามารถสร้าง Payload เพื่อสั่งรันคำสั่งบนเซิร์ฟเวอร์ (Remote Code Execution) ได้ทันที",
        "remediation": "ใช้ `json.loads()` หรือ `yaml.safe_load()` แทนการใช้ `pickle` หรือ `yaml.load()`",
    },
    {
        "title": "การใช้อัลกอริทึมแฮชที่ล้าสมัยและไม่ปลอดภัย (MD5 / SHA1)",
        "severity": "Medium",
        "category": "Weak Cryptography",
        "owasp": "A02:2021 Cryptographic Failures",
        "cwe": "CWE-328",
        "pattern": r"""(?i)\b(?:hashlib\.md5|hashlib\.sha1|md5\s*\(|sha1\s*\(|CryptoJS\.MD5|CryptoJS\.SHA1)""",
        "description": "อัลกอริทึม MD5 และ SHA1 มีความเสี่ยงต่อการเกิด Collision และสามารถถูกถอดรหัสด้วย Rainbow Tables ได้อย่างรวดเร็ว ไม่เหมาะสำหรับเก็บรหัสผ่านหรือตรวจสอบความถูกต้องสำคัญ",
        "remediation": "ใช้ `bcrypt`, `Argon2` หรือ `PBKDF2` สำหรับรหัสผ่าน และใช้ `SHA-256` / `SHA-512` สำหรับตรวจสอบความสมบูรณ์ของข้อมูล",
    },
    {
        "title": "การปิดการตรวจสอบใบรับรอง SSL/TLS (verify=False / rejectUnauthorized: false)",
        "severity": "Medium",
        "category": "Improper Certificate Validation",
        "owasp": "A02:2021 Cryptographic Failures",
        "cwe": "CWE-295",
        "pattern": r"""(?:\bverify\s*=\s*False\b|rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['"]?0)""",
        "description": "การตั้งค่าข้ามการตรวจสอบใบรับรอง SSL (`verify=False` หรือ `rejectUnauthorized: false`) ทำให้การเชื่อมต่อเสี่ยงต่อการถูกดักฟังแบบ Man-in-the-Middle (MitM)",
        "remediation": "เปิดใช้งานการตรวจสอบใบรับรอง SSL (`verify=True`) บน Production และระบุ CA Bundle ที่ถูกต้องหากใช้ Internal CA",
    },
    {
        "title": "การเปิดโหมด Debug ทิ้งไว้ในโค้ดแอปพลิเคชัน (debug=True)",
        "severity": "Medium",
        "category": "Security Misconfiguration",
        "owasp": "A05:2021 Security Misconfiguration",
        "cwe": "CWE-489",
        "pattern": r"""\bapp\.run\s*\([^)]*debug\s*=\s*True|^\s*DEBUG\s*=\s*True\b""",
        "description": "การเปิด `debug=True` บนเซิร์ฟเวอร์จริงจะแสดงหน้า Interactive Debugger และ Stack Trace เชิงลึกเมื่อเกิดข้อผิดพลาด ซึ่งอาจนำไปสู่การรันโค้ดจากระยะไกล",
        "remediation": "ตั้งค่า `debug=False` เป็นค่าเริ่มต้น และควบคุมผ่าน Environment Variable เฉพาะในเครื่องพัฒนา",
    },
    {
        "title": "ความเสี่ยง Path Traversal จากการนำข้อมูลผู้ใช้ไปเปิดไฟล์โดยไม่กรองเส้นทาง (CWE-22)",
        "severity": "High",
        "category": "Path Traversal",
        "owasp": "A01:2021 Broken Access Control",
        "cwe": "CWE-22",
        "pattern": r"""(?i)(?:open|send_file|os\.path\.join|Path)\s*\([^)]*(?:request\.(?:args|form|json|values)|req\.(?:query|body|params))""",
        "description": "พบการนำพารามิเตอร์จาก Request ของผู้ใช้ไปประกอบเป็น Path เพื่อเปิดหรือส่งไฟล์โดยตรง ทำให้ผู้โจมตีสามารถใช้ `../../` เพื่ออ่านไฟล์สำคัญของระบบได้",
        "remediation": "ใช้ `werkzeug.utils.secure_filename()` และตรวจสอบ `os.path.realpath(target).startswith(BASE_DIR)` ก่อนเปิดไฟล์เสมอ",
    },
    {
        "title": "ความเสี่ยง Server-Side Request Forgery (SSRF) จากการนำ URL จากผู้ใช้ไปยิง Request โดยตรง (CWE-918)",
        "severity": "High",
        "category": "Server-Side Request Forgery (SSRF)",
        "owasp": "A10:2021 Server-Side Request Forgery",
        "cwe": "CWE-918",
        "pattern": r"""(?i)(?:requests\.(?:get|post|request|put|delete)|urllib\.request\.urlopen|axios\.(?:get|post)|fetch)\s*\([^)]*(?:request\.(?:args|form|json)|req\.(?:query|body|params))""",
        "description": "การนำ URL ที่รับจากผู้ใช้ไปสั่งให้เซิร์ฟเวอร์ยิง HTTP Request ออกไปโดยตรง ทำให้ผู้โจมตีสามารถสั่งสแกนเครือข่ายภายใน (`127.0.0.1`) หรือดึง Cloud Metadata (`169.254.169.254`) ได้",
        "remediation": "ตรวจสอบ Hostname กับ Whitelist และแปลง DNS เพื่อบล็อก Private/Loopback/Link-Local IP ทั้งหมดก่อนทำการเชื่อมต่อ",
    },
    {
        "title": "ความเสี่ยง Unrestricted File Upload จากการบันทึกไฟล์อัปโหลดโดยไม่ผ่าน secure_filename (CWE-434)",
        "severity": "High",
        "category": "Unrestricted File Upload",
        "owasp": "A04:2021 Insecure Design",
        "cwe": "CWE-434",
        "pattern": r"""(?i)\.save\s*\([^)]*\.filename\b""",
        "description": "พบการบันทึกไฟล์ที่อัปโหลดโดยใช้ `.filename` ดิบจากผู้ใช้โดยตรงโดยไม่ผ่านการทำความสะอาดชื่อไฟล์และตรวจสอบนามสกุล เสี่ยงต่อการอัปโหลดสคริปต์อันตรายหรือเขียนทับไฟล์ระบบ",
        "remediation": "ตรวจสอบนามสกุลไฟล์กับ `ALLOWED_EXTENSIONS`, ใช้ `secure_filename(file.filename)` หรือตั้งชื่อไฟล์ใหม่ด้วย `uuid.uuid4()`",
    },
    {
        "title": "ความเสี่ยง Open Redirect จากการนำค่าพารามิเตอร์ไปสั่ง Redirect โดยไม่ตรวจสอบโดเมน (CWE-601)",
        "severity": "Medium",
        "category": "Open Redirect",
        "owasp": "A01:2021 Broken Access Control",
        "cwe": "CWE-601",
        "pattern": r"""(?i)\b(?:redirect|res\.redirect)\s*\([^)]*(?:request\.(?:args|form|values)|req\.(?:query|body|params))""",
        "description": "การนำค่า URL จากพารามิเตอร์ของผู้ใช้ไปใส่ในฟังก์ชัน `redirect()` โดยตรง ทำให้ผู้โจมตีสร้างลิงก์หลอกส่งผู้ใช้ไปยังเว็บปลอม (Phishing) ได้",
        "remediation": "ตรวจสอบว่า URL ปลายทางเป็น Relative Path ภายในระบบ (`urlparse(target).netloc == ''`) ก่อนทำการ Redirect",
    },
]


def scan_source_code_sast(
    source_code: str,
    language: str = "auto",
    standard: str = "OWASP Top 10 (2021)",
    target_label: str = "Source Code Snippet",
    use_ai: bool = True,
) -> Dict[str, Any]:
    """
    Runs deterministic line-by-line SAST rules + secret detection on source code,
    and optionally enriches with Gemini AI Security Architect review.
    """
    t0 = time.time()
    if not source_code or not source_code.strip():
        raise ValueError("กรุณาระบุ Source Code หรืออัปโหลดไฟล์ที่ต้องการตรวจสอบ")

    findings: List[Dict[str, Any]] = []
    lines = source_code.splitlines()
    current_file = target_label

    for line_no, line in enumerate(lines, 1):
        file_marker = re.match(r"^---\s*FILE:\s*(.+?)\s*---$", line.strip())
        if file_marker:
            current_file = file_marker.group(1).strip()
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "/*", "*")):
            continue

        for rule in SAST_RULES:
            if re.search(rule["pattern"], line):
                start_l = max(0, line_no - 2)
                end_l = min(len(lines), line_no + 1)
                snippet = "\n".join(f"{i + 1}: {lines[i]}" for i in range(start_l, end_l))
                findings.append(
                    {
                        "id": f"SAST-{len(findings) + 1:03d}",
                        "severity": rule["severity"],
                        "category": rule["category"],
                        "owasp": rule["owasp"],
                        "cwe": rule["cwe"],
                        "title": rule["title"],
                        "target": f"{current_file} (บรรทัดที่ {line_no})",
                        "description": rule["description"],
                        "evidence": stripped[:220],
                        "remediation": rule["remediation"],
                        "code_snippet": snippet,
                    }
                )

        for sec_name, pattern, cwe_id, sev in SECRET_PATTERNS:
            m = re.search(pattern, line)
            if m:
                matched_val = m.group(0)
                masked = matched_val[:8] + "..." + matched_val[-4:] if len(matched_val) > 14 else matched_val
                findings.append(
                    {
                        "id": f"SAST-{len(findings) + 1:03d}",
                        "severity": sev,
                        "category": "Hardcoded Secret",
                        "owasp": "A02:2021 Cryptographic Failures",
                        "cwe": cwe_id,
                        "title": f"ตรวจพบ {sec_name} ฝังอยู่ใน Source Code",
                        "target": f"{current_file} (บรรทัดที่ {line_no})",
                        "description": f"พบกุญแจความลับ ({sec_name}) อยู่ในโค้ดโดยตรง ซึ่งเสี่ยงต่อการรั่วไหลในระบบควบคุมเวอร์ชัน (Git)",
                        "evidence": masked,
                        "remediation": "ทำการเพิกถอน (Revoke) กุญแจนี้ทันที และเปลี่ยนไปใช้ Environment Variable แทน",
                        "code_snippet": f"{line_no}: {stripped[:180]}",
                    }
                )

    findings.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "Info"), 99))
    score, grade, counts = _compute_score_and_grade(findings, standard)

    ai_summary = None
    if use_ai:
        ai_summary = _run_optional_ai_code_review(source_code, language, standard, findings)

    duration_sec = round(time.time() - t0, 2)
    report_md = _format_findings_to_markdown(
        target_label=target_label,
        scan_mode_label=f"Source Code SAST ({language})",
        standard=standard,
        score=score,
        grade=grade,
        counts=counts,
        findings=findings,
        ai_summary=ai_summary,
    )

    return {
        "success": True,
        "scan_mode": "source_code",
        "target": target_label,
        "standard": standard,
        "security_score": score,
        "grade": grade,
        "vulnerabilities_found": counts["Critical"] + counts["High"] + counts["Medium"] + counts["Low"],
        "severity_counts": counts,
        "findings": findings,
        "header_checks": [],
        "attack_surface": {
            "crawled_pages": [],
            "discovered_apis": [],
            "forms": [],
            "scripts_analyzed": [target_label],
            "spa_rendered": False,
            "framework_detected": f"Source Code ({len(lines)} lines)",
        },
        "scan_meta": {
            "duration_sec": duration_sec,
            "profile": "sast_hybrid" if use_ai else "sast_deterministic",
            "pages_scanned": 1,
            "lines_scanned": len(lines),
            "timestamp": datetime.now().isoformat(),
        },
        "report": report_md,
    }


def _run_optional_ai_web_summary(
    target_url: str,
    standard: str,
    score: int,
    grade: str,
    findings: List[Dict[str, Any]],
    header_checks: List[Dict[str, Any]],
) -> Optional[str]:
    """Calls Gemini if available to synthesize executive security advice; fails silently if credits are depleted."""
    try:
        from ocr_engine import get_all_api_keys, _get_gemini_client
        from google.genai import types

        keys = get_all_api_keys()
        if not keys:
            return None
        client = _get_gemini_client(0)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        brief_findings = [
            f"- [{f.get('severity')}] {f.get('title')} ({f.get('owasp')})" for f in findings[:12]
        ]
        prompt = (
            f"คุณคือ Application Security Architect สรุปคำแนะนำเชิงกลยุทธ์สั้นๆ (ไม่เกิน 8 บรรทัด) เป็นภาษาไทย "
            f"สำหรับผลการสแกนเว็บไซต์ {target_url} ตามมาตรฐาน {standard} (Score: {score}/100, Grade {grade}):\n"
            + ("\n".join(brief_findings) if brief_findings else "- ไม่พบช่องโหว่ความเสี่ยงสูง")
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.15),
        )
        return resp.text if resp and resp.text else None
    except Exception as e:
        logger.info(f"Optional AI web summary skipped: {e}")
        return None


def _run_optional_ai_code_review(
    source_code: str,
    language: str,
    standard: str,
    existing_findings: List[Dict[str, Any]],
) -> Optional[str]:
    """Calls Gemini if available to provide deeper logic/contextual code security review; never breaks the scan on 402/429."""
    try:
        from ocr_engine import get_all_api_keys, _get_gemini_client
        from google.genai import types

        keys = get_all_api_keys()
        if not keys:
            return None
        client = _get_gemini_client(0)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        prompt = (
            f"วิเคราะห์ช่องโหว่เชิงตรรกะ (Business Logic / Auth / Injection) เพิ่มเติมสำหรับโค้ดภาษา {language} "
            f"ตามเกณฑ์ {standard} เป็นภาษาไทยแบบกระชับ พร้อมตัวอย่างโค้ดที่แก้ไขแล้ว:\n\n"
            f"```\n{source_code[:18000]}\n```"
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.15),
        )
        return resp.text if resp and resp.text else None
    except Exception as e:
        logger.info(f"Optional AI code review skipped: {e}")
        return None


# =========================================================================
# 4. MULTI-SHEET EXECUTIVE EXCEL (.XLSX) REPORT GENERATOR
# =========================================================================

def compute_report_verdict(score: int, counts: Dict[str, int]) -> Dict[str, str]:
    """Determines the executive post-scan report status verdict."""
    crit = int(counts.get("Critical", 0))
    high = int(counts.get("High", 0))
    med = int(counts.get("Medium", 0))
    low = int(counts.get("Low", 0))

    if crit > 0:
        return {
            "code": "FAIL_CRITICAL",
            "status_label": "ไม่ผ่านเกณฑ์ความปลอดภัย (CRITICAL ACTION REQUIRED)",
            "badge_text": "CRITICAL RISK",
            "tone": "critical",
            "summary": f"ตรวจพบช่องโหว่ระดับวิกฤต (Critical) {crit} รายการ และระดับสูง (High) {high} รายการ ต้องดำเนินการแก้ไขก่อนนำขึ้น Production",
        }
    if high > 0:
        return {
            "code": "FAIL_HIGH",
            "status_label": "ไม่ผ่านเกณฑ์มาตรฐาน — พบช่องโหว่ความเสี่ยงสูง (HIGH RISK)",
            "badge_text": "HIGH RISK",
            "tone": "high",
            "summary": f"ตรวจพบช่องโหว่ระดับสูง (High) {high} รายการ และระดับปานกลาง (Medium) {med} รายการ แนะนำให้แก้ไขตามแนวทาง Remediation",
        }
    if med > 0:
        return {
            "code": "WARN_MEDIUM",
            "status_label": "ผ่านแบบมีเงื่อนไข — พบความเสี่ยงระดับปานกลาง (CONDITIONAL PASS)",
            "badge_text": "WARNING",
            "tone": "warning",
            "summary": f"ไม่พบช่องโหว่ระดับวิกฤตหรือสูง แต่พบความเสี่ยงระดับปานกลาง {med} รายการ และระดับต่ำ {low} รายการที่ควรปรับปรุง",
        }
    return {
        "code": "PASS",
        "status_label": "ผ่านเกณฑ์ความปลอดภัยมาตรฐาน (SECURITY VERIFIED PASS)",
        "badge_text": "PASSED",
        "tone": "pass",
        "summary": (
            f"คะแนนความปลอดภัย {score}/100 ไม่พบช่องโหว่ระดับ Critical, High หรือ Medium "
            + (f"(พบข้อเสนอแนะระดับต่ำ {low} รายการ)" if low > 0 else "ระบบมีการป้องกันตามเกณฑ์มาตรฐานครบถ้วน")
        ),
    }


def generate_security_excel_bytes(scan_data: Dict[str, Any]) -> bytes:
    """
    Generates a 4-sheet professional Excel (.xlsx) Security Assessment Report:
      Sheet 1: สรุปผลการตรวจ (Executive Summary)
      Sheet 2: รายการช่องโหว่ (Vulnerability Findings)
      Sheet 3: Security Headers & TLS
      Sheet 4: Attack Surface & Assets
    """
    import io
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    target = str(scan_data.get("target") or scan_data.get("target_label") or "Target Application")
    scan_mode = str(scan_data.get("scan_mode") or "web_url")
    standard = str(scan_data.get("standard") or "OWASP Top 10 (2021)")
    score = int(scan_data.get("security_score") if scan_data.get("security_score") is not None else 100)
    grade = str(scan_data.get("grade") or "A")
    counts = scan_data.get("severity_counts") if isinstance(scan_data.get("severity_counts"), dict) else {}
    findings = scan_data.get("findings") if isinstance(scan_data.get("findings"), list) else []
    header_checks = scan_data.get("header_checks") if isinstance(scan_data.get("header_checks"), list) else []
    attack_surface = scan_data.get("attack_surface") if isinstance(scan_data.get("attack_surface"), dict) else {}
    scan_meta = scan_data.get("scan_meta") if isinstance(scan_data.get("scan_meta"), dict) else {}

    verdict = compute_report_verdict(score, counts)

    # Color Palette
    dark_header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
    sub_header_fill = PatternFill(start_color="312E81", end_color="312E81", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    sev_fills = {
        "Critical": PatternFill(start_color="FFE4E6", end_color="FFE4E6", fill_type="solid"),
        "High": PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid"),
        "Medium": PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
        "Low": PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid"),
        "Info": PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid"),
    }
    sev_fonts = {
        "Critical": Font(name="Tahoma", size=10, bold=True, color="BE123C"),
        "High": Font(name="Tahoma", size=10, bold=True, color="C2410C"),
        "Medium": Font(name="Tahoma", size=10, bold=True, color="B45309"),
        "Low": Font(name="Tahoma", size=10, bold=True, color="0369A1"),
        "Info": Font(name="Tahoma", size=10, bold=True, color="475569"),
    }

    title_font = Font(name="Tahoma", size=14, bold=True, color="FFFFFF")
    th_font = Font(name="Tahoma", size=10, bold=True, color="FFFFFF")
    label_font = Font(name="Tahoma", size=10, bold=True, color="1E293B")
    body_font = Font(name="Tahoma", size=10, color="0F172A")

    thin_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # -----------------------------------------------------------------
    # SHEET 1: สรุปผลการตรวจ (Executive Summary)
    # -----------------------------------------------------------------
    ws1 = wb.active
    ws1.title = "Executive Summary"
    ws1.views.sheetView[0].showGridLines = True

    ws1.merge_cells("A1:D1")
    ws1["A1"] = "SPECTRA QA — รายงานผลการตรวจสอบความปลอดภัย (SECURITY ASSESSMENT REPORT)"
    ws1["A1"].font = title_font
    ws1["A1"].fill = dark_header_fill
    ws1["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[1].height = 34

    verdict_fill = (
        sev_fills["Critical"]
        if verdict["tone"] == "critical"
        else sev_fills["High"]
        if verdict["tone"] == "high"
        else sev_fills["Medium"]
        if verdict["tone"] == "warning"
        else PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    )
    verdict_font = (
        sev_fonts["Critical"]
        if verdict["tone"] == "critical"
        else sev_fonts["High"]
        if verdict["tone"] == "high"
        else sev_fonts["Medium"]
        if verdict["tone"] == "warning"
        else Font(name="Tahoma", size=11, bold=True, color="065F46")
    )

    ws1.merge_cells("A3:D3")
    ws1["A3"] = f"สถานะรายงาน (Report Status): {verdict['status_label']}"
    ws1["A3"].font = verdict_font
    ws1["A3"].fill = verdict_fill
    ws1["A3"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[3].height = 26

    ws1.merge_cells("A4:D4")
    ws1["A4"] = verdict["summary"]
    ws1["A4"].font = body_font
    ws1["A4"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[4].height = 22

    meta_rows = [
        ("เป้าหมายการตรวจสอบ (Target)", target, "คะแนนความปลอดภัย (Security Score)", f"{score} / 100 (Grade {grade})"),
        ("โหมดการตรวจสอบ (Scan Mode)", scan_mode.upper(), "มาตรฐานอ้างอิง (Standard)", standard),
        (
            "สถาปัตยกรรมที่ตรวจพบ (Architecture)",
            str(attack_surface.get("framework_detected") or "Web / Application"),
            "จำนวนหน้า/Endpoint ที่ตรวจ",
            str(scan_meta.get("pages_scanned") or len(attack_surface.get("crawled_pages") or []) or 1),
        ),
        (
            "เวลาที่ใช้ตรวจสอบ (Duration)",
            f"{scan_meta.get('duration_sec', 0)} วินาที",
            "วันที่และเวลาที่ตรวจสอบ",
            str(scan_meta.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ),
    ]

    row_idx = 6
    for l1, v1, l2, v2 in meta_rows:
        ws1.cell(row=row_idx, column=1, value=l1).font = label_font
        ws1.cell(row=row_idx, column=1).fill = zebra_fill
        ws1.cell(row=row_idx, column=2, value=v1).font = body_font
        ws1.cell(row=row_idx, column=3, value=l2).font = label_font
        ws1.cell(row=row_idx, column=3).fill = zebra_fill
        ws1.cell(row=row_idx, column=4, value=v2).font = body_font
        for col_i in range(1, 5):
            ws1.cell(row=row_idx, column=col_i).border = cell_border
            ws1.cell(row=row_idx, column=col_i).alignment = Alignment(vertical="center", wrap_text=True)
        ws1.row_dimensions[row_idx].height = 22
        row_idx += 1

    row_idx += 1
    ws1.cell(row=row_idx, column=1, value="ระดับความรุนแรง (Severity Level)").font = th_font
    ws1.cell(row=row_idx, column=2, value="จำนวนที่พบ (Count)").font = th_font
    ws1.cell(row=row_idx, column=3, value="ผลกระทบต่อคะแนน (Weight)").font = th_font
    ws1.cell(row=row_idx, column=4, value="คำแนะนำการดำเนินการ (Action SLA)").font = th_font
    for col_i in range(1, 5):
        c = ws1.cell(row=row_idx, column=col_i)
        c.fill = sub_header_fill
        c.border = cell_border
        c.alignment = Alignment(horizontal="center" if col_i in (2, 3) else "left", vertical="center")
    ws1.row_dimensions[row_idx].height = 24

    sla_map = {
        "Critical": ("-22 คะแนน/จุด", "ต้องแก้ไขทันที (Immediate Blocker ก่อนขึ้น Production)"),
        "High": ("-12 คะแนน/จุด", "แก้ไขเร่งด่วนภายในรอบ Sprint ปัจจุบัน"),
        "Medium": ("-6 คะแนน/จุด", "วางแผนแก้ไขและเพิ่มการป้องกันเชิงลึก (Defense-in-Depth)"),
        "Low": ("-2 คะแนน/จุด", "ปรับปรุงตาม Best Practices เพื่อลดพื้นที่โจมตี"),
        "Info": ("0 คะแนน", "ข้อสังเกตเชิงสถาปัตยกรรมเพื่อรับทราบ"),
    }
    for sev_key in ("Critical", "High", "Medium", "Low", "Info"):
        row_idx += 1
        cnt = int(counts.get(sev_key, 0))
        w_txt, sla_txt = sla_map[sev_key]
        c1 = ws1.cell(row=row_idx, column=1, value=sev_key)
        c1.font = sev_fonts[sev_key]
        c1.fill = sev_fills[sev_key]
        c2 = ws1.cell(row=row_idx, column=2, value=cnt)
        c2.font = sev_fonts[sev_key] if cnt > 0 else body_font
        c2.alignment = Alignment(horizontal="center", vertical="center")
        c3 = ws1.cell(row=row_idx, column=3, value=w_txt)
        c3.font = body_font
        c3.alignment = Alignment(horizontal="center", vertical="center")
        c4 = ws1.cell(row=row_idx, column=4, value=sla_txt)
        c4.font = body_font
        for col_i in range(1, 5):
            ws1.cell(row=row_idx, column=col_i).border = cell_border
        ws1.row_dimensions[row_idx].height = 21

    ws1.column_dimensions["A"].width = 34
    ws1.column_dimensions["B"].width = 42
    ws1.column_dimensions["C"].width = 34
    ws1.column_dimensions["D"].width = 48

    # -----------------------------------------------------------------
    # SHEET 2: รายการช่องโหว่และวิธีแก้ไข (Vulnerability Findings)
    # -----------------------------------------------------------------
    ws2 = wb.create_sheet(title="Vulnerability Findings")
    headers2 = [
        "ลำดับ",
        "รหัส (ID)",
        "ความรุนแรง (Severity)",
        "ชื่อช่องโหว่ (Vulnerability Title)",
        "หมวดหมู่ (Category)",
        "มาตรฐาน OWASP",
        "รหัส CWE",
        "ตำแหน่งที่พบ (Target / Location)",
        "รายละเอียดความเสี่ยง (Description)",
        "หลักฐานที่พบ (Evidence / Snippet)",
        "แนวทางแก้ไข (Remediation)",
    ]
    ws2.append(headers2)
    ws2.row_dimensions[1].height = 26
    for col_i in range(1, len(headers2) + 1):
        cell = ws2.cell(row=1, column=col_i)
        cell.font = th_font
        cell.fill = dark_header_fill
        cell.border = cell_border
        cell.alignment = Alignment(horizontal="center" if col_i <= 3 else "left", vertical="center", wrap_text=True)

    if not findings:
        ws2.append([1, "-", "PASS", "ไม่พบช่องโหว่ความเสี่ยงสูงในขอบเขตที่ตรวจสอบ", "-", standard, "-", target, "ผ่านเกณฑ์มาตรฐาน", "-", "-"])
    else:
        for idx, f in enumerate(findings, 1):
            sev = str(f.get("severity") or "Info")
            ev_text = str(f.get("evidence") or "")
            if f.get("code_snippet"):
                ev_text = (ev_text + "\n" + str(f.get("code_snippet"))).strip()
            row_vals = [
                idx,
                str(f.get("id") or f"SEC-{idx:03d}"),
                sev,
                str(f.get("title") or ""),
                str(f.get("category") or ""),
                str(f.get("owasp") or ""),
                str(f.get("cwe") or ""),
                str(f.get("target") or target),
                str(f.get("description") or ""),
                ev_text,
                str(f.get("remediation") or ""),
            ]
            ws2.append(row_vals)
            r_num = idx + 1
            ws2.row_dimensions[r_num].height = 42
            row_bg = zebra_fill if idx % 2 == 0 else white_fill
            for col_i in range(1, len(headers2) + 1):
                c = ws2.cell(row=r_num, column=col_i)
                c.border = cell_border
                if col_i == 3:
                    c.fill = sev_fills.get(sev, white_fill)
                    c.font = sev_fonts.get(sev, body_font)
                    c.alignment = Alignment(horizontal="center", vertical="top")
                else:
                    c.fill = row_bg
                    c.font = label_font if col_i == 4 else body_font
                    c.alignment = Alignment(
                        horizontal="center" if col_i in (1, 2, 7) else "left",
                        vertical="top",
                        wrap_text=True,
                    )

    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(headers2))}{max(2, len(findings) + 1)}"
    col_widths2 = [8, 13, 16, 38, 24, 28, 12, 36, 46, 42, 48]
    for i, w in enumerate(col_widths2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # -----------------------------------------------------------------
    # SHEET 3: Security Headers & TLS Matrix
    # -----------------------------------------------------------------
    ws3 = wb.create_sheet(title="Security Headers & TLS")
    headers3 = ["ลำดับ", "รายการตรวจสอบ (Header / Check)", "สถานะ (Status)", "ค่าที่ตรวจพบ (Detected Value)", "คำแนะนำ (Recommendation)"]
    ws3.append(headers3)
    ws3.row_dimensions[1].height = 25
    for col_i in range(1, len(headers3) + 1):
        c = ws3.cell(row=1, column=col_i)
        c.font = th_font
        c.fill = dark_header_fill
        c.border = cell_border
        c.alignment = Alignment(horizontal="center" if col_i in (1, 3) else "left", vertical="center")

    for idx, hc in enumerate(header_checks, 1):
        st = str(hc.get("status") or "info").upper()
        ws3.append([idx, str(hc.get("header") or ""), st, str(hc.get("value") or ""), str(hc.get("recommendation") or "")])
        r_num = idx + 1
        ws3.row_dimensions[r_num].height = 24
        for col_i in range(1, 6):
            c = ws3.cell(row=r_num, column=col_i)
            c.border = cell_border
            c.font = body_font
            c.alignment = Alignment(horizontal="center" if col_i in (1, 3) else "left", vertical="center", wrap_text=True)
            if col_i == 3:
                if st == "PASS":
                    c.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
                    c.font = Font(name="Tahoma", size=10, bold=True, color="065F46")
                elif st == "WARN":
                    c.fill = sev_fills["Medium"]
                    c.font = sev_fonts["Medium"]
                else:
                    c.fill = sev_fills["Critical"]
                    c.font = sev_fonts["Critical"]

    ws3.freeze_panes = "A2"
    for i, w in enumerate([8, 34, 15, 48, 52], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    # -----------------------------------------------------------------
    # SHEET 4: Attack Surface & Crawled Assets
    # -----------------------------------------------------------------
    ws4 = wb.create_sheet(title="Attack Surface & Assets")
    headers4 = ["ลำดับ", "ประเภท (Type)", "HTTP Method", "URL / Endpoint", "HTTP Status", "Latency (ms)", "Content-Type / หมายเหตุ"]
    ws4.append(headers4)
    ws4.row_dimensions[1].height = 25
    for col_i in range(1, len(headers4) + 1):
        c = ws4.cell(row=1, column=col_i)
        c.font = th_font
        c.fill = dark_header_fill
        c.border = cell_border

    asset_idx = 0
    for pg in attack_surface.get("crawled_pages") or []:
        asset_idx += 1
        ws4.append([
            asset_idx,
            "Crawled Page / Endpoint",
            str(pg.get("method") or "GET"),
            str(pg.get("url") or ""),
            pg.get("status_code") or "-",
            pg.get("latency_ms") or 0,
            str(pg.get("content_type") or pg.get("note") or pg.get("error") or ""),
        ])
    for api_str in attack_surface.get("discovered_apis") or []:
        asset_idx += 1
        parts = str(api_str).split(" ", 1)
        m_str = parts[0] if len(parts) == 2 else "GET"
        u_str = parts[1] if len(parts) == 2 else str(api_str)
        ws4.append([asset_idx, "Discovered API Route", m_str, u_str, "-", "-", "Extracted from DOM / JS Bundle"])

    for r_num in range(2, asset_idx + 2):
        ws4.row_dimensions[r_num].height = 21
        for col_i in range(1, 8):
            c = ws4.cell(row=r_num, column=col_i)
            c.border = cell_border
            c.font = body_font
            c.alignment = Alignment(horizontal="center" if col_i in (1, 3, 5, 6) else "left", vertical="center")

    ws4.freeze_panes = "A2"
    for i, w in enumerate([8, 24, 14, 54, 14, 15, 36], 1):
        ws4.column_dimensions[get_column_letter(i)].width = w

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()


