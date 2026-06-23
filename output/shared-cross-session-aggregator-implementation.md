# shared-cross-session-aggregator-implementation-001 Output

## Scope

Ez a job az ELSŐ TÉNYLEGES aggregátor-kód a `cic-mcp-shared` repóban. A megelőző három
job (`shared-session-catalog-consumer-001`, `shared-cross-session-search-001`,
`shared-weighting-model-001`) kontraktus-szinten definiálta a kereszt-session lekérdezés
alakját és a súlyozási formulát; a `shared-core-storage-implementation-001` megépítette és
valódi Postgres ellen bizonyította a `shared_core.candidates` schema-t. Ez a job az ELSŐ,
amely:

1. valódi subprocess + stdio MCP handshake-kel hívja a `cic-mcp-session`
   `search_session_context(session_id, query, limit)` tool-ját N session_id-re,
2. a `shared-cross-session-search-001` riport szerinti session-enkénti min-max
   normalizálással és összegzéssel kombinálja a több session válaszát,
3. a `shared-weighting-model-001` riport additív formulájával kiszámolja a
   `weight_score`-t és a `recurrence_count`-ot,
4. beír egy valódi sort a `shared_core.candidates` táblába, és ezt valódi psql
   SELECT-tel bizonyítja.

Implementált modulok:
- `shared_core/session_client.py` — valódi subprocess + stdio MCP kliens
  (`SessionServerLaunchConfig`, mirroring `gateway_core/compile_context.py:70`)
- `shared_core/aggregator.py` — normalizálás, súlyozás, `shared_core.candidates` INSERT
- `tests/test_shared_core/test_aggregator.py` — valódi, futtatott end-to-end teszt

Scope-korlátozások (input.md "Nem cél"):
- a `shared_core.candidates` schema NEM módosult (a meglévő schema-ra épültünk)
- a `weight_score`/`recurrence_count` formula NEM lett újradefiniálva (idézve, nem
  kitalálva — lásd "Aggregator Implementation" szekció)
- canonical promotion / emberi review-folyamat NEM implementált
- `historical-import-runner-001` NEM ennek a jobnak a tárgya

## Inputs Read

- `cic-mcp-factory/jobs/index.yaml` — a három prerequisite job `status: "done"`
  megerősítése (lásd "Prerequisite Check")
- `cic-mcp-factory/jobs/shared-cross-session-search-001/output/shared-cross-session-search.md`
  — "Cross-Session Query Shape And Ranking" szekció (270-345. sor): session-szűrés sorrendje,
  soros (nem párhuzamos) végrehajtás session-enként, session-enkénti min-max normalizálás
  (`(score - min) / (max - min)`, vagy 1.0 egyetlen sor esetén), majd ÖSSZEGZÉS (nem
  átlagolás) session-ek között
- `cic-mcp-factory/jobs/shared-weighting-model-001/output/shared-weighting-model.md` —
  290-298. sor: `weight_score = cross_session_score + factory_linkage_bonus +
  recency_bonus` additív formula, `recurrence_count >= 2 AND weight_score >= THRESHOLD`
  AND-feltétel (a `THRESHOLD`/bónusz-értékek konkrét számértéke a riport 308-309. sora
  szerint EXPLICITEN egy jövőbeli implementációs jobra van bízva — ez az a job)
- `cic-mcp-factory/jobs/shared-core-storage-implementation-001/output/shared-core-storage-schema.sql`
  — a TELJES `shared_core.candidates` schema: `candidate_id` (48. sor), `weight_score`
  (83. sor), `recurrence_count` (84-85. sor), `provenance_refs` (105. sor JSONB,
  `{session_id, chunk_id, turn_id, content_hash}` struktúra), `canonical` CHECK constraint
  (63-65. sor: `canonical = FALSE OR trust = 'reviewed_shared'`)
- `cic-mcp-gateway/gateway_core/compile_context.py` — `SessionServerLaunchConfig` (70-99.
  sor) + `StdioServerParameters(...)` hívás (84-88. sor) — a subprocess-launch minta, amit
  KÖVETTÜNK (lásd "MCP Subprocess Launch Pattern" szekció); `_decode_tool_result()` (269-290.
  sor) — a wire-format dekódolás empirikusan ellenőrzött mintája (`.structuredContent` NEM
  populálódik, `.content[0].text` JSON dekódolása a tényleges út)
