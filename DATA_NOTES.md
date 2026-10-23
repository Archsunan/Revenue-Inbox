# DATA_NOTES.md — Phase 0 Findings
> Derived exclusively from reading `data/01_initial.json` (2 803 lines, 137 795 bytes)
> and `data/02_update.json` (200 lines, 9 235 bytes) in full.
> No external documents (DATA_CONTRACT.md, glossary, etc.) were present in the working
> folder. All interpretations below are inferred directly from the data and the assignment
> brief. Assumptions are flagged explicitly.

---

## 1. Identity Rule

**Rule (inferred):** A record is uniquely identified by the pair `(source_type, source_id)`.

Evidence:
- Every record carries `"source_type": "call" | "meeting"` and a UUID `source_id`.
- The `source_id` equals the nested `payload.id` in every case observed.
- `record_ref` (B01…B20, C01…C10, M01…M14) is a human-readable label present in the
  batch envelope only. It is **not** stable across batches (the update batch reuses "M07"
  for the same UUID as the initial batch). It must **never** be used as an identity key.
- Names (`rep_name`, speaker labels) are display strings — not identity.

**Assumption A1:** `source_type` + `source_id` form the canonical primary key everywhere.
`record_ref` is stored for display only.

---

## 2. Field Meanings and Units

### Calls (source_type = "call")
| Field | Meaning | Unit |
|-------|---------|------|
| `duration_seconds` | Wall-clock length of the call event | **seconds** |
| `talk_time_seconds` | Time with active speech | **seconds** |
| `speaker_count` | Number of distinct speakers detected | integer |
| `segment_count` | Number of speech segments | integer |
| `is_connected` | Whether the call connected to a human | boolean |
| `is_conversation` | Whether a two-way conversation occurred | boolean |
| `observed_outcome` | System-assigned call result label | string enum |
| `is_campaign_call` | Part of a dialler campaign | boolean |
| `first_dial_ever` / `first_connect_ever` | First time this rep reached this number | boolean |
| `prior_dials_ever` / `prior_connects_ever` | Historical contact count | integer |
| `transcript` | Flat string of conversation text (inline) | string or null |
| `transcript_payload` | Always null for calls in these batches | null |

**Note B13 anomaly:** `duration_seconds: 4` but `talk_time_seconds: 5`. Talk_time exceeds
duration — data quality artefact. Flag in UI; do not compute ratios assuming talk_time ≤ duration.

### Meetings (source_type = "meeting")
| Field | Meaning | Unit |
|-------|---------|------|
| `duration_seconds` | Recorded/scheduled duration | **seconds** |
| `starts_at` / `ends_at` | UTC timestamps | ISO 8601 UTC |
| `attendee_count` | Attendees **besides** the organiser | integer |
| `recording_status` | "recorded" / "cancelled" / "not_scheduled" | string |
| `has_transcript` / `has_video` | Media availability flags | boolean |
| `transcript_payload.turns[].starts_at_seconds` | Turn offset from recording start | **seconds** (float) |
| `transcript_payload.turns[].timecode` | HH:MM:SS offset | string |
| `transcript_payload.unavailable_reason` | Null or explanation string | string or null |
| `organizer_email` | Email of meeting organiser | string |

**Assumption A2:** Turn numbers are 1-indexed (turn 1 = first element of turns array).

---

## 3. Timestamp Semantics and Timezone

- All `started_at` (calls) and `starts_at`/`ends_at` (meetings) are in **UTC** (Z suffix).
- **Assignment date: 21 August 2026 in Asia/Kolkata (IST = UTC+5:30).**
- IST midnight = 2026-08-20T18:30:00Z; end of day = 2026-08-21T18:29:59Z.
- Every record's UTC timestamp converts to 21 Aug 2026 IST.
- Batch `exported_at` values (08-22 IST) are the next day — activity date is Aug 21.

**Assumption A3:** All local-date filtering uses Asia/Kolkata (UTC+5:30). UI displays IST; DB stores UTC.

---

## 4. Status Values

