import time
from lightrag import LightRAG, QueryParam


class QueryPlaygroundService:
    def __init__(self, lightrag: LightRAG):
        self._lr = lightrag

    def _make_param(self, mode: str, top_k: int, chunk_top_k: int,
                    enable_rerank: bool) -> QueryParam:
        return QueryParam(
            mode=mode,
            top_k=top_k,
            chunk_top_k=chunk_top_k,
            enable_rerank=enable_rerank,
            include_references=True,
        )

    def _normalize(self, result: dict, full_prompt: str | None,
                   timing: dict) -> dict:
        """Normalize LightRAG response into playground format."""
        llm_resp = result.get("llm_response")
        if isinstance(llm_resp, dict):
            llm_content = llm_resp.get("content")
        else:
            llm_content = llm_resp

        keywords = result.get("metadata", {}).get("keywords", {})

        return {
            "status": result.get("status"),
            "data": {
                "keywords": keywords,
                "entities": result.get("data", {}).get("entities", []),
                "relationships": result.get("data", {}).get("relationships", []),
                "chunks": result.get("data", {}).get("chunks", []),
                "references": result.get("data", {}).get("references", []),
            },
            "metadata": {
                "query_mode": result.get("metadata", {}).get("query_mode"),
                "processing_info": result.get("metadata", {}).get(
                    "processing_info", {}
                ),
            },
            "full_prompt": full_prompt,
            "llm_response": llm_content,
            "timing": timing,
        }

    async def query_full(self, query: str, mode: str, top_k: int,
                         chunk_top_k: int, enable_rerank: bool) -> dict:
        """Full query: retrieval data + LLM response + timing."""
        t0 = time.monotonic()
        param = self._make_param(mode, top_k, chunk_top_k, enable_rerank)

        prompt_param = QueryParam(
            mode=mode, top_k=top_k, chunk_top_k=chunk_top_k,
            enable_rerank=enable_rerank, include_references=True,
            only_need_prompt=True,
        )
        full_prompt = await self._lr.aquery(query, prompt_param)
        if not isinstance(full_prompt, str):
            full_prompt = str(full_prompt) if full_prompt else ""

        result = await self._lr.aquery_llm(query, param)
        total_ms = round((time.monotonic() - t0) * 1000)

        return self._normalize(result, full_prompt, {"total_ms": total_ms})

    async def retrieve_only(self, query: str, mode: str, top_k: int,
                            chunk_top_k: int, enable_rerank: bool) -> dict:
        """Retrieval only: no LLM generation."""
        param = self._make_param(mode, top_k, chunk_top_k, enable_rerank)

        t0 = time.monotonic()
        result = await self._lr.aquery_data(query, param)
        retrieval_ms = round((time.monotonic() - t0) * 1000)

        return self._normalize(result, None, {"retrieval_ms": retrieval_ms})

    async def compare(self, query: str, params_a: dict,
                      params_b: dict) -> dict:
        """Run same query with two param sets, sequential."""
        result_a = await self.query_full(query, **params_a)
        result_b = await self.query_full(query, **params_b)
        return {"result_a": result_a, "result_b": result_b}