- `cic-mcp-gateway/tests/test_gateway_core/test_compile_context.py` — a valódi
  subprocess+Postgres end-to-end teszt mintája (`_run_chain_for_envelope`,
  `session_repo_root` fixture, `SHARED_AGGREGATOR_TEST_SESSION_REPO`-stílusú env var)
- `cic-mcp-session/mcp-server/session_server.py` — `search_session_context(session_id,
  query, limit)` (94-95. sor, teljes docstring 96-147. sor): visszatérési érték
  `list[dict]` `chunk_id`, `turn_id`, `text`, `fused_score` mezőkkel, `fused_score` DESC
  sorrendben
- `cic-mcp-session/tests/test_session_store/test_session_api.py` — `_run_chain_for_envelope()`
  minta (`insert_envelope` → `run_projection_batch` → `run_indexing_batch`), `_valid_envelope()`
  mezőlista — EZEKET követtük a szintetikus fixture felépítésénél
- `cic-mcp-shared/CLAUDE.md` — "Trust modell" (`trust: mixed/candidate/reviewed_shared`,
  `canonical: false` by default), "Fő határok" (a shared réteg nem hoz létre canonical
  tényt automatikusan)

## Prerequisite Check

```
$ grep -n '\- id: "shared-cross-session-search-001"' -A 3 jobs/index.yaml
286:  - id: "shared-cross-session-search-001"
287-    level: "capability"
288-    status: "done"
289-    parent: "shared-session-catalog-consumer-001"

$ grep -n '\- id: "shared-weighting-model-001"' -A 3 jobs/index.yaml
303:  - id: "shared-weighting-model-001"
304-    level: "capability"
305-    status: "done"
306-    parent: "shared-cross-session-search-001"

$ grep -n '\- id: "shared-core-storage-implementation-001"' -A 3 jobs/index.yaml
269:  - id: "shared-core-storage-implementation-001"
270-    level: "capability"
271-    status: "done"
272-    parent: "shared-weighting-model-001"
```

Mindhárom prerequisite `status: "done"` az `id:` kulccsal megerősítve. **GO döntés**:
a job folytatható, az aggregátor a meglévő, lezárt kontraktusokra (query-alak,
súlyozási formula, schema) épülhet.

## MCP Subprocess Launch Pattern (Real, Not Mocked)

```
$ grep -rn "class SessionServerLaunchConfig\|StdioServerParameters(" --include="*.py" . | grep -v test_
./gateway_core/compile_context.py:70:class SessionServerLaunchConfig:
./gateway_core/compile_context.py:97:        return StdioServerParameters(
```

(a `cic-mcp-gateway` klónban futtatva.)

