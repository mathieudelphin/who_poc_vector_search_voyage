"""
MongoDB Atlas connection & index setup for the Open edX Learner Assistant PoC (Option 1).
Database: `genai_search`
Collections:
  - `chunks`: 300-400 token plain-text chunks with breadcrumb prefix (autoEmbed via voyage-4)
  - `courses`: 1 card document per course run
  - `sources`: sha256 version tracking per Open edX HTML block
  - `ingest_runs`: ingestion job execution telemetry
  - `chat_sessions`: conversation session metadata
  - `chat_turns`: individual Q&A turns with citations, chunks_used, rating, and TTL index
"""

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.operations import SearchIndexModel

load_dotenv()

logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "genai_search")
OPENEDX_MODULESTORE_DB_NAME = os.getenv("OPENEDX_MODULESTORE_DB_NAME", "openedx_ulmo")
CHAT_TURNS_TTL_SECONDS = int(os.getenv("CHAT_TURNS_TTL_SECONDS", "7776000"))  # 90 days
VOYAGE_EMBED_MODEL = os.getenv("VOYAGE_EMBED_MODEL", "voyage-4")
VOYAGE_MULTIMODAL_MODEL = os.getenv("VOYAGE_MULTIMODAL_MODEL", "voyage-multimodal-3")

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Return a singleton AsyncIOMotorClient connected to MongoDB Atlas."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=10000)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Return the `genai_search` database handle."""
    return get_client()[MONGODB_DB_NAME]


def get_modulestore_db() -> AsyncIOMotorDatabase:
    """Return the Open edX Split Modulestore database (`openedx_ulmo`)."""
    return get_client()[OPENEDX_MODULESTORE_DB_NAME]


# ---------------------------------------------------------------------------
# Atlas Index Definitions (as specified in Option 1 architecture)
# ---------------------------------------------------------------------------

CHUNKS_VECTOR_INDEX_NAME = "chunks_vector"
CHUNKS_VECTOR_INDEX_DEFINITION: Dict[str, Any] = {
    "fields": [
        {
            "type": "autoEmbed",
            "modality": "text",
            "path": "text",
            "model": VOYAGE_EMBED_MODEL,
        },
        {
            "type": "filter",
            "path": "course_id",
        },
        {
            "type": "filter",
            "path": "is_active",
        },
    ]
}

CHUNKS_TEXT_INDEX_NAME = "chunks_text"
CHUNKS_TEXT_INDEX_DEFINITION: Dict[str, Any] = {
    "mappings": {
        "dynamic": False,
        "fields": {
            "text": {
                "type": "string",
                "analyzer": "lucene.standard",
            },
            "course_id": {
                "type": "token",
            },
            "is_active": {
                "type": "boolean",
            },
        },
    }
}

# Multimodal Image Vector Search Index on `chunks.image_embedding` (populated via Voyage AI `voyage-multimodal-3`)
# Note: Voyage AI vectors (`voyage-4` and `voyage-multimodal-3`) are unit-normalized (L2 norm = 1.0),
# so `dotProduct` is the recommended similarity metric (mathematically identical ranking to cosine, with lower CPU cost),
# and `scalar` quantization (`float32` -> `int8`) reduces HNSW index RAM usage by ~75% with negligible recall loss.
CHUNKS_IMAGE_VECTOR_INDEX_NAME = "chunks_image_vector"
CHUNKS_IMAGE_VECTOR_INDEX_DEFINITION: Dict[str, Any] = {
    "fields": [
        {
            "type": "vector",
            "path": "image_embedding",
            "numDimensions": 1024,
            "similarity": "dotProduct",
            "quantization": "scalar",
        },
        {
            "type": "filter",
            "path": "course_id",
        },
        {
            "type": "filter",
            "path": "is_active",
        },
    ]
}


async def ensure_collections_exist(db: AsyncIOMotorDatabase) -> None:
    """Ensure all required collections exist in `genai_search` before creating Search Indexes."""
    existing = await db.list_collection_names()
    required = [
        "chunks",
        "courses",
        "sources",
        "ingest_runs",
        "chat_sessions",
        "chat_turns",
        "benchmark_runs",
    ]
    for coll_name in required:
        if coll_name not in existing:
            await db.create_collection(coll_name)
            logger.info("Created collection: %s.%s", MONGODB_DB_NAME, coll_name)


