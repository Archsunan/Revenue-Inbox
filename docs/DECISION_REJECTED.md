# DECISION_REJECTED.md — Architectural & Product Decision Trade-Off

## Rejected Alternative
**Single-Category Exclusive Classification ("One Route per Conversation")**

In traditional CRM inboxes and revenue intelligence platforms (e.g., Gong, Chorus), activities are assigned to exactly one primary category, stage, or owner folder (e.g., *"Is this deal progression OR customer support?"*). We explicitly evaluated and rejected this single-label paradigm.

---

## Why It Was Rejected

1. **Reality of Real-World Sales Conversations**:
   As discovered in our data profiling (Finding 2), enterprise conversations rarely adhere to neat operational silos:
   - **Record M04 (Cedarwave Distribution)**: Primarily a commercial discussion about migrating physical credit cards to a new programme, but contains an urgent blocker in Turn 30 where accounting statements fail to reconcile due to an internal database permission bug when moving users between departments.
   - **Record M09**: A single 32-turn scheduled meeting addressing two completely distinct corporate entities (**Brookmint Holdings** login failure due to expired auth token, and **Northkite Equipment** tax sync).
   - **Record M01**: A partnership discovery call that concurrently addresses compliance boundaries (KYC for corporate vs personal entities) and co-marketing (recording podcast episodes).

2. **Severe Operational Consequences of Single-Route Assignment**:
   - If M04 is labeled exclusively as `deal_next_steps`, the technical support escalation is buried, customer statements remain broken, and the account is placed at severe risk of churn.
   - If M04 is labeled exclusively as `support_account_admin`, sales leadership loses visibility into the commercial timeline for reissuing physical cards.

---

## Trade-Offs Accepted

By adopting **Multi-Route Non-Exclusive Assignment**, we deliberately accepted several trade-offs:

1. **Sum of Routes > Total Records**:
   - The route distribution breakdown in the dashboard sums to more than 44 (or 18 usable records). Managers accustomed to simple pie charts must understand that routes represent actionable workflow items, not mutually exclusive bins.
2. **Export and Storage Redundancy**:
   - A single conversation may generate two or three separate markdown reports in `exports/by_route/`.
   - We mitigated confusion by introducing a unified index in `exports/by_record/<source_type>_<source_id>/index.md` linking all route deliverables back to the source record.
3. **UI Complexity in Route Management**:
   - Route editing requires multi-select checkboxes rather than a simple dropdown select.

---

## Where This Decision Appears in the Product

1. **Database Schema (`app/db.py`)**:
   - `analysis` table uses a composite primary key: `PRIMARY KEY (source_type, source_id, route)`, allowing multiple route-specific analyses per record.
   - `route_assignment` table stores `suggested_routes` and `manual_routes` as serialized JSON arrays rather than single scalar strings.
2. **Deterministic Router (`app/router.py`)**:
   - `compute_routes()` evaluates orthogonal trigger conditions and appends all matched routes to a list.
3. **Manager Dashboard (`app/web/templates/dashboard.html`)**:
   - The Route Distribution card clearly indicates that percentages are calculated against active records and may overlap.
4. **Record Detail Page (`app/web/templates/record_detail.html`)**:
   - Displays multiple route badges; provides an interactive multi-select modal for manual routing override; renders distinct analysis cards for each active route.
5. **Export Manifest (`app/exporter.py`)**:
   - `manifest.json` logs `routes` as a list, and copies files into each respective route directory without losing record provenance.
