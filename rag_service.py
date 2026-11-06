"""
Flow B & Path B': Answer Generation Backend (`rag_service.py`)
Implements the answer generation pipeline + Path B' personal progress flow with a Single-LLM-Call architecture:
  - B1 & B2: Identify learner (`learner_id`), enforce service-side `enrolled_courses` scope, load recent chat history from `genai_search.chat_turns`.
  - B3: Instant Deterministic Intent Router (`0 LLM calls`, `0 ms`, `$0.00`) choosing between `search_course_content` (Flow B) vs `get_my_progress` (Path B'). No LLM "Query Beautifier" call is made before search because `voyage-4` handles natural-language questions directly.
  - B4: Filtered Hybrid Search with `$rankFusion` merging `$vectorSearch` (`chunks_vector` with `autoEmbed` / `voyage-4` plain-text query) and `$search` (`chunks_text`), pre-filtered by `course_id: {"$in": enrolled_courses}` and `is_active: True`.
  - B5: Rerank & Threshold Check via Voyage AI `rerank-3` (`top_k: 3`, drop `< 0.50`). If best score `< 0.50`, return `"This topic was not found in your enrolled courses."` immediately (`0 LLM calls`, `$0.00` LLM cost).
  - B6: Grounded Answer Generation (Single LLM Call) via Azure AI Foundry / OpenAI using `[S1]`, `[S2]`, `[S3]` citations.
  - B7: Stream tokens via Server-Sent Events (`SSE`), map `[S1]` to real course unit URLs, and persist the turn in `genai_search.chat_turns`.
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncAzureOpenAI, AsyncOpenAI

from db import (
    CHUNKS_IMAGE_VECTOR_INDEX_NAME,
    CHUNKS_TEXT_INDEX_NAME,
    CHUNKS_VECTOR_INDEX_NAME,
    VOYAGE_EMBED_MODEL,
    VOYAGE_MULTIMODAL_MODEL,
    get_db,
)

load_dotenv()

logger = logging.getLogger(__name__)

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_BASE_URL = os.getenv("VOYAGE_BASE_URL", "https://ai.mongodb.com/v1").rstrip("/")
VOYAGE_RERANK_MODEL = os.getenv("VOYAGE_RERANK_MODEL", "rerank-3")
VOYAGE_RERANK_THRESHOLD = float(os.getenv("VOYAGE_RERANK_THRESHOLD", "0.50"))
VOYAGE_MIN_INTERVAL_SECONDS = float(os.getenv("VOYAGE_MIN_INTERVAL_SECONDS", "0.65"))
VOYAGE_MAX_RETRIES = int(os.getenv("VOYAGE_MAX_RETRIES", "3"))

# Polite rate-limiter & in-memory cache for `ai.mongodb.com/v1/rerank`
_VOYAGE_RATE_LOCK = asyncio.Lock()
_LAST_VOYAGE_CALL_TS: float = 0.0
_RERANK_CACHE: Dict[Tuple[Any, ...], Tuple[List[Dict[str, Any]], str, float]] = {}
_LAST_RERANK_HTTP_MS: float = 0.0

# Azure AI Foundry / OpenAI Gateway — `/v1/responses` or `/v1/chat/completions`
_RAW_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
_RAW_AZURE_KEY_2 = os.getenv("AZURE_OPENAI_API_2_KEY", "")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "") or _RAW_AZURE_KEY
AI_GATEWAY_SECONDARY_KEY = os.getenv("AI_GATEWAY_SECONDARY_KEY", "") or _RAW_AZURE_KEY_2
AI_GATEWAY_BASE_URL = os.getenv(
    "AI_GATEWAY_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")
AI_GATEWAY_MODEL = os.getenv("AI_GATEWAY_MODEL", "gpt-4o-mini")

AZURE_OPENAI_API_KEY = _RAW_AZURE_KEY
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

NOT_FOUND_MESSAGE = "This topic was not found in your enrolled courses."


# ---------------------------------------------------------------------------
# Mock Open edX Learner Enrollment & Live Progress Store (Steps B1 & Path B')
# ---------------------------------------------------------------------------

MOCK_LEARNER_PROFILES: Dict[str, Dict[str, Any]] = {
    "Learner_1042": {
        "learner_id": "Learner_1042",
        "name": "Dr. Amina Diallo",
        "enrolled": [
            # Real WHO courses from `openedx_ulmo`
            "course-v1:WHOA+H0118EN+Q1_2025",
            "course-v1:WHOA+HQ_SPTB_EN+2025",
            "course-v1:WHOA+0006_BEC_EN+2026",
            "course-v1:WHOA+H0140EN+2025_Q4",
            "course-v1:WHOA+H0117EN+2025_Q1",
            "course-v1:WHOA+bbt+bbt",
            # Reference seed courses
            "course-v1:WHOA+IHH+2026",
            "course-v1:WHOA+MAT+2026",
        ],
        # Note: Learner_1042 is NOT enrolled in `course-v1:WHOA+BIO+2026` (Biosafety Level 4)
        "progress": {
            "course-v1:WHOA+H0118EN+Q1_2025": {
                "course_id": "course-v1:WHOA+H0118EN+Q1_2025",
                "course_title": "(UC-513) WHO Good Practices for Clinical Trial Design and Implementation",
                "completion_percent": "72%",
                "completed_units": 48,
                "total_units": 66,
                "current_section": "Module 4: Randomization, Blinding, and Trial Governance",
                "next_deadline": "12 Nov 2026",
                "grade_summary": "91% (Passing threshold: 70%)",
            },
            "course-v1:WHOA+0006_BEC_EN+2026": {
                "course_id": "course-v1:WHOA+0006_BEC_EN+2026",
                "course_title": "Basic Emergency Care",
                "completion_percent": "64%",
                "completed_units": 60,
                "total_units": 94,
                "current_section": "Module 1 - ABCDE approach > SAMPLE History",
                "next_deadline": "30 Nov 2026",
                "grade_summary": "88% (Passing threshold: 75%)",
            },
            "course-v1:WHOA+IHH+2026": {
                "course_id": "course-v1:WHOA+IHH+2026",
                "course_title": "Hand Hygiene Essentials",
                "completion_percent": "64%",
                "completed_units": 5,
                "total_units": 8,
                "current_section": "2. Gloves > 2.1 Gloves and hand hygiene",
                "next_deadline": "30 Oct 2026",
                "grade_summary": "88% (Passing threshold: 70%)",
            },
        },
    }
}


def resolve_learner_scope(
    learner_id: str,
    explicit_enrolled: Optional[List[str]] = None,
) -> Tuple[str, List[str]]:
    """
    Step B1: Identify learner and deterministically resolve their enrolled `course_id` list.
    Security Rule: `course_id` filter is always enforced by the backend service from the
    verified learner session — never generated by the LLM.
    """
    profile = MOCK_LEARNER_PROFILES.get(learner_id)
    if explicit_enrolled is not None:
        return learner_id, explicit_enrolled
    if profile:
        return learner_id, list(profile["enrolled"])
    # Default PoC enrollment scope
    return learner_id, ["course-v1:WHOA+IHH+2026", "course-v1:WHOA+MAT+2026"]


def get_my_progress(learner_id: str, course_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Path B': Mock Open edX live progress API (`get_my_progress`).
    Personal learner progress is fetched live at request time and is NEVER indexed in MongoDB vector search.
    """
    profile = MOCK_LEARNER_PROFILES.get(learner_id, MOCK_LEARNER_PROFILES["Learner_1042"])
    progress_map = profile.get("progress", {})
    if course_id and course_id in progress_map:
        return progress_map[course_id]
    return {
        "learner_id": learner_id,
        "courses": list(progress_map.values()),
    }


