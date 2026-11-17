# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary users:** QA engineers and software teams automating test design, API/security/performance testing, and Thai/English document OCR QA across one or more software projects.
- **Roles:** Standard `user` accounts (scoped to assigned menus and projects) and `admin` accounts (managing projects, API collections, skills, members, and exit criteria).

## Product Purpose

Spectra QA is a unified AI-powered QA automation and document-verification platform. It exists to help QA engineers and engineering teams turn requirements, live API traffic, and documents into structured test artifacts, automated checks, and verified Thai/English copy from a single workspace. Success means faster, more consistent test coverage, fewer manual handoffs between requirements, API sniffing, execution, and sign-off, and accurate bilingual (Thai/English) document proofreading.

## Positioning

Unlike standalone OCR tools or single-purpose test runners, Spectra QA combines multi-agent QA orchestration (workflow builder, master agent, QA consult, analysis diagrams, and test automation), API/performance/security testing, a Chrome Extension network sniffer (`Spectra QA - Network & API Sniffer`), MCP server integration for external AI clients, and ZhipuAI-powered Thai/English OCR spell-checking in one project-scoped workspace.

## Operating Context

- **Web workspace (`svelte-app/`):** Served via Vite/Svelte during development (`http://localhost:5173`) proxied to a Flask backend (`http://localhost:5000`), used during daily QA planning, execution, document review, and reporting.
- **Browser capture (`chrome-extension/`):** Manifest V3 Chrome Extension ("Spectra QA - Network & API Sniffer") capturing real-time network traffic and APIs and syncing them into Spectra QA.
- **AI & MCP integrations (`backend/mcp_server.py`, `mcp-proxy/`):** Model Context Protocol server and proxy allowing external AI tools (e.g., Cursor, Claude Desktop) to invoke OCR and QA capabilities.
- **Project-scoped artifacts:** Work is organized by project (`projects`, `qa_database.db`), session groups, exit criteria, knowledge bases, custom Thai dictionary (`data/thai_custom_words.txt`), and reusable skills.

## Capabilities and Constraints

- **Core modules:** QA Consult, QA Document Creation, Test Automation, Performance, Security, Research, Analysis Diagram, Workflow Builder, Master Agent UI, Exit Criteria Manager, Knowledge Base, Skill Manager, API Collection Admin & Usage Dashboard, and Thai/EN Document OCR & Spell Check (`UploadPanel`, `ResultsPanel`, `FormatRules`, `DictStats`).
- **Bilingual requirement:** Must support both Thai and English UI copy, document OCR, and context-aware spell-checking.
- **Role & project scoping:** Menu visibility and project access are enforced by role (`authAllowedMenus`, `authAllowedProjects`).
- **Technical & deployment constraints:** Local/on-prem friendly stack (Svelte 5 + Vite frontend, Flask + SQLite backend, Poppler for PDF rendering, ZhipuAI GLM-OCR / GLM-4-Flash and local model support, SSRF protection and 50MB file limit on OCR URL/file ingestion).

## Brand Commitments

- **Product name:** Spectra QA (preserved across the web app and Chrome Extension).
- **Existing visual assets:** Favicon `/spectra-favicon.svg` and Chrome Extension icons (`chrome-extension/icon16.png`, `icon48.png`, `icon128.png`).
- **Language commitment:** Bilingual Thai + English support must be preserved.

## Evidence on Hand

- `svelte-app/index.html` and `svelte-app/src/` — active Svelte 5 web application with `Spectra QA` branding and full QA + OCR modules.
- `chrome-extension/manifest.json` — Manifest V3 extension ("Spectra QA - Network & API Sniffer").
- `backend/` and `README.md` — Flask API, MCP server, SQLite persistence (`qa_database.db`), and Thai OCR spell-check pipeline.
- `data/thai_custom_words.txt` — custom Thai domain dictionary.
- No external customer testimonials, public pricing, or third-party benchmarks are confirmed; future UI work must not fabricate them.

## Product Principles

1. **Project-scoped clarity:** Keep workflows, history, exit criteria, and permissions anchored to the active project and user role.
2. **Evidence-backed QA:** Ground test generation, API collections, and OCR corrections in inspectable inputs (requirements, captured traffic, custom dictionaries, and execution logs).
3. **Bilingual precision:** Treat Thai and English copy, OCR layout parsing, and domain terminology as first-class citizens.
4. **Composable automation:** Support both visual in-app workflows and external agent/browser integrations (Chrome Extension, MCP) without duplicating setup.

