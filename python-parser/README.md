# L5X source-analysis application

The `plc_workbench` package reads a captured L5X and builds traceable source
evidence, engineering candidates and an offline HTML report. It supports rung
and branch structure, I/O, scoped references, PID evidence, calculations,
conditions, sequences, communication and cross-rung groups. Source facts,
inferred candidates and unresolved questions remain distinguishable.

Phase 1's fourteen analysis cycles, cleanup confirmation and C16 embedded-guide
refresh are validated. The current editor imports those saved results without
another parser run and saves categories, groups, rules and engineering
properties in a private SQLite project. The established `bash ./run-work-check.sh`
now checks and analyzes the source, loads the completed run into that project
and opens the editor. `bash ./open-workbench.sh` only reopens saved work without
another analysis. PCSD and FHX are later phases. Use the
[project README](../README.md) for the normal user workflow and the
[tracker](../public/docs/planning/PRE_TEAM_REVIEW_TRACKER.md) for current status.

The header and **Project tools** show the selected analysis run's saved date/time
in your computer's time zone. **Choose analysis run** lists dates and identifies
the current run. A newer saved run is flagged when you return to the window or
open Project tools; it is loaded only when you choose it. If work-check finishes
while an older workspace still occupies the port, choose that completed run in
the existing window. You do not need to analyze the L5X again. After updating
the application code, use **Stop workspace**, then `bash ./open-workbench.sh` so
the server also uses the new code.

The editor has adjustable equation text (75% by default), a resizable rung/source
split, and optional offline English views of French/mixed comments and descriptions.
Run `bash ./setup-translation.sh` once, then choose **English** or **Both languages**
under **Source language** in the editor. To finish translation before browsing,
close the editor, run `bash ./prepare-english.sh`, then `bash ./open-workbench.sh`.
The command also saves a private English report; no parser rerun is needed.
The model and exact-text translation cache
stay under `confidential/`; unchanged wording is reused across analyses. See the
[workspace guide](../public/docs/reviews/ENGINEERING_WORKSPACE.md#reading-layout-and-english-wording)
for setup, cache/backup behavior and translation limits.

## Run from the repository root

Python 3.12+ and `uv` are required. Commands use `uv.lock`:

```bash
uv run --project python-parser --locked plc --help
uv run --project python-parser --locked plc inspect --help
uv run --project python-parser --locked plc review --help
```

To create an invented report locally:

```bash
uv run --project python-parser --locked plc review \
  public/fixtures/synthetic/control_interpretation_demo.L5X \
  --workspace confidential/workspaces/synthetic-review
```

Open the printed `review.html` path. Exit status 3 means a usable report with
explicit partial coverage, not a failed save. The command creates a fresh run;
it does not overwrite earlier reports. For the work-PC check with automatic
local feedback commit, use [the normal script](../public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md).

The standalone report is read-only. Import its completed run into the workspace
for saved classifications, groups, properties and review status. Its former
text-feedback template is superseded by the workspace controls.

Add `--debug` to `plc review` to include developer versions and rule diagnostics
in the HTML. Normal HTML keeps the engineering evidence and uncertainty while
omitting that generated implementation metadata. Canonical evidence JSON and
manifests retain their existing contents in both modes. The work-PC equivalent
is `bash ./run-work-check.sh --debug`.

## Command map

| Command | Output |
|---|---|
| `review` | Complete private offline HTML review and evidence artifacts; requires `--workspace`. |
| `inspect` | Source inventory and optional exact snapshot-bound rung selection. |
| `references` | Scoped tag/alias root bindings. |
| `sfc-structure` | Captured SFC structure and gaps. |
| `summarize` | Validated bounded source counts. |
| `reference-summary` | Validated bounded reference counts. |
| `sfc-summary` | Validated bounded SFC counts. |

Use each command's `--help` for current options. Private commands can contain
names, raw logic and values; save them beneath `confidential/` in this checkout.
Snapshot-bound IDs identify exact captured source occurrences and may change
with a new export. Complete runs have a final `manifest.json` with artifact
hashes. Retain the whole run directory when backing up or reviewing.

| Exit | Meaning |
|---|---|
| 0 | Report completed within the command's scope. |
| 1 | Read, validation, selection or save failed. |
| 2 | Invalid command-line arguments. |
| 3 | Usable report with explicit partial coverage. |

## Code and tests

| Location | Responsibility |
|---|---|
| [src/plc_workbench/](src/plc_workbench/README.md) | Current application and module map. |
| `src/plc_workbench/ladder/` | Ladder syntax reader. |
| `src/plc_workbench/contracts/` | Shared versioned work-report envelope/serialization policy. |
| `src/plc_workbench/review_assets/` | Offline report JavaScript and CSS. |
| `tests/` | Synthetic unit, workflow, contract and optional browser/DOM checks. |
| `main.py` | Retained original prototype; the installed `plc` command uses the package. |
| `pyproject.toml`, `uv.lock` | Package entrypoint and locked dependencies. |

The [development guide](../public/docs/DEVELOPMENT_GUIDE.md) gives test commands,
versioning rules and change boundaries. The work-PC runner uses the explicit
allowlists in `work_check_tests.py`; new test modules require deliberate review.
Development-only Git/process/UI tests stay outside that work-PC selection.

The [full pre-cleanup application reference](../public/docs/history/2026-10-19-pre-cleanup/files/python-parser/README.md)
preserves detailed historical CLI examples, per-layer contracts and validation
notes. Read its dated checkpoints as history; current contract details are in
[DATA_CONTRACTS.md](../public/docs/planning/DATA_CONTRACTS.md) and the implementation.
