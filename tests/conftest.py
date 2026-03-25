import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


class _FakeQueryParam:
    """Lightweight stand-in for lightrag.QueryParam used in tests."""

    def __init__(self, mode="hybrid", top_k=60, chunk_top_k=None,
                 enable_rerank=False, include_references=False,
                 only_need_prompt=False, **kwargs):
        self.mode = mode
        self.top_k = top_k
        self.chunk_top_k = chunk_top_k
        self.enable_rerank = enable_rerank
        self.include_references = include_references
        self.only_need_prompt = only_need_prompt
        for k, v in kwargs.items():
            setattr(self, k, v)


# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock lightrag and its submodules so they can be imported without installation
_lightrag_mock = MagicMock()
_lightrag_mock.QueryParam = _FakeQueryParam
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
