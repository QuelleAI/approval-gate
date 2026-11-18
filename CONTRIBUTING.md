# Contributing to Approval Gate

This project is intentionally small: a **local, read-only educational example** of human approval and duplicate prevention.

Contributions are welcome through GitHub issues and pull requests. Before opening a PR:

1. Describe the behavior you want to change and its expected security impact.
2. Keep the default behavior approval-first: no job can run before an explicit `approved` decision.
3. Preserve idempotency: repeated identical requests must not trigger a second execution.
4. Add or adjust unit tests using only synthetic data.
5. Run `python3 -m unittest -v test_approval_gate.py` locally.
6. Avoid adding real contact lists, secrets, token strings, customer information, or private operational records.

Changes that add network access, outbound messages, automation schedules, write operations, authentication, or payment logic are **out of scope** without a separate design review. Avoid dependencies where standard-library code suffices.

Please be respectful in discussions and reviews. The maintainer may decline out-of-scope contributions.