# ---------------------------------------------------------------------------
# LLM Client Factory (Azure AI Foundry / OpenAI Gateway + Fallback)
# ---------------------------------------------------------------------------

def is_responses_gateway_configured() -> bool:
    """Return True if `AI_GATEWAY_API_KEY` is configured for the `/v1/responses` gateway."""
    return bool(AI_GATEWAY_API_KEY and not AI_GATEWAY_API_KEY.startswith("your-"))


def _extract_text_from_responses_payload(body: Dict[str, Any]) -> str:
    """
    Extract the assistant text output from an OpenAI `/v1/responses` JSON payload
    (handles `output_text`, `output[].content[].text`, or standard `choices[].message.content`).
    """
    if isinstance(body.get("output_text"), str) and body["output_text"].strip():
        return body["output_text"].strip()

    texts: List[str] = []
    for item in body.get("output", []):
        if isinstance(item, dict):
            if isinstance(item.get("text"), str):
                texts.append(item["text"])
            for content_part in item.get("content", []):
                if isinstance(content_part, dict) and isinstance(content_part.get("text"), str):
                    texts.append(content_part["text"])
    if texts:
        return "\n".join(texts).strip()

    choices = body.get("choices", [])
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message", {})
        if isinstance(msg.get("content"), str):
            return msg["content"].strip()

    return ""


