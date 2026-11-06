# Voyage AI & MongoDB Atlas Search Benchmark Report

- **Generated At (UTC):** `2026-11-06T11:44:32Z`
- **Benchmark Run ID:** `6aedbda364b167f05eaf1883`
- **Learner Scope (`enrolled_courses`):** `course-v1:WHOA+H0118EN+Q1_2025, course-v1:WHOA+HQ_SPTB_EN+2025, course-v1:WHOA+0006_BEC_EN+2026, course-v1:WHOA+H0140EN+2025_Q4, course-v1:WHOA+H0117EN+2025_Q1, course-v1:WHOA+bbt+bbt, course-v1:WHOA+IHH+2026, course-v1:WHOA+MAT+2026`
- **Rerank Safety Cutoff:** `>= 0.5`

## 1. Executive Summary: Search Mode & Reranker Comparison

| Profile | Search Mode | Reranker | Top-1 Accuracy | Recall@3 | Chunks Sent to LLM (`>=0.50`) | Off-Topic Cutoff (`<0.50`) | Avg Top-1 Score | Avg Latency | Search Cost (per 1,000 Questions) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Recommended Baseline (Hybrid + rerank-3)** | `hybrid` | `rerank-3` | **100.0%** | 100.0% | `8 retrieved -> 1.0 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.8350` | `828.1 ms` | **`$0.13` / 1,000 questions** (~13 cents) |
| **Low-Cost Rerank (Hybrid + rerank-3-lite)** | `hybrid` | `rerank-3-lite` | **100.0%** | 100.0% | `8 retrieved -> 1.0 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.8356` | `768.7 ms` | **`$0.05` / 1,000 questions** (~5 cents) |
| **Hybrid Only — No Reranker (No >=0.50 Cutoff)** | `hybrid` | `none` | **100.0%** | 100.0% | `8 retrieved -> 3.0 kept (max 3)` | **PASS (0 Unrelated Sent)** | `N/A (No Reranker)` | `332.1 ms` | **`$0.001` / 1,000 questions** (~0.1 cent) |
| **Vector-Only + Rerank ($vectorSearch + rerank-3)** | `vector` | `rerank-3` | **0.0%** | 0.0% | `8 retrieved -> 0.0 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.0000` | `752.5 ms` | **`$0.03` / 1,000 questions** (~3 cents) |
| **Lexical-Only + Rerank ($search + rerank-3)** | `lexical` | `rerank-3` | **100.0%** | 100.0% | `8 retrieved -> 1.0 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.8350` | `501.7 ms` | **`$0.16` / 1,000 questions** (~16 cents) |

---

## 2. Question-by-Question Breakdown

### CUSTOM_QUERY: Interactive Custom Query
- **Learner Question:** *"Where is chart_P4-1080.png or TESTwho-ucn-tb-2023.3_Page_01-1080.png embedded in the course?"*
- **Rewritten Query:** `Where is chart_P4-1080.png or TESTwho-ucn-tb-2023.3_Page_01-1080.png embedded in the course?`
- **Expected Target:** `Open Query`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-0034dd8e0f-c01` | `0.8350` | 1/3 | `828.1 ms` (332.1+496.0) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `HQSPTBEN2025-0034dd8e0f-c01` | `0.8356` | 1/3 | `768.7 ms` (332.1+436.6) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html4-c01` | `N/A (No Reranker)` | 3/3 | `332.1 ms` (332.1+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `752.5 ms` (322.6+429.9) | **DIFF / MISS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-0034dd8e0f-c01` | `0.8350` | 1/3 | `501.7 ms` (91.7+410.0) | **PASS** |
