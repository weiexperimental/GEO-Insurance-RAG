# tests/test_integration.py
import os
import pytest

SAMPLE_PDF = "/Users/weiexperimental/Desktop/RAGbot/testdoc/CTFLife_PRMP Leaflet_0625GEN_2601_(Eng).pdf"

pytestmark = pytest.mark.skipif(
    not os.path.exists(SAMPLE_PDF) or not os.getenv("LLM_API_KEY"),
    reason="Requires sample PDF and API key",
)


@pytest.mark.asyncio
async def test_full_ingestion_and_query():
    """End-to-end: ingest a PDF, then query it."""
    from src.config import load_config
    from src.logging_service import RAGLogger
    from src.rag import RAGEngine
    from src.ingestion import IngestionPipeline

    config = load_config()
    logger = RAGLogger(log_dir=config.paths.log_dir)

    engine = RAGEngine(
        llm_config=config.llm,
        embedding_config=config.embedding,
        vision_config=config.vision,
        opensearch_config=config.opensearch,
        working_dir="./test_working_dir",
    )
    await engine.initialize()

    pipeline = IngestionPipeline(config=config, rag_engine=engine, logger=logger)
    result = await pipeline.enqueue(SAMPLE_PDF)
    assert result["status"] == "pending"
    assert result["document_id"]

    await pipeline.process_queue()

    status = pipeline.get_status(result["document_id"])
    assert status["status"] in ("ready", "partial")

    # Query
    answer = await engine.query("What is Policy Reverse Mortgage?")
    assert len(answer) > 0
