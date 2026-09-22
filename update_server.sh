#!/usr/bin/env bash
# ==============================================================================
# Spectra QA Consult - Linux Server Update Script
# ==============================================================================
set -e

echo "=========================================================="
echo "🚀 Updating Spectra QA System on Linux Server..."
echo "=========================================================="

# 1. Pull latest code from git repository
echo "📥 [1/4] Pulling latest changes from git..."
git pull origin main

# 2. Check if docker and docker compose are available
if ! command -v docker &> /dev/null; then
    echo "❌ Error: docker is not installed or not in PATH."
    exit 1
fi

# 3. Rebuild and restart Frontend and Backend containers
echo "🔨 [2/4] Rebuilding and restarting containers (Frontend & Backend)..."
docker compose up -d --build frontend backend

# Optional: If MCP server also needs restart
if docker ps -a --format '{{.Names}}' | grep -q "spectra_mcp_server"; then
    echo "🔄 Restarting MCP server container..."
    docker compose restart mcp_server
fi

# 4. Check Container Health
echo "🔍 [3/4] Checking container status..."
docker compose ps

# 5. Verify Database connectivity and schema
echo "🗄️ [4/4] Verifying Database schema (documents, ocr_history, api_usage_logs, billing_credit)..."
if docker ps --format '{{.Names}}' | grep -q "qa_agent_db"; then
    # Ensure ocr_history table exists
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS ocr_history (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          filename VARCHAR(255),
          result_json JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );" || true

    # Ensure api_usage_logs table and all modern columns exist
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS api_usage_logs (
          log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          endpoint_name VARCHAR(100),
          model_name VARCHAR(100),
          filename VARCHAR(255),
          prompt_tokens INT DEFAULT 0,
          completion_tokens INT DEFAULT 0,
          total_tokens INT DEFAULT 0,
          estimated_cost_usd DECIMAL(10, 6) DEFAULT 0,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS endpoint_name VARCHAR(100);
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS filename VARCHAR(255);
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS prompt_tokens INT DEFAULT 0;
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS completion_tokens INT DEFAULT 0;
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS total_tokens INT DEFAULT 0;
      ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS estimated_cost_usd DECIMAL(10, 6) DEFAULT 0;
      " || true

    # Ensure billing_credit table and all modern columns exist
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS billing_credit (
          id SERIAL PRIMARY KEY,
          total_credit_thb DECIMAL(12, 2) DEFAULT 0.00,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS total_credit_thb DECIMAL(12, 2) DEFAULT 0.00;
      ALTER TABLE billing_credit ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
      " || true

    # Ensure qa_transactions table and columns exist
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS qa_transactions (
          transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
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
      ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
      " || true

    # Ensure qa_groups table exists
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS qa_groups (
          group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
          group_name VARCHAR(255) NOT NULL,
          group_type VARCHAR(100) NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(project_id, group_name)
      );
      ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
      ALTER TABLE qa_groups ADD COLUMN IF NOT EXISTS group_type VARCHAR(100);
      " || true

    # Ensure qa_generated_documents table exists
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS qa_generated_documents (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
          doc_name VARCHAR(255),
          doc_type VARCHAR(255),
          skill_id VARCHAR(500),
          status VARCHAR(50) DEFAULT 'Generating',
          file_url VARCHAR(255),
          pdf_url VARCHAR(255),
          markdown_content TEXT,
          is_saved_to_project BOOLEAN DEFAULT FALSE,
          saved_doc_id UUID,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );
      ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS markdown_content TEXT;
      ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(255);
      ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS is_saved_to_project BOOLEAN DEFAULT FALSE;
      ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS saved_doc_id UUID;
      ALTER TABLE qa_generated_documents ALTER COLUMN skill_id TYPE VARCHAR(500);
      " || true

    # Verify doc_category column
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'doc_category';" || true
fi

echo "=========================================================="
echo "✅ Update completed successfully!"
echo "🌐 Frontend: http://<SERVER_IP>:5173"
echo "⚙️ Backend : http://<SERVER_IP>:8125"
echo "=========================================================="
