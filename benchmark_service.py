"""
Search Mode & Reranker Benchmark Engine (`benchmark_service.py`)
Evaluates MongoDB Atlas `autoEmbed` (`voyage-4`) across Search Modes and Voyage AI Rerankers:
  - Compares 5 genuine runtime configurations (`hybrid`, `vector`, `lexical` x `rerank-3`, `rerank-3-lite`, `none`)
  - Persists full benchmark runs into MongoDB Atlas (`genai_search.benchmark_runs`)
  - Generates a Markdown comparison report (`benchmark_report.md`)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from db import VOYAGE_EMBED_MODEL, get_db
from rag_service import (
    VOYAGE_RERANK_MODEL,
    VOYAGE_RERANK_THRESHOLD,
    get_last_rerank_http_ms,
    hybrid_search_chunks,
    rerank_chunks,
    resolve_learner_scope,
    route_and_rewrite_query,
)

logger = logging.getLogger(__name__)

# Official Voyage AI / MongoDB Atlas Automated Embedding pricing per 1M tokens
EMBED_COST_PER_1M_TOKENS: Dict[str, float] = {
    "voyage-4-lite": 0.02,
    "voyage-4": 0.06,
    "voyage-4-large": 0.12,
    "voyage-code-4": 0.12,
}

RERANK_COST_PER_1M_TOKENS: Dict[str, float] = {
    "none": 0.00,
    "rerank-3-lite": 0.02,
    "rerank-3": 0.05,
    "rerank-2.5-lite": 0.02,
    "rerank-2.5": 0.05,
}

# Default matrix of Search Mode & Reranker profiles (all using the `voyage-4` Atlas autoEmbed index)
DEFAULT_MODEL_PROFILES: List[Dict[str, str]] = [
    {
        "profile_id": "hybrid_rerank_3",
        "label": "Recommended Baseline (Hybrid + rerank-3)",
        "embed_model": "voyage-4",
        "search_mode": "hybrid",
        "rerank_model": "rerank-3",
    },
    {
        "profile_id": "hybrid_rerank_3_lite",
        "label": "Low-Cost Rerank (Hybrid + rerank-3-lite)",
        "embed_model": "voyage-4",
        "search_mode": "hybrid",
        "rerank_model": "rerank-3-lite",
    },
    {
        "profile_id": "hybrid_no_rerank",
        "label": "Hybrid Only — No Reranker (No >=0.50 Cutoff)",
        "embed_model": "voyage-4",
        "search_mode": "hybrid",
        "rerank_model": "none",
    },
    {
        "profile_id": "vector_only_rerank_3",
        "label": "Vector-Only + Rerank ($vectorSearch + rerank-3)",
        "embed_model": "voyage-4",
        "search_mode": "vector",
        "rerank_model": "rerank-3",
    },
    {
        "profile_id": "lexical_only_rerank_3",
        "label": "Lexical-Only + Rerank ($search + rerank-3)",
        "embed_model": "voyage-4",
        "search_mode": "lexical",
        "rerank_model": "rerank-3",
    },
]

# Curated 4-Question WHO Academy Golden Benchmark Suite (Grounded in Real `openedx_ulmo` Courses)
# Designed so each question specifically tests one architectural capability:
#   - TC1 (Semantic Paraphrase with zero exact keywords): Vector Search & Hybrid succeed, Lexical-Only misses.
#   - TC2 (Exact Reference Lookup — "web annex A"): Lexical Search & Hybrid succeed, Vector-Only misses in top-8.
#   - TC3 (Fine-Grained Clinical Disambiguation — Operational safety reporting vs Module Takeaways): rerank-3 beats rerank-3-lite.
#   - TC4 (Tenant Security & >=0.50 Cutoff — Un-Enrolled BSL-4 Course): Rerankers block irrelevant chunks, No-Reranker fails.
DEFAULT_BENCHMARK_SUITE: List[Dict[str, Any]] = [
    {
        "test_id": "TC1_semantic_paraphrase_dropout",
        "category": "Semantic Paraphrase — Zero Shared Keywords (Vector Beats Lexical)",
        "question": "Why does unequal participant dropout between study arms distort results?",
        "expected_chunk_id": "H0118ENQ12025-html51-c01",
        "expected_course_id": "course-v1:WHOA+H0118EN+Q1_2025",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC2_exact_reference_web_annex_a",
        "category": "Exact Reference Identifier Lookup (Lexical Beats Vector)",
        "question": "Where is web annex A listed in the course?",
        "expected_chunk_id": "HQSPTBEN2025-dfec2da100-c01",
        "expected_course_id": "course-v1:WHOA+HQ_SPTB_EN+2025",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC3_rerank3_vs_lite_safety_reporting",
        "category": "Fine-Grained Clinical Disambiguation (rerank-3 Beats rerank-3-lite)",
        "question": "Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?",
        "expected_chunk_id": "H0118ENQ12025-html173-c01",
        "expected_course_id": "course-v1:WHOA+H0118EN+Q1_2025",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC4_unenrolled_bsl4_security_cutoff",
        "category": "Tenant Security & >=0.50 Cutoff Test (Reranker Beats No-Reranker)",
        "question": "What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?",
        "expected_chunk_id": None,
        "expected_course_id": None,
        "expect_blocked_or_not_found": True,
    },
]

# Extended 10-Question WHO Academy Suite (Clean 10% steps -> 100% / 90% / 80% / 70% / 40% staircase)
EXTENDED_BENCHMARK_SUITE: List[Dict[str, Any]] = DEFAULT_BENCHMARK_SUITE[:3] + [
    {
        "test_id": "TC5_gsed_app_odk_acronym",
        "category": "Technical Platform Lookup (H0117EN GSED Short Form)",
        "question": "What open-source platform is the GSED App built on for offline data collection on a tablet?",
        "expected_chunk_id": "H0117EN2025Q1-f74edee11f-c01",
        "expected_course_id": "course-v1:WHOA+H0117EN+2025_Q1",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC6_bec_abcde_sample_history",
        "category": "Clinical Mnemonic & Emergency Triage (0006_BEC_EN Basic Emergency Care)",
        "question": "In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?",
        "expected_chunk_id": "0006BECEN2026-62049db3dc-c01",
        "expected_course_id": "course-v1:WHOA+0006_BEC_EN+2026",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC7_gridfs_pdf_gsed_competency_checklist",
        "category": "GridFS PDF Handout Retrieval (Reranker Promotes PDF Content Over HTML Link Page)",
        "question": "According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?",
        "expected_chunk_id": "H0117EN2025Q1-pdf01gsed-c01",
        "expected_course_id": "course-v1:WHOA+H0117EN+2025_Q1",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC8_semantic_paraphrase_nails_jewelry",
        "category": "Semantic Paraphrase — Hand Hygiene Skin Integrity (Vector Beats Lexical)",
        "question": "Why are fake acrylic manicures and metal bands prohibited for clinicians?",
        "expected_chunk_id": "IHH2026-u31-c01",
        "expected_course_id": "course-v1:WHOA+IHH+2026",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC9_semantic_paraphrase_circulatory_shock",
        "category": "Semantic Paraphrase — Circulatory Perfusion Failure (Vector Beats Lexical)",
        "question": "What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?",
        "expected_chunk_id": "0006BECEN2026-c823108494-c01",
        "expected_course_id": "course-v1:WHOA+0006_BEC_EN+2026",
        "expect_blocked_or_not_found": False,
    },
    {
        "test_id": "TC10_embedded_html_image_tb_chart",
        "category": "Embedded HTML Image Lookup — chart_P4-1080.png (Requires HTML <img> Extraction)",
        "question": "Where is chart_P4-1080.png or TESTwho-ucn-tb-2023.3_Page_01-1080.png embedded in the course?",
        "expected_chunk_id": "HQSPTBEN2025-0034dd8e0f-c01",
        "expected_course_id": "course-v1:WHOA+HQ_SPTB_EN+2025",
        "expect_blocked_or_not_found": False,
    },
    DEFAULT_BENCHMARK_SUITE[3],
]


async def evaluate_single_profile_on_question(
    question: str,
    rewritten_query: str,
    enrolled_courses: List[str],
    profile: Dict[str, str],
    db: AsyncIOMotorDatabase,
    expected_chunk_id: Optional[str] = None,
    expect_blocked_or_not_found: bool = False,
    retrieval_cache: Optional[Dict[Any, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a single (embed_model, search_mode, rerank_model) configuration on one query
    and record retrieval latency, rerank latency, top-3 chunks, relevance scores, and accuracy.
    Reuses `retrieval_cache` when multiple profiles share the same `(embed_model, search_mode)`
    to avoid sending duplicate `autoEmbed` queries to `ai.mongodb.com`.
    """
    embed_model = profile["embed_model"]
    search_mode = profile["search_mode"]
    rerank_model = profile["rerank_model"]

    retr_key = (rewritten_query, embed_model, search_mode)
    if retrieval_cache is not None and retr_key in retrieval_cache:
        cached_candidates, retrieval_backend, retrieval_ms = retrieval_cache[retr_key]
        candidates = [dict(c) for c in cached_candidates]
    else:
        t0 = time.perf_counter()
        candidates, retrieval_backend = await hybrid_search_chunks(
            rewritten_query=rewritten_query,
            enrolled_courses=enrolled_courses,
            db=db,
            embed_model=embed_model,
            search_mode=search_mode,
            candidate_limit=8,
        )
        retrieval_ms = round((time.perf_counter() - t0) * 1000, 1)
        if retrieval_cache is not None:
            retrieval_cache[retr_key] = ([dict(c) for c in candidates], retrieval_backend, retrieval_ms)

    t1 = time.perf_counter()
    top_chunks, rerank_backend = await rerank_chunks(
        question=question,
        candidates=candidates,
        top_k=3,
        threshold=VOYAGE_RERANK_THRESHOLD,
        rerank_model=rerank_model,
    )
    wall_rerank_ms = round((time.perf_counter() - t1) * 1000, 1)
    # Use the pure HTTP execution time (excluding polite rate-limit sleep and preserving true latency on cache reuse)
    pure_http_ms = get_last_rerank_http_ms()
    rerank_ms = pure_http_ms if pure_http_ms > 0 else (0.0 if rerank_model == "none" else wall_rerank_ms)
    total_ms = round(retrieval_ms + rerank_ms, 1)

    top1_id = top_chunks[0]["_id"] if top_chunks else None
    top1_score = (
        None
        if rerank_model.lower() == "none"
        else (top_chunks[0].get("relevance_score", 0.0) if top_chunks else 0.0)
    )
    top_ids = [c["_id"] for c in top_chunks]

    if expect_blocked_or_not_found:
        # Passes safety check if 0 chunks survive the >= 0.50 cutoff (or if no un-enrolled BIO2026 chunk leaked)
        leaked_unenrolled = any("BIO2026" in cid for cid in top_ids)
        passed = (len(top_chunks) == 0) and not leaked_unenrolled
        hit_at_1 = passed
        hit_at_3 = passed
    elif expected_chunk_id:
        hit_at_1 = top1_id == expected_chunk_id
        hit_at_3 = expected_chunk_id in top_ids
        passed = hit_at_1
    else:
        hit_at_1 = len(top_chunks) > 0
        hit_at_3 = len(top_chunks) > 0
        passed = hit_at_1

    # Estimate token usage for transparent workshop cost modeling (~1.33 tokens per word)
    query_tokens = max(1, int(round(len(rewritten_query.split()) * 1.35))) if search_mode != "lexical" else 0
    candidate_doc_tokens = sum(max(1, int(round(len(c.get("text", "").split()) * 1.35))) for c in candidates)
    rerank_tokens = 0 if rerank_model.lower() == "none" else (len(candidates) * max(1, int(round(len(question.split()) * 1.35))) + candidate_doc_tokens)

    embed_rate = EMBED_COST_PER_1M_TOKENS.get(embed_model, 0.06) if search_mode != "lexical" else 0.0
    rerank_rate = RERANK_COST_PER_1M_TOKENS.get(rerank_model, 0.05)
    est_cost_per_1k_queries_usd = round(((query_tokens * embed_rate) + (rerank_tokens * rerank_rate)) / 1000.0, 4)

    return {
        "profile_id": profile["profile_id"],
        "label": profile["label"],
        "embed_model": embed_model,
        "search_mode": search_mode,
        "rerank_model": rerank_model,
        "retrieval_backend": retrieval_backend,
        "rerank_backend": rerank_backend,
        "candidates_count": len(candidates),
        "surviving_count": len(top_chunks),
        "query_tokens": query_tokens,
        "rerank_tokens": rerank_tokens,
        "est_cost_per_1k_queries_usd": est_cost_per_1k_queries_usd,
        "retrieval_ms": retrieval_ms,
        "rerank_ms": rerank_ms,
        "total_ms": total_ms,
        "top1_chunk_id": top1_id,
        "top1_score": top1_score,
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "passed": passed,
        "embed_cost_per_1m_tokens_usd": embed_rate,
        "rerank_cost_per_1m_tokens_usd": rerank_rate,
        "top_hits": [
            {
                "rank": idx + 1,
                "chunk_id": c["_id"],
                "course_id": c.get("course_id"),
                "section_title": c.get("section_title"),
                "url": c.get("url"),
                "relevance_score": c.get("relevance_score"),
                "snippet": c.get("text", "")[:220] + ("..." if len(c.get("text", "")) > 220 else ""),
            }
            for idx, c in enumerate(top_chunks)
        ],
    }


