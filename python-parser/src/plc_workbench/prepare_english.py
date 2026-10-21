"""Complete local English wording for the saved L5X before a review phase."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from .project_store import ProjectError
from .storage import StorageError
from .workspace import Workspace, _startup_project


def prepare(workspace: Workspace, *, retry: bool = False) -> tuple[dict, Path | None]:
    """Reuse the same cache and source identity as the interactive workspace."""
    state = workspace.state()
    if not state['active_run']:
        raise ProjectError('Run the work check and import its analysis before preparing English.')

    def require_same_run() -> None:
        if workspace.store.state()['active_run'] != state['active_run']:
            raise ProjectError('The active analysis changed during English preparation. Close the workspace and rerun; completed translations remain cached.')

    status = workspace.configure_translation({
        'presentation_mode': 'english', 'prepare': True, 'retry': retry,
        'run_id': state['active_run'],
    })
    last_print = -10.0
    while status['state'] == 'running':
        now = time.monotonic()
        if now - last_print >= 2:
            remaining = status.get('remaining_seconds')
            estimate = f"; about {max(1, round(remaining / 60))} min remaining" if remaining is not None else ''
            print(f"English preparation: {status['completed']}/{status['total']} unique texts"
                  f"; {status['cached']} reused{estimate}", flush=True)
            last_print = now
        time.sleep(.2)
        require_same_run()
        status = workspace.translation()
    if status['state'] != 'complete':
        return status, None

    # These are derived reading artifacts, not a replacement analysis import.
    # Each preparation has its own directory, so earlier exports stay intact.
    require_same_run()
    catalog = workspace.annotation_catalog()
    entries = workspace._translator().lookup_many(row['original'] for row in catalog['entries'])
    report = workspace.report('english')
    require_same_run()
    status['coverage_gaps'] = catalog['coverage'].get('namespace_exclusions', 0)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    destination = workspace.project.parent / 'english-analysis' / f'{stamp}-{uuid4().hex[:8]}'
    if destination.resolve() != destination:
        raise ProjectError('The English export folder must remain beside its project, without redirected paths.')
    destination.mkdir(parents=True, exist_ok=False)
    payload = {
        'schema_version': 1, 'run_id': state['active_run'], 'snapshot_id': catalog['snapshot_id'],
        'model_id': status['model_id'], 'coverage': catalog['coverage'],
        'limitations': catalog['limitations'], 'annotations': catalog['entries'], 'translations': entries,
        'purpose': 'Derived English reading aid; original L5X and reviewed decisions are unchanged.',
    }
    (destination / 'source-wording.json').write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    (destination / 'review-english.html').write_bytes(report)
    require_same_run()
    # The completion record is last: an interrupted folder is never a finished export.
    (destination / 'complete.json').write_text(json.dumps({
        'snapshot_id': catalog['snapshot_id'], 'run_id': state['active_run'],
        'status': 'partial' if status['needs_review'] or status['failed'] or status['coverage_gaps'] else 'complete',
        'scope': 'Eligible source annotations only; this is not engineering approval.',
        'coverage': catalog['coverage'], 'limitations': catalog['limitations'],
        'unique_texts': status['total'], 'needs_review': status['needs_review'],
        'files': ['source-wording.json', 'review-english.html'],
    }, indent=2) + '\n', encoding='utf-8')
    return status, destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        'Prepare English for the entire saved L5X analysis, using the local model and existing cache. '
        'Close the workspace first. No parser rerun, Git operation or model download.'))
    parser.add_argument('--project', type=Path, help='Use this existing private project; otherwise use the selected project.')
    parser.add_argument('--retry', action='store_true', help='Retry previously withheld/missing translations.')
    arguments = parser.parse_args(argv)
    workspace = None
    try:
        project, _ = _startup_project(arguments.project, automatic_import=True)
        if not project.is_file():
            raise ProjectError('No saved project is available. Run bash ./run-work-check.sh first.')
        workspace = Workspace(project, Path('confidential/workspaces/work-check'))
        status, destination = prepare(workspace, retry=arguments.retry)
        if destination is None:
            print(status.get('message') or 'English preparation did not finish. Completed translations remain cached.')
            return 1
        print(f"Prepared {status['completed']}/{status['total']} unique texts; {status['cached']} reused.")
        print(f"English report: {destination / 'review-english.html'}")
        print('Scope: source comments and descriptions; names, addresses and executable text remain original.')
        coverage = status.get('catalog_coverage', {})
        if coverage.get('structured_text_lines') or coverage.get('namespace_exclusions'):
            print('Some embedded or unsupported notes remain original; see report coverage and limitations.')
        print('Reopen with bash ./open-workbench.sh. English is selected; originals remain accessible.')
        if status['needs_review'] or status['failed'] or status.get('coverage_gaps'):
            print(f"{status['needs_review']} texts need wording review. The report marks them and retains original wording.")
            if status.get('coverage_gaps'):
                print(f"{status['coverage_gaps']} unsupported source notes were excluded; see the coverage details.")
            return 3
        return 0
    except KeyboardInterrupt:
        print('English preparation stopped. Completed translations remain cached; rerun to continue.')
        return 130
    except (ProjectError, StorageError) as exc:
        print(str(exc))
        return 1
    except Exception:
        print('English preparation could not finish. Original source and reviewed decisions were preserved.')
        return 1
    finally:
        if workspace is not None:
            workspace.close()


if __name__ == '__main__':
    raise SystemExit(main())
