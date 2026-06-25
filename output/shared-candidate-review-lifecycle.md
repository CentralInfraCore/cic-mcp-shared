# shared-candidate-review-lifecycle-001 Output

## Scope

A `cic-mcp-shared` repóban a `shared_core.candidates` tábla DB-szinten már kikényszerítette, hogy
`canonical = TRUE` kizárólag `trust = 'reviewed_shared'`-nél lehetséges
(`candidates_canonical_requires_reviewed_shared` CHECK constraint), és a
`shared-promotion-candidate-logic-001` job már implementálta a `mixed → candidate` automatikus
átmenetet (`decide_trust_level()`, `shared_core/aggregator.py:82-96`). Ami HIÁNYZOTT: egy
operátor által hívható eszköz, ami a `candidate → reviewed_shared` (és `→ canonical`,
`→ rejected`, `→ superseded`) átmenetet TÉNYLEGESEN végrehajtja, audit-naplóval.

Ez a job megépítette ezt az operátor-felületet:
1. `shared_audit.candidate_transitions` audit-tábla migrációként (`migrations/0001_candidate_transitions_audit.sql`)
2. `shared_core/review_lifecycle.py` négy függvénnyel: `promote_to_reviewed_shared()`,
   `promote_to_canonical()`, `reject_candidate()`, `mark_superseded()`
3. `tests/test_shared_core/test_review_lifecycle.py` — valós Postgres-szel futtatott, 8 teszttel

Nem érintett: a `mixed → candidate` gating logika (változatlan, `aggregator.py`), a
weight_score/recurrence_count formula, és bármilyen automatikus `reviewed_shared`/`canonical`
átmenet (nincs ilyen hívó pont a kódban).

## Inputs Read

- `jobs/shared-candidate-review-lifecycle-001/input.md` — job spec
- `jobs/shared-candidate-review-lifecycle-001/workspace/cic-mcp-shared/output/shared-core-storage-schema.sql`
  — `shared_core.candidates` teljes schema, a `trust`/`canonical` CHECK constraint-ek
- `jobs/shared-promotion-candidate-logic-001/output/shared-promotion-candidate-logic.md` —
  a már implementált `mixed → candidate` logika (NEM módosítva)
- `jobs/shared-promotion-candidate-logic-001/meta.yaml` — `status: "done"` ellenőrzése (boot sequence)
- `jobs/shared-core-storage-implementation-001/output/shared-core-storage-implementation.md` —
  "Canonical Constraint - Real Postgres Proof" szekció (a CHECK constraint korábbi, valós
  Postgres-bizonyítéka, mintaként a jelen job saját bizonyítékához)
- `cic-mcp-shared/CLAUDE.md` "Trust modell" szekció
- `shared_core/aggregator.py` (cic-mcp-shared klón) — `SharedStoreConfig`, DB connection minta,
  a meglévő `_insert_candidate()` tranzakció-stílus
- `tests/test_shared_core/test_aggregator.py` — teszt-fixture és valós-Postgres bizonyítási minta

## Findings

1. **Pre-change állapot megerősítve.** A `grep -rn "promote_to_reviewed_shared\|promote_to_canonical\|candidate_transitions" --include="*.py" shared_core/ | grep -v test_` parancs **0 találatot** adott
   (grep exit code 1) a módosítás előtt — a review-felület tényleg nem létezett.

2. **Nincs `migrations/` könyvtár a `cic-mcp-shared` repóban korábban** — a `shared_core.candidates`
   schema-ja eddig csak egy job `output/*.sql` fájljaként élt. Döntés: ez a job bevezeti a
   `migrations/0001_candidate_transitions_audit.sql` fájlt, a `cic-mcp-session` repóban már
   használt számozott (`000N_*.sql`) konvenciót követve (lásd `Decisions Proposed`).

3. **A `promote_to_canonical()` validációja TÉNYLEGESEN a DB UPDATE előtt fut**, Python-szinten
   (`shared_core/review_lifecycle.py:228-235`), és csak EZUTÁN issue-olja a tényleges
   `UPDATE ... SET canonical = TRUE`-t (`review_lifecycle.py:243-247`). A DB CHECK constraint
   nincs letiltva, nincs megkerülve — ezt a `test_promote_to_canonical_db_constraint_rejects_bypass`
   teszt külön, a tool teljes kihagyásával (nyers SQL UPDATE) is bizonyítja.

4. **Minden végrehajtott átmenet ugyanazon tranzakción belül írja az audit-sort**, mint a
   `shared_core.candidates` UPDATE-et (egyetlen `with psycopg.connect(...) as conn: with
   conn.cursor() as cur:` blokk, egy `conn.commit()`) — nincs külön, "best-effort" audit-írás,
   ami divergálhatna a tényleges UPDATE-től.

