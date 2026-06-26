# cic-mcp-shared

Cross-session memória, súlyozás és factory/PR/artifact-kapcsolási réteg a CIC agent-kontextus
(`cic-mcp-*` család) számára.

A `cic-mcp-*` család trust-domain rétegezésében ez a komponens több session-t fűz össze és
jelöl ki promotion-kandidátust — **nem** első igazságforrás, **nem** canonical réteg.

## Mi ez és mi nem

**Igen:**
- több session összefűzése
- factory job/PR/artifact kapcsolás
- visszatérő fogalmak azonosítása
- súlyozás
- konfliktus/superseded jelöltek
- promotion candidates

**Nem:**
- raw hook ingestion első igazságforrása
- canonical layer

A komponensek közti pontos határt lásd: [CLAUDE.md](CLAUDE.md).

## Státusz

`experimental` — a repo a `cic-mcp-factory` job-lifecycle-én keresztül épül fel, kapacitás-jobonként.

**Implementált (`implemented`):**
- `shared_core/aggregator.py` — `aggregate_cross_session()`: cross-session aggregáció,
  trust level scoring, evidence gate, score cap, `CrossSessionAggregationResult`
- `shared_core/session_client.py` — session catalog consumer

**Scaffold (kód van, de nincs bekötve):**
- domain-specifikus MCP tool-ok — nincs `shared_server.py`; a `mcp-server/server.py` a
  base-repo FastMCP KB szerver, nem shared-specifikus
- schema migration runner — a DB séma (`output/shared-core-storage-schema.sql`) létezik,
  de nincs automatizált migráció-futtató

## Kapcsolódó dokumentáció

- [`cic-mcp-factory` factory-docs](https://github.com/CentralInfraCore/cic-mcp-factory) — a komponens
  tervezési alapja (`architecture.md`, `acceptance-contract.md`, `execution-phases.md` Phase 4)
- [`cic-mcp-session`](https://github.com/CentralInfraCore/cic-mcp-session) — innen fogyaszt session
  catalógot, de nem ő az első igazságforrás
- [`cic-mcp-knowledge`](https://github.com/CentralInfraCore/cic-mcp-knowledge) — a canonical réteg,
  amire ez a komponens csak emberi review után promote-olhat
