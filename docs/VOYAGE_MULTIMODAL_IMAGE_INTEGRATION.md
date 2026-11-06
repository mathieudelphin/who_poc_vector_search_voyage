# Integrating Voyage Multimodal (`voyage-multimodal-3`) Alongside Atlas Auto-Embed (`voyage-4`)

This guide explains how **embedded Open edX HTML images (`<img ...>`)** and **GridFS binary assets (`openedx_ulmo.fs.files` / `fs.chunks`)** are indexed and retrieved using **`voyage-multimodal-3`** while keeping **MongoDB Atlas Automated Embedding (`type: "autoEmbed"` with `voyage-4`)** as the primary text backbone.

---

## 1. Architectural Pattern: Dual-Field, Sparse Multimodal Indexing

### Why Two Separate Vector Indexes on `poc-who.chunks`?
1. **Atlas `autoEmbed` (`voyage-4`) is Text-Only:** `chunks_vector` (`type: "autoEmbed"`) automatically embeds plain text stored in `chunks.text` inside MongoDB Atlas (`mongot`), with zero client-side vector code. However, `mongot` cannot fetch binary images from Open edX GridFS (`openedx_ulmo.fs.chunks`) or parse `<img src="...">` pixels.
2. **Distinct Latent Vector Spaces:** Even though both `voyage-4` and `voyage-multimodal-3` produce `1024`-dimension float vectors, they live in **different mathematical coordinate spaces** and cannot share a single vector index path.

### The Unified `poc-who.chunks` Schema
Instead of splitting text and images into separate collections, we keep **one unified `chunks` collection** with a sparse multimodal vector field (`image_embedding`) populated **only** on chunks that contain substantive clinical diagrams, charts, or banners:

```json
{
  "_id": "HQSPTBEN2025-0034dd8e0f-c01",
  "course_id": "course-v1:WHOA+HQ_SPTB_EN+2025",
  "unit_id": "0034dd8e0fd4450bafa644fe95732753",
  "sha256": "8c14f903...",
  "text": "Social protection for people affected by TB > Module 3 > Module 3 Unit 5 summary\nUnit 5 summary: Monitoring the coverage and performance... [Embedded HTML Image (chart_P4-1080.png): TB Treatment chart] ...",
  "url": "/learning/course/course-v1:WHOA+HQ_SPTB_EN+2025/...",
  "section_title": "Module 3 Unit 5 summary",
  "is_active": true,
  "images": [
    {
      "filename": "chart_P4-1080.png",
      "alt": "TB Treatment chart",
      "src": "/static/chart_P4-1080.png",
      "url": "/assets/gridfs/asset-v1:WHOA+HQ_SPTB_EN+2025+type@asset+block@chart_P4-1080.png",
      "gridfs_id": "asset-v1:WHOA+HQ_SPTB_EN+2025+type@asset+block@chart_P4-1080.png",
      "thumbnail_gridfs_id": null,
      "content_type": "image/png"
    }
  ],
  "image_embed_model": "voyage-multimodal-3",
  "image_embedding": [0.03529, -0.02662, -0.01909, 0.05849, "... (1024 floats)"]
}
```

### The Three Search Indexes on `poc-who.chunks` (`db.py`)

| Index Name | Type | Indexed Path | Model / Analyzer | Pre-Filters | Footprint in `poc-who` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`chunks_vector`** | `vectorSearch` (`autoEmbed`) | `text` | `voyage-4` | `course_id`, `is_active` | All `411` chunks (managed by Atlas) |
| **`chunks_text`** | `search` (BM25 lexical) | `text` | `lucene.standard` | `course_id`, `is_active` | All `411` chunks |
| **`chunks_image_vector`** | `vectorSearch` (`vector`, `1024d`, `cosine`) | `image_embedding` | `voyage-multimodal-3` | `course_id`, `is_active` | **Sparse (`20` image chunks only, `<100 KB` RAM)** |

```python
# db.py
CHUNKS_IMAGE_VECTOR_INDEX_DEFINITION = {
    "fields": [
        {
            "type": "vector",
            "path": "image_embedding",
            "numDimensions": 1024,
            "similarity": "cosine",
        },
        {"type": "filter", "path": "course_id"},
        {"type": "filter", "path": "is_active"},
    ]
}
```

---

## 2. Five Best Practices Implemented in Code

### 1. Bridge Text & Vision by Injecting `alt` Captions into `chunks.text`
During HTML cleaning (`clean_html_preserving_headings()` in `ingest_worker.py`), every substantive `<img ...>` tag is converted into an inline text marker before HTML tags are stripped:
```text
[Embedded HTML Image (Principle_banner_01_New.png): Principle 1: Good trials are designed to produce scientifically sound answers to relevant questions]
```
- **Recovers image-only Open edX units:** In `course-v1:WHOA+H0118EN+Q1_2025`, 5 units (*Principle 1* through *Principle 5*, e.g. `H0118ENQ12025-html54-c01`) consist solely of a full-width `<img ...>` banner with no `<p>` text. Previously, stripping HTML tags dropped these units as empty; now all `14` image-based chunks in `H0118EN` are preserved.
- **Zero-Vision-LLM compatibility:** Because `chunks.text` contains the image caption, `voyage-4` (`autoEmbed`), `chunks_text` (BM25), `rerank-3`, and the Step B6 text LLM (`gpt-4o-mini`) all see the diagram description without requiring an expensive Vision LLM call on every query.

