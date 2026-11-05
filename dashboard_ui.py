"""
Interactive HTML Dashboard (`dashboard_ui.py`) for the WHO Academy Open edX Learner Assistant PoC:
  - Tab 1: Flow B — Live Pipeline X-Ray & Grounded SSE Chat (Step-by-step visualization of Scope B1 -> Query Rewrite B3 -> Hybrid $rankFusion B4 -> Voyage rerank-3 / rerank-3-lite B5 -> Grounded Answer [S1]/[S2] B6/B7)
  - Tab 2: Flow A — Data Processing & Ingestion Inspector (Raw Open edX HTML vs Cleaned Breadcrumb Chunks, SHA-256 delta logs, and Custom WHO Lecture HTML Sandbox)
  - Tab 3: Search Mode & Reranker Benchmark Matrix (`Hybrid`, `Vector`, `Lexical` x `rerank-3`, `rerank-3-lite`, `none` with `voyage-4` autoEmbed) stored in MongoDB Atlas (`genai_search.benchmark_runs`)
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WHO Academy — AI Course Assistant</title>
  <style>
    :root {
      /* Official World Health Organization (WHO) / WHO Academy Light & Blue Palette */
      --bg: #f4f8fb;
      --surface: #ffffff;
      --surface-elevated: #eef5fa;
      --border: #d5e3ee;
      --text: #0b2545;
      --text-muted: #4a6580;
      --primary: #008dc9;       /* Official WHO Emblem Blue */
      --primary-hover: #006999; /* Deep WHO Blue */
      --accent: #005a8c;        /* WHO Navy Accent */
      --success: #0d8a52;
      --warn: #d97706;
      --danger: #c81e1e;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }

    header {
      background: #ffffff;
      border-block-start: 5px solid var(--primary);
      border-block-end: 1px solid var(--border);
      padding: 1.15rem 2rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      box-shadow: 0 2px 8px rgba(11, 37, 69, 0.04);
    }

    .brand-row {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .who-logo-badge {
      display: flex;
      align-items: center;
      justify-content: center;
      inline-size: 48px;
      block-size: 48px;
      border-radius: 50%;
      background: #e6f4fa;
      border: 2px solid var(--primary);
      color: var(--primary);
      flex-shrink: 0;
    }

    .who-org-kicker {
      font-size: 0.74rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--primary);
      margin-block-end: 0.1rem;
    }

    header h1 {
      margin: 0;
      font-size: 1.28rem;
      font-weight: 700;
      color: var(--text);
    }

    header p {
      margin: 0.15rem 0 0;
      color: var(--text-muted);
      font-size: 0.86rem;
    }

    .badge-group {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    .badge {
      background: #e6f4fa;
      border: 1px solid #b3dff2;
      color: var(--accent);
      padding: 0.3rem 0.75rem;
      border-radius: 999px;
      font-size: 0.76rem;
      font-weight: 600;
    }

    /* Navigation Tabs */
    .tab-nav {
      background: #ffffff;
      border-block-end: 1px solid var(--border);
      padding: 0 2rem;
      display: flex;
      gap: 0.5rem;
      overflow-x: auto;
    }

    .tab-btn {
      background: transparent;
      color: var(--text-muted);
      border: none;
      border-block-end: 3px solid transparent;
      border-radius: 0;
      padding: 0.9rem 1.2rem;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
    }

    .tab-btn:hover {
      color: var(--primary);
      background: #f4f9fd;
    }

    .tab-btn.active {
      color: var(--primary);
      border-block-end-color: var(--primary);
      background: #eef7fc;
    }

    main {
      max-inline-size: 1440px;
      margin: 0 auto;
      padding: 1.5rem 2rem 3rem;
    }

    .tab-section {
      display: none;
      gap: 1.5rem;
    }

    .tab-section.active {
      display: grid;
    }

    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.25rem 1.5rem;
      box-shadow: 0 1px 4px rgba(11, 37, 69, 0.04);
    }

    .panel-header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-block-end: 1rem;
    }

    .panel-header h2 {
      margin: 0;
      font-size: 1.06rem;
      color: var(--text);
    }

    .controls-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
    }

    input[type="text"], select, textarea {
      background: #ffffff;
      color: var(--text);
      border: 1px solid #bfd3e3;
      border-radius: 0.5rem;
      padding: 0.6rem 0.9rem;
      font-size: 0.88rem;
      font-family: inherit;
    }

    input[type="text"]:focus, select:focus, textarea:focus {
      outline: 2px solid rgba(0, 141, 201, 0.25);
      border-color: var(--primary);
    }

    input[type="text"] {
      flex: 1 1 320px;
    }

    textarea {
      inline-size: 100%;
      min-block-size: 140px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.82rem;
    }

    button {
      background: var(--primary);
      color: #ffffff;
      border: none;
      border-radius: 0.5rem;
      padding: 0.6rem 1.1rem;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }

    button:hover {
      background: var(--primary-hover);
      color: #ffffff;
    }

    button.secondary {
      background: #eef6fb;
      color: var(--accent);
      border: 1px solid #b8d9ed;
    }

    button.secondary:hover {
      background: #dceef9;
      color: var(--text);
    }

    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    .preset-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-block-start: 0.75rem;
    }

    .preset-pill {
      background: #eef7fc;
      border: 1px solid #bee0f3;
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 500;
      padding: 0.3rem 0.7rem;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.12s ease;
    }

    .preset-pill:hover {
      background: #d7edf9;
      border-color: var(--primary);
    }

    .split-2col {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 1.25rem;
    }

    .step-timeline {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 0.75rem;
      margin-block-end: 1.25rem;
    }

    .step-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-inline-start: 4px solid var(--primary);
      border-radius: 0.5rem;
      padding: 0.75rem 0.95rem;
      font-size: 0.82rem;
      box-shadow: 0 1px 3px rgba(11, 37, 69, 0.03);
    }

    .step-card strong {
      display: block;
      color: var(--accent);
      margin-block-end: 0.25rem;
    }

    pre.code-box {
      background: #f7fafc;
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 0.85rem;
      overflow-x: auto;
      font-size: 0.79rem;
      color: #1e3a5f;
      margin: 0.4rem 0 0;
      white-space: pre-wrap;
    }

    /* Responsive Table (modern-web-guidance: sticky headers + @container stacked fallback) */
    .table-wrapper {
      overflow: auto;
      max-inline-size: 100%;
      max-block-size: min(520px, 80vh);
      container-type: inline-size;
      border: 1px solid var(--border);
      border-radius: 0.5rem;
    }

    table {
      inline-size: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.86rem;
      --label-2: "Search Mode";
      --label-3: "Reranker";
      --label-4: "Top-1 Accuracy";
      --label-5: "Recall@3";
      --label-6: "Chunks Sent to LLM";
      --label-7: "Safety Gate (<0.50)";
      --label-8: "Avg Top-1 Score";
      --label-9: "Avg Latency";
      --label-10: "Est. Cost / 1,000 Queries";
    }

    th, td {
      padding: 0.72rem 0.85rem;
      text-align: start;
      border-block-end: 1px solid var(--border);
    }

    thead {
      position: sticky;
      inset-block-start: 0;
      z-index: 2;
      background: #eaf3f9;
    }

    thead th {
      color: var(--accent);
      font-weight: 700;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    tbody th {
      position: sticky;
      inset-inline-start: 0;
      z-index: 1;
      background: var(--surface);
      font-weight: 600;
      color: var(--text);
    }

    tbody tr:hover td,
    tbody tr:hover th {
      background: var(--surface-elevated);
    }

    @container (width < 680px) {
      table, thead, tbody, tr, th, td {
        display: block;
      }

      thead {
        display: none;
      }

      tr {
        margin-block-end: 1rem;
        border: 1px solid var(--border);
      }

      tbody th {
        position: sticky;
        inset-block-start: 0;
        z-index: 2;
        background: var(--surface-elevated);
      }

      td:nth-child(2)::before { content: var(--label-2) ": " / var(--label-2); font-weight: 600; color: var(--text-muted); }
      td:nth-child(3)::before { content: var(--label-3) ": " / var(--label-3); font-weight: 600; color: var(--text-muted); }
      td:nth-child(4)::before { content: var(--label-4) ": " / var(--label-4); font-weight: 600; color: var(--text-muted); }
      td:nth-child(5)::before { content: var(--label-5) ": " / var(--label-5); font-weight: 600; color: var(--text-muted); }
      td:nth-child(6)::before { content: var(--label-6) ": " / var(--label-6); font-weight: 600; color: var(--text-muted); }
      td:nth-child(7)::before { content: var(--label-7) ": " / var(--label-7); font-weight: 600; color: var(--text-muted); }
      td:nth-child(8)::before { content: var(--label-8) ": " / var(--label-8); font-weight: 600; color: var(--text-muted); }
      td:nth-child(9)::before { content: var(--label-9) ": " / var(--label-9); font-weight: 600; color: var(--text-muted); }
    }

    .question-card {
      background: #f8fbfd;
      border: 1px solid var(--border);
      border-radius: 0.65rem;
      padding: 1.15rem;
      margin-block-end: 1.25rem;
    }

    .profile-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(305px, 1fr));
      gap: 0.85rem;
    }

    .profile-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 0.85rem;
    }

    .profile-box.pass {
      border-inline-start: 4px solid var(--primary);
    }

    .profile-box.diff {
      border-inline-start: 4px solid var(--warn);
    }

    .hit-item {
      background: #f4f9fd;
      border: 1px solid #d5e6f2;
      border-radius: 0.4rem;
      padding: 0.55rem 0.7rem;
      margin-block-start: 0.5rem;
      font-size: 0.8rem;
    }

    .score-pill {
      display: inline-block;
      padding: 0.12rem 0.5rem;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.74rem;
    }

    .score-high {
      background: #e1f4ec;
      color: #0b6e40;
      border: 1px solid #b5e2ce;
    }

    .score-cutoff {
      background: #fde8e8;
      color: #9b1c1c;
      border: 1px solid #f8b4b4;
    }

    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.82em;
      color: var(--accent);
      background: #edf5fb;
      padding: 0.08rem 0.32rem;
      border-radius: 0.25rem;
    }

    .llm-answer-hero {
      background: linear-gradient(180deg, #ffffff 0%, #f8fbfe 100%);
      border: 1.5px solid #b8d8ee;
      border-inline-start: 5px solid var(--primary);
      border-radius: 0.75rem;
      padding: 1.25rem 1.4rem;
      box-shadow: 0 4px 14px rgba(0, 141, 201, 0.07);
      margin-block-end: 1.25rem;
    }

    .question-bubble {
      background: #eef6fc;
      border: 1px solid #cde4f5;
      border-radius: 0.5rem;
      padding: 0.6rem 0.9rem;
      font-size: 0.86rem;
      color: var(--accent);
      margin-block-end: 0.85rem;
    }

    .answer-rich-body {
      font-size: 0.98rem;
      line-height: 1.65;
      color: var(--text);
      min-block-size: 72px;
    }

    .answer-rich-body p {
      margin: 0 0 0.65rem 0;
    }

    .answer-rich-body p:last-child {
      margin-block-end: 0;
    }

    .cit-badge {
      display: inline-flex;
      align-items: center;
      background: #008dc9;
      color: #ffffff;
      font-weight: 700;
      font-size: 0.75rem;
      padding: 0.1rem 0.48rem;
      border-radius: 999px;
      text-decoration: none;
      margin: 0 0.15rem;
      vertical-align: baseline;
      box-shadow: 0 1px 3px rgba(0, 141, 201, 0.25);
      transition: transform 0.12s ease, background 0.12s ease;
    }

    .cit-badge:hover {
      background: #005a8c;
      transform: translateY(-1px);
    }

    .blocked-callout {
      background: #fef6f6;
      border: 1px solid #f5c2c2;
      border-inline-start: 4px solid var(--danger);
      border-radius: 0.5rem;
      padding: 0.85rem 1rem;
      color: #7f1d1d;
      font-weight: 500;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand-row">
      <div class="who-logo-badge" aria-hidden="true" title="World Health Organization — WHO Academy">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <ellipse cx="12" cy="12" rx="4.5" ry="10"></ellipse>
          <line x1="2" y1="12" x2="22" y2="12"></line>
          <path d="M4.5 7.5h15"></path>
          <path d="M4.5 16.5h15"></path>
          <line x1="12" y1="5" x2="12" y2="19" stroke-width="2.4"></line>
        </svg>
      </div>
      <div>
        <div class="who-org-kicker">World Health Organization &bull; WHO Academy</div>
        <h1>WHO Academy — AI Course Assistant</h1>
        <p>Test <strong>grounded course Q&amp;A with unit citations</strong>, inspect <strong>Open edX HTML chunking</strong>, and compare <strong>Search &amp; Reranking accuracy (<code>voyage-4</code> + <code>rerank-3</code>)</strong></p>
      </div>
    </div>
    <div class="badge-group" id="env-badges">
      <span class="badge">MongoDB Atlas Hybrid Search</span>
      <span class="badge">Auto-Embed: voyage-4 ($0.06/1M)</span>
      <span class="badge">Rerank: rerank-3 / rerank-3-lite (&ge; 0.50)</span>
      <button class="secondary" style="padding:0.28rem 0.75rem;font-size:0.78rem;border-radius:999px;" onclick="openStatusTab()">Check Demo Status</button>
    </div>
  </header>

  <nav class="tab-nav">
    <button class="tab-btn active" id="nav-tab-topics" onclick="switchTab('tab-topics', this)">1. Course Topics &amp; Sample Questions</button>
    <button class="tab-btn" id="nav-tab-xray" onclick="switchTab('tab-xray', this)">2. Live Course Assistant (Q&amp;A Demo)</button>
    <button class="tab-btn" id="nav-tab-ingest" onclick="switchTab('tab-ingest', this)">3. Open edX Course Ingestion</button>
    <button class="tab-btn" id="nav-tab-benchmark" onclick="switchTab('tab-benchmark', this)">4. Search &amp; Reranker Benchmark</button>
    <button class="tab-btn" id="nav-tab-status" onclick="switchTab('tab-status', this)">5. System Health Check</button>
  </nav>

  <main>
    <!-- =================================================================== -->
    <!-- TAB 1: LIVE LEARNER ASSISTANT & SEARCH X-RAY                        -->
    <!-- =================================================================== -->
    <section id="tab-xray" class="tab-section">
      <div class="panel">
        <div class="panel-header">
          <h2>Ask a WHO Course Question — Trace Retrieval, Reranking &amp; Streaming Answer</h2>
          <button class="secondary" onclick="runSeedIngest()">Sync WHO Courses from Open edX Modulestore</button>
        </div>

        <div class="controls-row">
          <input
            type="text"
            id="xray-question"
            value="Why does loss to follow-up introduce bias in randomized clinical trials when the likelihood of follow-up differs between intervention groups?"
            placeholder="Ask a WHO lecture question or personal progress question..."
          />
          <input type="hidden" id="xray-embed" value="voyage-4" />
          <select id="xray-rerank">
            <option value="rerank-3" selected>Rerank: rerank-3 ($0.05/1M)</option>
            <option value="rerank-3-lite">Rerank: rerank-3-lite ($0.02/1M)</option>
            <option value="none">Rerank: none (Raw Hybrid Order)</option>
          </select>
          <select id="xray-mode">
            <option value="hybrid" selected>Mode: Hybrid (Vector + Text)</option>
            <option value="vector">Mode: Vector Only ($vectorSearch)</option>
            <option value="lexical">Mode: Lexical Only ($search)</option>
          </select>
          <button id="btn-xray-run" onclick="runLiveXray()">Trace &amp; Stream Answer</button>
        </div>

        <div class="preset-pills">
          <span class="preset-pill" onclick="setXrayQuestion('Why does loss to follow-up introduce bias in randomized clinical trials when the likelihood of follow-up differs between intervention groups?')">Clinical Trials (H0118EN): Loss to Follow-up Bias</span>
          <span class="preset-pill" onclick="setXrayQuestion('What open-source platform is the GSED App built on for offline data collection on a tablet?')">GSED Short Form (H0117EN): ODK Tablet Platform</span>
          <span class="preset-pill" onclick="setXrayQuestion('In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?')">Emergency Care (0006_BEC_EN): ABCDE &amp; SAMPLE History</span>
          <span class="preset-pill" onclick="setXrayQuestion('How is shock defined when poor perfusion prevents oxygen-carrying blood from reaching vital organs, and which age groups are most likely to be affected?')">Emergency Care (0006_BEC_EN): Shock vs Altered Mental Status</span>
          <span class="preset-pill" onclick="setXrayQuestion('Which 2023 WHO operational guidance document supports the Multisectoral Accountability Framework to end TB (MAF-TB)?')">TB Social Protection (HQ_SPTB_EN): MAF-TB 2023 Guidance</span>
          <span class="preset-pill" onclick="setXrayQuestion('Which international ethical guidelines and ICH Good Clinical Practice (GCP) revision are listed in Module 2 resources for protecting participant safety?')">Research Ethics (H0140EN): CIOMS &amp; ICH E6(R3)</span>
          <span class="preset-pill" onclick="setXrayQuestion('According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?')">PDF Handout (H0117EN GridFS): GSED Competency Checklist PDF</span>
          <span class="preset-pill" onclick="setXrayQuestion('In the Ethical Integration of AI PDF module, what is required before collecting or using digital colposcopy images from data subjects?')">PDF Handout (H0118EN GridFS): Ethical AI &amp; Colposcopy Consent PDF</span>
          <span class="preset-pill" onclick="setXrayQuestion('How much of the course have I finished?')">Personal Progress: My Course Completion</span>
          <span class="preset-pill" onclick="setXrayQuestion('What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?')">Security Test: Un-Enrolled Course (BSL-4 Blocked)</span>
        </div>
      </div>

      <!-- 3-Step Pipeline Trace Cards -->
      <div class="step-timeline">
        <div class="step-card">
          <strong>1. Learner Course Access Filter</strong>
          <div id="xray-step-b1" style="color:var(--text-muted);">Pre-filters search to Learner_1042's enrolled WHO courses only</div>
        </div>
        <div class="step-card">
          <strong>2. MongoDB Atlas Hybrid Search</strong>
          <div id="xray-step-b4" style="color:var(--text-muted);">Combines <code>$vectorSearch</code> (<code>voyage-4</code> autoEmbed) + <code>$search</code> (BM25)</div>
        </div>
        <div class="step-card">
          <strong>3. Voyage AI Reranker (&ge; 0.50) + 1 LLM Call</strong>
          <div id="xray-step-b5" style="color:var(--text-muted);">Keeps top chunks &ge; 0.50 &rarr; 1 final LLM call (or 0 calls if blocked)</div>
        </div>
      </div>

      <!-- Transparent Live Per-Query Cost & Token Bar -->
      <div class="panel" style="padding:0.85rem 1.15rem;margin-block-end:1.25rem;border-inline-start:3px solid var(--primary);">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.75rem;">
          <div>
            <strong style="font-size:0.86rem;color:var(--primary);">Transparent 3-Step Cost Architecture (Per 1,000 Queries)</strong>
            <div style="font-size:0.78rem;color:var(--text-muted);margin-block-start:0.15rem;">
              Direct query to <code>voyage-4</code> Hybrid Search + <code>rerank-3</code> (&ge; 0.50 cutoff) + <strong>1 single LLM call</strong> (or <strong>0 LLM calls</strong> when blocked by the <code>&lt; 0.50</code> safety gate).
            </div>
          </div>
          <div id="xray-cost-badges" style="display:flex;gap:0.5rem;flex-wrap:wrap;font-size:0.76rem;">
            <span class="badge">1. Query Embed (<code>voyage-4</code>): <strong>~$0.001 / 1k</strong></span>
            <span class="badge">2. Rerank (<code>rerank-3</code>): <strong>~$0.079 / 1k</strong></span>
            <span class="badge" style="border-color:var(--primary);color:var(--primary);">3. Grounded Answer LLM: <strong>1 Call (~$0.180 / 1k)</strong></span>
          </div>
        </div>
      </div>

      <!-- Final LLM Answer Hero Card -->
      <div class="llm-answer-hero">
        <div class="panel-header" style="margin-block-end:0.65rem;">
          <div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;">
            <span class="score-pill score-high" id="xray-llm-status-pill" style="font-size:0.78rem;">Final Grounded LLM Answer</span>
            <h2 style="margin:0;font-size:1.08rem;">WHO Course Assistant Response (with Verified Course Citations)</h2>
          </div>
          <span id="xray-source-summary-pill" class="badge">Ready to answer</span>
        </div>

        <div id="xray-asked-question-box" class="question-bubble" style="display:none;"></div>

        <div id="xray-answer-box" class="answer-rich-body">
          Click <strong>"Trace &amp; Stream Answer"</strong> above (or select any topic in <strong>Tab 1</strong>) to stream the grounded LLM response and inspect the exact WHO lecture chunks used.
        </div>
      </div>

      <!-- Verified WHO Course Source Chunks & Saved MongoDB Turn -->
      <div class="split-2col">
        <div class="panel">
          <div class="panel-header">
            <h2>Verified WHO Source Chunks Sent to the LLM (<code>[S1]</code>, <code>[S2]</code>)</h2>
          </div>
          <div id="xray-citations-box">
            <p style="font-size:0.84rem;color:var(--text-muted);margin:0;">
              The surviving chunks scoring <code>&ge; 0.50</code> from Voyage AI <code>rerank-3</code> will appear here so you can verify every <code>[S1]</code> / <code>[S2]</code> citation word-for-word.
            </p>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h2>Saved Conversation Turn (<code>chat_turns</code> Collection)</h2>
          </div>
          <pre id="xray-turn-json" class="code-box">// The persisted MongoDB chat_turns document (with 30-day TTL expiration) will appear here...</pre>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 2: COURSE HTML INGESTION & CHUNK INSPECTOR                      -->
    <!-- =================================================================== -->
    <section id="tab-ingest" class="tab-section">
      <div class="panel">
        <div class="panel-header">
          <h2>HTML Chunking Sandbox — Paste Any Open edX Lecture HTML to Preview Plain-Text Chunks</h2>
          <div class="controls-row">
            <button onclick="previewCustomLecture(false)">Preview Chunking Only</button>
            <button class="secondary" onclick="previewCustomLecture(true)">Preview &amp; Upsert into MongoDB Atlas</button>
          </div>
        </div>

        <div class="split-2col">
          <div>
            <label style="font-size:0.82rem;color:var(--text-muted);display:block;margin-block-end:0.35rem;">
              Raw Open edX HTML Block (strips HTML tags &amp; splits at <code>&lt;h2&gt;/&lt;h3&gt;</code> headings):
            </label>
            <textarea id="sandbox-html">&lt;h3&gt;WHO Surgical Hand Preparation Protocol&lt;/h3&gt;
&lt;p&gt;Surgical hand antisepsis must be performed either by scrubbing with a suitable antimicrobial soap and water or by using a suitable alcohol-based handrub (ABHR) with sustained activity before donning sterile surgical gloves.&lt;/p&gt;
&lt;h3&gt;Brushless Technique Recommendation&lt;/h3&gt;
&lt;p&gt;The WHO strongly discourages the use of brushes for surgical hand preparation because scrubbing with a brush causes skin micro-abrasions and increases bacterial shedding from hands.&lt;/p&gt;</textarea>
          </div>
          <div>
            <label style="font-size:0.82rem;color:var(--text-muted);display:block;margin-block-end:0.35rem;">
              Plain-Text Chunks Written to MongoDB <code>chunks</code> Collection (with Breadcrumb Header + SHA-256):
            </label>
            <pre id="sandbox-output" class="code-box">Click "Preview Chunking Only" to inspect the exact JSON document written to MongoDB Atlas (where autoEmbed embeds the `text` field automatically).</pre>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>WHO Course &amp; Lecture Reader — Browse Extracted Lectures &amp; Delta Sync Logs</h2>
          <div class="controls-row">
            <select id="course-filter-select" onchange="renderFilteredChunks()">
              <option value="ALL">All WHO Courses (Loading...)</option>
            </select>
            <input
              type="text"
              id="chunk-search-input"
              placeholder="Filter lectures by keyword (e.g. SAMPLE, ODK, dropout, MAF-TB)..."
              oninput="renderFilteredChunks()"
              style="flex: 0 1 280px;"
            />
            <button class="secondary" onclick="loadPipelineInspector()">Refresh MongoDB Snapshot</button>
          </div>
        </div>
        <div id="ingest-inspector-container">
          <p style="color:var(--text-muted);">Loading stored chunks and delta ingestion telemetry from MongoDB...</p>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 3: SEARCH MODE & RERANKER BENCHMARK MATRIX                      -->
    <!-- =================================================================== -->
    <section id="tab-benchmark" class="tab-section">
      <div class="panel">
        <div class="panel-header">
          <h2>Compare Search Modes (<code>Hybrid</code> / <code>Vector</code> / <code>Lexical</code>) &times; Rerankers (<code>rerank-3</code> / <code>rerank-3-lite</code> / <code>No Reranker</code>)</h2>
          <span id="status-banner" style="color:var(--text-muted);font-size:0.86rem;">Ready (Indexed with Atlas Auto-Embed <code>voyage-4</code>)</span>
        </div>
        <div class="controls-row">
          <input
            type="text"
            id="custom-question"
            placeholder="Enter a custom WHO lecture question to benchmark across all 5 search & rerank profiles (or click a question below)..."
          />
          <button id="btn-run-custom" onclick="runBenchmark('custom')">Benchmark Custom Question</button>
          <button id="btn-run-suite" class="secondary" onclick="runBenchmark('quick_4')">Run Quick 4-Question Suite</button>
          <button id="btn-run-full8" class="secondary" onclick="runBenchmark('full_8')">Run Full 10-Question WHO Suite</button>
        </div>

        <details style="margin-block-start: 1rem; border-block-start: 1px solid var(--border); padding-block-start: 0.85rem;" open>
          <summary style="cursor: pointer; font-weight: 600; font-size: 0.9rem; color: var(--accent);">
            Inspect WHO Golden Benchmark Questions (4 Quick Smoke-Test Questions / 10 Full Course Questions)
          </summary>
          <div class="table-wrapper" style="margin-block-start: 0.75rem; max-block-size: 380px;">
            <table>
              <thead>
                <tr>
                  <th>Suite</th>
                  <th>Test Case &amp; Capability</th>
                  <th>WHO Course</th>
                  <th>Learner Question</th>
                  <th>Expected Chunk ID</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="score-pill score-high">Quick 4 &amp; Full 10</span></td>
                  <td><strong>TC1</strong> — Semantic Paraphrase (Vector Beats Lexical)</td>
                  <td><code>WHOA+H0118EN+Q1_2025</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">Clinical Trials</span></td>
                  <td>Why does unequal participant dropout between study arms distort results?</td>
                  <td><code>H0118ENQ12025-html51-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('Why does unequal participant dropout between study arms distort results?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="score-pill score-high">Quick 4 &amp; Full 10</span></td>
                  <td><strong>TC2</strong> — Exact Reference Lookup (Lexical Beats Vector)</td>
                  <td><code>WHOA+HQ_SPTB_EN+2025</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">TB Social Protection</span></td>
                  <td>Where is web annex A listed in the course?</td>
                  <td><code>HQSPTBEN2025-dfec2da100-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('Where is web annex A listed in the course?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="score-pill score-high">Quick 4 &amp; Full 10</span></td>
                  <td><strong>TC3</strong> — Fine-Grained Disambiguation (<code>rerank-3</code> Beats <code>lite</code>)</td>
                  <td><code>WHOA+H0118EN+Q1_2025</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">Clinical Trials Module 6</span></td>
                  <td>Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?</td>
                  <td><code>H0118ENQ12025-html173-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('Why should investigators communicate new safety information to trial participants in plain language without causing undue alarm?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="score-pill score-high">Quick 4 &amp; Full 10</span></td>
                  <td><strong>TC4</strong> — Tenant Security &amp; &ge;0.50 Cutoff</td>
                  <td><code>Un-Enrolled Course</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">BSL-4 Biosafety</span></td>
                  <td>What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?</td>
                  <td><code>Blocked (&lt; 0.50 Cutoff)</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC5</strong> — Technical Platform Lookup</td>
                  <td><code>WHOA+H0117EN+2025_Q1</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">GSED Short Form</span></td>
                  <td>What open-source platform is the GSED App built on for offline data collection on a tablet?</td>
                  <td><code>H0117EN2025Q1-f74edee11f-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('What open-source platform is the GSED App built on for offline data collection on a tablet?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC6</strong> — Clinical Mnemonic &amp; Triage</td>
                  <td><code>WHOA+0006_BEC_EN+2026</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">Basic Emergency Care</span></td>
                  <td>In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?</td>
                  <td><code>0006BECEN2026-62049db3dc-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC7</strong> — GridFS PDF Handout (Reranker Beats No-Reranker)</td>
                  <td><code>WHOA+H0117EN+2025_Q1</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">GridFS PDF Checklist</span></td>
                  <td>According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?</td>
                  <td><code>H0117EN2025Q1-pdf01gsed-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC8</strong> — Semantic Paraphrase (Vector Beats Lexical)</td>
                  <td><code>WHOA+IHH+2026</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">Hand Hygiene Skin Integrity</span></td>
                  <td>Why are fake acrylic manicures and metal bands prohibited for clinicians?</td>
                  <td><code>IHH2026-u31-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('Why are fake acrylic manicures and metal bands prohibited for clinicians?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC9</strong> — Semantic Paraphrase (Vector Beats Lexical)</td>
                  <td><code>WHOA+0006_BEC_EN+2026</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">Emergency Care Shock</span></td>
                  <td>What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?</td>
                  <td><code>0006BECEN2026-c823108494-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('What life-threatening circulatory failure happens when tissues receive insufficient arterial flow?')">Test 1Q</button></td>
                </tr>
                <tr>
                  <td><span class="badge">Full 10 Suite</span></td>
                  <td><strong>TC10</strong> — Exact Reference Lookup (Lexical Beats Vector)</td>
                  <td><code>WHOA+HQ_SPTB_EN+2025</code><br/><span style="font-size:0.75rem;color:var(--text-muted);">TB Social Protection</span></td>
                  <td>Where is Oliosi or e219-e26 listed in the course?</td>
                  <td><code>HQSPTBEN2025-dfec2da100-c01</code></td>
                  <td><button class="secondary" style="padding:0.35rem 0.65rem;font-size:0.76rem;" onclick="benchmarkSinglePreset('Where is Oliosi or e219-e26 listed in the course?')">Test 1Q</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>Executive Model Comparison Matrix (Saved in <code>genai_search.benchmark_runs</code>)</h2>
          <div class="controls-row">
            <label for="history-select" style="font-size: 0.84rem; color: var(--text-muted);">Historical Runs:</label>
            <select id="history-select" onchange="onSelectSavedRun()">
              <option value="">Loading saved runs...</option>
            </select>
          </div>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Profile</th>
                <th>Search Mode</th>
                <th>Reranker</th>
                <th>Top-1 Accuracy</th>
                <th>Recall@3</th>
                <th>Chunks Sent to LLM (&ge;0.50)</th>
                <th>Off-Topic Cutoff (&lt;0.50)</th>
                <th>Avg Top-1 Score</th>
                <th>Avg Latency</th>
                <th>Search Cost (per 1,000 Questions)</th>
              </tr>
            </thead>
            <tbody id="summary-tbody">
              <tr>
                <th>No benchmark run loaded yet</th>
                <td colspan="9">Click "Run Quick 4-Question Suite" or "Run Full 8-Question WHO Suite" above to execute and store a full comparison in MongoDB Atlas.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Transparent End-to-End Cost Breakdown Panel -->
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Transparent End-to-End Cost Breakdown (Per 1,000 Learner Queries)</h2>
            <p style="margin:0.25rem 0 0;font-size:0.84rem;color:var(--text-muted);">
              Full financial disclosure across <strong>Intent Routing</strong>, <strong>MongoDB Atlas Auto-Embedding</strong>, <strong>Voyage AI Reranking</strong>, and the <strong>Single Final LLM Answer Call</strong>.
            </p>
          </div>
          <span class="score-pill score-high">Total End-to-End: ~$0.26 / 1,000 Queries ($0.00026 / Question)</span>
        </div>

        <div class="profile-grid" style="margin-block-end:1rem;">
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>1. Instant Intent Router (Step B3)</strong>
              <span class="score-pill score-high">$0.000 / 1k Qs</span>
            </div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.4rem;">
              <strong>Why we removed the "LLM Query Beautifier":</strong> Calling OpenAI before search would double LLM API invocations (2 calls/request) and add ~1.5s latency. Because <code>voyage-4</code> understands natural learner questions directly at <strong>100% accuracy</strong>, routing between <code>get_my_progress</code> and <code>search_course_content</code> is done deterministically in Python at <strong>0 ms and $0.00</strong>.
            </div>
          </div>

          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>2. Hybrid Retrieval (<code>voyage-4</code> + BM25)</strong>
              <span class="score-pill score-high">$0.001 / 1k Qs</span>
            </div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.4rem;">
              <strong>Pricing:</strong> <code>$0.06 / 1M tokens</code> for <code>voyage-4</code> query auto-embedding + <strong>$0.00</strong> for lexical BM25 <code>$search</code> inside MongoDB Atlas.<br/>
              <strong>Math:</strong> An average 20-token learner question costs <code>20 &times; $0.06 / 1,000,000 = $0.0012</code> per 1,000 queries (one-tenth of a cent).
            </div>
          </div>

          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>3. Voyage AI Reranker (<code>rerank-3</code>)</strong>
              <span class="score-pill score-high">$0.079 / 1k Qs</span>
            </div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.4rem;">
              <strong>Pricing:</strong> <code>$0.05 / 1M tokens</code> for <code>rerank-3</code> (or <code>$0.02 / 1M</code> for <code>rerank-3-lite</code> = <strong>$0.032 / 1k Qs</strong>).<br/>
              <strong>Math:</strong> Scoring 8 candidate chunks (~1,580 tokens/query) costs <strong>$0.079 per 1,000 queries</strong> while pruning noisy chunks (&lt; 0.50) down to <strong>1.8 kept chunks</strong>.
            </div>
          </div>

          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>4. Final Answer Generation (1 LLM Call)</strong>
              <span class="score-pill score-high">~$0.180 / 1k Qs</span>
            </div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.4rem;">
              <strong>Context Compression Savings:</strong> By sending only the <strong>1.8 surviving chunks</strong> (~650 input tokens + ~140 output tokens) instead of stuffing all 8 retrieved chunks (~1,700 tokens) into the prompt, <code>rerank-3</code> cuts LLM input tokens by <strong>~60%</strong>.<br/>
              <strong>Safety Cutoff Savings:</strong> When 0 chunks score &ge; 0.50 (un-enrolled/off-topic query), the LLM is <strong>not called at all ($0.000)</strong>.
            </div>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>Side-by-Side Question &amp; Chunk Ranking Breakdown</h2>
        </div>
        <div id="questions-container"></div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 4: PRE-DEMO SYSTEM STATUS CHECK                                 -->
    <!-- =================================================================== -->
    <section id="tab-status" class="tab-section">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>Pre-Demo Live Readiness Check — Verify All 3 Architecture Services Before Presenting</h2>
            <p style="margin:0.2rem 0 0;font-size:0.84rem;color:var(--text-muted);">
              Sends live requests to <strong>MongoDB Atlas</strong> (<code>poc-who</code> &amp; <code>openedx_ulmo</code>), <strong>Voyage AI API</strong> (<code>voyage-4</code> / <code>rerank-3</code>), and <strong>Azure AI Foundry Chat Model</strong> (Step <code>B6</code> Single Grounded LLM Call).
            </p>
          </div>
          <div class="controls-row">
            <span id="overall-status-pill" class="badge">Not checked yet</span>
            <button id="btn-run-status" onclick="runPreDemoStatusCheck()">Run Live System Check Now</button>
          </div>
        </div>

        <div class="profile-grid" id="status-cards-grid" style="margin-block-start:1rem;">
          <div class="profile-box">
            <strong>1. MongoDB Atlas Database &amp; Search Indexes</strong>
            <p style="font-size:0.82rem;color:var(--text-muted);">Click "Run Live System Check Now" to ping MongoDB Atlas and inspect index statuses.</p>
          </div>
          <div class="profile-box">
            <strong>2. Voyage AI Rerank &amp; Auto-Embed API</strong>
            <p style="font-size:0.82rem;color:var(--text-muted);">Click "Run Live System Check Now" to test <code>https://ai.mongodb.com/v1/rerank</code>.</p>
          </div>
          <div class="profile-box">
            <strong>3. Azure AI Foundry — Chat Model (Step B6 Single Call)</strong>
            <p style="font-size:0.82rem;color:var(--text-muted);">Click "Run Live System Check Now" to test the Step B6 Grounded Answer LLM.</p>
          </div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <h2>Detailed Diagnostic Payload (<code>GET /status/check</code>)</h2>
        </div>
        <pre id="status-raw-json" class="code-box">// Live diagnostic JSON from /status/check will appear here...</pre>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 1: COURSE TOPICS & SAMPLE QUESTIONS                             -->
    <!-- =================================================================== -->
    <section id="tab-topics" class="tab-section active">
      <div class="panel">
        <div class="panel-header">
          <div>
            <h2>WHO Course Catalog — Lecture Summaries &amp; One-Click Questions</h2>
            <p style="margin:0.2rem 0 0;font-size:0.86rem;color:var(--text-muted);">
              Simple overview of every WHO course indexed in <code>poc-who.chunks</code>. Click any question below to launch it immediately in <strong>Tab 2 (Live Course Assistant)</strong>.
            </p>
          </div>
        </div>

        <div class="profile-grid" style="grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 1.15rem;">

          <!-- Course 1: Clinical Trials (H0118EN) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>1. WHO Good Practices for Clinical Trials</strong>
              <span class="score-pill score-high">Enrolled (HTML + 2 GridFS PDFs)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course ID: <code>course-v1:WHOA+H0118EN+Q1_2025</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              Covers the <strong>2022 World Health Assembly resolution (WHA75.8)</strong>, how <strong>randomization and blinding</strong> prevent bias, why <strong>differential loss to follow-up</strong> distorts treatment outcomes, and includes the GridFS PDF <strong><em>Ethical Integration of AI (Module 3 Unit 1)</em></strong>.
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant (HTML &amp; PDF):</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('What did the 2022 World Health Assembly resolution call for regarding clinical trials?')">
                  &rarr; "What did the 2022 World Health Assembly resolution call for regarding clinical trials?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('Why does unequal participant dropout between study arms distort results?')">
                  &rarr; "Why does unequal participant dropout between study arms distort results?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('In the Ethical Integration of AI PDF module, what is required before collecting or using digital colposcopy images from data subjects?')">
                  &rarr; [PDF] "In the Ethical Integration of AI PDF, what is required before collecting digital colposcopy images?"
                </button>
              </div>
            </div>
          </div>

          <!-- Course 2: Basic Emergency Care (0006_BEC_EN) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>2. Basic Emergency Care (BEC)</strong>
              <span class="score-pill score-high">Enrolled (113 Chunks)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course ID: <code>course-v1:WHOA+0006_BEC_EN+2026</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              Trains frontline healthcare workers on the systematic <strong>ABCDE primary survey</strong> (Airway, Breathing, Circulation, Disability, Exposure), the <strong>SAMPLE secondary history</strong> mnemonic, and managing <strong>Trauma, Difficulty in Breathing (DIB), Shock (poor perfusion), and Altered Mental Status (AMS)</strong>.
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant:</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('In Basic Emergency Care, what does the SAMPLE history approach stand for after completing the initial ABCDE approach?')">
                  &rarr; "What does the SAMPLE history approach stand for after completing the initial ABCDE approach?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('How is shock defined when poor perfusion prevents oxygen-carrying blood from reaching vital organs, and which age groups are most likely to be affected?')">
                  &rarr; "How is shock defined and which age groups are most likely to be affected?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('What are the main causes of altered mental status and how should you assess a patient with difficulty in breathing?')">
                  &rarr; "What are the main causes of altered mental status in emergency care?"
                </button>
              </div>
            </div>
          </div>

          <!-- Course 3: GSED Child Development (H0117EN) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>3. Global Scales for Early Development (GSED)</strong>
              <span class="score-pill score-high">Enrolled (HTML + 1 GridFS PDF)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course ID: <code>course-v1:WHOA+H0117EN+2025_Q1</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              Explains how to assess child neurodevelopment (<strong>0 to 36 months</strong>) using the <strong>GSED Short Form (SF) caregiver questionnaire</strong>, the <strong>Open Data Kit (ODK)</strong> tablet app, and the GridFS PDF <strong><em>GSED SF Assessor Competency Checklist</em></strong>.
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant (HTML &amp; PDF):</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('What open-source platform is the GSED App built on for offline data collection on a tablet?')">
                  &rarr; "What open-source platform is the GSED App built on for offline data collection on a tablet?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('According to the GSED Short Form Assessor Competency Checklist PDF, what general skills and tablet preparation steps must an assessor demonstrate?')">
                  &rarr; [PDF] "According to the GSED Competency Checklist PDF, what general skills and tablet steps must an assessor show?"
                </button>
              </div>
            </div>
          </div>

          <!-- Course 4: TB Social Protection (HQ_SPTB_EN) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>4. Social Protection for People Affected by TB</strong>
              <span class="score-pill score-high">Enrolled (24 Chunks)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course ID: <code>course-v1:WHOA+HQ_SPTB_EN+2025</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              Covers the <strong>WHO End TB Strategy</strong> goal of eliminating catastrophic costs for TB-affected households, cross-sector collaboration between National TB Programmes and social protection ministries, and the <strong>2023 Multisectoral Accountability Framework (MAF-TB, Web Annex A)</strong>.
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant:</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('Which 2023 WHO operational guidance document supports the Multisectoral Accountability Framework to end TB (MAF-TB)?')">
                  &rarr; "Which 2023 WHO operational guidance document supports the Multisectoral Accountability Framework to end TB (MAF-TB)?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('Where is web annex A listed in the course?')">
                  &rarr; "Where is web annex A listed in the course?"
                </button>
              </div>
            </div>
          </div>

          <!-- Course 5: Research Ethics (H0140EN) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>5. Research Ethics Online Training (Part 2)</strong>
              <span class="score-pill score-high">Enrolled (HTML + 14 GridFS PDFs)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course ID: <code>course-v1:WHOA+H0140EN+2025_Q4</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              Covers Research Ethics Committee (REC) review of interventional clinical research, <strong>CIOMS International Ethical Guidelines</strong>, <strong>ICH E6 (R3) GCP</strong>, plus <strong>14 GridFS PDFs</strong> (Module 2 &amp; 3 Glossaries and 12 Video Lecture Transcripts).
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant (HTML &amp; PDF):</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('Which international ethical guidelines and ICH Good Clinical Practice (GCP) revision are listed in Module 2 resources for protecting participant safety?')">
                  &rarr; "Which international ethical guidelines and ICH GCP revision are listed in Module 2 resources?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('How does the Research Ethics Module 3 Glossary PDF define Accreditation and Quality Improvement (QA/QI) for a Research Ethics Committee?')">
                  &rarr; [PDF] "How does the Module 3 Glossary PDF define Accreditation and QA/QI for a Research Ethics Committee?"
                </button>
              </div>
            </div>
          </div>

          <!-- Course 6 & 7: Hand Hygiene (IHH2026) & Postpartum Haemorrhage (MAT2026 / bbt) -->
          <div class="profile-box pass">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>6. Hand Hygiene &amp; Maternal Postpartum Care (PPH)</strong>
              <span class="score-pill score-high">Enrolled (15 Chunks)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Course IDs: <code>WHOA+IHH+2026</code> &bull; <code>WHOA+MAT+2026</code> &bull; <code>WHOA+bbt+bbt</code>
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              <strong>Hand Hygiene:</strong> WHO My 5 Moments for Hand Hygiene, Alcohol-Based Handrub (ABHR, 20–30s) vs. soap &amp; water (40–60s, required for <em>C. difficile</em> spores), and why medical gloves never replace hand hygiene.<br/>
              <strong>Maternal Care:</strong> First-line <strong>Oxytocin (10 IU IM/IV)</strong> for PPH prevention and the <strong>E-MOTIVE bundle</strong> (Massage, Oxytocics, Tranexamic acid 1g IV, IV fluids, Escalation).
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant:</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('Do I still need to wash my hands if I wore medical gloves, and when is soap and water required instead of alcohol-based handrub?')">
                  &rarr; "Do I still need to wash my hands if I wore gloves, and when is soap and water required?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('What is the recommended first-line uterotonic drug for preventing postpartum haemorrhage (PPH) and what are the steps of the E-MOTIVE bundle?')">
                  &rarr; "What is the first-line drug for preventing PPH and what are the steps of the E-MOTIVE bundle?"
                </button>
              </div>
            </div>
          </div>

          <!-- Restricted / Un-Enrolled Security Test Course (BIO2026) & Personal Progress -->
          <div class="profile-box diff">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
              <strong>7. Security &amp; Routing Tests (Un-Enrolled Course + Personal Progress)</strong>
              <span class="score-pill score-cutoff">Not Enrolled (1 Chunk in DB &rarr; 0 Returned)</span>
            </div>
            <div style="font-size:0.76rem;color:var(--accent);margin:0.2rem 0 0.5rem;">
              Restricted Course in MongoDB: <code>course-v1:WHOA+BIO+2026</code> (1 chunk: <code>BIO2026-u1-c00</code> — Learner_1042 is <strong>NOT</strong> enrolled)
            </div>
            <p style="font-size:0.84rem;color:var(--text);margin:0 0 0.55rem;">
              <strong>Why this returns 0 Chunks (on purpose):</strong><br/>
              1. <strong>Un-Enrolled Course Block (<code>WHOA+BIO+2026</code>):</strong> This course has 1 chunk in MongoDB about BSL-4 Ebola positive-pressure suits. Because <code>Learner_1042</code> is not enrolled in <code>BIO+2026</code>, Step 1 blocks that course and Step 4 (<code>&ge; 0.50</code> cutoff) drops any unrelated chunks so <strong>0 chunks reach the LLM</strong>.<br/>
              2. <strong>Personal Progress API (<code>get_my_progress</code>):</strong> Student grades and completion % are never stored in vector chunks — Step 2 routes directly to the live Progress API.
            </p>
            <div class="hit-item">
              <div style="font-weight:600;color:var(--accent);margin-block-end:0.35rem;">Try Asking in Live Assistant:</div>
              <div style="display:grid;gap:0.4rem;">
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?')">
                  &rarr; [Blocked / Un-Enrolled] "What is the BSL-4 positive-pressure suit chemical shower protocol for Ebola?"
                </button>
                <button class="secondary" style="text-align:start;font-size:0.78rem;padding:0.4rem 0.65rem;" onclick="askFromGuide('How much of the course have I finished and when is my next deadline?')">
                  &rarr; [Live Progress API] "How much of the course have I finished and when is my next deadline?"
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  </main>

  <script>
    let savedRuns = [];

    function switchTab(tabId, btnElem) {
      document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      if (btnElem) btnElem.classList.add('active');
      if (tabId === 'tab-ingest') loadPipelineInspector();
      if (tabId === 'tab-benchmark') loadSavedRuns();
      if (tabId === 'tab-status') runPreDemoStatusCheck();
    }

    function openStatusTab() {
      switchTab('tab-status', document.getElementById('nav-tab-status'));
    }

    function askFromGuide(questionText) {
      document.getElementById('xray-question').value = questionText;
      switchTab('tab-xray', document.getElementById('nav-tab-xray'));
      runLiveXray();
    }

    async function runPreDemoStatusCheck() {
      const btn = document.getElementById('btn-run-status');
      const pill = document.getElementById('overall-status-pill');
      const grid = document.getElementById('status-cards-grid');
      const rawBox = document.getElementById('status-raw-json');

      if (btn) btn.disabled = true;
      pill.className = 'badge';
      pill.textContent = 'Checking live services...';
      rawBox.textContent = '// Pinging MongoDB Atlas, Voyage AI (ai.mongodb.com), and Azure AI Foundry / OpenAI Gateway...';

      try {
        const res = await fetch('/status/check');
        const data = await res.json();
        rawBox.textContent = JSON.stringify(data, null, 2);

        if (data.all_systems_ready) {
          pill.className = 'score-pill score-high';
          pill.textContent = 'ALL 3 SYSTEMS ONLINE & READY FOR DEMO';
        } else {
          pill.className = 'score-pill score-cutoff';
          pill.textContent = 'ATTENTION NEEDED — SEE CARDS BELOW';
        }

        const m = data.checks?.mongodb || {};
        const v = data.checks?.voyage_ai || {};
        const l = data.checks?.llm_gateway || {};

        const idxHtml = (m.search_indexes || []).map(idx => `
          <div class="hit-item" style="display:flex;justify-content:space-between;align-items:center;">
            <span><code>${idx.name}</code> (${idx.type || 'index'})</span>
            <span class="score-pill ${idx.status === 'READY' ? 'score-high' : 'score-cutoff'}">${idx.status || 'UNKNOWN'}</span>
          </div>
        `).join('') || '<div class="hit-item">No search indexes reported yet</div>';

        grid.innerHTML = `
          <div class="profile-box ${m.ok ? 'pass' : 'diff'}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>1. MongoDB Atlas Database</strong>
              <span class="score-pill ${m.ok ? 'score-high' : 'score-cutoff'}">${m.ok ? 'ONLINE' : 'ISSUE'} (${m.latency_ms || 0} ms)</span>
            </div>
            <div style="font-size:0.82rem;margin:0.5rem 0;color:var(--text);">
              ${m.message || ''}
            </div>
            <div style="font-size:0.78rem;color:var(--text-muted);">
              RAG DB: <code>${m.rag_database || '-'}</code> | Modulestore DB: <code>${m.modulestore_database || '-'}</code> | Server: <code>v${m.mongodb_version || '?'}</code>
            </div>
            <div style="margin-block-start:0.5rem;font-size:0.78rem;font-weight:600;color:var(--accent);">Atlas Search Indexes:</div>
            ${idxHtml}
          </div>

          <div class="profile-box ${v.ok ? 'pass' : 'diff'}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>2. Voyage AI API (ai.mongodb.com)</strong>
              <span class="score-pill ${v.ok ? 'score-high' : 'score-cutoff'}">${v.ok ? 'ONLINE' : 'FALLBACK / ISSUE'} (${v.latency_ms || 0} ms)</span>
            </div>
            <div style="font-size:0.82rem;margin:0.5rem 0;color:var(--text);">
              ${v.message || ''}
            </div>
            <div class="hit-item">
              <div>Endpoint: <code>${v.base_url || ''}/rerank</code></div>
              <div>Embed Model: <code>${v.embed_model || ''}</code> | Rerank Model: <code>${v.rerank_model || ''}</code></div>
              <div>Live Test Score: <strong>${Number(v.sample_relevance_score || 0).toFixed(4)}</strong></div>
            </div>
          </div>

          <div class="profile-box ${l.ok ? 'pass' : 'diff'}">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <strong>3. Azure AI Foundry — Chat Model (Step B6 Single Call)</strong>
              <span class="score-pill ${l.ok ? 'score-high' : 'score-cutoff'}">${l.ok ? 'ONLINE' : 'OFFLINE / VPN NEEDED'} (${l.latency_ms || 0} ms)</span>
            </div>
            <div style="font-size:0.82rem;margin:0.5rem 0;color:var(--text);">
              ${l.message || ''}
            </div>
            <div class="hit-item">
              <div>Provider: <code>${l.provider || ''}</code></div>
              <div>Gateway URL: <code>${l.gateway_url || ''}</code></div>
              <div>Active Model: <code>${l.model || ''}</code></div>
            </div>
          </div>
        `;
      } catch (err) {
        pill.className = 'score-pill score-cutoff';
        pill.textContent = 'CHECK FAILED';
        rawBox.textContent = `Error calling /status/check: ${err.message}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      if (window.location.hash === '#status' || window.location.pathname === '/status') {
        openStatusTab();
      }
    });

    function setXrayQuestion(text) {
      document.getElementById('xray-question').value = text;
    }

    async function runSeedIngest() {
      const btn = event?.target;
      if (btn) btn.disabled = true;
      try {
        const res = await fetch('/ingest/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force: true })
        });
        const data = await res.json();
        alert(`Ingested ${data.ingest_runs?.length || 0} WHO courses into MongoDB Atlas (genai_search)!`);
        loadPipelineInspector();
      } catch (err) {
        alert(`Ingest error: ${err.message}`);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    // ---------------------------------------------------------------------
    // TAB 1: Live Flow B SSE X-Ray
    // ---------------------------------------------------------------------
    // TAB 2: Live Flow B SSE X-Ray & Rich Grounded Answer Renderer
    // ---------------------------------------------------------------------
    function formatGroundedAnswerHtml(rawText, citations) {
      if (!rawText) return '';
      const trimmed = rawText.trim();
      if (trimmed.includes('This topic was not found in your enrolled courses')) {
        return `
          <div class="blocked-callout">
            <strong>Safety Gate Triggered (0 Surviving Chunks &ge; 0.50 &rarr; 0 LLM Calls):</strong><br/>
            "${trimmed}"
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.35rem;font-weight:400;">
              Because no chunk in <code>Learner_1042</code>'s enrolled courses scored &ge; 0.50 in Voyage AI <code>rerank-3</code>, the assistant refused to guess and did not call the LLM ($0.00 LLM cost).
            </div>
          </div>
        `;
      }

      // Escape basic HTML entities first
      let html = rawText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      // Format bold (**text**) and italic (*text*)
      html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
      html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');

      // Format inline [S1], [S2], [S3] citation badges with tooltip & smooth scroll to source card
      const citMap = {};
      (citations || []).forEach(c => {
        citMap[c.tag] = c;
      });
      html = html.replace(/\\[(S\\d+)\\]/g, (match, tagCode) => {
        const fullTag = `[${tagCode}]`;
        const cInfo = citMap[fullTag];
        const titleAttr = cInfo ? `${cInfo.chunk_id} — ${cInfo.title}` : `Verified WHO Source ${fullTag}`;
        return `<a href="#source-card-${tagCode}" class="cit-badge" title="${titleAttr.replace(/"/g, '&quot;')}">${fullTag}</a>`;
      });

      // Convert line breaks and bullet points into clean paragraphs
      const paragraphs = html.split(/\\n{2,}/).map(block => {
        const lines = block.split('\\n');
        if (lines.every(l => l.trim().startsWith('- '))) {
          const items = lines.map(l => `<li>${l.trim().slice(2)}</li>`).join('');
          return `<ul style="margin:0.4rem 0 0.6rem 1.2rem;padding:0;">${items}</ul>`;
        }
        return `<p>${lines.join('<br/>')}</p>`;
      });

      return paragraphs.join('');
    }

    async function runLiveXray() {
      const question = document.getElementById('xray-question').value.trim();
      const embed_model = document.getElementById('xray-embed').value;
      const rerank_model = document.getElementById('xray-rerank').value;
      const search_mode = document.getElementById('xray-mode').value;
      const btn = document.getElementById('btn-xray-run');

      if (!question) return;
      btn.disabled = true;

      const ansBox = document.getElementById('xray-answer-box');
      const citBox = document.getElementById('xray-citations-box');
      const jsonBox = document.getElementById('xray-turn-json');
      const askedBox = document.getElementById('xray-asked-question-box');
      const llmPill = document.getElementById('xray-llm-status-pill');
      const srcPill = document.getElementById('xray-source-summary-pill');

      if (askedBox) {
        askedBox.style.display = 'block';
        askedBox.innerHTML = `<strong>Learner Question:</strong> "${question}"`;
      }
      if (llmPill) {
        llmPill.className = 'badge';
        llmPill.textContent = 'Streaming LLM Answer...';
      }
      if (srcPill) {
        srcPill.textContent = 'Retrieving & reranking WHO chunks...';
      }

      let rawAnswerStream = '';
      let activeCitations = [];
      ansBox.innerHTML = '<span style="color:var(--text-muted);">Searching WHO courses and streaming grounded answer...</span>';
      citBox.innerHTML = '';
      jsonBox.textContent = '// Streaming from /chat/stream...';

      try {
        const response = await fetch('/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: 'sess_xray_demo',
            learner_id: 'Learner_1042',
            question,
            embed_model,
            rerank_model,
            search_mode
          })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = 'message';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\\n');
          buffer = lines.pop() || '';

          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              const payload = JSON.parse(line.slice(5).trim());
              if (currentEvent === 'metadata') {
                const cb = payload.cost_breakdown || {};
                const costBadges = document.getElementById('xray-cost-badges');
                activeCitations = payload.citations || [];

                if (payload.tool === 'get_my_progress') {
                  document.getElementById('xray-step-b4').innerHTML = `<em>Bypassed vector index (Live Progress API: <code>get_my_progress</code>)</em>`;
                  document.getElementById('xray-step-b5').innerHTML = `<em>Bypassed reranker &amp; LLM (0 LLM calls)</em>`;
                  if (llmPill) {
                    llmPill.className = 'score-pill score-high';
                    llmPill.textContent = 'Live Progress API (0 LLM Calls)';
                  }
                  if (srcPill) {
                    srcPill.textContent = 'Source: Open edX Live Student Progress API';
                  }
                  if (costBadges) {
                    costBadges.innerHTML = `
                      <span class="badge">Live Progress API: <strong>0 LLM Calls ($0.000)</strong></span>
                      <span class="badge" style="border-color:var(--primary);color:var(--primary);">Total Cost: <strong>$0.000 / 1k Qs</strong></span>
                    `;
                  }
                } else {
                  const llmCalls = payload.llm_calls_count !== undefined ? payload.llm_calls_count : (payload.surviving_chunks > 0 ? 1 : 0);
                  document.getElementById('xray-step-b1').innerHTML = `Enrolled filter: <code>${(payload.enrolled_courses || []).join(', ')}</code>`;
                  document.getElementById('xray-step-b4').innerHTML = `Mode: <code>${payload.retrieval_mode}</code><br/>Candidates: <strong>${payload.candidates_retrieved}</strong> chunks`;
                  document.getElementById('xray-step-b5').innerHTML = `Model: <code>${payload.rerank_mode}</code><br/>Surviving (&ge;0.50): <strong>${payload.surviving_chunks}/3</strong> &rarr; <strong>${llmCalls} LLM Call${llmCalls === 1 ? '' : 's'}</strong>`;
                  if (llmPill) {
                    llmPill.className = llmCalls > 0 ? 'score-pill score-high' : 'score-pill score-cutoff';
                    llmPill.textContent = llmCalls > 0
                      ? `1 Grounded LLM Call (${payload.surviving_chunks} Verified Chunk${payload.surviving_chunks === 1 ? '' : 's'})`
                      : 'Blocked by < 0.50 Safety Gate (0 LLM Calls)';
                  }
                  if (srcPill) {
                    srcPill.textContent = payload.surviving_chunks > 0
                      ? `Cited from ${payload.surviving_chunks} surviving WHO chunk${payload.surviving_chunks === 1 ? '' : 's'} (out of ${payload.candidates_retrieved} retrieved)`
                      : `0 of ${payload.candidates_retrieved} retrieved chunks passed >= 0.50 cutoff`;
                  }
                  if (costBadges) {
                    const embCost = Number(cb.embed_cost_per_1k_usd || 0.001).toFixed(3);
                    const rrkCost = Number(cb.rerank_cost_per_1k_usd || 0).toFixed(3);
                    const llmCost = Number(cb.llm_cost_per_1k_usd || 0).toFixed(3);
                    const totCost = Number(cb.total_cost_per_1k_usd || 0).toFixed(3);
                    costBadges.innerHTML = `
                      <span class="badge">1. Embed (<code>${cb.embed_tokens || 0} tok</code>): <strong>$${embCost} / 1k</strong></span>
                      <span class="badge">2. Rerank (<code>${cb.rerank_tokens || 0} tok</code>): <strong>$${rrkCost} / 1k</strong></span>
                      <span class="badge" style="border-color:var(--primary);color:var(--primary);">3. Answer LLM: <strong>${llmCalls} Call${llmCalls === 1 ? '' : 's'} ($${llmCost} / 1k)</strong> | Total: <strong>$${totCost} / 1k Qs</strong></span>
                    `;
                  }
                }

                if (activeCitations.length > 0) {
                  citBox.innerHTML = activeCitations.map((c, idx) => {
                    const tagCode = (c.tag || '').replace(/[\\[\\]]/g, '');
                    return `
                      <div class="hit-item" id="source-card-${tagCode}">
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
                          <div>
                            <span class="cit-badge">${c.tag}</span> <code>${c.chunk_id}</code> — <strong>${c.title}</strong>
                          </div>
                          <span class="score-pill score-high">${c.relevance_score !== null && c.relevance_score !== undefined ? 'Rerank Score: ' + Number(c.relevance_score).toFixed(4) : 'Raw Rank'}</span>
                        </div>
                        <div style="font-size:0.76rem;color:var(--accent);margin-top:0.25rem;">
                          Course: <code>${c.course_id || '-'}</code> | Open edX Unit: <code>${c.url}</code>
                        </div>
                        ${c.text ? `
                          <details ${idx === 0 ? 'open' : ''} style="margin-top:0.45rem;">
                            <summary style="cursor:pointer;font-size:0.78rem;font-weight:600;color:var(--primary);">
                              Read Full WHO Source Lecture Text (${c.tag})
                            </summary>
                            <pre class="code-box" style="margin-top:0.35rem;max-block-size:220px;overflow-y:auto;">${c.text}</pre>
                          </details>
                        ` : ''}
                      </div>
                    `;
                  }).join('');
                } else {
                  citBox.innerHTML = `
                    <div class="hit-item">
                      <span class="score-pill score-cutoff">0 Chunks Sent to LLM</span>
                      <div style="margin-top:0.3rem;color:var(--text-muted);">
                        ${payload.tool === 'get_my_progress'
                          ? 'Personal progress queries are answered directly from the live Progress API without reading course chunks.'
                          : 'No chunk in Learner_1042\\'s enrolled courses scored >= 0.50 in Voyage AI rerank-3.'}
                      </div>
                    </div>
                  `;
                }
              } else if (currentEvent === 'token') {
                rawAnswerStream += payload.token;
                ansBox.innerHTML = formatGroundedAnswerHtml(rawAnswerStream, activeCitations);
              } else if (currentEvent === 'done') {
                ansBox.innerHTML = formatGroundedAnswerHtml(rawAnswerStream || payload.answer || '', activeCitations);
                jsonBox.textContent = JSON.stringify(payload, null, 2);
              }
            }
          }
        }
      } catch (err) {
        ansBox.textContent = `Error: ${err.message}`;
      } finally {
        btn.disabled = false;
      }
    }

    // ---------------------------------------------------------------------
    // TAB 2: Flow A Ingestion Inspector & Custom Lecture Sandbox
    // ---------------------------------------------------------------------
    async function previewCustomLecture(ingestToAtlas) {
      const raw_html = document.getElementById('sandbox-html').value;
      const out = document.getElementById('sandbox-output');
      out.textContent = 'Processing HTML and computing SHA-256 chunks...';
      try {
        const res = await fetch('/ingest/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            course_title: 'Hand Hygiene Essentials',
            section: '3. Skin Care and Surgical Hand Preparation',
            unit_title: '3.2 Surgical Hand Antisepsis Protocol',
            raw_html,
            ingest_to_atlas: ingestToAtlas
          })
        });
        const data = await res.json();
        out.textContent = JSON.stringify(data, null, 2);
        if (ingestToAtlas) loadPipelineInspector();
      } catch (err) {
        out.textContent = `Error: ${err.message}`;
      }
    }

    let allInspectorChunks = [];
    let allInspectorCourses = [];
    let allInspectorSources = [];
    let allInspectorRuns = [];

    function askAboutLecture(sectionTitle) {
      const cleanTopic = (sectionTitle || '').split('—').pop().trim() || sectionTitle;
      document.getElementById('xray-question').value = `What are the key WHO guidelines and recommendations covered in "${cleanTopic}"?`;
      switchTab('tab-xray', document.getElementById('nav-tab-xray'));
      runLiveXray();
    }

    async function loadPipelineInspector() {
      const container = document.getElementById('ingest-inspector-container');
      try {
        const res = await fetch('/pipeline/inspect');
        const data = await res.json();
        allInspectorChunks = data.stored_chunks || [];
        allInspectorCourses = data.stored_courses || [];
        allInspectorSources = data.stored_sources || [];
        allInspectorRuns = data.recent_ingest_runs || [];

        const courseSelect = document.getElementById('course-filter-select');
        if (courseSelect) {
          const prevVal = courseSelect.value || 'ALL';
          courseSelect.innerHTML = `<option value="ALL">All WHO Courses (${allInspectorChunks.length} chunks across ${allInspectorCourses.length} courses)</option>` +
            allInspectorCourses.map(course => {
              const cnt = allInspectorChunks.filter(ch => ch.course_id === course._id).length;
              return `<option value="${course._id}">${course.title || course._id} (${cnt} chunks)</option>`;
            }).join('');
          if ([...courseSelect.options].some(o => o.value === prevVal)) {
            courseSelect.value = prevVal;
          }
        }

        renderFilteredChunks();
      } catch (err) {
        container.innerHTML = `<p style="color:var(--danger);">Failed to inspect pipeline: ${err.message}</p>`;
      }
    }

    function renderFilteredChunks() {
      const container = document.getElementById('ingest-inspector-container');
      if (allInspectorChunks.length === 0) {
        container.innerHTML = `<p style="color:var(--warn);">No chunks in MongoDB yet. Click "Sync WHO Courses from Open edX Modulestore" in Tab 1.</p>`;
        return;
      }

      const selectedCourse = document.getElementById('course-filter-select')?.value || 'ALL';
      const keyword = (document.getElementById('chunk-search-input')?.value || '').trim().toLowerCase();

      const filtered = allInspectorChunks.filter(c => {
        const matchCourse = selectedCourse === 'ALL' || c.course_id === selectedCourse;
        const matchKw = !keyword || (c.text || '').toLowerCase().includes(keyword) || (c.section_title || '').toLowerCase().includes(keyword) || (c._id || '').toLowerCase().includes(keyword);
        return matchCourse && matchKw;
      });

      const shown = filtered.slice(0, 60);

      container.innerHTML = `
        <div style="margin-block-end:1rem;font-size:0.86rem;color:var(--text-muted);">
          Showing <strong>${shown.length}</strong> of <strong>${filtered.length}</strong> matching lecture chunks |
          Total Courses: <strong>${allInspectorCourses.length}</strong> |
          Total Plain-Text Chunks (autoEmbed): <strong>${allInspectorChunks.length}</strong> |
          Tracked HTML Source Hashes: <strong>${allInspectorSources.length}</strong>
        </div>
        <div class="profile-grid">
          ${shown.map(c => {
            const safeTitle = (c.section_title || '').replace(/'/g, "\\'");
            return `
            <div class="profile-box pass">
              <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
                <code>${c._id}</code>
                <span class="score-pill score-high">${c.course_id}</span>
              </div>
              <div style="font-size:0.82rem;font-weight:600;color:var(--text);margin-top:0.35rem;">
                ${c.section_title || ''}
              </div>
              <div style="font-size:0.75rem;color:var(--text-muted);margin:0.2rem 0 0.45rem;display:flex;justify-content:space-between;align-items:center;">
                <span>SHA-256: <code>${(c.sha256 || '').slice(0, 12)}...</code></span>
                <button class="secondary" style="padding:0.22rem 0.55rem;font-size:0.74rem;" onclick="askAboutLecture('${safeTitle}')">Ask Assistant About This Lecture &rarr;</button>
              </div>
              <pre class="code-box" style="max-block-size:210px;overflow-y:auto;">${c.text}</pre>
            </div>
          `}).join('')}
        </div>
        <h3 style="font-size:0.95rem;margin-top:1.5rem;">Recent Delta Ingest Run Telemetry (<code>ingest_runs</code>)</h3>
        <pre class="code-box">${JSON.stringify(allInspectorRuns.slice(0, 3), null, 2)}</pre>
      `;
    }

    // ---------------------------------------------------------------------
    // TAB 3: Voyage AI Model Benchmark Matrix
    // ---------------------------------------------------------------------
    function benchmarkSinglePreset(questionText) {
      document.getElementById('custom-question').value = questionText;
      runBenchmark('custom');
    }

    async function runBenchmark(mode) {
      const status = document.getElementById('status-banner');
      const btnCustom = document.getElementById('btn-run-custom');
      const btnSuite = document.getElementById('btn-run-suite');
      const btnFull8 = document.getElementById('btn-run-full8');
      const qInput = document.getElementById('custom-question').value.trim();

      const payload = {};
      if (mode === 'custom' && qInput) {
        payload.custom_question = qInput;
      } else if (mode === 'full_8') {
        payload.suite_mode = 'full_8';
      } else {
        payload.suite_mode = 'quick_4';
      }

      btnCustom.disabled = true;
      btnSuite.disabled = true;
      if (btnFull8) btnFull8.disabled = true;
      status.textContent = 'Running benchmark across Voyage AI models (with polite rate-limit pacing & deduplication)...';

      try {
        const res = await fetch('/benchmark/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const runDoc = await res.json();
        status.textContent = `Saved benchmark ${runDoc.benchmark_id} to benchmark_runs`;
        await loadSavedRuns(runDoc.benchmark_id);
      } catch (err) {
        status.textContent = `Benchmark error: ${err.message}`;
      } finally {
        btnCustom.disabled = false;
        btnSuite.disabled = false;
        if (btnFull8) btnFull8.disabled = false;
      }
    }

    async function loadSavedRuns(selectId = null) {
      try {
        const res = await fetch('/benchmark/history?limit=15');
        const data = await res.json();
        savedRuns = data.runs || [];
        const sel = document.getElementById('history-select');
        sel.innerHTML = '';

        if (savedRuns.length === 0) {
          sel.innerHTML = '<option value="">No saved runs yet — click Run 4-Question WHO Golden Suite</option>';
          return;
        }

        savedRuns.forEach((run, idx) => {
          const opt = document.createElement('option');
          opt.value = idx;
          const qCount = (run.questions || []).length;
          opt.textContent = `${run.created_at_iso} — ${run.run_type} (${qCount} Qs) [${run.benchmark_id}]`;
          if (selectId && run.benchmark_id === selectId) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });

        renderRun(savedRuns[sel.value || 0]);
      } catch (err) {
        console.error('Failed to load benchmark history:', err);
      }
    }

    function onSelectSavedRun() {
      const sel = document.getElementById('history-select');
      const run = savedRuns[Number(sel.value)];
      if (run) renderRun(run);
    }

    function renderRun(run) {
      if (!run) return;

      const tbody = document.getElementById('summary-tbody');
      tbody.innerHTML = (run.summary_by_profile || []).map(s => {
        const isNoRerank = s.rerank_model === 'none' || s.avg_top1_score === null || s.avg_top1_score === undefined;
        const scoreCell = isNoRerank ? '<span style="color:var(--text-muted);font-style:italic;">N/A (No Reranker)</span>' : `<code>${Number(s.avg_top1_score).toFixed(4)}</code>`;
        const avgCand = Math.round(s.avg_candidates !== undefined ? s.avg_candidates : 8);
        const avgSurv = s.avg_surviving !== undefined ? s.avg_surviving : 3;
        const safetyOk = s.safety_blocked !== undefined ? s.safety_blocked : !isNoRerank;
        const safetyBadge = safetyOk
          ? '<span class="score-pill score-high">PASS (0 Unrelated Sent)</span>'
          : '<span class="score-pill score-cutoff">FAIL (Sent 3 Unrelated)</span>';
        const rawCost = Number(s.est_cost_per_1k_queries_usd || 0);
        const costDisplay = rawCost >= 0.01 ? `$${rawCost.toFixed(2)}` : `$${rawCost.toFixed(3)}`;
        const centsNum = rawCost * 100;
        const centsLabel = centsNum >= 1 ? `~${Math.round(centsNum)} cents` : `~${centsNum.toFixed(1)} cent`;
        const costBreakdownNote = isNoRerank
          ? `(${centsLabel} — Embed only, No Rerank)`
          : (s.search_mode === 'lexical'
              ? `(${centsLabel} — Rerank only, Free BM25)`
              : `(${centsLabel} total for Embed + Rerank)`);
        return `
        <tr>
          <th>${s.label}</th>
          <td><code>${s.search_mode}</code></td>
          <td><code>${s.rerank_model}</code></td>
          <td><strong>${s.accuracy_pct}%</strong></td>
          <td>${s.recall_at_3_pct}%</td>
          <td>
            <strong>${avgSurv} kept</strong> <span style="color:var(--text-muted);font-size:0.75rem;">(max 3)</span><br/>
            <span style="color:var(--text-muted);font-size:0.72rem;">from ${avgCand} retrieved</span>
          </td>
          <td>${safetyBadge}</td>
          <td>${scoreCell}</td>
          <td><code>${s.avg_total_ms} ms</code> <span style="color:var(--text-muted);font-size:0.76rem;">(${s.avg_retrieval_ms}+${s.avg_rerank_ms})</span></td>
          <td>
            <strong>${costDisplay}</strong> <span style="color:var(--text-muted);font-size:0.75rem;">/ 1,000 questions</span><br/>
            <span style="color:var(--text-muted);font-size:0.72rem;">${costBreakdownNote}</span>
          </td>
        </tr>
      `}).join('');

      const qContainer = document.getElementById('questions-container');
      qContainer.innerHTML = (run.questions || []).map(q => `
        <div class="question-card">
          <div style="margin-block-end:0.8rem;padding-block-end:0.5rem;border-block-end:1px solid var(--border);">
            <strong>${q.test_id} (${q.category}):</strong> "${q.question}"
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.2rem;">
              Rewritten Query: <code>${q.rewritten_query}</code> |
              Expected Target: <code>${q.expected_chunk_id || (q.expect_blocked_or_not_found ? 'Blocked / < 0.50 Cutoff' : 'Open Query')}</code>
            </div>
          </div>

          <div class="profile-grid">
            ${(q.profiles || []).map(p => `
              <div class="profile-box ${p.passed ? 'pass' : 'diff'}">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
                  <strong style="font-size:0.86rem;">${p.label}</strong>
                  <span class="score-pill ${p.passed ? 'score-high' : 'score-cutoff'}">${p.passed ? 'PASS' : 'DIFF'}</span>
                </div>
                <div style="font-size:0.76rem;color:var(--text-muted);margin:0.25rem 0 0.5rem;">
                  Embed: <code>${p.embed_model}</code> | Rerank: <code>${p.rerank_model}</code> | Latency: <code>${p.total_ms} ms</code>
                </div>
                ${(p.top_hits && p.top_hits.length > 0) ? p.top_hits.map(h => `
                  <div class="hit-item">
                    <div style="display:flex;justify-content:space-between;">
                      <strong>#${h.rank}: <code>${h.chunk_id}</code></strong>
                      <span class="score-pill ${p.rerank_model === 'none' || h.relevance_score === null ? 'score-cutoff' : 'score-high'}">${p.rerank_model === 'none' || h.relevance_score === null ? 'No Rerank Score' : 'Score: ' + Number(h.relevance_score).toFixed(4)}</span>
                    </div>
                    <div style="color:var(--text-muted);margin-top:0.18rem;">${h.section_title}</div>
                  </div>
                `).join('') : `
                  <div class="hit-item">
                    <span class="score-pill score-cutoff">0 Chunks Survived &ge; 0.50 Cutoff</span>
                    <div style="color:var(--text-muted);margin-top:0.2rem;">Returns: "This topic was not found in your enrolled courses."</div>
                  </div>
                `}
              </div>
            `).join('')}
          </div>
        </div>
      `).join('');
    }
  </script>
</body>
</html>
"""
