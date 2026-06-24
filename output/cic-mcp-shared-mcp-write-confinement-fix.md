# cic-mcp-shared-mcp-write-confinement-fix-001 Output

## Scope

Ez a job a `mcp-server/server.py` `update_companion()` és `record_decision()`
`@mcp.tool()` függvényeiben feltárt path-traversal / write-confinement
sebezhetőséget zárja a `cic-mcp-shared` repóban, ÉS a `project.yaml`
`metadata.name: base` drift-mezőjét javítja `cic-mcp-shared`-re.

A másik 3 érintett repó (`cic-mcp-session`, `cic-mcp-knowledge`,
`cic-mcp-gateway`) NEM része ennek a jobnak — párhuzamos, külön jobok futnak
rájuk ugyanezzel a logikával.

## Inputs Read

- `jobs/cic-mcp-shared-mcp-write-confinement-fix-001/input.md` (teljes spec)
- `mcp-server/server.py` — `SOURCE_DIR` (1167. sor), `update_companion()`
  (1486-1556. sor — fix előtti sorszámozás), `record_decision()`
  (1560-1638. sor — fix előtti sorszámozás), `_find_promptmaps()` (1261.
  sor), `claim_task`/`complete_task`/`fail_task` (1426-1482. sor)
- `tests/test_tools/test_mcp_server.py` — meglévő teszt-minta
  (`import server as mcp_server`, `sys.path` illesztés)
- `project.yaml` — `metadata.name: base` (3. sor)
- `project.schema.yaml` — `metadata.name` mező típusa (egyszerű `string`,
  nincs pattern-korlátozás)

## Vulnerability Reproduction (Before Fix)

Grep megerősítés:

```
$ grep -rn "def update_companion\|def record_decision" --include="*.py" mcp-server/ | grep -v test_
mcp-server/server.py:1486:def update_companion(
mcp-server/server.py:1560:def record_decision(
```

A fix ELŐTTI kód (`git stash`-elt állapotban futtatva) tényleges, futtatott
reprodukciója — `update_companion()`:

```
Victim file exists before attack: False
update_companion() return value: {'success': False, 'path': '/tmp/cic-write-confinement-poc-victim.yaml', 'message': 'file not found'}
```

(`update_companion()` `if not p.exists()` miatt csak már létező fájlra ír —
ez a valós threat-modell: a kliens egy, a futó processz által elérhető,
MÁR LÉTEZŐ fájlt céloz meg.) Megismételve egy előzőleg létező `/tmp` fájllal:

```
--- BEFORE ATTACK ---
description: "legit pre-existing file, NOT part of SOURCE_DIR"
owner: "someone else's config"

update_companion() return value: {'success': True, 'path': '/tmp/cic-write-confinement-poc-victim.yaml', 'updated_fields': ['description'], 'message': "Updated 1 field(s). Commit to trigger Vault Transit signing."}
--- AFTER ATTACK ---
description: PWNED by path traversal via update_companion()
owner: someone else's config
```

`record_decision()` (companion_path explicit, `load_kb()` mockolva, hogy a
hívás KB nélkül is lefusson):

```
--- BEFORE ATTACK ---
some_field: "legit pre-existing file #2, NOT part of SOURCE_DIR"

record_decision() return value: {'success': True, 'path': '/tmp/cic-write-confinement-poc-victim2.yaml', 'message': 'Decision recorded in agent_decisions[0]. Commit to persist.'}
--- AFTER ATTACK ---
some_field: 'legit pre-existing file #2, NOT part of SOURCE_DIR'
agent_decisions:
- node_id: n1
  decision: PWNED by path traversal via record_decision()
  timestamp: '2026-06-24T17:36:47.745304+00:00'
```

**Mindkét függvény, a fix előtt, ténylegesen ír egy SOURCE_DIR-en kívüli
fájlba — a sebezhetőség futtatott bizonyítékkal megerősítve.**

A `claim_task`/`complete_task`/`fail_task` biztonságának megerősítése
(NEM módosítva):

```
$ grep -n "def _update_task_status\|task_id" mcp-server/server.py
1394:def _update_task_status(pm_path: Path, task_id: str, new_status: str, extra: Optional[dict] = None) -> bool:
1402:        if task.get("task") == task_id:
1426:def claim_task(task_id: str, repo: str = "") -> dict:
...
```

