"""
Flow A: Content Ingestion Worker (`ingest_worker.py`)
Implements the 7-step ingestion flow for Open edX courses into MongoDB Atlas (`genai_search`):
  - A1 & A2: Detect course change (`published_branch` comparison against `genai_search.courses`).
  - A3 & A4: Extract, clean, and filter HTML (`html` text blocks & `about` page only; skip `video`, `problem`, `pdf`, `scorm`, `chatgptxblock`, `lti`).
  - A5: Cut into 300-400 token chunks at HTML headings with breadcrumb prefix (`"Course Title > Section > Unit"`), deterministic `_id`, and `sha256`.
  - A6: Delta write to Atlas (`chunks`, `courses`, `sources`, `ingest_runs`) — upsert only new/changed `sha256` chunks and delete removed chunks.
  - A7: Atlas Automated Embedding (`autoEmbed` with `voyage-4`) automatically embeds `chunks.text` inside MongoDB Atlas.
"""

import asyncio
import base64
import hashlib
import io
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorDatabase
from pypdf import PdfReader

from db import VOYAGE_MULTIMODAL_MODEL, ensure_indexes, get_db, get_modulestore_db

load_dotenv()

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_BASE_URL = os.getenv("VOYAGE_BASE_URL", "https://ai.mongodb.com/v1").rstrip("/")

logger = logging.getLogger(__name__)

SKIPPED_BLOCK_TYPES = {
    "problem",
    "video",
    "pdf",
    "scorm",
    "scorm_v2",
    "cmi5",
    "h5pxblock",
    "chatgptxblock",
    "lti",
    "lti_consumer",
    "discussion",
    "poll",
    "survey",
    "non_mandatory_survey",
    "drag-and-drop-v2",
    "openassessment",
}
ALLOWED_BLOCK_TYPES = {"html", "about", "gridfs_pdf"}

# Target ~300-400 tokens (~220-320 words) per chunk when splitting long sections
MAX_WORDS_PER_CHUNK = 300

# Default real WHO courses in `openedx_ulmo` to ingest first
DEFAULT_OPENEDX_ULMO_COURSES = [
    {"org": "WHOA", "course": "H0118EN", "run": "Q1_2025"},   # (UC-513) WHO Good Practices for Clinical Trial Design and Implementation (269 html blocks)
    {"org": "WHOA", "course": "HQ_SPTB_EN", "run": "2025"},  # Social protection for people affected by TB - programmatic considerations (56 html blocks)
    {"org": "WHOA", "course": "0006_BEC_EN", "run": "2026"}, # Basic Emergency Care (27 html blocks)
    {"org": "WHOA", "course": "H0140EN", "run": "2025_Q4"},  # (H5P) Ethics and Review of Interventional Clinical Research Part 2 (42 html blocks)
    {"org": "WHOA", "course": "H0117EN", "run": "2025_Q1"},  # (H5p) Global Scales for Early Development (GSED): Short Form (68 html blocks)
    {"org": "WHOA", "course": "bbt", "run": "bbt"},          # Bleeding after birth – prevention, diagnosis and treatment of postpartum haemorrhage
]


# ---------------------------------------------------------------------------
# Realistic Open edX Seed Courses (WHO Academy PoC)
# ---------------------------------------------------------------------------

