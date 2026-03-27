# src/rag.py
import os
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from raganything import RAGAnything, RAGAnythingConfig

from src.config import ModelConfig, OpenSearchConfig


async def _llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    keyword_extraction: bool = False,
    **kwargs,
) -> str:
    """LLM function — config injected via kwargs at call time."""
    model = kwargs.pop("model", "gpt-4o-mini")
    api_key = kwargs.pop("api_key", "")
    base_url = kwargs.pop("base_url", "")
    return await openai_complete_if_cache(
        model=model,
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    )


async def _embed_func(texts: list[str], **kwargs) -> list[list[float]]:
    """Embedding function."""
    model = kwargs.pop("model", "text-embedding-3-large")
    api_key = kwargs.pop("api_key", "")
    base_url = kwargs.pop("base_url", "")
    return await openai_embed(
        texts=texts,
        model=model,
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    )


class RAGEngine:
    def __init__(
        self,
        llm_config: ModelConfig,
        embedding_config: ModelConfig,
        vision_config: ModelConfig,
        opensearch_config: OpenSearchConfig,
        working_dir: str,
    ):
        self._llm_cfg = llm_config
        self._embed_cfg = embedding_config
        self._vision_cfg = vision_config
        self._os_cfg = opensearch_config
        self._working_dir = working_dir
        self._lightrag: LightRAG | None = None
        self._rag: RAGAnything | None = None

    async def initialize(self) -> None:
        # Configure OpenSearch env vars BEFORE LightRAG init
        os.environ["OPENSEARCH_HOSTS"] = f"{self._os_cfg.host}:{self._os_cfg.port}"
        os.environ["OPENSEARCH_USE_SSL"] = "false"
        os.environ["OPENSEARCH_VERIFY_CERTS"] = "false"

        async def llm_func(prompt, system_prompt=None, history_messages=None, keyword_extraction=False, **kw):
            return await _llm_func(
                prompt, system_prompt, history_messages, keyword_extraction,
                model=self._llm_cfg.model,
                api_key=self._llm_cfg.api_key,
                base_url=self._llm_cfg.api_base,
                **kw,
            )

        async def embed_func(texts, **kw):
            return await _embed_func(
                texts,
                model=self._embed_cfg.model,
                api_key=self._embed_cfg.api_key,
                base_url=self._embed_cfg.api_base,
                **kw,
            )

        async def vision_func(prompt, system_prompt=None, history_messages=None, **kw):
            image_data = kw.pop("image_data", None)
            if image_data:
                # RAG-Anything passes base64 image via image_data kwarg.
                # Convert to OpenAI vision format: messages with content array.
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=self._vision_cfg.api_key,
                    base_url=self._vision_cfg.api_base,
                )
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                })
                response = await client.chat.completions.create(
                    model=self._vision_cfg.model,
                    messages=messages,
                )
                return response.choices[0].message.content
            else:
                return await _llm_func(
                    prompt, system_prompt, history_messages,
                    model=self._vision_cfg.model,
                    api_key=self._vision_cfg.api_key,
                    base_url=self._vision_cfg.api_base,
                    **kw,
                )

        self._lightrag = LightRAG(
            working_dir=self._working_dir,
            llm_model_func=llm_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=3072,
                max_token_size=8192,
                func=embed_func,
            ),
            kv_storage="OpenSearchKVStorage",
            vector_storage="OpenSearchVectorDBStorage",
            graph_storage="OpenSearchGraphStorage",
            doc_status_storage="OpenSearchDocStatusStorage",
        )
        await self._lightrag.initialize_storages()

        # Reset stale pipeline_status busy flag (can be stuck after crash)
        try:
            from lightrag.kg.shared_storage import get_namespace_data, get_pipeline_status_lock
            lock = get_pipeline_status_lock(workspace="")
            async with lock:
                ps = await get_namespace_data("pipeline_status", workspace="")
                if ps.get("busy", False):
                    ps["busy"] = False
                    ps["request_pending"] = False
        except Exception:
            pass  # pipeline_status may not be initialized yet

        self._rag = RAGAnything(
            lightrag=self._lightrag,
            llm_model_func=llm_func,
            vision_model_func=vision_func,
            embedding_func=self._lightrag.embedding_func,
            config=RAGAnythingConfig(
                working_dir=self._working_dir,
                enable_image_processing=True,
                enable_table_processing=True,
                enable_equation_processing=True,
            ),
        )

    @property
    def doc_status(self):
        """Expose LightRAG's doc_status storage for direct access."""
        return self._lightrag.doc_status

    async def query(self, question: str, mode: str = "hybrid", top_k: int = 5) -> str:
        return await self._rag.aquery(question, mode=mode, top_k=top_k)

    async def ingest_document(self, file_path: str, output_dir: str, device: str = "mps", lang: str = "ch", doc_id: str | None = None) -> None:
        if self._rag is None:
            raise RuntimeError("RAGEngine not initialized — call initialize() first")
        kwargs = dict(
            file_path=file_path,
            output_dir=output_dir,
            parse_method="auto",
            device=device,
            lang=lang,
        )
        if doc_id:
            kwargs["doc_id"] = doc_id
        await self._rag.process_document_complete(**kwargs)

    async def delete_document(self, document_id: str) -> bool:
        try:
            await self._lightrag.adelete_by_doc_id(document_id)
            return True
        except Exception:
            return False