Mindhárom függvény kizárólag `_find_promptmaps()` (env override vagy
`SOURCE_DIR.rglob("PROMPTMAP.yaml")`) által felsorolt fájlokon, `task_id`
STRING-EGYEZÉS alapján mutál — a kliens NEM ad meg fájl-elérési utat,
csak egy task-azonosítót, amit a szerver maga keres meg az ismert
PROMPTMAP fájlok között. Path-traversal vektor itt nincs, ezért a job
nem nyúl hozzájuk.

## Confinement Check Implementation

Új helper, `mcp-server/server.py:1170-1195` (a `SOURCE_DIR` definíció
közvetlen folytatásában):

```python
def _resolve_within_source_dir(file_path: str) -> Path:
    p = Path(file_path)
    if not p.is_absolute():
        p = SOURCE_DIR / file_path

    resolved = p.resolve()
    resolved_source_dir = SOURCE_DIR.resolve()

    if not resolved.is_relative_to(resolved_source_dir):
        raise ValueError(f"path escapes SOURCE_DIR: {file_path!r} resolved to {resolved}")

    return resolved
```

- a path-felépítés UGYANAZ marad, mint eddig (abszolút marad abszolút,
  relatív `SOURCE_DIR`-hez illesztve) — nincs viselkedés-változás a
  legitim esetben
- `Path.resolve()` MINDKÉT oldalon (kapott path ÉS `SOURCE_DIR`) —
  symlink és `..` szegmens feloldva, NEM string-prefix összehasonlítás
- `Path.is_relative_to()` a containment check — bypass-mentes
- explicit `ValueError`, amit a hívó elkap

Bevezetve:
- `update_companion()`, `mcp-server/server.py:1538-1541` — a path-felépítés
  helyén, `p.exists()` és `p.open()` ELŐTT
- `record_decision()`, `mcp-server/server.py:1614-1617` (explicit
  `companion_path` ág) ÉS `mcp-server/server.py:1640-1645` (egységes záró
  check, ami a `node_id`-ből levezetett ágat is lefedi — az is
  SOURCE_DIR-en kívülre mutathatna, ha a KB node `source_file`/`file_path`
  mezője abszolút, out-of-tree érték) — mindkét helyen a `p.open()` ELŐTT

Mindkét hívó oldal `ValueError`-t fog el és
`{"success": False, "message": "path escapes SOURCE_DIR, refused"}`-ot ad
vissza, ÍRÁS/OLVASÁS MEGKÍSÉRLÉSE NÉLKÜL.

## Real Test Proof — Rejection AND No-Regression

Új teszt-fájl: `tests/test_tools/test_mcp_write_confinement.py`, a meglévő
`test_mcp_server.py` mintáját követve (`sys.path` illesztés,
`import server as mcp_server`). `tmp_path`/`monkeypatch` fixture-ökkel
izolált `SOURCE_DIR`-t használ, valódi fájlrendszer-írásokkal — nincs
mockolva a path-resolution logika.

Tényleges, futtatott pytest kimenet:

```
$ p_venv/bin/python -m pytest tests/test_tools/test_mcp_write_confinement.py -v --no-cov -p no:cacheprovider

tests/test_tools/test_mcp_write_confinement.py::TestResolveWithinSourceDir::test_rejects_absolute_path_outside_source_dir PASSED [ 12%]
tests/test_tools/test_mcp_write_confinement.py::TestResolveWithinSourceDir::test_rejects_dotdot_traversal PASSED [ 25%]
tests/test_tools/test_mcp_write_confinement.py::TestResolveWithinSourceDir::test_accepts_relative_path_inside_source_dir PASSED [ 37%]
tests/test_tools/test_mcp_write_confinement.py::TestResolveWithinSourceDir::test_accepts_absolute_path_inside_source_dir PASSED [ 50%]
tests/test_tools/test_mcp_write_confinement.py::TestUpdateCompanionConfinement::test_rejects_out_of_source_dir_absolute_path PASSED [ 62%]
tests/test_tools/test_mcp_write_confinement.py::TestUpdateCompanionConfinement::test_legit_companion_update_still_works PASSED [ 75%]
tests/test_tools/test_mcp_write_confinement.py::TestRecordDecisionConfinement::test_rejects_out_of_source_dir_companion_path PASSED [ 87%]
tests/test_tools/test_mcp_write_confinement.py::TestRecordDecisionConfinement::test_legit_decision_record_still_works PASSED [100%]

============================== 8 passed in 3.70s ===============================
```

