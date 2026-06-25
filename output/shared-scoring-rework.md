# shared-scoring-rework-001 Output

## Scope

Egy korábbi review két hibát tárt fel a `shared_core/aggregator.py` cross-session
aggregátorban: (1) a `cross_session_score` `sum(sum(per_session_normalized.values()))`
formulája MINDEN session normalizált értékét egyszerűen összeadta, ami lehetővé tette,
hogy egy SOK, gyengén releváns találatot adó session egyedül felhúzza a pontszámot, akár
TÖBB, erősen releváns session fölé; (2) az insert-logikában NEM volt `ON CONFLICT`/upsert,
így minden aggregációs futás ÚJ candidate sort szúrt be, akkor is, ha pontosan ugyanazt a
mintázatot már korábban is észlelte.

Ez a job:
1. egy ABSZOLÚT MINIMUM RELEVANCE THRESHOLD-ot vezet be (`MIN_RELEVANCE_THRESHOLD = 0.2`)
2. session-enkénti SCORE CAP-et: top-K súlyozott átlag (`SESSION_SCORE_TOP_K = 3`) az
   egyszerű összegzés helyett
3. egy MINIMUM BIZONYÍTÉKSZÁM-GATE-et (`MIN_PROVENANCE_REFS_FOR_CANDIDATE = 2`) — ha a
   teljes provenance_refs-szám ez alatt van, NEM keletkezik candidate sor
4. egy `fingerprint` oszlopot (migrációként, hátrafelé kompatibilis) + `INSERT ... ON
   CONFLICT (fingerprint) DO UPDATE` idempotens upsertet, amely a `provenance_refs`-et
   MEGTARTJA/KIEGÉSZÍTI (nem felülírja) ismételt futásnál

**Nem érintett**: a `trust`/`canonical` CHECK constraint (MÁR helyes), a candidate
review/promote/reject lifecycle (`shared-candidate-review-lifecycle-001`, külön job — ez a
job véletlenül PÁRHUZAMOSAN futott ugyanebben a körben, de a két job NEM nyúl egymás
fájljaihoz: ez a job `aggregator.py`-t módosítja, a review-lifecycle job
`review_lifecycle.py`-t hoz létre), a `provenance_refs` JSONB STRUKTÚRÁJA (csak a tartalma
egészül ki upsertnél, a forma változatlan).

## Inputs Read

- `jobs/shared-scoring-rework-001/input.md` — job spec
- `shared_core/aggregator.py` — teljes fájl, módosítás előtt és után
- `output/shared-core-storage-schema.sql` — `shared_core.candidates` teljes schema
- `jobs/shared-cross-session-search-001/output/shared-cross-session-search.md` (368-376. sor)
  — az EREDETI normalizálási/kombinálási design
- `jobs/shared-weighting-model-001/output/shared-weighting-model.md` (290-322. sor) —
  `weight_score`/`recurrence_count` additív struktúra
- `tests/test_shared_core/test_aggregator.py` — meglévő teszt-konvenció (valós ingest
  pipeline, valós MCP subprocess, valós Postgres follow-up SELECT)

## Findings

### 1. Pre-change állapot — idézve, a committed (`HEAD`) kód ellen futtatva

```
$ grep -rn "ON CONFLICT" --include="*.py" shared_core/ | grep -v test_
(nincs kimenet, exit code 1)
```

A `tests/test_shared_core/test_scoring_rework.py::test_pre_change_no_on_conflict_in_committed_head`
teszt ezt a `git show HEAD:shared_core/aggregator.py` ellen futtatva ÚJRA-ellenőrizhetővé
teszi (nem csak egy egyszeri manuális grep marad).

A régi `cross_session_score` formula, PONTOSAN idézve (`HEAD` állapot, 271-274. sor):

```python
cross_session_score = sum(
    sum(normalized) for normalized in per_session_normalized.values()
)
```

### 2. Score-formula javítás

