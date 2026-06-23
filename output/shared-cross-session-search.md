# shared-cross-session-search-001 Output

## Scope

Ez a job a Phase 4 MÁSODIK jobja a `cic-mcp-shared` repóban
(`execution-phases.md` "Phase 4 - cic-mcp-shared"). A `shared-session-catalog-
consumer-001` (mergelve, `status: "done"`) definiálta az alap adapter-
kontraktust: a `cic-mcp-shared` az MCP tool-határon keresztül fogyasztja a
`cic-mcp-session` katalógust, csak DERIVÁLT adatot (klaszterek, súlyozott
jelöltek, provenance-pointerek) perzisztál, a raw session-tartalmat sosem
duplikálja. Az a riport explicit DEFERRÁLTA a
`search_session_context_fts`/`search_session_context_vector` finomhangolását
és a cross-session rangsorolás kérdését ERRE a jobra.

Ez a job KONTRAKTUS-szintű (NEM implementáció): definiálja, HOGYAN ismerne fel
a `cic-mcp-shared` egy VISSZATÉRŐ FOGALMAT több, különböző session-ben —
KIZÁRÓLAG lexikai/vektor-hasonlóság alapján, a már létező
`search_session_context` hibrid RRF-fúzió tool-on keresztül, anélkül hogy mély
szemantikai claim-extraction-t végezne a session-rétegben vagy a shared
konzument-adapterben. A keresztezett (konfliktus/superseded) jelölt-kezelés
adatmodelljét is itt definiáljuk.

Nincs futtatható kereső/aggregátor kód, nincs schema-módosítás
(`SessionIngressEnvelope`/`GatewayContextEnvelope`), és a `cic-mcp-session`
repo NEM módosul (kizárólag olvasásra klónozva ehhez a jobhoz). A `status_
after_merge: experimental` indoklása megegyezik az előd-jobéval: nincs
futtatható kereszt-session kereső/aggregátor kód, csak kontraktus.

## Inputs Read

