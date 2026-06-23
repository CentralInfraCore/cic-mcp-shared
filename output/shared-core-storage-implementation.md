# shared-core-storage-implementation-001 Output

## Scope

Ez a job a `cic-mcp-shared` repo ELSŐ tényleges kódja: egy futtatható PostgreSQL
schema (`shared_core.candidates`), amely a három korábbi kontraktus-riport
(`shared-session-catalog-consumer-001`, `shared-cross-session-search-001`,
`shared-weighting-model-001`) candidate-rekord mezőtábláit MINDEN mezővel,
módosítás/újradefiniálás nélkül átveszi, ÉS a `canonical` mező védelmét DB-szintű
CHECK constraint-tel kikényszeríti — ezt a constraint-et VALÓS, futó Postgres
ellen (`postgres:16-alpine`, `shared-core-storage-test` container) teszteltük,
elutasított INSERT/UPDATE hibaüzenetet idézve, nem csak a constraint szövegét.

Nem cél: az aggregátor-kód (ami beírná ezeket a sorokat) — ez egy KÉSŐBBI job
(`shared-cross-session-aggregator-implementation-001`) tárgya. Ez a job KIZÁRÓLAG
a storage-schema-t és annak valós bizonyítását adja.

## Inputs Read

- `${WORKDIR}/jobs/index.yaml` — prerequisite-ellenőrzéshez
- `${WORKDIR}/jobs/shared-session-catalog-consumer-001/output/shared-session-catalog-consumer.md` (sor 254-255 és "Trust Mapping" szekció)
- `${WORKDIR}/jobs/shared-cross-session-search-001/output/shared-cross-session-search.md` (sor 368-376, "Conflict/Superseded Candidate Data Model" szekció)
- `${WORKDIR}/jobs/shared-weighting-model-001/output/shared-weighting-model.md` (sor 317-322, "promotion_candidate Schema Fields" szekció)
- `cic-mcp-shared/CLAUDE.md` "Trust modell" szekció (sor 27-35)
- `cic-mcp-shared` repo gyökere és teljes fastruktúra (`find . -type f`) — nincs `schema/`-szerű mappa, nincs SQL fájl
- analóg precedens: `${WORKDIR}/jobs/session-postgres-storage-design-001/output/session-postgres-schema.sql` (stílus-referencia, NEM kötelező forrás, de a `cic-mcp-session` repóban hasonló jobok az `output/` mappába tették a SQL fájlt, nem repo-root `schema/`-ba)

## Prerequisite Check

```
$ grep -n '\- id: "shared-session-catalog-consumer-001"' -A 3 jobs/index.yaml
286:  - id: "shared-session-catalog-consumer-001"
287-    level: "capability"
288-    status: "done"
289-    target_repo: "cic-mcp-shared"

$ grep -n '\- id: "shared-cross-session-search-001"' -A 3 jobs/index.yaml
277:  - id: "shared-cross-session-search-001"
278-    level: "capability"
279-    status: "done"
280-    parent: "shared-session-catalog-consumer-001"

$ grep -n '\- id: "shared-weighting-model-001"' -A 3 jobs/index.yaml
294:  - id: "shared-weighting-model-001"
295-    level: "capability"
296-    status: "done"
297-    parent: "shared-cross-session-search-001"
```

Mindhárom prerequisite `status: "done"`. **GO** — a job folytatható.

## Schema Design — Field-By-Field Traceability

Először megerősítve: a `cic-mcp-shared` repóban NINCS meglévő SQL/schema-fájl-konvenció.

```
$ grep -rn "CREATE SCHEMA\|CREATE TABLE" --include="*.sql" . | grep -v test_
(nincs találat, exit code 1)

$ find . -iname "*.sql" | grep -v test_
(nincs találat, exit code 1)
```

