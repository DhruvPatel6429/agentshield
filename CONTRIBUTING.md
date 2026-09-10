# Contributing to AgentShield

Thanks for considering a contribution — this project is genuinely shaped by real usage, and adapters/policy examples from real agent stacks are the most valuable kind of PR.

## Getting set up

```bash
git clone https://github.com/DhruvPatel6429/agentshield.git
cd agentshield
pip install -e ".[dev]"
pytest tests/ -v
```

## Ways to contribute

- **New framework adapters** — the adapter interface in `src/agentshield/adapters/` is designed to be extended without touching the core engine. If you use an agent framework AgentShield doesn't support yet, this is the highest-impact contribution you can make.
- **New policy operators** — extend `policy_engine.py`'s `_VALID_OPERATORS` and `PolicyRule.matches()`.
- **Bug reports** — please include a minimal reproduction (a policy YAML + the action that behaved unexpectedly is ideal).
- **Documentation** — more real-world policy examples in `policies/` help everyone.

## Before opening a PR

1. Add or update tests for any behavior change — `pytest tests/ -v` must stay green.
2. Keep the core package dependency-free beyond PyYAML; put anything heavier behind an optional extra (see how `risk_scoring.py` handles the `xgboost`/`shap` optional import).
3. Run `python examples/quickstart.py` to sanity-check nothing broke end-to-end.

CI (`.github/workflows/tests.yml`) runs the full suite automatically across Python 3.10–3.12 on both Ubuntu and Windows when you open a PR.

## Code style

Plain, explicit Python — type hints on public functions, docstrings on public classes/modules explaining *why*, not just *what*. No hard framework dependencies in core.