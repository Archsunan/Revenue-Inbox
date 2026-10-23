# VIDEO_SCRIPT.md — 3-Minute Video Demonstration Script

**Target Duration**: 3:00  
**Presenter**: Candidate  
**Demonstration Scope**: Manager workflow, edge-case routing, idempotent ingestion, late transcript update, and manual override persistence.

---

## [0:00 – 0:35] Part 1: The Manager Workflow & First-Screen Dashboard

### Visual
- Browser open at `http://127.0.0.1:8000/`.
- Hovering over the top metric cards (44 Total Records, 18 Usable Transcripts, 40.9% Coverage, 1 Needs Review).
- Hovering over the Definition popover next to Coverage.

### Spoken Narration
> *"Welcome. As a sales manager reviewing 44 customer interactions across telephony and video meetings on August 21st, 2026, my first priority is answering three questions: What happened today, what needs my immediate attention, and what should I do next?*
>
> *Looking at our dashboard, we immediately see that out of 44 records, exactly 18 have usable conversation text—giving us a real coverage of 40.9%. We state this denominator explicitly because 26 records represent short dials or silent recordings, not failed reps.*
>
> *Our Attention Required tray flags one record needing review and four telephony metadata conflicts. Let’s drill into one of those difficult records right now."*

---

## [0:35 – 1:15] Part 2: Difficult Routing Decision & Evidence Drill-Down

### Visual
- Click on record `C04` in the Records list.
- Show metadata panel (`is_connected: false`, `speaker_count: 2`).
- Scroll down to transcript and highlight the automated screener prompt.
- Show Data Quality Flag: *"screener_counted_as_speaker"*.
- Point to the Route Assignment badge: `needs_human_decision`.
- Click on the Route Correction button and select `customer_follow_up`. Add reason: *"Ritesh voicemail left by Arun; follow up next week."* Click Save.
- Badge updates from `suggested` to `manual`.

### Spoken Narration
> *"Here is Record C04. Upstream telephony recorded speaker_count as 2, yet is_connected is false. Looking at our transcript, we see why: the call was answered by an automated call screener, which the telephony bot falsely counted as a human conversation.*
>
> *Rather than letting an automated rule file this under closed deals, our deterministic router caught the conflict and assigned 'needs_human_decision'.*
>
> *As manager, I can correct this directly: I open the route modal, tag it as 'customer_follow_up', and save. Notice the badge instantly updates to 'manual' with my timestamp and reason preserved in the audit trail."*

---

## [1:15 – 1:55] Part 3: Idempotent Import Pipeline (CLI Demonstration)

### Visual
- Switch to terminal.
- Run `python -m app import data/01_initial.json --shuffle`.
- Show CLI output: `Inserted=0, Updated=0, Unchanged=44`.
- Switch back to browser, refresh dashboard: Record count remains strictly 44.

### Spoken Narration
> *"Now let's verify data integrity. Upstream systems often re-send batches out of order or re-export existing records.*
>
> *In the terminal, I'm executing a repeat import of our initial batch with shuffled record order. Look at the output: 44 records examined, zero inserted, zero updated, 44 unchanged. Our primary key is strictly composite (source_type, source_id). No duplicates are ever created, and the record count remains rock-solid at 44."*

---

## [1:55 – 2:35] Part 4: Late Transcript Delivery & Staleness Flag (M07)

### Visual
- In terminal, run `python -m app import data/02_update.json`.
- Output: `Batch: update-002 (rev=2), Inserted=0, Updated=1`.
- Switch to browser, refresh dashboard:
  - Usable transcripts counter moves from 17 to 18.
  - Stale Analysis badge appears under Attention Required.
- Click into `M07`:
  - Show 27 turns attached to the record.
  - Show analysis card with amber badge: `⚠ STALE — transcript updated`.
  - Show review state: `needs_review`.

### Spoken Narration
> *"Now, let's look at what happens when a late transcript arrives. In batch two, meeting M07 arrives with revision 2.*
>
> *I run the update import. Notice: Inserted is 0, Updated is 1. The total record count stays at 44, but our usable transcript count updates to 18.*
>
> *When we open M07 in the UI, all 27 turns now appear with 1-based index numbers. Because the transcript changed after the initial analysis was generated, the system automatically sets the stale flag to true and routes the record to 'needs_review', preventing the manager from relying on outdated summaries."*

---

## [2:35 – 3:00] Part 5: Manual Override Persistence & Export Generation

### Visual
- Navigate back to `C04`: show that the manual route override (`customer_follow_up`) survived the repeat import and the batch update!
- In terminal, run `python -m app export`.
- Show `exports/` folder structure (`by_route`, `by_record`, `manifest.json`, `exports.zip`).
- Close with view of the Manager Brief page (`/brief`).

### Spoken Narration
> *"Finally, we check record C04 again. Despite re-running imports and updating the database, our manual route correction persists intact.*
>
> *With a single command—python -m app export—we generate our audit manifest and structured folder deliverables, ready for downstream CRM sync.*
>
> *The Revenue Intelligence Inbox turns chaotic, conflicting raw streams into verified, evidence-backed manager action. Thank you."*
