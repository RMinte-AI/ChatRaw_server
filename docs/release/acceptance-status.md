# T8 Acceptance Status

This file records evidence classes, not a production-approval claim.

| Requirement | Local evidence | Production status |
|---|---|---|
| Fresh Source setup | `scripts/t8-data-recovery-acceptance.py` | Engineering evidence |
| Classic data import | Same script; content equality and source unchanged | Engineering evidence |
| Source backup/verify/restore | Same script; admin/member login after restore | Engineering evidence |
| Fresh Compose + volume restore | `scripts/run-t8-compose-recovery-gate.sh` | Engineering evidence |
| Reference module Source/Compose | T6 Source and Compose gates | Engineering evidence |
| Agent Source/Compose and outage | T7 Source and Compose gates | Engineering evidence |
| Server and Agent restart recovery | T6/T7 gates | Engineering evidence |
| Role authorization | backend tests and T7 black-box flow | Engineering evidence |
| Real browser admin/member | Refreshed 2026-07-23: member account-only settings, Agent clarification/result table, admin module status and controls | Engineering evidence |
| OpenAPI/Schema/docs consistency | `check-t8-docs.py`, `export-openapi.py --check`, conformance | Engineering evidence |
| Customer data and credentials | No customer input in repository | `PENDING_ONSITE` |
| Customer hardware/network/TLS/firewall | Not represented by local fixtures | `PENDING_ONSITE` |
| Real upstream API behavior | Synthetic fixture only | `PENDING_ONSITE` |
| Production scale and cutover | No production environment evidence | `PENDING_ONSITE` |

The single local gate is:

```bash
./scripts/run-t8-release-gate.sh
```

Passing it means the committed local engineering contracts are internally
consistent. It must not be reported as customer or production acceptance.