Lefedettség mindkét eset × mindkét függvény:
- `update_companion()` rejection: `test_rejects_out_of_source_dir_absolute_path` — `success: False`, célfájl tartalma bizonyítottan változatlan
- `update_companion()` no-regression: `test_legit_companion_update_still_works` — `success: True`, mezők tényleg frissültek
- `record_decision()` rejection: `test_rejects_out_of_source_dir_companion_path` — `success: False`, célfájl tartalma bizonyítottan változatlan
- `record_decision()` no-regression: `test_legit_decision_record_still_works` — `success: True`, `agent_decisions` tényleg bővült

Regressziós kontroll a meglévő test-suite-on (`test_mcp_server.py`):
11/12 teszt zöld; az 1 sikertelen (`TestSearchQuerySemantic::test_result_has_required_fields`,
`file_path` vs `file_paths` kulcsnév-eltérés) reprodukálva `git stash`-elt
(fix előtti) állapotban is FAILED — ez egy pre-existing, a write-confinement
jobtól FÜGGETLEN `search_query()` schema-eltérés, NEM ennek a jobnak a
hatóköre, NEM e job módosítása okozta.

## project.yaml Fix

```diff
 metadata:
-  name: base
+  name: cic-mcp-shared
```

Csak a `metadata.name` mező változott — `description`/`tags`/`version`/
`license`/`owner`/`validatedBy` érintetlen (`git diff project.yaml`
1 sornyi változást mutat).

## Findings

- Mindkét érintett tool (`update_companion`, `record_decision`) ÍRÁS előtt
  KÖZVETLENÜL a kliens-megadott abszolút path-ra nyitott fájlt — sem
  containment-check, sem whitelisting nem volt jelen a fix előtt.
- `record_decision()` `node_id`-ből levezetett ága (amikor nincs explicit
  `companion_path`) ELMÉLETBEN is escape-elhetne SOURCE_DIR-ből, ha a KB
  node `source_file`/`file_path` mezője abszolút, out-of-tree érték —
  ezért a záró confinement-check ezt az ágat is lefedi, nem csak az
  explicit `companion_path` ágat.
- `claim_task`/`complete_task`/`fail_task` BIZTOSAN nem érintett — nincs
  kliens-megadott fájl-path paraméterük.
- A `mcp-server/server.py` byte-azonos a 4 `cic-mcp-*` repóban — ez a
  fix MINTA, amit a többi 3 repó joboja replikál, de a tényleges
  módosítás KIZÁRÓLAG ebben a repóban történt.

## Claim-Evidence Matrix

| Claim | Status | Evidence | Verification Method | Risk |
|---|---|---|---|---|
| `update_companion()` fix előtt ténylegesen ír SOURCE_DIR-en kívüli fájlba | proven | "Vulnerability Reproduction" szekció, `/tmp` victim fájl tartalma `PWNED`-re változott | futtatott Python reprodukció, fix előtti kóddal | n/a (bizonyíték) |
| `record_decision()` fix előtt ténylegesen ír SOURCE_DIR-en kívüli fájlba | proven | "Vulnerability Reproduction" szekció, `/tmp` victim2 fájl `agent_decisions`-szel bővült | futtatott Python reprodukció, fix előtti kóddal, `load_kb()` mockolva | n/a (bizonyíték) |
| `_resolve_within_source_dir()` `Path.resolve()`+`is_relative_to()`-alapú, NEM string-prefix | proven | `mcp-server/server.py:1170-1195` forráskód | kódolvasás + `test_rejects_dotdot_traversal` (`..`-szegmens elutasítva) | low |
| `update_companion()` elutasítja a SOURCE_DIR-en kívüli path-ot, írás nélkül | proven | `test_rejects_out_of_source_dir_absolute_path` PASSED, célfájl tartalma bizonyítottan változatlan | pytest, valódi fájlrendszer | low |
| `update_companion()` legitim eset NEM regresszált | proven | `test_legit_companion_update_still_works` PASSED | pytest, valódi fájlrendszer | low |
| `record_decision()` elutasítja a SOURCE_DIR-en kívüli `companion_path`-ot, írás nélkül | proven | `test_rejects_out_of_source_dir_companion_path` PASSED | pytest, valódi fájlrendszer | low |
| `record_decision()` legitim eset NEM regresszált | proven | `test_legit_decision_record_still_works` PASSED | pytest, valódi fájlrendszer | low |
| `claim_task`/`complete_task`/`fail_task` nem érintett path-traversal által | proven | grep kimenet — kizárólag `task_id` string-match, `_find_promptmaps()` scope | grep + kódolvasás | low |
| `project.yaml` `metadata.name` javítva, más mező érintetlen | proven | `git diff project.yaml` 1 sornyi diff | git diff | low |
| Meglévő test-suite nem regresszált a fix miatt | proven | `test_mcp_server.py` 11/12 zöld, az 1 FAILED reprodukálva fix előtti állapotban is | pytest + `git stash` kontroll | low |