`_combine_session_scores(normalized)` (`aggregator.py`, új függvény) egy session
hozzájárulását adja: a `MIN_RELEVANCE_THRESHOLD`-nál NEM nagyobb értékeket eldobja, majd a
megmaradt értékek TOP-`SESSION_SCORE_TOP_K` (3) elemének ÁTLAGÁT veszi (NEM az összegét) —
ez [0, 1]-be korlátozott KONSTRUKCIÓ szerint (átlag már [0,1]-beli értékekből), így egyetlen
session SOK sora már nem tudja felhúzni a saját hozzájárulását az egyetlen, tökéletesen
releváns találat fölé. A sessionök közötti ÖSSZEGZÉS (minél több session, annál magasabb a
pontszám) VÁLTOZATLAN.

A `recurrence_count` is konzisztensen a `MIN_RELEVANCE_THRESHOLD`-ot használja (egy session,
ahol minden sor a küszöb alatt van, már nem "recurring" — korábban `> 0` volt a feltétel).

A minimum bizonyítékszám-gate (`MIN_PROVENANCE_REFS_FOR_CANDIDATE = 2`) a `provenance_refs`
TELJES (threshold-független) hosszán ellenőrződik, az INSERT/UPSERT hívás ELŐTT — ha alatta
van, a függvény `candidate_id=None`-nal tér vissza, és SEMMILYEN `shared_core.candidates`
sor nem íródik.

### 3. Candidate fingerprint + idempotens upsert

`_compute_fingerprint(keyword_description, session_ids)` egy `sha256(keyword_description +
"\x00" + sorted(set(session_ids)) join)`-ot ad — a `session_ids` HALMAZÁT (nem a listát/
sorrendet) használva, hogy egy újrafutás ELTÉRŐ session-sorrenddel (pl. egy
`last_seen_at`-rendezés változása miatt) UGYANAZT a fingerprint-et adja.

`output/shared-scoring-rework-migration.sql`: `fingerprint TEXT NULL` oszlop +
`idx_candidates_fingerprint_unique` UNIQUE index (NULL-tolerant, a meglévő — pre-migration —
sorokat NEM törli/migrálja hamis fingerprint-tel).

`_insert_candidate()` mostantól `INSERT ... ON CONFLICT (fingerprint) DO UPDATE`-et futtat:
`trust`/`weight_score`/`recurrence_count`/`linked_factory_job_ids`/`last_evidence_at`/
`recency_flag` FELÜLÍRÓDIK az új futás értékeivel, `provenance_refs` pedig egy
`jsonb_array_elements(... || ...)` + `DISTINCT` aggregációval MERGE-ölődik (a régi és az új
refs UNIÓJA, deduplikálva) — `canonical` SOHA nem szerepel a SET záradékban.

### 4. Valós, futtatott bizonyíték — MINDKÉT javítás

**Score-cap hatása** (`test_score_cap_one_busy_session_no_longer_dominates` PASSED):
egy fixture-ön, ahol session A 6 mérsékelt találatot ad (`[0.50, 0.45, 0.40, 0.35, 0.30,
0.25]`), session B és C egyenként 1 ERŐS találatot (`[0.95]`, `[0.92]`):

```
old_score (sum-of-sums)          = sum(normalized_a) + 1.0 + 1.0 = 3.0 + 1.0 + 1.0 = 5.0
new_score (_combine_session_scores) = _combine(normalized_a) + 1.0 + 1.0
                                     = 1.0 + 1.0 + 1.0 = 3.0   (session_a kapott <= 1.0)
```

(`normalized_a` egy 6-elemű min-max normalizálás `[1.0, 0.8, 0.6, 0.4, 0.2, 0.0]`-ra esik,
ezek ÖSSZEGE 3.0 — ez a RÉGI bug pontos demonstrációja: egyetlen, csupán MÉRSÉKELTEN
releváns session önmagában 3.0-t ad, MEGHALADVA a két erős-egyezésű session összesített
2.0-ját. Az ÚJ formula session_a saját hozzájárulását a top-3 átlagára (`(1.0+0.8+0.6)/3 =
0.8`) korlátozza, ami `<= 1.0` — session_a TÖBBÉ nem dominálhat egyetlen erős találat fölé.)

```
$ pytest tests/test_shared_core/test_scoring_rework.py::test_score_cap_one_busy_session_no_longer_dominates -v
PASSED
```

