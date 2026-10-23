# SLIDES.md — Presentation Deck (5 Slides)

---

## Slide 1: Manager Problem & Core Findings
### Title: Revenue Intelligence Inbox: Signal vs. Noise on 21 August 2026
- **The Core Problem**:
  - A sales manager faces 44 incoming activity records (30 calls, 14 meetings) spanning fragmented telephony and video systems on a single local date (21 August 2026 IST).
  - Raw system feeds are noisy, incomplete, and deceptive: uncritical automation leads to false deal confidence and overlooked customer crises.
- **Key Finding 1 — Upstream Telephony Conflicts**:
  - Vendor metadata cannot be trusted blindly: Record C02 marked `is_conversation: true` was a 40s gatekeeper interaction; C04 marked `speaker_count: 2` counted an Android automated call screener.
- **Key Finding 2 — The 18/44 Usable Coverage Reality**:
  - Exactly 18 records possess usable speech (10 calls, 8 meetings after M07 update). The other 26 represent short dials (B01–B20) or silent recordings (M05, M08, M11). Missing text does not mean the meeting was never held.
- **Key Finding 3 — Multi-Workflow Conversations**:
  - Conversations like M04 (Cedarwave) combine commercial card migration with severe accounting bugs. Forcing single-category tagging causes customer churn.

---

## Slide 2: Interface Architecture & Deliberate Omissions
### Title: Designing for Manager Focus: What We Built vs. What We Left Out
- **Built for Immediate Manager Action**:
  - **Three Primary Questions Answered**: What happened today? What demands my attention? What should I do next?
  - **Transparent Coverage Metrics**: Headline stats explicitly declare denominators (e.g., 18/44 = 40.9% coverage) to prevent statistical deception.
  - **Evidence Jump-Links**: Every claim in an analysis jumps directly to the turn number (meetings) or verbatim quote (calls).
  - **Full Operational Auditability**: Manual route corrections are badged and preserve audit logs (`manual_set_at`, `manual_set_by`, `manual_reason`).
- **What Was Deliberately Left Out (and Why)**:
  - **No Hallucinated Deal Values / Win Probabilities**: Without contractual pipeline data, inventing $ amounts or win % is analytical malpractice.
  - **No Cross-Rep Leaderboards**: 44 records on a single day with heterogeneous distribution (Leela has 1 meeting; Dev has 1 call) is statistically invalid for rep ranking.
  - **No Generic "AI Summaries"**: Generic LLM summaries lose actionable technical details. We enforce structured, route-specific analysis cards.

---

## Slide 3: Routing Architecture & A Difficult Case
### Title: Transparent Routing Rules & Handling Edge Cases
- **Deterministic Routing Pipeline**:
  - Transparent keyword and structural rules evaluate transcript text and metadata to suggest 0, 1, or multiple routes:
    - `deal_next_steps` | `customer_follow_up` | `sales_coaching` | `support_account_admin` | `internal_vendor_note` | `needs_human_decision`
  - Each suggestion outputs confidence, trigger snippets, and plain-language reasoning.
- **The Difficult Case: Record C04 (Lanternpath Media)**:
  - *Metadata*: `is_connected: false`, `duration: 38s`, `talk_time: 19s`, `speaker_count: 2`.
  - *Transcript Content*: An automated call screener (*"Please record your name and the purpose of your call..."*) followed by rep Arun leaving a voicemail for Ritesh about an email misdirection.
  - *The Dilemma*: Is it an unanswered call? A voicemail? A conversation?
  - *Our Solution*: Routed to `needs_human_decision` with a prominent Data Quality warning. Preserves human oversight rather than allowing automated routing to misfile the account.

---

## Slide 4: Verification Methodology: Numbers & Conclusions
### Title: Rigorous Verification: Ground Truth Over Assumption
- **Verifying the Headline Number: 18 Usable Transcripts**:
  - *Initial Batch*: 44 records imported. Programmatic inspection reveals 10 calls with flat string transcripts in `payload.transcript` (C01–C10) and 7 meetings with `transcript_payload.turns` (M01, M02, M03, M04, M06, M09, M10). Total = 17.
  - *Update Batch (M07)*: Revision 2 arrives with 27 turns for M07.
  - *Verification Invariant*: Total record count remains strictly 44; usable transcripts update from 17 to 18 (10 calls, 8 meetings). Automated pytest confirms state under shuffled imports and repeat deliveries.
- **Verifying Analytical Conclusions: Programmatic Quote Validation**:
  - We implemented `app/quote_validator.py`: every cited quote in call analyses is verified via whitespace-normalized exact substring match against stored text.
  - Meeting turn references are checked against array bounds (1 to N).
  - 100% of the 67 cited passages across all 23 analysis entries pass automated programmatic verification.

---

## Slide 5: Trade-Offs, Limitations & Next Steps
### Title: Operational Realities & Future Roadmap
- **Technical & Design Trade-Offs**:
  - *Server-Rendered Templates (Jinja2/FastAPI) vs. SPA*: Prioritized zero-dependency local execution, instant startup, and strict reproducibility over client-side reactivity.
  - *Multi-Route Storage Redundancy*: Deliberately permitted multi-route exports and higher category counts in exchange for eliminating lost support escalations.
- **Known Limitations**:
  - *Single-Date Scope*: All data covers 21 August 2026 IST; multi-day trend analysis requires expanding batch window.
  - *Static Pre-Generated Analyses*: Analyses are point-in-time snapshots. When transcripts update (e.g. M07), records are flagged `stale` and queued for `needs_review`.
- **Immediate Next Steps**:
  - Integrate live webhook listener for real-time telephony stream ingestion.
  - Implement bidirectional CRM push for route corrections and verified next-step tasks.