A `gateway_core/compile_context.py:70-99` `SessionServerLaunchConfig` dataclass-t (és a
`:84-88` `StdioServerParameters(...)` konstrukciót) a `shared_core/session_client.py:55-88`
`SessionServerLaunchConfig` reprodukálja — SZÁNDÉKOSAN nem importálja a `cic-mcp-gateway`
package-jét (cross-repo Python import nem megengedett, `cic-mcp-shared/CLAUDE.md` "Fő
határok"), de a launch SHAPE pontosan ugyanaz:

- `command`: `{repo_root}/.venv-host/bin/python` (NEM resolve-olt — a symlink resolve
  a venv csomagjait elveszítené, ugyanaz a komment mint
  `compile_context.py:84-90`)
- `args`: `[{repo_root}/mcp-server/session_server.py]`
- `env`: `{"PYTHONPATH": str(repo_root)}` + a `SESSION_STORE_PG_*` env változók
  továbbítása (ha be vannak állítva) — ugyanaz az 5 env var lista mint
  `compile_context.py:46-52` (`_SESSION_STORE_ENV_VARS`), mert `StdioServerParameters.env`
  beállítása ESETÉN a subprocess környezet TELJESEN lecserélődik (nem additív) — ezt a
  kommentet is szó szerint átvettük (`session_client.py:32-37`).

A valódi handshake (`shared_core/session_client.py:119-132` `session_mcp_client()`):

```python
async with stdio_client(server_params) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        yield session
```

— `mcp.client.stdio.stdio_client` + `mcp.ClientSession`, NEM mockolt session-válasz, NEM
in-process Python import a `session_server.py` tool-függvényeiből.

A wire-format dekódolás (`shared_core/session_client.py:91-113` `_decode_tool_result()`)
a `gateway_core/compile_context.py:269-290` EMPIRIKUSAN ellenőrzött mintáját követi:
`.structuredContent` NEM populálódik ennél a szervernél (mcp SDK 1.28.0), a tényleges
visszatérési érték `.content[0].text`-ben JSON-ként szerializálva érkezik — ezt a
sajátos viselkedést NEM újra fedeztük fel, hanem a gateway dokumentált megfigyelését
vettük át.

## Aggregator Implementation

### Session-enkénti lekérdezés

`shared_core/aggregator.py:170-` `_aggregate_cross_session_async()` minden `session_id`-re
EGY `search_session_context(session_id, query, limit)` hívást indít, SOROS (nem
párhuzamos) sorrendben (`shared_core/aggregator.py:_query_one_session` minden hívás
külön await), a `shared-cross-session-search.md` "Soros (nem párhuzamos) végrehajtás"
szekciójának megfelelően.

### Min-max normalizálás + összegzés

`shared_core/aggregator.py:138-149` `_min_max_normalize()` — pontosan a
`shared-cross-session-search.md` 309. és 321-330. sora szerint:

```python
def _min_max_normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    if len(scores) == 1:
        return [1.0]
    lo = min(scores)
    hi = max(scores)
    if hi == lo:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]
```

A `cross_session_score` a session-enkénti normalizált értékek ÖSSZEGE az ÖSSZES
session-en át (`shared_core/aggregator.py:243-245`), NEM átlag — a forrás riport
"A kombinálás" szekciójának (333-339. sor) pontosan megfelelően.

### weight_score / recurrence_count

`shared_core/aggregator.py:274-277`:

```python
weight_score = cross_session_score + factory_linkage_bonus + recency_bonus
```

— szó szerint a `shared-weighting-model.md:290-292` additív struktúráját követi. A
`factory_linkage_bonus`/`recency_bonus` KONKRÉT numerikus értéke (`FACTORY_LINKAGE_BONUS
= 0.1`, `RECENCY_BONUS = 0.1`, `shared_core/aggregator.py:75-76`) implementációs döntés —
a forrás riport 308-309. sora EXPLICITEN ezt a jövőbeli implementációs jobra (= ez a job)
bízza, csak az ADDITÍV STRUKTÚRÁT rögzíti kontraktus-szinten. A `PROMOTION_WEIGHT_THRESHOLD
= 0.5` és `PROMOTION_MIN_RECURRENCE = 2` konstansok (`aggregator.py:77-78`) jelenleg NEM
kerülnek felhasználásra a `shared_core.candidates` INSERT-ben (a `promotion_candidate`
státusz-átmenet NEM ennek a jobnak a tárgya, lásd "Nem cél" / `shared-weighting-model.md`
"A `THRESHOLD` konkrét numerikus értéke implementációs döntés" — itt csak névvel
deklaráltuk, nem silently inline-oltuk, egy jövőbeli promotion-logikai job készen találja).

`recurrence_count` (`shared_core/aggregator.py:249-252`): azon session-ek száma, ahol a
normalizált relevancia LEGALÁBB egy sorban nem-nulla — pontosan az input.md "Feladat" 3
megfogalmazása szerint ("hány session-ben volt nem-nulla normalizált relevancia").

### shared_core.candidates INSERT

`shared_core/aggregator.py:361-` `_insert_candidate()` a MEGLÉVŐ schema mezőivel ír be egy
sort (`candidate_id` auto-generált `gen_random_uuid()`-dal, NINCS explicit megadva):
`keyword_description`, `trust='candidate'`, `weight_score`, `recurrence_count`,
`linked_factory_job_ids`, `last_evidence_at`, `recency_flag`, `provenance_refs` (JSONB).
`canonical` a DEFAULT FALSE-on marad (nincs explicit beállítva) — a
`candidates_canonical_requires_reviewed_shared` CHECK constraint amúgy is elutasítaná
`canonical=true`-t `trust='candidate'` mellett.

`provenance_refs` (`shared_core/aggregator.py:336-359` `_build_provenance_refs()`)
a `shared-cross-session-search.md:372` dokumentált `{session_id, chunk_id, turn_id,
content_hash}` pointer-struktúrát építi — KIZÁRÓLAG pointereket, SOHA a chunk szövegét.

## Synthetic Multi-Session Test Fixture

`tests/test_shared_core/test_aggregator.py` — KÉT, KIZÁRÓLAG fabrikált session, a
`cic-mcp-session` `_run_chain_for_envelope`/`_valid_envelope` mintáját követve (NEM
hand-crafted SQL INSERT a `session_core`/`session_idx` táblákba):

```python
RECURRING_PHRASE = "factory job lifecycle audit checklist"

session_a turns:
  "Reviewed the quarterly synthetic widget inventory totals for fixture-corp."
  "Drafted a factory job lifecycle audit checklist for the fictitious widget-factory pipeline."
  "Filed a synthetic ticket about the fixture-corp break room coffee machine."

session_b turns:
  "Discussed fictitious holiday schedule swaps for the fixture-corp team."
  "Updated the factory job lifecycle audit checklist after the fictitious widget-factory retro."
  "Noted a synthetic reminder to water the office plants at fixture-corp."
```

Mindkét session 3 turn-ön keresztül a VALÓDI ingest pipeline-on fut át
(`insert_envelope` → `run_projection_batch` → `run_indexing_batch`), így a
`session_core.chunks`/`session_idx.chunk_fts`/`chunk_embeddings` táblák valódi, a
hibrid FTS+vektor kereséshez szükséges sorokat tartalmaznak. Egyetlen sor sem valós,
személyes session-tartalom — "fixture-corp", "widget-factory" fiktív entitások,
ugyanaz a szabály mint a `historical-dedupe-idempotency-001`-ben.

## Real Postgres + Real MCP Subprocess Proof

### Tesztfuttatás

```
$ SESSION_STORE_PG_HOST=localhost SESSION_STORE_PG_PORT=55435 \
  SESSION_STORE_PG_DB=testdb SESSION_STORE_PG_USER=postgres \
  SESSION_STORE_PG_PASSWORD=test \
  SHARED_AGGREGATOR_TEST_SESSION_REPO=<cic-mcp-session checkout> \
  <cic-mcp-session>/.venv-host/bin/python -m pytest tests/test_shared_core/test_aggregator.py -v --no-cov

============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0
collecting ... collected 2 items

tests/test_shared_core/test_aggregator.py::test_aggregate_cross_session_real_subprocess_real_postgres PASSED [ 50%]
tests/test_shared_core/test_aggregator.py::test_aggregate_cross_session_no_factory_link_no_recency PASSED [100%]

============================== 2 passed in 29.47s ==============================
```

(Az interpreter a `cic-mcp-session/.venv-host/bin/python` — ez a teljes, `make
deps.local`-lal megépített host-natív venv, amely `mcp`+`psycopg`+`pytest`+a teljes
`session_store` package-et tartalmazza. A `cic-mcp-shared/p_venv` egy Docker `builder`
service-hez tartozó flat `pip install --target` könyvtár (lásd `cic-mcp-shared/CLAUDE.md`
"Python környezet"), Linux-specifikus compiled extension-jei (pl. `pydantic_core`) NEM
futtathatók host-natívan eltérő glibc/Python build alatt — ezért a teszt-futtatáshoz a
session repo saját, host-natívan megépített venv-jét használtuk interpreterként,
`PYTHONPATH`-on keresztül importálva a `shared_core` package-et. A `p_venv`-et magát is
megépítettük `docker compose run --rm setup`-pal a repo-konvenció betartásához — lásd
"Findings" a hálózati instabilitásról ennek a build-nek a futtatása során.)

### Real Postgres SELECT — TÉNYLEGES sorok

```
$ psql -h localhost -p 55435 -U postgres -d testdb -c "
SELECT candidate_id, keyword_description, trust, canonical, weight_score, recurrence_count,
       linked_factory_job_ids, recency_flag, jsonb_array_length(provenance_refs) AS n_provenance_refs
FROM shared_core.candidates
ORDER BY created_at DESC
LIMIT 2;
"

             candidate_id             |          keyword_description          |   trust   | canonical |   weight_score    | recurrence_count |                linked_factory_job_ids                | recency_flag | n_provenance_refs
--------------------------------------+---------------------------------------+-----------+-----------+-------------------+------------------+------------------------------------------------------+--------------+-------------------
 b94a9609-b796-45b7-9932-b35c634f9630 | factory job lifecycle audit checklist | candidate | f         | 2.030272952853598 |                2 | {}                                                   | f            |                 6
 0f83aa35-2230-47e4-9055-73875b6b20b6 | factory job lifecycle audit checklist | candidate | f         | 2.230272952853598 |                2 | {shared-cross-session-aggregator-implementation-001} | t            |                 6
(2 rows)
```

A két sor a két pytest teszt-eset INSERT-jét tükrözi:

- `0f83aa35-...` (`test_aggregate_cross_session_real_subprocess_real_postgres`):
  `linked_factory_job_ids` nem üres + `last_evidence_at = now()` → mindkét bónusz aktív
  → `weight_score = 2.230272952853598`, `recurrence_count = 2`, `recency_flag = true`.
- `b94a9609-...` (`test_aggregate_cross_session_no_factory_link_no_recency`): se
  factory-linkage, se recency → `weight_score = 2.030272952853598` (PONTOSAN 0.2-vel
  kevesebb — a két 0.1-es bónusz hiánya, ami matematikailag bizonyítja az additív
  struktúra helyes működését), `recurrence_count` változatlanul 2.

Mindkét esetben `recurrence_count = 2 >= 2` (Definition of Done követelmény) és
`canonical = false` (a meglévő CHECK constraint mellett, nem módosítva).

### provenance_refs teljes tartalom (egy sor)

```
$ psql -h localhost -p 55435 -U postgres -d testdb -c "
SELECT provenance_refs FROM shared_core.candidates
WHERE linked_factory_job_ids != '{}' ORDER BY created_at DESC LIMIT 1;" -x

provenance_refs | [
  {"turn_id": 2, "chunk_id": 2, "session_id": "5a5c3d51-5eab-4a88-bf49-08c759fdfb89", "content_hash": "sha256:cd37d466..."},
  {"turn_id": 1, "chunk_id": 1, "session_id": "5a5c3d51-5eab-4a88-bf49-08c759fdfb89", "content_hash": "sha256:e3c6c7b4..."},
  {"turn_id": 3, "chunk_id": 3, "session_id": "5a5c3d51-5eab-4a88-bf49-08c759fdfb89", "content_hash": "sha256:1b6ed8ca..."},
  {"turn_id": 5, "chunk_id": 5, "session_id": "7bb5ac10-f20a-4967-b08e-8c90aed28eb5", "content_hash": "sha256:b4c2ba7d..."},
  {"turn_id": 6, "chunk_id": 6, "session_id": "7bb5ac10-f20a-4967-b08e-8c90aed28eb5", "content_hash": "sha256:6daaf611..."},
  {"turn_id": 4, "chunk_id": 4, "session_id": "7bb5ac10-f20a-4967-b08e-8c90aed28eb5", "content_hash": "sha256:3ddb07e5..."}
]
```

6 pointer, 2 KÜLÖNBÖZŐ `session_id`-vel (a két szintetikus fixture session-je) — ez
tényleges, futtatott bizonyítéka annak, hogy mindkét session lekérdezésre került és a
`recurrence_count = 2` valódi cross-session jelenlétet tükröz, nem placeholder értéket.

## Findings

1. **A hálózati letöltés instabil volt mindkét nehéz venv build során** (a
   `cic-mcp-session/.venv-host` és a `cic-mcp-shared/p_venv`, mindkettő a
   `sentence-transformers` tranzitív `torch`/`nvidia-cublas` ~400+MB CUDA wheel-jét
   tölti) — több `ReadTimeoutError`/`SSL: DECRYPTION_FAILED` hiba miatt 2-3 retry kellett
   mindkét oldalon. Ez infrastrukturális, nem kódhiba; a `requirements.in` NEM lett
   módosítva CPU-only torch-ra váltás miatt (ez egy meglévő, read-only/established
   konvenció megváltoztatása lett volna, ami túllépte volna a job scope-ját).
2. **A `cic-mcp-shared/p_venv` flat target-dir NEM futtatható host-natívan** — a
   `pydantic_core` compiled extension-je a host Python build-jéhez (eltérő glibc/ABI)
   nem kompatibilis, `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`
   hibával. Ez a repo saját dokumentált konvenciójának (CLAUDE.md "Python környezet":
   "p_venv/ ← Docker builder PYTHONPATH-hoz, NEM host-natívan futtatható venv") pontos
   megerősítése, NEM egy ÚJ hiba — a `p_venv`-et a `docker compose exec builder python -m
   pytest` futtatná, de ehhez a `cic-mcp-session` checkout-ot is mountolni kellene a
   builder konténerbe (jelenleg nincs ilyen volume-mount a `docker-compose.yml`-ben), amit
   ennek a jobnak nem feladata bevezetni. A valódi bizonyíték tesztfuttatáshoz ehelyett a
   `cic-mcp-session/.venv-host/bin/python` host-natív interpretert használtuk (ami a
   `shared_core` tiszta Python package-et `PYTHONPATH`-on keresztül problémamentesen
   importálja, és minden szükséges függőséget — `mcp`, `psycopg`, `pytest` — tartalmazza).
3. **`requirements.in` módosult**: `psycopg[binary]` hozzáadva a "Testing" szekcióhoz
   (`cic-mcp-shared/requirements.in`), ugyanazt a mintát követve mint a
   `gateway-compile-context-test-hardening-001` jobban a `cic-mcp-gateway`-ben — ez egy
   ÚJ, könyvtárszintű függőség (a `shared_core.candidates` INSERT-hez), nem schema- vagy
   formula-módosítás.
4. **`FACTORY_LINKAGE_BONUS`/`RECENCY_BONUS`/`PROMOTION_WEIGHT_THRESHOLD`/
   `PROMOTION_MIN_RECURRENCE` konstansok deklarálva, de a THRESHOLD/MIN_RECURRENCE
   jelenleg NEM kerül felhasználásra** (a `promotion_candidate` átmenet logikája nincs itt
   implementálva — lásd "Aggregator Implementation" / "Next Jobs"). Ez SZÁNDÉKOS:
   az input.md "Feladat" 3 csak a `weight_score`/`recurrence_count` kiszámítását és az
   INSERT-et kéri, nem egy promotion-döntési logikát.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Mindhárom prerequisite job `status: "done"` | proven | `jobs/index.yaml:286-289,303-306,269-272` grep kimenet idézve | grep parancs futtatva, kimenet idézve | low |
| Az aggregátor VALÓS subprocess-szel hívja a `cic-mcp-session` MCP-t | proven | `gateway_core/compile_context.py:70` `SessionServerLaunchConfig` file:line idézve, `shared_core/session_client.py:55-88` ugyanazt a launch shape-et reprodukálja; pytest teszt valódi `.venv-host/bin/python` subprocess-t indít | file:line idézve + futtatott teszt PASSED | low |
| A subprocess valódi stdio MCP handshake-kel kommunikál (NEM mock) | proven | `shared_core/session_client.py:119-132` `stdio_client`+`ClientSession`+`session.initialize()`; a teszt valódi Postgres-adatot kapott vissza (6 provenance_ref, 2 session_id) | kód idézve + valódi psql kimenet idézve | low |
| Session-enkénti min-max normalizálás `(score-min)/(max-min)`, NEM nyers összegzés | proven | `shared_core/aggregator.py:138-149` `_min_max_normalize()` kódidézet, pontosan a `shared-cross-session-search.md:309,321-330` formulájával | kód idézve, forrás file:line idézve | low |
| `weight_score = cross_session_score + factory_linkage_bonus + recency_bonus` | proven | `shared_core/aggregator.py:274-277` kódidézet + `shared-weighting-model.md:290-292` idézve; valódi futtatott eredmény: 2.230272952853598 (bónuszokkal) vs 2.030272952853598 (bónuszok nélkül) — PONTOSAN 0.2 különbség | psql SELECT tényleges sorok idézve, két teszteset összevetve | low |
| `recurrence_count` = nem-nulla normalizált relevanciájú session-ek száma | proven | `shared_core/aggregator.py:249-252` kódidézet; valódi futtatott eredmény: `recurrence_count = 2` mindkét sorban, 2 KÜLÖNBÖZŐ `session_id` a `provenance_refs`-ben | psql SELECT + provenance_refs JSON idézve | low |
| Legalább egy `shared_core.candidates` sor létrejön, `recurrence_count >= 2`, nem-triviális `weight_score` | proven | psql SELECT 2 sort mutat, mindkettő `recurrence_count = 2`, `weight_score > 2.0` | tényleges psql kimenet idézve | low |
| A teszt-fixture KIZÁRÓLAG szintetikus tartalom | proven | `tests/test_shared_core/test_aggregator.py` teljes turn-szöveg-lista idézve a riportban ("fixture-corp", "widget-factory" fiktív entitások) | kód idézve | low |
| `canonical` mező a meglévő CHECK constraint mellett `false` marad | proven | psql SELECT mindkét sorban `canonical = f`; schema NEM módosítva | psql kimenet idézve + schema diff hiánya | low |
| 2/2 pytest teszt zöld, valódi DB + subprocess | proven | `2 passed in 29.47s` — pytest kimenet idézve | pytest lefuttatva, kimenet idézve | low |
| A `cic-mcp-session` klónba semmit nem commitoltunk | proven | a cic-mcp-session workspace csak olvasásra használt — nem futtattunk `git add`/`git commit` parancsot abban a klónban | szándékos scope-korlátozás | low |

## Decisions Proposed

1. **`shared_core` top-level package neve** — a repo top-level package-konvencióját
   (`session_store` a `cic-mcp-session`-ben, `gateway_core` a `cic-mcp-gateway`-ben)
   követve `shared_core`-nak neveztük el az új package-et, ami EGYBEN megegyezik a
   Postgres schema saját `shared_core` schema-nevével — ez NEM véletlen egyezés, hanem
   szándékos, konzisztens elnevezés a réteg neve és a kód package-neve között.
2. **Szinkron wrapper (`aggregate_cross_session`) + async implementáció
   (`_aggregate_cross_session_async`) szétválasztás** — pontosan a
   `gateway_core/compile_context.py:152,354` mintáját követve (`compile_context()` /
   `_compile_context_async()`), hogy a hívó kód (és a pytest teszt) NE igényeljen
   `pytest-asyncio` függőséget.
3. **A bónusz-konstansok (`FACTORY_LINKAGE_BONUS=0.1`, `RECENCY_BONUS=0.1`) névvel
   deklarált modul-szintű konstansok**, nem inline literál — egy jövőbeli job könnyen
   módosíthatja/kalibrálhatja anélkül, hogy a formula struktúráját kellene
   megváltoztatnia.
4. **`RECENCY_WINDOW_DAYS = 30`** — a `last_evidence_at` "utolsó N nap" ablakának konkrét
   értéke (a forrás riport ezt sem rögzíti számszerűen) — implementációs döntés, NÉVVEL
   deklarálva.

## Rejected / Out Of Scope

- **`shared_core.candidates` schema módosítása** — input.md "Nem cél", nem történt.
- **A `weight_score`/`recurrence_count` formula újradefiniálása** — input.md "Nem cél",
  a formula PONTOSAN a `shared-weighting-model-001` riportból idézve került
  implementálásra.
- **`promotion_candidate` státusz-átmenet / canonical promotion logika** — input.md
  "Nem cél". A `PROMOTION_WEIGHT_THRESHOLD`/`PROMOTION_MIN_RECURRENCE` konstansok
  deklarálva vannak, de NEM kerülnek felhasználásra ebben a jobban — egy jövőbeli job
  feladata ezekre épülő döntési logikát írni.
- **`historical-import-runner-001`** — input.md "Nem cél", másik Phase 6 job, nem
  érintett.
- **Párhuzamos (konkurens) session-lekérdezés** — a `shared-cross-session-search-001`
  riport ezt implementációs döntésnek hagyja, de mi a SOROS mintát követtük (egyszerűbb
  auditálhatóság, file:line visszakövethetőség minden hívásra) — egy jövőbeli job
  szabadon párhuzamosíthatja.

## Risks

- **Hálózati instabilitás a venv build-eknél** (lásd "Findings" 1.) — ha ez egy CI
  környezetben rendszeresen előfordul, érdemes lehet egy pip retry/timeout konfigurációt
  bevezetni a `Makefile`/`docker-compose.yml` szintjén (jelenleg env var-on keresztül
  oldottuk meg ad-hoc módon, `PIP_DEFAULT_TIMEOUT`/`PIP_RETRIES`).
- **A `cic-mcp-shared/p_venv` Docker builder workflow-ja nem tesztelte ezt a kódot
  saját magában** (lásd "Findings" 2.) — a valódi bizonyíték a `cic-mcp-session`
  host-natív venv-jén át futott. Ha a `cic-mcp-shared` CI pipeline-ja a `builder`
  konténeren keresztül futtatja a teszteket, a `cic-mcp-session` checkout mountolása
  szükséges lesz a `docker-compose.yml`-ben (jelenleg nincs ilyen mount) — ez egy NYITOTT
  HÍD: a kód és a teszt bizonyítottan működik, de a repo saját CI-konvenciójába még nincs
  bekötve.
- **A bónusz-konstansok (0.1/0.1) és a `RECENCY_WINDOW_DAYS=30` implementáció-szintű,
  NEM kalibrált értékek** — ha egy jövőbeli job valódi promotion-küszöböt akar
  beállítani, ezeket az értékeket felül kell vizsgálnia valós adat alapján, nem
  örökölheti vakon ebből a jobból.

## Definition Of Done Check

- [x] mindhárom prerequisite `id:` kulccsal megerősítve, GO döntés indokolva — lásd
      "Prerequisite Check"
- [x] az aggregátor VALÓS subprocess-szel hívja a `cic-mcp-session` MCP-t, file:line
      hivatkozással a `SessionServerLaunchConfig` mintára — lásd "MCP Subprocess Launch
      Pattern"
- [x] `weight_score`/`recurrence_count` a `shared-weighting-model-001` formuláját
      pontosan követi, file:line hivatkozással — lásd "Aggregator Implementation"
- [x] szintetikus, fabrikált multi-session fixture, valós tartalom nélkül — lásd
      "Synthetic Multi-Session Test Fixture"
- [x] valós Postgres + valós MCP subprocess teszt: legalább egy `shared_core.candidates`
      sor létrejön, `recurrence_count >= 2`, nem-triviális `weight_score` — lásd "Real
      Postgres + Real MCP Subprocess Proof" (`recurrence_count = 2`,
      `weight_score = 2.230272952853598`/`2.030272952853598`)
