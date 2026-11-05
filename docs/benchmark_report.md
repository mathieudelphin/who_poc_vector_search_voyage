# Voyage AI & MongoDB Atlas Search Benchmark Report

- **Generated At (UTC):** `2026-11-05T14:05:23Z`
- **Benchmark Run ID:** `6aec8d418166399799d2df84`
- **Learner Scope (`enrolled_courses`):** `course-v1:WHOA+H0118EN+Q1_2025, course-v1:WHOA+HQ_SPTB_EN+2025, course-v1:WHOA+0006_BEC_EN+2026, course-v1:WHOA+H0140EN+2025_Q4, course-v1:WHOA+H0117EN+2025_Q1, course-v1:WHOA+bbt+bbt, course-v1:WHOA+IHH+2026, course-v1:WHOA+MAT+2026`
- **Rerank Safety Cutoff:** `>= 0.5`

## 1. Executive Summary: Search Mode & Reranker Comparison

| Profile | Search Mode | Reranker | Top-1 Accuracy | Recall@3 | Chunks Sent to LLM (`>=0.50`) | Off-Topic Cutoff (`<0.50`) | Avg Top-1 Score | Avg Latency | Search Cost (per 1,000 Questions) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Recommended Baseline (Hybrid + rerank-3)** | `hybrid` | `rerank-3` | **100.0%** | 100.0% | `8 retrieved -> 1.6 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.7838` | `651.1 ms` | **`$0.08` / 1,000 questions** (~8 cents total for Embed + Rerank) |
| **Low-Cost Rerank (Hybrid + rerank-3-lite)** | `hybrid` | `rerank-3-lite` | **90.0%** | 100.0% | `8 retrieved -> 1.7 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.7767` | `671.4 ms` | **`$0.03` / 1,000 questions** (~3 cents total for Embed + Rerank) |
| **Hybrid Only — No Reranker (No >=0.50 Cutoff)** | `hybrid` | `none` | **40.0%** | 80.0% | `8 retrieved -> 3.0 kept (max 3)` | **FAIL (Sent 3 Unrelated)** | `N/A (No Reranker)` | `252.1 ms` | **`$0.001` / 1,000 questions** (~0.1 cent — Embed only, No Rerank) |
| **Vector-Only + Rerank ($vectorSearch + rerank-3)** | `vector` | `rerank-3` | **80.0%** | 80.0% | `8 retrieved -> 1.4 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.6289` | `624.0 ms` | **`$0.07` / 1,000 questions** (~7 cents total for Embed + Rerank) |
| **Lexical-Only + Rerank ($search + rerank-3)** | `lexical` | `rerank-3` | **70.0%** | 70.0% | `8 retrieved -> 1.2 kept (max 3)` | **PASS (0 Unrelated Sent)** | `0.6289` | `479.9 ms` | **`$0.09` / 1,000 questions** (~9 cents — Rerank only, Free BM25) |

---

## 2. Question-by-Question Breakdown

