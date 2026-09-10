import pytest

from agentshield.exceptions import PolicyConfigError
from agentshield.policy_engine import PolicyEngine
from agentshield.schemas import Action, Decision


@pytest.fixture
def engine() -> PolicyEngine:
    e = PolicyEngine()
    e.load_from_dict(
        {
            "global": [
                {"field": "amount", "operator": "gt", "value": 5000, "action_on_match": "block"},
            ],
            "agents": {
                "billing-bot": [
                    {"field": "amount", "operator": "gt", "value": 500, "action_on_match": "block"},
                ],
            },
            "tools": {
                "delete_file": [
                    {"field": "path", "operator": "regex", "value": ".*", "action_on_match": "flag"},
                ],
            },
        }
    )
    return e


def test_default_allow_when_nothing_matches(engine: PolicyEngine):
    action = Action(action_name="noop", parameters={"amount": 10}, agent_id="billing-bot")
    decision, reason, matched = engine.evaluate(action)
    assert decision == Decision.ALLOW
    assert matched is None


def test_agent_scoped_rule_blocks(engine: PolicyEngine):
    action = Action(action_name="send_payment", parameters={"amount": 1200}, agent_id="billing-bot")
    decision, reason, matched = engine.evaluate(action)
    assert decision == Decision.BLOCK
    assert matched == "agents.billing-bot"


def test_global_rule_applies_to_other_agents(engine: PolicyEngine):
    # research-bot has no agent-specific rule, so it falls through to global
    action = Action(action_name="send_payment", parameters={"amount": 6000}, agent_id="research-bot")
    decision, reason, matched = engine.evaluate(action)
    assert decision == Decision.BLOCK
    assert matched == "global"


def test_agent_limit_is_stricter_than_global_limit(engine: PolicyEngine):
    # 1200 is under the global 5000 ceiling but over billing-bot's 500 cap
    action = Action(action_name="send_payment", parameters={"amount": 1200}, agent_id="billing-bot")
    decision, _, matched = engine.evaluate(action)
    assert decision == Decision.BLOCK
    assert matched == "agents.billing-bot"


def test_tool_scope_takes_precedence_over_agent_and_global(engine: PolicyEngine):
    action = Action(action_name="delete_file", parameters={"path": "/tmp/x.csv"}, agent_id="billing-bot")
    decision, _, matched = engine.evaluate(action)
    assert decision == Decision.FLAG
    assert matched == "tools.delete_file"


def test_missing_field_never_matches(engine: PolicyEngine):
    action = Action(action_name="send_payment", parameters={"currency": "USD"}, agent_id="billing-bot")
    decision, _, matched = engine.evaluate(action)
    assert decision == Decision.ALLOW


def test_invalid_operator_raises_policy_config_error():
    e = PolicyEngine()
    with pytest.raises(PolicyConfigError):
        e.load_from_dict(
            {"global": [{"field": "x", "operator": "bogus", "value": 1, "action_on_match": "block"}]}
        )


def test_invalid_action_on_match_raises_policy_config_error():
    e = PolicyEngine()
    with pytest.raises(PolicyConfigError):
        e.load_from_dict(
            {"global": [{"field": "x", "operator": "eq", "value": 1, "action_on_match": "bogus"}]}
        )


def test_missing_required_key_raises_policy_config_error():
    e = PolicyEngine()
    with pytest.raises(PolicyConfigError):
        e.load_from_dict({"global": [{"field": "x", "operator": "eq", "action_on_match": "block"}]})


@pytest.mark.parametrize(
    "operator,value,param_value,expected",
    [
        ("gt", 10, 15, True),
        ("gt", 10, 5, False),
        ("gte", 10, 10, True),
        ("lt", 10, 5, True),
        ("lte", 10, 10, True),
        ("eq", "USD", "USD", True),
        ("neq", "USD", "INR", True),
        ("in_list", ["USD", "INR"], "INR", True),
        ("in_list", ["USD", "INR"], "GBP", False),
        ("contains", "example.com", "user@example.com", True),
        ("regex", r"^\d+$", "12345", True),
        ("regex", r"^\d+$", "abc123", False),
    ],
)
def test_operators(operator, value, param_value, expected):
    e = PolicyEngine()
    e.load_from_dict(
        {"global": [{"field": "x", "operator": operator, "value": value, "action_on_match": "block"}]}
    )
    action = Action(action_name="t", parameters={"x": param_value}, agent_id="a")
    decision, _, _ = e.evaluate(action)
    assert (decision == Decision.BLOCK) == expected


def test_type_mismatch_fails_closed_to_no_match():
    e = PolicyEngine()
    e.load_from_dict(
        {"global": [{"field": "x", "operator": "gt", "value": 10, "action_on_match": "block"}]}
    )
    action = Action(action_name="t", parameters={"x": "not-a-number"}, agent_id="a")
    decision, _, _ = e.evaluate(action)
    assert decision == Decision.ALLOW
