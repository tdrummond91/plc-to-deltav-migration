# Inspection helpers

Normal work-machine use starts with `bash ./run-work-check.sh` at the repository
root. The application lives in [python-parser](../python-parser/README.md).

The [l5x_inspect](l5x_inspect/README.md) folder contains separate source-profile,
rung-inspection, skeleton and synthetic-fixture helpers. Their own README
explains the commands and output boundaries. These helpers are development and
diagnostic tools; running them is not an extra step in the normal work check.

Their tests live under `l5x_inspect/tests/` and are included in the helper suite.
Actual plant input and derived plant records belong under ignored
`confidential/`; portable source and approved bounded feedback have separate
roles described in the [documentation index](../public/docs/README.md).