### Call `observed_outcome`
| Value | Meaning |
|-------|---------|
| `voicemail` | Reached voicemail; no human answered |
| `unresponsive` | Connected but no response / hung up quickly |
| `uninterested` | Human answered; prospect explicitly not interested |
| `ooo` | Human answered (receptionist); target out of office |
| `follow_up` | Human answered; agreed/offered to follow up |
| `referred` | Human answered; referred rep to another contact |

### Meeting `recording_status`
| Value | Meaning |
|-------|---------|
| `recorded` | Recording and transcript attempted |
| `cancelled` | Notetaker cancelled before meeting started |
| `not_scheduled` | No notetaker ever set up |

### Meeting `summary_status`: "stored" / "failed" (M01) / "pending" (M06) / null (unrecorded)

### Batch `revision`: initial = 1, update = 2.

**Revision rule (inferred):** Incoming revision strictly > stored → update. Equal/older → no-op.
Late transcript in higher-revision batch attaches to existing record; count stays 44.

---

## 5. Counts by Source Type

### Initial batch — 44 records total (30 calls + 14 meetings) ✓

**Calls: 30**
| Group | refs | Count | Has transcript |
|-------|------|-------|---------------|
| Short/no-answer (voicemail/unresponsive) | B01–B20 | 20 | 0 |
| Conversational | C01–C10 | 10 | 10 (inline string) |

**Meetings: 14**
| ref | Title (abbreviated) | Turns | Status |
|-----|---------------------|-------|--------|
| M01 | Harborpath Advisory | 27 | Usable |
| M02 | LedgerBridge | 30 | Usable |
| M03 | Asterloom Systems | 30 | Usable |
| M04 | Cedarwave Distribution | 25 | Usable |
| M05 | Pinehaven Studio setup | 0 | Silent recording |
| M06 | Mapletrail Services | 27 | Usable |
| M07 | Willowfield Trust | 0 | Deferred to update batch |
| M08 | Amberleaf Health demo | 0 | Silent recording |
| M09 | Account setup & workflow | 26 | Usable |
| M10 | Billing workflow walkthrough | 18 | Usable (internal only) |
| M11 | Internal design discussion | 0 | Silent recording |
| M12 | Sample account setup | 0 | Notetaker cancelled |
| M13 | Cedarwave Migration | 0 | No notetaker |
| M14 | CRM demonstration | 0 | Notetaker cancelled |

### After update batch: 18 usable transcripts (M07 added), record count still 44.

---

## 6. Null / Empty Fields Inventory

### Calls
- `transcript`: null for B01–B20 (short calls)
- `transcript_payload`: null for ALL 30 calls (calls use inline string)
- `summary`: null for all 30 calls
- `classification_reason`: null for all 30 calls
- `rep_user_id`: null for Leela's records (workspace-02) + some others

### Meetings
- `recording_detail`: null except M12, M13, M14 (populated only when recording cancelled/missing)
- `recording_id`: null for M12, M13, M14
- `summary`: null for all 14 meetings
- `summary_status`: null for M12, M13, M14 (no recording)

---

## 7. Label vs Transcript Disagreements

### C02 — `ooo` label, `is_conversation: true`
Transcript: Rep reaches a receptionist (Kavya) who says target is not in the office.
Assessment: `ooo` is correct, but `is_conversation: true` overstates — this is a gatekeeper
interaction, not a sales conversation. Coaching note: rep handled the gatekeeper professionally.

### C04 — `is_connected: false` with `speaker_count: 2`
Transcript: Rep navigates an automated screening system ("Please record your name...") then
leaves voicemail for Ritesh at Lanternpath Media.
Assessment: The automated system's prompts were counted as a second speaker. Internal
inconsistency: `is_connected: false` but `speaker_count: 2` and `segment_count: 8`.
**Flag this record** — the screener interaction makes call metadata misleading.

### C03 — `observed_outcome: "follow_up"` appears optimistic
Transcript: Very poor audio quality (roaming). Milan (prospect) offers email and "maybe
Monday" but is non-committal about interest. Label is not strictly wrong, but overstates
the strength of the commitment. Coaching opportunity: poor call quality degraded outcome.

### M07 (initial) — `has_transcript: true` but no usable transcript
Intentional deferred delivery, not a real conflict. UI must handle the state "flagged as
having transcript, but delivery pending". Resolved by update batch.