- [x] claim-evidence tábla kitöltve, nem üres — lásd "Claim-Evidence Matrix" (10 sor)

## Next Jobs

- **`shared-promotion-candidate-logic-001`** (javasolt) — a `PROMOTION_WEIGHT_THRESHOLD`/
  `PROMOTION_MIN_RECURRENCE` konstansokra épülő `promotion_candidate` állapot-átmenet
  logika (mikor érdemes egy `trust='candidate'` sort emberi review-ra jelölni) —
  jelenleg deklarálva, de nem felhasznált konstansok.
- **`historical-import-runner-001`** (már ismert, ez a job explicit "Nem cél"-ja) —
  történeti session-import batch-futtatás.
- **`shared-cross-session-aggregator-batch-scheduler-001`** (javasolt) — ez a job egy
  EGYSZERI aggregációs ciklust implementál (`aggregate_cross_session()` egy
  `keyword_description`-re és egy `session_id` listára); egy jövőbeli job feladata lenne
  a session-szűrés (`get_session_status` alapján), az "utolsó N aktív session" lista
  összeállítása, és a batch-ciklus ütemezése.
- **`cic-mcp-shared/docker-compose.yml` builder-mount kiterjesztés** (javasolt,
  alacsony prioritású) — a `cic-mcp-session` checkout opcionális volume-mountja a
  `builder` service-hez, hogy a `tests/test_shared_core/test_aggregator.py` a repo saját
  Docker CI workflow-ján (`make test`) keresztül is futtatható legyen, nem csak a
  `cic-mcp-session/.venv-host` host-natív interpreteren át.
