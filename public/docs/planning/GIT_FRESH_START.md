# Fresh local copy and Git history

Chosen approach: copy the current files to the new project name, omit old Git metadata and generated Python environments, review the copy, and initialize a new repository. A new empty GitHub repository will be linked separately. These are user-run commands; none were executed by Codex.

## 1. Copy while retaining the original

Run from Git Bash. Use a new destination; if that folder already contains independent edits, reconcile them before copying over it. Pause edits to the old folder while copying.

```bash
old_repo="$HOME/Desktop/coding-projects/allen-bradley-plc-to-mod-migration"
new_repo="$HOME/Desktop/coding-projects/plc-to-deltav-migration"

MSYS2_ARG_CONV_EXCL='*' robocopy.exe \
  "$(cygpath -w "$old_repo")" \
  "$(cygpath -w "$new_repo")" \
  /E /XJ /R:1 /W:1 \
  /XD .git .venv __pycache__ .pytest_cache .ruff_cache .mypy_cache

copy_status=$?
printf 'Robocopy exit code: %s\n' "$copy_status"
```

This copies ordinary and hidden files, including confidential inputs. /E includes empty directories; /XD excludes named directories; /XJ skips junctions; /R:1 /W:1 limits retries. cygpath supplies Windows paths, and MSYS2_ARG_CONV_EXCL preserves native switches.

Check FAILED in the summary. Codes >=8 report copy failures. Lower codes can include differences, so review the summary. A return code of 1 can be successful. The operation retains the source. See [Microsoft Robocopy](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy).

If files are locked against reading, the copy may also fail; keep the original and retry after the restart. Finish copy verification before adding new handoff files, so intended differences are easy to distinguish.

## 2. Check before treating the copy as the working project

Re-run the same Robocopy command with /L appended to list remaining differences without copying. Confirm needed source files and confidential inputs are present. This checks size/timestamp differences, not cryptographic equality. Where stronger assurance is needed, compare SHA-256 locally before deleting the original.

Do not delete the original until inputs, code, and the new Python environment have been checked. The original .git is the only preserved old commit/stash history in this approach. If you want that history after removing the old folder, archive it privately first. Keep such an archive under confidential/ or an approved private backup location.

Use COPY_COMMANDS.md in the handoff bundle to add the public fixture/docs and correct the root and nested ignore files. Then run uv sync and the fixture checks from the new python-parser folder.

## 3. Initialize only the new copy

From the new root, inspect hidden files first. If .git already exists, stop and inspect it; do not remove it blindly.

```bash
cd "$new_repo" || exit
ls -la
test ! -e .git && git init -b main
git check-ignore -v --no-index confidential/__ignore_probe__.txt
git check-ignore -v python-parser/uv.lock
```

The confidential probe should report the confidential rule without creating a file. The uv.lock check should print nothing and return 1, meaning it is not ignored. If it reports a rule, fix that rule before staging.

Stage the specific reviewed files:

```bash
git add -- .gitignore .gitattributes README.md CODEX_HANDOFF.md public \
  python-parser/.gitignore python-parser/main.py \
  python-parser/pyproject.toml python-parser/uv.lock python-parser/README.md
```

If python-parser/.python-version exists and contains only the intended Python version, include it too. Add other source files individually after review. Avoid force-adding ignored content.

Review locally:

```bash
git ls-files -- confidential/
git ls-files -ci --exclude-standard
git diff --cached --name-status
git diff --cached --stat
git diff --cached
git remote -v
```

The first two commands should show no files. The staged files must contain only reviewed source, public synthetic artifacts, docs, and dependency metadata. The fresh repository should have no remotes yet. Filenames alone do not establish that file contents are non-proprietary.

After reviewing the staged content:

```bash
git commit -m "chore: establish synthetic PLC development baseline"
```

## 4. Link a new GitHub repository later

Create a new empty GitHub repository without generated README, license, or ignore files. Choose visibility deliberately after reviewing the public bundle. Local folder name and GitHub repository name can match.

Before any push, fetch and inspect the destination state:

```bash
git remote add origin "PASTE_NEW_GITHUB_REPOSITORY_URL_HERE"
git fetch origin
git remote -v
git branch -r
git log --oneline --decorate --all -8
```

Review that output before choosing the first push command. Fetch updates local remote-tracking metadata, so Tyler runs it on this work machine. No push or history rewrite has been performed or scheduled.

New local history does not erase any old remote repository or past disclosure. The state of any previous remote is unverified.