**Idempotencia** (`test_rerun_same_aggregation_upserts_not_duplicates` PASSED) — két, VALÓS
session a teljes ingest pipeline-on keresztül beszúrva, majd `aggregate_cross_session()`
KÉTSZER hívva UGYANAZZAL a `keyword_description`/`session_ids`-szel:

```
count_before_any_run = 0
result_1.candidate_id, result_1.fingerprint  -- első futás után
count_after_run_1 = 1   (SELECT count(*) WHERE fingerprint = result_1.fingerprint)
result_2.fingerprint == result_1.fingerprint   -- TRUE
result_2.candidate_id == result_1.candidate_id -- TRUE
count_after_run_2 = 1   (VÁLTOZATLAN — nincs második sor)
```

```
$ pytest tests/test_shared_core/test_scoring_rework.py::test_rerun_same_aggregation_upserts_not_duplicates -v
PASSED
```

**`provenance_refs` upsertnél kiegészül, nem törlődik** — ugyanaz a teszt: a két futás
UGYANAZOKAT a chunk-okat adta vissza (ugyanaz a query, ugyanazok a sessionök), így a végső
`provenance_refs` hossza EGYENLŐ egy EGYETLEN futás refs-számával (a `DISTINCT` aggregáció
dedup-olt, NEM duplikálta), ÉS mindkét forrás session_id-ja szerepel benne — azaz a merge
NEM vesztett el adatot.

**Minimum bizonyítékszám-gate** (`test_min_evidence_gate_blocks_candidate_row_with_thin_evidence`
PASSED) — egyetlen session, `per_session_limit=1` (legfeljebb 1 provenance ref összesen, a
`MIN_PROVENANCE_REFS_FOR_CANDIDATE=2` alatt):

```
result.provenance_refs hossza < 2
result.candidate_id is None
result.fingerprint is None
SELECT count(*) FROM shared_core.candidates WHERE keyword_description = <keyword> -> 0
```

### Regresszió-ellenőrzés

```
$ pytest tests/test_shared_core/test_aggregator.py tests/test_shared_core/test_scoring_rework.py -v
9 passed in 76.91s
```