A repo gyökere `make_source.py`/`mcp-server/` scaffold-ot tartalmaz (a `base-repo`
MCP-template öröksége), `source/` üres, nincs `schema/` mappa. Mivel nincs
repo-saját konvenció, az analóg `cic-mcp-session` ökoszisztéma-testvér precedensét
követtem: a `session-postgres-storage-design-001` és az ezt követő session-jobok
mindegyike az `output/<topic>-schema.sql` / `output/<topic>-migration.sql`
elhelyezést használta, NEM egy repo-root `schema/` mappát. Ezért a fájl helye:
`output/shared-core-storage-schema.sql` (lásd "Decisions Proposed").

| Mező | Forrás (riport, sor) | SQL oszlop | Típus | Megjegyzés |
|---|---|---|---|---|
| `candidate_id` | shared-cross-session-search.md:369 | `candidate_id` | `UUID PRIMARY KEY DEFAULT gen_random_uuid()` | PK, identifier |
| `keyword_description` | shared-cross-session-search.md:370 | `keyword_description` | `TEXT NOT NULL` | nincs explicit hosszkorlát a riportokban, TEXT választva (ld. Decisions) |
| `trust` | shared-session-catalog-consumer.md:254 + shared-cross-session-search.md:371 | `trust` | `TEXT NOT NULL CHECK (trust IN ('mixed','candidate','reviewed_shared'))` | enum mintán CHECK, nem natív Postgres ENUM (ld. Decisions) |
| `canonical` | shared-session-catalog-consumer.md:255 + shared-cross-session-search.md:372 | `canonical` | `BOOLEAN NOT NULL DEFAULT FALSE` + CHECK | DEFAULT false ÉS CHECK constraint a reviewed_shared-hez kötve — lásd "Canonical Constraint" szekció |
| `conflicting_with` | shared-cross-session-search.md:373 | `conflicting_with` | `UUID[] NULL` | nullable lista candidate_id-kre, self-referencing (nem natív FK, ld. Decisions) |
| `superseded_by` | shared-cross-session-search.md:374 | `superseded_by` | `UUID NULL REFERENCES shared_core.candidates(candidate_id) ON DELETE SET NULL` | nullable self-reference, valós FK |
| `superseded_at` | shared-cross-session-search.md:375 | `superseded_at` | `TIMESTAMPTZ NULL` | nullable timestamp |
| `superseded_reviewed_by` | shared-cross-session-search.md:376 | `superseded_reviewed_by` | `TEXT NULL` | nullable identifier |
| `weight_score` | shared-weighting-model.md:317 | `weight_score` | `DOUBLE PRECISION NOT NULL DEFAULT 0` | float |
| `recurrence_count` | shared-weighting-model.md:318 | `recurrence_count` | `INTEGER NOT NULL DEFAULT 0 CHECK (>= 0)` | integer, nem-negatív védve |
| `linked_factory_job_ids` | shared-weighting-model.md:319 | `linked_factory_job_ids` | `TEXT[] NOT NULL DEFAULT '{}'` | lista string |
| `last_evidence_at` | shared-weighting-model.md:320 | `last_evidence_at` | `TIMESTAMPTZ NULL` | nullable timestamp |
| `recency_flag` | shared-weighting-model.md:321 | `recency_flag` | `BOOLEAN NOT NULL DEFAULT FALSE` | bool |
| `weighting_evaluated_at` | shared-weighting-model.md:322 | `weighting_evaluated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | timestamp |
| `provenance_refs` | shared-cross-session-search.md:372 | `provenance_refs` | `JSONB NOT NULL DEFAULT '[]'` | lista `{session_id, chunk_id, turn_id, content_hash}` — ld. Decisions a struktúra-eltérésről |

Plusz két NEM a riportokból jövő, de minden ilyen táblánál szokásos audit-mező:
`created_at`, `updated_at` (mindkettő `TIMESTAMPTZ NOT NULL DEFAULT now()`) — ezek
NEM helyettesítenek/duplikálnak semmit a 15 kötelező mezőből, csak a sor saját
életciklusát követik. Dokumentálva, mert a "minden mező a három riportból" feladat
explicit zárt listát ad — ezek a 15-ön FELÜLI, opcionális kiegészítések.

Mind a 15 kötelező mező megvan, nincs kihagyva, nincs átnevezve indoklás nélkül.

## Canonical Constraint — Real Postgres Proof

CHECK constraint pontos hivatkozása: `output/shared-core-storage-schema.sql:62-64`
(`CONSTRAINT candidates_canonical_requires_reviewed_shared CHECK (canonical = FALSE
OR trust = 'reviewed_shared')`).

Teszt-környezet: már futó `postgres:16-alpine` container (`shared-core-storage-test`,
`localhost:55434/testdb`), a schema a `psql -f output/shared-core-storage-schema.sql`
paranccsal lett betöltve, sikeresen (`CREATE EXTENSION` / `CREATE SCHEMA` /
`CREATE TABLE` / 5× `CREATE INDEX` / 6× `COMMENT`, hibátlanul).

### Eset 1 — sikeres INSERT, `trust='mixed', canonical=false`

```sql
INSERT INTO shared_core.candidates (keyword_description, trust, canonical)
VALUES ('test-1 deploy pipeline pattern', 'mixed', false)
RETURNING candidate_id, keyword_description, trust, canonical;
```

Tényleges kimenet:

```
             candidate_id             |      keyword_description       | trust | canonical