---

## 8. Duplicate-Looking Records

### M04 vs M13 — Both Cedarwave Distribution, same day
- M04: starts 09:00 UTC, recorded, 33 min, has transcript.
- M13: starts 08:30 UTC, no notetaker, 60 min (scheduled).
- Different source_ids → NOT duplicates. Two separate meetings with the same customer.

### B02/B06/B08/B11 — Multiple inbound calls from PHONE-003 to Leela
- Sequential calls within minutes; `prior_connects_ever` values are inconsistent (later
  calls show lower counts). NOT duplicates — separate events. Data quality issue flagged.

---

## 9. Multi-Purpose Conversations

### M04 — Cedarwave Distribution
Covers: (1) card programme migration, (2) credit vs prepaid question, (3) system integration,
(4) accounting sync, (5) user/department management. Must receive multiple routes.

### M09 — Account setup and workflow discussion
Covers: (1) Brookmint Holdings login broken (reset token expired), (2) Northkite Equipment
accounting correction, (3) role/permission design for shared mailbox. Two customer companies.

### M10 — Billing workflow walkthrough
**Entirely internal SpendNest training session.** All speakers are "Team member". No external
customer. Must be routed as "internal/vendor note" with clear warning in UI.

### M02 — LedgerBridge
SpendNest is **the buyer** evaluating LedgerBridge as a vendor. This is NOT a sales call
to a customer. Route as "internal/vendor note" or "strategic product decision".

---

## 10. Role Distinctions

### Calls
- `rep_email`/`rep_name` = SpendNest representative (Arun, Leela, Kiran, Meera, Dev)
- **Leela's `rep_user_id` is null** — data quality issue; identify by email

### Meetings
- `organizer_email` = SpendNest team member who created the meeting (team##@example.com or arun@)
- **Organiser ≠ salesperson.** Do not call organiser "salesperson" or "rep".
- Speaker labels: "Team member A/B/C" = SpendNest; "Customer A/B", "Partner A", "Supplier A" = external
- `attendee_count` = external attendees only
- M10 and M14: all participants appear internal (team##); attendee_count is misleading

---

## 11. Assumptions Log

| ID | Ambiguity | Assumption |
|----|-----------|-----------|
| A1 | record_ref looks like an ID | Never use as identity; display only |
| A2 | Turn numbers not in data | 1-indexed from array position |
| A3 | UI timezone | Asia/Kolkata (UTC+5:30) throughout |
| A4 | Update payload identical — full or partial replace? | Full replacement of payload + transcript when revision strictly higher |
| A5 | B13: talk_time > duration | Data anomaly; flag; no ratio calculations |
| A6 | Leela rep_user_id = null | Data quality; identify Leela by email |
| A7 | prior_connects_ever inconsistency in B series | Accept from source; flag in UI |
| A8 | M04 vs M13 same customer same day | Two distinct events; analyse M04 only |
| A9 | batch `revision` is batch-level not record-level | Each record inherits batch revision for conflict resolution |
| A10 | M02: SpendNest is the buyer | Route as internal/vendor note |
| A11 | C04: is_connected=false with speaker_count=2 | Automated screener caused inconsistency; label as screener voicemail |
| A12 | Call transcripts are flat strings | Quote extraction uses substring search; turns approximated |

---

## 12. Summary Counts

| Category | Count |
|----------|-------|
| Total records | **44** |
| Calls | 30 |
| Meetings | 14 |
| Usable transcripts — initial batch | **17** |
| Usable transcripts — after update | **18** |
| No usable text | 26 |
| Silent recordings (meetings) | 3 (M05, M08, M11) |
| No recording at all (meetings) | 3 (M12, M13, M14) |
| Transcript deferred → resolved by update | 1 (M07) |
| Calls: no transcript | 20 (B01–B20) |
| Calls: with transcript | 10 (C01–C10) |
| Reps (calls) | 5 (Arun, Leela, Kiran, Meera, Dev) |
| Label vs transcript conflicts | 3+ (C02, C04, C03) |
| Multi-purpose conversations | 4 (M02, M04, M09, M10) |

*Phase 0 complete. Ready to proceed to Phase 1: Architecture.*