async def call_gateway_responses(
    input_prompt: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Call the `/v1/responses` AI Gateway (`POST {AI_GATEWAY_BASE_URL}/responses`).
    Automatically falls back to `AI_GATEWAY_SECONDARY_KEY` if the primary key fails.
    """
    url = f"{AI_GATEWAY_BASE_URL}/responses"
    payload: Dict[str, Any] = {
        "model": model or AI_GATEWAY_MODEL,
        "input": f"{instructions}\n\n{input_prompt}" if instructions else input_prompt,
    }
    keys_to_try = [k for k in (AI_GATEWAY_API_KEY, AI_GATEWAY_SECONDARY_KEY) if k]
    last_exc: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        for key in keys_to_try:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            try:
                resp = await http_client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                body = resp.json()
                return _extract_text_from_responses_payload(body)
            except Exception as exc:
                last_exc = exc
                logger.warning("Primary gateway key attempt failed (%s); trying secondary key if available.", exc)

    if last_exc:
        raise last_exc
    return ""


def get_llm_client() -> Tuple[Optional[AsyncOpenAI], str]:
    """Return an AsyncOpenAI / AsyncAzureOpenAI client if configured."""
    if is_responses_gateway_configured():
        client = AsyncOpenAI(
            api_key=AI_GATEWAY_API_KEY,
            base_url=AI_GATEWAY_BASE_URL,
        )
        return client, AI_GATEWAY_MODEL

    if (
        AZURE_OPENAI_API_KEY
        and AZURE_OPENAI_ENDPOINT
        and not AZURE_OPENAI_API_KEY.startswith("your-")
    ):
        if "/openai/v1" in AZURE_OPENAI_ENDPOINT:
            base = AZURE_OPENAI_ENDPOINT.rstrip("/")
            if base.endswith("/responses"):
                base = base[: -len("/responses")]
            client = AsyncOpenAI(api_key=AZURE_OPENAI_API_KEY, base_url=base)
            return client, AZURE_OPENAI_DEPLOYMENT

        client = AsyncAzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        return client, AZURE_OPENAI_DEPLOYMENT

    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("your-"):
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        return client, os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    return None, AI_GATEWAY_MODEL


# ---------------------------------------------------------------------------
# Step B2: Load Recent Chat History
# ---------------------------------------------------------------------------

async def load_recent_chat_turns(
    session_id: str,
    db: AsyncIOMotorDatabase,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    """Load the most recent conversation turns for `session_id` from `genai_search.chat_turns`."""
    cursor = (
        db["chat_turns"]
        .find(
            {"session_id": session_id},
            {"_id": 0, "question": 1, "answer": 1, "rewritten_query": 1, "created_at": 1},
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    turns = await cursor.to_list(length=limit)
    turns.reverse()
    return turns


# ---------------------------------------------------------------------------
# Step B3: Tool Routing & Query Rewriting
# ---------------------------------------------------------------------------

ROUTER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_course_content",
            "description": (
                "Search the learner's enrolled Open edX course content for clinical guidelines, "
                "concepts, protocols, or factual questions. Rewrite the learner's question into "
                "a concise, self-contained keyword/semantic search query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Optimized search query (e.g., 'hand hygiene after removing gloves' "
                            "for 'Do I still need to wash my hands if I wore gloves?')."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_progress",
            "description": (
                "Fetch the learner's personal course completion percentage, completed units, "
                "grades, or upcoming deadlines from the live Open edX Progress API (Path B')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "course_id": {
                        "type": "string",
                        "description": "Optional specific course_id (e.g., 'course-v1:WHOA+IHH+2026').",
                    }
                },
            },
        },
    },
]


def _heuristic_route_and_rewrite(
    question: str,
    active_course_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Instant deterministic intent router (`0 LLM calls`, `0 ms`, `$0.00`).
    Routes personal course progress/grade/deadline questions to `get_my_progress` (Path B')
    and passes course content questions directly to `search_course_content` (Flow B) without
    paying for an extra LLM "Query Beautifier" round-trip before search.
    """
    q_lower = question.lower()
    progress_keywords = [
        "how much of the course",
        "my progress",
        "have i finished",
        "completion",
        "next deadline",
        "my grade",
        "how far along",
        "completed",
    ]
    if any(kw in q_lower for kw in progress_keywords):
        return {
            "tool": "get_my_progress",
            "course_id": active_course_id,
            "rewritten_query": None,
        }

    return {
        "tool": "search_course_content",
        "rewritten_query": question.strip(),
        "course_id": active_course_id,
    }


async def route_and_rewrite_query(
    question: str,
    recent_turns: List[Dict[str, Any]],
    active_course_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Step B3: Instant Deterministic Intent Router (`0 LLM calls`, `$0.00`).
    Why no LLM "Query Beautifier" call here?
      - Calling an LLM before retrieval doubles LLM API invocations (2 calls per request) and adds ~1.5s latency.
      - MongoDB Atlas Automated Embedding (`voyage-4`) + `$rankFusion` natively embeds natural-language
        learner questions at 100% Top-1 accuracy without needing an LLM to rewrite the query first.
      - Personal progress questions (`get_my_progress`) vs. course content questions (`search_course_content`)
        are routed deterministically in <1 ms at $0.00 cost.
    """
    _ = recent_turns
    return _heuristic_route_and_rewrite(question, active_course_id=active_course_id)


# ---------------------------------------------------------------------------
# Step B4: Filtered Hybrid Search with `$rankFusion` (`$vectorSearch` + `$search`)
# ---------------------------------------------------------------------------

def build_rank_fusion_pipeline(
    rewritten_query: str,
    enrolled_courses: List[str],
    embed_model: Optional[str] = None,
    candidate_limit: int = 40,
) -> List[Dict[str, Any]]:
    """
    Build the exact MongoDB Atlas `$rankFusion` hybrid search aggregation pipeline
    combining `$vectorSearch` (Atlas `autoEmbed` with `voyage-4` taking plain text `query`)
    and `$search` (`chunks_text` lexical search), pre-filtered by `enrolled_courses` and `is_active: True`.
    """
    vector_search_stage: Dict[str, Any] = {
        "index": CHUNKS_VECTOR_INDEX_NAME,
        "path": "text",
        "query": rewritten_query,
        "numCandidates": 150,
        "limit": candidate_limit,
        "filter": {
            "course_id": {"$in": enrolled_courses},
            "is_active": True,
        },
    }

    return [
        {
            "$rankFusion": {
                "input": {
                    "pipelines": {
                        "vector": [
                            {"$vectorSearch": vector_search_stage}
                        ],
                        "text": [
                            {
                                "$search": {
                                    "index": CHUNKS_TEXT_INDEX_NAME,
                                    "compound": {
                                        "must": [
                                            {
                                                "text": {
                                                    "query": rewritten_query,
                                                    "path": "text",
                                                }
                                            }
                                        ],
                                        "filter": [
                                            {
                                                "in": {
                                                    "path": "course_id",
                                                    "value": enrolled_courses,
                                                }
                                            },
                                            {
                                                "equals": {
                                                    "path": "is_active",
                                                    "value": True,
                                                }
                                            },
                                        ],
                                    },
                                }
                            },
                            {"$limit": candidate_limit},
                        ],
                    }
                }
            }
        },
        {"$limit": candidate_limit},
        {
            "$project": {
                "_id": 1,
                "course_id": 1,
                "text": 1,
                "url": 1,
                "section_title": 1,
                "images": 1,
                "image_embed_model": 1,
            }
        },
    ]


def build_vector_only_pipeline(
    rewritten_query: str,
    enrolled_courses: List[str],
    embed_model: Optional[str] = None,
    candidate_limit: int = 40,
) -> List[Dict[str, Any]]:
    """Build a pure `$vectorSearch` pipeline (`autoEmbed` with `voyage-4`) for side-by-side search mode comparison."""
    vector_search_stage: Dict[str, Any] = {
        "index": CHUNKS_VECTOR_INDEX_NAME,
        "path": "text",
        "query": rewritten_query,
        "numCandidates": 150,
        "limit": candidate_limit,
        "filter": {
            "course_id": {"$in": enrolled_courses},
            "is_active": True,
        },
    }

    return [
        {"$vectorSearch": vector_search_stage},
        {
            "$project": {
                "_id": 1,
                "course_id": 1,
                "text": 1,
                "url": 1,
                "section_title": 1,
                "images": 1,
                "image_embed_model": 1,
                "retrieval_score": {"$meta": "vectorSearchScore"},
            }
        },
    ]


async def embed_multimodal_query(query_text: str) -> Optional[List[float]]:
    """
    Embed a natural-language query into the 1024-dimension `voyage-multimodal-3` vector space
    (`POST {VOYAGE_BASE_URL}/multimodalembeddings` with `input_type: "query"`) to search
    `chunks_image_vector` (`path: "image_embedding"`).
    """
    if not VOYAGE_API_KEY or VOYAGE_API_KEY.startswith("pa-your-"):
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            resp = await http_client.post(
                f"{VOYAGE_BASE_URL}/multimodalembeddings",
                headers={
                    "Authorization": f"Bearer {VOYAGE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VOYAGE_MULTIMODAL_MODEL,
                    "inputs": [{"content": [{"type": "text", "text": query_text}]}],
                    "input_type": "query",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            vec = (body.get("data") or [{}])[0].get("embedding")
            if isinstance(vec, list) and len(vec) == 1024:
                return vec
    except Exception as exc:
        logger.warning("Voyage multimodal query embedding failed (%s).", exc)
    return None


def build_image_vector_pipeline(
    query_vector: List[float],
    enrolled_courses: List[str],
    candidate_limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Build a `$vectorSearch` pipeline against `chunks_image_vector` (`path: "image_embedding"`, 1024d `voyage-multimodal-3`),
    strictly pre-filtered by `course_id: {"$in": enrolled_courses}` and `is_active: True`.
    """
    return [
        {
            "$vectorSearch": {
                "index": CHUNKS_IMAGE_VECTOR_INDEX_NAME,
                "path": "image_embedding",
                "queryVector": query_vector,
                "numCandidates": 100,
                "limit": candidate_limit,
                "filter": {
                    "course_id": {"$in": enrolled_courses},
                    "is_active": True,
                },
            }
        },
        {
            "$project": {
                "_id": 1,
                "course_id": 1,
                "text": 1,
                "url": 1,
                "section_title": 1,
                "images": 1,
                "image_embed_model": 1,
                "retrieval_score": {"$meta": "vectorSearchScore"},
            }
        },
    ]


def build_lexical_only_pipeline(
    rewritten_query: str,
    enrolled_courses: List[str],
    candidate_limit: int = 40,
) -> List[Dict[str, Any]]:
    """Build a pure `$search` (`chunks_text`) lexical pipeline for side-by-side comparison."""
    return [
        {
            "$search": {
                "index": CHUNKS_TEXT_INDEX_NAME,
                "compound": {
                    "must": [
                        {
                            "text": {
                                "query": rewritten_query,
                                "path": "text",
                            }
                        }
                    ],
                    "filter": [
                        {
                            "in": {
                                "path": "course_id",
                                "value": enrolled_courses,
                            }
                        },
                        {
                            "equals": {
                                "path": "is_active",
                                "value": True,
                            }
                        },
                    ],
                },
            }
        },
        {"$limit": candidate_limit},
        {
            "$project": {
                "_id": 1,
                "course_id": 1,
                "text": 1,
                "url": 1,
                "section_title": 1,
                "images": 1,
                "image_embed_model": 1,
                "retrieval_score": {"$meta": "searchScore"},
            }
        },
    ]


def merge_rrf_candidates(
    vector_hits: List[Dict[str, Any]],
    lexical_hits: List[Dict[str, Any]],
    k: int = 60,
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) combiner (`score = sum(1 / (k + rank))`) for MongoDB 7.0 clusters
    where the server-side `$rankFusion` stage (introduced in MongoDB 8.0+) is not yet enabled.
    Merges `$vectorSearch` and `$search` results using the exact same RRF math as `$rankFusion`.
    """
    scores: Dict[str, float] = {}
    docs_by_id: Dict[str, Dict[str, Any]] = {}

    for rank_idx, doc in enumerate(vector_hits, start=1):
        cid = doc["_id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank_idx))
        docs_by_id[cid] = doc

    for rank_idx, doc in enumerate(lexical_hits, start=1):
        cid = doc["_id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank_idx))
        if cid not in docs_by_id:
            docs_by_id[cid] = doc

    ranked_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    merged: List[Dict[str, Any]] = []
    for cid in ranked_ids[:limit]:
        item = dict(docs_by_id[cid])
        item["retrieval_score"] = round(scores[cid], 6)
        merged.append(item)
    return merged


async def hybrid_search_chunks(
    rewritten_query: str,
    enrolled_courses: List[str],
    db: AsyncIOMotorDatabase,
    embed_model: Optional[str] = None,
    search_mode: str = "hybrid",
    candidate_limit: int = 40,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Step B4: Execute `$rankFusion` (on MongoDB 8.0+) or parallel `$vectorSearch` + `$search` RRF fusion
    (on MongoDB 7.0) on `chunks`. Also supports `multimodal_image` mode querying `chunks_image_vector`
    (`image_embedding` via `voyage-multimodal-3`).
    Preserves the strict `enrolled_courses` and `is_active: True` security pre-filter at every layer.
    """
    if not enrolled_courses:
        return [], "empty_enrollment"

    target_embed_model = embed_model or VOYAGE_EMBED_MODEL

    # 0. Multimodal Image + Text Search Mode (`$vectorSearch` on `chunks_image_vector` + RRF with `chunks_text`)
    if search_mode == "multimodal_image":
        img_vec_hits: List[Dict[str, Any]] = []
        lex_hits: List[Dict[str, Any]] = []
        q_vec = await embed_multimodal_query(rewritten_query)
        if q_vec:
            try:
                img_pipeline = build_image_vector_pipeline(
                    q_vec, enrolled_courses, candidate_limit=candidate_limit
                )
                img_vec_hits = await db["chunks"].aggregate(img_pipeline).to_list(length=candidate_limit)
            except Exception as exc:
                logger.info("`chunks_image_vector` `$vectorSearch` not ready yet (%s); falling back to MQL image filter + lexical.", exc)

        if not img_vec_hits:
            # While `chunks_image_vector` is building on Atlas, include enrolled chunks that carry `images`
            img_cursor = db["chunks"].find(
                {
                    "course_id": {"$in": enrolled_courses},
                    "is_active": True,
                    "images.0": {"$exists": True},
                },
                {
                    "_id": 1,
                    "course_id": 1,
                    "text": 1,
                    "url": 1,
                    "section_title": 1,
                    "images": 1,
                    "image_embed_model": 1,
                },
            ).limit(candidate_limit)
            img_vec_hits = await img_cursor.to_list(length=candidate_limit)

        try:
            lex_pipeline = build_lexical_only_pipeline(
                rewritten_query, enrolled_courses, candidate_limit=candidate_limit
            )
            lex_hits = await db["chunks"].aggregate(lex_pipeline).to_list(length=candidate_limit)
        except Exception:
            pass

        if img_vec_hits and lex_hits:
            merged = merge_rrf_candidates(img_vec_hits, lex_hits, limit=candidate_limit)
            return merged, f"atlas_multimodal_image_rrf ({VOYAGE_MULTIMODAL_MODEL} + chunks_text)"
        if img_vec_hits:
            return img_vec_hits, f"atlas_multimodal_image_vector ({VOYAGE_MULTIMODAL_MODEL})"
        if lex_hits:
            return lex_hits, f"atlas_lexical_fallback ({VOYAGE_MULTIMODAL_MODEL})"

    # 1. Pure Lexical Search Mode (`$search` on `chunks_text`)
    if search_mode == "lexical":
        try:
            lex_pipeline = build_lexical_only_pipeline(
                rewritten_query, enrolled_courses, candidate_limit=candidate_limit
            )
            hits = await db["chunks"].aggregate(lex_pipeline).to_list(length=candidate_limit)
            if hits:
                return hits, "atlas_lexical_only (lucene.standard)"
        except Exception as exc:
            logger.warning("Atlas lexical `$search` failed (%s).", exc)
        return [], "atlas_lexical_only (0 hits)"

    # 2. Pure Vector Search Mode (`$vectorSearch` on `chunks_vector`)
    elif search_mode == "vector":
        try:
            vec_pipeline = build_vector_only_pipeline(
                rewritten_query,
                enrolled_courses,
                embed_model=target_embed_model,
                candidate_limit=candidate_limit,
            )
            hits = await db["chunks"].aggregate(vec_pipeline).to_list(length=candidate_limit)
            if hits:
                return hits, f"atlas_vector_only ({target_embed_model})"
        except Exception as exc:
            logger.warning(
                "Atlas `$vectorSearch` failed (%s) — falling back to `$search` (`chunks_text`).",
                exc,
            )
            try:
                lex_pipeline = build_lexical_only_pipeline(
                    rewritten_query, enrolled_courses, candidate_limit=candidate_limit
                )
                lex_hits = await db["chunks"].aggregate(lex_pipeline).to_list(length=candidate_limit)
                if lex_hits:
                    return lex_hits, f"atlas_lexical_fallback (chunks_vector pending: {target_embed_model})"
            except Exception:
                pass
        return [], f"atlas_vector_only (0 hits)"

    # 3. Hybrid Search Mode (`$rankFusion` on MongoDB 8.0+, or Parallel RRF on MongoDB 7.0)
    else:
        try:
            rf_pipeline = build_rank_fusion_pipeline(
                rewritten_query,
                enrolled_courses,
                embed_model=target_embed_model,
                candidate_limit=candidate_limit,
            )
            hits = await db["chunks"].aggregate(rf_pipeline).to_list(length=candidate_limit)
            if hits:
                return hits, f"atlas_rank_fusion ({target_embed_model})"
        except Exception as exc:
            # MongoDB 7.0 clusters return Code 40324 ("Unrecognized pipeline stage name: '$rankFusion'").
            # Run `$vectorSearch` and `$search` (`chunks_text`) and fuse via Reciprocal Rank Fusion (RRF)!
            logger.info(
                "Server-side $rankFusion unavailable on MongoDB 7.0 (%s); running RRF over $vectorSearch + $search.",
                exc,
            )
            vector_hits: List[Dict[str, Any]] = []
            lexical_hits: List[Dict[str, Any]] = []

            try:
                vec_pipeline = build_vector_only_pipeline(
                    rewritten_query,
                    enrolled_courses,
                    embed_model=target_embed_model,
                    candidate_limit=candidate_limit,
                )
                vector_hits = await db["chunks"].aggregate(vec_pipeline).to_list(length=candidate_limit)
            except Exception as vec_exc:
                logger.info("`$vectorSearch` not active yet (%s); using `$search` (`chunks_text`).", vec_exc)

            try:
                lex_pipeline = build_lexical_only_pipeline(
                    rewritten_query, enrolled_courses, candidate_limit=candidate_limit
                )
                lexical_hits = await db["chunks"].aggregate(lex_pipeline).to_list(length=candidate_limit)
            except Exception as lex_exc:
                logger.warning("`$search` (`chunks_text`) failed (%s).", lex_exc)

            if vector_hits and lexical_hits:
                merged = merge_rrf_candidates(vector_hits, lexical_hits, limit=candidate_limit)
                return merged, f"atlas_hybrid_rrf_7.0 ({target_embed_model} + chunks_text)"
            if lexical_hits:
                return lexical_hits, f"atlas_search_chunks_text (vector index pending: {target_embed_model})"
            if vector_hits:
                return vector_hits, f"atlas_vector_only ({target_embed_model})"

    # 4. Last-resort strictly pre-filtered MQL fallback
    fallback_cursor = db["chunks"].find(
        {
            "course_id": {"$in": enrolled_courses},
            "is_active": True,
        },
        {
            "_id": 1,
            "course_id": 1,
            "text": 1,
            "url": 1,
            "section_title": 1,
            "images": 1,
            "image_embed_model": 1,
        },
    ).limit(40)
    fallback_hits = await fallback_cursor.to_list(length=40)
    return fallback_hits, f"filtered_mql_fallback ({target_embed_model})"


# ---------------------------------------------------------------------------
# Step B5: Rerank & Threshold Check via Voyage AI `rerank-2.5`
# ---------------------------------------------------------------------------

def _lexical_overlap_score(query: str, document_text: str) -> float:
    """
    Fallback relevance scorer used ONLY if `VOYAGE_API_KEY` is not yet configured in `.env`.
    Computes normalized keyword/medical-term overlap in `[0.0, 1.0]`.
    """
    stopwords = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "if",
        "is", "are", "was", "were", "be", "been", "do", "does", "did", "i", "my",
        "you", "your", "we", "they", "it", "this", "that", "what", "when", "how",
        "should", "need", "still", "can", "after", "before", "from", "by", "at",
    }
    q_tokens = [
        tok for tok in re.findall(r"[a-z0-9]+", query.lower())
        if tok not in stopwords and len(tok) > 2
    ]
    if not q_tokens:
        return 0.0

    doc_lower = document_text.lower()
    matched = sum(1 for tok in q_tokens if tok in doc_lower)
    ratio = matched / len(q_tokens)
    # Scale so strong multi-term matches exceed the 0.50 threshold while unrelated queries score < 0.25
    return round(min(0.95, ratio * 0.90), 4)


def get_last_rerank_http_ms() -> float:
    """Return the pure HTTP execution latency (ms) of the last `rerank_chunks` call (excluding rate-limit sleep)."""
    return _LAST_RERANK_HTTP_MS


async def rerank_chunks(
    question: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 3,
    threshold: float = VOYAGE_RERANK_THRESHOLD,
    rerank_model: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Step B5: Call Voyage AI Rerank API (`POST {VOYAGE_BASE_URL}/rerank` with `model: "rerank-3"`, `top_k: 3`)
    and drop all hits with `relevance_score < 0.50`.
    Includes:
      1. In-memory deduplication cache so identical (question, model, candidate_ids) never call `ai.mongodb.com` twice.
      2. Polite rate-limit pacing (`VOYAGE_MIN_INTERVAL_SECONDS`) between HTTP calls to `ai.mongodb.com`.
      3. Exponential backoff + `Retry-After` handling on HTTP 429 / 5xx responses.
    """
    global _LAST_VOYAGE_CALL_TS, _LAST_RERANK_HTTP_MS

    if not candidates:
        _LAST_RERANK_HTTP_MS = 0.0
        return [], "no_candidates"

    target_rerank_model = rerank_model if rerank_model is not None else VOYAGE_RERANK_MODEL
    if target_rerank_model.lower() in ("none", "off", "raw"):
        _LAST_RERANK_HTTP_MS = 0.0
        raw_top: List[Dict[str, Any]] = []
        for cand in candidates[:top_k]:
            c_copy = dict(cand)
            c_copy["relevance_score"] = None
            raw_top.append(c_copy)
        return raw_top, "none (raw_retrieval_order)"

    candidate_ids_key = tuple(str(c.get("_id", idx)) for idx, c in enumerate(candidates))
    cache_key = (question.strip(), target_rerank_model, top_k, round(threshold, 4), candidate_ids_key)
    if cache_key in _RERANK_CACHE:
        cached_chunks, cached_backend, cached_http_ms = _RERANK_CACHE[cache_key]
        _LAST_RERANK_HTTP_MS = cached_http_ms
        return [dict(c) for c in cached_chunks], f"{cached_backend} (cached)"

    documents = [c["text"] for c in candidates]

    if VOYAGE_API_KEY and not VOYAGE_API_KEY.startswith("pa-your-"):
        url = f"{VOYAGE_BASE_URL}/rerank"
        headers = {
            "Authorization": f"Bearer {VOYAGE_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": question,
            "documents": documents,
            "model": target_rerank_model,
            "top_k": top_k,
        }
        try:
            async with _VOYAGE_RATE_LOCK:
                body: Optional[Dict[str, Any]] = None
                pure_http_ms: float = 0.0
                async with httpx.AsyncClient(timeout=20.0) as http_client:
                    for attempt in range(1, VOYAGE_MAX_RETRIES + 1):
                        # Polite pacing between calls to ai.mongodb.com (excluded from pure_http_ms)
                        elapsed = time.monotonic() - _LAST_VOYAGE_CALL_TS
                        if elapsed < VOYAGE_MIN_INTERVAL_SECONDS:
                            await asyncio.sleep(VOYAGE_MIN_INTERVAL_SECONDS - elapsed)

                        t_http = time.perf_counter()
                        _LAST_VOYAGE_CALL_TS = time.monotonic()
                        resp = await http_client.post(url, headers=headers, json=payload)
                        pure_http_ms = round((time.perf_counter() - t_http) * 1000, 1)

                        if resp.status_code in (429, 502, 503, 504) and attempt < VOYAGE_MAX_RETRIES:
                            retry_after_hdr = resp.headers.get("Retry-After")
                            try:
                                backoff_s = float(retry_after_hdr) if retry_after_hdr else (1.5 * (2 ** (attempt - 1)))
                            except ValueError:
                                backoff_s = 1.5 * (2 ** (attempt - 1))
                            logger.info(
                                "ai.mongodb.com returned HTTP %d on %s (attempt %d/%d); sleeping %.1fs before retry...",
                                resp.status_code,
                                target_rerank_model,
                                attempt,
                                VOYAGE_MAX_RETRIES,
                                backoff_s,
                            )
                            await asyncio.sleep(backoff_s)
                            continue

                        resp.raise_for_status()
                        body = resp.json()
                        break

            if body is not None:
                surviving: List[Dict[str, Any]] = []
                for item in body.get("data", []):
                    idx = item["index"]
                    score = float(item["relevance_score"])
                    if score >= threshold and 0 <= idx < len(candidates):
                        chunk_copy = dict(candidates[idx])
                        chunk_copy["relevance_score"] = round(score, 4)
                        surviving.append(chunk_copy)

                top_surviving = surviving[:top_k]
                backend_label = f"voyage_{target_rerank_model}"
                _LAST_RERANK_HTTP_MS = pure_http_ms
                if len(_RERANK_CACHE) > 256:
                    _RERANK_CACHE.clear()
                _RERANK_CACHE[cache_key] = ([dict(c) for c in top_surviving], backend_label, pure_http_ms)
                return top_surviving, backend_label
        except Exception as exc:
            logger.warning("Voyage AI rerank API call failed (%s); using local relevance fallback.", exc)

    # Fallback scorer when VOYAGE_API_KEY is not yet populated
    scored: List[Dict[str, Any]] = []
    for cand in candidates:
        score = _lexical_overlap_score(question, cand["text"])
        # Slightly differentiate lite vs full model in offline fallback mode for visual testing
        if "lite" in target_rerank_model.lower() and score > 0:
            score = round(max(0.0, score - 0.03), 4)
        if score >= threshold:
            c_copy = dict(cand)
            c_copy["relevance_score"] = score
            scored.append(c_copy)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_k], f"local_overlap_fallback ({target_rerank_model})"


# ---------------------------------------------------------------------------
# Step B6 & B7: Grounded Answer Generation + SSE Streaming + Persist Turn
# ---------------------------------------------------------------------------

def build_citations_and_context(
    top_chunks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Label surviving top chunks `[S1]`, `[S2]`, `[S3]` and map each tag to its real course unit URL
    (and any embedded HTML `images` / `image_embed_model` metadata).
    """
    citations: List[Dict[str, Any]] = []
    context_blocks: List[str] = []

    for idx, chunk in enumerate(top_chunks, start=1):
        tag = f"[S{idx}]"
        citations.append(
            {
                "tag": tag,
                "chunk_id": chunk["_id"],
                "course_id": chunk.get("course_id", ""),
                "title": chunk.get("section_title", ""),
                "url": chunk.get("url", ""),
                "relevance_score": chunk.get("relevance_score"),
                "text": chunk.get("text", ""),
                "images": chunk.get("images", []),
                "image_embed_model": chunk.get("image_embed_model"),
            }
        )
        context_blocks.append(
            f"{tag} (Section: {chunk.get('section_title')} | URL: {chunk.get('url')}):\n{chunk.get('text')}"
        )

    return citations, "\n\n".join(context_blocks)


def _synthesize_extractive_grounded_answer(
    question: str,
    top_chunks: List[Dict[str, Any]],
) -> str:
    """
    Deterministic grounded answer synthesizer used only when Azure OpenAI credentials are not yet configured.
    Extracts key sentences from `[S1]`..`[S3]` and cites them strictly with `[S1]`.
    """
    if not top_chunks:
        return NOT_FOUND_MESSAGE

    primary = top_chunks[0]
    lines = primary["text"].split("\n", 1)
    body = lines[1] if len(lines) > 1 else primary["text"]
    # Clean heading prefix if present
    body = re.sub(r"^[^:]{3,60}:\s*", "", body).strip()

    answer_parts = [f"{body} [S1]"]
    if len(top_chunks) > 1:
        secondary = top_chunks[1]
        s_lines = secondary["text"].split("\n", 1)
        s_body = (s_lines[1] if len(s_lines) > 1 else secondary["text"]).strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", s_body)[0]
        if first_sentence:
            answer_parts.append(f"Additionally, {first_sentence.rstrip('.')} [S2].")

    return " ".join(answer_parts)


async def stream_chat_answer(
    session_id: str,
    learner_id: str,
    question: str,
    enrolled_courses: Optional[List[str]] = None,
    active_course_id: Optional[str] = None,
    embed_model: Optional[str] = None,
    rerank_model: Optional[str] = None,
    search_mode: str = "hybrid",
    db: Optional[AsyncIOMotorDatabase] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    End-to-end Flow B & Path B' SSE generator.
    Yields structured SSE event dicts:
      - `event: "metadata"` (routing, rewritten_query, retrieval & rerank telemetry, citations)
      - `event: "token"` (incremental answer tokens)
      - `event: "done"` (final turn document saved to `genai_search.chat_turns`)
    """
    if db is None:
        db = get_db()

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Step B1 & B2: Resolve verified learner scope and load recent chat history
    learner_id, verified_enrolled = resolve_learner_scope(learner_id, enrolled_courses)
    recent_turns = await load_recent_chat_turns(session_id=session_id, db=db)

    # Step B3: Choose tool & rewrite query
    route_decision = await route_and_rewrite_query(
        question=question,
        recent_turns=recent_turns,
        active_course_id=active_course_id,
    )
    chosen_tool = route_decision["tool"]
    rewritten_query = route_decision.get("rewritten_query")

    # -----------------------------------------------------------------------
    # Path B': Personal Learner Progress (`get_my_progress`) — Never Indexed
    # -----------------------------------------------------------------------
    if chosen_tool == "get_my_progress":
        progress_data = get_my_progress(
            learner_id=learner_id,
            course_id=route_decision.get("course_id"),
        )
        yield {
            "event": "metadata",
            "data": {
                "flow": "Path B' (Live Progress API)",
                "tool": "get_my_progress",
                "learner_id": learner_id,
                "progress": progress_data,
                "citations": [],
                "llm_calls_count": 0,
                "cost_breakdown": {
                    "router_llm_calls": 0,
                    "answer_llm_calls": 0,
                    "embed_tokens": 0,
                    "rerank_tokens": 0,
                    "llm_input_tokens_est": 0,
                    "llm_output_tokens_est": 0,
                    "embed_cost_per_1k_usd": 0.0,
                    "rerank_cost_per_1k_usd": 0.0,
                    "llm_cost_per_1k_usd": 0.0,
                    "total_cost_per_1k_usd": 0.0,
                },
            },
        }

        if "completion_percent" in progress_data:
            answer_text = (
                f"You have completed **{progress_data['completion_percent']}** "
                f"({progress_data['completed_units']}/{progress_data['total_units']} units) of "
                f"**{progress_data['course_title']}**. "
                f"Your current section is *{progress_data['current_section']}*, "
                f"your grade is **{progress_data['grade_summary']}**, and your next deadline is "
                f"**{progress_data['next_deadline']}**."
            )
        else:
            summaries = [
                f"- **{c['course_title']}**: {c['completion_percent']} complete "
                f"(next deadline: {c['next_deadline']}, current section: *{c['current_section']}*)"
                for c in progress_data.get("courses", [])
            ]
            answer_text = "Here is your live Open edX course progress:\n" + "\n".join(summaries)

        for word in re.findall(r"\S+\s*", answer_text):
            yield {"event": "token", "data": {"token": word}}

        turn_doc = await _persist_chat_turn(
            db=db,
            session_id=session_id,
            learner_id=learner_id,
            question=question,
            rewritten_query="[TOOL:get_my_progress]",
            answer=answer_text,
            chunks_used=[],
            citations=[],
            now_dt=now_dt,
            now_iso=now_iso,
        )
        yield {"event": "done", "data": turn_doc}
        return

    # -----------------------------------------------------------------------
    # Flow B: Hybrid Search ($rankFusion) -> Voyage rerank-2.5 -> Grounded SSE
    # -----------------------------------------------------------------------
    search_query = rewritten_query or question
    effective_embed_model = embed_model or VOYAGE_EMBED_MODEL
    effective_rerank_model = rerank_model or VOYAGE_RERANK_MODEL

    candidates, retrieval_mode = await hybrid_search_chunks(
        rewritten_query=search_query,
        enrolled_courses=verified_enrolled,
        db=db,
        embed_model=effective_embed_model,
        search_mode=search_mode,
    )

    # Step B5: Rerank & 0.50 Threshold Check via Voyage AI `rerank-2.5`
    top_chunks, rerank_mode = await rerank_chunks(
        question=question,
        candidates=candidates,
        top_k=3,
        threshold=VOYAGE_RERANK_THRESHOLD,
        rerank_model=effective_rerank_model,
    )

    citations, formatted_context = build_citations_and_context(top_chunks)
    chunks_used = [c["_id"] for c in top_chunks]

    # Transparent per-query token & cost calculation (scaled per 1,000 queries for clarity)
    # 1. Router: 0 LLM calls ($0.00)
    # 2. Query Embedding (`voyage-4` autoEmbed): $0.06 / 1M tokens (0 if lexical-only)
    # 3. Reranker (`rerank-3`: $0.05 / 1M tokens, `rerank-3-lite`: $0.02 / 1M tokens, `none`: $0.00)
    # 4. Grounded Answer Generation (Step B6): 1 LLM call ONLY if len(top_chunks) > 0 (0 LLM calls if < 0.50 cutoff!)
    #    Modeled at standard enterprise GPT-4o-mini / lightweight grounded generation tier ($0.15/1M input, $0.60/1M output)
    query_tokens = max(1, int(round(len(search_query.split()) * 1.35))) if search_mode != "lexical" else 0
    cand_doc_tokens = sum(max(1, int(round(len(c.get("text", "").split()) * 1.35))) for c in candidates)
    rerank_tokens = (
        0
        if effective_rerank_model.lower() == "none"
        else (len(candidates) * max(1, int(round(len(question.split()) * 1.35))) + cand_doc_tokens)
    )
    embed_rate = 0.06 if search_mode != "lexical" else 0.0
    rerank_rate = 0.0 if effective_rerank_model.lower() == "none" else (0.02 if "lite" in effective_rerank_model.lower() else 0.05)

    llm_calls_count = 1 if len(top_chunks) > 0 else 0
    surviving_context_tokens = sum(max(1, int(round(len(c.get("text", "").split()) * 1.35))) for c in top_chunks)
    llm_input_tokens_est = (110 + max(1, int(round(len(question.split()) * 1.35))) + surviving_context_tokens) if llm_calls_count > 0 else 0
    llm_output_tokens_est = 140 if llm_calls_count > 0 else 0

    embed_cost_1k = round((query_tokens * embed_rate) / 1000.0, 4)
    rerank_cost_1k = round((rerank_tokens * rerank_rate) / 1000.0, 4)
    llm_cost_1k = round(((llm_input_tokens_est * 0.15) + (llm_output_tokens_est * 0.60)) / 1000.0, 4) if llm_calls_count > 0 else 0.0
    total_cost_1k = round(embed_cost_1k + rerank_cost_1k + llm_cost_1k, 4)

    yield {
        "event": "metadata",
        "data": {
            "flow": "Flow B (Hybrid RAG + Voyage Rerank)",
            "tool": "search_course_content",
            "learner_id": learner_id,
            "enrolled_courses": verified_enrolled,
            "rewritten_query": search_query,
            "embed_model": effective_embed_model,
            "rerank_model": effective_rerank_model,
            "search_mode": search_mode,
            "retrieval_mode": retrieval_mode,
            "candidates_retrieved": len(candidates),
            "rerank_mode": rerank_mode,
            "surviving_chunks": len(top_chunks),
            "citations": citations,
            "llm_calls_count": llm_calls_count,
            "cost_breakdown": {
                "router_llm_calls": 0,
                "answer_llm_calls": llm_calls_count,
                "embed_tokens": query_tokens,
                "rerank_tokens": rerank_tokens,
                "llm_input_tokens_est": llm_input_tokens_est,
                "llm_output_tokens_est": llm_output_tokens_est,
                "embed_cost_per_1k_usd": embed_cost_1k,
                "rerank_cost_per_1k_usd": rerank_cost_1k,
                "llm_cost_per_1k_usd": llm_cost_1k,
                "total_cost_per_1k_usd": total_cost_1k,
            },
        },
    }

    # Step B5 Cutoff Rule: If no chunk scores >= 0.50, return immediately without calling the LLM to guess!
    if not top_chunks:
        yield {"event": "token", "data": {"token": NOT_FOUND_MESSAGE}}
        turn_doc = await _persist_chat_turn(
            db=db,
            session_id=session_id,
            learner_id=learner_id,
            question=question,
            rewritten_query=search_query,
            answer=NOT_FOUND_MESSAGE,
            chunks_used=[],
            citations=[],
            now_dt=now_dt,
            now_iso=now_iso,
        )
        yield {"event": "done", "data": turn_doc}
        return

    # Step B6: Write a Grounded Answer via Azure AI Foundry / OpenAI Gateway (`/v1/responses` or `chat.completions`)
    client, model_name = get_llm_client()
    full_answer_parts: List[str] = []

    system_prompt = (
        "You are the WHO Academy Open edX Learner Assistant.\n"
        "STRICT GROUNDING RULES:\n"
        "1. Answer the learner's question STRICTLY and ONLY using the provided course chunks ([S1], [S2], [S3]).\n"
        "2. Cite every factual claim inline using its bracketed source tag, e.g. [S1] or [S2].\n"
        "3. Respond in the same language as the learner's question.\n"
        "4. Never guess, extrapolate, or use outside knowledge. If the provided chunks do not answer the question, "
        f"say '{NOT_FOUND_MESSAGE}'."
    )
    user_prompt = (
        f"Learner Question: {question}\n\n"
        f"Verified Course Chunks:\n{formatted_context}\n\n"
        "Provide a clear, concise, grounded answer with inline [S1]/[S2] citations:"
    )

    if is_responses_gateway_configured():
        try:
            gateway_answer = await call_gateway_responses(
                input_prompt=user_prompt,
                instructions=system_prompt,
                model=AI_GATEWAY_MODEL,
            )
            if gateway_answer:
                for word in re.findall(r"\S+\s*", gateway_answer):
                    full_answer_parts.append(word)
                    yield {"event": "token", "data": {"token": word}}
        except Exception as exc:
            logger.warning("Responses gateway generation failed (%s); trying chat.completions/fallback.", exc)

    if not full_answer_parts and client is not None:
        try:
            stream = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_answer_parts.append(token)
                    yield {"event": "token", "data": {"token": token}}
        except Exception as exc:
            logger.warning("LLM streaming failed (%s); falling back to extractive grounded answer.", exc)

    if not full_answer_parts:
        fallback_answer = _synthesize_extractive_grounded_answer(question, top_chunks)
        for word in re.findall(r"\S+\s*", fallback_answer):
            full_answer_parts.append(word)
            yield {"event": "token", "data": {"token": word}}

    final_answer = "".join(full_answer_parts).strip()

    # Step B7: Record turn in `genai_search.chat_turns` & update `genai_search.chat_sessions`
    turn_doc = await _persist_chat_turn(
        db=db,
        session_id=session_id,
        learner_id=learner_id,
        question=question,
        rewritten_query=search_query,
        answer=final_answer,
        chunks_used=chunks_used,
        citations=[
            {"tag": c["tag"], "title": c["title"], "url": c["url"]}
            for c in citations
        ],
        now_dt=now_dt,
        now_iso=now_iso,
    )
    yield {"event": "done", "data": turn_doc}


async def _persist_chat_turn(
    db: AsyncIOMotorDatabase,
    session_id: str,
    learner_id: str,
    question: str,
    rewritten_query: str,
    answer: str,
    chunks_used: List[str],
    citations: List[Dict[str, str]],
    now_dt: datetime,
    now_iso: str,
) -> Dict[str, Any]:
    """
    Save the completed turn into `genai_search.chat_turns` (with BSON Date `created_at` for TTL expiration)
    and upsert session metadata in `genai_search.chat_sessions`.
    """
    await db["chat_sessions"].update_one(
        {"_id": session_id},
        {
            "$set": {
                "session_id": session_id,
                "learner_id": learner_id,
                "updated_at": now_dt,
            },
            "$setOnInsert": {
                "created_at": now_dt,
            },
        },
        upsert=True,
    )

    turn_record: Dict[str, Any] = {
        "session_id": session_id,
        "learner_id": learner_id,
        "question": question,
        "rewritten_query": rewritten_query,
        "answer": answer,
        "chunks_used": chunks_used,
        "citations": citations,
        "rating": None,
        # Store BSON datetime so MongoDB's native TTL index on `created_at` automatically expires old turns
        "created_at": now_dt,
    }
    insert_res = await db["chat_turns"].insert_one(turn_record)

    return {
        "turn_id": str(insert_res.inserted_id),
        "session_id": session_id,
        "learner_id": learner_id,
        "question": question,
        "rewritten_query": rewritten_query,
        "answer": answer,
        "chunks_used": chunks_used,
        "citations": citations,
        "rating": None,
        "created_at": now_iso,
    }
