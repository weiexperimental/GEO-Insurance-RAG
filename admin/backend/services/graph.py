from opensearchpy import OpenSearch

NOISE_TYPES = {"footer", "header", "aside_text", "content", "data", "UNKNOWN"}

NODE_INDEX = "chunk_entity_relation-nodes"
EDGE_INDEX = "chunk_entity_relation-edges"
ENTITY_INDEX = "entities"


# ---------------------------------------------------------------------------
# Module-level helpers for entity resolution
# ---------------------------------------------------------------------------

def _jaccard_tokens(a: str, b: str) -> float:
    """Token-level Jaccard similarity. Handles CJK by splitting into characters."""
    def tokenize(s: str) -> set[str]:
        tokens = set()
        for word in s.lower().split():
            tokens.add(word)
            # Also add individual CJK characters
            for ch in word:
                if '\u4e00' <= ch <= '\u9fff':
                    tokens.add(ch)
        return tokens

    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union) if union else 0.0


def _similarity_reason(source_name: str, target_name: str, name_sim: float, vector_score: float) -> str:
    """Human-readable reason for the similarity suggestion."""
    reasons = []
    if name_sim > 0.5:
        reasons.append("similar name")
    if name_sim > 0.8:
        reasons.append("very similar name")
    if vector_score > 0.9:
        reasons.append("similar description")
    if source_name.lower() in target_name.lower() or target_name.lower() in source_name.lower():
        reasons.append("substring match")
    return ", ".join(reasons) if reasons else "embedding similarity"


