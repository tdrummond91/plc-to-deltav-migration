# Portable development materials

This directory contains independently synthetic inputs, generic helper code, and planning documents. Application source and tests stay in ../python-parser/. Real exports and all private derived outputs stay in ../confidential/.

Start here:

1. [Canonical Codex handoff](CODEX_HANDOFF.md).
2. [Synthetic fixture and user-run checks](fixtures/synthetic/README.md).
3. [Architecture](docs/planning/ARCHITECTURE.md) and [milestones](docs/planning/ROADMAP.md).
4. [Artifact validation record](VALIDATION.md).
5. [Fresh Git workflow](docs/planning/GIT_FRESH_START.md).
6. [Engineering review guide](docs/reviews/ENGINEERING_REVIEW_REPORT.md) and
   [invented HTML demonstration](examples/engineering-review-demo.html).

The fixtures are small parser inputs, not deployable controller projects. The
read-only inventory, reference, SFC and offline engineering-review CLI commands
are implemented. Editable engineering records, PCSD and FHX generation remain
planned. Download/open the invented HTML demonstration in a browser to explore
the report interface; GitHub's source view does not execute its navigation.

Edit this material deliberately as development advances. Do not direct production report output here. A file being in public/ does not automatically make it suitable for publication; review new content before committing.

For the first parsing discussion, read [L5X structure and branch locations](docs/planning/L5X_STRUCTURE.md).
