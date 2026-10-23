# FINDINGS.md — Key Analytical Discoveries

This document details the three primary analytical and operational findings derived directly from analyzing all 44 records (30 calls, 14 meetings) received for 21 August 2026 (Asia/Kolkata).

---

## Finding 1: Telephony Metadata Conflicts & Automated Screener Misattribution

### Observation
Automated call telemetry from upstream telephony providers routinely produces misleading flags when calls encounter gatekeepers, interactive voice response (IVR) systems, or screening services. Blindly relying on vendor-provided metadata (`is_conversation`, `speaker_count`, `observed_outcome`) leads sales managers to draw false conclusions about rep activity and prospect engagement.

### Exact Supporting Evidence
1. **Record C02 (Call)**:
   - Stored Metadata: `observed_outcome: "ooo"`, `is_conversation: true`, `duration_seconds: 40`.
   - Verbatim Passage:
     > *"It looks as though she isn't in the office today. Would you like to leave a message with me, or would you prefer her voicemail?"*
   - Reality: Rep reached Kavya (receptionist at Fernhaven Group) inquiring for Leela. Leela was out of the office, and the rep was routed to voicemail. Labeling this as `is_conversation: true` artificially inflates rep conversation rates with non-decision-maker gatekeeper dialog.
2. **Record C04 (Call)**:
   - Stored Metadata: `is_connected: false`, `speaker_count: 2`, `segment_count: 8`.
   - Verbatim Passage:
     > *"Please record your name and the purpose of your call so the recipient can decide whether to answer."*
   - Reality: The call encountered Google/Android Call Screening. The screening bot's automated audio prompts were categorized as a second human speaker (`speaker_count: 2`), even though `is_connected` was false.

### Product & Architectural Impact
- **Data Quality (DQ) Flags**: The intake pipeline flags C02 (`gatekeeper_conversation_mismatch`) and C04 (`screener_counted_as_speaker`).
- **Rule-Based Routing**: Rather than automatically pushing C02 or C04 into closed deal pipelines, the router assigns `needs_human_decision` with high confidence flags noting telephony conflict.
- **UI Exposure**: Record detail view shows a high-contrast badge warning the manager: *"Conflict: Metadata says conversation, but transcript indicates gatekeeper/voicemail."*

---

## Finding 2: Multi-Purpose & Multi-Entity Conversations Masking Operational Risk

### Observation
Upstream CRM and calendar integrations assume a 1:1 relationship between an event and an account. In reality, single conversations frequently span multiple commercial workflows or entirely distinct customer entities. Forcing a conversation into a single category causes critical administrative, technical, or compliance issues to be lost.

### Exact Supporting Evidence
1. **Record M04 (Meeting — Cedarwave Distribution)**:
   - Verbatim Passage (Turn 1):
     > *"I wanted to discuss the migration while there is still time to plan it. We should cover the present arrangement, the reasons for switching, what the team expects and the timeline."*
   - Verbatim Passage (Turn 30):
     > *"There is also the earlier issue with moving users between departments. The current department setup creates problems for accounting reconciliation."*
   - Reality: A commercial card migration meeting also contained an urgent unblocking request: accounting cannot reconcile statements because user department transfers fail in the assistant interface.
2. **Record M09 (Meeting — Account Setup)**:
   - Verbatim Passage (Turn 2):
     > *"There are two things to cover: getting you into Brookmint Holdings and the accounting issue you reported earlier for Northkite Equipment."*
   - Verbatim Passage (Turn 31):
     > *"I will check the expired-token problem for Brookmint Holdings with the team and aim to return with an answer by tomorrow afternoon."*
   - Reality: A single scheduled call covered onboarding for **two distinct customer entities** (Brookmint Holdings and Northkite Equipment), with an expired login token blocking one and accounting reconciliation blocking the other.

### Product & Architectural Impact
- **Multi-Route Assignment**: The router supports 0, 1, or multiple orthogonal routes per record. M04 is routed to both `deal_next_steps` and `support_account_admin`.
- **Differentiated Analysis**: Analysis engines generate independent, route-specific deliverables for each stream rather than a blended summary.
- **Relational Export Structure**: The export engine stores files in `exports/by_route/<route>/` while preserving bidirectional cross-links in `exports/by_record/<source_type>_<source_id>/index.md`.

---

## Finding 3: Structural Coverage Gaps and the 18/44 Reality

### Observation
On 21 August 2026, 44 total interactions occurred, but only **18 records** contain usable conversation text (10 calls, 8 meetings after M07 update). Uninformed managers might conclude that 26 interactions were "lost" or that reps underperformed. A detailed forensic intake reveals that missing transcripts stem from multiple distinct operational realities.

### Exact Supporting Evidence
1. **Short/No-Answer Calls (20 records, B01–B20)**:
   - Durations range from 4 seconds to 38 seconds (e.g. B13 duration 4s). No speech was spoken or captured; these represent normal outbound dialer attempts, busy signals, or instantaneous hangups.
2. **Silent Recordings (3 records: M05, M08, M11)**:
   - `recording_status: "recorded"`, `summary_status: "stored"`, but `transcript_payload.turns: []`. Notetakers joined the meeting but captured zero audible speech (e.g., screen share only, muted bridge, or no-show).
3. **Notetaker Failures / Unscheduled (3 records: M12, M13, M14)**:
   - M12 & M14: `recording_status: "cancelled"`, `recording_detail: "Notetaker cancelled by host"`.
   - M13: `recording_status: "not_scheduled"` — customer migration meeting held entirely off the record.
4. **Deferred Transcript Delivery (1 record: M07)**:
   - Initial batch (rev 1) had `has_transcript: true` but `unavailable_reason: "Transcript processing deferred; available in later batch"`. Resolved in update batch (rev 2) with 27 usable turns.

### Product & Architectural Impact
- **Explicit Denominators**: Every headline card displays full context: `18/44 (40.9%) Coverage` broken down as `10/30 Calls` and `8/14 Meetings`.
- **Intake State Machine**: Distinct visual states across UI:
  - `transcript_usable` (Green)
  - `transcript_pending` (Amber)
  - `recorded_but_no_usable_text` (Gray)
  - `no_recording` (Dark Gray)
  - `call_no_transcript` (Dim)
- **Clear Manager Guidance**: A prominent banner reminds the manager: *"A missing transcript does NOT indicate the conversation was cancelled or invalid. Review metadata for attendance and duration."*
