# Revenue Intelligence Inbox — Candidate Assignment

A production-grade, local, zero-network Revenue Intelligence Inbox designed for sales managers reviewing heterogeneous call and meeting activities. Built end-to-end to handle 44 records (30 calls, 14 meetings) across fragmented telephony and video systems on 21 August 2026 (Asia/Kolkata timezone).

---

## Quick Start & Verification

### 1. Requirements & Setup
- **Python**: 3.11+ (Tested on Python 3.13)
- **Dependencies**: Minimal, zero paid services, no external network needed at runtime.
```bash
pip install -r requirements.txt
```

### 2. One-Command Replay Check (Demo Load)
Initializes the SQLite database, imports the initial batch, applies the update batch, runs deterministic routing, loads verified pre-generated analyses, and reports final metrics:
```bash
python -m app demo-load
```

### 3. Run Automated Test Suite
Executes all 16 automated tests verifying 44-record count invariant, shuffled imports, late transcript attachment, quote validator substring checks, and manual override persistence:
```bash
pytest
```

### 4. Launch Web Application
Starts the FastAPI web server on `http://127.0.0.1:8000`:
```bash
python -m app serve
```
Open your browser to:
- **Manager Dashboard**: `http://127.0.0.1:8000/`
- **Activity Inbox & Filters**: `http://127.0.0.1:8000/records`
- **Manager Brief (21 Aug 2026)**: `http://127.0.0.1:8000/brief`
- **Definitions & Limitations**: `http://127.0.0.1:8000/definitions`

---

## Step-by-Step Replay Verification Commands

To verify data integrity, idempotence, and conflict resolution step by step:

1. **Reset Database**:
   ```bash
   python -m app reset
   ```
2. **Initial Import (Batch 1, rev 1)**:
   ```bash
   python -m app import data/01_initial.json
   ```
   *Result*: 44 records inserted (30 calls, 14 meetings). Usable transcripts: 17.
3. **Repeat Import (Shuffled Order)**:
   ```bash
   python -m app import data/01_initial.json --shuffle
   ```
   *Result*: 0 inserted, 0 updated, 44 unchanged. Total records remain strictly 44.
4. **Manual Route Correction**:
   Navigate to record `C04` in the UI (`/records/call/<source_id>`). Assign route `customer_follow_up` with note *"Voicemail left for Ritesh"*.
5. **Apply Update Batch (Batch 2, rev 2 — M07 late transcript)**:
   ```bash
   python -m app import data/02_update.json
   ```
   *Result*: 0 inserted, 1 updated (M07), 0 unchanged. Usable transcripts increase from 17 to 18. Total count stays 44.
6. **Verify Manual Override Survival**:
   Check record `C04` in the UI or DB: the manual route, timestamp, and manager note are preserved intact.
7. **Run Export Engine**:
   ```bash
   python -m app export
   ```
   *Result*: Writes `exports/` folder structure, `manifest.json`, `manifest.csv`, and `exports.zip`.

---

## Output Structure & Artifacts

When `python -m app export` is executed, deliverables are written to:
```
exports/
├── by_route/
│   ├── deal_next_steps/
│   ├── customer_follow_up/
│   ├── sales_coaching/
│   ├── support_account_admin/
│   ├── internal_vendor_note/
│   └── needs_human_decision/
├── by_record/
│   └── <source_type>_<source_id>/
│       └── index.md             # Unified record report linking all assigned route outputs
├── manifest.json                # Complete machine-readable audit trail
├── manifest.csv                 # Flat spreadsheet export for ops
└── ../exports.zip               # Self-contained bundle of all outputs
```

---

## Pre-Generated vs. Runtime-Computed Deliverables

| Component | Nature | Description |
|-----------|--------|-------------|
| **Source Records & Transcripts** | Runtime-Computed | Ingested via streaming JSON parser, canonical primary key `(source_type, source_id)`. |
| **Intake State Machine** | Runtime-Computed | Evaluates turns and reasons to classify records into 5 distinct intake states. |
| **Deterministic Router** | Runtime-Computed | Pattern, keyword, and structure matching generates suggested routes, confidence, and triggers. |
| **Data Quality Flags** | Runtime-Computed | Identifies anomalies (e.g. B13 `talk_time > duration`, C02 gatekeeper mismatch, C04 bot screener). |
| **Analyses for 18 Conversations** | Pre-Generated | Differentiated, route-specific analysis cards stored in `analysis/analyses.json`. Every cited quote is verified programmatically as a verbatim substring (`app/quote_validator.py`). |
| **Manager Brief** | Pre-Generated | Executive briefing for 21 August 2026 synthesizing findings across all 18 usable conversations. |

---

## Metric Definitions

- **Total Records (Denominator = 44)**: Total unique `(source_type, source_id)` entities present across all imported batches.
- **Usable Transcripts (18/44 = 40.9%)**: Records containing non-empty conversation text (10 calls with `payload.transcript` + 8 meetings with `transcript_payload.turns` after update).
- **Silent Recording**: Meeting with `recording_status: "recorded"` but 0 turns in `transcript_payload` (e.g. M05, M08, M11).
- **Needs Review**: Any record where transcript content changed after analysis generation (`stale = 1`), or where telephony labels conflict with transcript evidence.
- **Duration**: Wall-clock elapsed time in seconds; formatted as `Xm Ys`.
- **Talk Time**: Cumulative active speech in seconds. Note B13 data anomaly (talk time 5s > duration 4s).

---

## Identity & Hard Constraints Compliance

1. **Identity Rule**: Composite key `(source_type, source_id)` is enforced everywhere. `record_ref`, rep names, and array indices are treated strictly as non-unique display labels.
2. **Zero Fabrication**: No invented pipeline revenue values, deal stages, or ownership. Owners are assigned if and only if explicitly stated in conversation text.
3. **Quote & Turn Verifiability**: Every quote cited in call analysis must be an exact verbatim substring of the stored transcript; every meeting citation must reference a valid 1-based turn number.
4. **Offline & Zero Network**: Runs 100% locally with SQLite and standard Python libraries.

---

## Known Limitations

1. **Single-Day Scope**: Dataset represents activity strictly on 21 August 2026 IST. Cross-day velocity and multi-week pipeline progression cannot be measured.
2. **Pre-Generated Analysis Refresh**: Newly added or updated records raise a `stale` flag and enter `needs_review` state; re-generating fresh analysis requires running the analysis pipeline.
3. **Telephony Bot Classification**: Automated screeners (e.g. C04) are flagged for human review; fully automated conversational AI classification requires acoustic/phonetic diarization.

---

## Approximate Time Spent
**Time spent**: [PLACEHOLDER: ~6 hours]
