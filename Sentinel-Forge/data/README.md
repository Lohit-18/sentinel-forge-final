# Data

All data in this repository is **synthetic**. It was written for the lab and does not come from any real organisation, person or network.

| File | Purpose |
|---|---|
| `sample/phase1_events.jsonl` | Eight hand-written events, one or more per category, used to demonstrate the event schema and `sentinelforge events validate`. |

Synthetic values follow these conventions so they can never point at real systems:

- **IP addresses:** private ranges (`10.0.0.0/8`) for the "internal" lab network, and the documentation ranges reserved by [RFC 5737](https://www.rfc-editor.org/rfc/rfc5737) (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) for "external" addresses.
- **Domains:** names under `example.com`, `example.org` or `.test`, reserved by [RFC 2606](https://www.rfc-editor.org/rfc/rfc2606).
- **Accounts and hosts:** invented names such as `alice.lab` and `ws-fin-01`.

The event format is documented in [docs/event-schema.md](../docs/event-schema.md). A deterministic event generator replaces these hand-written samples in Phase 2.
