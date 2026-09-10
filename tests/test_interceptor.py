import pytest

from agentshield import AgentShield, Decision
from agentshield.exceptions import AgentShieldBlockedAction


@pytest.fixture
def shield(tmp_path) -> AgentShield:
    s = AgentShield(audit_log_path=tmp_path / "audit.jsonl")
    s.policy_engine.load_from_dict(
        {
            "agents": {
                "billing-bot": [
                    {"field": "amount", "operator": "gt", "value": 500, "action_on_match": "block"},
                ],
            },
        }
    )
    return s


def test_guarded_function_executes_when_allowed(shield: AgentShield):
    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float) -> str:
        return f"sent {amount}"

    assert send_payment(amount=50) == "sent 50"


def test_guarded_function_raises_when_blocked(shield: AgentShield):
    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float) -> str:
        return f"sent {amount}"

    with pytest.raises(AgentShieldBlockedAction):
        send_payment(amount=1200)


def test_blocked_function_body_never_executes(shield: AgentShield):
    calls = []

    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float) -> str:
        calls.append(amount)
        return f"sent {amount}"

    with pytest.raises(AgentShieldBlockedAction):
        send_payment(amount=1200)

    assert calls == []  # function body must never have run


def test_raise_on_block_false_returns_none_instead(tmp_path):
    shield = AgentShield(audit_log_path=tmp_path / "audit.jsonl", raise_on_block=False)
    shield.policy_engine.load_from_dict(
        {"global": [{"field": "amount", "operator": "gt", "value": 500, "action_on_match": "block"}]}
    )

    @shield.guard()
    def send_payment(amount: float) -> str:
        return f"sent {amount}"

    assert send_payment(amount=1200) is None


def test_audit_log_records_every_call(shield: AgentShield):
    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float) -> str:
        return f"sent {amount}"

    send_payment(amount=50)
    try:
        send_payment(amount=1200)
    except AgentShieldBlockedAction:
        pass

    assert len(shield.audit_log) == 2
    decisions = [e.decision for e in shield.audit_log.all_events()]
    assert decisions == [Decision.ALLOW, Decision.BLOCK]


def test_keyword_and_positional_args_both_captured(shield: AgentShield):
    @shield.guard(agent_id="billing-bot")
    def send_payment(amount: float, currency: str = "USD") -> str:
        return f"{amount} {currency}"

    # positional
    assert send_payment(50) == "50 USD"
    # keyword
    assert send_payment(amount=50, currency="INR") == "50 INR"

    event = shield.audit_log.all_events()[-1]
    assert event.action.parameters["amount"] == 50
    assert event.action.parameters["currency"] == "INR"


def test_fail_safe_defaults_to_block_on_internal_error(tmp_path):
    shield = AgentShield(audit_log_path=tmp_path / "audit.jsonl")

    class ExplodingScorer:
        def score(self, action):
            raise RuntimeError("boom")

        def observe(self, action):
            pass

    shield.risk_scorer = ExplodingScorer()

    @shield.guard()
    def do_thing(x: int) -> int:
        return x

    with pytest.raises(AgentShieldBlockedAction):
        do_thing(x=1)


def test_action_name_defaults_to_function_name(shield: AgentShield):
    @shield.guard(agent_id="billing-bot")
    def some_custom_action(amount: float) -> str:
        return "ok"

    some_custom_action(amount=10)
    event = shield.audit_log.all_events()[-1]
    assert event.action.action_name == "some_custom_action"


def test_explicit_action_name_overrides_function_name(shield: AgentShield):
    @shield.guard(agent_id="billing-bot", action_name="wire_transfer")
    def some_custom_action(amount: float) -> str:
        return "ok"

    some_custom_action(amount=10)
    event = shield.audit_log.all_events()[-1]
    assert event.action.action_name == "wire_transfer"