async def ensure_indexes(db: AsyncIOMotorDatabase | None = None) -> Dict[str, Any]:
    """
    Programmatically create standard B-tree/TTL indexes as well as MongoDB Atlas
    Search (`chunks_text`) and Vector Search (`chunks_vector` with `autoEmbed` / `voyage-4`) indexes.
    """
    if db is None:
        db = get_db()

    results: Dict[str, Any] = {
        "database": MONGODB_DB_NAME,
        "standard_indexes": [],
        "search_indexes": [],
    }

    await ensure_collections_exist(db)

    # 1. Standard MongoDB Indexes & TTL Index on `chat_turns.created_at`
    await db["chunks"].create_index([("course_id", 1), ("is_active", 1)], name="idx_chunks_course_active")
    results["standard_indexes"].append("chunks.idx_chunks_course_active")

    await db["sources"].create_index([("course_id", 1)], name="idx_sources_course")
    results["standard_indexes"].append("sources.idx_sources_course")

    await db["chat_turns"].create_index(
        "created_at",
        expireAfterSeconds=CHAT_TURNS_TTL_SECONDS,
        name="idx_chat_turns_ttl",
    )
    await db["chat_turns"].create_index(
        [("session_id", 1), ("created_at", 1)],
        name="idx_chat_turns_session",
    )
    results["standard_indexes"].extend(["chat_turns.idx_chat_turns_ttl", "chat_turns.idx_chat_turns_session"])

    await db["chat_sessions"].create_index(
        [("learner_id", 1), ("updated_at", -1)],
        name="idx_chat_sessions_learner",
    )
    results["standard_indexes"].append("chat_sessions.idx_chat_sessions_learner")

    await db["benchmark_runs"].create_index(
        [("created_at", -1)],
        name="idx_benchmark_runs_created_at",
    )
    results["standard_indexes"].append("benchmark_runs.idx_benchmark_runs_created_at")

    # 2. Atlas Search & Vector Search (`autoEmbed`) Indexes on `chunks`
    chunks_coll = db["chunks"]
    try:
        existing_search_indexes = await chunks_coll.list_search_indexes().to_list(length=50)
        existing_names = {idx.get("name") for idx in existing_search_indexes}
    except Exception as exc:
        logger.warning("Could not list existing Atlas Search indexes: %s", exc)
        existing_names = set()

    # 2a. Vector Search Index (`chunks_vector` with autoEmbed voyage-4)
    if CHUNKS_VECTOR_INDEX_NAME not in existing_names:
        try:
            vector_model = SearchIndexModel(
                definition=CHUNKS_VECTOR_INDEX_DEFINITION,
                name=CHUNKS_VECTOR_INDEX_NAME,
                type="vectorSearch",
            )
            created_vec = await chunks_coll.create_search_index(model=vector_model)
            results["search_indexes"].append({"name": created_vec, "status": "created"})
            logger.info("Created Atlas Vector Search index (autoEmbed voyage-4): %s", created_vec)
        except Exception as exc:
            logger.warning("Could not create `chunks_vector` index automatically: %s", exc)
            results["search_indexes"].append(
                {
                    "name": CHUNKS_VECTOR_INDEX_NAME,
                    "status": "error",
                    "error": str(exc),
                    "definition": CHUNKS_VECTOR_INDEX_DEFINITION,
                }
            )
    else:
        results["search_indexes"].append({"name": CHUNKS_VECTOR_INDEX_NAME, "status": "already_exists"})

    # 2b. Lexical Search Index (`chunks_text`)
    if CHUNKS_TEXT_INDEX_NAME not in existing_names:
        try:
            text_model = SearchIndexModel(
                definition=CHUNKS_TEXT_INDEX_DEFINITION,
                name=CHUNKS_TEXT_INDEX_NAME,
                type="search",
            )
            created_txt = await chunks_coll.create_search_index(model=text_model)
            results["search_indexes"].append({"name": created_txt, "status": "created"})
            logger.info("Created Atlas Lexical Search index: %s", created_txt)
        except Exception as exc:
            logger.warning("Could not create `chunks_text` index automatically: %s", exc)
            results["search_indexes"].append(
                {
                    "name": CHUNKS_TEXT_INDEX_NAME,
                    "status": "error",
                    "error": str(exc),
                    "definition": CHUNKS_TEXT_INDEX_DEFINITION,
                }
            )
    else:
        results["search_indexes"].append({"name": CHUNKS_TEXT_INDEX_NAME, "status": "already_exists"})

    # 2c. Multimodal Image Vector Search Index (`chunks_image_vector` on `chunks.image_embedding`)
    if CHUNKS_IMAGE_VECTOR_INDEX_NAME not in existing_names:
        try:
            image_vec_model = SearchIndexModel(
                definition=CHUNKS_IMAGE_VECTOR_INDEX_DEFINITION,
                name=CHUNKS_IMAGE_VECTOR_INDEX_NAME,
                type="vectorSearch",
            )
            created_img_vec = await chunks_coll.create_search_index(model=image_vec_model)
            results["search_indexes"].append({"name": created_img_vec, "status": "created"})
            logger.info("Created Atlas Multimodal Image Vector Search index (voyage-multimodal-3): %s", created_img_vec)
        except Exception as exc:
            logger.warning("Could not create `chunks_image_vector` index automatically: %s", exc)
            results["search_indexes"].append(
                {
                    "name": CHUNKS_IMAGE_VECTOR_INDEX_NAME,
                    "status": "error",
                    "error": str(exc),
                    "definition": CHUNKS_IMAGE_VECTOR_INDEX_DEFINITION,
                }
            )
    else:
        try:
            await chunks_coll.update_search_index(
                name=CHUNKS_IMAGE_VECTOR_INDEX_NAME,
                definition=CHUNKS_IMAGE_VECTOR_INDEX_DEFINITION,
            )
            results["search_indexes"].append({"name": CHUNKS_IMAGE_VECTOR_INDEX_NAME, "status": "updated_dotProduct"})
        except Exception:
            results["search_indexes"].append({"name": CHUNKS_IMAGE_VECTOR_INDEX_NAME, "status": "already_exists"})

    return results
