# Security Policy

## Scope

Approval Gate is an educational, **offline** Python/SQLite demonstration and has not undergone a formal security audit. It has no authentication or role-based access controls, so **anyone with local CLI and database access is considered trusted**. Never expose its database or CLI as a network-facing service without independently designing and assessing authentication and authorization.

Only synthetic data should be used in shared examples. Avoid putting private customer information, credentials, or incident data in public GitHub issues.

## Reporting

If you find a security issue, avoid publishing exploit details or sensitive data. Use GitHub's private vulnerability-reporting option **if it is enabled** for this repository; otherwise open a minimal issue requesting a private contact channel, without disclosing vulnerability details.

## Supported versions

The latest default branch is the only version presently maintained. No formal patch service-level agreement is offered.
