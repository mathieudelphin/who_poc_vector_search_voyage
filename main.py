"""
FastAPI Application (`main.py`) for the Open edX Learner Assistant PoC (Option 1):
  - `POST /ingest/run`: Executes Flow A (`ingest_worker.py`) — ensures Atlas indexes (`chunks_vector` with `autoEmbed` `voyage-4`, `chunks_text`, and `chat_turns` TTL index) and runs delta HTML chunk ingestion into `genai_search`.
  - `POST /chat/stream`: Executes Flow B & Path B' (`rag_service.py`) — streams grounded answers and citation metadata over Server-Sent Events (`SSE`).
  - `POST /chat/rate`: Updates the learner's rating (`1` to `5` or `"up"` / `"down"`) on a saved turn in `genai_search.chat_turns`.
  - `GET /health`: Reports MongoDB Atlas connectivity and collection counts in `genai_search`.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from benchmark_service import generate_markdown_report, run_benchmark_suite
from dashboard_ui import DASHBOARD_HTML
from db import (
    MONGODB_DB_NAME,
    OPENEDX_MODULESTORE_DB_NAME,
    VOYAGE_EMBED_MODEL,
    ensure_indexes,
    get_db,
    get_modulestore_db,
)
from ingest_worker import (
    SAMPLE_OPEN_EDX_COURSES,
    build_chunks_for_block,
    clean_html_preserving_headings,
    compute_sha256,
    ingest_course,
    run_all_seed_ingestions,
)
from rag_service import (
    AI_GATEWAY_BASE_URL,
    AI_GATEWAY_MODEL,
    VOYAGE_API_KEY,
    VOYAGE_BASE_URL,
    VOYAGE_RERANK_MODEL,
    call_gateway_responses,
    get_llm_client,
    is_responses_gateway_configured,
    rerank_chunks,
    stream_chat_answer,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Open edX Learner Assistant PoC (Option 1 — MongoDB Atlas Auto-Embed + Voyage AI)",
    description=(
        "End-to-end RAG PoC using MongoDB Atlas (`genai_search`), Atlas Automated Embedding "
        "(`autoEmbed` with `voyage-4`), `$rankFusion` Hybrid Search, Voyage AI `rerank-2.5` (`>= 0.50` cutoff), "
        "and Azure AI Foundry / OpenAI SSE streaming."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class IngestRunRequest(BaseModel):
    force: bool = Field(
        default=True,
        description="If true, process blocks even if `published_branch` matches existing course card.",
    )
    custom_course: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional custom Open edX course payload to ingest instead of default seed courses.",
    )


class ChatStreamRequest(BaseModel):
    session_id: str = Field(default="sess_9921", description="Conversation session ID.")
    learner_id: str = Field(default="Learner_1042", description="Verified Open edX learner ID.")
    question: str = Field(
        ...,
        examples=["Do I still need to wash my hands if I wore gloves?"],
        description="Learner's question in natural language.",
    )
    enrolled: Optional[List[str]] = Field(
        default=None,
        description=(
            "Optional override for verified enrolled course IDs. "
            "Defaults to Learner_1042's enrolled courses (`WHOA+IHH+2026`, `WHOA+MAT+2026`)."
        ),
    )
    active_course_id: Optional[str] = Field(
        default="course-v1:WHOA+IHH+2026",
        description="Active course context where the learner opened the assistant.",
    )
    embed_model: Optional[str] = Field(
        default=None,
        description="Optional override for Voyage AI autoEmbed query model (`voyage-4-lite`, `voyage-4`, `voyage-4-large`).",
    )
    rerank_model: Optional[str] = Field(
        default=None,
        description="Optional override for Voyage AI reranker (`rerank-3`, `rerank-3-lite`, `none`).",
    )
    search_mode: str = Field(
        default="hybrid",
        description="Search mode (`hybrid` $rankFusion, `vector` $vectorSearch, or `lexical` $search).",
    )


class IngestPreviewRequest(BaseModel):
    course_title: str = Field(default="WHO Clinical Lecture", description="Course title for breadcrumb prefix.")
    section: str = Field(default="1. Clinical Guidelines", description="Section title for breadcrumb prefix.")
    unit_title: str = Field(default="1.1 Lecture Transcript & Key Protocols", description="Unit title.")
    raw_html: str = Field(
        ...,
        description="Raw Open edX HTML lecture block (`<h3>`, `<p>`, `<ul>`, etc.) to preview Flow A chunking.",
    )
    ingest_to_atlas: bool = Field(
        default=False,
        description="If true, also upserts the previewed lecture block into `genai_search.chunks`.",
    )


class BenchmarkRunRequest(BaseModel):
    custom_question: Optional[str] = Field(
        default=None,
        description="Optional single question to compare across all Voyage AI model profiles.",
    )
    suite_mode: str = Field(
        default="quick_4",
        description="Benchmark suite size when `custom_question` is omitted: `quick_4` (4 core questions) or `full_8` (all 8 WHO questions).",
    )
    learner_id: str = Field(default="Learner_1042", description="Verified learner ID.")
    enrolled: Optional[List[str]] = Field(
        default=None,
        description="Optional override for enrolled course IDs.",
    )


class ChatRateRequest(BaseModel):
    turn_id: Optional[str] = Field(
        default=None,
        description="MongoDB `_id` of the chat turn returned in the `done` SSE event.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Fallback session_id (rates the most recent turn in the session if turn_id is omitted).",
    )
    rating: Union[int, str] = Field(
        ...,
        examples=[5, "up"],
        description="Learner feedback rating (e.g., 1-5 or 'up'/'down').",
    )


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check MongoDB Atlas connection and report document counts in `genai_search`."""
    db = get_db()
    try:
        await db.command("ping")
        counts = {}
        for coll in [
            "chunks",
            "courses",
            "sources",
            "ingest_runs",
            "chat_sessions",
            "chat_turns",
            "benchmark_runs",
        ]:
            counts[coll] = await db[coll].count_documents({})
        return {
            "status": "ok",
            "database": MONGODB_DB_NAME,
            "collections": counts,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB Atlas connection failed: {exc}") from exc


@app.get("/status/check")
async def check_pre_demo_status() -> Dict[str, Any]:
    """
    Live System Readiness Probe:
      1. MongoDB Atlas (`poc-who` RAG DB + `openedx_ulmo` Split Modulestore + Search Index statuses)
      2. Voyage AI Model API (`POST https://ai.mongodb.com/v1/rerank` with `rerank-3`)
      3. Azure AI Foundry / OpenAI Chat Model Gateway (Step B6 Single LLM Call)
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # 1. Check MongoDB Atlas Connection, Server Version & Search Indexes
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    mongo_status: Dict[str, Any] = {
        "service": "MongoDB Atlas Database & Search Indexes",
        "ok": False,
        "latency_ms": 0.0,
    }
    try:
        db = get_db()
        mod_db = get_modulestore_db()
        build_info = await db.command("buildInfo")
        server_version = build_info.get("version", "unknown")

        chunks_count = await db["chunks"].count_documents({})
        courses_count = await db["courses"].count_documents({})
        sources_count = await db["sources"].count_documents({})
        modulestore_courses = await mod_db["modulestore.active_versions"].count_documents({})

        search_indexes: List[Dict[str, Any]] = []
        try:
            idx_cursor = db["chunks"].aggregate([{"$listSearchIndexes": {}}])
            async for idx in idx_cursor:
                search_indexes.append(
                    {
                        "name": idx.get("name"),
                        "type": idx.get("type"),
                        "status": idx.get("status"),
                        "queryable": idx.get("queryable"),
                    }
                )
        except Exception as idx_exc:
            search_indexes.append({"name": "listSearchIndexes", "status": f"info: {idx_exc}"})

        mongo_status.update(
            {
                "ok": chunks_count > 0,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "rag_database": MONGODB_DB_NAME,
                "modulestore_database": OPENEDX_MODULESTORE_DB_NAME,
                "mongodb_version": server_version,
                "rank_fusion_native_8_0": server_version.startswith(("8.", "9.")),
                "chunks_count": chunks_count,
                "courses_count": courses_count,
                "sources_count": sources_count,
                "openedx_modulestore_courses": modulestore_courses,
                "search_indexes": search_indexes,
                "message": (
                    f"Connected to MongoDB {server_version} — {chunks_count} chunks across {courses_count} courses "
                    f"({modulestore_courses} courses in {OPENEDX_MODULESTORE_DB_NAME})."
                ),
            }
        )
    except Exception as exc:
        mongo_status.update(
            {
                "ok": False,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "message": f"MongoDB connection error: {exc}",
            }
        )

    # ------------------------------------------------------------------
    # 2. Check Voyage AI API (`https://ai.mongodb.com/v1/rerank`)
    # ------------------------------------------------------------------
    t1 = time.perf_counter()
    voyage_status: Dict[str, Any] = {
        "service": "Voyage AI Rerank & Auto-Embed API (ai.mongodb.com)",
        "ok": False,
        "latency_ms": 0.0,
        "base_url": VOYAGE_BASE_URL,
        "embed_model": VOYAGE_EMBED_MODEL,
        "rerank_model": VOYAGE_RERANK_MODEL,
    }
    try:
        test_candidates = [
            {
                "_id": "health_check_chunk_1",
                "text": "WHO guidelines recommend performing hand hygiene with alcohol-based handrub immediately after removing gloves.",
            }
        ]
        reranked, backend_used = await rerank_chunks(
            question="Should I wash my hands after removing gloves?",
            candidates=test_candidates,
            top_k=1,
            threshold=0.0,
            rerank_model=VOYAGE_RERANK_MODEL,
        )
        live_api_ok = backend_used.startswith("voyage_")
        top_score = reranked[0].get("relevance_score", 0.0) if reranked else 0.0
        voyage_status.update(
            {
                "ok": live_api_ok,
                "latency_ms": round((time.perf_counter() - t1) * 1000, 1),
                "backend_used": backend_used,
                "sample_relevance_score": top_score,
                "api_key_configured": bool(VOYAGE_API_KEY and not VOYAGE_API_KEY.startswith("pa-your-")),
                "message": (
                    f"Live response from {VOYAGE_BASE_URL}/rerank ({backend_used}) — test relevance score: {top_score:.4f}"
                    if live_api_ok
                    else f"Using fallback scorer ({backend_used}) — check VOYAGE_API_KEY in .env"
                ),
            }
        )
    except Exception as exc:
        voyage_status.update(
            {
                "ok": False,
                "latency_ms": round((time.perf_counter() - t1) * 1000, 1),
                "message": f"Voyage AI API check failed: {exc}",
            }
        )

    # ------------------------------------------------------------------
    # 3. Check Azure AI Foundry / Chat Model Gateway (Step B6 — Single LLM Call)
    # ------------------------------------------------------------------
    t2 = time.perf_counter()
    llm_status: Dict[str, Any] = {
        "service": "Azure AI Foundry — Chat Model (Step B6 Single LLM Call)",
        "ok": False,
        "latency_ms": 0.0,
        "gateway_url": AI_GATEWAY_BASE_URL,
        "model": AI_GATEWAY_MODEL,
    }
    try:
        if is_responses_gateway_configured():
            reply = await call_gateway_responses(
                input_prompt="Reply with the single word: READY",
                model=AI_GATEWAY_MODEL,
            )
            llm_status.update(
                {
                    "ok": bool(reply.strip()),
                    "latency_ms": round((time.perf_counter() - t2) * 1000, 1),
                    "provider": "OpenAI Responses API Gateway (/openai/v1/responses)",
                    "sample_reply": reply.strip()[:120],
                    "message": f"Live response from LLM Gateway ({AI_GATEWAY_MODEL}): \"{reply.strip()[:80]}\"",
                }
            )
        else:
            client, model_name = get_llm_client()
            if client is not None:
                resp = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": "Reply with the single word: READY"}],
                    max_tokens=12,
                )
                reply_txt = (resp.choices[0].message.content or "").strip()
                llm_status.update(
                    {
                        "ok": True,
                        "latency_ms": round((time.perf_counter() - t2) * 1000, 1),
                        "provider": "OpenAI / Azure OpenAI (chat.completions)",
                        "model": model_name,
                        "sample_reply": reply_txt[:120],
                        "message": f"Live response from {model_name}: \"{reply_txt[:80]}\"",
                    }
                )
            else:
                llm_status.update(
                    {
                        "ok": False,
                        "latency_ms": round((time.perf_counter() - t2) * 1000, 1),
                        "provider": "Offline Grounded Fallback",
                        "message": "No AZURE_OPENAI_API_KEY / OPENAI_API_KEY configured in .env.",
                    }
                )
    except Exception as exc:
        llm_status.update(
            {
                "ok": False,
                "latency_ms": round((time.perf_counter() - t2) * 1000, 1),
                "message": f"LLM API check failed ({exc}). Verify endpoint and API key configuration in .env.",
            }
        )

    all_ready = bool(mongo_status["ok"] and voyage_status["ok"] and llm_status["ok"])
    return {
        "checked_at_utc": now_iso,
        "all_systems_ready": all_ready,
        "checks": {
            "mongodb": mongo_status,
            "voyage_ai": voyage_status,
            "llm_gateway": llm_status,
        },
    }


@app.post("/ingest/run")
async def trigger_ingest_run(req: IngestRunRequest = IngestRunRequest()) -> Dict[str, Any]:
    """
    Flow A: Ensure MongoDB Atlas Search & Vector Search (`autoEmbed` with `voyage-4`) and TTL indexes,
    and run the 7-step delta content ingestion pipeline.
    """
    db = get_db()
    if req.custom_course:
        index_status = await ensure_indexes(db)
        run_report = await ingest_course(req.custom_course, db=db, force=req.force)
        return {"indexes": index_status, "ingest_runs": [run_report]}

    return await run_all_seed_ingestions(db=db, force=req.force)


@app.post("/chat/stream")
async def chat_stream_endpoint(req: ChatStreamRequest) -> EventSourceResponse:
    """
    Flow B & Path B': Stream grounded answer tokens and `[S1]` citations over Server-Sent Events (`SSE`).
    """
    db = get_db()

    async def event_publisher():
        async for item in stream_chat_answer(
            session_id=req.session_id,
            learner_id=req.learner_id,
            question=req.question,
            enrolled_courses=req.enrolled,
            active_course_id=req.active_course_id,
            embed_model=req.embed_model,
            rerank_model=req.rerank_model,
            search_mode=req.search_mode,
            db=db,
        ):
            yield {
                "event": item["event"],
                "data": json.dumps(item["data"], ensure_ascii=False),
            }

    return EventSourceResponse(event_publisher())


@app.post("/benchmark/run")
async def trigger_benchmark_run(req: BenchmarkRunRequest = BenchmarkRunRequest()) -> Dict[str, Any]:
    """
    Execute a Voyage AI model & search mode comparison (`voyage-4-lite`, `voyage-4`, `voyage-4-large`
    + `rerank-3` / `rerank-3-lite` / `none`), persist the results in `benchmark_runs`,
    and export `docs/benchmark_report.md`.
    """
    db = get_db()
    return await run_benchmark_suite(
        custom_question=req.custom_question,
        suite_mode=req.suite_mode,
        learner_id=req.learner_id,
        enrolled_courses=req.enrolled,
        db=db,
        save_report_md=True,
    )


@app.get("/benchmark/history")
async def get_benchmark_history(limit: int = Query(default=15, ge=1, le=50)) -> Dict[str, Any]:
    """Fetch recent model comparison runs stored in `genai_search.benchmark_runs`."""
    db = get_db()
    cursor = db["benchmark_runs"].find({}).sort("created_at", -1).limit(limit)
    runs: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc["benchmark_id"] = str(doc.pop("_id"))
        if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
            doc["created_at"] = doc["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
        runs.append(doc)
    return {"count": len(runs), "runs": runs}


@app.get("/benchmark/report.md", response_class=PlainTextResponse)
async def get_latest_benchmark_markdown() -> PlainTextResponse:
    """Return the latest benchmark comparison report formatted as Markdown."""
    db = get_db()
    latest = await db["benchmark_runs"].find_one({}, sort=[("created_at", -1)])
    if not latest:
        raise HTTPException(
            status_code=404,
            detail="No benchmark runs found in `genai_search.benchmark_runs`. Call POST /benchmark/run first.",
        )
    latest["benchmark_id"] = str(latest.pop("_id"))
    return PlainTextResponse(content=generate_markdown_report(latest))


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/status", response_class=HTMLResponse)
async def serve_benchmark_dashboard() -> HTMLResponse:
    """Serve the interactive Voyage AI Model Comparison, Pipeline X-Ray & Pre-Demo Status Studio."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/pipeline/inspect")
