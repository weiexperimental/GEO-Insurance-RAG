#!/bin/bash
echo "Stopping GEO Insurance RAG..."

# Stop MCP Server
pkill -f "python src/server.py" 2>/dev/null && echo "  ✅ MCP Server stopped" || echo "  ⚠️  MCP Server not running"

# Stop Docker services
docker compose -f docker/docker-compose.yml down
echo "  ✅ Docker services stopped"

echo ""
echo "All services stopped."