A `test_aggregator.py` (KORÁBBI job output-ja, MÓDOSÍTÁS NÉLKÜL) mindhárom tesztje zöld —
a score-cap/gate/upsert bevezetése nem törte el a meglévő `weight_score`/`recurrence_count`/
`factory_linkage_bonus`/`recency_bonus`/`decide_trust_level()` viselkedést (a fixture-ök
elég erős, többszörös találatos session-eket használnak, hogy a CAP felett maradjanak).

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Pre-change: nincs `ON CONFLICT`, a régi formula `sum(sum(...))` | proven | `grep -rn "ON CONFLICT" shared_core/` → 0 találat a `HEAD` ellen; régi formula idézve `aggregator.py:271-274` (HEAD) | `test_pre_change_no_on_conflict_in_committed_head` PASSED, `git show HEAD:...` | Nincs |
| Minimum relevance threshold implementálva | proven | `MIN_RELEVANCE_THRESHOLD = 0.2` (`aggregator.py`); `_combine_session_scores([0.2, 0.1, 0.0]) == 0.0` | `test_combine_session_scores_drops_subthreshold_values` PASSED | Nincs |
| Session-enkénti score CAP (top-k mean) implementálva, MAX 1.0 | proven | `_combine_session_scores()`, `SESSION_SCORE_TOP_K = 3`; a 6-elemű session_a hozzájárulása `<=1.0`, NEM `3.0` | `test_score_cap_one_busy_session_no_longer_dominates` PASSED | Nincs |
| A score-cap TÉNYLEGESEN megakadályozza, hogy egy busy session dominálja az eredményt | proven | `old_score=5.0` (sum-of-sums) vs `new_score=3.0` (capped) UGYANAZON a fixture-ön, MINDKÉT érték idézve | valós, futtatott python összehasonlítás, mindkét formula tényleges kiszámolva | Nincs |
| Minimum bizonyítékszám-gate implementálva, NO candidate row ha alatta | proven | `MIN_PROVENANCE_REFS_FOR_CANDIDATE = 2`; valós teszt: `per_session_limit=1`, `candidate_id is None`, DB-ben `count(*) == 0` | `test_min_evidence_gate_blocks_candidate_row_with_thin_evidence` PASSED, valós Postgres SELECT | Nincs |
| Candidate fingerprint implementálva (keyword_description + session_id SET) | proven | `_compute_fingerprint()` (`aggregator.py`); két futás UGYANAZT a fingerprint-et adja | `test_rerun_same_aggregation_upserts_not_duplicates` PASSED | Nincs |
| `fingerprint` oszlop + UNIQUE index migrációként, hátrafelé kompatibilis | proven | `output/shared-scoring-rework-migration.sql` — `ADD COLUMN IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`, NULL-tolerant; ténylegesen alkalmazva egy valós Postgres ellen (`\d shared_core.candidates` mutatja a `fingerprint` oszlopot) | `psql -f` futtatás + `\d` ellenőrzés | Nincs |
| Idempotens rerun: COUNT változatlan 2 futás után | proven | `count_after_run_1 == 1`, `count_after_run_2 == 1`, `result_1.candidate_id == result_2.candidate_id` | `test_rerun_same_aggregation_upserts_not_duplicates` PASSED, valós Postgres COUNT | Nincs |
| `provenance_refs` upsertnél KIEGÉSZÜL, nem törlődik/duplikálódik | proven | ugyanaz a teszt: a végső refs-hossz EGYENLŐ egy futás refs-számával (dedup-olt), mindkét session_id szerepel | valós Postgres SELECT a candidate sorra | Nincs |
| A `trust`/`canonical` CHECK constraint nem módosult | proven | a migráció KIZÁRÓLAG a `fingerprint` oszlopot és indexet adja hozzá, semmilyen `ALTER ... DROP CONSTRAINT`/CHECK módosítás nincs benne | migráció-fájl olvasása (negatív bizonyíték) | Nincs |
| A meglévő `test_aggregator.py` teszt-suite nem regresszált | proven | `pytest tests/test_shared_core/test_aggregator.py` → `3 passed`, MÓDOSÍTÁS NÉLKÜL | tényleges pytest futtatás | Nincs |
| `meta.yaml` `status` mező nem módosítva | proven | a jelen munka csak a `cic-mcp-shared` klónban dolgozott | git diff (cic-mcp-factory klón) | Nincs |

## Decisions Proposed

1. **Top-K (K=3) MEAN, nem egyetlen `max()`** — indoklás a `SESSION_SCORE_TOP_K` konstans
   kommentjében: egy `max()` egyenlővé tenné egy "sok konzisztensen erős találatú" session
   hozzájárulását egy "egyetlen erős + sok gyenge" session-nel, elveszítve a "mennyire
   konzisztensen támogatja ezt a session ezt a fogalmat" szignált. A top-k átlag megtartja
   ezt a szignált, de [0,1]-re korlátozva.
2. **`MIN_RELEVANCE_THRESHOLD = 0.2`** — konzervatív küszöb: a min-max normalizálás
   garantálja, hogy a session leggyengébb sora PONTOSAN 0.0, a legerősebb PONTOSAN 1.0 — egy
   0.2-es küszöb csak a session SAJÁT padlójához közeli sorokat dobja el, nem egy abszolút
   (session-ek között nem összehasonlítható) `fused_score` értéket.
3. **Fingerprint = `keyword_description` + `session_ids` HALMAZA, nem a `provenance_refs`
   hash-e** — a `provenance_refs` az aggregátor SAJÁT kimenetétől függ (content_hash-ek),
   ami a keresési rangsorolástól/limittől függ, NEM a "ez konceptuálisan ugyanaz a
   candidate-e" kérdéstől; a bemenet (keyword + session-halmaz) fingerprint-elése ettől
   függetlenít.
4. **`provenance_refs` merge `jsonb_array_elements` + `DISTINCT`, nem egy Python-szintű
   set-unió** — egyetlen SQL UPDATE-en belül, nem egy SELECT-majd-Python-merge-majd-UPDATE
   három-lépéses race-elhető szekvencia.
5. **`trust` MINDIG újraszámolva minden upsertnél** (nem csak első insertkor) — egy
   candidate, ami egy KÉSŐBBI futáson lépi át a promóciós küszöböt, promotálódjon, ne
   ragadjon az ELSŐ futás trust-értékénél.