5. **Az elutasított kísérletek (mind tool-szintű, mind DB-szintű) szándékosan NEM kapnak
   audit-sort** — mert a tranzakció sosem éri el az `INSERT INTO shared_audit.candidate_transitions`
   hívást (a `ReviewLifecycleError` a `cur.execute(UPDATE...)` ELŐTT raise-el; a DB CHECK
   constraint hibája pedig a teljes tranzakciót rollback-eli, beleértve egy esetleges korábbi
   audit-INSERT-et is, ha lett volna). Ez bizonyítva: mindkét elutasított esetben a
   `shared_audit.candidate_transitions` sorok száma a candidate_id-ra **0**.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| Pre-change állapot: review-felület nem létezett | proven | `grep -rn "promote_to_reviewed_shared\|promote_to_canonical\|candidate_transitions" --include="*.py" shared_core/ \| grep -v test_` → 0 találat (exit 1) | grep futtatás a módosítás előtt | Nincs |
| `shared_audit.candidate_transitions` tábla migrációként létezik | proven | `migrations/0001_candidate_transitions_audit.sql`, `psql -f` futtatás kimenete: `CREATE SCHEMA` / `CREATE TABLE` / 2× `CREATE INDEX` / 4× `COMMENT`, hibátlanul, valós `postgres:16-alpine` ellen | psql futtatás (docker container `shared-review-lifecycle-test`, port 55436) | Nincs |
| `promote_to_reviewed_shared()` implementálva, `candidate`/`mixed`-ből indít | proven | `shared_core/review_lifecycle.py:165-216`; `test_full_valid_transition_path_candidate_to_canonical` és `test_full_valid_transition_path_starting_from_mixed` PASSED | pytest valós Postgres ellen | Nincs |
| Már-`reviewed_shared` eset hibát dob (nem no-op csendben) | proven | `review_lifecycle.py:182-188` (`ReviewLifecycleError`); `test_promote_to_reviewed_shared_rejects_already_reviewed_shared` PASSED | pytest | Nincs |
| `promote_to_canonical()` saját validációval ellenőrzi `trust=='reviewed_shared'`-et UPDATE előtt | proven | `review_lifecycle.py:228-235` (raise a `cur.execute(UPDATE...)`, sor 243, ELŐTT); `test_promote_to_canonical_rejected_by_tool_validation` PASSED | kód olvasás + pytest | Nincs |
| A DB CHECK constraint NINCS megkerülve, a tool nem bypassolja | proven | `test_promote_to_canonical_db_constraint_rejects_bypass` PASSED — nyers SQL UPDATE (a tool teljes kihagyásával) `psycopg.errors.CheckViolation`-t kapott: `"violates check constraint \"candidates_canonical_requires_reviewed_shared\""` | pytest, valós Postgres hibaüzenet | Nincs |
| `reject_candidate()` implementálva, audit-sort ír, trust-ot nem módosít | proven | `review_lifecycle.py:280-310`; `test_reject_candidate_writes_audit_row_without_changing_trust` PASSED | pytest | Nincs |
| `mark_superseded()` implementálva, FK oszlopokat (`superseded_by`/`superseded_at`/`superseded_reviewed_by`) írja | proven | `review_lifecycle.py:313-358`; `test_mark_superseded_writes_fk_columns_and_audit_row` PASSED | pytest | Nincs |
| Teljes érvényes átmenet-út: `candidate → reviewed_shared → canonical`, minden lépés újraolvasott állapota | proven | `test_full_valid_transition_path_candidate_to_canonical` PASSED — lásd lent "Real Postgres Proof — Valid Path" a tényleges SELECT kimenettel | pytest + külön evidence-run szkript psql SELECT-tel | Nincs |
| Érvénytelen kísérlet elutasítva — tool-szint | proven | `test_promote_to_canonical_rejected_by_tool_validation` PASSED; lásd lent a tényleges `ReviewLifecycleError` szöveg | pytest | Nincs |
| Érvénytelen kísérlet elutasítva — DB CHECK constraint szint | proven | `test_promote_to_canonical_db_constraint_rejects_bypass` PASSED; lásd lent a tényleges psql/psycopg hibaszöveg | pytest | Nincs |
| Audit-log sor mindkét VALÓS átmenetre megjelenik | proven | evidence-run: `audit row: (..., 'candidate', 'reviewed_shared', False, False, 'evidence-operator', ...)` és `(..., 'reviewed_shared', 'reviewed_shared', False, True, 'evidence-operator', ...)` — lásd lent | psql/psycopg SELECT az evidence-run után | Nincs |
| Elutasított kísérletekhez NINCS audit-sor (indokolt hiány) | proven | evidence-run: "audit row count after rejected tool attempt: 0" és "... after rejected bypass attempt: 0" | psycopg COUNT(*) az evidence-run után | Nincs |
| `meta.yaml` `status` mező nem módosítva | proven | a jelen agent munkafolyamat nem érintette a `meta.yaml`-t (csak `cic-mcp-shared` klónban dolgozott) | git diff (cic-mcp-factory klón) | Nincs |

