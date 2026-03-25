from opensearchpy import OpenSearch


class OpenSearchService:
    def __init__(self, client: OpenSearch):
        self._client = client

    def get_cluster_health(self) -> dict:
        return self._client.cluster.health()

    def get_node_stats(self) -> dict:
        return self._client.nodes.stats(metric="jvm,fs,os")

    def get_index_stats(self) -> list[dict]:
        return self._client.cat.indices(
            format="json",
            h="index,health,docs.count,docs.deleted,store.size,pri.store.size",
        )

    def get_doc_count(self, index: str) -> int:
        return self._client.count(index=index)["count"]

    def get_knn_stats(self) -> dict:
        return self._client.transport.perform_request("GET", "/_plugins/_knn/stats")

    @staticmethod
    def _translate(hit: dict) -> dict:
        src = hit["_source"]
        meta = src.get("metadata") or {}
        file_path = src.get("file_path", "")
        file_name = meta.get("file_name", "") or (file_path.rsplit("/", 1)[-1] if file_path else hit["_id"])
        return {
            "document_id": hit["_id"],
            "file_name": file_name,
            "file_path": file_path,
            "status": src.get("status", ""),
            "metadata": {k: v for k, v in meta.items() if k in (
                "company", "product_name", "product_type", "document_type", "document_date"
            )},
            "chunks_count": src.get("chunks_count"),
            "created_at": src.get("created_at"),
            "updated_at": src.get("updated_at"),
        }

    def get_ingestion_statuses(
        self,
        limit: int = 50,
        offset: int = 0,
        status_filter: str | None = None,
        sort_field: str = "updated_at",
        sort_order: str = "desc",
    ) -> dict:
        query: dict = {"match_all": {}}
        if status_filter:
            query = {"term": {"status": status_filter}}

        body = {
            "query": query,
            "sort": [{sort_field: {"order": sort_order}}],
            "from": offset,
            "size": limit,
        }
        resp = self._client.search(index="doc_status", body=body)
        return {
            "total": resp["hits"]["total"]["value"],
            "documents": [self._translate(h) for h in resp["hits"]["hits"]],
        }

    def get_active_ingestions(self) -> list[dict]:
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"status": ["pending", "processing"]}}
                    ]
                }
            },
            "size": 100,
        }
        resp = self._client.search(index="doc_status", body=body)
        return [self._translate(h) for h in resp["hits"]["hits"]]

    def get_ingestion_analytics(self) -> dict:
        body = {
            "size": 0,
            "aggs": {
                "status_counts": {"terms": {"field": "status", "size": 20}},
            },
        }
        resp = self._client.search(index="doc_status", body=body)
        return {
            "status_counts": {
                b["key"]: b["doc_count"]
                for b in resp["aggregations"]["status_counts"]["buckets"]
            },
        }

    def get_chunk_counts(self) -> dict[str, int]:
        try:
            body = {
                "size": 0,
                "aggs": {"by_doc": {"terms": {"field": "full_doc_id.keyword", "size": 100}}}
            }
            resp = self._client.search(index="text_chunks", body=body)
            return {b["key"]: b["doc_count"] for b in resp["aggregations"]["by_doc"]["buckets"]}
        except Exception:
            return {}

    def save_query_history(self, entry: dict) -> None:
        self._client.index(index="rag-query-history", body=entry)

    def get_query_history(self, limit: int = 50) -> list[dict]:
        try:
            resp = self._client.search(
                index="rag-query-history",
                body={"query": {"match_all": {}}, "sort": [{"timestamp": "desc"}], "size": limit},
            )
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception:
            return []

    def get_system_overview(self) -> dict:
        health = self.get_cluster_health()
        indices = self.get_index_stats()
        index_map = {i["index"]: i for i in indices}

        def count(name: str) -> str:
            return index_map.get(name, {}).get("docs.count", "0")

        def _parse_size(s: str) -> float:
            """Parse OpenSearch size string like '10.8mb', '409.5kb', '2.4gb' to bytes."""
            s = s.strip().lower()
            multipliers = {"kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "b": 1}
            for suffix, mult in multipliers.items():
                if s.endswith(suffix):
                    try:
                        return float(s[: -len(suffix)]) * mult
                    except ValueError:
                        return 0
            try:
                return float(s)
            except ValueError:
                return 0

        total_bytes = sum(
            _parse_size(i.get("pri.store.size", "0"))
            for i in indices if i.get("pri.store.size")
        ) if indices else 0
        index_size = f"{total_bytes / 1e9:.1f}GB" if total_bytes > 1e9 else f"{total_bytes / 1e6:.1f}MB"

        analytics = self.get_ingestion_analytics()
        status_counts = analytics.get("status_counts", {})

        return {
            "cluster_status": health["status"],
            "documents": count("doc_status"),
            "entities": count("chunk_entity_relation-nodes"),
            "relationships": count("chunk_entity_relation-edges"),
            "chunks": count("chunks"),
            "llm_cache": count("llm_response_cache"),
            "index_size": index_size,
            "pending": str(status_counts.get("pending", 0) + status_counts.get("processing", 0)),
            "failed": str(status_counts.get("failed", 0)),
            "total_indices": len(indices),
            "indices": indices,
        }
