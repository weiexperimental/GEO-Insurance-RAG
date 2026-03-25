import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from opensearchpy import OpenSearch

from admin.backend.config import load_settings
from admin.backend.ws import ConnectionManager
from admin.backend.poller import Poller
from admin.backend.services.opensearch import OpenSearchService
from admin.backend.services.graph import GraphService
from admin.backend.routers import system, documents, graph, queries, logs, query_playground, chunks, eval


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings

    os_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        use_ssl=False,
    )
    os_service = OpenSearchService(os_client)
    app.state.os_service = os_service

    # Initialize LightRAG library for graph editing + query playground
    import os as _os
    _os.environ["OPENSEARCH_HOSTS"] = f"{settings.opensearch_host}:{settings.opensearch_port}"
    _os.environ["OPENSEARCH_USE_SSL"] = "false"
    _os.environ["OPENSEARCH_VERIFY_CERTS"] = "false"

    lightrag = None
    try:
        from lightrag import LightRAG
        from lightrag.llm.openai import openai_complete_if_cache, openai_embed
        from lightrag.utils import EmbeddingFunc

        async def llm_func(prompt, system_prompt=None, history_messages=None,
                           keyword_extraction=False, **kw):
            return await openai_complete_if_cache(
                model=settings.llm_model,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base,
                **kw,
            )

        async def embed_func(texts, **kw):
            return await openai_embed(
                texts=texts,
                model=settings.embedding_model,
                api_key=settings.embedding_api_key,
                base_url=settings.embedding_api_base,
                **kw,
            )

        lightrag = LightRAG(
            working_dir="./rag_working_dir",
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
        await lightrag.initialize_storages()
    except Exception as e:
        import sys
        print(f"WARNING: LightRAG init failed: {e}", file=sys.stderr)

    graph_service = GraphService(os_client=os_client, lightrag=lightrag)
    app.state.graph_service = graph_service

    from admin.backend.services.query_playground import QueryPlaygroundService
    if lightrag:
        playground_service = QueryPlaygroundService(lightrag)
    else:
        playground_service = None
    app.state.playground_service = playground_service

    from admin.backend.services.chunks import ChunkService
    chunk_service = ChunkService(os_client=os_client, embedding_func=embed_func if lightrag else None)
    app.state.chunk_service = chunk_service

    from admin.backend.services.eval import EvalService

    # Wrap llm_func for eval (needs simpler signature: prompt -> str)
    async def eval_llm_func(prompt):
        return await llm_func(prompt, system_prompt=None, history_messages=[])

    eval_service = EvalService(
        os_client=os_client,
        llm_func=eval_llm_func if lightrag else None,
        lightrag=lightrag,
    )
    app.state.eval_service = eval_service

    ws_manager = ConnectionManager()
    app.state.ws_manager = ws_manager

    poller = Poller(os_service, ws_manager, log_dir=settings.log_dir)
    app.state.poller = poller

    await poller.poll_once()

    task = asyncio.create_task(poller.run())

    yield

    poller.stop()
    task.cancel()


app = FastAPI(title="GEO Insurance RAG Admin", lifespan=lifespan)

import os as _os_mod
_cors_origins = _os_mod.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(queries.router)
app.include_router(logs.router)
app.include_router(query_playground.router)
app.include_router(chunks.router)
app.include_router(eval.router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    manager = app.state.ws_manager
    await manager.connect(ws)
    await manager.send_snapshot(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "sync":
                await manager.send_snapshot(ws)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    settings = load_settings()
    uvicorn.run("admin.backend.main:app", host=settings.host, port=settings.port, reload=True)