## Real Postgres Proof — Valid Path

Test-környezet: disposable `postgres:16-alpine` container (`shared-review-lifecycle-test`,
`localhost:55436/testdb`), a `output/shared-core-storage-schema.sql` ÉS a
`migrations/0001_candidate_transitions_audit.sql` mindkettő hibátlanul betöltve.

Egy önálló evidence-run szkript (a pytest tesztektől függetlenül, közvetlen
`review_lifecycle.py` hívásokkal) a következő, tényleges kimenetet produkálta:

```
candidate_id: de9b4aa3-8a2e-4062-af17-12f34554d2b7
step1 result: TransitionResult(candidate_id='de9b4aa3-8a2e-4062-af17-12f34554d2b7',
  transition_id='6b06b920-234e-4970-9f1b-f1fb63480675', from_trust='candidate',
  to_trust='reviewed_shared', from_canonical=False, to_canonical=False,
  actor='evidence-operator', reason='evidence run: step 1')
step2 result: TransitionResult(candidate_id='de9b4aa3-8a2e-4062-af17-12f34554d2b7',
  transition_id='551a0933-ac00-4c60-9805-1775c92b06b3', from_trust='reviewed_shared',
  to_trust='reviewed_shared', from_canonical=False, to_canonical=True,
  actor='evidence-operator', reason='evidence run: step 2')
final row state: ('reviewed_shared', True)
audit row: (UUID('6b06b920-234e-4970-9f1b-f1fb63480675'), 'candidate', 'reviewed_shared',
  False, False, 'evidence-operator', 'evidence run: step 1')
audit row: (UUID('551a0933-ac00-4c60-9805-1775c92b06b3'), 'reviewed_shared', 'reviewed_shared',
  False, True, 'evidence-operator', 'evidence run: step 2')
```

A `final row state` egy ÚJ, friss `SELECT trust, canonical FROM shared_core.candidates WHERE
candidate_id = ...` lekérdezés kimenete (nem az in-process visszatérési érték) — bizonyítja,
hogy a sor tényleges DB-állapota `('reviewed_shared', True)`.

## Real Postgres Proof — Invalid Attempt (Both Layers)

Ugyanazon evidence-run szkript, egy ÚJ `trust='candidate'` sorra:

```
candidate_id (still trust=candidate): 70dcf1fa-c43a-4a29-9e08-cdae4bd6ef83
ReviewLifecycleError raised (tool validation): candidate_id=70dcf1fa-c43a-4a29-9e08-cdae4bd6ef83
  has trust='candidate', expected 'reviewed_shared' -- cannot promote_to_canonical()
  (tool-level pre-flight validation rejected this BEFORE any UPDATE was issued; the DB
  CHECK constraint candidates_canonical_requires_reviewed_shared would reject it too,
  but this check runs first)
row state after rejected tool attempt: ('candidate', False)
audit row count after rejected tool attempt: 0

=== bypass attempt (raw SQL, no tool) ===
DB CHECK constraint rejected bypass UPDATE:
new row for relation "candidates" violates check constraint "candidates_canonical_requires_reviewed_shared"
DETAIL:  Failing row contains (70dcf1fa-c43a-4a29-9e08-cdae4bd6ef83, evidence-run invalid
  attempt, candidate, t, null, null, null, null, 0, 0, {}, null, f,
  2026-06-25 06:33:44.032736+00, [], 2026-06-25 06:33:44.032736+00,
  2026-06-25 06:33:44.032736+00).
row state after rejected bypass attempt: ('candidate', False)
audit row count after rejected bypass attempt: 0
```

Két ELKÜLÖNÍTETT bizonyíték egy hibás kísérletre:
1. A `review_lifecycle.py` saját, Python-szintű validációja (`ReviewLifecycleError`) — UPDATE
   sosem futott le.