### 2. Filter Out Decorative UI Icons Before Calling `voyage-multimodal-3`
Open edX HTML blocks frequently include layout dividers and decorative icons (`page_band.png`, `icon-*.svg`, `spacer.gif`). `extract_html_images_from_raw_html()` filters out decorative filenames (`_DECORATIVE_IMAGE_PATTERNS`) so only substantive clinical charts, diagrams, and banners are embedded—reducing multimodal API calls by **>60%**.

### 3. Interleave Chunk Text + GridFS Image Bytes in a Single `multimodalembeddings` Call
Rather than embedding an image in isolation, `embed_chunk_images_multimodal()` (`ingest_worker.py`) loads the binary image from `openedx_ulmo.fs.chunks` (automatically preferring the GridFS JPEG thumbnail if the full PNG exceeds `450 KB`) and sends both the chunk text and image bytes to `POST https://ai.mongodb.com/v1/multimodalembeddings`:

```json
{
  "model": "voyage-multimodal-3",
  "inputs": [
    {
      "content": [
        {"type": "text", "text": "Course > Section > Unit\nChunk text..."},
        {"type": "image_base64", "image_base64": "data:image/png;base64,..."}
      ]
    }
  ],
  "input_type": "document"
}
```

### 4. Preserve `sha256` Delta-Sync for `image_embedding`
In `ingest_course()` (`ingest_worker.py`), before calling `voyage-multimodal-3`, the worker checks `existing_chunks_docs[chunk_id]`. If the chunk's `sha256` hash is unchanged and `image_embedding` is already present in MongoDB, the existing `1024`-float vector is kept at **`0 ms` and `$0.00`**.

### 5. Fuse Across Vector Spaces Using Rank (RRF), Then Rerank with `rerank-3`
At query time (`hybrid_search_chunks()` in `rag_service.py`):
- When `search_mode="multimodal_image"`, the query is embedded with `voyage-multimodal-3` (`input_type: "query"`) and executed against `chunks_image_vector` (`$vectorSearch` on `image_embedding`) with the same strict `course_id: {"$in": enrolled_courses}` and `is_active: True` pre-filter.
- Results from `chunks_image_vector` and `chunks_text` are fused via **Reciprocal Rank Fusion (`merge_rrf_candidates`)**—avoiding raw cosine score mixing across different models—and then passed to **`rerank-3` (`>= 0.50` cutoff)**.

---

## 3. Live Examples in `poc-who.chunks` & How to Demo

Out of `411` total chunks in `poc-who.chunks`, **`20` chunks** carry `images` metadata and a `1024`-dimension `image_embedding`:

| Course ID | Sample Chunk ID | Embedded GridFS Image(s) | Sample Demo Question (Tab 2 Preset Pill) |
| :--- | :--- | :--- | :--- |
| `course-v1:WHOA+HQ_SPTB_EN+2025` | `HQSPTBEN2025-0034dd8e0f-c01`<br/>`HQSPTBEN2025-ee991b6e40-c01` | `chart_P4-1080.png` (*TB Treatment chart*)<br/>`hiap-diagram.png` (*HIAP diagram*) | *"In the Module 3 Unit 5 and Module 4 Unit 3 summaries, what do the TB Treatment chart and the Health in All Policies (HiAP) diagram illustrate?"* |
| `course-v1:WHOA+H0118EN+Q1_2025` | `H0118ENQ12025-html54-c01` (*Principle 1*) | `Principle_banner_01_New.png` | *"What does Principle 1 state in the WHO clinical trials course banner?"* |
| `course-v1:WHOA+IHH+2026` | `IHH2026-u11-c01` | `who-5-moments-hand-hygiene-diagram.png` | *"What are the 5 moments for hand hygiene shown in the clinical diagram?"* |

### Where to Show It in the UI (`/dashboard`)
1. **Tab 2 (Live Course Assistant):**
   - Select **`Mode: Multimodal Image + Text (voyage-multimodal-3)`** (or keep **`Mode: Hybrid`**) and click the preset pill **`HTML Image Diagram (HQ_SPTB_EN): TB Treatment Chart & HiAP Diagram`** or **`HTML Image Banner (H0118EN): Principle 1 Clinical Trial Banner`**.
   - In the **`Verified WHO Source Chunks Sent to the LLM ([S1], [S2])`** panel, each surviving chunk renders the live image thumbnail served from `GET /assets/gridfs/{file_id}`, the `alt` caption, and the `Multimodal: voyage-multimodal-3 (1024d)` badge.
2. **Tab 3 (Open edX Course Ingestion):**
   - Click **"Preview Chunking Only"** in the HTML Chunking Sandbox to show live `<img ...>` extraction + `1024`-dimension `voyage-multimodal-3` vector generation (`image_embedding_dims: 1024`, `image_embedding_preview`).
