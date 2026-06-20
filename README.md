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
Jelenleg a `base-repo` `mcp/main` template-jéből bootstrapelt MCP-szerver scaffold van benne,
saját shared-specifikus implementáció (cross-session aggregáció, súlyozási modell) még nincs.

## Kapcsolódó dokumentáció

- [`cic-mcp-factory` factory-docs](https://github.com/CentralInfraCore/cic-mcp-factory) — a komponens
  tervezési alapja (`architecture.md`, `acceptance-contract.md`, `execution-phases.md` Phase 4)
- [`cic-mcp-session`](https://github.com/CentralInfraCore/cic-mcp-session) — innen fogyaszt session
  catalógot, de nem ő az első igazságforrás
- [`cic-mcp-knowledge`](https://github.com/CentralInfraCore/cic-mcp-knowledge) — a canonical réteg,
  amire ez a komponens csak emberi review után promote-olhat
