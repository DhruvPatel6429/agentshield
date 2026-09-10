from agentshield.risk_scoring import BaselineRiskScorer
from agentshield.schemas import Action


def _payment(amount: float, agent_id: str = "billing-bot") -> Action:
    return Action(action_name="send_payment", parameters={"amount": amount}, agent_id=agent_id)


def test_no_history_yields_zero_score():
    scorer = BaselineRiskScorer()
    result = scorer.score(_payment(100))
    assert result.score == 0.0


def test_consistent_history_then_normal_value_scores_low():
    scorer = BaselineRiskScorer(min_samples_for_zscore=5)
    for amount in [100, 105, 98, 102, 101]:
        scorer.observe(_payment(amount))

    result = scorer.score(_payment(103))
    assert result.score < 0.2


def test_wildly_different_value_scores_high():
    scorer = BaselineRiskScorer(min_samples_for_zscore=5)
    for amount in [100, 105, 98, 102, 101]:
        scorer.observe(_payment(amount))

    result = scorer.score(_payment(50000))
    assert result.score > 0.5
    assert result.top_factors  # explanation provided


def test_unseen_categorical_value_flagged():
    scorer = BaselineRiskScorer()
    action1 = Action(
        action_name="send_email", parameters={"domain": "internal.company.com"}, agent_id="a"
    )
    scorer.observe(action1)

    action2 = Action(action_name="send_email", parameters={"domain": "totally-new.biz"}, agent_id="a")
    result = scorer.score(action2)
    assert result.score > 0
    assert "never been used" in result.top_factors[0]


def test_scores_are_per_agent_isolated():
    scorer = BaselineRiskScorer(min_samples_for_zscore=5)
    for amount in [100, 105, 98, 102, 101]:
        scorer.observe(_payment(amount, agent_id="billing-bot"))

    # A different agent has no history yet — should not inherit billing-bot's baseline
    result = scorer.score(_payment(100000, agent_id="research-bot"))
    assert result.score == 0.0