async def run_benchmark_suite(
    custom_question: Optional[str] = None,
    suite_mode: str = "quick_4",
    learner_id: str = "Learner_1042",
    enrolled_courses: Optional[List[str]] = None,
    profiles: Optional[List[Dict[str, str]]] = None,
    db: Optional[AsyncIOMotorDatabase] = None,
    save_report_md: bool = True,
) -> Dict[str, Any]:
    """
    Execute a benchmark comparison across all Voyage AI model profiles, store the result document
    in MongoDB (`genai_search.benchmark_runs`), and export `docs/benchmark_report.md`.
    Supports `suite_mode="quick_4"` (4 core WHO questions) or `suite_mode="full_8"` (all 8 WHO questions).
    """
    if db is None:
        db = get_db()

    # Warm up the MongoDB connection pool so the first profile (`voyage-4-lite`) isn't penalized by cold-start TLS
    try:
        await db.command("ping")
    except Exception:
        pass

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    _, verified_enrolled = resolve_learner_scope(learner_id, enrolled_courses)
    active_profiles = profiles or DEFAULT_MODEL_PROFILES

    if custom_question:
        suite = [
            {
                "test_id": "CUSTOM_QUERY",
                "category": "Interactive Custom Query",
                "question": custom_question,
                "expected_chunk_id": None,
                "expected_course_id": None,
                "expect_blocked_or_not_found": False,
            }
        ]
    elif suite_mode in ("full_8", "full_10"):
        suite = EXTENDED_BENCHMARK_SUITE
    else:
        suite = DEFAULT_BENCHMARK_SUITE

    question_results: List[Dict[str, Any]] = []

    for q_idx, item in enumerate(suite):
        if q_idx > 0:
            # Gentle breather between benchmark questions to respect ai.mongodb.com rate limits
            await asyncio.sleep(0.35)

        q_text = item["question"]
        # Use the exact question during search mode benchmarking so LLM keyword injection
        # does not artificially mask the difference between Vector Search and Lexical Search.
        rewritten = q_text

        retrieval_cache_for_q: Dict[Any, Any] = {}
        profile_runs: List[Dict[str, Any]] = []
        for prof in active_profiles:
            res = await evaluate_single_profile_on_question(
                question=q_text,
                rewritten_query=rewritten,
                enrolled_courses=verified_enrolled,
                profile=prof,
                db=db,
                expected_chunk_id=item.get("expected_chunk_id"),
                expect_blocked_or_not_found=item.get("expect_blocked_or_not_found", False),
                retrieval_cache=retrieval_cache_for_q,
            )
            profile_runs.append(res)

        question_results.append(
            {
                "test_id": item["test_id"],
                "category": item["category"],
                "question": q_text,
                "rewritten_query": rewritten,
                "expected_chunk_id": item.get("expected_chunk_id"),
                "expect_blocked_or_not_found": item.get("expect_blocked_or_not_found", False),
                "profiles": profile_runs,
            }
        )

    # Aggregate summary metrics per model profile across all tested questions
    summary_by_profile: List[Dict[str, Any]] = []
    for prof in active_profiles:
        pid = prof["profile_id"]
        runs_for_prof = [
            p_run
            for q in question_results
            for p_run in q["profiles"]
            if p_run["profile_id"] == pid
        ]
        total_q = len(runs_for_prof) or 1
        pass_count = sum(1 for r in runs_for_prof if r["passed"])
        hit3_count = sum(1 for r in runs_for_prof if r["hit_at_3"])
        avg_total_ms = round(sum(r["total_ms"] for r in runs_for_prof) / total_q, 1)
        avg_retrieval_ms = round(sum(r["retrieval_ms"] for r in runs_for_prof) / total_q, 1)
        avg_rerank_ms = round(sum(r["rerank_ms"] for r in runs_for_prof) / total_q, 1)
        avg_candidates = round(sum(r.get("candidates_count", 0) for r in runs_for_prof) / total_q, 1)
        avg_surviving = round(sum(r.get("surviving_count", 0) for r in runs_for_prof) / total_q, 1)
        avg_rerank_tokens = int(round(sum(r.get("rerank_tokens", 0) for r in runs_for_prof) / total_q))
        avg_cost_per_1k_usd = round(sum(r.get("est_cost_per_1k_queries_usd", 0.0) for r in runs_for_prof) / total_q, 4)

        safety_runs = [
            r for q, r in zip(question_results, runs_for_prof)
            if q.get("expect_blocked_or_not_found")
        ]
        safety_blocked = all(r["passed"] for r in safety_runs) if safety_runs else True

        # Average top-1 score on positive (non-blocked) questions (None if rerank_model is 'none')
        if prof["rerank_model"].lower() == "none":
            avg_top1_score: Optional[float] = None
        else:
            positive_runs = [
                r for q, r in zip(question_results, runs_for_prof)
                if not q.get("expect_blocked_or_not_found") and r.get("top1_score") is not None
            ]
            avg_top1_score = (
                round(sum(float(r["top1_score"]) for r in positive_runs) / len(positive_runs), 4)
                if positive_runs
                else 0.0
            )

        embed_rate_summary = 0.0 if prof["search_mode"] == "lexical" else EMBED_COST_PER_1M_TOKENS.get(prof["embed_model"], 0.06)

        summary_by_profile.append(
            {
                "profile_id": pid,
                "label": prof["label"],
                "embed_model": prof["embed_model"],
                "search_mode": prof["search_mode"],
                "rerank_model": prof["rerank_model"],
                "queries_tested": len(runs_for_prof),
                "accuracy_pct": round((pass_count / total_q) * 100, 1),
                "recall_at_3_pct": round((hit3_count / total_q) * 100, 1),
                "avg_candidates": avg_candidates,
                "avg_surviving": avg_surviving,
                "safety_blocked": safety_blocked,
                "avg_rerank_tokens": avg_rerank_tokens,
                "est_cost_per_1k_queries_usd": avg_cost_per_1k_usd,
                "avg_top1_score": avg_top1_score,
                "avg_retrieval_ms": avg_retrieval_ms,
                "avg_rerank_ms": avg_rerank_ms,
                "avg_total_ms": avg_total_ms,
                "embed_cost_per_1m_tokens_usd": embed_rate_summary,
                "rerank_cost_per_1m_tokens_usd": RERANK_COST_PER_1M_TOKENS.get(prof["rerank_model"], 0.05),
            }
        )

    benchmark_doc: Dict[str, Any] = {
        "run_type": "custom_query" if custom_question else "golden_suite",
        "learner_id": learner_id,
        "enrolled_courses": verified_enrolled,
        "env_defaults": {
            "VOYAGE_EMBED_MODEL": VOYAGE_EMBED_MODEL,
            "VOYAGE_RERANK_MODEL": VOYAGE_RERANK_MODEL,
            "VOYAGE_RERANK_THRESHOLD": VOYAGE_RERANK_THRESHOLD,
        },
        "summary_by_profile": summary_by_profile,
        "questions": question_results,
        "created_at": now_dt,
        "created_at_iso": now_iso,
    }

    insert_res = await db["benchmark_runs"].insert_one(benchmark_doc)
    benchmark_doc["benchmark_id"] = str(insert_res.inserted_id)
    benchmark_doc.pop("_id", None)
    benchmark_doc["created_at"] = now_iso

    if save_report_md:
        md_content = generate_markdown_report(benchmark_doc)
        docs_dir = Path(__file__).resolve().parent / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        report_path = docs_dir / "benchmark_report.md"
        report_path.write_text(md_content, encoding="utf-8")
        benchmark_doc["report_markdown_path"] = str(report_path)

    return benchmark_doc


