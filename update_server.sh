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
echo "🗄️ [4/4] Verifying Database schema (documents.doc_category & ocr_history)..."
if docker ps --format '{{.Names}}' | grep -q "qa_agent_db"; then
    # Ensure ocr_history table exists
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "CREATE TABLE IF NOT EXISTS ocr_history (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          filename VARCHAR(255),
          result_json JSONB,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );" || true
    # Verify doc_category column
    docker exec -i qa_agent_db psql -U qa_admin -d qa_agent_db -c \
      "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'doc_category';" || true
fi

echo "=========================================================="
echo "✅ Update completed successfully!"
echo "🌐 Frontend: http://<SERVER_IP>:5173"
echo "⚙️ Backend : http://<SERVER_IP>:8125"
echo "=========================================================="