- `${WORKDIR}/.cic-context/factory-docs/architecture.md` — "Komponens térkép",
  "cic-mcp-shared" Igen/Nem határ-lista ("Igen": "visszatérő fogalmak",
  "konfliktus/superseded jelöltek"; "Nem": "raw hook ingestion első
  igazságforrása", "canonical layer"), "Schema szeparáció" (`shared_core.*`:
  "cross-session clusters, summaries, candidate memories, conflicts"), "Trust
  modell" (`shared: trust: mixed / candidate / reviewed_shared, canonical:
  false by default`).
- `${WORKDIR}/.cic-context/factory-docs/execution-phases.md` — "Phase 4 -
  cic-mcp-shared" (cél: "cross-session aggregation", "sulyozas", "factory
  job/PR/artifact kapcsolat", "candidate memory"; első capability-k:
  `shared-session-catalog-consumer-001`, `shared-cross-session-search-001`,
  `shared-weighting-model-001`; korlátozás: "shared meg mindig nem
  canonical").
- `${WORKDIR}/.cic-context/factory-docs/job-slices.yaml` —
  `shared-cross-session-search-001` bejegyzés (sor 745-767):
  `prerequisites: [shared-session-catalog-consumer-001]`, `acceptance_gates`
  (3 pont), `required_evidence` ("Cross-session query shape and ranking
  approach.", "Conflict/superseded candidate data model."),
  `forbidden_shortcuts` ("cross-session search treated as canonical knowledge
  graph", "deep semantic claim extraction performed inside the session
  layer"). NORMATÍV forrás ehhez a jobhoz.
- `${WORKDIR}/jobs/index.yaml` — `shared-session-catalog-consumer-001`
  bejegyzés (sor 260-263), `status: "done"` mező ellenőrzése, `id:` kulccsal
  (NEM `job_id:` — lásd "Prerequisite Check").
- `${WORKDIR}/jobs/shared-session-catalog-consumer-001/output/shared-session-
  catalog-consumer.md` — TELJES egészében, NORMATÍV. Az "Adapter Contract
  Table" (mind a 7 tool felsorolva, 5 használt + 2 nem-használt jelölve) és a
  "Persisted vs. Live-Queried Split" (7 mező-sor, mit perzisztál/mit kérdez le
  live a shared) a közvetlen alapja ennek a jobnak. A "Next Jobs" #1 pontja
  explicit ezt a jobot jelöli ki következő lépésként.
- `cic-mcp-session/mcp-server/session_server.py` (klón, KIZÁRÓLAG OLVASÁSRA)
  — mind a 7 `@mcp.tool()` tényleges szignatúrája (lásd "Session MCP API
  Surface"), modul-szintű docstring (1-81. sor: "thin MCP wrapper", "Source
  of truth for the SQL functions this module calls (NOT reimplemented here)"),
  a `search_session_context`/`search_session_context_fts`/
  `search_session_context_vector` teljes docstring-je (94-255. sor).
- `cic-mcp-session/output/session-retrieval-quality-report.md` — LÉTEZIK
  (ellentétben az input.md feltételes "ha nem található" ágával). Az RRF-
  fúzió mechanizmusát NEM ez a riport dokumentálja közvetlenül (ez a
  `search_context_hybrid()`-ot, a `'simple'/'simple'` FTS-konfigurációt és a
  `pending_jobs` job_type-aware union javítást dokumentálja a NEM-hibrid
  `search_context()`/`session_status()` függvényekre) — a hibrid RRF-fúzió
  tényleges forrása a `session_server.py` modul-docstring-je (24-29. sor):
  `session_api.search_context_hybrid(p_session_id, p_query,
  p_query_embedding, p_limit) RETURNS TABLE (chunk_id, turn_id, text,
  fused_score)`, és a `search_session_context()` docstring-je (96-125. sor):
  "this function does NOT reimplement the RRF fusion logic". A
  `session-hybrid-search-api-migration.sql` (a tényleges RRF SQL) NEM volt
  ennek a jobnak kötelező forrása, és nem lett külön elolvasva — ez egy
  explicit "Findings" pont lent.
- `cic-mcp-session/CLAUDE.md` (klón) — "Fő határok" (Igen/Nem lista, "Nem":
  "vegleges döntésbányászat"), "Trust modell" (`canonical: false`,
  `cross_session: false`), "Jelenlegi állapot" (a 7 tool-os MCP szerver és a
  retrieval-réteg `session_api.search_context()`/`search_context_vector()`/
  `search_context_hybrid()` mind valódi Postgres ellen bizonyítva — lásd
  `output/session-retrieval-quality-report.md`, `session-vector-search-api-
  report.md`, `session-hybrid-search-api-report.md`).
- `cic-mcp-shared/CLAUDE.md` (target repo) — "Fő határok" ("Igen": "konfliktus/
  superseded jelöltek"), "Trust modell" (`trust: mixed / candidate /
  reviewed_shared`, `canonical: false by default`, "A shared réteg sem állít
  elő canonical tényt automatikusan — a knowledge promotion külön, emberi
  review-flow"), "Jelenlegi állapot" (`experimental`, nincs shared-specifikus
  implementáció).

### Boot sequence eredménye

- `kb_status`: a cic-graph KB elérhető és betöltött — `chunks.pkl`,
  `graph_nodes.pkl`, `graph_edges.pkl`, `inverted_index.pkl`, `faiss.index`,
  `bm25.pkl` mind `exists: true` (`data_dir`:
  `/home/sinkog/sync/git.partners/CentralInfraCore/MCPs/private/kb_data/pkl`).
- Az input.md csak `kb_status`-t írt elő kötelezőként a Boot sequence-ben
  (nincs explicit `search_nodes` lépés, ugyanaz a minta, mint az előd-jobban)
  — a tartalmi forrás ehhez a riporthoz a fent felsorolt fájlok közvetlen
  olvasása.

## Prerequisite Check

Grep-parancs (a `cic-mcp-factory` klónban, `jobs/index.yaml`-on), PONTOSAN az
input.md által megadott, MÁR `id:`-re javított pattern-nel (a
`shared-session-catalog-consumer-001` riport "Findings" #1 / "Decisions
Proposed" #1 pontja által felfedett kulcsnév-eltérés ITT nem ismétlődik meg):

```
grep -n '\- id: "shared-session-catalog-consumer-001"' -A 3 jobs/index.yaml
```

**Teljes kimenet:**

```
260:  - id: "shared-session-catalog-consumer-001"
261-    level: "capability"
262-    status: "done"
263-    target_repo: "cic-mcp-shared"
```

**`status: "done"`** — a prerequisite KÉSZ, az `id:` kulccsal megerősítve
(NEM `job_id:`).

**Döntés: GO.** A `shared-session-catalog-consumer-001` prerequisite
teljesült — a riport folytatja a feladat 2-4. alpontjait.

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

Mind a 7 `@mcp.tool()`-dekorált függvény megjelenik, `grep -v test_` nem
szűrt ki semmit (nincs `test_` prefixű tool-definíció ebben a fájlban).

A 3 keresési tool, amelyre EZ a job fókuszál, file:line-nal:

| Tool | file:line (def) | Visszatérési mezők | RRF/fúzió? |
|---|---|---|---|
| `search_session_context(session_id, query, limit=20) -> list[dict]` | `mcp-server/session_server.py:94-95` | `chunk_id`, `turn_id`, `text`, `fused_score` (docstring 121-124. sor) | **IGEN** — hibrid (FTS+vektor, RRF-fúzió), `session_api.search_context_hybrid()` wrapper (docstring 96-99. sor) |
| `search_session_context_fts(session_id, query, limit=20) -> list[dict]` | `mcp-server/session_server.py:150-151` | `chunk_id`, `turn_id`, `text`, `rank` (docstring 189-193. sor) | NEM — kizárólag FTS, `session_api.search_context()` wrapper (`'simple'/'simple'` konfiguráció, lásd `session-retrieval-quality-report.md`) |
| `search_session_context_vector(session_id, query, limit=20) -> list[dict]` | `mcp-server/session_server.py:199-200` | `chunk_id`, `turn_id`, `text`, `similarity` (docstring 247-250. sor) | NEM — kizárólag cosine-vektor, `session_api.search_context_vector()` wrapper |

A 7. tool (`get_session_source_refs`) többsoros szignatúrája miatt a `-A 1`
csak a `def get_session_source_refs(` sort fogja el — a teljes szignatúra
(`mcp-server/session_server.py` 395-398. sor):

```python
@mcp.tool()
def get_session_source_refs(
    session_id: str, ref_kind: str | None = None, limit: int = 100
) -> list[dict]:
```

## Recurring-Concept Detection Without Semantic Claim Extraction

### A folyamat lépésről lépésre

1. **A shared aggregátor SAJÁT, korábban perzisztált klaszter-rekordjából
   indul ki** (`shared_core.*` séma, `architecture.md` "Schema szeparáció":
   "cross-session clusters, summaries, candidate memories, conflicts" —
   ez a `shared-session-catalog-consumer-001` riport "Persisted vs.
   Live-Queried Split" táblájának sora: "Cross-session klaszter/visszatérő-
   fogalom leírás... PERZISZTÁLT — ez NEM session-raw adat, hanem a shared
   réteg saját, levezetett aggregátuma"). Minden klaszter-rekord rendelkezik
   egy rövid, ember/korábbi-ciklus által rögzített CÍMMEL vagy
   KULCSSZÓ-LEÍRÁSSAL (pl. `"deploy pipeline incidens"`, `"Vault signing key
   rotáció"`) — ez a leírás a shared réteg SAJÁT, derivált adata, nem a
   session-tartalom szó szerinti másolata.
2. **A shared aggregátor a klaszter-leírást MINT `query` paramétert adja át**
   N különböző `session_id`-re, a `search_session_context(session_id, query,
   limit)` hibrid tool-on keresztül (`session_server.py:94-95`):
   ```
   for session_id in candidate_session_ids:
       results = search_session_context(
           session_id=session_id,
           query=cluster.keyword_description,   # pl. "Vault signing key rotáció"
           limit=20,
       )
   ```
   A `query` itt MINDIG a klaszter SAJÁT, már létező, rövid szöveges
   leírása — sosem egy adott session friss tartalmából most kivont,
   LLM-generált mondat.
3. **A hibrid tool a session-oldali, MÁR LÉTEZŐ RRF-fúziós logikát futtatja**
   (`session_api.search_context_hybrid()`, a `search_session_context()`
   docstring 96-99. sora szerint: "this function does NOT reimplement the
   RRF fusion logic" — a shared-oldali hívó kód csak a `query` string-et adja
   át, a fúzió, a `plainto_tsquery`/cosine-similarity számítás teljes
   egészében a session-oldali SQL függvényben történik).
4. **A visszakapott `fused_score`/`chunk_id`/`turn_id` sorok a "bizonyíték"
   egy adott session-ben** arra, hogy a klaszter fogalma ÚJRA előfordult — a
   shared aggregátor ezekből a `chunk_id`/`turn_id` PONTOKAT (nem a `text`
   tartalmat) fűzi a klaszter-rekordhoz provenance-pointerként, pontosan
   ugyanúgy, ahogy a `shared-session-catalog-consumer-001` riport
   "Persisted vs. Live-Queried Split" táblája már rögzítette ("Session
   FTS/vektor keresési eredmény... NEM perzisztált, csak az aktuális kérés
   idejére memóriában" a `text`/`fused_score` értékre, de a `chunk_id`/
   `turn_id` REFERENCIA perzisztálható).

### Miért tartja be a `forbidden_shortcuts` "deep semantic claim extraction
performed inside the session layer" tilalmát

1. **A session-rétegben SEMMI új logika nem fut.** A `search_session_context`
   tool egy "thin MCP wrapper" (`session_server.py` 21-23. sor: "Source of
   truth for the SQL functions this module calls (NOT reimplemented here)")
   egy MÁR LÉTEZŐ, MÁR TESZTELT (`session-hybrid-search-api-report.md`)
   `session_api.search_context_hybrid()` SQL függvény körül. A `query`
   paraméter feldolgozása a session oldalon KIZÁRÓLAG `embed_query()` (egy
   embedding-modell hívás, NEM egy LLM-alapú claim-extraction) +
   `plainto_tsquery`/cosine-similarity — ez lexikai+vektor-hasonlóság, nem
   szemantikai döntésbányászat. A `cic-mcp-session/CLAUDE.md` "Fő határok"
   "Nem" listája ("vegleges döntésbányászat") emiatt nem sérül: a hibrid
   keresés egy RANGSOROLÓ függvény, nem egy "mit jelent ez a session"
   értelmező réteg.
2. **A `query` paraméter forrása a shared SAJÁT, korábban már létező
   klaszter-leírása, NEM egy most végzett extrakció.** A klaszter-leírás
   keletkezése (hogyan jön létre EGYÁLTALÁN egy klaszter-cím egy session-ből)
   NEM ennek a jobnak a tárgya — ez a `shared-weighting-model-001` job
   (súlyozási/promotion logika) vagy egy jövőbeli implementációs job kérdése.
   Ez a job KIZÁRÓLAG azt definiálja, hogyan HASZNÁLJA fel a shared egy MÁR
   meglévő, rövid kulcsszó-leírást a keresztezett kereséshez — nem azt, hogy
   honnan ered a leírás szövege. Ha a leírás keletkezése valaha LLM-alapú
   szemantikai extrakciót igényelne, az a SHARED rétegben (a saját
   aggregátum-logikájában) történne, NEM a session rétegben átküldve — ez a
   `forbidden_shortcuts` pontos megfogalmazását tartja be ("...performed
   inside the SESSION layer", nem általában tiltja a klaszter-leírás
   létrehozását, csak azt, hogy ez a session MCP tool-határon átkerüljön).
3. **Az `embed_query()` egy rögzített, determinisztikus embedding-modell-
   hívás** (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimenzió — a
   `cic-mcp-session/CLAUDE.md` "Jelenlegi állapot" szerint MÁR bizonyítva),
   nem egy generatív LLM-hívás, amely új szöveges "claim"-et produkálna. A
   vektor-hasonlóság (cosine distance) és a lexikai egyezés (FTS `'simple'`
   tsquery) mindkettő SZÁMSZERŰ hasonlósági metrika egy ELŐRE MEGADOTT
   query-string és a session chunk-jai között — ez strukturálisan különbözik
   egy "olvasd el ezt a session-t és mondd meg, mi a fő állítása" típusú
   LLM-hívástól, amit a `forbidden_shortcuts` tilt.

## Cross-Session Query Shape And Ranking

### Hány session-t kérdez le egy ciklus, milyen sorrendben

1. **Session-szűrés `get_session_status`-szal** (`session_server.py:348-349`)
   — egy batch-aggregálási ciklus ELŐSZÖR a kandidált `session_id`-k listáját
   (pl. a `shared_core.*` provenance-kapcsolókból, mely session-ek
   játszottak már szerepet korábbi klaszter-rekordokban, VAGY egy faktort
   bővítő "utolsó N aktív session" lista) szűri a `status` mezőre, hogy
   lezárt/nem létező session-re ne próbáljon felesleges hibrid-keresést
   futtatni. Ez UGYANAZ a tool-felhasználási minta, amit a
   `shared-session-catalog-consumer-001` riport "Adapter Contract Table"-je
   már rögzített ("Aktív/lezárt session-ek szűrése egy aggregálási
   batch-ciklus előtt").
2. **A lekérdezett session-ek SZÁMA: "az utolsó N aktív session"** —
   konkrétan egy konfigurálható `N` (pl. 20-50, a tényleges érték a
   `shared-weighting-model-001` jobra van bízva, mert az a súlyozási modell
   kérdése, ITT csak a SORREND és a KOMBINÁLÁS módja a tárgy), rendezve a
   session `last_seen_at`/`started_at` mezője szerint (`get_session_status`
   válasz mezői) CSÖKKENŐ sorrendben — a legutóbb aktív session-ek előbb. Ez
   azért indokolt, mert egy visszatérő fogalom relevánsabb bizonyítéka
   frissebb session-ekben várható, és egy korlátozott batch-ciklusban
   (limitált futásidő/MCP-hívásszám) a frissebb session-eket előresorolni
   csökkenti annak esélyét, hogy egy régi, már lezárt/irreleváns session
   feleslegesen lekérdezésre kerüljön a lekérdezési költségvetésen belül.
3. **Soros (nem párhuzamos) végrehajtás session-enként** — minden
   `session_id`-re EGY `search_session_context(session_id, query, limit)`
   hívás (1 MCP round-trip / session), a fent rögzített sorrendben. A job
   ezt nem definiálja konkurens/párhuzamos hívásként, mert (a) a tényleges
   MCP kliens-implementáció (subprocess+stdio handshake, lásd
   `gateway-session-adapter-contract-001` precedens) konkurens hívás-kezelése
   egy IMPLEMENTÁCIÓS döntés, nem kontraktus-szintű kérdés, és (b) a
   soros minta egyszerűbben auditálható (minden hívás file:line szinten
   visszakövethető egy adott `session_id`-hez egy adott ciklusban) — egy
   jövőbeli implementációs jobnak szabad ezt párhuzamosítani, de ez a
   kontraktus nem KÖVETELI meg.

### Hogyan kombinálja a több session válaszának `fused_score`/`rank` értékét

**Döntés: session-enkénti min-max normalizálás, majd egyszerű összegzés —
NEM nyers `fused_score` összegzés/átlagolás.**

Indoklás:

1. **A `fused_score` skálája session-függő, nem abszolút.** A
   `search_session_context_hybrid()` RRF-fúziója (a `session_server.py`
   docstring szerint a session-oldali SQL függvény belső logikája, NEM
   reimplementálva) a session SAJÁT chunk-halmazán belüli RANGOT fúzionálja
   — egy 5 chunk-os session és egy 5000 chunk-os session `fused_score`
   eloszlása NEM feltétlenül összevethető skálán mozog (pl. egy kis
   session-ben egy közepes relevanciájú chunk is magas relatív rangot kaphat
   az alacsony versenyhelyzet miatt). Ha a shared egyszerűen összegezné vagy
   átlagolná a nyers `fused_score` értékeket session-ek között, egy kis
   session "véletlenül" magasabb cross-session összesített pontszámot
   kaphatna, mint egy nagy session valódi, erősebb bizonyítéka — ez egy
   session-méret torzítás, nem a fogalom valódi visszatérési erőssége.
2. **A normalizálás módja**: minden session válaszán BELÜL a `fused_score`
   értékeket [0, 1] tartományba skálázza (`(score - min) / (max - min)` az
   adott session összes visszaadott sorára, vagy ha csak 1 sor jön vissza,
   az érték 1.0-ra normalizálva) — ez a session-en BELÜLI relatív
   relevanciát őrzi meg, miközben kiküszöböli a session-ek KÖZÖTTI skála-
   eltérést.
3. **A kombinálás**: a normalizált értékeket session-enként ÖSSZESÍTI (nem
   átlagolja) egy cross-session rangsorba — minél TÖBB session-ben jelenik
   meg magas normalizált pontszámmal egy fogalom, annál magasabb a
   cross-session összesített pontszáma. Ez SZÁNDÉKOSAN előnyben részesíti a
   "sok session-ben visszatérő" mintát egy "egy session-ben extrém magas
   pontszámú, de csak ott előforduló" mintával szemben — ez direkt
   konzisztens a job céljával ("VISSZATÉRŐ fogalom" detektálása, nem
   "egyszeri kiugró találat" detektálása).
4. **Miért nem rang-alapú (pl. Borda count) kombinálás**: a `rank`
   (sorszám-alapú) kombinálás elveszítené azt az információt, HOGY MENNYIVEL
   jobb egy találat a másiknál egy adott session-en belül (egy session-ben az
   1. és 2. helyezett közötti pontszám-különbség lehet minimális vagy
   drámai) — a normalizált SCORE-alapú összesítés megőrzi ezt a relatív
   erősséget, miközben a normalizálás már kezeli a session-ek közötti
   skála-eltérést. A rang-alapú kombinálás egy alternatíva lett volna, de
   kevésbé informatív ugyanazon kontraktus-szintű döntés mellett.
5. **Explicit korlátozás**: ez a normalizálási/kombinálási LOGIKA egy
   kontraktus-szintű DÖNTÉS, nem implementáció — a tényleges súlyozási
   FAKTOROK (recurrence count, factory/PR/artifact linkage, recency-bónusz)
   a `shared-weighting-model-001` job tárgya (`job-slices.yaml:769-790`,
   prerequisite: ez a job). Ez a job csak azt rögzíti, hogy a `fused_score`
   értékek session-ek közötti KOMBINÁLÁSA normalizálást igényel, nem azt,
   hogy a végső promotion-küszöb hogyan számítódik.

## Conflict/Superseded Candidate Data Model

### A `shared_core.*` jelölt-rekord adatmodellje

A `shared_core.*` séma (`architecture.md` "Schema szeparáció": "cross-session
clusters, summaries, candidate memories, conflicts") egy jelölt-rekordján
(analóg, de NEM azonos a `GatewayContextEnvelope.conflicts[]` mintájával — az
egy MÁSIK trust-domain réteg, MÁSIK schema; itt a shared SAJÁT mezőiről van
szó):

| Mező | Típus (kontraktus-szintű) | Jelentés |
|---|---|---|
| `candidate_id` | identifier | A shared-oldali jelölt-rekord saját azonosítója |
| `keyword_description` | text | A klaszter rövid kulcsszó/lekérdezés-leírása (lásd "Recurring-Concept Detection" 1. lépés) |
| `trust` | enum (`mixed`/`candidate`/`reviewed_shared`) | A `shared-session-catalog-consumer-001` riport "Trust Mapping" szekciója szerint |
| `canonical` | bool, MINDIG `false` | Analóg a `session-ingress-envelope.schema.yaml` `canonical: const: false` mintájával — egy jövőbeli implementációs schema-ban ugyanígy kikényszerítendő |
| `provenance_refs[]` | lista `{session_id, chunk_id, turn_id, content_hash}` | A `get_session_source_refs`/`search_session_context` válaszokból perzisztált pointerek (NEM a `text` tartalom) |
| `conflicting_with` | nullable lista candidate_id-kre | Lásd lent |
| `superseded_by` | nullable candidate_id | Lásd lent |
| `superseded_at` | nullable timestamp | Mikor jelölték superseded-nek |
| `superseded_reviewed_by` | nullable identifier (ember/orchestrátor azonosító) | Lásd "A superseded döntés embert igényel-e" |

### `conflicting_with` — mikor és hogyan jelöli a shared

Amikor a shared aggregátor egy `keyword_description` query-vel KÉT (vagy
több) `session_id`-ből kap vissza bizonyítékot, és a két session evidence-e
(pl. két különböző session-ben a chunk `text`-je — amit a shared NEM
perzisztál, csak az adott review-pillanatban a `get_session_context_pack`
hívással néz meg) EGYMÁSNAK ELLENTMOND (pl. egy korábbi session szerint "a
deploy pipeline X mintát követ", egy újabb session szerint "a deploy pipeline
Y mintát követ, X-et elvetettük"), a két candidate-rekord
EGYMÁSRA-HIVATKOZÓ `conflicting_with` mezőt kap (`candidate_A.conflicting_
with = [candidate_B.candidate_id]`, és fordítva). Ez egy SZIMMETRIKUS jelölés
— a `conflicting_with` mező NEM állítja, melyik a "helyes", csak azt, hogy
emberi/review-figyelmet igényel a kettő közötti eltérés. Ez analóg a
`GatewayContextEnvelope.conflicts[]` mintájával (felszínre hozza a
konfliktust, nem dönt róla automatikusan), de a shared SAJÁT
`shared_core.*` rekordján él, nem a gateway envelope-on.

**Ki/mi DETEKTÁLJA, hogy két candidate ellentmond?** Ez a job KIZÁRÓLAG az
ADATMODELLT definiálja (a `conflicting_with` mező létezését és szemantikáját)
— a tényleges ÖSSZEHASONLÍTÁSI logika (hogyan dönti el a shared, hogy két
chunk "ellentmond" egymásnak) explicit NEM ennek a jobnak a tárgya. Mivel a
`forbidden_shortcuts` tiltja a "deep semantic claim extraction... inside the
session layer"-t, és ez a job sem vihet át rejtve egy ugyanilyen mély
szemantikai ellentmondás-detektálást a SHARED rétegbe ÚJ NLP/LLM-réteg
formájában, a konfliktus-DETEKTÁLÁS mechanizmusa egy KÜLÖN, jövőbeli
döntés tárgya (lásd "Risks" #3 és "Next Jobs") — itt csak az ADATMODELL,
amibe egy ilyen detektálás (akár heurisztikus, akár emberi review-alapú)
eredménye írható.

### `superseded_by` — mikor és hogyan jelöli a shared

Amikor egy candidate-ot egy ÚJABB candidate FELÜLÍR (pl. egy korábbi klaszter
állítása elavulttá vált egy frissebb session evidence fényében), a régebbi
candidate `superseded_by` mezője az újabb candidate `candidate_id`-jét kapja,
és a régebbi candidate `trust` értéke NEM törlődik (a `provenance_refs[]`
megmarad auditálhatóságra), csak egy `superseded_at` timestamp kerül rá.

### A "superseded" döntés embert igényel-e, vagy lehet automatikus heurisztika

**Döntés: a `superseded_by` MEZŐ BEÍRÁSA (jelölt-szintű javaslat) lehet
automatikus heurisztika (pl. időbélyeg-alapú: "ha egy újabb session
evidence-e azonos `keyword_description`-höz magasabb cross-session pontszámot
ad, mint a régebbi candidate, a régebbi automatikusan `superseded_by`-t
kaphat"), DE ez a heurisztikus jelölés `trust` szinten NEM léphet túl a
`mixed`/`candidate` szinten — a `reviewed_shared`-re emelés (ami szükséges
ELŐFELTÉTELE bármilyen későbbi, akár csak shared-belüli magasabb-bizalmú
felhasználásnak) MINDIG embert igényel.**

Indoklás a `cic-mcp-shared` trust modellje szerint:

1. **A `cic-mcp-shared/CLAUDE.md` "Trust modell" explicit kimondja**: "A
   shared réteg sem állít elő canonical tényt automatikusan — a knowledge
   promotion külön, emberi review-flow, nem ennek a rétegnek a feladata." Ez
   a `canonical`-ra vonatkozik direktben, de a `trust` enum belső lépcsője
   (`mixed` → `candidate` → `reviewed_shared`) ANALÓG korlátozás alá esik:
   ha egy automatikus heurisztika közvetlenül `reviewed_shared`-re emelhetne
   egy superseded-jelöltet, az UGYANAZT a kockázatot hordozná, mint egy
   automatikus canonical-promotion — egy NEM-review-zott állítás kapna
   magasabb bizalmi besorolást, mint amit egy automatikus folyamat
   legitimálhat.
2. **A `forbidden_shortcuts` explicit tiltja**: "automatikus `canonical`
   promotion egy 'superseded' döntés alapján emberi review nélkül" (input.md
   "Forbidden Shortcuts" 3. pont). Ez direkt a "superseded" döntésre
   vonatkozik — a tiltás PONTOSAN azt a forgatókönyvet nevezi meg, amit ez a
   szekció definiál: egy superseded-jelölés ÖNMAGÁBAN nem elég ahhoz, hogy
   bármi canonical-lá váljon.
3. **A `reviewed_shared`-hez vezető review-lépés nélkül egy automatikus
   "superseded" jelölés se válhatna `canonical`-lá** — ez a job-leírás
   explicit megfogalmazása (input.md feladat 4. bekezdés vége). Tehát a
   heurisztikus `superseded_by` MEZŐ-beírás (egy JAVASLAT, hogy "ezt nézd
   meg, valószínűleg elavult") elfogadható AUTOMATIKUSAN, mert ez csak egy
   jelzés/sorba-állítás egy review-queue-hoz — de a `trust` mező TÉNYLEGES
   emelése `reviewed_shared`-re (ami a "ez a candidate immár a magasabb
   bizalmú, felülíró verzió, ELFOGADVA shared-szintű használatra" állítást
   jelentené) emberi jóváhagyást igényel.
4. **Gyakorlati elválasztás**: `superseded_by` mező beírása = "jelölés,
   hogy van egy újabb verzió" (automatikus heurisztika OK). `trust:
   reviewed_shared` rászignálása a superseded-jelölt PÁRJÁRA (az ÚJABB
   candidate-ra) = emberi review szükséges. Egy automatikus heurisztika tehát
   LÁTHATÓVÁ teheti a konfliktust/elavulást (ezt a `conflicting_with`/
   `superseded_by` mezőpár ÉPP ezért létezik — hogy a review-queue-nak
   legyen mit feldolgoznia), de NEM dönthet a véglegesítésről.

## Findings

1. **A prerequisite (`shared-session-catalog-consumer-001`) `done` státuszú**,
   az `id:` kulccsal megerősítve (lásd "Prerequisite Check") — az input.md
   ebben a jobban MÁR a helyes (`id:`) grep-pattern-t adta meg, az előd-job
   által felfedett hiba itt nem ismétlődött meg.
2. **A `session-retrieval-quality-report.md` LÉTEZIK**, de NEM a hibrid
   RRF-fúzió ELSŐDLEGES dokumentációs forrása — az a `search_context()`
   (FTS-only) és `session_status()` (job_type-aware union) javításairól
   szól, NEM a `search_context_hybrid()`-ról. A hibrid RRF-fúzió tényleges
   szerződése a `session_server.py` modul-docstring-jében (24-29. sor) és a
   `search_session_context()` docstring-jében (96-125. sor) él — ezeket a
   riport idézte forrásként, a `session-hybrid-search-api-migration.sql`
   tényleges SQL-implementációja NEM volt kötelező forrás ehhez a
   kontraktus-szintű riporthoz, és nem lett közvetlenül elolvasva. Ez egy
   bridge, amit egy jövőbeli (akár implementációs) jobnak explicit kellene
   bejárnia, ha a tényleges RRF-súlyozási formulára (hogyan kombinálja az
   FTS-rangot és a cosine-similarity-t belül) van szükség.
3. **A `search_session_context_fts`/`search_session_context_vector` tool-ok
   NEM kerülnek felhasználásra ebben a kontraktusban** — a job a hibrid
   (`search_session_context`) tool-t definiálja elsődleges belépési pontként,
   konzisztensen az előd-riport "Decisions Proposed" #3 pontjával ("a
   különálló FTS/vektor tool-ok finomhangolása egy KÉSŐBBI
   (`shared-cross-session-search-001`) jobban dönthető el, nem itt" — ez a
   "később" MOST van, és a döntés az, hogy a hibrid tool ELEGENDŐ, a
   különálló FTS/vektor tool-ok finomhangolása NEM szükséges ehhez a
   kontraktushoz, mert a hibrid már kombinált rangsorolást ad).
4. **A `cic-mcp-session` MCP szerver MÉG NINCS bekötve élesben** semelyik
   `.mcp.json`-ba (`cic-mcp-session/CLAUDE.md` "Jelenlegi állapot" záró
   bekezdése) — ez a kockázat az előd-riportból ÖRÖKÖLT, és továbbra is
   érvényes: egy jövőbeli implementációs jobnak ezt a wiring-rést kezelnie
   kell, mielőtt a cross-session keresési kontraktus valós MCP-hívásokkal
   bizonyítható lenne.
5. **A `session_api.search_context_hybrid()` paraméter-sorrendje**
   (`p_session_id, p_query, p_query_embedding, p_limit`, a `session_server.py`
   24-26. sor szerint) azt jelenti, hogy a Python-oldali wrapper
   (`search_session_context`) a `query` szöveget KÉTSZER használja: egyszer
   verbátim (FTS oldal) és egyszer `embed_query()`-n átküldve (vektor oldal)
   — ez a job "Recurring-Concept Detection" szekciója szerint pontosan
   konzisztens azzal az állítással, hogy a `query` MINDIG egy egyszerű,
   előre megadott string, mert UGYANAZT a string-et adja át a wrapper mind a
   lexikai, mind a vektor oldalnak, nincs köztes szemantikai feldolgozás.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `shared-session-catalog-consumer-001` prerequisite `status: "done"` | proven | `jobs/index.yaml:260-263`, `- id: "shared-session-catalog-consumer-001"`, `status: "done"` | Fájl direkt grep + idézés (`id:` kulcs) | low |
| `search_session_context(session_id, query, limit=20) -> list[dict]` hibrid (RRF) keresés, `fused_score` mezővel | proven | `mcp-server/session_server.py:94-95` (def), docstring 96-99. sor ("Hybrid (FTS + vector, RRF-fused)"), 121-124. sor (`fused_score` visszatérési mező) | Fájl direkt grep + Read, sor idézve | low |
| `search_session_context_fts(session_id, query, limit=20) -> list[dict]` FTS-only, `rank` mezővel | proven | `mcp-server/session_server.py:150-151` (def), docstring 189-193. sor (`rank` mező) | Fájl direkt grep + Read, sor idézve | low |
| `search_session_context_vector(session_id, query, limit=20) -> list[dict]` vektor-only, `similarity` mezővel | proven | `mcp-server/session_server.py:199-200` (def), docstring 247-250. sor (`similarity` mező) | Fájl direkt grep + Read, sor idézve | low |
| A `search_session_context` tool NEM reimplementálja az RRF-fúziós logikát, csak a session_api.* SQL függvényt hívja | proven | `session_server.py` docstring (21-23. sor modul-szinten, 96-99. sor a tool-on): "this function does NOT reimplement the RRF fusion logic" | Fájl direkt idézése | low |
| `embed_query()`/`to_pgvector_literal()` reuse, nem reimplementáció | proven | `session_server.py:88` import sor, 126-127. sor a `search_session_context`-ben | Fájl direkt idézése | low |
| A cross-session query-alak: `query` paraméter MINDIG előre megadott klaszter-leírás, nem session-tartalomból kivont LLM-claim | proven (kontraktus-szintű állítás) | "Recurring-Concept Detection" szekció, a `forbidden_shortcuts` pontos szövegére (job-slices.yaml:767) hivatkozva | Szöveges indoklás a riportban, normatív forrás idézve | medium — ez egy TERVEZETT határ, nincs implementáció/schema-kikényszerítés (pl. egy `const`/enum mező) ami ezt automatikusan ellenőrizné egy jövőbeli kódban |
| Cross-session rangsorolás: session-enkénti min-max normalizálás + összesítés, NEM nyers `fused_score` összegzés | proven (kontraktus-szintű döntés) | "Cross-Session Query Shape And Ranking" szekció, indoklás a session-méret torzítás kockázatára | Szöveges indoklás, nincs futtatott kód (explicit "Nem cél") | medium — a tényleges súlyozási faktorok (`shared-weighting-model-001`) még nincsenek meghatározva, ez csak a kombinálási MÓD döntése |
| `session_api.search_context_hybrid()` SQL szignatúrája (`p_session_id, p_query, p_query_embedding, p_limit`) | proven | `session_server.py:24-26` (modul-docstring, "Source of truth" szekció, idézve a tényleges SQL signature-t) | Fájl direkt idézése (a `.sql` fájl maga NEM volt kötelező/elolvasott forrás, csak a Python docstring idézi) | medium — a tényleges SQL-implementáció (RRF-súlyozási formula belseje) nem volt ennek a riportnak közvetlen forrása, lásd "Findings" #2 |
| `conflicting_with`/`superseded_by` adatmodell a `shared_core.*` jelölt-rekordon, `GatewayContextEnvelope.conflicts[]`-tól független saját mezőkkel | proven (kontraktus-szintű definíció) | "Conflict/Superseded Candidate Data Model" szekció, mezőtábla + szöveges szemantika | Szöveges definíció, nincs implementált schema (explicit "Nem cél": `SessionIngressEnvelope`/`GatewayContextEnvelope` schema módosítása NEM, és a `shared_core.*` schema-implementáció sem ez a job tárgya) | medium — nincs schema-fájl, ami ezt kikényszerítené, csak ez a kontraktus-riport |
| `superseded_by` mező AUTOMATIKUS heurisztikával beírható, de a `trust: reviewed_shared` emelés emberi review-t igényel | proven (kontraktus-szintű döntés, normatív forrásra alapozva) | `cic-mcp-shared/CLAUDE.md` "Trust modell" idézet + `forbidden_shortcuts` 3. pont (input.md "Forbidden Shortcuts": "automatikus canonical promotion egy 'superseded' döntés alapján emberi review nélkül") | Két fájl/forrás direkt idézése és összevetése | low — ez a `forbidden_shortcuts` EXPLICIT szövegéből levezetett döntés, nem önkényes |
| Tényleges kereső/aggregátor kód implementálva és tesztelve | missing | Ez a job explicit "Nem cél"-ja — nincs adapter-/aggregátor-kód, nincs `shared_core.*` séma implementáció | N/A — ez a `status_after_merge: experimental` indoklása | high — ez a fő limitáció, lásd "Risks" |

## Decisions Proposed

1. **A hibrid `search_session_context` tool az ELSŐDLEGES (és egyetlen
   szükséges) belépési pont** a cross-session visszatérő-fogalom kereséshez
   — a `search_session_context_fts`/`search_session_context_vector`
   különálló tool-ok finomhangolása NEM szükséges ehhez a kontraktushoz
   (lásd "Findings" #3). Egy jövőbeli implementációs jobnak NEM kell ezt a
   két tool-t bekötnie, ha a hibrid elegendő bizonyítékot ad.
2. **A cross-session rangsoroláshoz session-enkénti min-max normalizálás
   szükséges** a nyers `fused_score` összegzése/átlagolása helyett — a
   session-méret okozta skála-torzítás kockázata miatt (lásd "Cross-Session
   Query Shape And Ranking" indoklás). Ez egy javaslat a
   `shared-weighting-model-001` jobnak, amely a tényleges súlyozási
   faktorokat (recurrence, factory/PR/artifact linkage, recency) ráépítené
   ezen a normalizált alapon.
3. **A `superseded_by` mező heurisztikus (automatikus) beírható, a
   `reviewed_shared` trust-emelés viszont mindig emberi review-t igényel** —
   ez egy explicit javaslat a `shared_core.*` schema egy jövőbeli
   implementációs jobjának, hogy a két lépést (jelölés vs. trust-emelés)
   STRUKTURÁLISAN különítse el (pl. két külön mező/külön API-hívás, nem egy
   közös "supersede" akció, amely mindkettőt egyszerre végzi el).
4. **A `session-hybrid-search-api-migration.sql` tényleges RRF-súlyozási
   formulájának elolvasása** egy jövőbeli jobnak ajánlott, ha a cross-session
   rangsorolás finomhangolása (`shared-weighting-model-001` vagy egy
   ezt-követő job) a session-oldali fúziós súlyokat is figyelembe akarná
   venni — ez a riport ezt a fájlt nem olvasta el (nem volt kötelező
   forrás), lásd "Findings" #2.

## Rejected / Out Of Scope

- **Tényleges kereső/aggregátor kód implementálása** — explicit "Nem cél",
  a `status_after_merge: experimental` ezt indokolja.
- **LLM-alapú szemantikai claim-extraction vagy entitás-kinyerés bármilyen
  formában** — explicit "Nem cél" és `forbidden_shortcuts` tétel; a teljes
  "Recurring-Concept Detection" szekció ezt a határt indokolja és tartja be.
- **`SessionIngressEnvelope`/`GatewayContextEnvelope` schema módosítása** —
  explicit "Nem cél", semelyik schema-fájl nem érintett.
- **`cic-mcp-session` repo módosítása** — explicit "Nem cél", a klón
  KIZÁRÓLAG olvasásra történt, semmi nem commitolva/pusholva bele.
- **`shared-weighting-model-001`** (a Phase 4 harmadik jobja) — explicit "Nem
  cél", a tényleges súlyozási formula/score-számítás (recurrence,
  factory/PR/artifact linkage, recency-faktor) RÁ van bízva, ez a job csak a
  query-alak, a normalizálási elv és a konfliktus-adatmodell.
- **A konfliktus-DETEKTÁLÁS tényleges mechanizmusa** (hogyan dönti el a
  rendszer, hogy két chunk "ellentmond" egymásnak) — explicit kívül esik ezen
  a jobon, mert ez magában hordozná a mély szemantikai
  összehasonlítás/claim-extraction kockázatát, amit a `forbidden_shortcuts`
  tilt; ez egy jövőbeli, külön döntést igénylő kérdés (lásd "Risks" #3 és
  "Next Jobs").
- **A canonical promotion folyamat/review-flow részletes kidolgozása** —
  csak az ÁLLÍTÁS szükséges (és megtörtént a "Conflict/Superseded Candidate
  Data Model" szekcióban), hogy a `reviewed_shared` trust-emelés emberi
  review-t igényel.

## Risks

1. **Nincs implementáció, ami a query-alakot/rangsorolást valódi adaton
   validálná.** Ez a fő ok, amiért `status_after_merge: experimental`, nem
   `candidate` (lásd input.md "Target" szekció "status indoklás") — egy
   jövőbeli implementációs jobnak (a `gateway-session-adapter-contract-001`
   → `session-context-pack-v1-001` mintát követve) valós, futtatott
   bizonyítékot kellene adnia.
2. **A `session-hybrid-search-api-migration.sql` tényleges RRF-súlyozási
   formulája nem volt ennek a riportnak közvetlen forrása** (lásd "Findings"
   #2, "Decisions Proposed" #4) — ha a cross-session normalizálási döntés
   (min-max session-enkénti normalizálás) a session-oldali fúziós súlyokkal
   ütközne (pl. ha a session-oldali RRF már implicit normalizál valamilyen
   módon, amit ez a riport nem vett figyelembe), egy jövőbeli implementációs
   jobnak ezt explicit ellenőriznie kell.
3. **A konfliktus-DETEKTÁLÁS mechanizmusa (nem csak az adatmodell) nincs
   definiálva** — ez tudatos hiány (lásd "Rejected / Out Of Scope"), mert a
   tényleges összehasonlítási logika kidolgozása vagy egy heurisztikus
   (pl. kulcsszó-átfedés-alapú, NEM LLM-alapú) megoldást igényelne, vagy
   emberi review-queue-t — ha egy jövőbeli implementációs job ide egy
   NLP/LLM-alapú "ellentmondás-felismerő" réteget építene be, az ÚJRA
   megsértené a `forbidden_shortcuts`-ot, csak a shared rétegben, nem a
   session rétegben — ez egy explicit figyelmeztetés a következő job
   szerzőjének.
4. **A session-enkénti min-max normalizálás kis mintaszámnál (pl. 1-2 sor
   visszaadva egy session-ből) instabil lehet** — ha egy session csak 1 sort
   ad vissza, a normalizálás definíció szerint 1.0-ra esik, ami torzíthatja
   a cross-session összesítést egy ritkán előforduló, alacsony konfidenciájú
   találat felé. Ez egy implementációs finomhangolási kérdés, amit a
   `shared-weighting-model-001` jobnak kellene kezelnie (pl. egy minimum
   mintaszám-küszöb bevezetésével).
5. **A `cic-mcp-session` MCP szerver még nincs bekötve élesben** (örökölt
   kockázat az előd-riportból) — egy jövőbeli implementációs jobnak ezt is
   kezelnie kell, különben a tervezett cross-session keresési kontraktus
   sosem tudna valódi MCP-hívást indítani.

## Definition Of Done Check

| DoD pont | Státusz | Megjegyzés |
|---|---|---|
| prerequisite (`shared-session-catalog-consumer-001`) `id:` kulccsal megerősítve (NEM `job_id:`), GO/NO-GO döntés indokolva | PASS | "Prerequisite Check" szekció — `status: "done"`, GO döntés |
| a 3 keresési tool file:line-nal idézve | PASS | "Session MCP API Surface" szekció — `94-95`, `150-151`, `199-200`, teljes grep-kimenet idézve |
| a visszatérő-fogalom detektálás explicit lexikai/vektor-alapú, NEM szemantikai-claim-extraction-alapú, indoklással | PASS | "Recurring-Concept Detection Without Semantic Claim Extraction" szekció, 3 indoklási pont |
| cross-session query shape és rangsorolási döntés indokolva | PASS | "Cross-Session Query Shape And Ranking" szekció, session-szám/sorrend + normalizálási döntés indoklással |
| konfliktus/superseded adatmodell definiálva, a review-igény tisztázva | PASS | "Conflict/Superseded Candidate Data Model" szekció, mezőtábla + 4 pontos indoklás a review-igényre |
| claim-evidence tábla kitöltve, nem üres | PASS | 13 sor, lásd fent |

## Next Jobs

1. **`shared-weighting-model-001`** (Phase 4, `job-slices.yaml:769-790`,
   prerequisite: ez a job) — a tényleges súlyozási faktorok (recurrence,
   factory/PR/artifact linkage, recency) és a `promotion_candidate` schema
   mezőinek definiálása, ráépítve a session-enkénti normalizálási döntésre
   (lásd "Decisions Proposed" #2).
2. **Egy jövőbeli döntési job a konfliktus-DETEKTÁLÁS mechanizmusára** (nem
   csak az adatmodellre, amit ez a job már definiált) — explicit figyelemmel
   a `forbidden_shortcuts`-ra, hogy a detektálási logika ne váljon rejtett
   szemantikai claim-extraction-né (lásd "Risks" #3).
3. **Egy jövőbeli implementációs job**, ami a `shared_core.*` schema-t
   (`architecture.md` "Schema szeparáció") és a tényleges MCP-kliens kódot
   megírja, a `gateway-session-adapter-contract-001` →
   `session-context-pack-v1-001` mintát követve (real subprocess + stdio
   handshake) — ez emelné a státuszt `experimental`-ról `candidate`-re.
4. **Egy karbantartó job, ami a `cic-mcp-session` MCP szervert bekötné**
   legalább egy `.mcp.json`-ba (örökölt, még nyitott kockázat — lásd "Risks"
   #5) — prerequisite a 3. pontban javasolt implementációs jobhoz.
5. **Egy kis kiegészítő olvasási feladat (vagy egy jövőbeli implementációs
   job része)**, ami a `session-hybrid-search-api-migration.sql` tényleges
   RRF-súlyozási formuláját elolvassa, ha a normalizálási döntés (lásd
   "Risks" #2) finomhangolást igényelne a session-oldali fúziós súlyok
   fényében.
