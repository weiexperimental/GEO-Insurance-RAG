#!/bin/bash
set -e

echo "╔═══════════════════════════════════════════════════╗"
echo "║  GEO Insurance RAG — One-Time Setup               ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ─── Check prerequisites ─────────────────────────────────────────────────────
echo "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
  echo "❌ Docker not found. Install Docker Desktop: https://docker.com/products/docker-desktop"
  exit 1
fi
echo "  ✅ Docker"

if ! command -v python3 &>/dev/null; then
  echo "❌ Python not found. Install Python 3.12: brew install python@3.12"
  exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ "$PY_VERSION" != "3.12" ]]; then
  echo "⚠️  Python $PY_VERSION detected. Python 3.12 required (MinerU compatibility)."
  echo "   Install: brew install python@3.12"
fi
echo "  ✅ Python $PY_VERSION"

PY_ARCH=$(python3 -c "import platform; print(platform.machine())")
if [[ "$PY_ARCH" != "arm64" ]]; then
  echo "⚠️  Python architecture: $PY_ARCH. ARM64 recommended for Apple Silicon (MLX GPU)."
fi
echo "  ✅ Architecture: $PY_ARCH"

if ! command -v uv &>/dev/null; then
  echo "  Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "  ✅ uv"

# ─── Create .env ─────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "📝 Created .env from template."
  echo "   ⚠️  EDIT .env NOW and fill in your YIBU API keys:"
  echo "   - LLM_API_KEY"
  echo "   - EMBEDDING_API_KEY"
  echo "   - VISION_API_KEY"
  echo ""
  echo "   Then run: ./start.sh"
  exit 0
else
  echo "  ✅ .env exists"
fi

# ─── Validate .env ───────────────────────────────────────────────────────────
echo ""
echo "Validating .env..."
source .env

MISSING=0
for KEY in LLM_API_KEY EMBEDDING_API_KEY VISION_API_KEY; do
  VAL=$(eval echo "\$$KEY")
  if [ -z "$VAL" ] || [ "$VAL" = "sk-xxx" ]; then
    echo "  ❌ $KEY not set (still default)"
    MISSING=1
  else
    echo "  ✅ $KEY"
  fi
done

if [ $MISSING -eq 1 ]; then
  echo ""
  echo "⚠️  Please edit .env with real API keys, then run ./start.sh"
  exit 1
fi

# ─── Create data directories ─────────────────────────────────────────────────
mkdir -p data/inbox data/processed data/failed logs
echo "  ✅ Data directories"

# ─── Install Python venv ─────────────────────────────────────────────────────
if [ ! -d .venv ]; then
  echo ""
  echo "Creating Python virtual environment..."
  uv venv --python 3.12 .venv
  source .venv/bin/activate
  uv pip install "raganything[all]>=1.2.9" "mineru[mlx]>=2.7.6" fastmcp watchdog opensearch-py python-dotenv
  echo "  ✅ Python venv"
else
  echo "  ✅ Python venv exists"
fi

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  Setup complete! Run ./start.sh to start.        ║"
echo "╚═══════════════════════════════════════════════════╝"