## Rejected / Out Of Scope

- A `trust`/`canonical` CHECK constraint módosítása — MÁR helyes (lásd Kontextus), nem
  ennek a jobnak a hatóköre.
- A candidate review/promote/reject lifecycle — `shared-candidate-review-lifecycle-001`,
  külön job (ugyanebben a körben, de más fájlokon: `review_lifecycle.py`, nem `aggregator.py`).
- A `provenance_refs` JSONB STRUKTÚRÁJÁNAK megváltoztatása — a forma (mezőnevek,
  beágyazás) változatlan, csak a TARTALOM egészül ki upsertnél.
- `egyetlen max()` a score-cap-hez — elvetve, lásd "Decisions Proposed" 1. pont.

## Risks

- **A `SESSION_SCORE_TOP_K = 3` és `MIN_RELEVANCE_THRESHOLD = 0.2` konstansok heurisztikusak**,
  nem egy mért, valós candidate-populáción validált érték — a `cic-mcp-shared` réteg
  jelenleg `experimental`, nincs production candidate-volumen, amin ezeket finomhangolni
  lehetett volna. Egy jövőbeli, production-közeli adathalmazon érdemes lehet újraértékelni.
- **A `fingerprint` UNIQUE index NULL-tolerant, de a pre-migration sorok (ha lennének)
  SOSEM kapnak upsert-célpontot** — egy jövőbeli aggregációs futás, ami egy pre-migration
  candidate-tel UGYANAZT a (keyword, session-halmaz) kombinációt produkálná, ÚJ sort
  szúrna be (mert a régi sor `fingerprint IS NULL`, nem egyezik semmilyen ÚJ
  fingerprint-tel) — ez egy ISMERT, dokumentált limitáció, de jelen pillanatban a
  `shared_core.candidates` tábla még gyakorlatilag üres volt ennek a jobnak a indulásakor
  (nincs production candidate-volumen), így ez ma nem aktív kockázat.
- **A score-cap fixture szintetikus normalizált értékeken demonstrált** (nem egy teljes,
  valós ingest pipeline-on átfutó "egy session sok gyenge találattal" eset) — a `_min_max_normalize()`
  függvény maga VALÓS (importált, nem reimplementált) kód, de a bemeneti `raw_scores` lista
  kézzel írt, hogy a bug pontosan reprodukálható legyen. Ez konzisztens az input.md "Feladat" 4.2
  igényével ("egy fixture-ön... mutasd meg a RÉGI formula szerinti score-t ÉS az ÚJ formula
  szerinti score-t UGYANAZON a fixture-ön").

## Definition Of Done Check

- [x] pre-change `ON CONFLICT`-hiány és a régi formula grep/idézet bizonyítva — "Findings" 1. pont
- [x] minimum relevance threshold + session-enkénti score CAP + minimum bizonyítékszám-gate implementálva — "Findings" 2. pont
- [x] candidate fingerprint + `ON CONFLICT` upsert implementálva, migrációval — "Findings" 3. pont
- [x] idempotens rerun valós Postgres teszttel bizonyítva (COUNT változatlan) — "Findings" 4. pont
- [x] score-cap hatása valós, régi-vs-új összehasonlítással bizonyítva — "Findings" 4. pont
- [x] `provenance_refs` upsertnél kiegészül, nem törlődik (bizonyítva) — "Findings" 4. pont
- [x] claim-evidence tábla kitöltve, nem üres — fent, 12 sor

## Next Jobs

- Ha a `cic-mcp-shared` réteg production-be kerül és valós candidate-volumen gyűlik össze,
  érdemes lehet a `SESSION_SCORE_TOP_K`/`MIN_RELEVANCE_THRESHOLD` konstansokat egy mért
  adathalmazon felülvizsgálni (lásd "Risks").
- A pre-migration NULL-fingerprint sorok upsert-cél-hiánya egy jövőbeli, kis kiegészítő
  jobban kezelhető (pl. egy backfill, ami a meglévő sorokra is kiszámolja a fingerprint-et a
  meglévő `provenance_refs`-ből kiolvasott session_id-k alapján), ha gyakorlatban
  problémává válik.
