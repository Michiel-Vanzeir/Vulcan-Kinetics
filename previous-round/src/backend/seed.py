"""Sample org + knowledge. Usage: python seed.py [--reset]"""
import sys
from datetime import datetime
from app import services
from app.db import get_driver
from app.models import CreateNodeIn, KnowledgeIn


def node(type_, name, summary, parents=(), **contact):
    return services.create_node(
        CreateNodeIn(type=type_, name=name, summary=summary, parent_ids=[p["id"] for p in parents], **contact)
    )["id"]


def know(title, summary, keywords, importance, when, source_type, uri, holders, supersedes=None):
    return services.add_knowledge(KnowledgeIn(
        title=title, summary=summary, keywords=keywords, importance=importance,
        occurred_at=datetime.fromisoformat(when), source_type=source_type, source_uri=uri,
        holder_ids=holders, supersedes_id=supersedes,
    ))["id"]


def main():
    with get_driver().session() as s:
        if "--reset" in sys.argv:
            s.run("MATCH (n) DETACH DELETE n").consume()
        elif s.run("MATCH (n:OrgNode) RETURN count(n) AS c").single()["c"] > 0:
            sys.exit("Database already has data. Re-run with --reset to wipe and reseed.")

    # Wrap ids as dicts so node() can take parents uniformly
    w = lambda i: {"id": i}
    eng = node("Department", "Engineering", "Builds and runs the company's software systems.")
    prod = node("Department", "Product", "Owns product strategy, design and user research.")
    pay = node("Project", "Payments Platform", "Cross-department project rebuilding payment processing and checkout.", [w(eng), w(prod)])
    mob = node("Project", "Mobile App", "Consumer iOS and Android app.", [w(prod)])
    core = node("Team", "Payments Core", "Backend services for charging, refunds and ledgers.", [w(pay)])
    cux = node("Team", "Checkout UX", "Designs and builds the checkout experience.", [w(pay)])
    ios = node("Team", "iOS", "Builds the native iOS app.", [w(mob)])
    fraud = node("Subteam", "Fraud Detection", "Models and rules that flag fraudulent transactions.", [w(core)])
    alice = node("Person", "Alice Nguyen", "ML engineer focused on fraud scoring models.", [w(fraud)], email="alice@example.com", phone="+1-555-0101")
    bob = node("Person", "Bob Martin", "Backend engineer; owns the ledger and refund services.", [w(core)], email="bob@example.com")
    carol = node("Person", "Carol Diaz", "Designer working on checkout flows and A/B tests.", [w(cux)], email="carol@example.com")
    dave = node("Person", "Dave Okafor", "iOS engineer; Apple Pay and in-app purchases.", [w(ios)], email="dave@example.com")
    erin = node("Person", "Erin Schulz", "Product manager for checkout and mobile payments.", [w(cux), w(ios)], email="erin@example.com", phone="+1-555-0105")

    know("Fraud model v1 thresholds", "Fraud score threshold set at 0.8; transactions above are auto-declined.",
         ["fraud", "threshold", "model"], 3, "2026-01-10T09:00:00", "document", "docs://fraud-v1", [alice])
    v1 = know("Fraud model v2 retraining", "Fraud model retrained on 2025 chargebacks; threshold lowered to 0.7.",
              ["fraud", "retraining", "chargebacks"], 4, "2026-03-02T14:00:00", "email", "mail://fraud-v2", [alice])
    know("Fraud model v3 rollout", "v3 adds device fingerprinting; threshold now 0.65 with manual review band.",
         ["fraud", "device fingerprint", "review"], 5, "2026-06-20T11:30:00", "slack", "slack://fraud-v3", [alice, fraud], supersedes=v1)
    know("Ledger double-entry migration", "Ledger moved to double-entry bookkeeping; refunds now post reversing entries.",
         ["ledger", "refunds", "accounting"], 5, "2026-04-15T10:00:00", "document", "docs://ledger", [bob])
    know("Refund SLA", "Refunds must settle within 5 business days; escalation goes to Payments Core.",
         ["refunds", "sla", "settlement"], 3, "2026-02-01T08:00:00", "document", "docs://refund-sla", [core])
    know("Checkout A/B test: one-page vs multi-step", "One-page checkout raised conversion by 4%; rollout approved.",
         ["checkout", "ab test", "conversion"], 4, "2026-05-05T13:00:00", "slack", "slack://checkout-ab", [carol])
    know("Apple Pay integration plan", "Apple Pay integrated via payment sheet; needs merchant ID renewal in Q4.",
         ["apple pay", "ios", "merchant id"], 4, "2026-05-28T16:00:00", "email", "mail://apple-pay", [dave])
    know("Mobile payments roadmap", "H2 roadmap: Apple Pay, Google Pay and saved cards across mobile checkout.",
         ["roadmap", "mobile", "payments"], 4, "2026-06-01T09:30:00", "document", "docs://mobile-roadmap", [erin])
    know("PCI compliance audit", "Annual PCI-DSS audit passed; tokenization vendor contract renewed.",
         ["pci", "compliance", "audit", "tokenization"], 5, "2026-03-20T12:00:00", "document", "docs://pci", [pay])
    know("Payment retries policy", "Failed card payments retried 3 times over 72 hours before cancelling.",
         ["retries", "failed payments", "billing"], 2, "2026-02-18T15:00:00", "slack", "slack://retries", [bob, core])

    print("Seeded. Try: curl 'http://localhost:5000/who-knows?q=fraud model threshold'")
    print("Engineering department id:", eng)


if __name__ == "__main__":
    main()
