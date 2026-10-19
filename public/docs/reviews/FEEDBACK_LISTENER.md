# Automatic work-machine feedback

Current distribution (2026-10-14): this is historical documentation for an
optional local development-PC tool. The launcher, `tools/feedback_listener/`
and application test loader are now untracked and ignored so they are absent
from work-machine checkouts. Existing files on the development PC were retained;
the task remains disabled and paused. Normal parser commands have no dependency
on these files. Installation/control commands below only apply to an existing
local copy; do not install or restore it on the work machine.

The temporary Git archive tag was retired during the 2026-10-19 history
cleanup. The current shared checkout continues to omit the listener. Keeping
this review does not re-enable it or establish a cause for the endpoint-security
detection.

Tyler explicitly authorized automatic checks and bounded follow-up development
on 2026-10-13. This listener runs on the development PC. The work machine keeps
using `bash ./run-work-check.sh` and does not need another service.

## Operation

Current hold (2026-10-14): after the restored poll described below, Tyler reported
endpoint-security alerts involving bash.exe on the work machine. The development
PC task is disabled again and listener state is paused with no pending worker.
The returned check tested `1419af7`, including the Git/process-host listener
regression tests. The alert rule and process attribution are not yet available;
do not treat this as a confirmed false positive or resume automatic execution
while the reported detection is being investigated.

Earlier restoration on 2026-10-14: the corrected scheduled task was enabled and the
listener was unpaused. The first production check ran at 00:14:29 America/Chicago,
completed with `LastTaskResult=0` and saved `waiting_for_report`, `paused=false`
and no pending claim. The verified GUI launcher is installed; the earlier
terminal-takeover hold is closed. Earlier smoke tests and that hold are preserved
below as history, not current operating instructions. Inspect live local status
before interactive changes.

When enabled, Windows Task Scheduler checks every five minutes while Tyler is logged in and
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
model and reasoning preference are inherited as well. Only this background worker
disables external completion notifications and TUI notifications with per-command
overrides. Interactive notifications and the global Codex configuration are unchanged.

The installer reads the Windows executable header to select a genuine GUI
`pythonw.exe` from the project's underlying Python installation. A virtual
environment's `pythonw.exe` can be a console-subsystem redirector and create a
Terminal tab before Python code runs. Existence and filename alone are insufficient.
The selected base interpreter and its console sibling run the listener and
isolated report validator, whose current imports use only the standard library.
Parser development and work-machine analysis continue to use the project environment.

On Windows, that verified GUI entry point now hosts the entire poll in
a private native pseudoconsole (ConPTY). Its console-Python child, Git, report
validator, Codex and ordinary descendants inherit that console. They do not
request a new console or attach to the user's Terminal. Redirected worker logs
remain ordinary byte-preserving files; the host separately retains at most 32 KiB
of terminal diagnostic output while continuously draining the stream.