2. Egy MÁSIK próbálkozás, amely teljesen KIHAGYJA a `review_lifecycle.py` modult, és direkt
   `UPDATE shared_core.candidates SET canonical = TRUE ...`-t futtat ugyanarra a sorra — ezt a
   tényleges Postgres `CheckViolation` hibája utasítja el, bizonyítva hogy a DB constraint a
   valódi végső kikényszerítő erő, függetlenül attól, hogy a Python-kód helyesen viselkedik-e.

Mindkét esetben a `shared_audit.candidate_transitions` sorok száma a candidate_id-ra **0** —
indokolt hiány, mert a tranzakció sosem érte el az `INSERT INTO shared_audit...` hívást.

## Pytest Futtatási Bizonyíték

```
$ PYTHONPATH=. p_venv/bin/python -m pytest tests/test_shared_core/test_review_lifecycle.py -v --no-cov

tests/test_shared_core/test_review_lifecycle.py::test_full_valid_transition_path_candidate_to_canonical PASSED [ 12%]
tests/test_shared_core/test_review_lifecycle.py::test_full_valid_transition_path_starting_from_mixed PASSED [ 25%]
tests/test_shared_core/test_review_lifecycle.py::test_promote_to_canonical_rejected_by_tool_validation PASSED [ 37%]
tests/test_shared_core/test_review_lifecycle.py::test_promote_to_canonical_db_constraint_rejects_bypass PASSED [ 50%]
tests/test_shared_core/test_review_lifecycle.py::test_promote_to_reviewed_shared_rejects_already_reviewed_shared PASSED [ 62%]
tests/test_shared_core/test_review_lifecycle.py::test_reject_candidate_writes_audit_row_without_changing_trust PASSED [ 75%]
tests/test_shared_core/test_review_lifecycle.py::test_mark_superseded_writes_fk_columns_and_audit_row PASSED [ 87%]
tests/test_shared_core/test_review_lifecycle.py::test_promote_to_reviewed_shared_unknown_candidate_id_raises PASSED [100%]

8 passed in 1.70s
```

Postgres-környezet: disposable `postgres:16-alpine` docker container, `localhost:55436/testdb`,
`SESSION_STORE_PG_*` env változókkal konfigurálva (ugyanaz a `SharedStoreConfig.from_env()`
mintát követi, mint `shared_core/aggregator.py`).

## Decisions Proposed

- **`migrations/` könyvtár bevezetése a `cic-mcp-shared` repóban**, a `cic-mcp-session` repó
  számozott (`000N_*.sql`) konvenciójával — eddig a `shared_core.candidates` schema csak egy
  job `output/*.sql` fájljaként élt, ami nem skálázódik további schema-változásokhoz. Ez a job
  az első migráció (`0001_candidate_transitions_audit.sql`), amely FELTÉTELEZI, hogy a
  `shared_core.candidates` tábla már létezik (FK rá).

- **`promote_to_canonical()` no-op helyett hibát dob, ha a candidate MÁR `canonical=TRUE`** —
  ugyanaz a döntés, mint a `promote_to_reviewed_shared()`-nél a már-`reviewed_shared` esetre:
  explicit hiba, nem csendes no-op, hogy egy operátor véletlen duplikált hívása ne maradjon
  észrevétlen.

- **`reject_candidate()` NEM módosítja a `trust` mezőt** — a `shared_core.candidates` schema-ban
  nincs `'rejected'` trust-érték (a `candidates_trust_valid_values` CHECK constraint csak
  `'mixed'`, `'candidate'`, `'reviewed_shared'`-et enged), így a `'rejected'` állapot KIZÁRÓLAG
  az audit-naplóban (`to_trust='rejected'`) létezik, dokumentált döntésként — ez a review-queue
  döntését rögzíti, nem a candidates sor saját trust-állapotát írja át.

- **`mark_superseded()` a MEGLÉVŐ `superseded_by`/`superseded_at`/`superseded_reviewed_by`
  oszlopokat használja** (`shared-core-storage-schema.sql:74-80`) — ezek a schema-ban már
  léteztek, de operátor-felület nélkül; ez a job adja az első írási útjukat.

## Rejected / Out Of Scope

- A `mixed → candidate` gating logika módosítása — `shared-promotion-candidate-logic-001`,
  változatlan maradt, csak olvasott (`aggregator.py` nem módosult).
- A scoring-formula (`weight_score`/`recurrence_count`) módosítása — `shared-scoring-rework-001`
  hatóköre.
- BÁRMILYEN automatikus `reviewed_shared`/`canonical` átmenet — a négy függvény mindegyike
  explicit `actor`/`reason` paramétert KÖVETEL, nincs heurisztikus hívó pont sehol a kódban.