### TC1_semantic_paraphrase_dropout: Semantic Paraphrase — Zero Shared Keywords (Vector Beats Lexical)
- **Learner Question:** *"Why does unequal participant dropout between study arms distort results?"*
- **Rewritten Query:** `Why does unequal participant dropout between study arms distort results?`
- **Expected Target:** `H0118ENQ12025-html51-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html51-c01` | `0.8051` | 3/3 | `762.7 ms` (339.5+423.2) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0118ENQ12025-html51-c01` | `0.7365` | 3/3 | `819.9 ms` (339.5+480.4) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html105-c01` | `N/A (No Reranker)` | 3/3 | `339.5 ms` (339.5+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html51-c01` | `0.8051` | 3/3 | `637.7 ms` (254.9+382.8) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html105-c01` | `0.7702` | 2/3 | `507.9 ms` (70.8+437.1) | **DIFF / MISS** |

### TC2_exact_reference_web_annex_a: Exact Reference Identifier Lookup (Lexical Beats Vector)
- **Learner Question:** *"Where is web annex A listed in the course?"*
- **Rewritten Query:** `Where is web annex A listed in the course?`
- **Expected Target:** `HQSPTBEN2025-dfec2da100-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6999` | 1/3 | `651.0 ms` (263.2+387.8) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `HQSPTBEN2025-dfec2da100-c01` | `0.7313` | 1/3 | `652.1 ms` (263.2+388.9) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0117EN2025Q1-dff8bdfd5d-c01` | `N/A (No Reranker)` | 3/3 | `263.2 ms` (263.2+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `617.3 ms` (245.1+372.2) | **DIFF / MISS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6999` | 1/3 | `471.8 ms` (77.6+394.2) | **PASS** |

### TC3_rerank3_vs_lite_safety_reporting: Fine-Grained Clinical Disambiguation (rerank-3 Beats rerank-3-lite)
- **Learner Question:** *"Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?"*
- **Rewritten Query:** `Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?`
- **Expected Target:** `H0118ENQ12025-html173-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `646.3 ms` (257.8+388.5) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0118ENQ12025-html177-c01` | `0.7992` | 3/3 | `649.4 ms` (257.8+391.6) | **DIFF / MISS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0118ENQ12025-html173-c01` | `N/A (No Reranker)` | 3/3 | `257.8 ms` (257.8+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `614.4 ms` (229.7+384.7) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0118ENQ12025-html173-c01` | `0.7867` | 3/3 | `467.8 ms` (69.4+398.4) | **PASS** |

### TC5_gsed_app_odk_acronym: Technical Platform Lookup (H0117EN GSED Short Form)
- **Learner Question:** *"What open-source platform is the GSED App built on for offline data collection on a tablet?"*
- **Rewritten Query:** `What open-source platform is the GSED App built on for offline data collection on a tablet?`
- **Expected Target:** `H0117EN2025Q1-f74edee11f-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `614.5 ms` (234.1+380.4) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0117EN2025Q1-f74edee11f-c01` | `0.9246` | 1/3 | `609.1 ms` (234.1+375.0) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0117EN2025Q1-f74edee11f-c01` | `N/A (No Reranker)` | 3/3 | `234.1 ms` (234.1+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `586.2 ms` (219.9+366.3) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0117EN2025Q1-f74edee11f-c01` | `0.9412` | 1/3 | `587.8 ms` (164.5+423.3) | **PASS** |

### TC6_bec_abcde_sample_history: Clinical Mnemonic & Emergency Triage (0006_BEC_EN Basic Emergency Care)
- **Learner Question:** *"In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?"*
- **Rewritten Query:** `In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?`
- **Expected Target:** `0006BECEN2026-62049db3dc-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `607.1 ms` (240.7+366.4) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `0006BECEN2026-62049db3dc-c01` | `0.9005` | 3/3 | `610.3 ms` (240.7+369.6) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-62049db3dc-c01` | `N/A (No Reranker)` | 3/3 | `240.7 ms` (240.7+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `635.1 ms` (237.7+397.4) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-62049db3dc-c01` | `0.9108` | 3/3 | `458.3 ms` (75.6+382.7) | **PASS** |

### TC7_ethics_cioms_ich_e6_guidelines: Regulatory Code Lookup (H0140EN Research Ethics Part 2)
- **Learner Question:** *"Which international ethical guidelines and ICH Good Clinical Practice (GCP) revision are listed in Module 2 resources for protecting participant safety?"*
- **Rewritten Query:** `Which international ethical guidelines and ICH Good Clinical Practice (GCP) revision are listed in Module 2 resources for protecting participant safety?`
- **Expected Target:** `H0140EN2025Q4-48908a5fb5-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `H0140EN2025Q4-48908a5fb5-c01` | `0.8569` | 2/3 | `591.7 ms` (232.2+359.5) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `H0140EN2025Q4-48908a5fb5-c01` | `0.8154` | 3/3 | `597.2 ms` (232.2+365.0) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0140EN2025Q4-48908a5fb5-c01` | `N/A (No Reranker)` | 3/3 | `232.2 ms` (232.2+0.0) | **PASS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `H0140EN2025Q4-48908a5fb5-c01` | `0.8569` | 2/3 | `679.9 ms` (229.0+450.9) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `H0140EN2025Q4-48908a5fb5-c01` | `0.8569` | 1/3 | `465.0 ms` (67.2+397.8) | **PASS** |

### TC8_semantic_paraphrase_nails_jewelry: Semantic Paraphrase — Hand Hygiene Skin Integrity (Vector Beats Lexical)
- **Learner Question:** *"Why are fake acrylic manicures and metal bands prohibited for clinicians?"*
- **Rewritten Query:** `Why are fake acrylic manicures and metal bands prohibited for clinicians?`
- **Expected Target:** `IHH2026-u31-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `IHH2026-u31-c01` | `0.7960` | 1/3 | `625.8 ms` (237.8+388.0) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `IHH2026-u31-c01` | `0.7513` | 1/3 | `771.6 ms` (237.8+533.8) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0140EN2025Q4-d7227f6958-c01` | `N/A (No Reranker)` | 3/3 | `237.8 ms` (237.8+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `IHH2026-u31-c01` | `0.7960` | 1/3 | `604.0 ms` (229.3+374.7) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `453.8 ms` (66.3+387.5) | **DIFF / MISS** |

### TC9_semantic_paraphrase_circulatory_shock: Semantic Paraphrase — Circulatory Perfusion Failure (Vector Beats Lexical)
- **Learner Question:** *"What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?"*
- **Rewritten Query:** `What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?`
- **Expected Target:** `0006BECEN2026-c823108494-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-c823108494-c01` | `0.5632` | 1/3 | `626.5 ms` (238.2+388.3) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `0006BECEN2026-c823108494-c01` | `0.6239` | 1/3 | `611.1 ms` (238.2+372.9) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-62049db3dc-c01` | `N/A (No Reranker)` | 3/3 | `238.2 ms` (238.2+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `0006BECEN2026-c823108494-c01` | `0.5632` | 1/3 | `624.5 ms` (238.6+385.9) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `468.1 ms` (87.1+381.0) | **DIFF / MISS** |

### TC10_exact_reference_bolsa_familia: Exact Reference Citation Lookup — Oliosi / e219-e26 (Lexical Beats Vector)
- **Learner Question:** *"Where is Oliosi or e219-e26 listed in the course?"*
- **Rewritten Query:** `Where is Oliosi or e219-e26 listed in the course?`
- **Expected Target:** `HQSPTBEN2025-dfec2da100-c01`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6947` | 1/3 | `742.6 ms` (238.3+504.3) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `HQSPTBEN2025-dfec2da100-c01` | `0.7072` | 1/3 | `635.6 ms` (238.3+397.3) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `H0140EN2025Q4-html1-c01` | `N/A (No Reranker)` | 3/3 | `238.3 ms` (238.3+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `638.9 ms` (232.8+406.1) | **DIFF / MISS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `HQSPTBEN2025-dfec2da100-c01` | `0.6947` | 1/3 | `471.6 ms` (79.8+391.8) | **PASS** |

### TC4_unenrolled_bsl4_security_cutoff: Tenant Security & >=0.50 Cutoff Test (Reranker Beats No-Reranker)
- **Learner Question:** *"What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?"*
- **Rewritten Query:** `What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?`
- **Expected Target:** `Blocked / < 0.50 Cutoff`

| Profile | Embed Model | Reranker | Top-1 Chunk ID | Top-1 Score | Surviving (`>=0.50`) | Latency (`Retr + Rerank`) | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| Recommended Baseline (Hybrid + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `643.3 ms` (239.6+403.7) | **PASS** |
| Low-Cost Rerank (Hybrid + rerank-3-lite) | `voyage-4` | `rerank-3-lite` | `None (Cutoff)` | `0.0000` | 0/3 | `757.3 ms` (239.6+517.7) | **PASS** |
| Hybrid Only — No Reranker (No >=0.50 Cutoff) | `voyage-4` | `none` | `0006BECEN2026-ae1870440c-c01` | `N/A (No Reranker)` | 3/3 | `239.6 ms` (239.6+0.0) | **DIFF / MISS** |
| Vector-Only + Rerank ($vectorSearch + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `601.7 ms` (234.0+367.7) | **PASS** |
| Lexical-Only + Rerank ($search + rerank-3) | `voyage-4` | `rerank-3` | `None (Cutoff)` | `0.0000` | 0/3 | `446.9 ms` (69.2+377.7) | **PASS** |
