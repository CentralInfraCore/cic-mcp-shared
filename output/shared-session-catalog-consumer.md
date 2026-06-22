# shared-session-catalog-consumer-001 Output

## Scope

Ez a job a Phase 4 ELSŐ jobja a `cic-mcp-shared` repóban (`execution-phases.md` "Phase 4 -
cic-mcp-shared"). A `cic-mcp-shared` jelenleg `experimental` állapotú, `source/` üres, nincs
shared-specifikus kód (`make_source.py`/`mcp-server/` a `base-repo` MCP-template öröksége) —
lásd a target repo `CLAUDE.md` "Jelenlegi állapot" szekcióját.

Ez a job NEM implementáció. KONTRAKTUS-szintű riport, amely definiálja, HOGYAN fogyasztaná a
`cic-mcp-shared` a `cic-mcp-session` session-katalógust a session MCP tool-határon keresztül,
anélkül hogy:

- a `cic-mcp-shared` válna a session-adat ELSŐ igazságforrásává (a teljes raw session-tartalom
  shared-oldali táblákba másolása ezt jelentené),
- a shared automatikus canonical promotiont végezne emberi review nélkül.

Nincs futtatható adapter/aggregátor kód, nincs `SessionIngressEnvelope` schema-módosítás, és a
`cic-mcp-session` repo NEM módosul (kizárólag olvasásra klónozva ehhez a jobhoz).

## Inputs Read

- `${WORKDIR}/.cic-context/factory-docs/architecture.md` — "Komponens térkép", "cic-mcp-shared"
  Igen/Nem határ-lista, "Schema szeparáció" (`shared_core.*`), "Trust modell" (`shared: trust:
  mixed / candidate / reviewed_shared, canonical: false by default`).
- `${WORKDIR}/.cic-context/factory-docs/execution-phases.md` — "Phase 4 - cic-mcp-shared" (cél,
  első capability-k, korlátozás: "shared meg mindig nem canonical").
- `${WORKDIR}/.cic-context/factory-docs/job-slices.yaml` — `shared-session-catalog-consumer-001`
  bejegyzés (sor 720-743): `prerequisites: [session-ingress-envelope-contract-001]`,
  `acceptance_gates`, `required_evidence`, `forbidden_shortcuts`. NORMATÍV forrás ehhez a jobhoz.
- `${WORKDIR}/jobs/index.yaml` — `session-ingress-envelope-contract-001` bejegyzés (sor
  127-135), `status: "done"` mező ellenőrzése.
- `${WORKDIR}/jobs/session-ingress-envelope-contract-001/output/session-ingress-envelope.schema.yaml`
  — a teljes `SessionIngressEnvelope` schema (required mezők, `trust` enum, `canonical`/
  `interpreted` const:false, `idempotency_key` felépítés).
- `${WORKDIR}/jobs/session-ingress-envelope-contract-001/output/session-ingress-envelope-contract.md`
  — a kontraktus indoklása, Claim-Evidence Matrix, Risks.
- `cic-mcp-session/mcp-server/session_server.py` (klón, KIZÁRÓLAG OLVASÁSRA) — a 7 MCP tool
  tényleges szignatúrája, modul-szintű docstring (sor 1-81: a tool-ok forrása `session_api.*`
  SQL függvények, "thin MCP wrapper", nincs RRF/FTS/vektor logika újraírva Pythonban).
- `cic-mcp-session/CLAUDE.md` (klón) — "Fő határok" (Igen/Nem lista), "Trust modell"
  (`canonical: false`, `promotion_allowed: false`, `interpreted: false`, `default_scope:
  session_id`, `cross_session: false`), "Jelenlegi állapot" (7 tool-os MCP szerver, NINCS
  bekötve élesben semelyik `.mcp.json`-ba — `output/session-mcp-config-wiring-report.md`).
- `cic-mcp-shared/CLAUDE.md` (target repo) — "Fő határok", "Trust modell" (`trust: mixed /
  candidate / reviewed_shared`, `canonical: false by default`), "Jelenlegi állapot",
  "Kapcsolódó rendszerek" ("innen fogyaszt session catalógot összefűzésre").
- `${WORKDIR}/.cic-context/factory-docs/job-slices.yaml` `gateway-session-adapter-contract-001`
  bejegyzés (sor 615-679) — precedens: a gateway réteg már bizonyította, hogy a session MCP
  tool-határon keresztüli fogyasztás (real subprocess + stdio handshake) implementálható,
  nem csak tervezhető (`gateway-context-pack-v1-001` lánc).

### Boot sequence eredménye

- `kb_status`: a cic-graph KB elérhető és betöltött — `chunks.pkl`, `graph_nodes.pkl`,
  `graph_edges.pkl`, `inverted_index.pkl`, `faiss.index`, `bm25.pkl` mind `exists: true`
  (`data_dir`: `/home/sinkog/sync/git.partners/CentralInfraCore/MCPs/private/kb_data/pkl`).
- A boot sequence-ben az input.md csak `kb_status`-t írt elő kötelezőként (nincs explicit
  `search_nodes` lépés ebben a jobban, szemben a `session-ingress-envelope-contract-001`
  job-bal) — a KB-állapot ellenőrzése megtörtént, a tartalmi forrás ehhez a riporthoz a fent
  felsorolt fájlok közvetlen olvasása.

## Prerequisite Check

Grep-parancs (a `cic-mcp-factory` klónban, `jobs/index.yaml`-on):

```
grep -A3 'job_id: "session-ingress-envelope-contract-001"' jobs/index.yaml
```

**Eredmény: NINCS találat** — a `jobs/index.yaml` ebben a repóban a job-bejegyzéseket `- id:
"<job-id>"` kulccsal indexeli, NEM `job_id:` kulccsal (ez a kulcsnév az input.md
specifikációjában feltételezett formátum, ami nem egyezik a tényleges `index.yaml` sémájával).
A tényleges bejegyzés a `id:` kulcsra keresve található meg:

```
$ grep -n "session-ingress-envelope-contract-001" jobs/index.yaml
127:  - id: "session-ingress-envelope-contract-001"
175:    parent: "session-ingress-envelope-contract-001"
```

A tényleges bejegyzés tartalma (`jobs/index.yaml` 127-135. sor):

```yaml
  - id: "session-ingress-envelope-contract-001"
    level: "capability"
    status: "done"
    parent: "session-infra-pipeline-fix-001"
    target_repo: "cic-mcp-session"
    capability_id: "cic_mcp.session.ingress_envelope_contract"
    created: "2026-06-20T20:21:14Z"
    started: "2026-06-20T20:26:29Z"
    completed: "2026-06-20T20:40:00Z"
```

**`status: "done"`** — a prerequisite KÉSZ. Megerősítve, hogy a `parent` lánc
(`session-infra-pipeline-fix-001` → `session-ingress-envelope-contract-001`) konzisztens, és
hogy a `completed` timestamp (`2026-06-20T20:40:00Z`) jelen van.

**Döntés: GO.** A `session-ingress-envelope-contract-001` prerequisite teljesült — a riport
folytatja a feladat 2-5. alpontjait.

(Megjegyzés a "Decisions Proposed" szekcióban: az input.md grep-pattern eltérése a tényleges
`index.yaml` sémától nem hiba ebben a riportban, hanem a jövőbeli job-spec-szerzők számára
dokumentált korrekció — lásd lent.)

## Session MCP API Surface

Grep-parancs (a `cic-mcp-session` klónban, `mcp-server/session_server.py`-on):

```
grep -rn "@mcp.tool()" -A 1 mcp-server/session_server.py | grep -v test_
```

**Teljes kimenet:**

```
mcp-server/session_server.py:94:@mcp.tool()
mcp-server/session_server.py-95-def search_session_context(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:150:@mcp.tool()
mcp-server/session_server.py-151-def search_session_context_fts(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:199:@mcp.tool()
mcp-server/session_server.py-200-def search_session_context_vector(session_id: str, query: str, limit: int = 20) -> list[dict]:
--
mcp-server/session_server.py:258:@mcp.tool()
mcp-server/session_server.py-259-def get_session_timeline(session_id: str, limit: int = 100) -> list[dict]:
--
mcp-server/session_server.py:302:@mcp.tool()
mcp-server/session_server.py-303-def get_session_context_pack(session_id: str, max_chunks: int = 50) -> list[dict]:
--
mcp-server/session_server.py:348:@mcp.tool()
mcp-server/session_server.py-349-def get_session_status(session_id: str) -> dict:
--
mcp-server/session_server.py:395:@mcp.tool()
mcp-server/session_server.py-396-def get_session_source_refs(
```

Mind a 7 `@mcp.tool()`-dekorált függvény megjelenik, `grep -v test_` után nem szűrt ki semmit
(nincs `test_` prefixű tool-definíció a fájlban — a teszt-szűrés ezen a fájlon no-op, ami
elvárt, mert a tool-definíciók a forrásfájlban élnek, a tesztek külön `tests/` fájlokban).

A 7. tool (`get_session_source_refs`) többsoros szignatúrája miatt a `-A 1` csak a `def
get_session_source_refs(` sort fogja el — a teljes szignatúra (`mcp-server/session_server.py`
395-398. sor):

```python
@mcp.tool()
def get_session_source_refs(
    session_id: str, ref_kind: str | None = None, limit: int = 100
) -> list[dict]:
```

### Melyik tool-t hívná a shared-konzument-adapter, milyen paraméterekkel

A `cic-mcp-shared` konzument-adapter (jövőbeli implementáció, NEM ez a job) a 7 tool-ból a
cross-session aggregáláshoz szükséges ALHALMAZT hívná, KIZÁRÓLAG az MCP tool-határon keresztül
(SOHA direkt SQL/`session_api.*`/tábla-hozzáférés — ahogy `gateway-session-adapter-contract-001`
is bizonyította, hogy ez betartható):

1. **`get_session_status(session_id: str) -> dict`**
   (`mcp-server/session_server.py:348-349`) — a shared aggregátor ezzel állapítja meg, mely
   session-ek aktívak/lezártak (`status` mező) egy batch-aggregálási ciklus előtt, hogy ne
   próbáljon meg lezárt vagy nem létező session-re aggregátumot építeni.

2. **`get_session_timeline(session_id: str, limit: int = 100) -> list[dict]`**
   (`mcp-server/session_server.py:258-259`) — a shared aggregátor ezzel kapja meg egy session
   turn-sorrendjét (`turn_seq`, `occurred_at`), amikor egy adott session-en belüli visszatérő
   fogalom időbeli elhelyezését kell rögzíteni egy klaszter-jelölthöz.

3. **`search_session_context(session_id: str, query: str, limit: int = 20) -> list[dict]`**
   (`mcp-server/session_server.py:94-95`) — a hibrid (FTS+vektor, RRF-fúzió) keresés a
   LEGFONTOSABB live-query belépési pont: amikor a shared egy korábban perzisztált
   klaszter/fogalom-jelölthöz friss bizonyítékot keres egy adott session-ben, ezt hívja
   `query`-ként a klaszter kulcsszavával/leírásával.

4. **`get_session_context_pack(session_id: str, max_chunks: int = 50) -> list[dict]`**
   (`mcp-server/session_server.py:302-303`) — amikor a shared egy konkrét session teljes,
   rendezett chunk-csomagját akarja megnézni egy jelölt validálásához (pl. mielőtt egy
   `promotion_candidate`-et `reviewed_shared`-re jelölne elő emberi review-hoz), ezt hívja —
   NEM tárolja el a chunk-tartalmat tartósan, csak az aktuális kérés idejére tartja memóriában.

5. **`get_session_source_refs(session_id, ref_kind=None, limit=100) -> list[dict]`**
   (`mcp-server/session_server.py:395-398`) — amikor egy shared-oldali aggregátumhoz
   provenance-láncot kell rögzíteni (pl. egy klaszter melyik konkrét fájl/tool_call
   forrásokból állt össze), ezt hívja, és a visszaadott `content_hash`/`ref_value` mezőket
   PERZISZTÁLJA a saját `shared_core.*` provenance-kapcsoló rekordjában (lásd "Persisted vs.
   Live-Queried Split").

**Nem felhasznált tool-ok ennek a konzument-rétegnek:**

- `search_session_context_fts` (`mcp-server/session_server.py:150-151`) és
  `search_session_context_vector` (`mcp-server/session_server.py:199-200`) — ezek a hibrid
  `search_session_context` ALKOMPONENSEI (csak FTS, csak vektor); a shared-konzument-adapter
  a hibrid (RRF-fúziós) verziót preferálja elsődlegesen, mert az már a kombinált rangsorolást
  adja. A különálló FTS/vektor tool-ok csak egy jövőbeli `shared-cross-session-search-001` job
  finomhangolásánál válhatnak relevánssá (pl. ha a cross-session rangsorolás saját súlyozást
  akarna alkalmazni a két aldimenzióra) — ez explicit Nem cél itt.

Minden hívás a 7 tool egyikén KERESZTÜL megy, soha nem `session_api.*` SQL függvényen vagy
`session_core.*`/`session_idx.*` táblán direktben — ez a `forbidden_shortcuts` "session-adat
direkt SQL/tábla-hozzáférése" pontjának betartása, és ugyanazt a határt követi, amit a
`gateway-session-adapter-contract-001` job már bizonyított betarthatónak a gateway oldalán
(real subprocess + stdio MCP handshake, nem direkt DB-kapcsolat).

## Persisted vs. Live-Queried Split

Mezőszintű döntés — mit PERZISZTÁL a `cic-mcp-shared` saját tárban (`shared_core.*`,
`architecture.md` "Schema szeparáció"), és mit kérdez le LIVE a session MCP API-n keresztül:

| Adat | Perzisztált shared-oldalon? | Indoklás |
|---|---|---|
| Raw session chunk-tartalom (`text` mező a `get_session_context_pack`/`search_session_context` válaszból) | **NEM** | Ez a session-réteg első igazságforrása (`cic-mcp-session/CLAUDE.md` "Fő határok" Igen: "chunk store"). Másolása `shared_core.*`-ba KÉT igazságforrást hozna létre — ha a session-oldali chunk módosulna/törlődne (pl. retention policy), a shared-oldali másolat elavult marad ÉS nem létezne mechanizmus a szinkronizálásra. |
| Session `turn_id`/`chunk_id` (numerikus referencia, NEM tartalom) | **IGEN** (provenance-kapcsolóként) | Csak az ID-t tárolja, nem a tartalmat — ez egy pointer/foreign-key-szerű hivatkozás, nem adatduplikáció. A tényleges tartalom mindig a `get_session_context_pack`/`get_session_source_refs` hívással kérhető le újra, igény szerint. |
| Cross-session klaszter/visszatérő-fogalom leírás (a shared SAJÁT levezetett aggregátuma) | **IGEN** | Ez NEM session-raw adat, hanem a shared réteg saját, levezetett tartalma (`architecture.md` "cic-mcp-shared" Igen: "visszatérő fogalmak", "súlyozás") — ennek a perzisztálása a shared réteg explicit feladata, nem session-adat duplikálása. |
| Súlyozott jelöltek (`promotion_candidate` rekordok, súly-score) | **IGEN** | Ugyanaz az indoklás: ez a shared réteg saját levezetett állapota (Phase 4 cél: "sulyozas", "promotion candidates"), nem a session raw tartalom kópiája. |
| Session `status` (aktív/lezárt) | **NEM** (mindig live) | A session `status` az időben gyorsan változhat (`get_session_status` válasz mezője) — ha a shared cache-elné, könnyen elavulttá válna; a hívás olcsó (`session_api.session_status()` egysoros lekérdezés), nincs ok a perzisztálásra. |
| `source_ref` provenance metaadat (`content_hash`, `ref_kind`, `ref_value`) | **IGEN** (a kapcsolódó shared-rekordhoz csatolva) | Ez NEM a session raw tartalma, hanem egy AUDIT-pointer (melyik fájl/tool_call alapozta meg a klasztert) — perzisztálása szükséges ahhoz, hogy egy emberi reviewer utólag visszanyomozhassa, MIÉRT keletkezett egy adott jelölt, anélkül hogy a teljes session-tartalmat duplikálná. |
| Session FTS/vektor keresési eredmény (egy konkrét `search_session_context` hívás output sorai) | **NEM** (csak az aktuális kérés idejére memóriában) | Ezek minden hívásnál újra lekérdezhetők, a session-oldali index naprakészebb mint egy elavuló shared-oldali cache lenne — a `fused_score`/`rank`/`similarity` érték is csak az adott pillanatban érvényes rangsorolás, nem stabil tény. |

**Miért NEM volna helyes a teljes session-tartalmat shared-oldali táblákba másolni** (a
`cic-mcp-shared/CLAUDE.md` "Nem": "raw hook ingestion első igazságforrása" pontjának
indoklása):

1. **Két igazságforrás keletkezne.** Ha a `cic-mcp-session` session_raw/session_core rétege
   módosulna (pl. egy hibás envelope javítása, vagy egy retention/GDPR-törlés), a shared-oldali
   másolat NEM frissülne automatikusan — innentől a shared réteg saját, divergáló "igazságot"
   állítana a session-tartalomról, ami pontosan az, amit a `architecture.md` Trust modell
   ("session: trust: session_local/session_derived, canonical: false, default scope: one
   session") és a `cic-mcp-shared` "Nem" listája tilt.
2. **A session-réteg MÁR biztosít stabil API-t erre a célra** (`cic-mcp-session/CLAUDE.md` "Fő
   határok" Igen: "stabil SQL/API/MCP read tools") — a shared rétegnek nem kell saját
   read-modellt fenntartania ugyanahhoz az adathoz, amikor a forrásréteg már ezt a feladatot
   ellátja egy MCP tool-határon át.
3. **A `SessionIngressEnvelope` raw preservation garanciája** (`session-ingress-envelope.schema.yaml`
   `payload` mező leírása: "stored AS-IS... MUST NOT be discarded or replaced by a derived
   summary") csak a `cic-mcp-session` oldalán érvényesíthető egyetlen helyen — ha a shared
   réteg egy SAJÁT, esetlegesen szűkebb/eltérő reprezentációt tartana fenn ugyanarról a
   payloadról, ez aláásná azt a garanciát, hogy PONTOSAN egy hely őrzi a raw tartalmat
   hash-ellenőrizhető formában.
4. **A live-query költsége alacsony, a duplikáció költsége magas.** A 7 MCP tool mindegyike
   egy egyszerű, indexelt SQL-függvényt hív (`session_api.*`) — a shared rétegnek nem kell
   saját FTS/vektor-indexet fenntartania a session raw tartalomra, amikor a session réteg ezt
   már megtette (`cic-mcp-session/CLAUDE.md` "Jelenlegi állapot": chunk indexer,
   `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimenzió, FTS/vektor/hibrid keresés — mindez
   MÁR létezik és bizonyított a session oldalon).

## Trust Mapping

A `cic-mcp-shared/CLAUDE.md` "Trust modell" szekciója szerint:

```yaml
trust: mixed / candidate / reviewed_shared
canonical: false   # by default
```

Egy `cic-mcp-session`-ből származó, shared-oldalon aggregált jelölt a következő `trust`
értéket kapná, az aggregáció jellege szerint:

| Aggregáció jellege | `trust` érték | Indoklás |
|---|---|---|
| Egy klaszter, amely TÖBB különböző session-ből, ELTÉRŐ provider/forrásból (`SessionIngressEnvelope.provider`, pl. `claude-code` + `chatgpt-export`) gyűjt visszatérő fogalmat, még review nélkül | `mixed` | A forrás-session-ek maguk `session_local`/`session_derived` trust-tal rendelkeznek (session-ingress-envelope-contract-001 schema, `trust` enum) — ha a shared ezeket egy klaszterbe fűzi össze, az eredmény trust-besorolása nem lehet magasabb, mint a leggyengébb bemenet, és mivel a forrás-keverék heterogén, ez `mixed`. |
| Egy jelölt, amely a shared SAJÁT súlyozási logikája szerint (recurrence, factory/PR/artifact linkage — `shared-weighting-model-001` job tárgya, itt NEM részletezve) elér egy küszöböt, és formálisan promotion-jelöltté válik, DE még nem ment át emberi review-n | `candidate` | Ez a `promotion_candidate` állapot — magasabb bizalmi szint mint `mixed`, mert már strukturált súlyozási kritériumon átesett, de explicit NEM jelenti azt, hogy bárki megerősítette a tartalmát. |
| Egy jelölt, amelyet egy ember (orchestrátor/reviewer) ÁTNÉZETT és jóváhagyott shared-szintű felhasználásra (DE még nem promote-olva `cic-mcp-knowledge`-be canonical-ra) | `reviewed_shared` | A `cic-mcp-shared/CLAUDE.md` szerint ez a LEGMAGASABB trust-szint, amit a shared réteg önmagában elérhet — "a knowledge promotion külön, emberi review-flow, NEM ennek a rétegnek a feladata" (CLAUDE.md "Trust modell" 4. mondat). `reviewed_shared` ≠ `canonical`: ez egy review a SHARED rétegen belüli felhasználásra, nem a knowledge-rétegbe való promotion. |

### Miért NEM kaphat egy shared-aggregátum `canonical: true`-t automatikus promotion nélkül

A `cic-mcp-shared/CLAUDE.md` "Trust modell" szekció explicit kimondja:

> `canonical: false   # by default`
>
> "A shared réteg sem állít elő canonical tényt automatikusan — a knowledge promotion külön,
> emberi review-flow, nem ennek a rétegnek a feladata."

Ez konzisztens az `architecture.md` "Trust modell" és "Factory legitimáció" szekcióival:

```text
knowledge
  trust: reviewed/canonical
  canonical: true only after review/promotion
```

```text
AI gyart es validal, de nem legitimál.
Human merge = state transition authorization.
```

Indoklás, mezőszinten:

1. **A `canonical: true` egy MÁSIK trust-domain (knowledge) kizárólagos állítása** — a `trust`
   enum (`mixed`/`candidate`/`reviewed_shared`) a session-réteg `trust` enumjához hasonlóan
   (`session_local`/`session_derived`) zárt halmaz; a `canonical` mező a shared-oldali
   aggregátumokon belül `false` még a legmagasabb belső trust-szinten (`reviewed_shared`) is,
   mert a `reviewed_shared` review a SHARED rétegen belüli felhasználásra vonatkozik, nem egy
   formális knowledge-promotion-review-folyamat eredménye.
2. **Strukturális párhuzam a session-réteg `canonical: const: false` kikényszerítésével**: a
   `session-ingress-envelope.schema.yaml` a `canonical` mezőt JSON Schema `const: false`-ként
   definiálja ("MUST always be false for any SessionIngressEnvelope... a validator
   implementing this schema literally cannot accept canonical=true"). A shared rétegnek
   analóg módon a saját aggregátum-schema-jában (egy JÖVŐBELI implementációs jobban, NEM itt)
   ugyanezt a kikényszerítést kellene alkalmaznia: `canonical` mező `const: false`-ként
   definiálva minden shared-oldali rekordon, amíg nincs explicit, külön knowledge-promotion
   workflow lépés.
3. **Nincs jelenleg semmilyen automatizált útvonal**, amin egy shared-aggregátum
   `canonical: true`-ra váltana — ez explicit "Nem cél" pont ebben a jobban
   ("canonical promotion folyamat/review-flow részletes kidolgozása (csak annak ÁLLÍTÁSA, hogy
   az emberi review-t igényel, kötelező)") és a `forbidden_shortcuts` listában ("a shared
   automatikus canonical promotiont végez emberi review nélkül" — TILOS).

## Adapter Contract Table

| `cic-mcp-session` MCP tool | shared-oldali felhasználás | trust-besorolás (a shared-oldali eredményen) | perzisztált vagy live-query |
|---|---|---|---|
| `get_session_status(session_id)` (`mcp-server/session_server.py:348-349`) | Aktív/lezárt session-ek szűrése egy aggregálási batch-ciklus előtt | N/A (nem hoz létre trust-jelölt rekordot, csak vezérlési input) | live-query (mindig friss állapot kell) |
| `get_session_timeline(session_id, limit=100)` (`mcp-server/session_server.py:258-259`) | Egy klaszter-jelölthöz tartozó esemény(ek) időbeli elhelyezése (`turn_seq`, `occurred_at`) | `mixed` (a timeline egy nyers bemenet a klaszterhez, önmagában még nem review-zott jelölt) | live-query (a `turn_id`/`occurred_at` referencia perzisztálható a klaszter-rekordon, de a teljes timeline NEM duplikálódik) |
| `search_session_context(session_id, query, limit=20)` (`mcp-server/session_server.py:94-95`) | Visszatérő fogalom/klaszter bizonyítékának keresése session-enkénti hibrid (FTS+vektor) kereséssel | `mixed` → `candidate` (ha a súlyozási küszöböt eléri, lásd `shared-weighting-model-001`) | live-query (a `chunk_id`/`fused_score` referencia perzisztálható, a `text` tartalom NEM) |
| `get_session_context_pack(session_id, max_chunks=50)` (`mcp-server/session_server.py:302-303`) | Egy jelölt manuális/emberi review előtti kontextus-betekintése (mit állít a forrás-session) | N/A (review-támogató live-lekérdezés, nem maga hoz létre trust-jelöltet) | live-query (sosem perzisztált — kifejezetten az ad-hoc review pillanatában kérve) |
| `get_session_source_refs(session_id, ref_kind=None, limit=100)` (`mcp-server/session_server.py:395-398`) | Egy shared-aggregátum provenance-láncának rögzítése (melyik fájl/tool_call alapozta meg) | `reviewed_shared`-hoz vezető audit-bizonyíték (a `content_hash`/`ref_value` a review-dokumentáció része) | **perzisztált** (`content_hash`, `ref_kind`, `ref_value` mint provenance-pointer a shared-rekordon — NEM a forrás-tartalom, csak a hivatkozás) |
| `search_session_context_fts(session_id, query, limit=20)` (`mcp-server/session_server.py:150-151`) | NEM HASZNÁLT ebben a kontraktusban (csak a `shared-cross-session-search-001` job tárgya lehet) | N/A | N/A |
| `search_session_context_vector(session_id, query, limit=20)` (`mcp-server/session_server.py:199-200`) | NEM HASZNÁLT ebben a kontraktusban (csak a `shared-cross-session-search-001` job tárgya lehet) | N/A | N/A |

## Findings

1. **A prerequisite (`session-ingress-envelope-contract-001`) `done` státuszú**, de az
   input.md-ben megadott grep-pattern (`job_id: "..."`) NEM egyezik a tényleges
   `jobs/index.yaml` séma kulcsnevével (`id: "..."`) — a riport ezt explicit jelezte és a
   tényleges, működő grep-paranccsal igazolta a `done` státuszt (lásd "Prerequisite Check").
2. **A `cic-mcp-session` MCP szerver mind a 7 tool-ja `thin wrapper`** a már létező, tesztelt
   `session_api.*` SQL függvények körül (`mcp-server/session_server.py` modul-docstring, sor
   1-81) — nincs RRF/FTS/vektor/provenance-join logika Pythonban újraírva, ez direkt
   konzisztens a shared-konzument-adapter tervezett határával (a shared se írná újra ezt a
   logikát, csak a 7 tool válaszát fogyasztaná).
3. **A session MCP szerver jelenleg NINCS bekötve élesben** semelyik `.mcp.json`-ba
   (`cic-mcp-session/CLAUDE.md` "Jelenlegi állapot": "a `cic-session` MCP szerver nincs bekötve
   élesben semelyik orchestrátor/Claude Code session `.mcp.json`-jába" —
   `output/session-mcp-config-wiring-report.md`) — ez azt jelenti, hogy egy jövőbeli
   `shared`-oldali implementációs job-nak ELŐSZÖR a wiring-rést kell kezelnie (vagy legalább
   dokumentálnia), mielőtt a tényleges adapter-kód MCP-kliensként hívhatná a 7 tool-t.
4. **A `gateway-session-adapter-contract-001` → a gateway-oldali implementációs job
   (`job-slices.yaml` sor 666: "Implement the FIRST real compile_context() function...
   real subprocess + stdio handshake") MÁR bizonyította**, hogy a session MCP tool-határon
   keresztüli fogyasztás (nem direkt SQL) gyakorlatilag implementálható egy másik
   trust-domain rétegből — ez a precedens támogatja, hogy a shared réteg ugyanezt a mintát
   követhetné egy jövőbeli implementációs jobban, anélkül hogy a kontraktus-tervezés
   szintjén ezt külön kellene bizonyítani.
5. **A `cic-mcp-shared` CLAUDE.md "Jelenlegi állapot" szekciója maga jelzi**, hogy a Phase 4
   három első capability-je (`shared-session-catalog-consumer-001`,
   `shared-cross-session-search-001`, `shared-weighting-model-001`) "jelenleg még nincsenek
   lebontva a `cic-mcp-factory/jobs/.../factory-docs/job-slices.yaml`-ban, ezt elsőként pótolni
   kell" — ez a riport olvasásakor MÁR ELLENTMOND a tényleges `job-slices.yaml` tartalmának
   (lásd sor 720-790, mind a három job MÁR le van bontva) — a `cic-mcp-shared/CLAUDE.md` ezen
   mondata elavult, a tényleges job-slices.yaml-hoz képest pontatlan állapotot ír.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `session-ingress-envelope-contract-001` prerequisite `status: "done"` | proven | `jobs/index.yaml:127-135`, `status: "done"` mező | Fájl direkt grep + idézés (`id:` kulcs, NEM `job_id:`) | low |
| Az input.md grep-pattern (`job_id: "..."`) nem egyezik az `index.yaml` tényleges sémájával | proven | `grep -A3 'job_id: "..."' jobs/index.yaml` üres kimenetet ad; `grep -n "session-ingress..." jobs/index.yaml` 127. és 175. sort talál `id:` kulccsal | Mindkét grep-parancs tényleges futtatása és kimenetének összevetése | low |
| Mind a 7 `@mcp.tool()` regisztrált tool a `session_server.py`-ban | proven | `grep -rn "@mcp.tool()" -A 1 mcp-server/session_server.py \| grep -v test_` teljes kimenete idézve (7 találat: sor 94, 150, 199, 258, 302, 348, 395) | Grep-parancs tényleges futtatása, teljes kimenet idézve | low |
| Mind a 7 tool "thin wrapper" egy létező `session_api.*` SQL függvény körül, nincs RRF/FTS/vektor logika Pythonban újraírva | proven | `mcp-server/session_server.py` modul-docstring (sor 1-81): "Source of truth for the SQL functions this module calls (NOT reimplemented here)" + minden egyes tool docstring-je explicit "does NOT reimplement..." mondattal | Fájl direkt idézése (docstring szövege minden egyes tool-nál) | low |
| A `get_session_source_refs` 4 soros (nem 1 soros) szignatúra | proven | `mcp-server/session_server.py:395-398`, idézve a "Session MCP API Surface" szekcióban | Fájl direkt olvasása (Read tool, sor 395-398) — a `grep -A1` csak a `def` sort fogta el, ezért szükséges volt a teljes fájl elolvasása a pontos szignatúrához | low |
| A shared réteg raw session chunk-tartalmat NEM perzisztál, csak `chunk_id`/`turn_id` referenciát | proven (kontraktus-szintű állítás, nem implementáció) | "Persisted vs. Live-Queried Split" tábla, indoklás a `cic-mcp-shared/CLAUDE.md` "Nem": "raw hook ingestion első igazságforrása" pontra hivatkozva | Tábla + szöveges indoklás a riportban, forrás idézve | medium — ez egy TERVEZETT határ, nincs implementáció ami ezt kikényszerítené (ahogy a `session-ingress-envelope.schema.yaml`-ban a `const: false` kikényszeríti a `canonical`/`interpreted` mezőket) |
| Egy shared-aggregátum `trust` értéke `mixed`/`candidate`/`reviewed_shared`, sosem automatikusan `canonical: true` | proven (kontraktus-szintű állítás) | `cic-mcp-shared/CLAUDE.md` "Trust modell": `trust: mixed / candidate / reviewed_shared`, `canonical: false # by default` + szöveg: "A shared réteg sem állít elő canonical tényt automatikusan" | Fájl direkt idézése | low |
| `gateway-session-adapter-contract-001` precedens bizonyítja, hogy az MCP tool-határon keresztüli fogyasztás implementálható | proven | `.cic-context/factory-docs/job-slices.yaml:666`: "Implement the FIRST real compile_context() function... real subprocess + stdio handshake" | Fájl direkt idézése | low — ez egy MÁSIK réteg (gateway) bizonyítéka, nem a shared rétegé; a shared-oldali implementáció még nincs bizonyítva, csak analóg mintaként hivatkozva |
| A `cic-mcp-shared/CLAUDE.md` "Jelenlegi állapot" szekciójának állítása ("Phase 4 jobok nincsenek lebontva job-slices.yaml-ban") elavult | proven | `job-slices.yaml:720-790` mind a 3 Phase 4 job tényleges bejegyzéssel szerepel, ellentétben a `cic-mcp-shared/CLAUDE.md` állításával | Két fájl közvetlen összevetése | low — dokumentációs inkonzisztencia, nem funkcionális kockázat, de jelzésre érdemes |
| A session MCP szerver nincs bekötve élesben semelyik `.mcp.json`-ba | proven | `cic-mcp-session/CLAUDE.md` "Jelenlegi állapot": "a `cic-session` MCP szerver nincs bekötve élesben... — `output/session-mcp-config-wiring-report.md`" | Fájl direkt idézése | medium — ez azt jelenti, hogy egy jövőbeli shared-implementációs jobnak a wiring-rést is kezelnie kell, mielőtt a tényleges adapter MCP-kliensként hívhatná a tool-okat |
| Tényleges adapter/aggregátor kód implementálva és tesztelve | missing | Ez a job explicit "Nem cél"-ja — nincs adapter-kód, nincs `shared_core.*` séma implementáció | N/A — ez a `status_after_merge: experimental` indoklása | high — ez a fő limitáció, lásd "Risks" |

## Decisions Proposed

1. **A jövőbeli job-spec szerzőknek a `jobs/index.yaml` grep-pattern-jét `id:`-re kell
   javítani**, nem `job_id:`-re — ez egy minta-eltérés, amit ez a riport felfedett (lásd
   "Findings" 1. pont és a Claim-Evidence Matrix 2. sora). Javaslat: a `tools/validate-spec.sh`
   egy jövőbeli verziója ellenőrizhetné, hogy egy input.md-ben megadott grep-pattern tényleg
   talál-e valamit a hivatkozott fájlban, mielőtt a jobot futásra engedné.
2. **A `get_session_source_refs` tool a provenance-megőrzés kulcs-belépési pontja** a shared
   rétegnek — javaslat, hogy egy jövőbeli implementációs job (`shared-cross-session-search-001`
   vagy egy külön adapter-job) a `content_hash` mezőt használja az integritás-ellenőrzéshez,
   konzisztensen a `SessionIngressEnvelope.raw_payload_hash` mintájával.
3. **A `search_session_context` (hibrid) tool az elsődleges live-query belépési pont**
   visszatérő fogalmak kereséséhez — a különálló FTS/vektor tool-ok finomhangolása egy KÉSŐBBI
   (`shared-cross-session-search-001`) jobban dönthető el, nem itt.
4. **A `cic-mcp-shared/CLAUDE.md` "Jelenlegi állapot" szekciójának elavult mondatát**
   ("Phase 4 jobok nincsenek lebontva") egy jövőbeli, kis karbantartó jobnak frissítenie
   kellene, hogy konzisztens legyen a tényleges `job-slices.yaml` tartalommal — ez NEM ennek a
   jobnak a feladata (a job "Nem cél"-ja a teljes implementáció), csak jelzés.

## Rejected / Out Of Scope

- **Tényleges adapter/aggregátor kód implementálása** — explicit "Nem cél", a `status_after_merge:
  experimental` ezt indokolja, a "Next Jobs" szekció javasolja a folytatást.
- **A `SessionIngressEnvelope` schema módosítása** — explicit "Nem cél", a schema teljes
  egészében változatlan maradt (`session-ingress-envelope.schema.yaml`, NEM érintett fájl).
- **`cic-mcp-session` repo módosítása** — explicit "Nem cél", a klón KIZÁRÓLAG olvasásra
  történt, semmi nem commitolva/pusholva bele.
- **`shared-cross-session-search-001`/`shared-weighting-model-001`** (a Phase 4 másik két
  jobja) — explicit "Nem cél", ezek a `search_session_context_fts`/`search_session_context_vector`
  finomhangolását és a súlyozási modellt tárgyalnák, NEM ez a job.
- **Canonical promotion folyamat/review-flow részletes kidolgozása** — explicit "Nem cél",
  csak az ÁLLÍTÁS szükséges (és megtörtént a "Trust Mapping" szekcióban), hogy ez emberi
  review-t igényel.

## Risks

1. **Nincs implementáció, ami a kontraktust valódi adaton validálná.** Ez a fő ok, amiért
   `status_after_merge: experimental`, nem `candidate` (lásd input.md "Target" szekció "status
   indoklás" — ehhez legalább egy valós, futtatott bizonyíték kellene, a
   `gateway-session-adapter-contract-001` → `session-context-pack-v1-001` mintát követve).
2. **A session MCP szerver nincs bekötve élesben semelyik `.mcp.json`-ba** — egy jövőbeli
   implementációs jobnak ezt a wiring-rést is kezelnie kell, különben a tervezett adapter
   sosem tudna valódi MCP-hívást indítani a session szerver felé.
3. **A "Persisted vs. Live-Queried Split" tábla jelenleg csak dokumentált konvenció, nincs
   schema-szintű kikényszerítés** (szemben a `session-ingress-envelope.schema.yaml`
   `const: false` mintájával a `canonical`/`interpreted` mezőkön) — egy jövőbeli implementációs
   jobnak a shared-oldali aggregátum-schema-ban hasonló kikényszerítést kellene bevezetnie
   (pl. `canonical: const: false` a shared rekordokon is).
4. **A `cic-mcp-shared/CLAUDE.md` "Jelenlegi állapot" elavult mondata** (lásd "Findings" 5.
   pont) megzavarhatja a következő job-szerzőt, ha nem veszi észre, hogy a Phase 4 jobok MÁR le
   vannak bontva a `job-slices.yaml`-ban.
5. **A `search_session_context` hibrid tool embedding-függő** (`embed_query()`,
   `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimenzió) — ha a shared-oldali implementáció
   ezt a tool-t hívja, implicit függőséget vállal a session-oldali embedding-modell
   verziójától/elérhetőségétől; ez egy jövőbeli implementációs jobnak explicit kezelendő
   kockázata (modell-verzió drift session és shared között, ha bármelyik réteg saját
   embedding-pipeline-t építene — ami itt NEM tervezett, mivel a shared csak az API-választ
   fogyasztja, nem maga futtat embeddinget).

## Definition Of Done Check

| DoD pont | Státusz | Megjegyzés |
|---|---|---|
| prerequisite (`session-ingress-envelope-contract-001`) állapota grep-pel megerősítve, GO/NO-GO döntés indokolva | PASS | "Prerequisite Check" szekció — `status: "done"`, GO döntés, az input.md grep-pattern eltérése explicit jelezve és korrigálva |
| minden felhasznált session MCP tool-hoz `file:line` szignatúra idézve | PASS | "Session MCP API Surface" szekció — mind az 5 felhasznált tool `file:line` hivatkozással (94-95, 258-259, 302-303, 348-349, 395-398), a 2 nem-használt tool is jelölve sor-hivatkozással (150-151, 199-200) |
| explicit perzisztált-vs-live-query mezőszintű döntés, indoklással | PASS | "Persisted vs. Live-Queried Split" tábla, 7 mező-sorral + 4 pontos szöveges indoklás |
| trust-mapping definiálva (`mixed`/`candidate`/`reviewed_shared`), `canonical: false` explicit kimondva | PASS | "Trust Mapping" szekció, 3 enum-érték leképezve aggregáció-jelleg szerint, `canonical: false by default` idézve és indokolva |
| adapter-kontraktus tábla kész | PASS | "Adapter Contract Table" szekció, mind a 7 tool szerepel (5 használt + 2 nem-használt jelölve) |
| claim-evidence tábla kitöltve, nem üres | PASS | 10 sor, lásd fent |

## Next Jobs

1. **`shared-cross-session-search-001`** (Phase 4, `job-slices.yaml:745-767`,
   prerequisite: ez a job) — a `search_session_context_fts`/`search_session_context_vector`
   finomhangolt felhasználása cross-session rangsoroláshoz, konfliktus/superseded jelöltek
   kezelése.
2. **`shared-weighting-model-001`** (Phase 4, `job-slices.yaml:769-790`, prerequisite:
   `shared-cross-session-search-001`) — a tényleges súlyozási faktorok (recurrence,
   factory/PR/artifact linkage, recency) és a `promotion_candidate` schema mezőinek
   definiálása.
3. **Egy jövőbeli implementációs job** (még nincs job-id), ami a `shared_core.*` schema-t
   (`architecture.md` "Schema szeparáció") és a tényleges MCP-kliens kódot megírja, ami a 7
   session tool-ból az 5 felhasználtat valós, futtatott Postgres-háttér ellen hívja — a
   `gateway-session-adapter-contract-001` → `session-context-pack-v1-001` mintát követve
   (real subprocess + stdio handshake, valós session_id-vel és deliberately-nonexistent
   session_id-vel is bizonyítva). Ez emelné a státuszt `experimental`-ról `candidate`-re.
4. **Egy karbantartó job, ami a `cic-mcp-session` MCP szervert bekötné** legalább egy
   `.mcp.json`-ba (jelenleg sehol nincs bekötve élesben — lásd "Findings" 3. pont) — ez
   prerequisite a 3. pontban javasolt implementációs jobhoz, mert addig a shared-oldali
   adapter nem tudna valódi MCP-hívást indítani.
5. **Egy kis karbantartó job, ami frissíti a `cic-mcp-shared/CLAUDE.md` "Jelenlegi állapot"
   szekcióját**, hogy konzisztens legyen a tényleges `job-slices.yaml` tartalommal (lásd
   "Findings" 5. pont és "Decisions Proposed" 4. pont).