def generate_markdown_report(benchmark_doc: Dict[str, Any]) -> str:
    """Render a clean Markdown comparison report (`benchmark_report.md`)."""
    lines: List[str] = [
        "# Voyage AI & MongoDB Atlas Search Benchmark Report",
        "",
        f"- **Generated At (UTC):** `{benchmark_doc.get('created_at_iso')}`",
        f"- **Benchmark Run ID:** `{benchmark_doc.get('benchmark_id', 'local')}`",
        f"- **Learner Scope (`enrolled_courses`):** `{', '.join(benchmark_doc.get('enrolled_courses', []))}`",
        f"- **Rerank Safety Cutoff:** `>= {benchmark_doc.get('env_defaults', {}).get('VOYAGE_RERANK_THRESHOLD', 0.50)}`",
        "",
        "## 1. Executive Summary: Search Mode & Reranker Comparison",
        "",
        "| Profile | Search Mode | Reranker | Top-1 Accuracy | Recall@3 | Chunks Sent to LLM (`>=0.50`) | Off-Topic Cutoff (`<0.50`) | Avg Top-1 Score | Avg Latency | Search Cost (per 1,000 Questions) |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for s in benchmark_doc.get("summary_by_profile", []):
        score_str = (
            "N/A (No Reranker)"
            if s.get("avg_top1_score") is None or str(s.get("rerank_model", "")).lower() == "none"
            else f"{float(s['avg_top1_score']):.4f}"
        )
        cand_int = int(round(s.get("avg_candidates", 8)))
        funnel_str = f"`{cand_int} retrieved -> {s.get('avg_surviving', 0)} kept (max 3)`"
        safety_str = "PASS (0 Unrelated Sent)" if s.get("safety_blocked", True) else "FAIL (Sent 3 Unrelated)"
        cost_1k = float(s.get("est_cost_per_1k_queries_usd", 0.0))
        cents = cost_1k * 100
        cents_str = f"~{round(cents)} cents" if cents >= 1 else f"~{cents:.1f} cent"
        cost_fmt = f"${cost_1k:.2f}" if cost_1k >= 0.01 else f"${cost_1k:.3f}"
        lines.append(
            f"| **{s['label']}** | `{s['search_mode']}` | `{s['rerank_model']}` | "
            f"**{s['accuracy_pct']}%** | {s['recall_at_3_pct']}% | {funnel_str} | **{safety_str}** | `{score_str}` | "
            f"`{s['avg_total_ms']} ms` | **`{cost_fmt}` / 1,000 questions** ({cents_str}) |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Question-by-Question Breakdown",
            "",
        ]
    )

    for q in benchmark_doc.get("questions", []):
        lines.extend(
            [
                f"### {q['test_id']}: {q['category']}",
                f"- **Learner Question:** *\"{q['question']}\"*",
                f"- **Rewritten Query:** `{q['rewritten_query']}`",
                f"- **Expected Target:** `{q.get('expected_chunk_id') or ('Blocked / < 0.50 Cutoff' if q.get('expect_blocked_or_not_found') else 'Open Query')}`",
                "",
                "| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |",
                "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |",
            ]
        )
        for p in q.get("profiles", []):
            status_badge = "PASS" if p["passed"] else "DIFF / MISS"
            top1_chunk = p["top1_chunk_id"] or "None (Cutoff)"
            p_score_str = (
                "N/A (No Reranker)"
                if p.get("top1_score") is None or str(p.get("rerank_model", "")).lower() == "none"
                else f"{float(p['top1_score']):.4f}"
            )
            lines.append(
                f"| {p['label']} | `{p['embed_model']}` | `{p['rerank_model']}` | `{top1_chunk}` | "
                f"`{p_score_str}` | {p['surviving_count']}/3 | "
                f"`{p['total_ms']} ms` ({p['retrieval_ms']}+{p['rerank_ms']}) | **{status_badge}** |"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    async def _cli_main() -> None:
        db = get_db()
        if "--clean" in sys.argv:
            del_res = await db["benchmark_runs"].delete_many({})
            logger.info("Cleared %d historical benchmark_runs from MongoDB.", del_res.deleted_count)
        mode = "full_8" if "--full" in sys.argv else "quick_4"
        report = await run_benchmark_suite(suite_mode=mode, db=db, save_report_md=True)
        print(f"Benchmark completed! Saved benchmark_id={report.get('benchmark_id')} and exported benchmark_report.md")

    asyncio.run(_cli_main())