SAMPLE_OPEN_EDX_COURSES: List[Dict[str, Any]] = [
    {
        "course_id": "course-v1:WHOA+IHH+2026",
        "short_code": "IHH2026",
        "title": "Hand Hygiene Essentials",
        "published_branch": "baae3ba76aae3ba9",
        "about_html": """
            <h2>Overview and Clinical Protocols</h2>
            <p>Overview and clinical protocols for WHO hand hygiene standards in health-care settings.
            This course trains healthcare workers on the My 5 Moments for Hand Hygiene framework, proper
            alcohol-based handrub (ABHR) technique, handwashing with soap and water, and appropriate medical glove use.</p>
        """,
        "blocks": [
            {
                "block_id": "html_1a01b2",
                "unit_code": "u11",
                "block_type": "html",
                "section": "1. The 5 Moments for Hand Hygiene",
                "unit_title": "1.1 Understanding the 5 Moments",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u11",
                "html": """
                    <h3>The WHO My 5 Moments for Hand Hygiene</h3>
                    <p>The WHO Multimodal Hand Hygiene Improvement Strategy defines five critical moments when health-care workers must perform hand hygiene to prevent health care-associated infections (HAIs) and curb antimicrobial resistance:</p>
                    <ul>
                        <li><strong>Moment 1 — Before touching a patient:</strong> Clean your hands before approaching and touching a patient to protect the patient against harmful germs carried on your hands.</li>
                        <li><strong>Moment 2 — Before clean/aseptic procedures:</strong> Clean your hands immediately before performing any clean or aseptic task (such as catheter insertion, wound dressing, or preparing medication) to prevent germs—including the patient's own—from entering their body.</li>
                        <li><strong>Moment 3 — After body fluid exposure risk:</strong> Clean your hands immediately after an exposure risk to body fluids (and after glove removal) to protect yourself and the health-care environment from harmful patient germs.</li>
                        <li><strong>Moment 4 — After touching a patient:</strong> Clean your hands when leaving the patient's side after touching the patient and their immediate surroundings.</li>
                        <li><strong>Moment 5 — After touching patient surroundings:</strong> Clean your hands after touching any object or furniture in the patient's immediate surroundings when leaving—even if the patient was not touched.</li>
                    </ul>
                    <p><img src="/assets/gridfs/who-5-moments-hand-hygiene-diagram.png" alt="WHO My 5 Moments for Hand Hygiene clinical diagram showing the 5 critical hand hygiene indications around the patient zone" /></p>
                """,
            },
            {
                "block_id": "html_1a02c3",
                "unit_code": "u12",
                "block_type": "html",
                "section": "1. The 5 Moments for Hand Hygiene",
                "unit_title": "1.2 Alcohol-Based Handrub (ABHR) vs Soap and Water",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u12",
                "html": """
                    <h3>Alcohol-Based Handrub (ABHR) Technique and Duration</h3>
                    <p>Alcohol-based handrub (ABHR) is the preferred mean for routine hygienic hand antisepsis in all clinical situations when hands are not visibly dirty or soiled with blood or other body fluids. ABHR acts faster, has broader microbiological spectrum activity, and is better tolerated by skin than soap and water.</p>
                    <p><strong>ABHR Duration:</strong> Apply a palmful of alcohol-based formulation in a cupped hand and rub all surfaces of the hands for <strong>20 to 30 seconds</strong> until hands are completely dry.</p>
                    <h3>When to Wash Hands with Soap and Water</h3>
                    <p>Wash your hands with soap and water whenever hands are visibly dirty or visibly soiled with blood or other body fluids, or after using the toilet. Washing with soap and water is also required when exposure to potential spore-forming pathogens is strongly suspected or proven, including outbreaks of <em>Clostridioides difficile</em> (C. difficile).</p>
                    <p><strong>Handwashing Duration:</strong> Wet hands with water, apply soap, rub all surfaces thoroughly, rinse, and dry with a single-use towel. The entire handwashing procedure with soap and water takes <strong>40 to 60 seconds</strong>.</p>
                """,
            },
            {
                "block_id": "video_9911",
                "unit_code": "u13",
                "block_type": "video",
                "section": "1. The 5 Moments for Hand Hygiene",
                "unit_title": "1.3 Demonstration Video (Non-Text Block)",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u13",
                "html": "<p>Video transcript metadata that must be skipped by Flow A filter.</p>",
            },
            {
                "block_id": "html_7f3a9c",
                "unit_code": "u21",
                "block_type": "html",
                "section": "2. Gloves",
                "unit_title": "2.1 Gloves and hand hygiene",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u21",
                "html": """
                    <h3>Do Gloves Replace Hand Hygiene?</h3>
                    <p>Gloves do not replace hand hygiene. Wearing gloves does not replace the need for cleaning your hands. Medical gloves are a barrier precaution, but they can still become contaminated during care or develop microscopic perforations, and hands can easily be contaminated during glove removal.</p>
                    <p>Therefore, you must always clean your hands <strong>before putting gloves on</strong> (for example before an aseptic task or anticipated contact with body fluids) and <strong>immediately after removing gloves</strong>.</p>
                    <h3>The Glove Pyramid and Single-Use Rule</h3>
                    <p>Never wear the same pair of gloves for the care of more than one patient. Change gloves when moving from a contaminated body site to a clean body site on the same patient. Do not wash or apply alcohol-based handrub to gloved hands—always remove gloves, discard them safely, and perform hand hygiene on bare hands.</p>
                """,
            },
            {
                "block_id": "problem_4410",
                "unit_code": "u22",
                "block_type": "problem",
                "section": "2. Gloves",
                "unit_title": "2.2 Graded Quiz on Glove Use",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u22",
                "html": "<p>Graded problem block that must be skipped during RAG ingestion.</p>",
            },
            {
                "block_id": "html_8b4d1e",
                "unit_code": "u31",
                "block_type": "html",
                "section": "3. Skin Care and Surgical Hand Preparation",
                "unit_title": "3.1 Fingernails, Jewelry, and Skin Integrity",
                "url": "/learning/course/course-v1:WHOA+IHH+2026/u31",
                "html": """
                    <h3>Artificial Fingernails and Hand Jewelry</h3>
                    <p>Health-care workers must not wear artificial fingernails or extenders when having direct contact with patients, as artificial nails harbor higher concentrations of Gram-negative bacilli and yeasts. Natural fingernails should be kept short (tips less than 0.5 cm long).</p>
                    <p>Rings and wrist jewelry substantially increase bacterial colonization on skin and can perforate medical gloves. Remove rings, watches, and bracelets before starting clinical care and before surgical hand preparation.</p>
                """,
            },
        ],
    },
    {
        "course_id": "course-v1:WHOA+MAT+2026",
        "short_code": "MAT2026",
        "title": "Maternal Health & Postpartum Care",
        "published_branch": "c77f91a200d1e442",
        "about_html": """
            <h2>WHO Maternal & Peripartum Clinical Guidelines</h2>
            <p>Evidence-based WHO clinical protocols for active management of the third stage of labour (AMTSL),
            early detection and treatment of postpartum haemorrhage (PPH) using the E-MOTIVE bundle, and essential newborn care.</p>
        """,
        "blocks": [
            {
                "block_id": "html_m101",
                "unit_code": "u11",
                "block_type": "html",
                "section": "1. Prevention of Postpartum Haemorrhage",
                "unit_title": "1.1 Active Management of Third Stage of Labour (AMTSL)",
                "url": "/learning/course/course-v1:WHOA+MAT+2026/u11",
                "html": """
                    <h3>First-Line Uterotonic for PPH Prevention</h3>
                    <p>The WHO recommends the use of uterotonics for the prevention of postpartum haemorrhage (PPH) during the third stage of labour for all births. <strong>Oxytocin (10 IU, intramuscular or intravenous)</strong> is the recommended first-line uterotonic drug for the prevention of PPH in vaginal and caesarean births.</p>
                    <p>In settings where oxytocin is unavailable or its quality cannot be guaranteed (for example due to cold-chain interruptions), heat-stable carbetocin, ergometrine/methylergometrine, or oral misoprostol (400 mcg to 600 mcg) are recommended alternatives.</p>
                """,
            },
            {
                "block_id": "html_m102",
                "unit_code": "u12",
                "block_type": "html",
                "section": "1. Prevention of Postpartum Haemorrhage",
                "unit_title": "1.2 The E-MOTIVE First-Response Bundle and Tranexamic Acid",
                "url": "/learning/course/course-v1:WHOA+MAT+2026/u12",
                "html": """
                    <h3>E-MOTIVE Bundle for Early PPH Detection and Treatment</h3>
                    <p>Objective blood-loss measurement using a calibrated obstetric drape enables early detection of postpartum haemorrhage (blood loss >= 500 mL, or >= 300 mL with abnormal vital signs). Once triggered, the <strong>MOTIVE</strong> first-response bundle should be initiated within 15 minutes:</p>
                    <ul>
                        <li><strong>M — Massage:</strong> Uterine massage to stimulate contractions.</li>
                        <li><strong>O — Oxytocic drugs:</strong> Administer therapeutic uterotonics immediately.</li>
                        <li><strong>T — Tranexamic acid (TXA):</strong> Administer 1 g intravenous tranexamic acid over 10 minutes within 3 hours of birth.</li>
                        <li><strong>I — IV fluids:</strong> Isotonic crystalloid infusion.</li>
                        <li><strong>V & E — Vaginal examination & Escalation:</strong> Examine the genital tract for trauma/retained placenta and escalate promptly if bleeding continues.</li>
                    </ul>
                """,
            },
        ],
    },
    {
        # Un-enrolled course for Learner_1042 — used to verify tenant pre-filtering security rule!
        "course_id": "course-v1:WHOA+BIO+2026",
        "short_code": "BIO2026",
        "title": "Laboratory Biosafety & Biosecurity Level 4",
        "published_branch": "f009e1123a884bc1",
        "about_html": """
            <h2>Maximum Containment Laboratory Protocols (BSL-4)</h2>
            <p>Restricted training on positive-pressure personnel suits, HEPA airlock decontamination showers,
            and Ebola/Marburg filovirus specimen containment in BSL-4 facilities.</p>
        """,
        "blocks": [
            {
                "block_id": "html_b101",
                "unit_code": "u11",
                "block_type": "html",
                "section": "1. BSL-4 Suit Integrity",
                "unit_title": "1.1 Positive-Pressure Suit Chemical Shower Protocol",
                "url": "/learning/course/course-v1:WHOA+BIO+2026/u11",
                "html": """
                    <h3>BSL-4 Chemical Disinfectant Shower</h3>
                    <p>Before exiting a Biosafety Level 4 (BSL-4) positive-pressure suit containment zone after handling filoviruses such as Ebola or Marburg virus, personnel must undergo a mandatory 5-minute chemical disinfectant shower using 5% Micro-Chem Plus followed by a water rinse and suit pressure-decay check.</p>
                """,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# HTML Cleaning & Heading-Aware Chunking (Steps A3, A4, A5)
# ---------------------------------------------------------------------------

def compute_sha256(text: str) -> str:
    """Compute hex SHA-256 digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Decorative UI banners/icons in Open edX HTML blocks that should not be indexed as clinical figures
DECORATIVE_IMAGE_SUBSTRINGS = (
    "page_band",
    "sskxupct50cjbklx",
    "icon-",
    "back-next-arrows",
    "previous-next-buttons",
    "next_prev",
    "course-banner",
    "character_standing",
    "topic1_intro_img",
    "topic2_intro_img",
    "topic3_intro_img",
    "topic4_intro_img",
    "topic5_intro_img",
)

GENERIC_ALT_STRINGS = {
    "",
    "image",
    "more",
    "icon",
    "decorative item",
    "decorative items",
    "card image 1",
    "card image 2",
    "card image 3",
    "card image 4",
    "card image 5",
}

KNOWN_CLINICAL_DIAGRAM_FILES = (
    "chart_p4",
    "hiap-diagram",
    "testwho-ucn-tb",
    "9789240067530",
    "principle_banner_",
    "m01_cover_page",
    "cover_page_m02",
    "module_cover_page",
    "m04_cover_page",
    "module9_cover_page",
    "who-5-moments",
)

# Compact 1x1 PNG fallback data URI used when embedding seed/sandbox HTML images without GridFS binary
SEED_DIAGRAM_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def extract_html_images_from_raw_html(
    raw_html: str,
    gridfs_image_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract substantive clinical diagrams, charts, and figure `<img>` tags from an Open edX HTML block,
    skipping purely decorative UI dividers/icons and resolving matching GridFS asset IDs.
    """
    if not raw_html or "<img" not in raw_html.lower():
        return []

    soup = BeautifulSoup(raw_html, "html.parser")
    extracted: List[Dict[str, Any]] = []
    seen_keys = set()

    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        alt = re.sub(r"\s+", " ", (img.get("alt") or img.get("title") or "").strip())
        alt_lower = alt.lower()

        if src.startswith("data:image/"):
            if alt_lower in GENERIC_ALT_STRINGS:
                continue
            fname = "inline_base64_image.png"
            dedup_key = f"data:{alt_lower}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            extracted.append(
                {
                    "filename": fname,
                    "alt": alt,
                    "src": src[:64] + "...",
                    "url": src,
                    "gridfs_id": None,
                    "thumbnail_gridfs_id": None,
                    "content_type": src.split(";")[0].replace("data:", "") or "image/png",
                }
            )
            continue

        filename = unquote(src.split("?")[0].split("@")[-1].split("/")[-1]).strip()
        fname_lower = filename.lower()
        if not filename or fname_lower.endswith(".svg"):
            continue
        if any(pat in fname_lower for pat in DECORATIVE_IMAGE_SUBSTRINGS):
            continue

        is_known_diagram = any(k in fname_lower for k in KNOWN_CLINICAL_DIAGRAM_FILES)
        if alt_lower in GENERIC_ALT_STRINGS and not is_known_diagram:
            continue

        dedup_key = fname_lower or alt_lower
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        g_info = (gridfs_image_map or {}).get(filename) or (gridfs_image_map or {}).get(fname_lower) or {}
        gridfs_id = g_info.get("gridfs_id")
        thumb_id = g_info.get("thumbnail_gridfs_id")
        content_type = g_info.get("content_type") or ("image/jpeg" if fname_lower.endswith((".jpg", ".jpeg")) else "image/png")

        if gridfs_id:
            asset_url = f"/assets/gridfs/{gridfs_id}"
        elif src.startswith("/assets/gridfs/"):
            asset_url = src
        elif src.startswith("http"):
            asset_url = src
        else:
            asset_url = f"/assets/gridfs/{filename}"

        effective_alt = alt if alt_lower not in GENERIC_ALT_STRINGS else filename.replace("_", " ").rsplit(".", 1)[0]
        extracted.append(
            {
                "filename": filename,
                "alt": effective_alt,
                "src": src,
                "url": asset_url,
                "gridfs_id": str(gridfs_id) if gridfs_id else None,
                "thumbnail_gridfs_id": str(thumb_id) if thumb_id else None,
                "content_type": content_type,
            }
        )

    return extracted


def clean_html_preserving_headings(
    raw_html: str,
    gridfs_image_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    """
    Step A3 & A4: Strip HTML tags (`<h3>`, `<p>`, `<strong>`, `<ul>`, `<li>`) and inline CSS blocks
    while splitting content into logical sections at `<h1>`/`<h2>`/`<h3>`/`<h4>` headings.
    Preserves substantive `<img alt="..." src="...">` clinical diagrams as inline `[Embedded HTML Image ...]`
    markers so both image-only HTML blocks (e.g. `H0118EN` Principles 1-5) and inline clinical charts are indexed.
    Returns a list of `{"heading": str | None, "body": str}` segments.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove script/style/svg/noscript tags if any
    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()

    # Convert substantive HTML <img> tags into inline text markers before stripping tags
    valid_imgs = extract_html_images_from_raw_html(raw_html, gridfs_image_map=gridfs_image_map)
    valid_by_fname = {im["filename"].lower(): im for im in valid_imgs}
    for img_tag in soup.find_all("img"):
        src = (img_tag.get("src") or "").strip()
        alt = re.sub(r"\s+", " ", (img_tag.get("alt") or img_tag.get("title") or "").strip())
        fname = "inline_base64_image.png" if src.startswith("data:image/") else unquote(src.split("?")[0].split("@")[-1].split("/")[-1]).strip()
        matched = valid_by_fname.get(fname.lower())
        if matched:
            marker = f" [Embedded HTML Image ({matched['filename']}): {matched['alt']}] "
            img_tag.replace_with(marker)
        elif alt and alt.lower() not in GENERIC_ALT_STRINGS and not any(p in fname.lower() for p in DECORATIVE_IMAGE_SUBSTRINGS):
            marker = f" [Embedded HTML Image ({fname or 'diagram'}): {alt}] "
            img_tag.replace_with(marker)

    segments: List[Dict[str, str]] = []
    current_heading: Optional[str] = None
    current_lines: List[str] = []

    heading_tags = {"h1", "h2", "h3", "h4"}
    block_tags = {"p", "li", "div", "blockquote"}

    for elem in soup.find_all(heading_tags | block_tags):
        # Skip nested block tags to avoid duplicating text
        if elem.name in block_tags and elem.find_parent(block_tags):
            continue

        text = re.sub(r"\s+", " ", elem.get_text(separator=" ", strip=True)).strip()
        # Strip inline raw CSS rules that occasionally appear inside poorly formatted Open edX HTML blocks
        text = re.sub(r"\.[a-zA-Z0-9_-]+\s*\{[^}]*\}", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        if elem.name in heading_tags:
            if current_lines:
                segments.append(
                    {
                        "heading": current_heading or "",
                        "body": " ".join(current_lines).strip(),
                    }
                )
                current_lines = []
            current_heading = text
        else:
            if elem.name == "li":
                current_lines.append(f"- {text}")
            else:
                current_lines.append(text)

    if current_lines:
        segments.append(
            {
                "heading": current_heading or "",
                "body": " ".join(current_lines).strip(),
            }
        )

    # Fallback if HTML had no standard heading/paragraph tags
    if not segments:
        plain = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        if plain:
            segments.append({"heading": "", "body": plain})

    return segments


async def embed_chunk_images_multimodal(
    chunk_doc: Dict[str, Any],
    modulestore_db: Optional[AsyncIOMotorDatabase] = None,
) -> Optional[List[float]]:
    """
    Generate a 1024-dimension multimodal vector (`image_embedding`) for a chunk containing HTML `<img>` diagrams
    by calling Voyage AI `voyage-multimodal-3` (`POST {VOYAGE_BASE_URL}/multimodalembeddings`) on the interleaved
    chunk text + binary image bytes from Open edX GridFS (`openedx_ulmo.fs.chunks`).
    """
    images = chunk_doc.get("images") or []
    if not images or not VOYAGE_API_KEY or VOYAGE_API_KEY.startswith("pa-your-"):
        return None

    content_items: List[Dict[str, str]] = [
        {"type": "text", "text": chunk_doc.get("text", "")[:2000]}
    ]

    # Attach the primary diagram binary from GridFS (preferring thumbnail if full PNG > 450 KB for fast upload)
    primary_img = images[0]
    data_uri: Optional[str] = None

    raw_url = primary_img.get("url") or ""
    if raw_url.startswith("data:image/"):
        data_uri = raw_url
    elif modulestore_db is not None:
        target_fid = primary_img.get("gridfs_id")
        thumb_fid = primary_img.get("thumbnail_gridfs_id")
        chosen_fid = target_fid
        chosen_mime = primary_img.get("content_type") or "image/png"
        try:
            if target_fid:
                fdoc = await modulestore_db["fs.files"].find_one({"_id": target_fid}, {"length": 1, "contentType": 1})
                if fdoc and fdoc.get("length", 0) > 450_000 and thumb_fid:
                    chosen_fid = thumb_fid
                    chosen_mime = "image/jpeg"
                elif fdoc and fdoc.get("contentType"):
                    chosen_mime = fdoc["contentType"]
            if chosen_fid:
                c_cursor = modulestore_db["fs.chunks"].find({"files_id": chosen_fid}).sort("n", 1)
                raw_chunks = await c_cursor.to_list(150)
                raw_bytes = b"".join(c.get("data", b"") for c in raw_chunks)
                if raw_bytes:
                    b64_str = base64.b64encode(raw_bytes).decode("ascii")
                    data_uri = f"data:{chosen_mime};base64,{b64_str}"
        except Exception as exc:
            logger.warning("Could not load GridFS image bytes for %s (%s)", chosen_fid, exc)

    if not data_uri:
        data_uri = SEED_DIAGRAM_PNG_DATA_URI

    content_items.append({"type": "image_base64", "image_base64": data_uri})

    try:
        async with httpx.AsyncClient(timeout=25.0) as http_client:
            resp = await http_client.post(
                f"{VOYAGE_BASE_URL}/multimodalembeddings",
                headers={
                    "Authorization": f"Bearer {VOYAGE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VOYAGE_MULTIMODAL_MODEL,
                    "inputs": [{"content": content_items}],
                    "input_type": "document",
                },
            )
            resp.raise_for_status()
            body = resp.json()
            vec = (body.get("data") or [{}])[0].get("embedding")
            if isinstance(vec, list) and len(vec) == 1024:
                return vec
    except Exception as exc:
        logger.warning("Voyage multimodal embedding call failed for chunk %s (%s)", chunk_doc.get("_id"), exc)

    return None


def build_chunks_for_block(
    course_id: str,
    short_code: str,
    course_title: str,
    block: Dict[str, Any],
    now_iso: str,
    gridfs_image_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Step A5: Cut into 300-400 token chunks at headings, prepend the course and section
    breadcrumb (`"Course Title > Section > Unit"`), keep short blocks as one chunk,
    attach extracted HTML `images` metadata, and generate a deterministic `_id` (`IHH2026-u21-c01`) and `sha256` hash.
    """
    unit_code = block["unit_code"]
    section_name = block["section"]
    unit_title = block["unit_title"]
    breadcrumb = f"{course_title} > {section_name} > {unit_title}"

    raw_html = block.get("html", "")
    block_images = block.get("images")
    if block_images is None:
        block_images = extract_html_images_from_raw_html(raw_html, gridfs_image_map=gridfs_image_map)

    segments = clean_html_preserving_headings(raw_html, gridfs_image_map=gridfs_image_map)
    chunks: List[Dict[str, Any]] = []
    chunk_idx = 1

    # Combine short segments if together they stay well within 300-400 tokens (~MAX_WORDS_PER_CHUNK words)
    combined_parts: List[str] = []
    combined_words = 0

    def flush_chunk(body_text: str) -> None:
        nonlocal chunk_idx
        full_text = f"{breadcrumb}\n{body_text.strip()}"
        chunk_id = f"{short_code}-{unit_code}-c{chunk_idx:02d}"
        chunk_doc: Dict[str, Any] = {
            "_id": chunk_id,
            "course_id": course_id,
            "unit_id": block["block_id"],
            "sha256": compute_sha256(full_text),
            "text": full_text,
            "url": block["url"],
            "section_title": unit_title,
            "is_active": True,
            "updated_at": now_iso,
        }
        if block_images:
            chunk_doc["images"] = block_images
        chunks.append(chunk_doc)
        chunk_idx += 1

    for seg in segments:
        seg_text = f"{seg['heading']}: {seg['body']}" if seg["heading"] else seg["body"]
        seg_words = len(seg_text.split())

        if combined_words > 0 and (combined_words + seg_words) > MAX_WORDS_PER_CHUNK:
            flush_chunk("\n".join(combined_parts))
            combined_parts = [seg_text]
            combined_words = seg_words
        else:
            combined_parts.append(seg_text)
            combined_words += seg_words

    if combined_parts:
        flush_chunk("\n".join(combined_parts))

    return chunks


# ---------------------------------------------------------------------------
# Flow A Execution (`ingest_course` and `run_ingestion`)
# ---------------------------------------------------------------------------

async def ingest_course(
    course_payload: Dict[str, Any],
    db: Optional[AsyncIOMotorDatabase] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Execute Flow A (Steps A1 through A7) for a single Open edX course payload.
    """
    if db is None:
        db = get_db()

    start_time = time.perf_counter()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    course_id = course_payload["course_id"]
    short_code = course_payload.get("short_code") or course_id.split("+")[1] + course_id.split("+")[-1]
    course_title = course_payload["title"]
    published_branch = course_payload["published_branch"]
    errors: List[str] = []

    # Step A1 & A2: Check if published_branch changed vs `genai_search.courses`
    existing_course = await db["courses"].find_one({"_id": course_id})
    has_html_img_blocks = any(
        "<img" in (b.get("html") or "").lower()
        for b in course_payload.get("blocks", [])
    )
    existing_img_embedded_count = (
        await db["chunks"].count_documents(
            {"course_id": course_id, "image_embedding": {"$exists": True}}
        )
        if has_html_img_blocks
        else 1
    )
    if (
        existing_course
        and existing_course.get("published_branch") == published_branch
        and existing_img_embedded_count > 0
        and not force
    ):
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "course_id": course_id,
            "published_branch": published_branch,
            "status": "skipped_unchanged_branch",
            "duration_ms": duration_ms,
        }

    # Step A3, A4, A5: Extract & filter HTML blocks, build chunks, track source block hashes
    desired_chunks: Dict[str, Dict[str, Any]] = {}
    sources_updated = 0
    skipped_blocks: List[str] = []
    gridfs_image_map: Dict[str, Dict[str, Any]] = course_payload.get("gridfs_image_map") or {}
    modulestore_db = get_modulestore_db()

    for block in course_payload.get("blocks", []):
        b_type = block.get("block_type", "html").lower()
        b_id = block["block_id"]

        # Step A4: Skip non-text blocks (problem, video, pdf, scorm, chatgptxblock, lti)
        if b_type in SKIPPED_BLOCK_TYPES or b_type not in ALLOWED_BLOCK_TYPES:
            skipped_blocks.append(f"{b_id} ({b_type})")
            continue

        raw_html = block.get("html", "")
        block_hash = compute_sha256(raw_html)
        source_doc_id = f"{course_id}:{b_id}"

        existing_source = await db["sources"].find_one({"_id": source_doc_id})
        if not existing_source or existing_source.get("sha256") != block_hash:
            await db["sources"].update_one(
                {"_id": source_doc_id},
                {
                    "$set": {
                        "course_id": course_id,
                        "block_id": b_id,
                        "sha256": block_hash,
                        "updated_at": now_iso,
                    }
                },
                upsert=True,
            )
            sources_updated += 1

        block_chunks = build_chunks_for_block(
            course_id=course_id,
            short_code=short_code,
            course_title=course_title,
            block=block,
            now_iso=now_iso,
            gridfs_image_map=gridfs_image_map,
        )
        for ch in block_chunks:
            desired_chunks[ch["_id"]] = ch

    # Step A6: Delta Write to Atlas (`genai_search.chunks`)
    existing_chunks_cursor = db["chunks"].find(
        {"course_id": course_id},
        {"_id": 1, "sha256": 1, "image_embedding": 1, "image_embed_model": 1},
    )
    existing_chunks_docs: Dict[str, Dict[str, Any]] = {
        doc["_id"]: doc
        async for doc in existing_chunks_cursor
    }
    existing_chunks_map: Dict[str, str] = {
        cid: doc.get("sha256", "")
        for cid, doc in existing_chunks_docs.items()
    }

    chunks_new = 0
    chunks_changed = 0
    chunks_unchanged = 0
    chunks_deleted = 0
    chunks_with_images = 0

    # Upsert only new or changed chunks (Atlas autoEmbed triggers automatically on text changes!)
    # For chunks containing substantive HTML `images`, also compute or preserve `image_embedding` (1024d voyage-multimodal-3).
    for chunk_id, chunk_doc in desired_chunks.items():
        has_images = bool(chunk_doc.get("images"))
        if has_images:
            chunks_with_images += 1

        prev_doc = existing_chunks_docs.get(chunk_id)
        prev_vec = prev_doc.get("image_embedding") if prev_doc else None
        needs_multimodal_embed = has_images and (
            not prev_doc
            or existing_chunks_map.get(chunk_id) != chunk_doc["sha256"]
            or not prev_vec
        )

        if needs_multimodal_embed:
            mm_vec = await embed_chunk_images_multimodal(
                chunk_doc,
                modulestore_db=modulestore_db,
            )
            if mm_vec:
                chunk_doc["image_embedding"] = mm_vec
                chunk_doc["image_embed_model"] = VOYAGE_MULTIMODAL_MODEL
        elif has_images and prev_vec:
            chunk_doc["image_embedding"] = prev_vec
            chunk_doc["image_embed_model"] = prev_doc.get("image_embed_model", VOYAGE_MULTIMODAL_MODEL)

        if chunk_id not in existing_chunks_map:
            await db["chunks"].replace_one({"_id": chunk_id}, chunk_doc, upsert=True)
            chunks_new += 1
        elif existing_chunks_map[chunk_id] != chunk_doc["sha256"] or needs_multimodal_embed:
            await db["chunks"].replace_one({"_id": chunk_id}, chunk_doc, upsert=True)
            chunks_changed += 1
        else:
            chunks_unchanged += 1

    # Delete chunks that no longer exist in the published course outline
    stale_chunk_ids = set(existing_chunks_map.keys()) - set(desired_chunks.keys())
    if stale_chunk_ids:
        del_result = await db["chunks"].delete_many({"_id": {"$in": list(stale_chunk_ids)}})
        chunks_deleted = del_result.deleted_count

    # Upsert course card in `genai_search.courses`
    about_segments = clean_html_preserving_headings(course_payload.get("about_html", ""))
    about_text = " ".join(seg["body"] for seg in about_segments).strip()
    course_doc = {
        "_id": course_id,
        "course_id": course_id,
        "title": course_title,
        "published_branch": published_branch,
        "about_text": about_text,
        "is_active": True,
        "updated_at": now_iso,
    }
    await db["courses"].replace_one({"_id": course_id}, course_doc, upsert=True)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Record job metrics in `genai_search.ingest_runs`
    ingest_run_doc = {
        "course_id": course_id,
        "published_branch": published_branch,
        "chunks_total": len(desired_chunks),
        "chunks_new": chunks_new,
        "chunks_changed": chunks_changed,
        "chunks_unchanged": chunks_unchanged,
        "chunks_deleted": chunks_deleted,
        "chunks_with_images": chunks_with_images,
        "sources_updated": sources_updated,
        "skipped_non_text_blocks": skipped_blocks,
        "duration_ms": duration_ms,
        "errors": errors,
        "created_at": now_iso,
    }
    await db["ingest_runs"].insert_one(ingest_run_doc)
    ingest_run_doc.pop("_id", None)

    return ingest_run_doc


# ---------------------------------------------------------------------------
# Open edX Split Modulestore (`openedx_ulmo`) Live Extractor
# ---------------------------------------------------------------------------

async def extract_course_payload_from_modulestore(
    av_doc: Dict[str, Any],
    modulestore_db: Optional[AsyncIOMotorDatabase] = None,
) -> Optional[Dict[str, Any]]:
    """
    Read a real Open edX course from `openedx_ulmo` (`modulestore.active_versions`,
    `modulestore.structures`, and `modulestore.definitions`) and convert its tree
    (`course` -> `chapter` -> `sequential` -> `vertical` -> leaf `html` / non-text blocks)
    into the standardized Flow A `course_payload` dictionary.
    """
    if modulestore_db is None:
        modulestore_db = get_modulestore_db()

    org = av_doc.get("org", "WHOA")
    course_num = av_doc.get("course", "")
    run = av_doc.get("run", "")
    course_id = f"course-v1:{org}+{course_num}+{run}"
    short_code = re.sub(r"[^A-Za-z0-9]", "", f"{course_num}{run}")[:16]

    versions = av_doc.get("versions") or {}
    pub_branch_oid = versions.get("published-branch")
    if not pub_branch_oid:
        return None

    struct_doc = await modulestore_db["modulestore.structures"].find_one({"_id": pub_branch_oid})
    if not struct_doc or not struct_doc.get("blocks"):
        return None

    blocks_by_id: Dict[str, Dict[str, Any]] = {}
    def_ids_to_fetch = set()
    course_block: Optional[Dict[str, Any]] = None

    for b in struct_doc["blocks"]:
        b_id = b.get("block_id")
        if b_id:
            blocks_by_id[b_id] = b
        if b.get("block_type") == "course":
            course_block = b
        if b.get("block_type") in ("html", "about") and b.get("definition"):
            def_ids_to_fetch.add(b["definition"])

    if not course_block:
        return None

    course_fields = course_block.get("fields") or {}
    course_title = course_fields.get("display_name") or f"{org} {course_num}"

    # Batch-fetch all HTML & About definitions for this course in a single query
    defs_cursor = modulestore_db["modulestore.definitions"].find(
        {"_id": {"$in": list(def_ids_to_fetch)}},
        {"_id": 1, "fields.data": 1},
    )
    defs_map: Dict[Any, str] = {
        d["_id"]: (d.get("fields") or {}).get("data", "")
        async for d in defs_cursor
    }

    # Extract `overview` about block if present
    about_html = ""
    overview_block = blocks_by_id.get("overview")
    if overview_block and overview_block.get("definition") in defs_map:
        about_html = defs_map[overview_block["definition"]]

    extracted_blocks: List[Dict[str, Any]] = []
    visited_block_ids = set()

    # Traverse `course` -> `chapter` -> `sequential` -> `vertical` -> leaf blocks
    for ch_ref in course_fields.get("children") or []:
        if not isinstance(ch_ref, list) or len(ch_ref) < 2:
            continue
        ch_block = blocks_by_id.get(ch_ref[1])
        if not ch_block:
            continue
        ch_title = (ch_block.get("fields") or {}).get("display_name") or ch_block["block_id"]

        for seq_ref in (ch_block.get("fields") or {}).get("children") or []:
            if not isinstance(seq_ref, list) or len(seq_ref) < 2:
                continue
            seq_block = blocks_by_id.get(seq_ref[1])
            if not seq_block:
                continue
            seq_title = (seq_block.get("fields") or {}).get("display_name") or seq_block["block_id"]
            section_breadcrumb = f"{ch_title} > {seq_title}" if seq_title != ch_title else ch_title

            for vert_ref in (seq_block.get("fields") or {}).get("children") or []:
                if not isinstance(vert_ref, list) or len(vert_ref) < 2:
                    continue
                vert_block = blocks_by_id.get(vert_ref[1])
                if not vert_block:
                    continue
                vert_title = (vert_block.get("fields") or {}).get("display_name") or vert_block["block_id"]

                for leaf_ref in (vert_block.get("fields") or {}).get("children") or []:
                    if not isinstance(leaf_ref, list) or len(leaf_ref) < 2:
                        continue
                    leaf_block = blocks_by_id.get(leaf_ref[1])
                    if not leaf_block:
                        continue

                    leaf_id = str(leaf_block["block_id"])
                    if leaf_id in visited_block_ids:
                        continue
                    visited_block_ids.add(leaf_id)

                    b_type = str(leaf_block.get("block_type", "html")).lower()
                    raw_html = defs_map.get(leaf_block.get("definition"), "") if b_type == "html" else ""
                    if b_type == "html" and not raw_html.strip():
                        continue

                    unit_code = leaf_id[:10]
                    extracted_blocks.append(
                        {
                            "block_id": leaf_id,
                            "unit_code": unit_code,
                            "block_type": b_type,
                            "section": section_breadcrumb,
                            "unit_title": vert_title,
                            "url": f"/learning/course/{course_id}/{vert_block['block_id']}",
                            "html": raw_html,
                        }
                    )

    # Also extract any PDF course assets stored in Open edX GridFS (`fs.files` + `fs.chunks`)
    pdf_blocks = await extract_pdf_blocks_from_gridfs(
        org=org,
        course_num=course_num,
        run=run,
        course_id=course_id,
        modulestore_db=modulestore_db,
    )
    extracted_blocks.extend(pdf_blocks)

    # Build GridFS image lookup map (`openedx_ulmo.fs.files`) for HTML `<img>` asset resolution
    gridfs_image_map: Dict[str, Dict[str, Any]] = {}
    try:
        img_cursor = modulestore_db["fs.files"].find(
            {
                "contentType": {"$regex": "^image/"},
                "content_son.org": org,
                "content_son.course": course_num,
                "content_son.run": run,
            },
            {"_id": 1, "contentType": 1, "content_son": 1},
        )
        img_docs = await img_cursor.to_list(1000)
        assets_by_name: Dict[str, Dict[str, Any]] = {}
        thumbs_by_stem: Dict[str, str] = {}
        for idoc in img_docs:
            fid = str(idoc["_id"])
            cson = idoc.get("content_son") or {}
            fname = str(cson.get("name") or fid.split("@")[-1])
            ctype = str(idoc.get("contentType") or "image/png")
            cat = str(cson.get("category") or "asset")
            if cat == "thumbnail":
                stem = re.sub(r"-jpeg-\d+x\d+\.jpg$", "", fname, flags=re.IGNORECASE)
                thumbs_by_stem[stem.lower()] = fid
            else:
                assets_by_name[fname] = {
                    "gridfs_id": fid,
                    "content_type": ctype,
                }
        for fname, meta in assets_by_name.items():
            stem_key = fname.rsplit(".", 1)[0].lower()
            if stem_key in thumbs_by_stem:
                meta["thumbnail_gridfs_id"] = thumbs_by_stem[stem_key]
            gridfs_image_map[fname] = meta
            gridfs_image_map[fname.lower()] = meta
    except Exception as exc:
        logger.warning("Could not build GridFS image map for %s (%s)", course_id, exc)

    return {
        "course_id": course_id,
        "short_code": short_code,
        "title": course_title,
        "published_branch": str(pub_branch_oid),
        "about_html": about_html,
        "blocks": extracted_blocks,
        "gridfs_image_map": gridfs_image_map,
        "source_database": "openedx_ulmo",
    }


async def extract_pdf_blocks_from_gridfs(
    org: str,
    course_num: str,
    run: str,
    course_id: str,
    modulestore_db: AsyncIOMotorDatabase,
) -> List[Dict[str, Any]]:
    """
    Extract text from PDF handouts, checklists, glossaries, and lecture transcripts
    stored in Open edX MongoContentStore GridFS (`openedx_ulmo.fs.files` + `fs.chunks`).
    """
    pdf_blocks: List[Dict[str, Any]] = []
    try:
        cursor = modulestore_db["fs.files"].find(
            {
                "contentType": "application/pdf",
                "content_son.org": org,
                "content_son.course": course_num,
                "content_son.run": run,
            }
        ).sort("_id", 1)
        pdf_files = await cursor.to_list(100)
    except Exception as exc:
        logger.warning("Could not query GridFS fs.files for %s (%s)", course_id, exc)
        return []

    for idx, pdf_doc in enumerate(pdf_files, 1):
        try:
            file_id = pdf_doc["_id"]
            c_son = pdf_doc.get("content_son") or {}
            asset_name = c_son.get("name") or str(file_id).split("@")[-1]
            display_name = pdf_doc.get("displayname") or asset_name

            chunks_cursor = (
                modulestore_db["fs.chunks"]
                .find({"files_id": file_id})
                .sort("n", 1)
            )
            raw_chunks = await chunks_cursor.to_list(200)
            if not raw_chunks:
                continue

            raw_bytes = b"".join(c.get("data", b"") for c in raw_chunks)
            if not raw_bytes:
                continue

            reader = PdfReader(io.BytesIO(raw_bytes))
            html_parts: List[str] = []
            for page_idx, page in enumerate(reader.pages, 1):
                page_text = re.sub(r"\s+", " ", (page.extract_text() or "").strip())
                if not page_text:
                    continue
                html_parts.append(
                    f"<h3>{display_name} — Page {page_idx}</h3><p>{page_text}</p>"
                )

            if not html_parts:
                continue

            safe_slug = re.sub(r"[^A-Za-z0-9]", "", asset_name)[:8].lower()
            unit_code = f"pdf{idx:02d}{safe_slug[:4]}"
            pdf_blocks.append(
                {
                    "block_id": f"gridfs_pdf_{idx:02d}_{safe_slug}",
                    "unit_code": unit_code,
                    "block_type": "gridfs_pdf",
                    "section": "Course PDF Resources (GridFS)",
                    "unit_title": f"PDF: {display_name}",
                    "url": f"/{file_id}" if not str(file_id).startswith("/") else str(file_id),
                    "html": "\n".join(html_parts),
                }
            )
        except Exception as exc:
            logger.warning("Failed to parse GridFS PDF %s (%s)", pdf_doc.get("_id"), exc)

    return pdf_blocks


async def ingest_openedx_course_by_id(
    course_id: str,
    db: Optional[AsyncIOMotorDatabase] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Delta-sync a single Open edX course (`course-v1:{org}+{course}+{run}`) from `openedx_ulmo`
    into `poc-who.chunks` (including HTML blocks, GridFS PDFs, and `voyage-multimodal-3` HTML images).
    Called directly by the MongoDB Atlas Trigger webhook (`POST /ingest/run`).
    """
    if db is None:
        db = get_db()

    clean_id = course_id.replace("course-v1:", "")
    parts = clean_id.split("+")
    if len(parts) != 3:
        raise ValueError(f"Invalid course_id format '{course_id}' (expected 'course-v1:ORG+COURSE+RUN').")

    org, course_num, run = parts[0], parts[1], parts[2]
    ms_db = get_modulestore_db()
    av_doc = await ms_db["modulestore.active_versions"].find_one(
        {"org": org, "course": course_num, "run": run}
    )
    if not av_doc:
        raise ValueError(f"Course '{course_id}' not found in openedx_ulmo.modulestore.active_versions.")

    payload = await extract_course_payload_from_modulestore(av_doc, modulestore_db=ms_db)
    if not payload or not payload.get("blocks"):
        return {
            "course_id": course_id,
            "status": "no_published_blocks",
        }

    run_report = await ingest_course(payload, db=db, force=force)
    run_report["source"] = "openedx_ulmo (Atlas Trigger Webhook)"
    run_report["course_title"] = payload["title"]
    return run_report


async def run_all_seed_ingestions(
    db: Optional[AsyncIOMotorDatabase] = None,
    force: bool = True,
    include_openedx_ulmo: bool = True,
    include_seed_courses: bool = True,
) -> Dict[str, Any]:
    """
    Ensure Atlas indexes exist and run Flow A ingestion across both:
      1. The `openedx_ulmo` Split Modulestore courses in MongoDB Atlas
      2. The reference seed courses (`WHOA+IHH+2026`, `WHOA+MAT+2026`, `WHOA+BIO+2026`)
    """
    if db is None:
        db = get_db()

    index_status = await ensure_indexes(db)
    runs: List[Dict[str, Any]] = []

    if include_openedx_ulmo:
        try:
            ms_db = get_modulestore_db()
            for target in DEFAULT_OPENEDX_ULMO_COURSES:
                av_doc = await ms_db["modulestore.active_versions"].find_one(target)
                if not av_doc:
                    continue
                payload = await extract_course_payload_from_modulestore(av_doc, modulestore_db=ms_db)
                if payload and payload.get("blocks"):
                    run_report = await ingest_course(payload, db=db, force=force)
                    run_report["source"] = "openedx_ulmo (Split Modulestore)"
                    run_report["course_title"] = payload["title"]
                    runs.append(run_report)
        except Exception as exc:
            logger.warning("Could not ingest from openedx_ulmo (%s)", exc)

    if include_seed_courses:
        for course_payload in SAMPLE_OPEN_EDX_COURSES:
            run_report = await ingest_course(course_payload, db=db, force=force)
            run_report["source"] = "seed_course"
            run_report["course_title"] = course_payload["title"]
            runs.append(run_report)

    return {
        "indexes": index_status,
        "ingest_runs": runs,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = asyncio.run(run_all_seed_ingestions(force=True))
    import json

    print(json.dumps(result, indent=2))
