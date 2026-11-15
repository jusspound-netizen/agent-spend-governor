# Security Policy

## Reporting a Vulnerability

Open a private security advisory on this repository. Do not open a public
issue for vulnerabilities.

## Scope

This project is a local MCP server. It does not transmit data to any remote
service. Findings about the policy engine's bypass resistance are in scope.

## Known Limitations (0.1.1)

- Budget enforcement relies on the nonce returned by `check_action` being
  passed to `record_spend`. Abandoned approvals count against the budget as
  reservations until a maintenance job cleans them up.
- Path blocking uses substring matching on serialized arguments. It is
  defense in depth, not a sandbox.