class GraphService:
    def __init__(self, os_client: OpenSearch, lightrag=None):
        self._os = os_client
        self._lr = lightrag

    # ------------------------------------------------------------------
    # Read methods (direct OpenSearch)
    # ------------------------------------------------------------------

    def get_graph(
        self,
        type_filter: str | None = None,
        doc_filter: str | None = None,
        max_nodes: int = 200,
    ) -> dict:
        """Return {nodes, edges} from OpenSearch graph indices."""
        must_clauses = []
        must_not_clauses = []
        filter_clauses = []

        if type_filter:
            filter_clauses.append({"terms": {"entity_type": [type_filter]}})
        else:
            must_not_clauses.append({"terms": {"entity_type": list(NOISE_TYPES)}})

        if doc_filter:
            must_clauses.append({"match": {"file_path": doc_filter}})

        bool_query: dict = {}
        if must_clauses:
            bool_query["must"] = must_clauses
        if must_not_clauses:
            bool_query["must_not"] = must_not_clauses
        if filter_clauses:
            bool_query["filter"] = filter_clauses

        node_body = {
            "query": {"bool": bool_query} if bool_query else {"match_all": {}},
            "size": max_nodes,
        }

        node_resp = self._os.search(index=NODE_INDEX, body=node_body)
        node_hits = node_resp["hits"]["hits"]
        nodes = [
            {
                "id": h["_id"],
                "entity_type": h["_source"].get("entity_type", ""),
                "description": h["_source"].get("description", ""),
                "file_path": h["_source"].get("file_path", ""),
                "source_ids": h["_source"].get("source_ids", []),
            }
            for h in node_hits
        ]
        node_ids = {n["id"] for n in nodes}

        if not node_ids:
            return {"nodes": nodes, "edges": []}

        edge_body = {
            "query": {
                "bool": {
                    "should": [
                        {"terms": {"source_node_id": list(node_ids)}},
                        {"terms": {"target_node_id": list(node_ids)}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "size": 10000,
        }
        edge_resp = self._os.search(index=EDGE_INDEX, body=edge_body)
        all_edges = edge_resp["hits"]["hits"]

        edges = []
        for h in all_edges:
            src = h["_source"].get("source_node_id", "")
            tgt = h["_source"].get("target_node_id", "")
            if src in node_ids and tgt in node_ids:
                edges.append(
                    {
                        "id": h["_id"],
                        "source": src,
                        "target": tgt,
                        "weight": h["_source"].get("weight", 1.0),
                        "description": h["_source"].get("description", ""),
                        "keywords": h["_source"].get("keywords", ""),
                        "file_path": h["_source"].get("file_path", ""),
                        "source_ids": h["_source"].get("source_ids", []),
                    }
                )

        return {"nodes": nodes, "edges": edges}

    def search_entities(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text fuzzy search on entity _id field."""
        body = {
            "query": {
                "fuzzy": {
                    "_id": {
                        "value": query,
                        "fuzziness": "AUTO",
                    }
                }
            },
            "size": limit,
        }
        resp = self._os.search(index=NODE_INDEX, body=body)
        return [
            {
                "id": h["_id"],
                "entity_type": h["_source"].get("entity_type", ""),
                "description": h["_source"].get("description", ""),
            }
            for h in resp["hits"]["hits"]
        ]

    def get_popular_entities(self, limit: int = 20) -> list[dict]:
        """Return entities excluding noise types, sorted by _id asc."""
        body = {
            "query": {
                "bool": {
                    "must_not": [
                        {"terms": {"entity_type": list(NOISE_TYPES)}}
                    ]
                }
            },
            "sort": [{"_id": {"order": "asc"}}],
            "size": limit,
        }
        resp = self._os.search(index=NODE_INDEX, body=body)
        return [
            {
                "id": h["_id"],
                "entity_type": h["_source"].get("entity_type", ""),
            }
            for h in resp["hits"]["hits"]
        ]

    def get_entity_detail(self, entity_id: str) -> dict:
        """Return entity node plus its connected edges."""
        try:
            node_resp = self._os.get(index=NODE_INDEX, id=entity_id)
        except Exception:
            return {"entity": None, "connections": []}

        entity = {
            "id": node_resp["_id"],
            **node_resp["_source"],
        }

        edge_body = {
            "query": {
                "bool": {
                    "should": [
                        {"term": {"source_node_id": entity_id}},
                        {"term": {"target_node_id": entity_id}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "size": 1000,
        }
        edge_resp = self._os.search(index=EDGE_INDEX, body=edge_body)

        connections = []
        for h in edge_resp["hits"]["hits"]:
            src = h["_source"].get("source_node_id", "")
            tgt = h["_source"].get("target_node_id", "")
            direction = "outgoing" if src == entity_id else "incoming"
            other_entity = tgt if src == entity_id else src
            connections.append(
                {
                    "id": h["_id"],
                    "direction": direction,
                    "other_entity": other_entity,
                    "weight": h["_source"].get("weight", 1.0),
                    "description": h["_source"].get("description", ""),
                    "keywords": h["_source"].get("keywords", ""),
                }
            )

        return {"entity": entity, "connections": connections}

    def find_similar_entities(self, entity_id: str, limit: int = 10) -> list[dict]:
        """Find similar entities using OpenSearch KNN vector search.

        entity_id can be either an OpenSearch _id (e.g. 'ent-xxx') or an entity name
        (e.g. '立橋人壽'). Falls back to name search if direct get fails.
        """
        # 1. Get the source entity's vector — try by _id first, then by entity_name
        source = None
        try:
            source = self._os.get(index=ENTITY_INDEX, id=entity_id)
        except Exception:
            pass

        if not source:
            # Fallback: search by entity_name
            try:
                resp = self._os.search(index=ENTITY_INDEX, body={
                    "query": {"term": {"entity_name": entity_id}},
                    "size": 1,
                    "_source": ["entity_name", "content", "vector", "file_path"],
                })
                if resp["hits"]["hits"]:
                    hit = resp["hits"]["hits"][0]
                    source = {"_id": hit["_id"], "_source": hit["_source"]}
            except Exception:
                pass

        if not source:
            return []

        source_vector = source["_source"].get("vector")
        if not source_vector:
            return []

        source_name = source["_source"].get("entity_name", "")
        source_doc_id = source["_id"]

        # 2. KNN search for nearest neighbors (fetch extra to filter self)
        body = {
            "size": limit + 1,
            "query": {
                "knn": {
                    "vector": {
                        "vector": source_vector,
                        "k": limit + 1,
                    }
                }
            },
            "_source": ["entity_name", "content", "file_path"],
        }

        try:
            resp = self._os.search(index=ENTITY_INDEX, body=body)
        except Exception:
            return []

        results = []
        for hit in resp["hits"]["hits"]:
            if hit["_id"] == source_doc_id:
                continue  # skip self

            src = hit["_source"]
            target_name = src.get("entity_name", "")

            # Compute string similarity as additional signal
            name_sim = _jaccard_tokens(source_name, target_name)

            # KNN score is the vector similarity
            vector_score = hit.get("_score", 0)

            results.append({
                "entity_id": hit["_id"],
                "entity_name": target_name,
                "description": (src.get("content") or "")[:200],
                "file_path": src.get("file_path", ""),
                "vector_similarity": round(float(vector_score), 4),
                "name_similarity": round(name_sim, 4),
                "reason": _similarity_reason(source_name, target_name, name_sim, vector_score),
            })

        return results[:limit]

    def get_edge_detail(self, source_id: str, target_id: str) -> dict | None:
        """Return the edge between two nodes, or None if not found."""
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"source_node_id": source_id}},
                        {"term": {"target_node_id": target_id}},
                    ]
                }
            },
            "size": 1,
        }
        resp = self._os.search(index=EDGE_INDEX, body=body)
        hits = resp["hits"]["hits"]
        if not hits:
            return None
        h = hits[0]
        return {"id": h["_id"], **h["_source"]}

    # ------------------------------------------------------------------
    # Write methods (LightRAG library, async)
    # ------------------------------------------------------------------

    def _check_lr(self):
        if not self._lr:
            return {"error": "LightRAG not initialized"}
        return None

    async def edit_entity(self, entity_name: str, updates: dict) -> dict:
        err = self._check_lr()
        if err:
            return err
        return await self._lr.edit_entity(entity_name, updates)

    async def delete_entity(self, entity_name: str) -> dict:
        err = self._check_lr()
        if err:
            return err
        return await self._lr.delete_by_entity(entity_name)

    async def merge_entities(self, source_entities: list[str], target_entity: str) -> dict:
        err = self._check_lr()
        if err:
            return err
        return await self._lr.merge_entities(source_entities, target_entity)

    async def edit_relation(self, source: str, target: str, updates: dict) -> dict:
        err = self._check_lr()
        if err:
            return err
        return await self._lr.edit_relation(source, target, updates)

    async def delete_relation(self, source: str, target: str) -> dict:
        err = self._check_lr()
        if err:
            return err
        return await self._lr.delete_by_relation(source, target)
