#!/bin/bash
set -e

echo "╔═══════════════════════════════════════════════════╗"
echo "║  GEO Insurance RAG — Starting All Services        ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ─── Validate .env ───────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "❌ .env not found. Run ./setup.sh first."
  exit 1
fi

# ─── Start Docker services ───────────────────────────────────────────────────
echo "Starting Docker services..."
docker compose -f docker/docker-compose.yml up -d --build

echo ""
echo "Waiting for OpenSearch..."
until curl -sf http://localhost:9200/_cluster/health &>/dev/null; do
  sleep 2
  printf "."
done
echo " ✅ OpenSearch ready"

echo "Waiting for Admin Backend..."
until curl -sf http://localhost:8080/api/system/health &>/dev/null; do
  sleep 2
  printf "."
done
echo " ✅ Admin Backend ready"

# ─── Start MCP Server (local — needs Metal GPU) ─────────────────────────────
echo ""
echo "Starting MCP Server..."

# Kill any existing MCP server
pkill -f "python src/server.py" 2>/dev/null || true
sleep 1

source .venv/bin/activate
PYTHONPATH=. nohup python src/server.py > logs/mcp-server.log 2>&1 &
MCP_PID=$!
echo "  ✅ MCP Server started (PID: $MCP_PID)"

# ─── Print access URLs ──────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  All services running!                            ║"
echo "╠═══════════════════════════════════════════════════╣"
echo "║                                                   ║"
echo "║  Admin Dashboard:  http://localhost               ║"
echo "║  OpenSearch:        http://localhost:9200          ║"
echo "║  OS Dashboards:     http://localhost:5601          ║"
echo "║                                                   ║"

# Show Tailscale IP if available
if command -v tailscale &>/dev/null; then
  TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
  if [ -n "$TS_IP" ]; then
    echo "║  Tailscale Access:  http://$TS_IP            ║"
  fi
fi

echo "║                                                   ║"
echo "║  MCP Server: running (logs/mcp-server.log)       ║"
echo "║                                                   ║"
echo "║  Stop: ./stop.sh                                  ║"
echo "╚═══════════════════════════════════════════════════╝"
