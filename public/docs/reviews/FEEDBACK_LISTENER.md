# Automatic work-machine feedback

Tyler explicitly authorized automatic checks and bounded follow-up development
on 2026-10-13. This listener runs on the development PC. The work machine keeps
using `bash ./run-work-check.sh` and does not need another service.

## Operation

Windows Task Scheduler checks every five minutes while Tyler is logged in and
the PC is awake, and also checks at logon. It uses a dedicated checkout under
`%LOCALAPPDATA%/PLCWorkbench/feedback-listener/checkout`. It never pulls or edits
the primary interactive checkout. Normal Git fetch/fast-forward and push rules
apply; local edits, divergence and incomplete work are preserved.

Only newly received validated `public/inspection/work-check-*.json` reports
trigger an agent. Ordinary code pushes do not. Existing reports are baselined
when installing; `-InitialReport` can select one existing report for the first
development follow-up. Report identity includes path and Git blob, so a corrected
report is distinguishable. The poller claims a batch before launching, locks
against concurrent workers and saves local state atomically. Interrupted or
uncertain runs require investigation instead of automatically replaying changes.

The worker uses the already signed-in Codex CLI through `codex exec`. OpenAI
documents noninteractive runs using saved ChatGPT authentication; a separate API
key is not required. Each actual worker run consumes the account's applicable
Codex allowance. Idle Git checks do not invoke a model.
[Official OpenAI documentation](https://learn.chatgpt.com/docs/non-interactive-mode)

Runs inherit this PC's existing Codex permission configuration; the listener does
not change global settings or override sandbox/approval policy. Environment API
keys and a parent thread ID are excluded from the child invocation. The configured
model and reasoning preference are inherited as well.

The worker reads the project handoff, reviews returned evidence and completes one
bounded Phase 1 step with tests, independent review, notes and a normal push to
the existing `-pc` branch. The prompt does not authorize phase changes, main-branch
merges, FHX/PCSD implementation, private input access or changes to the listener.
The listener checks the worker's structured result and checkout/remote state;
a successful process exit alone does not establish a completed step.

`waiting_for_report` keeps watching for the next work-machine run. `needs_input`
or `phase_complete` pauses monitoring for Tyler's decision. Invalid reports,
failed/uncertain execution or unfinished Git state surface as `needs_attention`.
Questions and results are saved in local status/run files and the project notes.
This is a separate local Codex session: it does not automatically add a message
to the original interactive chat. No email/chat messages are sent.

The installed CLI exposes `queue`, but no reachable shared daemon was available
and waking this chat was not verified. The implemented listener therefore uses
the documented noninteractive execution path. The desktop app can be closed;
the PC must remain awake and the Windows account logged in. Sleeping/offline
time delays checks. Authentication/rate-limit failures require local attention.

## Controls from Git Bash

```bash
bash ./feedback-listener.sh status
bash ./feedback-listener.sh pause --reason "Working interactively"
bash ./feedback-listener.sh resume
```

Pause before starting interactive code changes. If a worker is already running,
let it finish and inspect its status before taking over; pause does not terminate
or discard a running worker. Fetch before continuing interactive Git work. A
worker's rejected push leaves its commit in the dedicated checkout for review.

Local configuration, state, locks, run logs and final result files live under
`%LOCALAPPDATA%/PLCWorkbench/feedback-listener/`, outside the repo. They are not
pushed to GitHub. `PLC_LISTENER_STATE_DIR` can select another state directory for
the shell controls. Do not copy account authentication files into the repository.

To disable the Windows task independently of the listener state, use Task
Scheduler's **PLC Workbench Feedback Listener** entry. Do not delete the checkout
or state while it contains unfinished work. The installation uses the current
user's interactive logon at limited privilege, without storing a Windows password.

## Installation and reproducibility

The development PC installation is performed after the code is committed and
pushed. For an explicitly requested installation on another development PC:

```powershell
& .\tools\feedback_listener\install.ps1
```

Requirements: Git, uv, Python's `pythonw.exe`, a native Codex CLI executable and
an existing ChatGPT login, plus GitHub authentication. The installer discovers
the npm-distributed native CLI or accepts `-CodexPath`. It refuses a different
existing configuration/task instead of overwriting it. Repeating a matching
installation preserves state and permits retry if task registration failed after
successful initialization. Incomplete/corrupted initialization is preserved for
investigation; it is not silently replaced or treated as a working installation.

Implementation: [poller](../../../tools/feedback_listener/listener.py),
[worker instructions](../../../tools/feedback_listener/PROMPT.txt),
[Windows installer](../../../tools/feedback_listener/install.ps1).

## Validation

On 2026-10-13, the application suite ran **232 tests (231 passed, one Windows
symlink skip)**, including all 24 listener tests. All **139 helper tests passed**.
The listener tests use real temporary Git origins/checkouts and a controlled
agent boundary: new/corrected reports, explicit initial selection, code-only
pushes, invalid blobs/symlinks, dirty/divergent trees, durable claims, interrupted
runs, pause/resume, corrupt local state, worker failures and actual pushed
commits. Successful output must preserve event ancestry, identify any new commit
and leave the dedicated checkout synchronized. No production input was opened.

An independent reviewer verified the final code, including fixes for question
handling, Git ancestry/commit evidence, corrupted state and task reinstallation
identity. PowerShell parsing, Bash syntax and Git whitespace checks passed.

A real native `codex exec` smoke run using ChatGPT login and the existing user
configuration completed with exit 0, used the shell to write/read a temporary
file, produced the required JSON and passed an independent parent-process file
read. An earlier attempt to introduce a separate workspace sandbox failed during
Windows helper setup. The listener now inherits the user's existing configuration
instead of introducing that override; no global permission settings were changed.

These checks establish the worker execution boundary and poller behavior.

## Development PC installation evidence (2026-10-13)

Implementation fde4fc2 was installed after pushing it. The registered task is
**PLC Workbench Feedback Listener**, using this account's interactive logon,
limited privilege, `pythonw.exe`, five-minute repetition and a logon trigger.
Overlapping scheduled invocations are ignored. A real scheduled invocation while
the listener was paused completed with `LastTaskResult=0`, verifying task launch.
The listener was paused only to finish installation notes before activation.

The installer selected
`public/inspection/work-check-20261013T234851Z-b10d84dc.json` as its initial report;
earlier work-check reports were baselined. The first resumed poll can therefore
continue from the report already returned, without another work-machine run.

These installation facts are not a live status display. Use
`bash ./feedback-listener.sh status` for the current state, last result, pending
report and local run-log location. The paused launch check alone does not verify
the scheduled environment's Git authentication or a completed development run.