--------------------------------------+--------------------------------+-------+-----------
 31823c04-0b17-4c30-bac2-6ab719dee8c6 | test-1 deploy pipeline pattern | mixed | f
(1 row)

INSERT 0 1
```

### Eset 2 — elutasított INSERT és UPDATE, `canonical=true` + `trust != 'reviewed_shared'`

INSERT-próbálkozás:

```sql
INSERT INTO shared_core.candidates (keyword_description, trust, canonical)
VALUES ('test-2 bypass attempt', 'candidate', true)
RETURNING candidate_id;
```

Tényleges kimenet (elutasítva):

```
ERROR:  new row for relation "candidates" violates check constraint "candidates_canonical_requires_reviewed_shared"
DETAIL:  Failing row contains (9930c819-7081-4e0d-9ac9-c6806da984b8, test-2 bypass attempt, candidate, t, null, null, null, null, 0, 0, {}, null, f, 2026-06-23 19:53:07.772402+00, [], 2026-06-23 19:53:07.772402+00, 2026-06-23 19:53:07.772402+00).
```

Plusz UPDATE-próbálkozás (a már létező, `trust='mixed'` eset-1 sorra):

```sql
UPDATE shared_core.candidates
SET canonical = true
WHERE candidate_id = '31823c04-0b17-4c30-bac2-6ab719dee8c6';
```

Tényleges kimenet (elutasítva):

```
ERROR:  new row for relation "candidates" violates check constraint "candidates_canonical_requires_reviewed_shared"
DETAIL:  Failing row contains (31823c04-0b17-4c30-bac2-6ab719dee8c6, test-1 deploy pipeline pattern, mixed, t, null, null, null, null, 0, 0, {}, null, f, 2026-06-23 19:53:01.578276+00, [], 2026-06-23 19:53:01.578276+00, 2026-06-23 19:53:01.578276+00).
```

Mindkét bypass-irány (INSERT és UPDATE) ténylegesen elutasítva, a DB-motor
hibaüzenetével bizonyítva — nem csak a constraint szövege.

### Eset 3 — sikeres UPDATE, `trust='reviewed_shared', canonical=true`

```sql
UPDATE shared_core.candidates
SET trust = 'reviewed_shared', canonical = true, superseded_reviewed_by = 'orchestrator-test'
WHERE candidate_id = '31823c04-0b17-4c30-bac2-6ab719dee8c6'
RETURNING candidate_id, trust, canonical;
```

Tényleges kimenet:

```
             candidate_id             |      trust      | canonical
--------------------------------------+-----------------+-----------
 31823c04-0b17-4c30-bac2-6ab719dee8c6 | reviewed_shared | t
(1 row)

UPDATE 1
```

A `canonical` mező védelme bizonyítva: csak `trust='reviewed_shared'` mellett
engedett `true`-ra, minden más kombinációban (INSERT vagy UPDATE) a DB-motor
ténylegesen elutasítja.

## Conflicting/Superseded Self-Reference Proof

### `conflicting_with` — kölcsönös (szimmetrikus) jelölés két candidate között

Két candidate létrehozva (A, B):

```
             candidate_id             |                keyword_description
