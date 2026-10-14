param(
    [string]$Repository = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path,
    [string]$StateDir = (Join-Path $env:LOCALAPPDATA "PLCWorkbench/feedback-listener"),
    [string]$CodexPath,
    [string]$InitialReport,
    [ValidateRange(1, 60)][int]$IntervalMinutes = 5,
    [string]$TaskName = "PLC Workbench Feedback Listener"
)
$ErrorActionPreference = "Stop"
$repoPath = (Resolve-Path -LiteralPath $Repository).Path
$statePath = [System.IO.Path]::GetFullPath($StateDir)
$checkoutPath = Join-Path $statePath "checkout"
$gitPath = (Get-Command git.exe -ErrorAction Stop).Source
if (-not $CodexPath) {
    $nativeCodex = Get-Command codex.exe -ErrorAction SilentlyContinue
    if ($nativeCodex) { $CodexPath = $nativeCodex.Source }
    else {
        $npmRoot = Split-Path (Get-Command codex.cmd -ErrorAction Stop).Source
        $nativeFiles = @(Get-ChildItem -Path (Join-Path $npmRoot "node_modules/@openai/codex/node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe") -File)
        if ($nativeFiles.Count -ne 1) { throw "Supply -CodexPath with the native codex.exe path." }
        $CodexPath = $nativeFiles[0].FullName
    }
}
$CodexPath = (Resolve-Path -LiteralPath $CodexPath).Path
$branch = (& $gitPath -C $repoPath branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or -not $branch.EndsWith("-pc")) { throw "Use the project's current -pc branch." }
$dirty = & $gitPath -C $repoPath status --porcelain
if ($LASTEXITCODE -ne 0 -or $dirty) { throw "Commit or preserve current work before installation; checkout must be clean." }
$remote = (& $gitPath -C $repoPath remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot read origin." }
$pythonPath = (& uv run --project (Join-Path $repoPath "python-parser") --locked python -c "import sys; print(sys.executable)").Trim()
if ($LASTEXITCODE -ne 0) { throw "Cannot locate the project's Python environment." }
$pythonWindowless = Join-Path (Split-Path $pythonPath) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonWindowless -PathType Leaf)) { throw "pythonw.exe is required for hidden scheduled checks." }
$listenerPath = Join-Path $PSScriptRoot "listener.py"
& $CodexPath login status
if ($LASTEXITCODE -ne 0) { throw "Sign into Codex with ChatGPT first." }
New-Item -ItemType Directory -Path $statePath -Force | Out-Null
if (-not (Test-Path -LiteralPath $checkoutPath)) {
    & $gitPath clone --single-branch --branch $branch -- $remote $checkoutPath
    if ($LASTEXITCODE -ne 0) { throw "Dedicated checkout clone failed; existing files are preserved." }
}
if (-not (Test-Path -LiteralPath (Join-Path $statePath "config.json"))) {
    $initArgs = @('-B', $listenerPath, '--state-dir', $statePath, 'init', '--repository', $repoPath, '--checkout', $checkoutPath, '--branch', $branch, '--git', $gitPath, '--codex', $CodexPath)
    if ($InitialReport) { $initArgs += @('--initial-report', $InitialReport) }
    & $pythonPath @initArgs
    if ($LASTEXITCODE -ne 0) { throw "Listener initialization failed." }
}
else {
    $saved = Get-Content -LiteralPath (Join-Path $statePath "config.json") -Raw | ConvertFrom-Json
    $expected = @{ repository = $repoPath; checkout = $checkoutPath; branch = $branch; git = $gitPath; codex = $CodexPath; origin = $remote }
    if ($saved.schema_version -ne 1) { throw "Existing listener configuration has an unsupported version." }
    foreach ($key in $expected.Keys) {
        if ($saved.$key -ne $expected[$key]) { throw "Existing listener configuration differs at $key; it was preserved." }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $statePath "state.json") -PathType Leaf)) {
        throw "Listener initialization is incomplete. Existing configuration was preserved; investigate before scheduling."
    }
    & $pythonPath -B $listenerPath --state-dir $statePath status
    if ($LASTEXITCODE -ne 0) { throw "Existing listener state needs investigation before scheduling." }
}
$arguments = '-B "' + $listenerPath + '" --state-dir "' + $statePath + '" poll'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$account = $identity.Name
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    $taskUser = $existingTask.Principal.UserId
    if ($taskUser.StartsWith('S-1-')) { $taskSid = $taskUser }
    else { $taskSid = ([System.Security.Principal.NTAccount]::new($taskUser)).Translate([System.Security.Principal.SecurityIdentifier]).Value }
    if ($existingTask.Actions.Count -ne 1 -or $existingTask.Actions[0].Execute -ne $pythonWindowless -or $existingTask.Actions[0].Arguments -ne $arguments -or $existingTask.Actions[0].WorkingDirectory -ne $repoPath -or $taskSid -ne $identity.User.Value -or $existingTask.Principal.RunLevel -ne 'Limited' -or $existingTask.Principal.LogonType -ne 'Interactive' -or $existingTask.Settings.MultipleInstances -ne 'IgnoreNew') {
        throw "A different task with this name exists; it was not overwritten."
    }
    if ($existingTask.State -eq 'Disabled') { throw "The matching listener task is disabled. Its state was preserved." }
    Write-Output "Listener is already installed. Its state and schedule were preserved."
    & $pythonPath -B $listenerPath --state-dir $statePath status
    if ($LASTEXITCODE -ne 0) { throw "Listener status check failed." }
    exit 0
}
$action = New-ScheduledTaskAction -Execute $pythonWindowless -Argument $arguments -WorkingDirectory $repoPath
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes($IntervalMinutes) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($periodic, $logon) -Principal $principal -Settings $settings -Description "Check approved PLC work-machine reports and run one bounded Codex follow-up." | Out-Null
Write-Output "Installed $TaskName. Checks every $IntervalMinutes minutes while this account is logged on."
& $pythonPath -B $listenerPath --state-dir $statePath status
if ($LASTEXITCODE -ne 0) { throw "Installed task, but listener status check failed." }