## Decisions Proposed

- A `record_decision()` záró confinement-check-et a `node_id`-derived ágra
  IS alkalmazni kell, nem csak az explicit `companion_path` ágra — mert az
  is escape-elhet, ha a KB node metaadata abszolút, out-of-tree
  `source_file` értéket tartalmaz. Ez egy enyhe bővítés a spec szó szerinti
  "vezesd be MINDKÉT helyre" instrukcióján túl, indoklás: a védelem
  KIZÁRÓLAG a kliens-vezérelt `companion_path` ágra korlátozása résnyitva
  hagyta volna a másik ágat egy jövőbeli, sérült/manipulált KB node esetén.

## Rejected / Out Of Scope

- `cic-mcp-session`/`cic-mcp-knowledge`/`cic-mcp-gateway` javítása — külön,
  párhuzamos jobok.
- `claim_task`/`complete_task`/`fail_task` módosítása — biztonságosnak
  bizonyult, nem kell hozzá nyúlni.
- `project.yaml` `description`/`tags`/`version`/`license`/`owner`/
  `validatedBy` módosítása — kizárólag `metadata.name` a hatókör.
- A generikus KB-szerver egyéb funkcióinak (`search_query`/`focus_pack`/
  stb.) módosítása, INCLUDING a megtalált, független `test_result_has_required_fields`
  pre-existing teszthiba — ez nem ennek a jobnak a hatóköre, jelezve van a
  "Findings"-ben, de NEM javítva.

## Risks

- A `_resolve_within_source_dir()` `Path.resolve()`-t használ, ami
  szimbolikus linkeket old fel — ha `SOURCE_DIR` maga symlink egy másik
  útra, a `.resolve()` mindkét oldalon konzisztensen ugyanazt a kanonikus
  formát adja, így ez nem probléma, de érdemes figyelni rá deploy-kor,
  ha `SOURCE_DIR` env-változó symlink-re mutat.
- A `record_decision()` `node_id`-derived ág záró check-je elvileg
  "csendben" elutasíthat egy korábban (hibásan) működő, de SOURCE_DIR-en
  kívüli node-companion mapping-et — ez SZÁNDÉKOS biztonsági szigorítás,
  nem regresszió, de ha valamelyik élő KB node ilyen mappinget tartalmaz,
  az érintett `record_decision()` hívás most elutasításra kerül (correct
  behavior, de viselkedés-változás).

## Definition Of Done Check

- [x] a sebezhetőség REPRODUKÁLVA a javítás ELŐTT, TÉNYLEGES kimenettel
- [x] `_resolve_within_source_dir()` implementálva, `mcp-server/server.py:1170-1195`
- [x] MINDKÉT érintett függvény javítva (`update_companion`:1538-1541,
      `record_decision`:1614-1617 + 1640-1645)
- [x] valós teszt: path-traversal ELUTASÍTVA ÉS legitim eset TOVÁBBRA IS
      működik, MINDKÉT függvényre, TÉNYLEGES pytest kimenettel (8/8 PASSED)
- [x] `claim_task`/`complete_task`/`fail_task` biztonsága megerősítve
      grep-pel (NEM módosítva)
- [x] `project.yaml` `metadata.name` javítva, más mező érintetlen
- [x] claim-evidence tábla kitöltve, nem üres

## Next Jobs

- `cic-mcp-session-mcp-write-confinement-fix-001`,
  `cic-mcp-knowledge-mcp-write-confinement-fix-001`,
  `cic-mcp-gateway-mcp-write-confinement-fix-001` — ugyanez a fix a másik
  3 byte-azonos `mcp-server/server.py` repóban (PÁRHUZAMOS jobok, nem ez
  a job hatóköre).
- Érdemes egy KÜLÖN, kis hatókörű jobot nyitni a `test_mcp_server.py::TestSearchQuerySemantic::test_result_has_required_fields`
  pre-existing teszthibára (`file_path` vs `file_paths` kulcsnév-eltérés a
  `search_query()` válasz schema-jában) — ezt a job NEM javította, mert
  nem tartozik a hatókörébe.
