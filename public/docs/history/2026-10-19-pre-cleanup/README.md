# Complete entrypoint archive: 2026-10-19

The six entrypoints below accumulated chronological checkpoints and instructions.
Their full pre-cleanup contents are preserved here so the current entrypoints
can focus on the next action. No investigation, example, command, comment or
historical result was condensed or deleted from these archived copies.

| Original location | Preserved copy |
|---|---|
| Repository `README.md` | [Project README](files/README.md) |
| `public/README.md` | [Portable-materials README](files/public/README.md) |
| `public/CODEX_HANDOFF.md` | [Full handoff](files/public/CODEX_HANDOFF.md) |
| `public/docs/reviews/NEXT_DEVELOPMENT_PROMPT.md` | [Next-development notes](files/public/docs/reviews/NEXT_DEVELOPMENT_PROMPT.md) |
| `public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md` | [Work-machine instructions and results](files/public/docs/reviews/WORK_MACHINE_REFERENCES_RUN.md) |
| `python-parser/README.md` | [Detailed application/CLI reference](files/python-parser/README.md) |

These are historical snapshots. Follow the [current project README](../../../../README.md)
and [documentation index](../../README.md) for today's workflow. Other dated
review and planning files retain their existing locations.

## What changed in the archived copies

Only relative Markdown link destinations were rebased for the archive location.
Links between these six documents point to their archived counterparts; other
links still point to their original targets. Fragments and local anchors remain
intact. Code fences, inline code and prose are untouched. Files use LF line
endings for portable checking; the manifest records each original newline form.

[manifest.json](manifest.json) records the original paths, original byte counts
and SHA-256 hashes, normalized hashes, archived hashes and all 315 link-target
replacements. Replacement offsets are UTF-8 byte positions in the archived
content after normalizing CRLF to LF. Reverse them from last to first, then
restore the original newline form to reconstruct each original byte stream.
All six reconstructions were verified before the live entrypoints were replaced.

To repeat that read-only integrity check from the repository root:

```bash
uv run --project python-parser --locked python -B - <<'PY'
import hashlib
import json
from pathlib import Path

archive = Path("public/docs/history/2026-10-19-pre-cleanup")
manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
for entry in manifest["files"]:
    data = (archive / entry["archive_path"]).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(data).hexdigest() == entry["archive_sha256_lf"]
    for edit in reversed(entry["link_rewrites"]):
        offset = edit["archive_byte_offset_lf"]
        target = edit["archive_target"].encode("utf-8")
        assert data[offset:offset + len(target)] == target
        data = (data[:offset] + edit["original_target"].encode("utf-8")
                + data[offset + len(target):])
    assert hashlib.sha256(data).hexdigest() == entry["original_sha256_lf"]
    if entry["original_newline"] == "crlf":
        data = data.replace(b"\n", b"\r\n")
    assert len(data) == entry["original_byte_count"]
    assert hashlib.sha256(data).hexdigest() == entry["original_sha256"]
print("All six originals reconstruct byte-for-byte.")
PY
```
