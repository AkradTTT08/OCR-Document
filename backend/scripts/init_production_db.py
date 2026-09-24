"""
init_production_db.py - Production Database Bootstrap Script
Initializes both qa_agent_db (with pgvector) and spectra_auth_db (with pgcrypto)
with all required tables, extensions, and default seed records safely.
"""

import os
import sys
import logging
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_production_db")

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)
load_dotenv()

def init_qa_database():
    logger.info("── Initializing qa_agent_db (PostgreSQL + pgvector) ──")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "8123")
    dbname = os.environ.get("DB_NAME", "qa_agent_db")
    user = os.environ.get("DB_USER", "qa_admin")
    password = os.environ.get("DB_PASS", "qa_password")

    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        conn.autocommit = True
        cur = conn.cursor()

        # 1. pgvector and uuid extensions
        logger.info("Enabling extensions (vector, uuid-ossp, pgcrypto)...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

        # 2. Projects table
        logger.info("Ensuring table: projects...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_code VARCHAR(50) UNIQUE,
                project_name VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'Active',
                default_base_url TEXT DEFAULT '',
                site_urls JSONB DEFAULT '[]'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS default_base_url TEXT DEFAULT '';")
        cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS site_urls JSONB DEFAULT '[]'::jsonb;")

        # 3. Documents table
        logger.info("Ensuring table: documents...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                doc_category VARCHAR(50),
                doc_type VARCHAR(50),
                original_filename VARCHAR(255) NOT NULL,
                full_markdown_content TEXT,
                is_golden_data BOOLEAN DEFAULT FALSE,
                file_hash VARCHAR(256),
                version INT DEFAULT 1,
                status VARCHAR(20) DEFAULT 'Active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Document chunks for vector RAG
        logger.info("Ensuring table: document_chunks...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
                chunk_text TEXT NOT NULL,
                embedding VECTOR(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Agent skills
        logger.info("Ensuring table: agent_skills...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_skills (
                skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                skill_name VARCHAR(100) NOT NULL,
                skill_description TEXT,
                markdown_instructions TEXT,
                target_doc_type VARCHAR(50),
                version INT DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Evaluation logs
        logger.info("Ensuring table: evaluation_logs...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_logs (
                log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE SET NULL,
                doc_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,
                raw_input TEXT,
                final_output TEXT,
                verdict VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 7. Exit Criteria Tables
        logger.info("Ensuring exit criteria tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exit_criteria_templates (
                template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                doc_type VARCHAR(50) DEFAULT 'ALL',
                is_active BOOLEAN DEFAULT TRUE,
                max_loops INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exit_criteria_items (
                item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                template_id UUID NOT NULL REFERENCES exit_criteria_templates(template_id) ON DELETE CASCADE,
                item_code VARCHAR(50) NOT NULL,
                category VARCHAR(100) NOT NULL,
                question_text TEXT NOT NULL,
                target_metric VARCHAR(100) DEFAULT '100% (ผ่านบริบูรณ์)',
                severity VARCHAR(20) DEFAULT 'Major',
                is_mandatory BOOLEAN DEFAULT TRUE,
                order_index INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS document_exit_evaluations (
                eval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID REFERENCES documents(doc_id) ON DELETE SET NULL,
                template_id UUID REFERENCES exit_criteria_templates(template_id) ON DELETE SET NULL,
                evaluated_by VARCHAR(100) DEFAULT 'AI Evaluator',
                evaluation_status VARCHAR(50) NOT NULL,
                score_percentage NUMERIC(5,2) DEFAULT 0.0,
                total_items INT DEFAULT 0,
                passed_items INT DEFAULT 0,
                failed_items INT DEFAULT 0,
                na_items INT DEFAULT 0,
                evaluation_details JSONB,
                summary_remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 8. Operational & Billing Tables
        logger.info("Ensuring operational, workflow, and billing tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS qa_transactions (
                id SERIAL PRIMARY KEY,
                transaction_id UUID DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255),
                group_type VARCHAR(100),
                filename VARCHAR(255),
                doc_type VARCHAR(255),
                extracted_text TEXT,
                qa_report TEXT,
                total_pages INTEGER,
                email VARCHAR(255),
                qa_findings JSONB,
                exit_criteria_eval JSONB,
                user_id VARCHAR(100),
                action_type VARCHAR(50),
                tokens_used INTEGER DEFAULT 0,
                cost_estimate NUMERIC(10,6) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'SUCCESS',
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS group_type VARCHAR(100);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS doc_type VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS extracted_text TEXT;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS qa_report TEXT;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS total_pages INTEGER;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS email VARCHAR(255);
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS qa_findings JSONB;
            ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS exit_criteria_eval JSONB;

            CREATE TABLE IF NOT EXISTS api_usage_logs (
                log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                endpoint_name VARCHAR(100),
                model_name VARCHAR(100),
                filename VARCHAR(255),
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd NUMERIC(12,6) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS billing_credit (
                id SERIAL PRIMARY KEY,
                total_credit_thb DECIMAL(12, 2) DEFAULT 0.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS qa_groups (
                group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255) NOT NULL,
                group_type VARCHAR(100) DEFAULT 'Project Plan',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE;
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_type VARCHAR(100) DEFAULT 'Project Plan';
            CREATE TABLE IF NOT EXISTS board_cards (
                card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'BACKLOG',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS board_integrations (
                id SERIAL PRIMARY KEY,
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                service_name VARCHAR(50) NOT NULL,
                config_json JSONB DEFAULT '{}'::jsonb,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS agent_workflows (
                workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                flow_data JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ocr_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255),
                result_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.close()
        conn.close()
        logger.info("✓ qa_agent_db initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize qa_agent_db: {e}", exc_info=True)
        raise

def init_auth_database():
    logger.info("── Initializing spectra_auth_db (PostgreSQL + pgcrypto) ──")
    host = os.environ.get("AUTH_DB_HOST", "127.0.0.1")
    port = os.environ.get("AUTH_DB_PORT", "8124")
    dbname = os.environ.get("AUTH_DB_NAME", "postgres")
    user = os.environ.get("AUTH_DB_USER", "postgres")
    password = os.environ.get("AUTH_DB_PASS", "postgres")

    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(100),
                avatar_path VARCHAR(255),
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT true,
                login_count INTEGER DEFAULT 0,
                last_login_at TIMESTAMP,
                allowed_menus TEXT,
                allowed_projects TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_menus TEXT;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_projects TEXT;
            
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                action VARCHAR(100) NOT NULL,
                details TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Ensure default admin user exists
        cur.execute("SELECT COUNT(*) FROM users WHERE username = 'admin@domain.com';")
        if cur.fetchone()[0] == 0:
            logger.info("Creating default administrator account (admin@domain.com)...")
            cur.execute("""
                INSERT INTO users (username, email, password_hash, display_name, role)
                VALUES (
                    'admin@domain.com', 
                    'admin@domain.com', 
                    crypt('password123', gen_salt('bf')), 
                    'System Administrator', 
                    'admin'
                );
            """)

        cur.close()
        conn.close()
        logger.info("✓ spectra_auth_db initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize spectra_auth_db: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    logger.info("==========================================")
    logger.info("Starting Full Production Database Bootstrap")
    logger.info("==========================================")
    init_qa_database()
    init_auth_database()
    logger.info("==========================================")
    logger.info("All Databases Bootstrap Completed Successfully!")
    logger.info("==========================================")