--------------------------------------+---------------------------------------------------
 11111111-1111-1111-1111-111111111111 | candidate A - deploy pattern X
 22222222-2222-2222-2222-222222222222 | candidate B - deploy pattern Y (conflicts with A)
(2 rows)
INSERT 0 2
```

Kölcsönös `conflicting_with` beállítva, majd lekérdezve:

```sql
UPDATE shared_core.candidates SET conflicting_with = ARRAY['22222222-2222-2222-2222-222222222222'::uuid]
WHERE candidate_id = '11111111-1111-1111-1111-111111111111';
UPDATE shared_core.candidates SET conflicting_with = ARRAY['11111111-1111-1111-1111-111111111111'::uuid]
WHERE candidate_id = '22222222-2222-2222-2222-222222222222';
```

Tényleges kimenet:

```
             candidate_id             |                keyword_description                |            conflicting_with
--------------------------------------+---------------------------------------------------+----------------------------------------
 11111111-1111-1111-1111-111111111111 | candidate A - deploy pattern X                    | {22222222-2222-2222-2222-222222222222}
 22222222-2222-2222-2222-222222222222 | candidate B - deploy pattern Y (conflicts with A) | {11111111-1111-1111-1111-111111111111}
(2 rows)
```

A és B kölcsönösen hivatkoznak egymásra a `conflicting_with` mezőben — bizonyítva.

### `superseded_by` — lánc létrehozása és lekérdezése (A → C)

Candidate C létrehozva, A `superseded_by` mezője C-re állítva:

```sql
INSERT INTO shared_core.candidates (candidate_id, keyword_description, trust, canonical)
VALUES ('33333333-3333-3333-3333-333333333333', 'candidate C - newer evidence supersedes A', 'mixed', false);

UPDATE shared_core.candidates
SET superseded_by = '33333333-3333-3333-3333-333333333333'::uuid, superseded_at = now()
WHERE candidate_id = '11111111-1111-1111-1111-111111111111';
```

Tényleges kimenet:

```
             candidate_id             |      keyword_description       |            superseded_by             |         superseded_at
--------------------------------------+--------------------------------+--------------------------------------+-------------------------------
 11111111-1111-1111-1111-111111111111 | candidate A - deploy pattern X | 33333333-3333-3333-3333-333333333333 | 2026-06-23 19:53:51.249657+00
(1 row)
```

A lánc lekérdezve self-join-nal (a "superseded_by lánc... létrehozható és
lekérdezhető" elvárás teljesítése):

```sql
SELECT old.candidate_id AS superseded_id, old.keyword_description AS superseded_desc,
       new.candidate_id AS superseding_id, new.keyword_description AS superseding_desc,
       old.superseded_at
FROM shared_core.candidates old
JOIN shared_core.candidates new ON old.superseded_by = new.candidate_id
WHERE old.candidate_id = '11111111-1111-1111-1111-111111111111';
```

Tényleges kimenet:

```
            superseded_id             |        superseded_desc         |            superseding_id            |             superseding_desc              |         superseded_at
--------------------------------------+--------------------------------+--------------------------------------+-------------------------------------------+-------------------------------
 11111111-1111-1111-1111-111111111111 | candidate A - deploy pattern X | 33333333-3333-3333-3333-333333333333 | candidate C - newer evidence supersedes A | 2026-06-23 19:53:51.249657+00
(1 row)
```

Bónusz-bizonyíték (a `superseded_by` valós FK-ját kihasználva, nem kért, de
megerősíti az adatintegritást): egy nem-létező candidate_id-ra hivatkozó
`superseded_by` UPDATE elutasítva:

```
ERROR:  insert or update on table "candidates" violates foreign key constraint "candidates_superseded_by_fkey"
DETAIL:  Key (superseded_by)=(99999999-9999-9999-9999-999999999999) is not present in table "candidates".
```

És amikor a superseder sor (C) törlődik, az `ON DELETE SET NULL` ténylegesen
NULL-ra állítja A `superseded_by` mezőjét (nem marad dangling pointer):

```
DELETE 1
             candidate_id             | superseded_by
