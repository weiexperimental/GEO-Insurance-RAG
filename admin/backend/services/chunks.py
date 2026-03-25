import time

from opensearchpy import OpenSearch, NotFoundError

NOISE_TYPES = {"footer", "header", "aside_text", "UNKNOWN"}

CHUNK_INDEX = "text_chunks"


class ChunkService:
    def __init__(self, os_client: OpenSearch, embedding_func=None):
        self._os = os_client
        self._embedding_func = embedding_func

    # ------------------------------------------------------------------
    # Quality assessment
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        ascii_words = len(text.split())
        return cjk_chars + ascii_words

    def _assess_quality(self, chunk: dict) -> tuple[str, list[str]]:
        """Return (tier, reasons) where tier is 'good', 'warning', or 'bad'.

        Bad takes precedence over warning.
        """
        content = chunk.get("content", "") or ""
        tokens = chunk.get("tokens", 0) or 0
        original_type = chunk.get("original_type", "") or ""

        bad_reasons: list[str] = []
        warning_reasons: list[str] = []

        # Bad: noise type
        if original_type in NOISE_TYPES:
            bad_reasons.append(original_type)

        # Bad: empty content
        if not content.strip():
            bad_reasons.append("empty")

        # Bad: too short (tokens < 10)
        if tokens < 10:
            bad_reasons.append("too short (< 10 tokens)")

        # Warning: short (10 <= tokens < 50)
        elif tokens < 50:
            warning_reasons.append("short (< 50 tokens)")

        # Warning: too long (tokens > 2000)
        if tokens > 2000:
            warning_reasons.append("too long (> 2000 tokens)")

        # Warning: malformed table
        if "<table>" in content and "</table>" not in content:
            warning_reasons.append("malformed table")

        if bad_reasons:
            return "bad", bad_reasons
        if warning_reasons:
            return "warning", warning_reasons
        return "good", []

    # ------------------------------------------------------------------
    # List / get
    # ------------------------------------------------------------------

    def list_chunks(
        self,
        doc_id: str | None,
        type_filter: str | None,
        quality_filter: str | None,
        search: str | None,
        page: int,
        size: int,
    ) -> dict:
        """Return paginated chunk list with quality assessment.

        When quality_filter is set: fetch ALL matching chunks, filter in
        Python, paginate manually so total count is accurate.
        When quality_filter is NOT set: use OpenSearch pagination.
        """
        must_clauses: list[dict] = []

        if doc_id:
            must_clauses.append({"term": {"full_doc_id.keyword": doc_id}})

        if type_filter:
            must_clauses.append({"term": {"original_type.keyword": type_filter}})

        if search:
            must_clauses.append({"match": {"content": search}})

        bool_query: dict = {}
        if must_clauses:
            bool_query["must"] = must_clauses

        query = {"bool": bool_query} if bool_query else {"match_all": {}}

        sort = [{"chunk_order_index": {"order": "asc"}}]

        if quality_filter:
            # Fetch all, filter in Python, paginate manually
            body = {
                "query": query,
                "sort": sort,
                "size": 10000,
            }
            resp = self._os.search(index=CHUNK_INDEX, body=body)
            all_hits = resp["hits"]["hits"]

            filtered = []
            for h in all_hits:
                tier, reasons = self._assess_quality(h["_source"])
                if tier == quality_filter:
                    filtered.append(_format_chunk(h, tier, reasons))

            total = len(filtered)
            start = (page - 1) * size
            end = start + size
            chunks = filtered[start:end]
        else:
            # Normal OpenSearch pagination
            from_offset = (page - 1) * size
            body = {
                "query": query,
                "sort": sort,
                "from": from_offset,
                "size": size,
            }
            resp = self._os.search(index=CHUNK_INDEX, body=body)
            total = resp["hits"]["total"]["value"]
            chunks = []
            for h in resp["hits"]["hits"]:
                tier, reasons = self._assess_quality(h["_source"])
                chunks.append(_format_chunk(h, tier, reasons))

        return {
            "chunks": chunks,
            "total": total,
            "page": page,
            "size": size,
        }

    def get_chunk(self, chunk_id: str) -> dict | None:
        """Return a single chunk with quality assessment, or None if not found."""
        try:
            resp = self._os.get(index=CHUNK_INDEX, id=chunk_id)
        except NotFoundError:
            return None

        tier, reasons = self._assess_quality(resp["_source"])
        return _format_chunk(resp, tier, reasons)

    # ------------------------------------------------------------------
    # Update / delete
    # ------------------------------------------------------------------

    async def update_chunk(self, chunk_id: str, new_content: str) -> dict:
        """Update chunk content (and optionally re-embed) in text_chunks index."""
        tokens = self._estimate_tokens(new_content)
        doc = {"content": new_content, "tokens": tokens}
        self._os.update(index=CHUNK_INDEX, id=chunk_id, body={"doc": doc})

        if self._embedding_func is not None:
            vectors = await self._embedding_func([new_content])
            self._os.update(
                index=CHUNK_INDEX,
                id=chunk_id,
                body={"doc": {"content_vector": vectors[0]}},
            )

        return {"id": chunk_id, "content": new_content, "tokens": tokens}

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete chunk from both text_chunks and chunks indices.

        Returns True if deleted from at least one index, False if not found in either.
        """
        deleted = False
        for index in (CHUNK_INDEX, "chunks"):
            try:
                self._os.delete(index=index, id=chunk_id)
                deleted = True
            except NotFoundError:
                pass
        return deleted

    def batch_delete(self, chunk_ids: list[str]) -> dict:
        """Delete multiple chunks. Returns counts of deleted and total."""
        deleted = 0
        for chunk_id in chunk_ids:
            if self.delete_chunk(chunk_id):
                deleted += 1
        return {"deleted": deleted, "total": len(chunk_ids)}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_quality_stats(self, doc_id: str | None = None) -> dict:
        """Return counts per quality tier across all chunks (or filtered by doc_id)."""
        must_clauses: list[dict] = []
        if doc_id:
            must_clauses.append({"term": {"full_doc_id.keyword": doc_id}})

        bool_query: dict = {}
        if must_clauses:
            bool_query["must"] = must_clauses

        query = {"bool": bool_query} if bool_query else {"match_all": {}}

        body = {
            "query": query,
            "_source": ["tokens", "original_type", "content"],
            "size": 10000,
        }
        resp = self._os.search(index=CHUNK_INDEX, body=body)
        hits = resp["hits"]["hits"]

        counts: dict[str, int] = {"good": 0, "warning": 0, "bad": 0}
        for h in hits:
            tier, _ = self._assess_quality(h["_source"])
            counts[tier] += 1

        return {**counts, "total": len(hits)}

    def get_token_distribution(self, doc_id: str | None = None) -> dict:
        """Return histogram of token counts with interval 100."""
        must_clauses: list[dict] = []
        if doc_id:
            must_clauses.append({"term": {"full_doc_id.keyword": doc_id}})

        bool_query: dict = {}
        if must_clauses:
            bool_query["must"] = must_clauses

        query = {"bool": bool_query} if bool_query else {"match_all": {}}

        body = {
            "query": query,
            "size": 0,
            "aggs": {
                "token_histogram": {
                    "histogram": {"field": "tokens", "interval": 100}
                }
            },
        }
        resp = self._os.search(index=CHUNK_INDEX, body=body)
        raw_buckets = resp["aggregations"]["token_histogram"]["buckets"]

        buckets = [
            {"range": f"{b['key']}-{b['key'] + 99}", "count": b["doc_count"]}
            for b in raw_buckets
        ]
        return {"buckets": buckets}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_chunk(hit: dict, tier: str, reasons: list[str]) -> dict:
    return {
        "id": hit["_id"],
        **hit["_source"],
        "quality": tier,
        "quality_reasons": reasons,
    }
