# AgentShield

**An open-source safety and audit firewall for autonomous AI agents.**

AgentShield sits between your AI agent and the real-world actions it takes
(payments, emails, file operations, API calls) and evaluates every one of
them against configurable policies and a behavioral risk score — before
it executes.

```python
from agentshield import AgentShield, AgentShieldBlockedAction

shield = AgentShield(policy_path="policies/default.yaml")

@shield.guard(agent_id="billing-bot")
def send_payment(amount: float, currency: str, recipient: str) -> str:
    return f"Sent {amount} {currency} to {recipient}"

send_payment(amount=1200, currency="USD", recipient="unknown@example.com")
# -> AgentShieldBlockedAction: amount 1200 exceeds billing-bot's $500 limit
```

## Why

Agentic AI is being deployed everywhere — booking, spending, writing and
shipping code, touching customer data — with almost no safety layer
between an agent's decision and its real-world execution. AgentShield is
a framework-agnostic, self-hostable, free way to say "an agent must never
do X" and have it actually enforced, with a full audit trail of every
action attempted.

## Install

```bash
pip install -e .            # core (PyYAML only)
pip install -e ".[dev]"     # + pytest, for running the test suite
pip install -e ".[ml]"      # + xgboost/shap, for the optional higher-fidelity risk scorer
```

## Quickstart

```bash
python examples/quickstart.py
```

This wraps two example agent tools with a policy that caps `billing-bot`
at $500/action and always flags file deletions, then shows an allowed
call, a blocked call, and a flagged call, plus the resulting audit log.

## How it works

1. **Interceptor** — the `@shield.guard()` decorator wraps any function
   (or a LangChain tool via `agentshield.adapters.wrap_langchain_tool`)
   and captures every call's arguments before the function body runs.
2. **Policy Engine** — evaluates the captured arguments against YAML
   rules, in order of precedence: tool-specific → agent-specific →
   global. See `policies/default.yaml` for a full annotated example.
3. **Risk Scorer** — even actions no explicit rule blocks are scored
   against that agent's historical behavior baseline; a high anomaly
   score auto-escalates an action to `FLAG` for human review.
4. **Audit Log** — every evaluated action is recorded (append-only),
   regardless of outcome.

## Project layout

```
agentshield/
├── pyproject.toml
├── README.md
├── policies/
│   └── default.yaml            # example policy file (annotated)
├── src/agentshield/
│   ├── __init__.py              # public API
│   ├── schemas.py                # Action, Decision, EvaluationResult
│   ├── exceptions.py
│   ├── policy_engine.py          # YAML rule loading + evaluation
│   ├── risk_scoring.py           # BaselineRiskScorer + pluggable interface
│   ├── audit_log.py               # append-only event log
│   ├── interceptor.py             # AgentShield class + @guard() decorator
│   └── adapters/
│       └── langchain_adapter.py  # wrap_langchain_tool / guard_langchain_tools
├── tests/
│   ├── test_policy_engine.py
│   ├── test_interceptor.py
│   └── test_risk_scoring.py
└── examples/
    └── quickstart.py
```

## Running tests

```bash
pytest tests/ -v
```

## Roadmap

- [ ] v1: core interceptor + policy engine + LangChain adapter (this repo)
- [ ] v2: web dashboard + audit log export (see the TRD/UI-UX docs in `/docs`)
- [ ] v2: XGBoost + SHAP risk scorer as an opt-in upgrade
- [ ] v3: JS/TS agent framework adapters

## License

MIT