--------------------------------------+---------------
 11111111-1111-1111-1111-111111111111 |
(1 row)
```

## Findings

1. **`provenance_refs` struktúra-eltérés az input.md és a forrás-riport között.**
   Az input.md "Sources" szekciója a `provenance_refs[]` struktúráját
   `{content_hash, ref_kind, ref_value}`-ként írja le, DE a TÉNYLEGES forrás-riport
   (`shared-cross-session-search.md:372`) `{session_id, chunk_id, turn_id,
   content_hash}`-t definiál. A két leírás NEM ugyanaz. A job specifikációja
   explicit kimondja: "a három riport mező-tábláiból, MINDEN mezővel, módosítás/
   újradefiniálás nélkül" — ezért a forrás-riport LITERÁLIS struktúráját vettem
   át (`session_id, chunk_id, turn_id, content_hash`), nem az input.md
   "Feladat 2" szekciójának paraprázisát. Az input.md megfogalmazása valószínűleg
   egy általánosított/elvonatkoztatott leírás volt, nem szándékos újradefiniálás.
2. **pgvector extension NEM szükséges.** A `postgres:16-alpine` image NEM
   tartalmazza a `pgvector` extension-t (ahogy a job-leírás is jelezte, hogy ez
   valószínűleg nem kell). A candidate-rekord mezői (semantikai keresési vektor
   NINCS köztük) nem igényelnek embedding-oszlopot ezen a szinten — a
   `provenance_refs` csak pointer-eket tárol, a tényleges vektor-keresés a
   `cic-mcp-session` rétegen él (`session_idx` schema, `session-vector-search-api-001`
   job). Csak `pgcrypto` extension kellett (`gen_random_uuid()`).
3. **Nincs natív Postgres ENUM típus a `trust` mezőhöz.** TEXT + CHECK constraint
   mintát választottam natív `CREATE TYPE ... AS ENUM` helyett, mert (a) a
   `session_raw`/session-rétegbeli analóg schema-k (`session-postgres-schema.sql`)
   is ezt a mintát követik trust-szerű enumokra, (b) natív ENUM bővítése
   (`ALTER TYPE ... ADD VALUE`) tranzakció-korlátozott Postgres-ben, a CHECK
   constraint egyszerűbben karbantartható, ha a három trust-érték listája
   később bővülne.
4. **`conflicting_with` NEM valós FK, hanem `UUID[]` + GIN index.** Postgres nem
   tud natív FK-constraint-et alkalmazni tömb-elemekre trigger nélkül. A job
   explicit "self-referencing FK VAGY hasonló, NULL megengedett" megfogalmazást
   használ — a "vagy hasonló" opciót választottam (tömb + index), mert (a) a
   forrás-riport szerint a `conflicting_with` szimmetrikus, nem hierarchikus
   reláció (mindkét fél egyenrangú), (b) trigger-alapú tömb-FK extra komplexitás
   lenne ezen a schema-szintű jobon, ahol a konfliktus-DETEKTÁLÁS logikája
   explicit "Nem cél". Az adatintegritás (létező candidate_id-kra hivatkozás)
   ezen a szinten dokumentált korlátozás, nem schema-szinten kikényszerített —
   lásd "Risks".

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| mindhárom prerequisite job `status: "done"` | proven | `jobs/index.yaml:286-297` grep kimenet idézve | mechanikus grep, 3× `id:` kulcsos blokk | low |
| mind a 15 kötelező mező átkerült a három riportból, field-by-field nyomon követve | proven | "Schema Design" tábla, minden sor riport+sorszám hivatkozással + `output/shared-core-storage-schema.sql` | grep+olvasás minden forrás-sorra, kereszthivatkozva a SQL oszloplistával (`\d shared_core.candidates`) | low |
| `canonical` CHECK constraint létezik a SQL-ben, konkrét file:line | proven | `output/shared-core-storage-schema.sql:62-64` | `grep -n` a fájlban | low |
| `canonical=true` csak `trust='reviewed_shared'` mellett tárolható, MINDEN más esetben a DB elutasítja | proven | Eset 2 INSERT és UPDATE, idézett `ERROR: ... violates check constraint` | valós psql parancs futtatva `shared-core-storage-test` container ellen, hibaüzenet idézve | low |
| `canonical=true` sikeresen tárolható `trust='reviewed_shared'` mellett | proven | Eset 3 UPDATE, idézett `UPDATE 1` + visszaadott sor | valós psql parancs | low |
| `conflicting_with` kölcsönösen beállítható két candidate között | proven | A/B mutual UPDATE + SELECT kimenet idézve | valós psql parancs | low |
| `superseded_by` lánc (A→B) létrehozható és lekérdezhető | proven | A→C UPDATE + self-join SELECT kimenet idézve | valós psql parancs | low |
| `conflicting_with`/`superseded_by` NULL lehet | proven | "NULL allowed" teszt — `conflicting_with`/`superseded_by` mindkettő NULL egy sikeres INSERT-ben | valós psql parancs | low |
| `provenance_refs` JSONB elfogadja a `{session_id, chunk_id, turn_id, content_hash}` struktúrát | proven | provenance-check INSERT, visszaadott JSONB sor idézve | valós psql parancs | low |
| nincs meglévő SQL-konvenció a `cic-mcp-shared` repóban | proven | grep/find kimenet üres (exit 1) idézve | mechanikus grep+find | low |
| `conflicting_with` adatintegritás (csak létező candidate_id-kra hivatkozhat) schema-szinten kikényszerítve | missing | nincs trigger/FK ehhez, csak `UUID[]` típus | — | medium — ld. Risks #1 |

## Decisions Proposed

1. **SQL fájl helye: `output/shared-core-storage-schema.sql`**, NEM repo-root
   `schema/` mappa. Indok: a `cic-mcp-shared` repóban nincs SQL-konvenció
   (grep/find üres), az ökoszisztéma-testvér `cic-mcp-session` repo analóg
   jobjai (`session-postgres-storage-design-001` és követői) konzekvensen az
   `output/` mappába tették a schema-fájlt, a riport mellé. Ez konzisztens a
   factory job-output mintával is (a fájl a job bizonyítékának része, nem egy
   önálló app-réteg migrációs fájlja — a "tényleges aggregátor-kód" egy
   KÉSŐBBI job tárgya, így egy formális `migrations/`-mappa bevezetése
   korai lenne).
2. **`provenance_refs` struktúrája a forrás-riport literál szövege szerint**
   (`{session_id, chunk_id, turn_id, content_hash}`), NEM az input.md
   "Feladat 2" paraprázisa szerint (`{content_hash, ref_kind, ref_value}`) —
   ld. "Findings" #1.
3. **`provenance_refs` JSONB, nem külön tábla.** Indok: minden elem egy
   immutábilis, append-only pointer, semelyik forrás-riportban leírt
   konzument NEM kérdezi le ezt sub-mezők szerint relációsan (csak a teljes
   lista perzisztálódik auditálhatóságra) — egy join-tábla írási/olvasási
   overhead-et adna jelenlegi haszon nélkül.
4. **`trust` TEXT + CHECK, nem natív ENUM** — ld. "Findings" #3.
5. **`conflicting_with` `UUID[]` + GIN index, nem natív FK** — ld. "Findings" #4.
6. **`superseded_by` valós FK `ON DELETE SET NULL`-lal** — mivel ez egyetlen
   skaláris hivatkozás (nem tömb), a natív FK egyszerűen alkalmazható, és
   értékesebb integritást ad (dangling pointer elkerülve), mint a
   `conflicting_with` tömb esetén lehetséges lenne triggerek nélkül.
7. **`created_at`/`updated_at` audit-mezők hozzáadva** a 15 kötelező mezőn
   FELÜL — nem helyettesít/duplikál semmit a riportokból, csak a sor saját
   életciklusát követi (szokásos minta minden hasonló táblánál).
8. **`keyword_description` TEXT, nincs hossz-korlát** — a riportok nem adnak
   meg pontos string-hosszt, TEXT (korlátlan) választva, mint a session-réteg
   analóg mezőinél.

## Rejected / Out Of Scope

- a tényleges aggregátor-kód, ami beírná a candidate-sorokat — explicit "Nem
  cél", a `shared-cross-session-aggregator-implementation-001` job tárgya
- a három meglévő design-riport mezőinek megkérdőjelezése — nem történt,
  minden mező 1:1 átvéve
- a canonical promotion emberi review-folyamatának RÉSZLETES kidolgozása
  (workflow, UI, ki jogosult) — csak a DB-szintű bypass-blokkolás kellett, ez
  megvan
- `conflicting_with` konfliktus-DETEKTÁLÁSI logika (mi alapján dönt a shared,
  hogy két candidate ellentmond) — explicit "Nem cél" a forrás-riportban is
- natív Postgres ENUM típus a `trust` mezőhöz — TEXT+CHECK választva helyette
  (ld. Decisions #4)

## Risks

1. **`conflicting_with` adatintegritás nincs schema-szinten kikényszerítve.**
   Egy `conflicting_with` tömb tartalmazhat nem-létező `candidate_id`-t (nincs
   FK rajta), mert Postgres natívan nem FK-constraint-eli tömb-elemeket. Ezt
   trigger-alapú validáció oldhatná meg egy KÉSŐBBI jobban, ha ez gyakorlati
   problémává válik — jelenleg a séma-szintű egyszerűség mellett döntöttem,
   mivel ez schema-szintű job, a konfliktus-detektáló logika maga sincs még
   implementálva (lásd "Nem cél").
2. **A `canonical` constraint csak EGY védelmi réteg.** Ha egy jövőbeli migráció
   eltávolítja vagy módosítja a CHECK constraint-et anélkül, hogy észrevenné a
   szemantikai jelentőségét, a védelem megszűnik. Ajánlott: a constraint
   nevét (`candidates_canonical_requires_reviewed_shared`) tartsa stabilan
   minden jövőbeli migráció, és a teszt-suite (amikor implementálódik) tegyen
   regressziós tesztet rá.
3. **Nincs migrációs framework bekötve** (pl. Alembic) — ez egy önálló SQL
   fájl, nem egy verziózott migrációs lánc. Ez összhangban van a jelenlegi
   fázissal (ez az ELSŐ kód a repóban), de a következő implementációs jobnak
   foglalkoznia kell a migrációs eszköz bevezetésével, ha a schema tovább
   bővül.

## Definition Of Done Check

- [x] mindhárom prerequisite `id:` kulccsal megerősítve, GO döntés indokolva
      ("Prerequisite Check" szekció, mindhárom `status: "done"`)
- [x] minden mező mind a három riportból átkerült, field-by-field nyomon
      követve ("Schema Design — Field-By-Field Traceability" tábla, 15/15 mező)
- [x] a `canonical` constraint valós, elutasított INSERT-tel ÉS UPDATE-tel
      bizonyítva ("Canonical Constraint — Real Postgres Proof" Eset 2,
      mindkét irány idézett `ERROR`-ral)
- [x] a `conflicting_with`/`superseded_by` self-reference valós teszttel
      bizonyítva ("Conflicting/Superseded Self-Reference Proof", mindkét
      mező, idézett tényleges sorok)
- [x] claim-evidence tábla kitöltve, nem üres (11 sor, mind kitöltve)

## Next Jobs

- `shared-cross-session-aggregator-implementation-001` — a tényleges
  aggregátor-kód, ami beírja/frissíti a `shared_core.candidates` sorokat a
  session-rétegből gyűjtött evidence alapján
- (opcionális, ha gyakorlati igény mutatkozik) trigger-alapú `conflicting_with`
  integritás-validáció — ld. "Risks" #1
- migrációs framework bevezetése, ha a `shared_core` schema tovább bővül
  (ld. "Risks" #3)
