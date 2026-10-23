import json
from pathlib import Path
from app.db import get_conn
from app.quote_validator import validate_analyses_all

def main():
    with get_conn() as conn:
        records = conn.execute("""
            SELECT r.source_type, r.source_id, r.record_ref, r.batch_revision,
                   ra.suggested_routes, t.transcript_text, t.turns_json
            FROM source_record r
            JOIN route_assignment ra ON r.source_type=ra.source_type AND r.source_id=ra.source_id
            LEFT JOIN transcript t ON r.source_type=t.source_type AND r.source_id=t.source_id
            WHERE r.has_usable_transcript = 1
            ORDER BY r.source_type, r.record_ref
        """).fetchall()

    rec_map = {r["record_ref"]: dict(r) for r in records}
    analyses = []

    # Helper to create analysis item
    def add_item(ref, route, summary, evidence, not_est, next_step, rev=None):
        rec = rec_map[ref]
        analyses.append({
            "source_type": rec["source_type"],
            "source_id": rec["source_id"],
            "record_ref": ref,
            "route": route,
            "generated_from_revision": rev if rev is not None else rec["batch_revision"],
            "summary": summary,
            "evidence": evidence,
            "not_established": not_est,
            "next_step": next_step
        })

    # C01
    add_item(
        "C01", "needs_human_decision",
        "Cold outreach to Pranav regarding Harborlight Advisory. Prospect expressed strong dissatisfaction at being contacted without opt-in and stated finance operations are already automated.",
        [
            {"label": "Prospect refusal", "quote": "I don't know how I ended up on your list. I didn't ask for this call, and I'm not interested."},
            {"label": "Existing automation", "quote": "Our processes are already very automated. We have a fairly advanced setup, so I don't think this is something we need."}
        ],
        "Whether Harborlight Advisory has other decision makers or if contact was removed from list.",
        {"action": "Verify list acquisition origin and mark Pranav as do-not-contact.", "owner": None}
    )

    # C02
    add_item(
        "C02", "needs_human_decision",
        "Call to Fernhaven Group answered by receptionist Kavya. Target contact Leela was out of office; rep transferred to voicemail.",
        [
            {"label": "Gatekeeper response", "quote": "It looks as though she isn't in the office today. Would you like to leave a message with me, or would you prefer her voicemail?"},
            {"label": "Rep routing choice", "quote": "Her voicemail would be fine, thank you."}
        ],
        "Whether Leela listened to the voicemail or will call back. Stored 'is_conversation: true' is misleading for a gatekeeper interaction.",
        {"action": "Log gatekeeper touchpoint and re-attempt contact next week.", "owner": None}
    )

    # C03
    add_item(
        "C03", "deal_next_steps",
        "Follow-up call by Kiran to Milan regarding API developer access and event notifications. Milan was travelling outdoors on roaming with poor audio quality; expressed price sensitivity and suggested connecting by email or early next week.",
        [
            {"label": "Price sensitivity", "quote": "We did ask about some developer functionality, but it isn't essential enough for us to spend much on it."},
            {"label": "Next conversation window", "quote": "Send the email and we can speak Monday or Tuesday."}
        ],
        "Specific budget amount, exact team size, or firm purchase commitment.",
        {"action": "Send follow-up email titled 'Developer access and event notifications — follow-up' and call back Monday.", "owner": "Kiran"}
    )

    # C04
    add_item(
        "C04", "needs_human_decision",
        "Call to Lanternpath Media handled by an automated call screener. Rep Arun left a voicemail for Ritesh regarding previous expense software discussion and a corrected email address.",
        [
            {"label": "Automated screener", "quote": "Please record your name and the purpose of your call so the recipient can decide whether to answer."},
            {"label": "Screener outcome", "quote": "The person you called is unavailable. You may leave a further message after the signal."},
            {"label": "Rep voicemail context", "quote": "My understanding is that our information first went to the wrong email address."}
        ],
        "Whether Ritesh reviewed the resent proposal. Stored 'speaker_count: 2' counted the automated screener system as a speaker.",
        {"action": "Check email delivery metrics and wait for prospect reply before next dial.", "owner": None}
    )

    # C05
    add_item(
        "C05", "needs_human_decision",
        "Cold sales call by Meera offering store expense and vendor management software. Prospect indicated they already use StoreHarbor and other internal tools, but agreed to receive a presentation via email.",
        [
            {"label": "Proposal request", "quote": "What I suggest is that you send me your presentation. If we ever decide to change the providers we already have, we could consider it then."},
            {"label": "Email confirmation", "quote": "I have an email address noted down; may I confirm contact05@example.com?"}
        ],
        "Active buying intent, dissatisfaction with current providers, or budget.",
        {"action": "Send standard product overview deck to contact05@example.com.", "owner": "Meera"}
    )

    # C06
    add_item(
        "C06", "sales_coaching",
        "Cold outreach by Ravi to Nikhil regarding store expenses for retail/distribution business (>120 stores). Prospect explained their essential processes are already automated and managed centrally by head office; declined further discussion.",
        [
            {"label": "Current automation status", "quote": "We have quite a lot of automation, with a mixed model where needed."},
            {"label": "Central governance", "quote": "Head office manages it, and we have full visibility. That is why I said the arrangements are already in place."}
        ],
        "Specific vendor platforms used, renewal dates, or departmental dissatisfaction.",
        {"action": "Log account notes noting high automation and central head-office management; do not pursue immediate follow-up.", "owner": None}
    )

    # C07
    add_item(
        "C07", "support_account_admin",
        "Outreach call by Dev to Aditya at Willowbank Advisory regarding partnering to offer virtual business accounts to newly incorporated companies. Aditya agreed to review proposal over messaging app and take a call on Monday.",
        [
            {"label": "Partnership inquiry", "quote": "We'd like to partner with advisory firms such as yours so your clients can access a virtual business account after incorporation."},
            {"label": "Delivery channel", "quote": "Sorry, could you message me on our chat app and send whatever proposal you have?"},
            {"label": "Follow-up agreement", "quote": "Once you've received them, could I call on Monday to see whether you'd like to discuss it further? Yes, that's fine."}
        ],
        "Client incorporation volumes, revenue share terms, or regulatory jurisdictions supported.",
        {"action": "Send partnership proposal over messaging app and follow up by phone on Monday.", "owner": "Dev"}
    )

    # C08
    add_item(
        "C08", "deal_next_steps",
        "Cold introduction by Meera to Raghav regarding expense software. Raghav noted a frontline/people operations colleague deals with location processes and offered their email for a proposal.",
        [
            {"label": "Internal referral", "quote": "The colleague handling our people operations also deals with frontline processes and the locations."},
            {"label": "Referral permission", "quote": "If you send him a proposal and say you spoke with me, he can take a look."},
            {"label": "Email destination", "quote": "It's contact08@example.com."}
        ],
        "Specific pain points, software currently in use, or budget.",
        {"action": "Send tailored proposal to contact08@example.com referencing discussion with Mr Raghav.", "owner": "Meera"}
    )

    # C09
    add_item(
        "C09", "needs_human_decision",
        "Cold call by Meera to Vedant (>130 store chain). Vedant explained software was developed internally and referred rep to business head Mr Rishabh on professional network, but requested his own name not be mentioned.",
        [
            {"label": "Internal system in place", "quote": "We have developed our own software internally, so at present we aren't looking for anything outside the organisation."},
            {"label": "Referral to business head", "quote": "If you want to speak to somebody about it, you can find our business head, Mr Rishabh, on a professional networking site."},
            {"label": "Name usage constraint", "quote": "No, please don't use my name."}
        ],
        "Whether Mr Rishabh has identified gaps in the internal software or is open to external vendors.",
        {"action": "Conduct outreach to Mr Rishabh without referencing Vedant.", "owner": None}
    )

    # C10
    add_item(
        "C10", "customer_follow_up",
        "Cold call by Meera to Aniket inquiring about Meadowbrick. Aniket stated he left Meadowbrick and now works in manufacturing; agreed to receive a brief on messaging app but declined a scheduled follow-up call.",
        [
            {"label": "Job change", "quote": "Are you calling about Meadowbrick? Yes, that's right. I don't work there anymore."},
            {"label": "Brief request", "quote": "send an explanation of what you do. I will get back to you."},
            {"label": "Refusal of scheduled follow-up", "quote": "No. I said I will contact you if there is anything to discuss."}
        ],
        "Current company name, role/title, or purchasing authority at new manufacturing employer.",
        {"action": "Send product overview brief via messaging app; do not schedule unsolicited outbound call.", "owner": "Meera"}
    )

    # M01
    add_item(
        "M01", "deal_next_steps",
        "Partnership exploration meeting with Harborpath Advisory on remote corporate bank account opening. Partner A expressed interest in offering client accounts and suggested co-marketing/podcasts.",
        [
            {"label": "Core inquiry", "turn_number": 1},
            {"label": "Business eligibility boundary", "turn_number": 2},
            {"label": "Co-marketing initiative", "turn_number": 26},
            {"label": "Agreed follow-up", "turn_number": 28}
        ],
        "Client referral volume, compliance onboarding timeline, or commercial rev-share agreements.",
        {"action": "Send partner information pack and connect Partner A with marketing regarding podcast and client spotlight.", "owner": "Team member A"}
    )
    add_item(
        "M01", "support_account_admin",
        "Clarified business verification and KYC prerequisites for registered corporate entities versus personal individual accounts.",
        [
            {"label": "Registered business restriction", "turn_number": 2},
            {"label": "Account opening requirements discussion", "turn_number": 8}
        ],
        "Specific banking partner licenses or overseas jurisdiction support.",
        {"action": "Provide written documentation on entity verification guidelines.", "owner": "Team member A"}
    )

    # M02
    add_item(
        "M02", "deal_next_steps",
        "Partnership and technical integration review with Supplier A covering electronic invoicing, payment templates, and vendor evaluation criteria.",
        [
            {"label": "Initial partnership scope", "turn_number": 1},
            {"label": "Electronic invoicing priority", "turn_number": 3},
            {"label": "Formal evaluation criteria", "turn_number": 34},
            {"label": "Next meeting arrangement", "turn_number": 35}
        ],
        "Commercial contract pricing, SLA terms, or formal partnership sign-off.",
        {"action": "Supplier A to send the integration/evaluation template shortly.", "owner": "Supplier A"}
    )
    add_item(
        "M02", "customer_follow_up",
        "Scheduled follow-up call after completing the vendor integration template to review product fit and commercial alignment.",
        [
            {"label": "Template review call", "turn_number": 35},
            {"label": "Template delivery commitment", "turn_number": 36}
        ],
        "Confirmed date and time for the follow-up meeting.",
        {"action": "Complete vendor template upon receipt and hold explanation call.", "owner": "Team member A"}
    )

    # M03
    add_item(
        "M03", "deal_next_steps",
        "Solution presentation to Asterloom Systems covering corporate cards, employee expense reimbursement, and accounting integration for 65 employees.",
        [
            {"label": "Finance team evaluation", "turn_number": 1},
            {"label": "Product scope: cards and reimbursements", "turn_number": 2},
            {"label": "Company scale and budget priority", "turn_number": 34},
            {"label": "Proposal request", "turn_number": 35},
            {"label": "CFO internal review condition", "turn_number": 36}
        ],
        "CFO approval, decision date, or agreed card limits.",
        {"action": "Send cards proposal and module information to Customer B.", "owner": "Team member A"}
    )

    # M04
    add_item(
        "M04", "deal_next_steps",
        "Migration planning discussion with Cedarwave Distribution regarding physical cards, contactless acceptance issues, wallet payments, and department user management.",
        [
            {"label": "Migration agenda", "turn_number": 1},
            {"label": "Card acceptance difficulties", "turn_number": 2},
            {"label": "Digital wallet expectations", "turn_number": 3},
            {"label": "Department reconciliation issue", "turn_number": 30}
        ],
        "Exact card reissue migration date or accounting software version.",
        {"action": "Customer A to review migration requirements and follow up with team.", "owner": "Customer A"}
    )
    add_item(
        "M04", "support_account_admin",
        "Customer reported database issue where users cannot be moved between departments from standard assistant view, breaking accounting reconciliation.",
        [
            {"label": "Department setup error", "turn_number": 30},
            {"label": "Technical support session requirement", "turn_number": 31}
        ],
        "Resolution timeline or root cause of database permission restriction.",
        {"action": "Arrange session with technical support to review database user department records.", "owner": "Team member A"}
    )

    # M06
    add_item(
        "M06", "deal_next_steps",
        "Exploratory finance discussion with Mapletrail Services branch (50 people) covering branch expenditure, card controls, security, and audit trails.",
        [
            {"label": "Branch operations scope", "turn_number": 2},
            {"label": "Confidentiality and audit concerns", "turn_number": 31},
            {"label": "Compliance controls explanation", "turn_number": 32},
            {"label": "Information request", "turn_number": 33}
        ],
        "Head office buy-in, formal RFP issuance, or total branch budget.",
        {"action": "Send security documentation and platform overview to Customer A.", "owner": "Team member A"}
    )

    # M07 (rev 2)
    add_item(
        "M07", "sales_coaching",
        "Technical support and screen-share session with Willowfield Trust reviewing transaction editing bugs, balance refresh glitches, and receipt attachment workarounds.",
        [
            {"label": "Description update failure", "turn_number": 2},
            {"label": "Bug reproduction confirmation", "turn_number": 3},
            {"label": "Balance display refresh bug", "turn_number": 25},
            {"label": "Workaround and pending fixes", "turn_number": 26}
        ],
        "Release schedule for platform bug fix.",
        {"action": "Send reproduction sequence to engineering team, get confirmation, and report back to customer.", "owner": "Team member A"},
        rev=2
    )

    # M09
    add_item(
        "M09", "support_account_admin",
        "Account setup troubleshooting covering expired invite tokens for Brookmint Holdings, accounting reconciliation for Northkite Equipment, and separate email identities.",
        [
            {"label": "Expired invitation token", "turn_number": 1},
            {"label": "Dual account setup scope", "turn_number": 2},
            {"label": "Token engineering check commitment", "turn_number": 31},
            {"label": "Customer IT follow-up", "turn_number": 32}
        ],
        "Whether Brookmint and Northkite share backend legal entity tax IDs.",
        {"action": "Check expired-token problem with engineering and respond by tomorrow afternoon.", "owner": "Team member A"}
    )
    add_item(
        "M09", "deal_next_steps",
        "Onboarding continuation for Brookmint Holdings and Northkite Equipment once login issues and email identity segregation are addressed.",
        [
            {"label": "Setup resumption", "turn_number": 1},
            {"label": "Training videos review", "turn_number": 30}
        ],
        "Target go-live date for transaction processing.",
        {"action": "Customer A to review onboarding videos before scheduling next walkthrough session.", "owner": "Customer A"}
    )

    # M10
    add_item(
        "M10", "support_account_admin",
        "Internal training walkthrough on billing workflows, subscription lifecycles, account freeze triggers, and operations invoice clearance.",
        [
            {"label": "Training agenda", "turn_number": 3},
            {"label": "Account unfreeze process", "turn_number": 18},
            {"label": "Back-office access request", "turn_number": 20}
        ],
        "Customer-facing communication or pricing discounts.",
        {"action": "Request back-office system access for the next training session.", "owner": "Team member A"}
    )
    add_item(
        "M10", "internal_vendor_note",
        "Internal operational procedure documentation: frozen customer accounts require operations team clearance of outstanding invoices before unfreezing.",
        [
            {"label": "Operations freeze procedure", "turn_number": 18},
            {"label": "Internal note documentation", "turn_number": 20}
        ],
        "Exceptions to standard credit policy.",
        {"action": "Add unresolved questions to internal team notes.", "owner": None}
    )

    out_path = Path("analysis/analyses.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analyses, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(analyses)} analysis entries to {out_path}.")

    # Validate all!
    results = validate_analyses_all(str(out_path))
    failures = [r for r in results if not r.get("valid")]
    print(f"Validation completed: {len(results)} items validated.")
    if failures:
        print(f"ERRORS found ({len(failures)}):")
        for fail in failures:
            print(" ", fail)
    else:
        print("ALL QUOTES AND TURNS VALIDATED 100% SUCCESSFULLY!")

if __name__ == "__main__":
    main()