- `conflicting_with` konfliktus-detekció kezelése — nem ennek a jobnak a feladata (lásd a
  schema saját kommentje: "detection logic is out of scope for this job" — egy korábbi jobra
  utal, nem erre).

## Risks

- A `migrations/` könyvtár bevezetése egy ÚJ konvenció a `cic-mcp-shared` repóban — ha egy
  jövőbeli job nem ismeri fel ezt (és pl. újra `output/*.sql`-t generál séma-változáshoz),
  inkonzisztencia keletkezhet. Ajánlott: a `cic-mcp-shared/CLAUDE.md`-t egy következő jobban
  frissíteni a `migrations/` konvenció dokumentálásával.

- A `reject_candidate()` "no trust-mező-változás" döntése azt jelenti, hogy egy elvetett
  candidate row formálisan ÚJRA elérhető marad a `promote_to_reviewed_shared()` számára (nincs
  állapot-zár, ami megakadályozná egy elvetett candidate újra-promotálását). Ez szándékos (az
  audit-log a döntés rögzítője, nem egy state-machine lock), de egy jövőbeli job dönthet úgy,
  hogy ezt szigorítja (pl. egy `is_rejected` flag hozzáadása a `shared_core.candidates`-hez).

- A teszt egy disposable `postgres:16-alpine` docker container ellen futott (port 55436), NEM a
  host gépen futó, megosztott `postgres` containeren (5432, `ms_base` adatbázissal) — szándékos
  elszigetelés, hogy a teszt ne módosítson egy megosztott instance-t. A container jelenleg
  leállítva (`docker stop`), de NEM eltávolítva — egy jövőbeli `/job-close` review
  újraindíthatja (`docker start shared-review-lifecycle-test`) ellenőrzéshez.

## Definition Of Done Check

| Kritérium | Teljesül? | Megjegyzés |
|---|---|---|
| `shared_audit.candidate_transitions` tábla migrációként létrehozva | Igen | `migrations/0001_candidate_transitions_audit.sql`, valós Postgres-en betöltve |
| `promote_to_reviewed_shared()` implementálva | Igen | `shared_core/review_lifecycle.py:165-216` |
| `promote_to_canonical()` implementálva, saját validációval | Igen | `review_lifecycle.py:219-274`, sor 228-235 a pre-flight check |
| `reject_candidate()` implementálva | Igen | `review_lifecycle.py:277-310` |
| `mark_superseded()` implementálva | Igen | `review_lifecycle.py:313-358` |
| Teljes érvényes átmenet-út valós Postgres teszttel, minden lépés újraolvasott állapota | Igen | `test_full_valid_transition_path_candidate_to_canonical` PASSED + evidence-run psql SELECT |
| Érvénytelen kísérlet elutasítva — tool-szint | Igen | `test_promote_to_canonical_rejected_by_tool_validation` PASSED |
| Érvénytelen kísérlet elutasítva — DB CHECK constraint szint | Igen | `test_promote_to_canonical_db_constraint_rejects_bypass` PASSED — nyers SQL bypass, nem a tool-on keresztül |
| Audit-log sorok TÉNYLEGESEN megjelennek (érvényes eset) | Igen | evidence-run: 2 audit sor a teljes path-hoz |
| Audit-log hiánya indokolt (elutasított esetek) | Igen | evidence-run: 0 audit sor mindkét elutasított kísérletnél, indoklással |
| Claim-evidence tábla kitöltve, nem üres | Igen | 13 sor fent |
| `meta.yaml` `status` mező NEM módosítva | Igen | csak `cic-mcp-shared` klónban dolgoztam |

## Next Jobs

- `/job-close shared-candidate-review-lifecycle-001` — output review, PR nyitása
  (`cic-mcp-shared` PR a `feature/shared-candidate-review-lifecycle-001` branch alapján,
  `cic-mcp-factory` PR a `close/shared-candidate-review-lifecycle-001` branch alapján).
- Egy jövőbeli job dokumentálhatná a `migrations/` konvenciót a `cic-mcp-shared/CLAUDE.md`-ben
  (jelenleg csak ez a job vezette be, nincs még normatív leírás róla a repo saját
  dokumentációjában).
- Egy jövőbeli enhancement megfontolhatja a `reject_candidate()` "no re-promotion lock"
  kockázatának kezelését (lásd "Risks").
- A `migrations/` mechanikus alkalmazásának automatizálása (pl. egy `make migrate` target) NEM
  ennek a jobnak a hatóköre — jelenleg `psql -f migrations/000N_*.sql` manuális futtatást
  igényel, ahogy ez a job is tette.
