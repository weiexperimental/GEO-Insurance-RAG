import json
import time
import uuid
from hashlib import md5

from opensearchpy import NotFoundError, RequestError

QA_INDEX = "eval_qa_pairs"
RUNS_INDEX = "eval_runs"

NOISE_TYPES = {"footer", "header", "aside_text", "UNKNOWN"}

CHUNK_INDEX = "text_chunks"

ALLOWED_UPDATE_FIELDS = {
    "question",
    "expected_answer",
    "source_doc",
    "category",
    "difficulty",
    "status",
}


class EvalService:
    def __init__(self, os_client, llm_func=None, lightrag=None):
        self._os = os_client
        self._llm = llm_func
        self._lr = lightrag

    def _safe_search(self, index: str, body: dict) -> dict:
        """Search that returns empty results if index doesn't exist yet."""
        try:
            return self._os.search(index=index, body=body)
        except NotFoundError:
            return {"hits": {"total": {"value": 0}, "hits": []}}

    # ------------------------------------------------------------------
    # Sync — QA pair CRUD
    # ------------------------------------------------------------------

    def list_qa_pairs(
        self,
        category: str | None,
        status: str | None,
        search: str | None,
        page: int,
        size: int,
    ) -> dict:
        must_clauses: list[dict] = []

        if category:
            must_clauses.append({"term": {"category.keyword": category}})

        if status:
            must_clauses.append({"term": {"status": status}})

        if search:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": search,
                        "fields": ["question", "expected_answer"],
                    }
                }
            )

        bool_query: dict = {}
        if must_clauses:
            bool_query["must"] = must_clauses

        query = {"bool": bool_query} if bool_query else {"match_all": {}}

        from_offset = (page - 1) * size
        body = {
            "query": query,
            "sort": [{"created_at": {"order": "desc"}}],
            "from": from_offset,
            "size": size,
        }

        resp = self._safe_search(QA_INDEX, body)
        total = resp["hits"]["total"]["value"]
        pairs = [_format_qa_pair(h) for h in resp["hits"]["hits"]]

        return {"pairs": pairs, "total": total, "page": page, "size": size}

    def create_qa_pair(
        self,
        question: str,
        expected_answer: str,
        source_doc: str,
        category: str,
        difficulty: str = "simple",
    ) -> dict:
        qa_id = f"qa-{md5(question.encode()).hexdigest()[:12]}"
        now = int(time.time())
        body = {
            "question": question,
            "expected_answer": expected_answer,
            "source_doc": source_doc,
            "category": category,
            "difficulty": difficulty,
            "status": "approved",
            "created_by": "manual",
            "created_at": now,
            "updated_at": now,
        }
        self._os.index(index=QA_INDEX, id=qa_id, body=body)
        return {"id": qa_id, **body}

    def update_qa_pair(self, qa_id: str, updates: dict) -> dict:
        doc = {k: v for k, v in updates.items() if k in ALLOWED_UPDATE_FIELDS}
        doc["updated_at"] = int(time.time())
        self._os.update(index=QA_INDEX, id=qa_id, body={"doc": doc})
        return {"id": qa_id, **doc}

    def delete_qa_pair(self, qa_id: str) -> bool:
        try:
            self._os.delete(index=QA_INDEX, id=qa_id)
            return True
        except NotFoundError:
            return False

    def batch_update_status(self, qa_ids: list[str], status: str) -> dict:
        now = int(time.time())
        updated = 0
        for qa_id in qa_ids:
            self._os.update(
                index=QA_INDEX,
                id=qa_id,
                body={"doc": {"status": status, "updated_at": now}},
            )
            updated += 1
        return {"updated": updated, "total": len(qa_ids)}

    # ------------------------------------------------------------------
    # Sync — Eval runs
    # ------------------------------------------------------------------

    def list_eval_runs(self, limit: int = 20) -> list:
        body = {
            "query": {"match_all": {}},
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": limit,
            "_source": {
                "excludes": ["results"],
            },
        }
        resp = self._safe_search(RUNS_INDEX, body)
        return [_format_run(h) for h in resp["hits"]["hits"]]

    def get_eval_run(self, run_id: str) -> dict | None:
        try:
            resp = self._os.get(index=RUNS_INDEX, id=run_id)
        except NotFoundError:
            return None
        return _format_run(resp)

    # ------------------------------------------------------------------
    # Async — LLM operations
    # ------------------------------------------------------------------

    async def generate_qa_pairs(self, doc_id: str | None, count: int) -> dict:
        if not self._llm:
            return {"error": "LLM not initialized"}

        # Fetch good-quality chunks
        must_clauses: list[dict] = [
            {
                "bool": {
                    "must_not": [
                        {"terms": {"original_type": list(NOISE_TYPES)}}
                    ]
                }
            }
        ]
        if doc_id:
            must_clauses.append({"term": {"full_doc_id.keyword": doc_id}})

        body = {
            "query": {"bool": {"must": must_clauses}},
            "size": min(count * 3, 50),
        }
        resp = self._os.search(index=CHUNK_INDEX, body=body)
        hits = resp["hits"]["hits"]

        if not hits:
            return {"generated": 0, "source_doc": doc_id}

        # Build prompt
        chunks_text = "\n\n".join(
            f"[Chunk {i+1}]\n{h['_source'].get('content', '')}"
            for i, h in enumerate(hits[:10])
        )
        source_doc = hits[0]["_source"].get("file_path", doc_id or "unknown")

        prompt = (
            f"根據以下保險文件片段，生成 {count} 個高質量問答對（QA pairs）。\n"
            f"每個 QA pair 必須係 JSON 格式，包含：question, expected_answer, difficulty (simple/medium/complex), category (product_detail/pricing/eligibility/claim/general)。\n"
            f"只返回 JSON array，唔需要其他解釋。\n\n"
            f"{chunks_text}\n\n"
            f"返回格式示例：\n"
            f'[{{"question": "...", "expected_answer": "...", "difficulty": "simple", "category": "product_detail"}}]'
        )

        raw = await self._llm(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON array from response
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start == -1 or end == 0:
                return {"generated": 0, "source_doc": source_doc, "error": "no JSON array in response"}
            qa_list = json.loads(raw[start:end])
        except (json.JSONDecodeError, ValueError):
            return {"generated": 0, "source_doc": source_doc, "error": "failed to parse LLM response"}

        now = int(time.time())
        generated = 0
        for item in qa_list[:count]:
            question = item.get("question", "").strip()
            expected_answer = item.get("expected_answer", "").strip()
            if not question or not expected_answer:
                continue

            qa_id = f"qa-{md5(question.encode()).hexdigest()[:12]}"
            self._os.index(
                index=QA_INDEX,
                id=qa_id,
                body={
                    "question": question,
                    "expected_answer": expected_answer,
                    "source_doc": source_doc,
                    "category": item.get("category", "general"),
                    "difficulty": item.get("difficulty", "simple"),
                    "status": "draft",
                    "created_by": "generated",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            generated += 1

        return {"generated": generated, "source_doc": source_doc}

    async def run_evaluation(self) -> dict:
        if not self._lr:
            return {"error": "LightRAG not initialized"}

        # Fetch all approved QA pairs
        body = {
            "query": {"term": {"status": "approved"}},
            "size": 10000,
        }
        resp = self._safe_search(QA_INDEX, body)
        pairs = [_format_qa_pair(h) for h in resp["hits"]["hits"]]

        if not pairs:
            return {"error": "no approved QA pairs found"}

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        now = int(time.time())

        # Create run record with status=running
        self._os.index(
            index=RUNS_INDEX,
            id=run_id,
            body={
                "timestamp": now,
                "total_pairs": len(pairs),
                "status": "running",
                "scores": {},
                "results": [],
            },
        )

        from lightrag import QueryParam  # type: ignore

        results = []
        score_totals = {
            "answer_correctness": 0.0,
            "faithfulness": 0.0,
            "context_relevancy": 0.0,
        }

        for pair in pairs:
            question = pair["question"]
            expected = pair["expected_answer"]
            try:
                actual = await self._lr.aquery_llm(
                    question, QueryParam(mode="hybrid")
                )
            except Exception:
                actual = ""

            scores = await self._judge_response(question, expected, actual)

            results.append(
                {
                    "qa_id": pair["id"],
                    "question": question,
                    "expected_answer": expected,
                    "actual_answer": actual,
                    "scores": scores,
                }
            )

            for k in score_totals:
                score_totals[k] += scores.get(k, 0.0)

        n = len(pairs)
        avg_scores = {k: round(v / n, 4) for k, v in score_totals.items()}

        self._os.update(
            index=RUNS_INDEX,
            id=run_id,
            body={
                "doc": {
                    "status": "completed",
                    "scores": avg_scores,
                    "results": results,
                    "completed_at": int(time.time()),
                }
            },
        )

        return {"run_id": run_id, "total_pairs": n, "scores": avg_scores}

    async def _judge_response(
        self, question: str, expected: str, actual: str
    ) -> dict:
        if not self._llm:
            return {"answer_correctness": 0.0, "faithfulness": 0.0, "context_relevancy": 0.0}

        prompt = (
            "你係一個 RAG 評估專家。請根據以下問題、預期答案同實際答案，評估以下三個指標（每個 0-1 分）：\n"
            "- answer_correctness：實際答案係咪準確回答咗問題\n"
            "- faithfulness：實際答案有冇捏造內容\n"
            "- context_relevancy：實際答案同問題嘅相關程度\n\n"
            f"問題：{question}\n"
            f"預期答案：{expected}\n"
            f"實際答案：{actual}\n\n"
            '只返回 JSON，格式：{{"answer_correctness": 0.0, "faithfulness": 0.0, "context_relevancy": 0.0}}'
        )

        try:
            raw = await self._llm(prompt)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError("no JSON object")
            parsed = json.loads(raw[start:end])
            return {
                "answer_correctness": max(0.0, min(1.0, float(parsed.get("answer_correctness", 0.0)))),
                "faithfulness": max(0.0, min(1.0, float(parsed.get("faithfulness", 0.0)))),
                "context_relevancy": max(0.0, min(1.0, float(parsed.get("context_relevancy", 0.0)))),
            }
        except Exception:
            return {"answer_correctness": 0.0, "faithfulness": 0.0, "context_relevancy": 0.0}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_qa_pair(hit: dict) -> dict:
    return {"id": hit["_id"], **hit["_source"]}


def _format_run(hit: dict) -> dict:
    return {"run_id": hit["_id"], **hit["_source"]}
