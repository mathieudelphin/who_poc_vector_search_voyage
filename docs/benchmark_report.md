# Voyage AI & MongoDB Atlas Search Benchmark Report

- **Generated At (UTC):** `2026-11-05T20:53:39Z`
- **Benchmark Run ID:** `6aececf18bf9774059fb45eb`
- **Learner Scope (`enrolled_courses`):** `course-v1:WHOA+H0118EN+Q1_2025, course-v1:WHOA+HQ_SPTB_EN+2025, course-v1:WHOA+0006_BEC_EN+2026, course-v1:WHOA+H0140EN+2025_Q4, course-v1:WHOA+H0117EN+2025_Q1, course-v1:WHOA+bbt+bbt, course-v1:WHOA+IHH+2026, course-v1:WHOA+MAT+2026`
- **Rerank Safety Cutoff:** `>= 0.5`

## 1. Executive Summary: Search Mode & Reranker Comparison

| Profile | Search Mode | Reranker | Top-1 Accuracy | Recall@3 | Chunks Sent to LLM (`>=0.50`) | Off-Topic Cutoff (`<0.50`) | Avg Top-1 Score | Avg Latency | Search Cost (per 1,000 Questions) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Recommended Baseline (Hybrid + rerank-3)** | `hybrid` | `rerank-3` | **100.0%** | 100.0% | `8 retrieved -> 1.7 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.7883` | `705.6 ms` | **`$0.10` / 1,000 questions** (~10 cents) |
| **Low-Cost Rerank (Hybrid + rerank-3-lite)** | `hybrid` | `rerank-3-lite` | **90.0%** | 100.0% | `8 retrieved -> 1.7 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.7870` | `693.2 ms` | **`$0.04` / 1,000 questions** (~4 cents) |
| **Hybrid Only — No Reranker (No >=0.50 Cutoff)** | `hybrid` | `none` | **30.0%** | 90.0% | `8 retrieved -> 3.0 kept (max 3)` | **FAIL (Sent 3 Unrelated)** | `N/A (No Reranker)` | `296.8 ms` | **`$0.001` / 1,000 questions** (~0.1 cent) |
| **Vector-Only + Rerank ($vectorSearch + rerank-3)** | `vector` | `rerank-3` | **80.0%** | 80.0% | `8 retrieved -> 1.5 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.6334` | `725.1 ms` | **`$0.07` / 1,000 questions** (~7 cents) |
| **Lexical-Only + Rerank ($search + rerank-3)** | `lexical` | `rerank-3` | **70.0%** | 70.0% | `8 retrieved -> 1.3 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.6334` | `494.2 ms` | **`$0.11` / 1,000 questions** (~11 cents) |

---

## 2. Question-by-Question Breakdown