The host preserves the direct child's exit code and waits for attached
descendants to finish naturally. It uses
[ReleasePseudoConsole](https://learn.microsoft.com/en-us/windows/console/releasepseudoconsole)
to detect when all clients have disconnected before freeing the session, avoiding
premature termination after only the direct child exits. This requires Windows
11 24H2 or later (or Windows Server 2025); installation checks the required APIs
before creating local listener state or registering a task. The parser and
work-machine runner retain their existing OS support; unsupported native-host
integration tests skip there, while missing-API rejection is still tested.
Worker notification overrides use the documented
[Codex notification configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#notifications).
This is a console-launch policy, not a restriction on a program explicitly opening
a GUI. Background work must not launch terminals, editors or browser windows.

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

`resume` clears the listener-state pause; it does not enable a disabled Windows
scheduled task. Both controls were restored after the launcher fix was verified.

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

Native launch/child failures pause the listener without clearing pending report
claims or history. `host-failure.json` saves the exit code and bounded local
diagnostic. If native read/wait/release operations fail while work is still active,
the host retains ownership and reports `host_problem` through `status`; it never
terminates an in-flight Git operation to enforce a timeout. `host-problem.json`
records whether that problem is still active. These files stay local.

## Installation and reproducibility

The development PC installation is performed after the code is committed and
pushed. For an explicitly requested installation on another development PC:

```powershell
& .\tools\feedback_listener\install.ps1
```

To migrate an existing listener installed with the old virtual-environment
launcher, use `install.ps1 -UpdateLauncher`. Migration requires the exact known
old action and matching task identity, refuses a running task and updates only
its action. The installer verifies the triggers, account/settings and enabled
state are preserved. A disabled task remains disabled; this switch never resumes
the listener's paused state. Tasks in other Task Scheduler folders are untouched.

Requirements: Windows 11 24H2+ with the required pseudoconsole APIs, Git, uv,
Python's `pythonw.exe`, a native Codex CLI executable and
an existing ChatGPT login, plus GitHub authentication. The installer discovers
the npm-distributed native CLI or accepts `-CodexPath`. It refuses a different
existing configuration/task instead of overwriting it. Repeating a matching
installation preserves state and permits retry if task registration failed after
successful initialization. Incomplete/corrupted initialization is preserved for
investigation; it is not silently replaced or treated as a working installation.

Archived implementation: [poller](https://github.com/tdrummond91/plc-to-deltav-migration/blob/832090bdad42a26e685515bd996eaded2c69d6b6/tools/feedback_listener/listener.py),
[native host](https://github.com/tdrummond91/plc-to-deltav-migration/blob/832090bdad42a26e685515bd996eaded2c69d6b6/tools/feedback_listener/windows_host.py),
[GUI launcher verification](https://github.com/tdrummond91/plc-to-deltav-migration/blob/832090bdad42a26e685515bd996eaded2c69d6b6/tools/feedback_listener/windows_launcher.py),
[worker instructions](https://github.com/tdrummond91/plc-to-deltav-migration/blob/832090bdad42a26e685515bd996eaded2c69d6b6/tools/feedback_listener/PROMPT.txt),
[Windows installer](https://github.com/tdrummond91/plc-to-deltav-migration/blob/832090bdad42a26e685515bd996eaded2c69d6b6/tools/feedback_listener/install.ps1).

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

## Silent execution attempt and recurring issue (2026-10-13)

Tyler reported the listener opening/focusing a terminal during other work. The
listener was idle after successfully pushing the address-shape slice at 833f900;
monitoring was paused while fixing its launch behavior. The original direct-child
`CREATE_NO_WINDOW` flag did not give normally spawned descendants a console to
inherit. That attempt used `CREATE_NEW_CONSOLE` with `STARTF_USESHOWWINDOW` / `SW_HIDE`
for Git, report validation and Codex. Per-invocation `notify=[]` and
`tui.notifications=false` suppress the inherited external completion helper and
TUI notifications for this worker only. No global configuration, permission policy,
task account or schedule was changed. The exact historical window was not captured;
these changes address the identified console inheritance gap and notification path.

All 247 application tests ran successfully (246 passed, one existing Windows
symlink skip); all 139 helper tests passed. This includes 25 listener tests and
a real Windows child/grandchild probe that
requires the same nonzero console handle and verifies both are invisible. The
worker-boundary test checks notification overrides and hidden launch options.
A real Codex smoke used the production `_agent` launch path with an isolated
temporary prompt, executed a Python probe through PowerShell, returned valid
structured output and passed independent inspection of the probe file. WinEvent
hooks for window-show and foreground-change events recorded zero events throughout
that run; the foreground window was unchanged. The temporary smoke repository held
only invented test code. Its first launch outside a Git repository was rejected
before execution; initializing the disposable repository allowed the normal check.
Independent review found no blockers; wording was corrected to distinguish
windowless Python validation from console programs, and to prefer Git Bash.

Background instructions now explicitly prohibit opening GUI applications and
identify Windows shell choices to avoid the system32 WSL launcher. This fix does
not attempt to suppress an application that deliberately opens its own GUI.
Check local status after deployment for current monitoring state.

Tyler subsequently reported that the command still opens and takes over Terminal.
On inspection, Terminal uses `windowingBehavior=useExisting`. The earlier WinEvent
test watched top-level foreground changes and window-show events, not which tab
was selected inside an existing window; its success did not establish that no
tab takeover occurred. The task was disabled and the listener paused. Current
process inspection found no active listener or worker. The exact command/title
and timing were not captured. Tyler confirmed that disabling the task stopped the
interruption, implicating the listener's launch path. No terminal preferences,
account permissions or unrelated processes were changed. The ConPTY replacement
above superseded the hidden-console flags; monitoring stayed off at that checkpoint.

Subsequent scheduled testing captured the missed root cause: the uv virtual
environment's `Scripts/pythonw.exe` has PE subsystem 3 (console). The base
installation's `pythonw.exe` has subsystem 2 (GUI). A scheduled launch with the
console redirector selected a new Terminal tab before the hosted worker started;
the same worker with the verified base GUI executable did not. The earlier
descendant-console explanation was incomplete. In-process tests with redirected
handles had masked the outer launch problem.

## Native headless host verification (2026-10-13)

The complete application suite ran **274 tests: 273 passed and one existing
Windows symlink test skipped**. All **139 helper tests passed**. The application
suite includes 30 listener cases, 12 native host cases and 10 launcher cases. Host checks exercise
windowless Python launch, inherited child/grandchild consoles, a descendant that
outlives its parent, binary pipes/files, large output, argument quoting, exact
nonzero exits, resource cleanup and native error reporting. Real temporary Git
repositories verify the hosted poll's behavior and durable failure state.

On this Windows build 26200 PC, all required APIs are present. A simulated missing
capability skipped the 11 native integration cases while still passing the
missing-API fail-closed case. Installer PowerShell parsing, Bash syntax and Git
whitespace checks passed. Independent code and documentation review found no
remaining blockers after the descendant-lifetime and compatibility fixes.

The installer also verifies GUI versus console PE headers, malformed executables,
fallback interpreter paths and the actual uv console-shim bypass. Listener launch
tests now use the verified GUI executable, including a real temporary Git poll.

A one-shot scheduled task using the original venv redirector completed functionally
but opened/selected a tenth Terminal tab. Repeating the real native Codex worker
with the verified base GUI executable passed: 36 passive UIAutomation snapshots
before/during/after showed the same nine tab runtime IDs and selected tab, with
zero selection events, zero foreground/window-show events and zero observer errors.
Task Scheduler and the hosted child both returned 0; the structured worker result
validated, and independent reads confirmed the invented nested probe succeeded.
The observation covered 2026-10-14 04:51:08-04:51:34 UTC. The disposable task used
Interactive/Limited/IgnoreNew without recurring triggers and was removed afterward.

A separate model-free base-GUI launch exercised the production `_validate_report`
fresh-interpreter path against the tracked approved report
`work-check-20261013T234851Z-b10d84dc.json`, successfully. The installer resolver
selects the same underlying executable used by the successful scheduled test.
Detailed smoke artifacts stay local under `%TEMP%/plc-listener-ui-boundary-gui-*`;
the preceding failed run is preserved separately for comparison.

This evidence covered the tested scheduled launch and native worker path; recurring
production execution stayed off during verification. The task was disabled and
listener state paused at that checkpoint. No global Terminal or Codex settings were changed.

After pushing implementation `6853aba`, `install.ps1 -UpdateLauncher` successfully
migrated the development PC's existing action to the verified base GUI interpreter.
The installer verified unchanged triggers, principal and settings; independent
checks confirmed task state `Disabled` and an unchanged listener-state file hash.
