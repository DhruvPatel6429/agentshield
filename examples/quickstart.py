"""
AgentShield — 2-minute quickstart.

Run with:  python examples/quickstart.py
(from the project root, after `pip install -e .`)

This simulates an agent tool that "sends a payment," guarded by the
example policy in policies/default.yaml, which caps billing-bot at $500
per action. It shows an allowed action, a blocked action, and a flagged
action, plus the resulting audit trail.
"""

from agentshield import AgentShield, AgentShieldBlockedAction

shield = AgentShield(
    policy_path="policies/default.yaml",
    audit_log_path="audit_log.jsonl",
)


@shield.guard(agent_id="billing-bot")
def send_payment(amount: float, currency: str, recipient: str) -> str:
    return f"Sent {amount} {currency} to {recipient}"


@shield.guard(agent_id="billing-bot")
def delete_file(path: str) -> str:
    return f"Deleted {path}"


if __name__ == "__main__":
    print("1) A normal, small payment (should be ALLOWED):")
    print("   ->", send_payment(amount=50, currency="USD", recipient="vendor@example.com"))

    print("\n2) A payment over billing-bot's $500 limit (should be BLOCKED):")
    try:
        send_payment(amount=1200, currency="USD", recipient="unknown@example.com")
    except AgentShieldBlockedAction as e:
        print("   -> Blocked as expected:", e)

    print("\n3) A file deletion (policy says: always FLAG, but still executes):")
    print("   ->", delete_file(path="/tmp/old_report.csv"))

    print("\n--- Audit log summary ---")
    for event in shield.audit_log.all_events():
        print(
            f"[{event.decision.value.upper():5}] {event.action.action_name} "
            f"params={event.action.parameters} reason={event.reason}"
        )

    print(f"\nFull audit trail also written to: audit_log.jsonl ({len(shield.audit_log)} events)")