### TC1_semantic_paraphrase_dropout: Semantic Paraphrase — Zero Shared Keywords (Vector Beats Lexical)
- **Learner Question:** *"Why does unequal participant dropout between study arms distort results?"*
- **Rewritten Query:** `Why does unequal participant dropout between study arms distort results?`
- **Expected Target:** `H0118ENQ12025-html51-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html51-c01` | `0.8051` | 3/3 | `700.0 ms` (279.3+420.7) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0118ENQ12025-html51-c01` | `0.7365` | 3/3 | `745.0 ms` (279.3+465.7) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html105-c01` | `N/A (No Reranker)` | 3/3 | `279.3 ms` (279.3+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html51-c01` | `0.8051` | 3/3 | `1066.6 ms` (592.5+474.1) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html105-c01` | `0.7702` | 1/3 | `492.5 ms` (98.5+394.0) | **DIFF / MISS** |

### TC2_exact_reference_web_annex_a: Exact Reference Identifier Lookup (Lexical Beats Vector)
- **Learner Question:** *"Where is web annex A listed in the course?"*
- **Rewritten Query:** `Where is web annex A listed in the course?`
- **Expected Target:** `HQSPTBEN2025-dfec2da100-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6999` | 1/3 | `626.9 ms` (247.2+379.7) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `HQSPTBEN2025-dfec2da100-c01` | `0.7313` | 1/3 | `602.0 ms` (247.2+354.8) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0117EN2025Q1-dff8bdfd5d-c01` | `N/A (No Reranker)` | 3/3 | `247.2 ms` (247.2+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `734.9 ms` (246.8+488.1) | **DIFF / MISS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6999` | 1/3 | `486.7 ms` (79.2+407.5) | **PASS** |

### TC3_rerank3_vs_lite_safety_reporting: Fine-Grained Clinical Disambiguation (rerank-3 Beats rerank-3-lite)
- **Learner Question:** *"Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?"*
- **Rewritten Query:** `Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?`
- **Expected Target:** `H0118ENQ12025-html173-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `625.9 ms` (246.6+379.3) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0118ENQ12025-html177-c01` | `0.7992` | 3/3 | `646.5 ms` (246.6+399.9) | **DIFF / MISS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html173-c01` | `N/A (No Reranker)` | 3/3 | `246.6 ms` (246.6+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `609.5 ms` (241.2+368.3) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `466.3 ms` (85.0+381.3) | **PASS** |

### TC5_gsed_app_odk_acronym: Technical Platform Lookup (H0117EN GSED Short Form)
- **Learner Question:** *"What open-source platform is the GSED App built on for offline data collection on a tablet?"*
- **Rewritten Query:** `What open-source platform is the GSED App built on for offline data collection on a tablet?`
- **Expected Target:** `H0117EN2025Q1-f74edee11f-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `720.3 ms` (322.9+397.4) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0117EN2025Q1-f74edee11f-c01` | `0.9246` | 1/3 | `685.5 ms` (322.9+362.6) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0117EN2025Q1-f74edee11f-c01` | `N/A (No Reranker)` | 3/3 | `322.9 ms` (322.9+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `621.4 ms` (236.4+385.0) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `487.7 ms` (88.0+399.7) | **PASS** |

### TC6_bec_abcde_sample_history: Clinical Mnemonic & Emergency Triage (0006_BEC_EN Basic Emergency Care)
- **Learner Question:** *"In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?"*
- **Rewritten Query:** `In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?`
- **Expected Target:** `0006BECEN2026-62049db3dc-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `995.9 ms` (609.0+386.9) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `0006BECEN2026-62049db3dc-c01` | `0.9005` | 3/3 | `968.8 ms` (609.0+359.8) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-62049db3dc-c01` | `N/A (No Reranker)` | 3/3 | `609.0 ms` (609.0+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `693.9 ms` (241.2+452.7) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `548.8 ms` (80.0+468.8) | **PASS** |

### TC7_gridfs_pdf_gsed_competency_checklist: GridFS PDF Handout Retrieval (Reranker Promotes PDF Content Over HTML Link Page)
- **Learner Question:** *"According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?"*
- **Rewritten Query:** `According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?`
- **Expected Target:** `H0117EN2025Q1-pdf01gsed-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-pdf01gsed-c01` | `0.8972` | 3/3 | `632.0 ms` (250.3+381.7) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0117EN2025Q1-pdf01gsed-c01` | `0.9084` | 3/3 | `704.4 ms` (250.3+454.1) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0117EN2025Q1-238dc1914d-c01` | `N/A (No Reranker)` | 3/3 | `250.3 ms` (250.3+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-pdf01gsed-c01` | `0.8972` | 3/3 | `630.4 ms` (234.0+396.4) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-pdf01gsed-c01` | `0.8972` | 3/3 | `471.3 ms` (76.2+395.1) | **PASS** |

### TC8_semantic_paraphrase_nails_jewelry: Semantic Paraphrase — Hand Hygiene Skin Integrity (Vector Beats Lexical)
- **Learner Question:** *"Why are fake acrylic manicures and metal bands prohibited for clinicians?"*
- **Rewritten Query:** `Why are fake acrylic manicures and metal bands prohibited for clinicians?`
- **Expected Target:** `IHH2026-u31-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `IHH2026-u31-c01` | `0.7960` | 1/3 | `698.1 ms` (249.2+448.9) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `IHH2026-u31-c01` | `0.7513` | 1/3 | `658.5 ms` (249.2+409.3) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html178-c01` | `N/A (No Reranker)` | 3/3 | `249.2 ms` (249.2+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `IHH2026-u31-c01` | `0.7960` | 1/3 | `610.2 ms` (232.6+377.6) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `511.8 ms` (74.8+437.0) | **DIFF / MISS** |

### TC9_semantic_paraphrase_circulatory_shock: Semantic Paraphrase — Circulatory Perfusion Failure (Vector Beats Lexical)
- **Learner Question:** *"What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?"*
- **Rewritten Query:** `What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?`
- **Expected Target:** `0006BECEN2026-c823108494-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-c823108494-c01` | `0.5632` | 1/3 | `660.2 ms` (251.1+409.1) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `0006BECEN2026-c823108494-c01` | `0.6239` | 1/3 | `623.1 ms` (251.1+372.0) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-62049db3dc-c01` | `N/A (No Reranker)` | 3/3 | `251.1 ms` (251.1+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-c823108494-c01` | `0.5632` | 1/3 | `610.8 ms` (233.4+377.4) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `509.2 ms` (94.3+414.9) | **DIFF / MISS** |

### TC10_exact_reference_bolsa_familia: Exact Reference Citation Lookup — Oliosi / e219-e26 (Lexical Beats Vector)
- **Learner Question:** *"Where is Oliosi or e219-e26 listed in the course?"*
- **Rewritten Query:** `Where is Oliosi or e219-e26 listed in the course?`
- **Expected Target:** `HQSPTBEN2025-dfec2da100-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6947` | 1/3 | `750.4 ms` (269.0+481.4) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `HQSPTBEN2025-dfec2da100-c01` | `0.7072` | 1/3 | `650.0 ms` (269.0+381.0) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0140EN2025Q4-html1-c01` | `N/A (No Reranker)` | 3/3 | `269.0 ms` (269.0+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `967.9 ms` (260.5+707.4) | **DIFF / MISS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6947` | 1/3 | `473.2 ms` (94.1+379.1) | **PASS** |

### TC4_unenrolled_bsl4_security_cutoff: Tenant Security & >=0.50 Cutoff Test (Reranker Beats No-Reranker)
- **Learner Question:** *"What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?"*
- **Rewritten Query:** `What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?`
- **Expected Target:** `Blocked / < 0.50 Cutoff`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `646.1 ms` (243.5+402.6) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `None (Cutoff)` | `0.0000` | 0/3 | `648.0 ms` (243.5+404.5) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-ae1870440c-c01` | `N/A (No Reranker)` | 3/3 | `243.5 ms` (243.5+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `705.4 ms` (303.0+402.4) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `494.6 ms` (95.1+399.5) | **PASS** |
