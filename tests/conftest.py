import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock lightrag and its submodules so they can be imported without installation
_lightrag_mock = MagicMock()
_lightrag_llm_mock = MagicMock()
_lightrag_llm_openai_mock = MagicMock()
_lightrag_llm_openai_mock.openai_complete_if_cache = AsyncMock()

sys.modules.setdefault("lightrag", _lightrag_mock)
sys.modules.setdefault("lightrag.llm", _lightrag_llm_mock)
sys.modules.setdefault("lightrag.llm.openai", _lightrag_llm_openai_mock)
sys.modules.setdefault("lightrag.utils", MagicMock())

# Mock raganything and its submodules
sys.modules.setdefault("raganything", MagicMock())

# Mock opensearchpy so server.py can import without installation
_opensearchpy_mock = MagicMock()
sys.modules.setdefault("opensearchpy", _opensearchpy_mock)