async def inspect_pipeline_data() -> Dict[str, Any]:
    """
    Return a full X-Ray snapshot of Flow A (Raw Open edX HTML blocks -> Cleaned Chunks in `genai_search.chunks`,
    `courses`, `sources`, `ingest_runs`) so the user can visually trace how WHO lectures are processed.
    """
    db = get_db()
    chunks = await db["chunks"].find({}).to_list(length=400)
    courses = await db["courses"].find({}).to_list(length=50)
    sources = await db["sources"].find({}).to_list(length=300)
    ingest_runs = await db["ingest_runs"].find({}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(length=10)

    return {
        "seed_courses_raw": SAMPLE_OPEN_EDX_COURSES,
        "stored_courses": courses,
        "stored_chunks": chunks,
        "stored_sources": sources,
        "recent_ingest_runs": ingest_runs,
    }


@app.post("/ingest/preview")
async def preview_or_ingest_custom_lecture(req: IngestPreviewRequest) -> Dict[str, Any]:
    """
    Interactive Flow A Sandbox: Takes raw Open edX lecture HTML, runs Step A3/A4 (HTML tag cleaning &
    heading segmentation) and Step A5 (breadcrumb injection, 300-400 token chunking, deterministic `_id`,
    and `sha256` hash), and optionally writes the chunks into `genai_search.chunks`.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block_payload = {
        "block_id": "html_custom_lecture",
        "unit_code": "u99",
        "block_type": "html",
        "section": req.section,
        "unit_title": req.unit_title,
        "url": "/learning/course/course-v1:WHOA+IHH+2026/u99",
        "html": req.raw_html,
    }
    segments = clean_html_preserving_headings(req.raw_html)
    generated_chunks = build_chunks_for_block(
        course_id="course-v1:WHOA+IHH+2026",
        short_code="IHH2026",
        course_title=req.course_title,
        block=block_payload,
        now_iso=now_iso,
    )

    upserted = 0
    if req.ingest_to_atlas:
        db = get_db()
        for ch in generated_chunks:
            await db["chunks"].replace_one({"_id": ch["_id"]}, ch, upsert=True)
            upserted += 1

    return {
        "raw_html_sha256": compute_sha256(req.raw_html),
        "cleaned_segments": segments,
        "generated_chunks": generated_chunks,
        "upserted_to_atlas": upserted,
    }


@app.post("/chat/rate")
async def rate_chat_turn(req: ChatRateRequest) -> Dict[str, Any]:
    """
    Step B7: Record a learner's rating on a saved conversation turn in `genai_search.chat_turns`.
    """
    db = get_db()
    query: Dict[str, Any] = {}

    if req.turn_id:
        try:
            query["_id"] = ObjectId(req.turn_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid turn_id ObjectId: {req.turn_id}") from exc
    elif req.session_id:
        latest = await db["chat_turns"].find_one(
            {"session_id": req.session_id},
            sort=[("created_at", -1)],
        )
        if not latest:
            raise HTTPException(
                status_code=404,
                detail=f"No chat turns found for session_id '{req.session_id}'.",
            )
        query["_id"] = latest["_id"]
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either `turn_id` or `session_id` to rate a chat turn.",
        )

    result = await db["chat_turns"].update_one(query, {"$set": {"rating": req.rating}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Chat turn not found.")

    return {
        "status": "updated",
        "turn_id": str(query["_id"]),
        "rating": req.rating,
    }
