# Stage 1 validation

Date: 2026-10-08.

The delivered `tests/test_summarize_xml.py` suite completed successfully:
**19 tests passed** with Python from the existing local project environment.
Execution used `-B`, in-memory invented XML, and mocked output writes. No project
files, Git metadata, or confidential exports were modified.

Test coverage includes complete global/nested counts, repeated paths, optional
attributes, source-value exclusion, text/CDATA presence, split UTF-8 input chunks,
distinct parents, first-seen child order, namespace omission/collision handling,
malformed input, DTD/entity rejection, depth/path limits, same-input/output
protection, and JSON preparation before publication.

Not yet verified:
- execution on the actual confidential L5X;
- the real file's encoding, size, nesting, and possible extensions;
- writing/replacing the report on Tyler's filesystem;
- any Studio 5000 import, ladder semantics, or DeltaV behavior.

User-run test command from the repository root:

```bash
uv run --project python-parser python -B -m unittest discover \
  -s tools/l5x_inspect/tests -p 'test_*.py' -v
```

The Stage 1 run and inspection of its JSON are the next acceptance check.
