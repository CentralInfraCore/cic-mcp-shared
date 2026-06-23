# shared-weighting-model-001 Output

## Scope

Ez a job a Phase 4 HARMADIK, UTOLSÓ jobja a `cic-mcp-shared` repóban
(`execution-phases.md` "Phase 4 - cic-mcp-shared", `job-slices.yaml:769-790`). A
`shared-cross-session-search-001` (mergelve, `status: "done"`) definiálta a
cross-session query-alakot (session-enkénti min-max normalizálás + összesítés a
`fused_score`-okra) és a konfliktus/superseded jelölt-adatmodellt
(`candidate_id`, `trust`, `canonical`, `provenance_refs[]`, `conflicting_with`,
`superseded_by`) — de explicit DEFERRÁLTA "a tényleges súlyozási FAKTOROK
(recurrence count, factory/PR/artifact linkage, recency-bónusz)" kérdését ERRE
a jobra (`output/shared-cross-session-search.md` "Cross-Session Query Shape And
Ranking" 5. pont, és "Next Jobs" #1).

Ez a job KONTRAKTUS-szintű riport (NEM implementáció): definiálja a SÚLYOZÁSI
MODELLT — milyen konkrét faktorok emelnek egy `mixed` trust-szintű jelöltet
formális `promotion_candidate` (`candidate`) állapotba —, ÉS explicit kimondja
(a thead02 döntési alap szerint: "AI gyártja és validálja a capability-t, de a
legitimáció mindig embernél/orchestrátornál marad"), hogy a
`cic-mcp-knowledge`-be való canonical promotion EGY TELJESEN KÜLÖN, emberi
review-flow, amit ez a job NEM specifikál részletesen és NEM automatizál.

Nincs futtatható súlyozó-algoritmus kód, nincs schema-implementáció
(`shared_core.*`), és a `cic-mcp-session` repo nem érintett ehhez a jobhoz
(a forrás kizárólag a `cic-mcp-factory` és `cic-mcp-shared` repókban él). A
`status_after_merge: experimental` indoklása megegyezik az előd-jobokéval:
nincs futtatható súlyozó-algoritmus kód, csak kontraktus — `candidate`-hez egy
tényleges implementáció és legalább egy valós, futtatott bizonyíték kellene (a
`gateway-session-adapter-contract-001` → `session-context-pack-v1-001`
mintát követve).

## Inputs Read

- `${WORKDIR}/.cic-context/factory-docs/architecture.md` — "Komponens térkép"
  (`cic-mcp-shared`: "tobb session osszefuzese", "factory job/PR/artifact
  kapcsolas", "sulyozas", "promotion candidates"), "Trust modell" (`shared:
  trust: mixed / candidate / reviewed_shared, canonical: false by default`),
  "Factory legitimacio" szekció TELJES egészében (NORMATÍV — idézve a
  "Canonical Promotion Boundary" szekcióban).
- `${WORKDIR}/jobs/index.yaml` — `shared-cross-session-search-001` bejegyzés
  (260. sortól, lásd "Prerequisite Check"), `status: "done"` mező
  ellenőrzése, `id:` kulccsal (NEM `job_id:` — a `shared-session-catalog-
  consumer-001` riport "Findings" #1 hibáját itt nem ismételtük meg, az
  input.md ebben a jobban már a helyes pattern-t adta meg).
- `${WORKDIR}/jobs/.schema/meta.yaml` — a `capability:` blokk mezői
  (`id`, `target_repo`, `change_type`, `status_after_merge`), GREP-pel
  megerősítve (lásd "Weighting Factors" — factory-linkage faktor).
- `${WORKDIR}/jobs/shared-cross-session-search-001/meta.yaml` — a tényleges,
  kitöltött `capability.id`/`capability.target_repo` mezők egy MÁR lezárt
  (`status: "done"`) jobból (lásd "Weighting Factors" — factory-linkage
  faktor bizonyítéka).
- `${WORKDIR}/jobs/shared-cross-session-search-001/output/shared-cross-
  session-search.md` — TELJES egészében, NORMATÍV. A "Conflict/Superseded
  Candidate Data Model" mező-táblája (`candidate_id`, `keyword_description`,
  `trust`, `canonical`, `provenance_refs[]`, `conflicting_with`,
  `superseded_by`, `superseded_at`, `superseded_reviewed_by`) a közvetlen
  kiindulópont a "promotion_candidate Schema Fields" szekcióhoz. A
  "Cross-Session Query Shape And Ranking" (session-enkénti min-max
  normalizálás + összesítés) a közvetlen alapja annak, hogyan kombinálódnak
  az új súlyozási faktorok a meglévő cross-session pontszámmal.
- `${WORKDIR}/jobs/shared-session-catalog-consumer-001/output/shared-session-
  catalog-consumer.md` — "Trust Mapping" szekció (`mixed`/`candidate`/
  `reviewed_shared` leképezés, és "Miért NEM kaphat egy shared-aggregátum
  `canonical: true`-t automatikus promotion nélkül" alszekció).
- `cic-mcp-shared/CLAUDE.md` (target repo) — "Fő határok" (Igen: "súlyozás",
  "promotion candidates"; Nem: "canonical layer"), "Trust modell" (`trust:
  mixed / candidate / reviewed_shared`, `canonical: false by default`, "A
  shared réteg sem állít elő canonical tényt automatikusan — a knowledge
  promotion külön, emberi review-flow").
- `${WORKDIR}/.cic-context/factory-docs/job-slices.yaml` — `shared-weighting-
  model-001` bejegyzés (sor 769-790): `prerequisites:
  [shared-cross-session-search-001]`, `acceptance_gates` (3 pont),
  `required_evidence` ("Weighting factor list with rationale.",
  "promotion_candidate schema fields."), `forbidden_shortcuts` ("shared
  auto-promotes a candidate to canonical without human review"). NORMATÍV
  forrás ehhez a jobhoz.
- `${WORKDIR}/CLAUDE.md` (a `cic-mcp-factory` repo saját CLAUDE.md-je) —
  thead02 sora a "Felülvizsgált AI párbeszédek" táblában: "cic-mcp-*
  família elnevezés + trust-domain rétegezés; AI gyártja/validálja, ember
  legitimálja a capability-t".

### Boot sequence eredménye

- `kb_status`: a cic-graph KB elérhető és betöltött — `chunks.pkl`,
  `graph_nodes.pkl`, `graph_edges.pkl`, `inverted_index.pkl`, `faiss.index`,
  `bm25.pkl` mind `exists: true` (`data_dir`:
  `/home/sinkog/sync/git.partners/CentralInfraCore/MCPs/private/kb_data/pkl`).
- Az input.md ehhez a jobhoz is csak `kb_status`-t írt elő kötelezőként a
  Boot sequence-ben (nincs explicit `search_nodes` lépés, ugyanaz a minta,
  mint az előd-két jobban) — a tartalmi forrás ehhez a riporthoz a fent
  felsorolt fájlok közvetlen olvasása.

## Prerequisite Check

Grep-parancs (a `cic-mcp-factory` klónban, `jobs/index.yaml`-on), PONTOSAN az
input.md által megadott, `id:`-re javított pattern-nel:

```
grep -n '\- id: "shared-cross-session-search-001"' -A 3 jobs/index.yaml
```

**Teljes kimenet:**

```
252:  - id: "shared-cross-session-search-001"
253-    level: "capability"
254-    status: "done"
255-    parent: "shared-session-catalog-consumer-001"
```

**`status: "done"`** — a prerequisite KÉSZ, az `id:` kulccsal megerősítve
(NEM `job_id:`).

**Döntés: GO.** A `shared-cross-session-search-001` prerequisite teljesült —
a riport folytatja a feladat 2-4. alpontjait.

## Weighting Factors

A `shared-cross-session-search-001` riport "Cross-Session Query Shape And
Ranking" szekciója (5. pont) a session-enkénti min-max NORMALIZÁLT
`fused_score` ÖSSZESÍTÉSÉT rögzítette mint a cross-session kombinálás MÓDJA —
de explicit NEM definiálta a végső promotion-küszöböt vagy azt, hogy MILYEN
további faktorok módosítják ezt az összesített pontszámot. Ez a szekció ezt a
3 faktort definiálja.

### 1. Recurrence count

**Definíció**: hány KÜLÖNBÖZŐ `session_id`-ben jelent meg bizonyíték
ugyanarra a `keyword_description`-re (klaszter-leírásra).

**Kapcsolódó forrás** — a `shared-cross-session-search-001` riport
"Cross-Session Query Shape And Ranking" → "Hogyan kombinálja a több session
válaszának `fused_score`/`rank` értékét" szekció 3. pontja:

> "a normalizált értékeket session-enkénti ÖSSZESÍTI (nem átlagolja) egy
> cross-session rangsorba — minél TÖBB session-ben jelenik meg magas
> normalizált pontszámmal egy fogalom, annál magasabb a cross-session
> összesített pontszáma. Ez SZÁNDÉKOSAN előnyben részesíti a 'sok
> session-ben visszatérő' mintát egy 'egy session-ben extrém magas
> pontszámú, de csak ott előforduló' mintával szemben."

**Indoklás**: a `recurrence_count` MAGA a cross-session normalizált-összesített
pontszám egyik közvetlen mozgatórugója — minél több session-ben fordul elő
egy fogalom magas normalizált relevanciával, annál magasabb az összesített
pontszám. Ez a faktor nem ÚJ mennyiség, hanem a már definiált cross-session
összesítés EGYIK explicit, külön mérhető komponense (a darabszám maga,
elválasztva attól, hogy az egyes session-ekben MENNYIRE magas volt a
normalizált relevancia).

**Kombinálás a cross-session pontszámmal**: a `recurrence_count` egy
KÜLÖN, kvantált tényező (egész szám: hány session adott vissza nem-nulla
normalizált relevanciát), amely a cross-session összesített pontszám MELLÉ
kerül a `promotion_candidate` rekordra (lásd "promotion_candidate Schema
Fields") — NEM egy szorzó/súlytényező a meglévő összesített pontszámon belül,
hanem egy ÖNÁLLÓ mező, amely egy KÜLÖN küszöbfeltétel forrása lehet (pl.
"a `weight_score` küszöböt csak akkor érheti el egy jelölt, ha
`recurrence_count >= 2`" — ez egy AND-kapcsolat a két feltétel között, nem
egy súlyozott összeg). Az AND-kapcsolat indoklása: egy fogalom, amely csak
EGY session-ben fordul elő (akármilyen magas normalizált relevanciával), nem
"visszatérő" — a "visszatérő fogalom" definíció szerint (`architecture.md`
"cic-mcp-shared" Igen: "visszatérő fogalmak") legalább 2 különböző
session-ben kell megjelennie, mielőtt egyáltalán jelölt-szintű mérlegelés
tárgya lehetne.

### 2. Factory job/PR/artifact linkage

**Indoklás, miért növeli a súlyt**: ha egy jelölt EGY konkrét
`cic-mcp-factory` job-id-hez/PR-hez/artifacthoz köthető, ez NÖVELI a súlyt,
mert egy factory-job-hoz kötött jelölt nagyobb eséllyel egy VALÓS, dokumentált
döntés (egy commitolt, Vault-aláírt, GitHub-on review-zett job-output), nem
véletlen lexikai egyezés a session-tartalomban. Egy lexikai/vektor-egyezés
önmagában csak azt mutatja, hogy egy SZÖVEGES minta többször előfordult — a
factory-job-linkage egy FÜGGETLEN, strukturált bizonyítékforrás (egy
git-history-ban rögzített, Vault-aláírt esemény), amely megerősíti, hogy az
egyezés egy valódi, dokumentált munkafolyamathoz kötődik, nem zajos
véletlenhez.

**Konkrét mező-azonosítás — GREP a séma-fájlon:**

```
grep -rn "^[a-z_]*:" jobs/.schema/meta.yaml | grep -v test_
```

**Teljes kimenet:**

```
jobs/.schema/meta.yaml:1:schema_version: "1.0"
jobs/.schema/meta.yaml:4:job_id: ""                  # unique, e.g. "workdir-get-diff-001"
jobs/.schema/meta.yaml:5:parent_job_id: ""           # parent job id if this is a child job; "" for root
jobs/.schema/meta.yaml:8:level: ""                   # orchestrator | capability
jobs/.schema/meta.yaml:11:capability:
jobs/.schema/meta.yaml:18:kb_focus: []                # focus_pack node-ids or tags, e.g. ["mcp", "trust-domain"]
jobs/.schema/meta.yaml:19:promptmap_ref: ""           # key in ai/PROMPTMAP.yaml; "" if not applicable
jobs/.schema/meta.yaml:22:agent:
jobs/.schema/meta.yaml:32:workplace:
jobs/.schema/meta.yaml:37:status: "pending"           # pending | running | agent_done | done | error
jobs/.schema/meta.yaml:44:error_message: ""           # only when status: error
jobs/.schema/meta.yaml:47:timestamps:
```

(A `grep -v test_` ezen a fájlon no-op — nincs `test_` prefixű mező.)

**Választott mező: `job_id`** (`jobs/.schema/meta.yaml:4`).

**Indoklás a választásra**: a `job_id` az egyetlen olyan mező a fenti
listából, amely EGYEDI, stabil azonosítóként mutat egy KONKRÉT,
visszakereshető factory-job-ra (ahonnan a git history-ban a feature branch,
a commit-ok, és — egy jövőbeli `/job-close` után — a PR is visszakövethető).
A `capability:` blokk mezői (sor 11, `id`/`target_repo`/`change_type`/
`status_after_merge`) ezzel szemben a capability-t azonosítják (mit gyárt a
job), nem a job-ESEMÉNYT magát — egy `provenance_refs[]` bejegyzésnek a
KONKRÉT job-futást kell azonosítania, nem csak a capability-kategóriát. A
`job_id` ehhez a legpontosabb hivatkozási pont.

**Bizonyíték egy MEGLÉVŐ, lezárt job `meta.yaml`-jából**
(`jobs/shared-cross-session-search-001/meta.yaml`):

```
job_id: "shared-cross-session-search-001"
```

A mező tehát NEM csak a sémában létezik, hanem tényleges, korábban kitöltött,
`status: "done"` jobokban is megjelenik — ugyanebből a fájlból idézve a
kapcsolódó `capability.id`/`capability.target_repo` mezőket is (a
"factory-linkage" faktor SZÉLESEBB hivatkozási kontextusához):

```
capability:
  id: "cic_mcp.shared.cross_session_search"
  target_repo: "cic-mcp-shared"
```

**Kombinálás a cross-session pontszámmal**: a factory-linkage egy BINÁRIS
(van/nincs) vagy LISTA-alapú (`linked_factory_job_ids[]` — lásd
"promotion_candidate Schema Fields") bónusz-tényező, amely egy FIX
ADALÉKKAL (additív bónusz, NEM szorzó) emeli a `weight_score`-t, ha a
`provenance_refs[]`-en keresztül legalább egy `job_id` (vagy a hozzá tartozó
PR-szám, ha az output egy `/job-close` után PR-ré válik) kapcsolódik a
jelölthöz. Az additív (nem szorzó) választás indoklása: egy szorzó-tényező
egy ALACSONY alap cross-session pontszámot is felnagyítana, ha a
factory-linkage megvan — ez azt a torz hatást eredményezné, hogy egy
gyengén-visszatérő (pl. 1 session-ből, de egy factory-job-hoz kötött)
fogalom magasabb végső pontszámot kapna, mint egy erősen-visszatérő (sok
session-ből, de factory-job nélküli) fogalom. Egy additív bónusz ehelyett
csak egy MÁR LÉTEZŐ, nem-nulla cross-session alapra ad rátoldást — nem
helyettesíti a recurrence-alapú bizonyítékot, csak kiegészíti.

### 3. Recency-bónusz

**Definíció**: frissebb bizonyíték magasabb súlyt kap-e, és ha igen, milyen
egyszerű (NEM ML-alapú) függvénnyel.

**Döntés**: IGEN, a frissebb bizonyíték magasabb súlyt kap, egy egyszerű
**"utolsó N nap" ablak-függvénnyel** (nem lineáris decay-jel) — egy
bizonyíték (`provenance_refs[]` bejegyzés `session_id`-jéhez tartozó
legutóbbi aktivitás, a `get_session_status` `last_seen_at` mezője alapján,
a `shared-cross-session-search-001` riport "Cross-Session Query Shape And
Ranking" 2. pontja szerint, amely már ezt a mezőt használja session-szűrésre)
egy bináris "friss" (`true`, ha `last_seen_at` az utolsó N napban van) vagy
"nem friss" (`false`) jelzőt kap, ahol N egy konfigurálható konstans (pl.
30 nap).

**Indoklás, miért elég egy egyszerű függvény**: ez a job KONTRAKTUS-szintű,
nem implementáció — a cél, hogy a FAKTOR létezése és a döntés ELVE rögzüljön,
nem a pontos numerikus formula. Egy lineáris/exponenciális decay-függvény
(pl. `bónusz = max(0, 1 - days_since/90)`) egy IMPLEMENTÁCIÓS finomítás,
amely egy jövőbeli, tényleges kódot író jobra van bízva — egy bináris
ablak-függvény (1) egyszerűbben auditálható (egy adott pillanatban egy
jelölt vagy friss, vagy nem, nincs köztes "0.73 frissességi pontszám", amit
emberi reviewer-nek meg kellene értenie egy `reviewed_shared`-re emelési
döntés előtt), (2) konzisztens a `shared-cross-session-search-001` riport
döntésével, hogy a session-rendezés is egyszerű csökkenő sorrend (nem súlyozott
decay-függvény) a `last_seen_at`/`started_at` mezőn, és (3) elkerüli, hogy a
súlyozási modell egy ÚJ, finomhangolandó hiperparamétert (a decay-görbe
alakja) vezessen be egy kontraktus-szintű riportban, amit implementáció
nélkül nem lehet érvényesen kalibrálni.

**Kombinálás a cross-session pontszámmal**: a recency-bónusz, hasonlóan a
factory-linkage-hez, egy ADDITÍV bónusz (nem szorzó), amely csak akkor
érvényesül, ha a jelölt MÁR rendelkezik nem-nulla cross-session alappal
(recurrence_count >= 1). Az additív választás indoklása megegyezik a
factory-linkage-nél leírtakkal: egy szorzó torzítaná a végeredményt egy
gyenge, de friss jelölt irányába egy erős, de régebbi jelölttel szemben,
ami nem a "visszatérő fogalom" detektálás célja.

### Összesített küszöb-logika (a 3 faktor együtt)

```
weight_score = cross_session_score (session-enkénti min-max normalizált összeg)
               + factory_linkage_bonus   (additív, fix érték, ha linked_factory_job_ids[] nem üres)
               + recency_bonus           (additív, fix érték, ha last_evidence_at az utolsó N napban van)

promotion_candidate (trust: candidate) feltétel:
  recurrence_count >= 2   AND   weight_score >= THRESHOLD
```

A `recurrence_count >= 2` egy KÜLÖN, AND-kapcsolt feltétel, NEM a
`weight_score` összegébe olvasztott tag — ez biztosítja, hogy egyetlen
session-ből, akármilyen erős factory-linkage/recency-bónusszal sem válhat egy
jelölt `promotion_candidate`-té anélkül, hogy legalább 2 különböző
session-ben bizonyítottan visszatérő lenne. A `THRESHOLD` konkrét numerikus
értéke implementációs döntés (NEM ennek a jobnak a tárgya) — itt csak a
KOMBINÁLÁSI STRUKTÚRA (additív bónuszok + külön AND-feltétel) a kontraktus.

## promotion_candidate Schema Fields

A `shared-cross-session-search-001` riportban MÁR definiált jelölt-rekordot
(`candidate_id`, `keyword_description`, `trust`, `canonical`,
`provenance_refs[]`, `conflicting_with`, `superseded_by`, `superseded_at`,
`superseded_reviewed_by` — "Conflict/Superseded Candidate Data Model"
szekció) ÚJ, súlyozás-specifikus mezőkkel bővítjük. A MÁR LÉTEZŐ mezők
EZEN a riporton nem módosulnak, nem törlődnek, nem definiálódnak újra.

| Mező | Típus | Jelentés | Melyik faktorhoz tartozik |
|---|---|---|---|
| `weight_score` | float | A cross-session normalizált-összesített pontszám + factory-linkage bónusz + recency-bónusz végeredménye | Mindhárom faktor összesítése |
| `recurrence_count` | integer | Hány KÜLÖNBÖZŐ `session_id`-ben volt nem-nulla normalizált relevancia bizonyíték ugyanarra a `keyword_description`-re | Recurrence count |
| `linked_factory_job_ids[]` | lista string (job_id formátum) | A `jobs/.schema/meta.yaml:4` `job_id` mezőre hivatkozó, a jelölthöz köthető factory-job azonosítók listája | Factory job/PR/artifact linkage |
| `last_evidence_at` | nullable timestamp | A `provenance_refs[]`-ben szereplő legfrissebb bizonyíték session-jének `last_seen_at`/`started_at` időbélyege | Recency-bónusz |
| `recency_flag` | bool | `true`, ha `last_evidence_at` az utolsó N napos ablakon belül van (N konfigurálható, implementációs döntés) | Recency-bónusz |
| `weighting_evaluated_at` | timestamp | Mikor futott le utoljára a súlyozási kiértékelés ezen a jelölten (auditálhatósághoz — mikor változott a `weight_score`) | Mindhárom faktor (audit-mező, nem maga a súly) |

**Megjegyzés a `provenance_refs[]` mezőről**: ez a mező a `shared-cross-
session-search-001` riportban MÁR definiált (`{session_id, chunk_id,
turn_id, content_hash}` szerkezetű lista) — a `linked_factory_job_ids[]`
NEM helyettesíti, NEM duplikálja ezt, hanem egy KÜLÖN listát ad a
factory-domain hivatkozásokhoz (job-id-k, NEM session-pointer-ek), mert a
factory-job és a session-provenance két STRUKTURÁLISAN különböző
hivatkozás-típus (az egyik egy git-history esemény, a másik egy
session-chunk pointer) — összevonásuk egy közös listába elmosná ezt a
megkülönböztetést egy jövőbeli implementációs/audit jobnál.

## Canonical Promotion Boundary — Human Review Required

**Explicit kimondva**: a `promotion_candidate` állapot ELÉRÉSE (akármilyen
magas `weight_score`-ral) SOHA nem jelenti automatikusan a
`cic-mcp-knowledge`-be való canonical promotiont. Ez egy TELJESEN KÜLÖN,
emberi review-flow, amit ez a job NEM specifikál részletesen (csak az
ÁLLÍTÁS szükséges, hogy létezik és kötelező).

**Normatív forrás — `architecture.md` "Factory legitimacio" szekció**
(TELJES egészében idézve):

> "Az AI/factory:
> - capability requestet olvas
> - tervet keszit
> - contractot javasol
> - kodot/schema-t ir
> - tesztet futtat
> - review summaryt ad
>
> Az ember/orchestrator:
> - review-zik
> - merge/reject/revise allapotot ad
> - legitimacios hatart kepvisel
>
> Rogzitett szabaly:
> AI gyart es validal, de nem legitimál.
> Human merge = state transition authorization."

**Normatív forrás — thead02 (`cic-mcp-factory/CLAUDE.md` "Felülvizsgált AI
párbeszédek" tábla)**:

> "thead02: cic-mcp-* família elnevezés + trust-domain rétegezés; AI
> gyártja/validálja, ember legitimálja a capability-t."

**A HATÁR — mi az UTOLSÓ shared-oldali állapot, amit egy jelölt
AUTOMATIKUSAN elérhet, és mi igényel MINDIG emberi akciót:**

| Állapot | Elérhető automatikusan (súlyozási küszöb alapján)? | Ki/mi engedélyezi |
|---|---|---|
| `trust: mixed` | IGEN | Automatikus aggregáció (több session, heterogén forrás összefűzése — lásd `shared-session-catalog-consumer-001` "Trust Mapping") |
| `trust: candidate` (`promotion_candidate`) | **IGEN** — ez az UTOLSÓ automatikusan elérhető állapot, a "Weighting Factors" szekcióban definiált `weight_score`/`recurrence_count` küszöb alapján | Automatikus súlyozási kiértékelés (ez a job tárgya) |
| `trust: reviewed_shared` | **NEM** — MINDIG emberi akciót igényel | Ember/orchestrátor (shared-szintű review, NEM knowledge-promotion) |
| `canonical: true` (`cic-mcp-knowledge`-be promóció) | **NEM** — MINDIG egy KÜLÖN, ezen a jobon kívüli, emberi review-flow | Ember/orchestrátor, egy KÜLÖN folyamatban (nem ennek a jobnak/repónak a tárgya) |

**A két emberi-akció-igényű lépés KÜLÖNBÖZIK egymástól**:

1. **`candidate` → `reviewed_shared`**: ez egy SHARED-RÉTEGEN BELÜLI review
   — egy ember/orchestrátor megnézi a jelölt bizonyítékait
   (`get_session_context_pack`/`get_session_source_refs` hívásokkal, a
   `shared-session-catalog-consumer-001` riport "Adapter Contract Table"-je
   szerint) és jóváhagyja shared-szintű FELHASZNÁLÁSRA — ez NEM jelenti,
   hogy a `cic-mcp-knowledge`-be is bekerül.
2. **`reviewed_shared` → `canonical: true`**: ez egy TELJESEN KÜLÖN,
   ezen a jobon és ezen a repón TÚLI folyamat, amit a `cic-mcp-knowledge`
   repo saját capability-jobjai (jövőbeli, itt nem definiált jobok)
   specifikálnak. A `cic-mcp-shared/CLAUDE.md` "Kapcsolódó rendszerek"
   szekciója ezt már jelzi: "cic-mcp-knowledge: canonical réteg — ide csak
   emberi review után, soha automatikusan nem promote-olunk."

**Miért nem elég egy magas `weight_score` SEMMILYEN automatikus
canonical-promotionhoz**: a `weight_score` egy SÚLYOZÁSI heurisztika
(recurrence, factory-linkage, recency) — ez egy STATISZTIKAI jelzés arra,
hogy egy fogalom valószínűleg releváns és visszatérő, de NEM egy
TARTALMI/SZEMANTIKAI állítás arról, hogy a fogalom helyes/pontos/ellentmondás-
mentes. A canonical promotion egy MINŐSÉGI állítást tesz ("ez a knowledge
réteg hivatalos, megbízható tudása") — ezt egy számszerű küszöb sosem
helyettesítheti, mert a küszöb csak a GYAKORISÁGOT/KAPCSOLTSÁGOT méri, nem a
TARTALMI HELYESSÉGET. Ez direkt konzisztens a `forbidden_shortcuts`
tilalmával ("a `weight_score` küszöb elérése ÖNMAGÁBAN `canonical: true`-t
eredményez" — ez explicit TILOS, lásd "Rejected / Out Of Scope").

## Findings

1. **A prerequisite (`shared-cross-session-search-001`) `done` státuszú**,
   az `id:` kulccsal megerősítve (lásd "Prerequisite Check") — az input.md
   ebben a jobban is a helyes (`id:`) grep-pattern-t adta meg, az eredeti
   `shared-session-catalog-consumer-001` riport által felfedett hiba itt sem
   ismétlődött meg.
2. **A `jobs/.schema/meta.yaml` GREP-pel megerősített mező-listája
   (`job_id`, `parent_job_id`, `level`, `capability:`, `kb_focus`,
   `promptmap_ref`, `agent:`, `workplace:`, `status`, `error_message`,
   `timestamps:`) nem tartalmaz explicit "PR-szám" vagy "artifact-id" mezőt**
   — a job-slices.yaml `forbidden_shortcuts`/`required_evidence` szövege
   "factory job/PR/artifact linkage"-ről beszél, de a séma jelenleg
   KIZÁRÓLAG a `job_id`-t biztosítja közvetlen, kitöltött mezőként (egy
   PR-szám csak a `/job-close` UTÁN, a GitHub PR létrehozásakor keletkezik,
   és NEM kerül vissza a `meta.yaml`-ba semmilyen mezőként — ez egy
   strukturális rés, amit a "Risks" szekció rögzít).
3. **A `linked_factory_job_ids[]` mező EGYIRÁNYÚ hivatkozás** (a
   `promotion_candidate` rekord hivatkozik a `job_id`-ra, a `meta.yaml`
   NEM hivatkozik vissza a candidate-ra) — ez konzisztens azzal, hogy a
   `meta.yaml` séma a factory-job ÉLETCIKLUSÁT írja le, nem a shared-oldali
   jelölt-rekordokat; egy fordított (job → candidate) hivatkozás bevezetése
   a `meta.yaml` sémájában jelentősen túllépné ennek a jobnak a hatókörét
   (a `meta.yaml` séma módosítása explicit NEM cél).
4. **A `shared-cross-session-search-001` riport "Findings" #2 pontja már
   jelezte**, hogy a session-oldali RRF-súlyozási formula tényleges SQL
   implementációja (`session-hybrid-search-api-migration.sql`) nem volt
   közvetlen forrás — ez a job sem olvasta el ezt a fájlt (nem volt
   kötelező forrás, és a "Sources" szekció ehhez a jobhoz nem hivatkozott
   rá), mert a `weight_score` itt definiált 3 faktora (recurrence,
   factory-linkage, recency) a cross-session pontszám TETEJÉRE épül, nem a
   session-oldali fúzió belső mechanikájára.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `shared-cross-session-search-001` prerequisite `status: "done"` | proven | `jobs/index.yaml:252-255`, `- id: "shared-cross-session-search-001"`, `status: "done"` | Fájl direkt grep + idézés (`id:` kulcs) | low |
| `job_id` mező létezik a `jobs/.schema/meta.yaml` sémában | proven | `jobs/.schema/meta.yaml:4`, `job_id: ""  # unique, e.g. "workdir-get-diff-001"` | Fájl direkt grep + idézés | low |
| `job_id` mező tényleges, korábban kitöltött jobban is megjelenik | proven | `jobs/shared-cross-session-search-001/meta.yaml`, `job_id: "shared-cross-session-search-001"` | Fájl direkt olvasás + idézés | low |
| `capability.id`/`capability.target_repo` mezők kitöltve egy lezárt jobban | proven | `jobs/shared-cross-session-search-001/meta.yaml`, `capability: id: "cic_mcp.shared.cross_session_search"`, `target_repo: "cic-mcp-shared"` | Fájl direkt olvasás + idézés | low |
| Legalább 3 súlyozási faktor definiálva (recurrence, factory-linkage, recency), mindegyik indoklással és kombinálási móddal | proven (kontraktus-szintű állítás) | "Weighting Factors" szekció, 3 alpont + "Összesített küszöb-logika" alszekció | Szöveges definíció a riportban, normatív forrásokra (`shared-cross-session-search-001` riport) hivatkozva | medium — kontraktus-szintű döntés, nincs implementáció/teszt, amely a tényleges `THRESHOLD`/bónusz-értékeket validálná |
| `promotion_candidate` schema-mezők táblája ÉPÍT a `shared-cross-session-search-001` jelölt-rekordjára, nem helyettesíti | proven | "promotion_candidate Schema Fields" szekció — a táblázat explicit NEM ismétli meg a `candidate_id`/`trust`/`canonical`/`provenance_refs[]`/`conflicting_with`/`superseded_by` mezőket, csak 6 ÚJ mezőt ad hozzá | Tábla-összevetés a két riport között | low |
| Canonical promotion KÜLÖN, emberi review-flow, az `architecture.md` "Factory legitimacio" + thead02 forrásra hivatkozva | proven | "Canonical Promotion Boundary" szekció — `architecture.md` 208-230. sor TELJES "Factory legitimacio" szekció idézve, `cic-mcp-factory/CLAUDE.md` "Felülvizsgált AI párbeszédek" thead02 sor idézve | Két fájl direkt idézése | low |
| A `weight_score` küszöb elérése ÖNMAGÁBAN NEM eredményez `canonical: true`-t | proven (kontraktus-szintű döntés, normatív forrásra alapozva) | "Canonical Promotion Boundary" → "Miért nem elég egy magas `weight_score`" alszekció, a `forbidden_shortcuts` szövegére hivatkozva | Szöveges indoklás, normatív forrás idézve | low — ez a `forbidden_shortcuts` EXPLICIT szövegéből levezetett döntés |
| A `jobs/.schema/meta.yaml` séma NEM tartalmaz explicit PR-szám/artifact-id mezőt | proven | `jobs/.schema/meta.yaml` teljes GREP-kimenete (lásd "Weighting Factors" #2 szekció és "Findings" #2) — nincs ilyen mező a kimenetben | Grep-parancs tényleges futtatása, teljes kimenet idézve, hiány explicit jelezve | medium — strukturális rés, lásd "Risks" |
| Tényleges súlyozó-algoritmus kód implementálva és tesztelve | missing | Ez a job explicit "Nem cél"-ja — nincs futtatható súlyozó-kód, nincs `shared_core.*` schema implementáció | N/A — ez a `status_after_merge: experimental` indoklása | high — ez a fő limitáció, lásd "Risks" |

## Decisions Proposed

1. **A factory-linkage faktorhoz a `job_id` mezőt (`jobs/.schema/meta.yaml:4`)
   javasoljuk elsődleges hivatkozási mezőként** a `linked_factory_job_ids[]`
   schema-mezőn keresztül — ez az egyetlen mező a sémában, amely egyedi,
   stabil módon azonosít egy konkrét factory-job-futást (szemben a
   `capability:` blokk mezőivel, amelyek a capability-kategóriát írják le,
   nem az egyedi job-eseményt).
2. **A `weight_score` kombinálási struktúrája additív bónuszok + külön
   AND-feltétel** (`recurrence_count >= 2 AND weight_score >= THRESHOLD`),
   NEM egy egységes szorzó-formula — ez egy javaslat egy jövőbeli
   implementációs jobnak, hogy a két feltételt STRUKTURÁLISAN elkülönítve
   valósítsa meg (pl. két külön validációs lépés, nem egy közös numerikus
   kifejezés), hogy egy gyenge recurrence (1 session) semmilyen
   factory-linkage/recency-bónusszal se válhasson `promotion_candidate`-té.
3. **Egy jövőbeli job-spec/séma-bővítési feladat fontolja meg egy
   explicit PR-szám/artifact-id mező bevezetését a `meta.yaml`-ba** (vagy egy
   külön, a `/job-close` által írt mezőbe) — jelenleg a `job_id` az egyetlen
   strukturált hivatkozási pont, a "PR-szám"-ra való hivatkozás
   (`job-slices.yaml` "factory job/PR/artifact linkage" szövege) jelenleg
   csak a `provenance_refs[]`-en keresztüli, kézi/review-időben rögzített
   szabad-szöveges hivatkozásként valósulhatna meg, amíg ez a mező nem létezik.
4. **A recency-bónusz egyszerű "utolsó N nap" ablak-függvényként**
   (NEM lineáris/exponenciális decay) javasolt egy jövőbeli implementációs
   jobnak — az N konkrét értéke (pl. 30 nap) implementációs döntés, ezen a
   riporton kívül esik.

## Rejected / Out Of Scope

- **Tényleges súlyozó-algoritmus kód implementálása** — explicit "Nem cél",
  a `status_after_merge: experimental` ezt indokolja.
- **A `cic-mcp-knowledge`-be való canonical promotion folyamatának RÉSZLETES
  kidolgozása** — csak az ÁLLÍTÁS szükséges (és megtörtént a "Canonical
  Promotion Boundary" szekcióban), hogy embert igényel; a folyamat maga egy
  másik, itt nem definiált job/repo tárgya.
- **A `shared-cross-session-search-001`/`shared-session-catalog-consumer-001`
  által MÁR definiált mezők (`candidate_id`, `trust`, `canonical`,
  `provenance_refs[]`, `conflicting_with`, `superseded_by`, `superseded_at`,
  `superseded_reviewed_by`) megkérdőjelezése vagy újradefiniálása** —
  explicit "Nem cél", ezekre ÉPÍTETT a riport, nem helyettesítette őket.
- **`cic-mcp-session` repo módosítása vagy klónozása** — explicit "Nem cél",
  ehhez a jobhoz nem volt szükséges, nem is történt meg.
- **A konkrét `THRESHOLD`/bónusz-numerikus-értékek meghatározása** — ez egy
  implementációs finomítás, amelyet egy jövőbeli, tényleges kódot író job
  végezne el, nem ez a kontraktus-szintű riport.
- **A `jobs/.schema/meta.yaml` módosítása egy explicit PR-szám/artifact-id
  mezővel** — ez egy javasolt KÖVETKEZŐ lépés ("Decisions Proposed" #3), de
  ennek a jobnak nem feladata a séma tényleges módosítása.

## Risks

1. **Nincs implementáció, ami a súlyozási faktorokat valódi adaton
   validálná.** Ez a fő ok, amiért `status_after_merge: experimental`, nem
   `candidate` (lásd "Target" szekció "status indoklás") — egy jövőbeli
   implementációs jobnak (a `gateway-session-adapter-contract-001` →
   `session-context-pack-v1-001` mintát követve) valós, futtatott
   bizonyítékot kellene adnia a `weight_score` számítására.
2. **A `jobs/.schema/meta.yaml` séma jelenleg NEM tartalmaz explicit
   PR-szám/artifact-id mezőt** (lásd "Findings" #2) — ez azt jelenti, hogy a
   "factory/PR/artifact linkage" faktor PR-/artifact-komponense (szemben a
   job_id-komponenssel) jelenleg csak kézi, szabad-szöveges
   `provenance_refs[]` bejegyzésként rögzíthető, nincs strukturált mező rá.
   Egy jövőbeli séma-bővítési jobnak ezt kezelnie kell, ha a PR-szintű
   linkage strukturált formában szükséges.
3. **A `THRESHOLD` konkrét numerikus értéke nincs meghatározva** — ez
   szándékos (kontraktus-szintű riport, nem implementáció), de azt
   jelenti, hogy a `promotion_candidate` átmenet tényleges, élesben futó
   kiértékelése csak egy KÉSŐBBI implementációs jobban válik
   bizonyíthatóvá/kalibrálhatóvá.
4. **A recurrence/factory-linkage/recency hármas additív kombinálása nincs
   matematikailag validálva** (pl. nincs megvizsgálva, hogy az additív
   bónuszok skálája hogyan viszonyul a cross-session normalizált alap
   pontszám [0, N] skálájához) — ez egy implementációs finomhangolási
   kérdés, amit egy jövőbeli implementációs jobnak kell kezelnie, amikor a
   tényleges numerikus értékek meghatározásra kerülnek.
5. **A `recency_flag` bináris (nem fokozatos) jellege éles határeseteket
   hozhat létre** (egy bizonyíték, amely N+1 napos, ugyanúgy "nem friss"
   minősítést kap, mint egy 2 évvel régebbi) — ez egy tudatos egyszerűsítési
   döntés (lásd "Weighting Factors" #3 indoklás), de egy jövőbeli
   implementációs jobnak érdemes lehet egy fokozatosabb (pl. több sávos)
   változatot megfontolnia, ha a bináris határeset gyakorlati problémát
   okoz.

## Definition Of Done Check

| DoD pont | Státusz | Megjegyzés |
|---|---|---|
| prerequisite (`shared-cross-session-search-001`) `id:` kulccsal megerősítve, GO/NO-GO döntés indokolva | PASS | "Prerequisite Check" szekció — `status: "done"`, GO döntés |
| legalább 3 súlyozási faktor definiálva, mindegyik indoklással és a cross-session pontszámmal való kombinálási móddal | PASS | "Weighting Factors" szekció — recurrence count, factory job/PR/artifact linkage, recency-bónusz, mindegyik indoklással + "Összesített küszöb-logika" alszekció |
| a factory job/PR/artifact linkage faktorhoz KONKRÉT `meta.yaml`/`index.yaml` mező megnevezve | PASS | `job_id` (`jobs/.schema/meta.yaml:4`), GREP-pel megerősítve + meglévő lezárt job (`shared-cross-session-search-001/meta.yaml`) idézve |
| `promotion_candidate` schema-mezők táblája kész, ÉPÍT a `shared-cross-session-search-001` jelölt-rekordjára | PASS | "promotion_candidate Schema Fields" szekció — 6 új mező, a meglévő 8 mező nem ismételve/módosítva |
| explicit kimondva: canonical promotion KÜLÖN, emberi review-flow, hivatkozva a `architecture.md` "Factory legitimacio" + thead02 forrásra | PASS | "Canonical Promotion Boundary — Human Review Required" szekció, mindkét forrás teljes idézettel |
| claim-evidence tábla kitöltve, nem üres | PASS | 9 sor, lásd fent |

## Next Jobs

1. **Egy jövőbeli implementációs job**, ami a `shared_core.*` schema-t
   (`architecture.md` "Schema szeparáció") és a tényleges súlyozó-algoritmus
   kódot megírja (`weight_score` számítás, `THRESHOLD` kalibrálás), a
   `gateway-session-adapter-contract-001` → `session-context-pack-v1-001`
   mintát követve (real subprocess + stdio handshake, valós adattal
   bizonyítva) — ez emelné a státuszt `experimental`-ról `candidate`-re.
2. **Egy séma-bővítési job**, amely a `jobs/.schema/meta.yaml`-ba egy
   explicit PR-szám/artifact-id mezőt vezet be (lásd "Risks" #2, "Decisions
   Proposed" #3) — ez teljesebbé tenné a "factory job/PR/artifact linkage"
   faktor PR-/artifact-komponensét, amely jelenleg csak a `job_id`
   komponensen keresztül strukturált.
3. **Egy jövőbeli, a `cic-mcp-shared` repóban induló capability-job**, ami a
   `reviewed_shared`-re emelés tényleges EMBERI review-workflow-ját
   specifikálja (pl. milyen MCP tool/UI-felület mutatja meg a jelölteket egy
   reviewernek, hogyan rögzíti a `superseded_reviewed_by` mezőt) — ez a job
   explicit csak az ÁLLÍTÁST tette meg, hogy ez emberi akciót igényel, a
   folyamat maga nincs specifikálva.
4. **Egy KÜLÖN, a `cic-mcp-knowledge` repo saját job-szeletei közé tartozó
   capability-job**, ami a `reviewed_shared` → `canonical: true` promóciós
   review-flow-t specifikálja — ez explicit NEM ennek a riportnak vagy a
   `cic-mcp-shared` repónak a tárgya (lásd "Canonical Promotion Boundary").
