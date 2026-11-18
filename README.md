# Approval Gate

**A tiny offline Python + SQLite job queue that requires explicit human approval before any work runs.**

Use it to study three patterns: **approval-first execution**, **idempotent requests**, and **audit trails**. The software makes **no network requests**, has **no external dependencies**, and includes only two read-only demonstration jobs: counting records and finding duplicate strings.

[MIT License](LICENSE) · Python 3.9+ · No paid services or accounts required

## Quick start

Clone this repository or download the source. From its directory, run:

```sh
python3 approval_gate.py --db demo.db queue --kind find_duplicates --items '["Alpha"," alpha ","Beta"]' --key example-1
python3 approval_gate.py --db demo.db run-one
python3 approval_gate.py --db demo.db list
python3 approval_gate.py --db demo.db decide --id 1 --decision approved
python3 approval_gate.py --db demo.db run-one
python3 approval_gate.py --db demo.db audit
```

The first `run-one` returns `idle` because the queued job is still **pending**. After explicit approval it completes and reports one duplicate group (`alpha`: 2). Reusing an idempotency key with the **same** payload returns the original job instead of queuing a duplicate; reusing it with **different** content is rejected.

## Test

```sh
python3 -m unittest -v test_approval_gate.py
```

Nine standard-library unit tests cover approval, rejection, run-once behavior, duplicate handling, conflicts, input limits, audit events, and persistence.

## Scope

- Local SQLite states: `pending` → `approved` → `completed` (or `rejected` / `failed`).
- An explicit CLI decision is required for every queued operation.
- The default allowlist includes `count_records` and `find_duplicates` only.
- Local SQLite transactions and an audit-events table make the state transitions inspectable.
- You supply demo strings locally. No network access, cloud service, email, billing, web interface, or background scheduler is present.
- No CI workflow runs or paid services are required.

**Educational example, not a production security boundary.** The command-line operator and users who can access the SQLite file are trusted. Authentication, authorization, database-at-rest encryption, durability beyond a single local node, monitoring, and a public API are **not** provided. Don't use real sensitive customer records in demonstrations.

## Community

Contributions and corrections are welcome. Open an issue or propose a pull request with synthetic test cases. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

Copyright (c) 2026 Jamison Shults. Distributed under the [MIT License](LICENSE).
